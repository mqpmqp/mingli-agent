from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from importlib.resources import files
from typing import Literal, Mapping, Sequence

from .contracts.serialization import canonical_json, digest

PHASE22_SCHEMA_VERSION = "real-case-backtest-report@0.3"
PHASE22_METHOD_ID = "consented-deidentified-case-benchmark@0.3.0"
PHASE22_CALCULATION_VERSION = "0.3.0"
PHASE22_DECISION_ID = "PHASE_22_REAL_CASE_BENCHMARK_BACKTEST_R2_CONDITIONAL"
REGISTRY_RESOURCE = "phase22_real_case_registry_v0.1.json"
ALLOWED_LABELS = frozenset({"supportive", "mixed", "challenging"})
REQUIRED_UNIQUE_PERSON_CASES = 30
REQUIRED_GOLD_UNIQUE_PERSON_CASES = 10
MAX_SILVER_UNIQUE_PERSON_CASES = 20
REQUIRED_COMPARABLE_CLAIMS = 100
REQUIRED_SCENARIOS = 3


class Phase22InputError(ValueError):
    pass


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    person_case_id: str | None
    scenario_id: str | None
    case_class: str
    evidence_tier: str
    eligible_real_case: bool
    product_accuracy_eligible: bool
    comparable_claims: int
    matches: int
    mismatches: int
    unresolved: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ValidationClosureAssessment:
    validation_closure_passed: bool
    validation_closure_failures: tuple[str, ...]
    qualified_unique_person_cases: int
    qualified_gold_unique_person_cases: int
    qualified_silver_unique_person_cases: int
    qualified_scenario_records: int
    comparable_claims_count: int
    required_comparable_claims: int
    scenario_coverage_passed: bool
    review_coverage_passed: bool
    privacy_coverage_passed: bool


@dataclass(frozen=True)
class CaseBenchmarkReport:
    registry_id: str
    total_records: int
    eligible_real_cases: int
    eligible_gold_cases: int
    eligible_silver_cases: int
    synthetic_contract_cases: int
    comparable_claims: int
    matches: int
    mismatches: int
    unresolved: int
    exact_match_rate: str | None
    validation_closure_passed: bool
    validation_closure_failures: tuple[str, ...]
    qualified_unique_person_cases: int
    qualified_gold_unique_person_cases: int
    qualified_silver_unique_person_cases: int
    qualified_scenario_records: int
    comparable_claims_count: int
    required_comparable_claims: int
    scenario_coverage_passed: bool
    review_coverage_passed: bool
    privacy_coverage_passed: bool
    product_accuracy_claim_allowed: bool
    minimum_real_cases: int
    case_scores: tuple[CaseScore, ...]
    warnings: tuple[str, ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE22_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE22_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE22_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return json.loads(canonical_json(asdict(self)))


def load_case_registry() -> dict[str, object]:
    return json.loads(files("mingli.derived.data").joinpath(REGISTRY_RESOURCE).read_text(encoding="utf-8"))


def _validate_claims(value: object, field_name: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise Phase22InputError(f"{field_name} must be an object")
    result: dict[str, str] = {}
    for claim_id, label in value.items():
        key, normalized = str(claim_id), str(label)
        if not key or normalized not in ALLOWED_LABELS | {"unresolved"}:
            raise Phase22InputError(f"invalid {field_name} claim or label")
        result[key] = normalized
    return result


def _parse_timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field_name)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def evaluate_validation_closure(
    scores: Sequence[CaseScore],
    *,
    pii_leak_count: int | None,
) -> ValidationClosureAssessment:
    qualified = [score for score in scores if score.eligible_real_case]
    tiers_by_person: dict[str, set[str]] = {}
    for score in qualified:
        if score.person_case_id is not None:
            tiers_by_person.setdefault(score.person_case_id, set()).add(score.evidence_tier)

    gold_people = 0
    silver_people = 0
    conflicting_tiers = False
    for tiers in tiers_by_person.values():
        if tiers == {"gold"}:
            gold_people += 1
        elif tiers == {"silver"}:
            silver_people += 1
        else:
            conflicting_tiers = True
            silver_people += 1

    unique_people = len(tiers_by_person)
    comparable_claims = sum(score.comparable_claims for score in qualified)
    scenario_ids = {score.scenario_id for score in qualified if score.scenario_id is not None}
    scenario_coverage_passed = len(scenario_ids) >= REQUIRED_SCENARIOS
    review_failure_codes = {"real_case_missing_double_review", "real_case_missing_adjudication"}
    review_coverage_passed = bool(qualified) and not any(
        score.case_class == "real"
        and score.evidence_tier in {"gold", "silver"}
        and bool(review_failure_codes.intersection(score.warnings))
        for score in scores
    )
    privacy_failure_codes = {"real_case_not_deidentified"}
    privacy_coverage_passed = bool(qualified) and pii_leak_count == 0 and not any(
        score.case_class == "real"
        and score.evidence_tier in {"gold", "silver"}
        and bool(privacy_failure_codes.intersection(score.warnings))
        for score in scores
    )

    failures: list[str] = []
    if unique_people < REQUIRED_UNIQUE_PERSON_CASES:
        failures.append("insufficient_qualified_unique_person_cases")
    if gold_people < REQUIRED_GOLD_UNIQUE_PERSON_CASES:
        failures.append("insufficient_qualified_gold_unique_person_cases")
    if silver_people > MAX_SILVER_UNIQUE_PERSON_CASES:
        failures.append("too_many_qualified_silver_unique_person_cases")
    if comparable_claims < REQUIRED_COMPARABLE_CLAIMS:
        failures.append("insufficient_comparable_claims")
    if not scenario_coverage_passed:
        failures.append("scenario_coverage_not_met")
    if not review_coverage_passed:
        failures.append("review_coverage_not_met")
    if not privacy_coverage_passed:
        failures.append("privacy_coverage_not_met")
    if conflicting_tiers:
        failures.append("conflicting_person_tiers")

    return ValidationClosureAssessment(
        validation_closure_passed=not failures,
        validation_closure_failures=tuple(failures),
        qualified_unique_person_cases=unique_people,
        qualified_gold_unique_person_cases=gold_people,
        qualified_silver_unique_person_cases=silver_people,
        qualified_scenario_records=len(qualified),
        comparable_claims_count=comparable_claims,
        required_comparable_claims=REQUIRED_COMPARABLE_CLAIMS,
        scenario_coverage_passed=scenario_coverage_passed,
        review_coverage_passed=review_coverage_passed,
        privacy_coverage_passed=privacy_coverage_passed,
    )


def run_case_benchmark(registry: Mapping[str, object] | None = None) -> CaseBenchmarkReport:
    data = dict(registry or load_case_registry())
    registry_id = str(data.get("registry_id", "external-case-registry"))
    minimum = data.get("minimum_cases_for_product_claim", 30)
    pii_leak_count = data.get("pii_leak_count")
    cases = data.get("cases", [])
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 30 or not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise Phase22InputError("invalid registry contract")
    if pii_leak_count is not None and (isinstance(pii_leak_count, bool) or not isinstance(pii_leak_count, int) or pii_leak_count < 0):
        raise Phase22InputError("pii_leak_count must be a non-negative integer")
    scores: list[CaseScore] = []
    seen: set[str] = set()
    for index, item in enumerate(cases, 1):
        if not isinstance(item, Mapping):
            raise Phase22InputError("case records must be objects")
        case_id = str(item.get("case_id") or f"case:{index}")
        if case_id in seen:
            raise Phase22InputError(f"duplicate case_id: {case_id}")
        seen.add(case_id)
        case_class = str(item.get("case_class"))
        if case_class not in {"real", "synthetic"}:
            raise Phase22InputError("case_class must be real or synthetic")
        evidence_tier = str(item.get("evidence_tier", "bronze"))
        if evidence_tier not in {"gold", "silver", "bronze"}:
            raise Phase22InputError("evidence_tier must be gold, silver or bronze")
        person_case_id = str(item.get("person_case_id", "")).strip() or None
        scenario_id = str(item.get("scenario_id", "")).strip() or None
        warnings: list[str] = []
        eligible = case_class == "real"
        if eligible and person_case_id is None:
            eligible = False; warnings.append("real_case_missing_person_case_id")
        if eligible and scenario_id is None:
            eligible = False; warnings.append("real_case_missing_scenario_id")
        if eligible and item.get("consent_status") != "granted":
            eligible = False; warnings.append("real_case_missing_consent")
        if eligible and item.get("deidentified") is not True:
            eligible = False; warnings.append("real_case_not_deidentified")
        if eligible and str(item.get("source_ref", "")).strip() == "":
            eligible = False; warnings.append("real_case_missing_source_ref")
        if eligible and not str(item.get("source_ref", "")).startswith("authorized:"):
            eligible = False; warnings.append("real_case_source_not_authorized")
        if eligible and str(item.get("consent_record_id", "")).strip() == "":
            eligible = False; warnings.append("real_case_missing_consent_record")
        if eligible and item.get("provenance_class") != "external_observation":
            eligible = False; warnings.append("real_case_missing_external_provenance")
        if eligible:
            try:
                observed_at = _parse_timestamp(item.get("observed_at"), "observed_at")
            except ValueError:
                eligible = False; warnings.append("real_case_invalid_observation_date")
        if eligible and item.get("double_review_complete") is not True:
            eligible = False; warnings.append("real_case_missing_double_review")
        if eligible and item.get("review_disagreement") is True and item.get("adjudication_status") != "completed":
            eligible = False; warnings.append("real_case_missing_adjudication")
        if eligible and evidence_tier == "gold":
            if item.get("prospective_prediction") is not True:
                eligible = False; warnings.append("gold_case_not_prospective")
            elif not str(item.get("prediction_freeze_hash", "")).strip():
                eligible = False; warnings.append("gold_case_missing_freeze_hash")
            else:
                try:
                    frozen_at = _parse_timestamp(item.get("prediction_frozen_at"), "prediction_frozen_at")
                    if frozen_at >= observed_at:
                        raise ValueError("prediction must be frozen before observation")
                except (TypeError, ValueError):
                    eligible = False; warnings.append("gold_case_invalid_freeze_order")
        if eligible and evidence_tier == "silver" and item.get("retrospective_external_support") is not True:
            eligible = False; warnings.append("silver_case_missing_external_support")
        if eligible and evidence_tier == "bronze":
            eligible = False; warnings.append("bronze_case_excluded_from_benchmark")
        accuracy_eligible = eligible and evidence_tier == "gold"
        predicted = _validate_claims(item.get("predicted_claims", {}), "predicted_claims")
        observed = _validate_claims(item.get("observed_claims", {}), "observed_claims")
        comparable = matches = mismatches = unresolved = 0
        for claim_id in sorted(set(predicted) | set(observed)):
            left, right = predicted.get(claim_id, "unresolved"), observed.get(claim_id, "unresolved")
            if left == "unresolved" or right == "unresolved":
                unresolved += 1
            else:
                comparable += 1
                if left == right: matches += 1
                else: mismatches += 1
        if case_class == "synthetic":
            warnings.append("synthetic_case_excluded_from_accuracy")
        scores.append(CaseScore(case_id, person_case_id, scenario_id, case_class, evidence_tier, eligible, accuracy_eligible, comparable, matches, mismatches, unresolved, tuple(warnings)))
    real_scores = [score for score in scores if score.eligible_real_case]
    gold_scores = [score for score in scores if score.product_accuracy_eligible]
    silver_scores = [score for score in real_scores if score.evidence_tier == "silver"]
    comparable = sum(score.comparable_claims for score in real_scores)
    matches = sum(score.matches for score in real_scores)
    mismatches = sum(score.mismatches for score in real_scores)
    unresolved = sum(score.unresolved for score in real_scores)
    eligible_count = len(real_scores)
    closure = evaluate_validation_closure(scores, pii_leak_count=pii_leak_count)
    claim_allowed = (
        closure.qualified_gold_unique_person_cases >= minimum
        and closure.review_coverage_passed
        and closure.privacy_coverage_passed
    )
    rate = format(matches / comparable, ".4f") if comparable else None
    warnings = ["retrospective_exact_match_is_not_prospective_validity", "synthetic_cases_never_count_as_real", "silver_cases_never_count_toward_product_accuracy_claim"]
    if eligible_count == 0:
        warnings.append("no_eligible_real_cases_accuracy_not_evaluated")
    if closure.qualified_gold_unique_person_cases < minimum:
        warnings.append("minimum_gold_case_threshold_not_met_for_product_accuracy_claim")
    if not closure.review_coverage_passed:
        warnings.append("review_coverage_not_met_for_product_accuracy_claim")
    if not closure.privacy_coverage_passed:
        warnings.append("privacy_coverage_not_met_for_product_accuracy_claim")
    body = {"registry_id": registry_id, "total_records": len(scores), "eligible_real_cases": eligible_count, "eligible_gold_cases": len(gold_scores), "eligible_silver_cases": len(silver_scores), "synthetic_contract_cases": sum(score.case_class == "synthetic" for score in scores), "comparable_claims": comparable, "matches": matches, "mismatches": mismatches, "unresolved": unresolved, "exact_match_rate": rate, **asdict(closure), "product_accuracy_claim_allowed": claim_allowed, "minimum_real_cases": minimum, "case_scores": [asdict(score) for score in scores], "warnings": warnings}
    return CaseBenchmarkReport(
        registry_id=registry_id,
        total_records=len(scores),
        eligible_real_cases=eligible_count,
        eligible_gold_cases=len(gold_scores),
        eligible_silver_cases=len(silver_scores),
        synthetic_contract_cases=sum(score.case_class == "synthetic" for score in scores),
        comparable_claims=comparable,
        matches=matches,
        mismatches=mismatches,
        unresolved=unresolved,
        exact_match_rate=rate,
        validation_closure_passed=closure.validation_closure_passed,
        validation_closure_failures=closure.validation_closure_failures,
        qualified_unique_person_cases=closure.qualified_unique_person_cases,
        qualified_gold_unique_person_cases=closure.qualified_gold_unique_person_cases,
        qualified_silver_unique_person_cases=closure.qualified_silver_unique_person_cases,
        qualified_scenario_records=closure.qualified_scenario_records,
        comparable_claims_count=closure.comparable_claims_count,
        required_comparable_claims=closure.required_comparable_claims,
        scenario_coverage_passed=closure.scenario_coverage_passed,
        review_coverage_passed=closure.review_coverage_passed,
        privacy_coverage_passed=closure.privacy_coverage_passed,
        product_accuracy_claim_allowed=claim_allowed,
        minimum_real_cases=minimum,
        case_scores=tuple(scores),
        warnings=tuple(warnings),
        canonical_hash=digest({"record_type": "CaseBenchmarkReport", "payload": body}),
    )


def benchmark_phase22() -> dict[str, object]:
    empty = run_case_benchmark()
    synthetic = run_case_benchmark({"registry_id": "contract-test", "minimum_cases_for_product_claim": 30, "cases": [{"case_id": "synthetic:1", "case_class": "synthetic", "predicted_claims": {"career:2024": "supportive"}, "observed_claims": {"career:2024": "supportive"}}]})
    ineligible = run_case_benchmark({"registry_id": "ineligible-test", "minimum_cases_for_product_claim": 30, "cases": [{"case_id": "real:1", "person_case_id": "person:1", "scenario_id": "career", "case_class": "real", "consent_status": "granted", "deidentified": True, "source_ref": "fixture", "predicted_claims": {}, "observed_claims": {}}]})
    checks = [(empty.eligible_real_cases == 0, "empty_registry"), (not empty.validation_closure_passed, "empty_validation_hold"), (empty.exact_match_rate is None, "no_fake_rate"), (not empty.product_accuracy_claim_allowed, "no_product_claim"), (synthetic.synthetic_contract_cases == 1 and synthetic.eligible_real_cases == 0, "synthetic_exclusion"), (synthetic.exact_match_rate is None, "synthetic_no_rate"), (ineligible.eligible_real_cases == 0, "authorization_gate"), ("real_case_source_not_authorized" in ineligible.case_scores[0].warnings, "source_gate"), (synthetic.canonical_hash == run_case_benchmark(json.loads(json.dumps({"registry_id": "contract-test", "minimum_cases_for_product_claim": 30, "cases": [{"case_id": "synthetic:1", "case_class": "synthetic", "predicted_claims": {"career:2024": "supportive"}, "observed_claims": {"career:2024": "supportive"}}]}))).canonical_hash, "determinism")]
    failures = [name for ok, name in checks if not ok]
    return {"assertions_total": len(checks), "passed": len(checks) - len(failures), "failed": len(failures), "unresolved": 0, "failures": failures, "real_case_count": empty.eligible_real_cases, "validation_closure_passed": empty.validation_closure_passed, "product_accuracy_claim_allowed": empty.product_accuracy_claim_allowed}
