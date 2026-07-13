from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from importlib.resources import files
from typing import Literal, Mapping, Sequence

from .contracts.serialization import canonical_json, digest

PHASE22_SCHEMA_VERSION = "real-case-backtest-report@0.1"
PHASE22_METHOD_ID = "consented-deidentified-case-benchmark@0.1.0"
PHASE22_CALCULATION_VERSION = "0.1.0"
PHASE22_DECISION_ID = "PHASE_22_REAL_CASE_BENCHMARK_BACKTEST_R1_CONDITIONAL"
REGISTRY_RESOURCE = "phase22_real_case_registry_v0.1.json"
ALLOWED_LABELS = frozenset({"supportive", "mixed", "challenging"})


class Phase22InputError(ValueError):
    pass


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    case_class: str
    eligible_real_case: bool
    comparable_claims: int
    matches: int
    mismatches: int
    unresolved: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CaseBenchmarkReport:
    registry_id: str
    total_records: int
    eligible_real_cases: int
    synthetic_contract_cases: int
    comparable_claims: int
    matches: int
    mismatches: int
    unresolved: int
    exact_match_rate: str | None
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


def run_case_benchmark(registry: Mapping[str, object] | None = None) -> CaseBenchmarkReport:
    data = dict(registry or load_case_registry())
    registry_id = str(data.get("registry_id", "external-case-registry"))
    minimum = data.get("minimum_cases_for_product_claim", 30)
    cases = data.get("cases", [])
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1 or not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise Phase22InputError("invalid registry contract")
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
        warnings: list[str] = []
        eligible = case_class == "real"
        if eligible and item.get("consent_status") != "granted":
            eligible = False; warnings.append("real_case_missing_consent")
        if eligible and item.get("deidentified") is not True:
            eligible = False; warnings.append("real_case_not_deidentified")
        if eligible and str(item.get("source_ref", "")).strip() == "":
            eligible = False; warnings.append("real_case_missing_source_ref")
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
        scores.append(CaseScore(case_id, case_class, eligible, comparable, matches, mismatches, unresolved, tuple(warnings)))
    real_scores = [score for score in scores if score.eligible_real_case]
    comparable = sum(score.comparable_claims for score in real_scores)
    matches = sum(score.matches for score in real_scores)
    mismatches = sum(score.mismatches for score in real_scores)
    unresolved = sum(score.unresolved for score in real_scores)
    eligible_count = len(real_scores)
    claim_allowed = eligible_count >= minimum and comparable > 0
    rate = format(matches / comparable, ".4f") if comparable else None
    warnings = ["retrospective_exact_match_is_not_prospective_validity", "synthetic_cases_never_count_as_real"]
    if eligible_count == 0:
        warnings.append("no_eligible_real_cases_accuracy_not_evaluated")
    if eligible_count < minimum:
        warnings.append("minimum_real_case_threshold_not_met")
    body = {"registry_id": registry_id, "total_records": len(scores), "eligible_real_cases": eligible_count, "synthetic_contract_cases": sum(score.case_class == "synthetic" for score in scores), "comparable_claims": comparable, "matches": matches, "mismatches": mismatches, "unresolved": unresolved, "exact_match_rate": rate, "product_accuracy_claim_allowed": claim_allowed, "minimum_real_cases": minimum, "case_scores": [asdict(score) for score in scores], "warnings": warnings}
    return CaseBenchmarkReport(**body, canonical_hash=digest({"record_type": "CaseBenchmarkReport", "payload": body}))  # type: ignore[arg-type]


def benchmark_phase22() -> dict[str, object]:
    empty = run_case_benchmark()
    synthetic = run_case_benchmark({"registry_id": "contract-test", "minimum_cases_for_product_claim": 1, "cases": [{"case_id": "synthetic:1", "case_class": "synthetic", "predicted_claims": {"career:2024": "supportive"}, "observed_claims": {"career:2024": "supportive"}}]})
    ineligible = run_case_benchmark({"registry_id": "ineligible-test", "minimum_cases_for_product_claim": 1, "cases": [{"case_id": "real:1", "case_class": "real", "consent_status": "missing", "deidentified": True, "source_ref": "fixture", "predicted_claims": {}, "observed_claims": {}}]})
    eligible = run_case_benchmark({"registry_id": "eligible-test", "minimum_cases_for_product_claim": 1, "cases": [{"case_id": "real:ok", "case_class": "real", "consent_status": "granted", "deidentified": True, "source_ref": "user-confirmed:fixture", "predicted_claims": {"c": "mixed", "w": "supportive"}, "observed_claims": {"c": "mixed", "w": "challenging"}}]})
    checks = [(empty.eligible_real_cases == 0, "empty_registry"), (empty.exact_match_rate is None, "no_fake_rate"), (not empty.product_accuracy_claim_allowed, "no_product_claim"), (synthetic.synthetic_contract_cases == 1 and synthetic.eligible_real_cases == 0, "synthetic_exclusion"), (synthetic.exact_match_rate is None, "synthetic_no_rate"), (ineligible.eligible_real_cases == 0, "consent_gate"), (eligible.eligible_real_cases == 1, "eligible_case"), (eligible.comparable_claims == 2 and eligible.matches == 1 and eligible.exact_match_rate == "0.5000", "metric"), (eligible.canonical_hash == run_case_benchmark(json.loads(json.dumps({"registry_id": "eligible-test", "minimum_cases_for_product_claim": 1, "cases": [{"case_id": "real:ok", "case_class": "real", "consent_status": "granted", "deidentified": True, "source_ref": "user-confirmed:fixture", "predicted_claims": {"c": "mixed", "w": "supportive"}, "observed_claims": {"c": "mixed", "w": "challenging"}}]}))).canonical_hash, "determinism")]
    failures = [name for ok, name in checks if not ok]
    return {"assertions_total": len(checks), "passed": len(checks) - len(failures), "failed": len(failures), "unresolved": 0, "failures": failures, "real_case_count": empty.eligible_real_cases, "product_accuracy_claim_allowed": empty.product_accuracy_claim_allowed}
