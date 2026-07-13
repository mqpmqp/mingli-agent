from __future__ import annotations

from datetime import datetime
import json
from importlib.resources import files
from typing import Mapping, Sequence

from .contracts.serialization import digest
from .derived.static_engine import BRANCHES, STEMS
from .phase8_engine import validate_import_origin
from .phase15 import build_phase15_fixture, evaluate_bazi_tengod_domains
from .phase15_contracts import record_digest as phase15_record_digest
from .phase16_contracts import (
    BASE_DOMAINS,
    JUDGEMENT_LABELS,
    PHASE16_CALCULATION_VERSION,
    PHASE16_DECISION_ID,
    PHASE16_METHOD_ID,
    PHASE16_SCHEMA_VERSION,
    BaseDomainContract,
    BaseDomainRuleMatch,
    BaziBaseDomainContractResult,
    DomainFacetAssessment,
    Phase16BenchmarkResult,
    Phase16InputError,
    record_digest,
)

DEFAULT_PHASE16_PROFILE_ID = "base-domain-contract-r1@0.1"
RULE_RESOURCE = "phase16_base_domain_rules_v0.1.json"
ASSERTION_RESOURCE = "phase16_base_domain_assertions_v0.1.json"
METADATA_FIELDS = {
    "canonical_hash",
    "schema_version",
    "method_id",
    "calculation_version",
    "prediction_validity",
    "domain_judgement_validity",
    "domain_contract_validity",
}
BLOCKED_OUTPUTS = {
    "auspiciousness",
    "good_bad",
    "fortune_judgement",
    "event_prediction",
    "promotion_prediction",
    "dismissal_prediction",
    "job_offer_prediction",
    "profit_prediction",
    "loss_prediction",
    "income_amount_prediction",
    "investment_recommendation",
    "marriage_prediction",
    "reunion_prediction",
    "breakup_prediction",
    "affair_prediction",
    "partner_count_prediction",
    "natural_language_renderer",
}


def _resource(name: str, label: str) -> dict[str, object]:
    value = json.loads(files("mingli.derived.data").joinpath(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def load_phase16_base_rules() -> dict[str, object]:
    return _resource(RULE_RESOURCE, "Phase 16 base-domain rule manifest")


def load_phase16_assertions() -> dict[str, object]:
    return _resource(ASSERTION_RESOURCE, "Phase 16 assertion manifest")


def get_phase16_rule_profile(profile_id: str = DEFAULT_PHASE16_PROFILE_ID) -> dict[str, object]:
    profile = load_phase16_base_rules()
    if profile.get("profile_id") != profile_id:
        raise ValueError(f"unsupported Phase 16 profile: {profile_id}")
    result = dict(profile)
    result["canonical_hash"] = digest({
        "record_type": "Phase16BaseDomainRuleProfile",
        "payload": {key: value for key, value in result.items() if key != "canonical_hash"},
    })
    return result


def validate_phase16_rules() -> tuple[str, ...]:
    issues: list[str] = []
    try:
        profile = get_phase16_rule_profile()
        if profile.get("decision_id") != PHASE16_DECISION_ID:
            issues.append("decision_id is invalid")
        if profile.get("reviewed") is not True:
            issues.append("reviewed must be true")
        if tuple(profile.get("domains", ())) != BASE_DOMAINS:
            issues.append("domains must exactly match Phase 16 base domains")
        required = profile.get("required_facets")
        if not isinstance(required, Mapping) or set(required) != set(BASE_DOMAINS):
            issues.append("required_facets must cover all base domains")
            required = {}
        rules = profile.get("rules")
        if not isinstance(rules, list) or not rules:
            issues.append("rules must be a non-empty array")
            rules = []
        seen: set[str] = set()
        covered: dict[str, set[str]] = {domain: set() for domain in BASE_DOMAINS}
        for item in rules:
            if not isinstance(item, Mapping):
                issues.append("rule entry must be an object")
                continue
            rule_id = str(item.get("rule_id", ""))
            domain = str(item.get("domain", ""))
            facet = str(item.get("facet_code", ""))
            if not rule_id or rule_id in seen:
                issues.append(f"duplicate or empty rule_id: {rule_id}")
            seen.add(rule_id)
            if domain not in BASE_DOMAINS:
                issues.append(f"unsupported rule domain: {domain}")
                continue
            if not isinstance(item.get("theme_any"), list) or not item["theme_any"]:
                issues.append(f"{rule_id} theme_any must be non-empty")
            if item.get("status") != "reviewed":
                issues.append(f"{rule_id} must remain reviewed")
            if not str(item.get("claim_code", "")) or not str(item.get("statement", "")).strip():
                issues.append(f"{rule_id} claim_code and statement are required")
            priority = item.get("priority")
            if not isinstance(priority, int) or not 0 <= priority <= 100:
                issues.append(f"{rule_id} priority must be between 0 and 100")
            covered[domain].add(facet)
        if isinstance(required, Mapping):
            for domain in BASE_DOMAINS:
                facets = required.get(domain)
                if not isinstance(facets, list) or not facets or len(facets) != len(set(facets)):
                    issues.append(f"{domain} required facets are invalid")
                elif covered[domain] != set(str(value) for value in facets):
                    issues.append(f"{domain} rule facets do not exactly cover required facets")
        if not profile.get("explicit_exclusions"):
            issues.append("explicit_exclusions are required")
        if not profile.get("claim_boundary_codes"):
            issues.append("claim_boundary_codes are required")
        if not str(profile.get("canonical_hash", "")).startswith("sha256:"):
            issues.append("profile canonical hash is invalid")
    except (ValueError, TypeError) as exc:
        issues.append(str(exc))
    return tuple(issues)


def phase16_schema_summary() -> dict[str, object]:
    return {
        "decision_id": PHASE16_DECISION_ID,
        "schema_version": PHASE16_SCHEMA_VERSION,
        "method_id": PHASE16_METHOD_ID,
        "calculation_version": PHASE16_CALCULATION_VERSION,
        "profile_id": DEFAULT_PHASE16_PROFILE_ID,
        "prediction_validity": "not_evaluated",
        "domain_contract_validity": "base_rules_only",
        "domains": list(BASE_DOMAINS),
        "judgement_labels": list(JUDGEMENT_LABELS),
        "output_boundary": "career_wealth_relationship_base_contract_no_concrete_event_prediction",
    }


def _verify_phase15(value: Mapping[str, object]) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase16InputError("Phase 15 Domain Judgement Result missing canonical_hash")
    if value.get("schema_version") != "bazi-tengod-domain-judgement-result@0.1":
        raise Phase16InputError("unsupported Phase 15 Domain Judgement Result schema")
    if value.get("prediction_validity") != "not_evaluated":
        raise Phase16InputError("Phase 15 prediction_validity must be not_evaluated")
    if value.get("domain_judgement_validity") != "candidate_only":
        raise Phase16InputError("Phase 15 domain_judgement_validity must be candidate_only")
    judgements = value.get("domain_judgements")
    if not isinstance(judgements, list) or not judgements:
        raise Phase16InputError("Phase 15 domain_judgements must be a non-empty array")
    seen: set[tuple[str, str]] = set()
    for item in judgements:
        if not isinstance(item, Mapping):
            raise Phase16InputError("Phase 15 domain judgement entry must be an object")
        key = (str(item.get("target_id")), str(item.get("domain")))
        if key in seen:
            raise Phase16InputError(f"duplicate Phase 15 target/domain judgement: {key[0]}:{key[1]}")
        seen.add(key)
        if item.get("canonical_digest") != phase15_record_digest("DomainJudgementCandidate", item):
            raise Phase16InputError("Phase 15 domain judgement canonical_digest mismatch")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    if found != phase15_record_digest("BaziTenGodDomainJudgementResult", body):
        raise Phase16InputError("Phase 15 Domain Judgement Result canonical_hash mismatch")
    return found


def _rules(profile: Mapping[str, object], domain: str) -> tuple[Mapping[str, object], ...]:
    raw = profile["rules"]
    assert isinstance(raw, list)
    return tuple(sorted(
        (item for item in raw if isinstance(item, Mapping) and item.get("domain") == domain),
        key=lambda item: (-int(item["priority"]), str(item["rule_id"])),
    ))


def _build_matches(
    judgement: Mapping[str, object],
    profile: Mapping[str, object],
) -> tuple[BaseDomainRuleMatch, ...]:
    domain = str(judgement["domain"])
    themes = {str(value) for value in judgement.get("active_theme_codes", [])}
    records: list[BaseDomainRuleMatch] = []
    for rule in _rules(profile, domain):
        matched = tuple(sorted(themes & {str(value) for value in rule["theme_any"]}))
        if not matched:
            continue
        payload = {
            "match_id": f"base-rule-match:{judgement['target_id']}:{rule['rule_id']}",
            "rule_id": str(rule["rule_id"]),
            "target_id": str(judgement["target_id"]),
            "domain": domain,
            "facet_code": str(rule["facet_code"]),
            "matched_theme_codes": list(matched),
            "judgement_label": str(judgement["judgement_label"]),
            "confidence": str(judgement["confidence"]),
            "priority": int(rule["priority"]),
            "claim_code": str(rule["claim_code"]),
            "source_judgement_id": str(judgement["judgement_id"]),
            "source_judgement_digest": str(judgement["canonical_digest"]),
            "profile_id": str(profile["profile_id"]),
        }
        records.append(BaseDomainRuleMatch(
            match_id=payload["match_id"],
            rule_id=payload["rule_id"],
            target_id=payload["target_id"],
            domain=domain,
            facet_code=payload["facet_code"],
            matched_theme_codes=matched,
            judgement_label=payload["judgement_label"],
            confidence=payload["confidence"],  # type: ignore[arg-type]
            priority=payload["priority"],
            claim_code=payload["claim_code"],
            source_judgement_id=payload["source_judgement_id"],
            source_judgement_digest=payload["source_judgement_digest"],
            profile_id=payload["profile_id"],
            canonical_digest=record_digest("BaseDomainRuleMatch", payload),
        ))
    return tuple(records)


def _build_facets(
    judgement: Mapping[str, object],
    matches: Sequence[BaseDomainRuleMatch],
    profile: Mapping[str, object],
) -> tuple[DomainFacetAssessment, ...]:
    required = profile["required_facets"]
    assert isinstance(required, Mapping)
    domain = str(judgement["domain"])
    records: list[DomainFacetAssessment] = []
    for facet in required[domain]:
        facet_matches = tuple(item for item in matches if item.facet_code == facet)
        matched = bool(facet_matches)
        payload = {
            "assessment_id": f"domain-facet:{judgement['target_id']}:{domain}:{facet}",
            "target_id": str(judgement["target_id"]),
            "domain": domain,
            "facet_code": str(facet),
            "judgement_label": str(judgement["judgement_label"]) if matched else "unresolved",
            "confidence": str(judgement["confidence"]) if matched else "low",
            "claim_codes": sorted({item.claim_code for item in facet_matches}),
            "rule_match_ids": [item.match_id for item in facet_matches],
            "source_judgement_id": str(judgement["judgement_id"]),
            "evidence_status": "matched" if matched else "unresolved",
        }
        records.append(DomainFacetAssessment(
            assessment_id=payload["assessment_id"],
            target_id=payload["target_id"],
            domain=domain,
            facet_code=payload["facet_code"],
            judgement_label=payload["judgement_label"],
            confidence=payload["confidence"],  # type: ignore[arg-type]
            claim_codes=tuple(payload["claim_codes"]),
            rule_match_ids=tuple(payload["rule_match_ids"]),
            source_judgement_id=payload["source_judgement_id"],
            evidence_status=payload["evidence_status"],  # type: ignore[arg-type]
            canonical_digest=record_digest("DomainFacetAssessment", payload),
        ))
    return tuple(records)


def _build_contract(
    judgement: Mapping[str, object],
    matches: Sequence[BaseDomainRuleMatch],
    facets: Sequence[DomainFacetAssessment],
    profile: Mapping[str, object],
) -> BaseDomainContract:
    boundary_codes = sorted(set(
        [str(value) for value in judgement.get("claim_boundary_codes", [])]
        + [str(value) for value in profile["claim_boundary_codes"]]
    ))
    payload = {
        "contract_id": f"base-domain-contract:{judgement['target_id']}:{judgement['domain']}",
        "target_id": str(judgement["target_id"]),
        "target_type": str(judgement["target_type"]),
        "domain": str(judgement["domain"]),
        "sequence_index": judgement.get("sequence_index"),
        "label_year": judgement.get("label_year"),
        "start_age": judgement.get("start_age"),
        "end_age": judgement.get("end_age"),
        "start_instant_utc": str(judgement["start_instant_utc"]),
        "end_instant_utc": str(judgement["end_instant_utc"]),
        "judgement_label": str(judgement["judgement_label"]),
        "confidence": str(judgement["confidence"]),
        "facet_assessment_ids": [item.assessment_id for item in facets],
        "matched_rule_ids": sorted({item.rule_id for item in matches}),
        "active_theme_codes": sorted({str(value) for value in judgement.get("active_theme_codes", [])}),
        "top_ten_gods": [str(value) for value in judgement.get("top_ten_gods", [])],
        "reality_override_direction": judgement.get("reality_override_direction"),
        "reality_evidence_ids": [str(value) for value in judgement.get("reality_evidence_ids", [])],
        "confidence_rationale_codes": [str(value) for value in judgement.get("confidence_rationale_codes", [])],
        "claim_boundary_codes": boundary_codes,
        "source_judgement_id": str(judgement["judgement_id"]),
        "source_judgement_digest": str(judgement["canonical_digest"]),
    }
    return BaseDomainContract(
        contract_id=payload["contract_id"],
        target_id=payload["target_id"],
        target_type=payload["target_type"],
        domain=payload["domain"],
        sequence_index=payload["sequence_index"],  # type: ignore[arg-type]
        label_year=payload["label_year"],  # type: ignore[arg-type]
        start_age=payload["start_age"],  # type: ignore[arg-type]
        end_age=payload["end_age"],  # type: ignore[arg-type]
        start_instant_utc=payload["start_instant_utc"],
        end_instant_utc=payload["end_instant_utc"],
        judgement_label=payload["judgement_label"],
        confidence=payload["confidence"],  # type: ignore[arg-type]
        facet_assessment_ids=tuple(payload["facet_assessment_ids"]),
        matched_rule_ids=tuple(payload["matched_rule_ids"]),
        active_theme_codes=tuple(payload["active_theme_codes"]),
        top_ten_gods=tuple(payload["top_ten_gods"]),
        reality_override_direction=payload["reality_override_direction"],  # type: ignore[arg-type]
        reality_evidence_ids=tuple(payload["reality_evidence_ids"]),
        confidence_rationale_codes=tuple(payload["confidence_rationale_codes"]),
        claim_boundary_codes=tuple(boundary_codes),
        source_judgement_id=payload["source_judgement_id"],
        source_judgement_digest=payload["source_judgement_digest"],
        canonical_digest=record_digest("BaseDomainContract", payload),
    )


def _indexes(contracts: Sequence[BaseDomainContract]) -> tuple[
    dict[str, tuple[str, ...]], dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]
]:
    years: dict[str, set[str]] = {}
    ages: dict[str, set[str]] = {}
    domains: dict[str, set[str]] = {domain: set() for domain in BASE_DOMAINS}
    for item in contracts:
        domains[item.domain].add(item.contract_id)
        if item.label_year is not None:
            years.setdefault(str(item.label_year), set()).add(item.contract_id)
        else:
            try:
                start = datetime.fromisoformat(item.start_instant_utc.replace("Z", "+00:00")).year
                end = datetime.fromisoformat(item.end_instant_utc.replace("Z", "+00:00")).year
                if 0 <= end - start <= 30:
                    for year in range(start, end + 1):
                        years.setdefault(str(year), set()).add(item.contract_id)
            except ValueError:
                pass
        if item.start_age is not None:
            end_age = item.end_age if item.end_age is not None else item.start_age
            if 0 <= end_age - item.start_age <= 30:
                for age in range(item.start_age, end_age + 1):
                    ages.setdefault(str(age), set()).add(item.contract_id)
    return (
        {key: tuple(sorted(value)) for key, value in sorted(years.items(), key=lambda row: int(row[0]))},
        {key: tuple(sorted(value)) for key, value in sorted(ages.items(), key=lambda row: int(row[0]))},
        {key: tuple(sorted(value)) for key, value in sorted(domains.items())},
    )


def evaluate_base_domain_contracts(
    phase15_result: Mapping[str, object],
    *,
    profile_id: str = DEFAULT_PHASE16_PROFILE_ID,
    requested_outputs: Sequence[str] = (),
) -> BaziBaseDomainContractResult:
    if set(requested_outputs) & BLOCKED_OUTPUTS:
        raise Phase16InputError("Phase 16 cannot return concrete events, guaranteed outcomes, investments, or renderer outputs")
    if not isinstance(phase15_result, Mapping) or not phase15_result:
        raise Phase16InputError("Phase 15 Domain Judgement Result is required")
    profile = get_phase16_rule_profile(profile_id)
    phase15_hash = _verify_phase15(phase15_result)
    raw_judgements = phase15_result["domain_judgements"]
    assert isinstance(raw_judgements, list)
    selected = tuple(sorted(
        (item for item in raw_judgements if isinstance(item, Mapping) and item.get("domain") in BASE_DOMAINS),
        key=lambda item: (str(item["target_id"]), BASE_DOMAINS.index(str(item["domain"]))),
    ))
    if not selected:
        raise Phase16InputError("Phase 15 result contains no supported base-domain judgements")
    targets = {str(item["target_id"]) for item in selected}
    if len(selected) != len(targets) * len(BASE_DOMAINS):
        raise Phase16InputError("Phase 15 base-domain partition is incomplete")
    matches: list[BaseDomainRuleMatch] = []
    facets: list[DomainFacetAssessment] = []
    contracts: list[BaseDomainContract] = []
    unresolved: list[dict[str, object]] = []
    for judgement in selected:
        current_matches = _build_matches(judgement, profile)
        current_facets = _build_facets(judgement, current_matches, profile)
        contract = _build_contract(judgement, current_matches, current_facets, profile)
        matches.extend(current_matches)
        facets.extend(current_facets)
        contracts.append(contract)
        for facet in current_facets:
            if facet.evidence_status == "unresolved":
                unresolved.append({
                    "code": "base_domain_facet_unresolved",
                    "target_id": facet.target_id,
                    "domain": facet.domain,
                    "facet_code": facet.facet_code,
                    "source": "phase16",
                })
        if contract.judgement_label == "unresolved":
            unresolved.append({
                "code": "base_domain_contract_unresolved",
                "target_id": contract.target_id,
                "domain": contract.domain,
                "source": "phase15",
            })
    contract_tuple = tuple(contracts)
    year_index, age_index, domain_index = _indexes(contract_tuple)
    judgement_counts = {label: 0 for label in JUDGEMENT_LABELS}
    confidence_counts = {level: 0 for level in ("high", "medium", "low")}
    for item in contract_tuple:
        judgement_counts[item.judgement_label] += 1
        confidence_counts[item.confidence] += 1
    provenance = {
        "phase15_result_hash": phase15_hash,
        "phase15_profile_id": phase15_result.get("profile_id"),
        "phase16_profile_hash": profile["canonical_hash"],
        "source_ids": list(profile.get("source_ids", [])),
        "source_reality_evidence_ids": sorted({value for item in contract_tuple for value in item.reality_evidence_ids}),
    }
    body = {
        "phase15_result_hash": phase15_hash,
        "profile_id": profile_id,
        "rule_set_hash": profile["canonical_hash"],
        "rule_matches": [item.to_dict() for item in matches],
        "facet_assessments": [item.to_dict() for item in facets],
        "domain_contracts": [item.to_dict() for item in contract_tuple],
        "year_index": {key: list(value) for key, value in year_index.items()},
        "age_index": {key: list(value) for key, value in age_index.items()},
        "domain_index": {key: list(value) for key, value in domain_index.items()},
        "judgement_counts": judgement_counts,
        "confidence_counts": confidence_counts,
        "provenance_index": provenance,
        "warnings": [
            "base_domain_rules_only",
            "phase15_candidate_judgement_preserved",
            "unmatched_facet_remains_unresolved",
            "verified_reality_override_preserved_not_expanded",
            "prediction_validity_not_evaluated",
            "no_concrete_career_wealth_relationship_event_prediction",
        ],
        "unresolved": unresolved,
    }
    return BaziBaseDomainContractResult(
        phase15_result_hash=phase15_hash,
        profile_id=profile_id,
        rule_set_hash=str(profile["canonical_hash"]),
        rule_matches=tuple(matches),
        facet_assessments=tuple(facets),
        domain_contracts=contract_tuple,
        year_index=year_index,
        age_index=age_index,
        domain_index=domain_index,
        judgement_counts=judgement_counts,
        confidence_counts=confidence_counts,
        provenance_index=provenance,
        warnings=tuple(body["warnings"]),
        unresolved=tuple(unresolved),
        canonical_hash=record_digest("BaziBaseDomainContractResult", body),
    )


def _verify_phase16_result(value: Mapping[str, object]) -> None:
    if value.get("schema_version") != PHASE16_SCHEMA_VERSION:
        raise Phase16InputError("unsupported Phase 16 result schema")
    found = value.get("canonical_hash")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    if found != record_digest("BaziBaseDomainContractResult", body):
        raise Phase16InputError("Phase 16 result canonical_hash mismatch")


def query_base_domain_contracts(
    result: BaziBaseDomainContractResult | Mapping[str, object],
    *,
    domain: str | None = None,
    year: int | None = None,
    age: int | None = None,
    target_id: str | None = None,
) -> tuple[dict[str, object], ...]:
    if domain is not None and domain not in BASE_DOMAINS:
        raise Phase16InputError(f"unsupported domain: {domain}")
    selectors = sum(value is not None for value in (year, age, target_id))
    if selectors != 1:
        raise Phase16InputError("exactly one of year, age, or target_id is required")
    payload = result.to_dict() if isinstance(result, BaziBaseDomainContractResult) else dict(result)
    _verify_phase16_result(payload)
    contracts = payload.get("domain_contracts")
    if not isinstance(contracts, list):
        raise Phase16InputError("Phase 16 domain_contracts must be an array")
    identifiers: set[str]
    if year is not None:
        identifiers = set(payload.get("year_index", {}).get(str(year), []))  # type: ignore[union-attr]
    elif age is not None:
        identifiers = set(payload.get("age_index", {}).get(str(age), []))  # type: ignore[union-attr]
    else:
        identifiers = {str(item.get("contract_id")) for item in contracts if isinstance(item, Mapping) and item.get("target_id") == target_id}
    return tuple(
        dict(item)
        for item in contracts
        if isinstance(item, Mapping)
        and item.get("contract_id") in identifiers
        and (domain is None or item.get("domain") == domain)
    )


def build_phase16_fixture(day_stem: str, month_branch: str) -> dict[str, object]:
    graph, interaction, trend = build_phase15_fixture(day_stem, month_branch)
    return evaluate_bazi_tengod_domains(graph, interaction, trend).to_dict()


def benchmark_phase16() -> Phase16BenchmarkResult:
    failures = list(validate_phase16_rules())
    assertions_total = passed = 0

    def check(condition: bool, message: str) -> None:
        nonlocal assertions_total, passed
        assertions_total += 1
        if condition:
            passed += 1
        else:
            failures.append(message)

    profile = get_phase16_rule_profile()
    required = profile["required_facets"]
    assert isinstance(required, Mapping)
    for day_stem in STEMS:
        for month_branch in BRANCHES:
            source = build_phase16_fixture(day_stem, month_branch)
            result = evaluate_base_domain_contracts(source)
            reordered = evaluate_base_domain_contracts(json.loads(json.dumps(source, ensure_ascii=False, sort_keys=True)))
            target_ids = {str(item["target_id"]) for item in source["domain_judgements"] if item["domain"] in BASE_DOMAINS}
            contract_ids = {item.contract_id for item in result.domain_contracts}
            checks = [
                result.schema_version == PHASE16_SCHEMA_VERSION,
                result.method_id == PHASE16_METHOD_ID,
                result.calculation_version == PHASE16_CALCULATION_VERSION,
                result.prediction_validity == "not_evaluated",
                result.domain_contract_validity == "base_rules_only",
                result.canonical_hash.startswith("sha256:"),
                result.canonical_hash == reordered.canonical_hash,
                result.phase15_result_hash == source["canonical_hash"],
                result.rule_set_hash == profile["canonical_hash"],
                len(result.domain_contracts) == len(target_ids) * len(BASE_DOMAINS),
                {item.target_id for item in result.domain_contracts} == target_ids,
                {item.domain for item in result.domain_contracts} == set(BASE_DOMAINS),
                len(contract_ids) == len(result.domain_contracts),
                all(item.judgement_label in JUDGEMENT_LABELS for item in result.domain_contracts),
                all(item.confidence in {"high", "medium", "low"} for item in result.domain_contracts),
                all(item.source_judgement_digest.startswith("sha256:") for item in result.domain_contracts),
                all(item.canonical_digest.startswith("sha256:") for item in result.domain_contracts),
                all("base_domain_rule_only" in item.claim_boundary_codes for item in result.domain_contracts),
                all(item.domain in BASE_DOMAINS for item in result.rule_matches),
                all(item.matched_theme_codes for item in result.rule_matches),
                all(item.canonical_digest.startswith("sha256:") for item in result.rule_matches),
                all(item.domain in BASE_DOMAINS for item in result.facet_assessments),
                all(item.evidence_status in {"matched", "unresolved"} for item in result.facet_assessments),
                all(item.canonical_digest.startswith("sha256:") for item in result.facet_assessments),
                len(result.facet_assessments) == len(target_ids) * sum(len(required[domain]) for domain in BASE_DOMAINS),
                all(
                    {facet.facet_code for facet in result.facet_assessments if facet.target_id == target and facet.domain == domain}
                    == set(required[domain])
                    for target in target_ids for domain in BASE_DOMAINS
                ),
                set(result.domain_index) == set(BASE_DOMAINS),
                all(identifier in contract_ids for values in result.domain_index.values() for identifier in values),
                bool(result.year_index),
                bool(result.age_index),
                sum(result.judgement_counts.values()) == len(result.domain_contracts),
                sum(result.confidence_counts.values()) == len(result.domain_contracts),
                all(key not in result.to_dict() for key in BLOCKED_OUTPUTS),
                all(item.judgement_label == next(source_item["judgement_label"] for source_item in source["domain_judgements"] if source_item["judgement_id"] == item.source_judgement_id) for item in result.domain_contracts),
                all(item.confidence == next(source_item["confidence"] for source_item in source["domain_judgements"] if source_item["judgement_id"] == item.source_judgement_id) for item in result.domain_contracts),
            ]
            for index, condition in enumerate(checks, 1):
                check(condition, f"{day_stem}{month_branch}: check {index} failed")

    source = build_phase16_fixture(STEMS[0], BRANCHES[2])
    target_source = next(item for item in source["domain_judgements"] if item["domain"] == "career")
    graph, interaction, trend = build_phase15_fixture(STEMS[0], BRANCHES[2])
    reality_source = evaluate_bazi_tengod_domains(graph, interaction, trend, reality_evidence=({
        "target_id": target_source["target_id"],
        "domain": "career",
        "direction": "support",
        "detail": "verified career reality",
        "weight": "10",
        "verified": True,
        "source_id": "phase16-benchmark-reality",
    },)).to_dict()
    preserved = evaluate_base_domain_contracts(reality_source)
    preserved_item = next(item for item in preserved.domain_contracts if item.target_id == target_source["target_id"] and item.domain == "career")
    check(preserved_item.reality_override_direction == "support", "Phase 15 reality override direction was not preserved")
    check(preserved_item.confidence == "high", "Phase 15 scoped high confidence was not preserved")
    check(bool(preserved_item.reality_evidence_ids), "Phase 15 reality evidence ids were not preserved")
    year_contract = next(item for item in preserved.domain_contracts if item.label_year is not None)
    age_contract = next(item for item in preserved.domain_contracts if item.start_age is not None)
    check(bool(query_base_domain_contracts(preserved, year=year_contract.label_year, domain=year_contract.domain)), "year query failed")
    check(bool(query_base_domain_contracts(preserved, age=age_contract.start_age, domain=age_contract.domain)), "age query failed")
    check(len(query_base_domain_contracts(preserved, target_id=year_contract.target_id)) == len(BASE_DOMAINS), "target query failed")
    check(assertions_total >= int(load_phase16_assertions()["minimum_expected_assertions_total"]), "assertion matrix is too small")

    return Phase16BenchmarkResult(
        assertions_total=assertions_total,
        passed=passed,
        failed=len(failures),
        unresolved=0,
        schema_failures=sum("schema" in item for item in failures),
        provenance_failures=sum("source" in item or "provenance" in item for item in failures),
        hash_mismatches=sum("hash" in item for item in failures),
        rule_coverage_failures=sum("rule" in item or "facet" in item for item in failures),
        contract_partition_failures=sum("partition" in item for item in failures),
        reality_preservation_failures=sum("reality" in item for item in failures),
        query_failures=sum("query" in item for item in failures),
        prediction_boundary_failures=sum("prediction" in item or "blocked" in item for item in failures),
        failures=tuple(failures),
    )
