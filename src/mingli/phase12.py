from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from importlib.resources import files
from typing import Mapping, Sequence

from .contracts.serialization import digest
from .derived.static_engine import BRANCHES, CONTROLS, GENERATES, STEMS, STEM_ELEMENT
from .phase8_engine import validate_import_origin
from .phase11 import build_regulation_fixture_inputs, evaluate_bazi_regulation
from .phase11_contracts import record_digest as phase11_record_digest
from .phase12_contracts import (
    BaziXiJiEvaluationResult,
    ElementRoleAssignment,
    PHASE12_CALCULATION_VERSION,
    PHASE12_DECISION_ID,
    PHASE12_METHOD_ID,
    PHASE12_SCHEMA_VERSION,
    Phase12BenchmarkResult,
    Phase12InputError,
    RoleEvidenceRecord,
    StemCarrierRole,
    XIJI_ROLES,
    record_digest,
)
from .phase9_contracts import ELEMENTS

DEFAULT_PHASE12_PROFILE_ID = "xiji-role-classification-r1@0.1"
PROFILE_RESOURCE = "phase12_xiji_role_profiles_v0.1.json"
ASSERTION_RESOURCE = "phase12_xiji_role_assertions_v0.1.json"
METADATA_FIELDS = {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}
BLOCKED_OUTPUTS = {
    "luck_cycle_prediction", "annual_prediction", "event_prediction", "career_prediction",
    "wealth_prediction", "relationship_prediction", "health_prediction", "natural_language_renderer",
}


def _decimal(value: object, name: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise Phase12InputError(f"{name} must be decimal-compatible") from exc
    if not number.is_finite():
        raise Phase12InputError(f"{name} must be finite")
    return number


def _score(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")


def _load_resource(name: str, label: str) -> dict[str, object]:
    value = json.loads(files("mingli.derived.data").joinpath(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def load_phase12_xiji_profiles() -> dict[str, object]:
    return _load_resource(PROFILE_RESOURCE, "Phase 12 profile manifest")


def load_phase12_xiji_assertions() -> dict[str, object]:
    return _load_resource(ASSERTION_RESOURCE, "Phase 12 assertion manifest")


def get_xiji_role_profile(profile_id: str = DEFAULT_PHASE12_PROFILE_ID) -> dict[str, object]:
    raw = load_phase12_xiji_profiles().get("profiles")
    if not isinstance(raw, list):
        raise ValueError("profiles must be an array")
    for item in raw:
        if isinstance(item, dict) and item.get("profile_id") == profile_id:
            result = dict(item)
            result["canonical_hash"] = digest({
                "record_type": "XiJiRoleProfile",
                "payload": {key: value for key, value in result.items() if key != "canonical_hash"},
            })
            return result
    raise ValueError(f"unsupported Phase 12 profile: {profile_id}")


def validate_phase12_profiles() -> tuple[str, ...]:
    issues: list[str] = []
    try:
        profile = get_xiji_role_profile()
        thresholds = profile.get("thresholds")
        required = {
            "minimum_yongshen_score", "minimum_xishen_score", "direct_jishen_contradiction",
            "direct_jishen_excess", "top_tie_delta",
        }
        if profile.get("reviewed") is not True:
            issues.append("reviewed must be true")
        if set(profile.get("roles", [])) != set(XIJI_ROLES):
            issues.append("roles must cover all Phase 12 roles")
        if not isinstance(thresholds, dict) or set(thresholds) != required:
            issues.append("thresholds must exactly cover Phase 12 thresholds")
        else:
            for key, value in thresholds.items():
                if _decimal(value, str(key)) < 0:
                    issues.append(f"threshold {key} must be non-negative")
        if len(set(profile.get("independence_groups", []))) < 2:
            issues.append("at least two independence groups are required")
        if not str(profile["canonical_hash"]).startswith("sha256:"):
            issues.append("profile canonical hash is invalid")
    except (ValueError, Phase12InputError) as exc:
        issues.append(str(exc))
    return tuple(issues)


def phase12_schema_summary() -> dict[str, object]:
    return {
        "decision_id": PHASE12_DECISION_ID,
        "schema_version": PHASE12_SCHEMA_VERSION,
        "method_id": PHASE12_METHOD_ID,
        "calculation_version": PHASE12_CALCULATION_VERSION,
        "profile_id": DEFAULT_PHASE12_PROFILE_ID,
        "prediction_validity": "not_evaluated",
        "roles": list(XIJI_ROLES),
        "elements": list(ELEMENTS),
        "output_boundary": "xiji_role_classification_only_no_luck_cycle_or_event_prediction",
    }


def _verify_regulation(value: Mapping[str, object]) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase12InputError("Phase 11 Regulation Result missing canonical_hash")
    if value.get("schema_version") != "bazi-regulation-yongshen-candidate-result@0.1":
        raise Phase12InputError("unsupported Phase 11 Regulation Result schema")
    if value.get("prediction_validity") != "not_evaluated":
        raise Phase12InputError("Phase 11 Regulation Result prediction_validity must be not_evaluated")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    if found != phase11_record_digest("BaziRegulationEvaluationResult", body):
        raise Phase12InputError("Phase 11 Regulation Result canonical_hash mismatch")
    return found


def _candidate_map(value: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw = value.get("candidates")
    if not isinstance(raw, list) or len(raw) != 5:
        raise Phase12InputError("Phase 11 Regulation Result must contain five candidates")
    result: dict[str, Mapping[str, object]] = {}
    for item in raw:
        if not isinstance(item, Mapping) or item.get("element") not in ELEMENTS or not isinstance(item.get("candidate_id"), str):
            raise Phase12InputError("Phase 11 candidate identity is malformed")
        if item.get("canonical_digest") != phase11_record_digest("YongShenCandidate", item):
            raise Phase12InputError("Phase 11 candidate canonical_digest mismatch")
        element = str(item["element"])
        if element in result:
            raise Phase12InputError("Phase 11 candidate elements must be unique")
        result[element] = item
    if set(result) != set(ELEMENTS):
        raise Phase12InputError("Phase 11 candidates must cover all five elements")
    return result


def _value(candidate: Mapping[str, object], key: str) -> Decimal:
    if key == "excess_risk":
        availability = candidate.get("availability")
        if not isinstance(availability, Mapping):
            raise Phase12InputError("candidate availability must be an object")
        return _decimal(availability.get("candidate_excess_risk", "0"), key)
    return _decimal(candidate.get(key, "0"), key)


def _relation(source: str, target: str) -> str:
    if source == target:
        return "same_element"
    if GENERATES[source] == target:
        return "generates"
    if GENERATES[target] == source:
        return "generated_by"
    if CONTROLS[source] == target:
        return "controls"
    if CONTROLS[target] == source:
        return "controlled_by"
    return "none"


def _derive_roles(regulation: Mapping[str, object], candidates: Mapping[str, Mapping[str, object]], profile: Mapping[str, object]):
    thresholds = profile["thresholds"]
    assert isinstance(thresholds, Mapping)
    minimum_yong = _decimal(thresholds["minimum_yongshen_score"], "minimum_yongshen_score")
    minimum_xi = _decimal(thresholds["minimum_xishen_score"], "minimum_xishen_score")
    ji_contradiction = _decimal(thresholds["direct_jishen_contradiction"], "direct_jishen_contradiction")
    ji_excess = _decimal(thresholds["direct_jishen_excess"], "direct_jishen_excess")
    tie_delta = _decimal(thresholds["top_tie_delta"], "top_tie_delta")
    eligible = [
        element for element, candidate in candidates.items()
        if str(candidate.get("status")) in {"supported", "conditionally_supported", "secondary"}
        and _value(candidate, "combined_score") >= minimum_yong
    ]
    eligible.sort(key=lambda element: (_value(candidates[element], "combined_score"), str(candidates[element]["candidate_id"])), reverse=True)
    roles: dict[str, str] = {}
    statuses: dict[str, str] = {}
    unresolved: list[dict[str, object]] = []
    yongshen: tuple[str, ...] = ()
    if eligible:
        top = _value(candidates[eligible[0]], "combined_score")
        tied = tuple(sorted(element for element in eligible if top - _value(candidates[element], "combined_score") <= tie_delta))
        if len(tied) > 1:
            for element in tied:
                roles[element], statuses[element] = "unresolved", "unresolved"
            unresolved.append({"code": "equal_rank_yongshen_candidates", "elements": list(tied), "source": "phase12"})
        elif regulation.get("unresolved"):
            roles[eligible[0]], statuses[eligible[0]] = "unresolved", "unresolved"
            unresolved.append({"code": "phase11_unresolved_retained", "source": "phase11"})
        else:
            yongshen = (eligible[0],)
            roles[eligible[0]] = "yongshen"
            statuses[eligible[0]] = "resolved" if candidates[eligible[0]].get("status") == "supported" else "conditional"
    else:
        unresolved.append({"code": "no_eligible_yongshen_candidate", "source": "phase12"})
    jishen: set[str] = set()
    for element, candidate in candidates.items():
        if element in roles:
            continue
        if candidate.get("status") == "contradicted" or _value(candidate, "contradiction_score") >= ji_contradiction:
            jishen.add(element)
        elif candidate.get("status") not in {"unavailable", "unresolved"} and _value(candidate, "excess_risk") >= ji_excess:
            jishen.add(element)
    for element in jishen:
        roles[element], statuses[element] = "jishen", "resolved"
    xishen: set[str] = set()
    if yongshen:
        target = yongshen[0]
        for element, candidate in candidates.items():
            if element in roles:
                continue
            supportive = GENERATES[element] == target or CONTROLS[element] in jishen
            if supportive and candidate.get("status") not in {"contradicted", "conflicted", "unresolved", "unavailable"} and _value(candidate, "combined_score") >= minimum_xi:
                xishen.add(element)
        for element in xishen:
            roles[element] = "xishen"
            statuses[element] = "resolved" if candidates[element].get("status") == "supported" else "conditional"
    for element in ELEMENTS:
        if element in roles:
            continue
        harms_support = bool(yongshen and CONTROLS[element] == yongshen[0]) or CONTROLS[element] in xishen
        feeds_ji = GENERATES[element] in jishen
        if harms_support or feeds_ji:
            roles[element], statuses[element] = "choushen", "resolved"
        else:
            roles[element] = "xianshen"
            statuses[element] = "conditional" if candidates[element].get("status") in {"conflicted", "unresolved"} else "resolved"
    return roles, statuses, unresolved


def _assignment(element: str, role: str, status: str, candidate: Mapping[str, object], yongshen: tuple[str, ...], regulation_hash: str, profile_id: str):
    rationale = [f"phase11_status:{candidate.get('status')}", f"phase12_role:{role}"]
    rationale.append({
        "yongshen": "unique_highest_eligible_regulation_candidate",
        "xishen": "supports_yongshen_or_controls_jishen",
        "jishen": "contradiction_or_excess_threshold",
        "choushen": "harms_support_or_feeds_jishen",
        "xianshen": "no_dominant_role_trigger",
        "unresolved": "semantic_tie_or_upstream_unresolved",
    }[role])
    payload = {
        "assignment_id": f"xiji:element:{element}",
        "element": element,
        "role": role,
        "status": status,
        "phase11_candidate_id": str(candidate["candidate_id"]),
        "phase11_status": str(candidate.get("status")),
        "combined_score": _score(_value(candidate, "combined_score")),
        "contradiction_score": _score(_value(candidate, "contradiction_score")),
        "excess_risk": _score(_value(candidate, "excess_risk")),
        "relation_to_yongshen": _relation(element, yongshen[0]) if yongshen else "not_resolved",
        "rationale_codes": sorted(set(rationale)),
        "source_result_hashes": [regulation_hash],
        "profile_id": profile_id,
    }
    return ElementRoleAssignment(
        assignment_id=payload["assignment_id"],
        element=element,
        role=role,
        status=status,
        phase11_candidate_id=payload["phase11_candidate_id"],
        phase11_status=payload["phase11_status"],
        combined_score=payload["combined_score"],
        contradiction_score=payload["contradiction_score"],
        excess_risk=payload["excess_risk"],
        relation_to_yongshen=payload["relation_to_yongshen"],
        rationale_codes=tuple(payload["rationale_codes"]),
        source_result_hashes=(regulation_hash,),
        profile_id=profile_id,
        canonical_digest=record_digest("ElementRoleAssignment", payload),
    )


def evaluate_bazi_xiji_roles(
    regulation_result: Mapping[str, object],
    *,
    profile_id: str = DEFAULT_PHASE12_PROFILE_ID,
    requested_outputs: Sequence[str] = (),
) -> BaziXiJiEvaluationResult:
    if set(requested_outputs) & BLOCKED_OUTPUTS:
        raise Phase12InputError("Phase 12 cannot return luck-cycle, event, domain prediction, or renderer outputs")
    if not isinstance(regulation_result, Mapping) or not regulation_result:
        raise Phase12InputError("Phase 11 Regulation Result is required")
    profile = get_xiji_role_profile(profile_id)
    candidates = _candidate_map(regulation_result)
    regulation_hash = _verify_regulation(regulation_result)
    roles, statuses, unresolved = _derive_roles(regulation_result, candidates, profile)
    buckets = {role: tuple(sorted(element for element, value in roles.items() if value == role)) for role in XIJI_ROLES}
    assignments = tuple(
        _assignment(element, roles[element], statuses[element], candidates[element], buckets["yongshen"], regulation_hash, profile_id)
        for element in ELEMENTS
    )
    assignment_map = {item.element: item for item in assignments}
    carriers: list[StemCarrierRole] = []
    for stem in STEMS:
        assignment = assignment_map[STEM_ELEMENT[stem]]
        payload = {
            "carrier_id": f"xiji:stem:{stem}",
            "stem": stem,
            "element": assignment.element,
            "inherited_role": assignment.role,
            "assignment_status": assignment.status,
            "inheritance_rule": "inherits_element_role",
            "yin_yang_differentiation_status": "not_evaluated",
            "source_assignment_id": assignment.assignment_id,
        }
        carriers.append(StemCarrierRole(canonical_digest=record_digest("StemCarrierRole", payload), **payload))
    evidence: list[RoleEvidenceRecord] = []
    for assignment in assignments:
        rows = [
            ("phase11_candidate_score", "support", assignment.combined_score, 80),
            ("phase12_role_relation", "support", "1.0000", 95),
        ]
        if Decimal(assignment.contradiction_score):
            rows.append(("phase11_contradiction", "contradict", assignment.contradiction_score, 90))
        for evidence_type, direction, contribution, priority in rows:
            payload = {
                "evidence_id": f"evidence:{assignment.assignment_id}:{evidence_type}",
                "element": assignment.element,
                "role": assignment.role,
                "evidence_type": evidence_type,
                "direction": direction,
                "contribution": contribution,
                "priority": priority,
                "source_candidate_ids": [assignment.phase11_candidate_id],
                "source_result_hashes": [regulation_hash],
                "profile_id": profile_id,
            }
            evidence.append(RoleEvidenceRecord(
                evidence_id=payload["evidence_id"],
                element=assignment.element,
                role=assignment.role,
                evidence_type=evidence_type,
                direction=direction,
                contribution=contribution,
                priority=priority,
                source_candidate_ids=(assignment.phase11_candidate_id,),
                source_result_hashes=(regulation_hash,),
                profile_id=profile_id,
                canonical_digest=record_digest("RoleEvidenceRecord", payload),
            ))
    evidence.sort(key=lambda item: item.evidence_id)
    classification_status = (
        "unresolved" if buckets["unresolved"]
        else "conditional" if any(item.status == "conditional" for item in assignments)
        else "resolved"
    )
    provenance = {
        "profile_hash": profile["canonical_hash"],
        "regulation_result_hash": regulation_hash,
        "fact_graph_hash": regulation_result.get("fact_graph_hash"),
        "strength_result_hash": regulation_result.get("strength_result_hash"),
        "pattern_result_hash": regulation_result.get("pattern_result_hash"),
        "phase11_profile_id": regulation_result.get("profile_id"),
    }
    body = {
        "regulation_result_hash": regulation_hash,
        "fact_graph_hash": str(regulation_result.get("fact_graph_hash", "")),
        "strength_result_hash": str(regulation_result.get("strength_result_hash", "")),
        "pattern_result_hash": str(regulation_result.get("pattern_result_hash", "")),
        "profile_id": profile_id,
        "classification_status": classification_status,
        "element_assignments": [item.to_dict() for item in assignments],
        "stem_carriers": [item.to_dict() for item in carriers],
        "yongshen_elements": list(buckets["yongshen"]),
        "xishen_elements": list(buckets["xishen"]),
        "jishen_elements": list(buckets["jishen"]),
        "choushen_elements": list(buckets["choushen"]),
        "xianshen_elements": list(buckets["xianshen"]),
        "unresolved_elements": list(buckets["unresolved"]),
        "evidence_records": [item.to_dict() for item in evidence],
        "provenance_index": provenance,
        "warnings": [
            "structural_xiji_role_classification_only",
            "stem_yin_yang_role_differentiation_not_evaluated",
            "prediction_validity_not_evaluated",
            "no_luck_cycle_or_event_prediction",
        ],
        "unresolved": unresolved,
    }
    return BaziXiJiEvaluationResult(
        regulation_result_hash=regulation_hash,
        fact_graph_hash=body["fact_graph_hash"],
        strength_result_hash=body["strength_result_hash"],
        pattern_result_hash=body["pattern_result_hash"],
        profile_id=profile_id,
        classification_status=classification_status,
        element_assignments=assignments,
        stem_carriers=tuple(carriers),
        yongshen_elements=buckets["yongshen"],
        xishen_elements=buckets["xishen"],
        jishen_elements=buckets["jishen"],
        choushen_elements=buckets["choushen"],
        xianshen_elements=buckets["xianshen"],
        unresolved_elements=buckets["unresolved"],
        evidence_records=tuple(evidence),
        provenance_index=provenance,
        warnings=tuple(body["warnings"]),
        unresolved=tuple(unresolved),
        canonical_hash=record_digest("BaziXiJiEvaluationResult", body),
    )


def xiji_result_to_phase8_evidence(result: BaziXiJiEvaluationResult | Mapping[str, object]):
    if isinstance(result, BaziXiJiEvaluationResult):
        return tuple(item.to_phase8_evidence() for item in result.evidence_records)
    raw = result.get("evidence_records")
    if not isinstance(raw, list):
        raise Phase12InputError("evidence_records must be an array")
    records: list[RoleEvidenceRecord] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise Phase12InputError("evidence record must be an object")
        records.append(RoleEvidenceRecord(
            evidence_id=str(item["evidence_id"]),
            element=str(item["element"]),
            role=str(item["role"]),
            evidence_type=str(item["evidence_type"]),
            direction=str(item["direction"]),
            contribution=str(item["contribution"]),
            priority=int(item["priority"]),
            source_candidate_ids=tuple(str(value) for value in item["source_candidate_ids"]),
            source_result_hashes=tuple(str(value) for value in item["source_result_hashes"]),
            profile_id=str(item["profile_id"]),
            canonical_digest=str(item["canonical_digest"]),
        ))
    return tuple(item.to_phase8_evidence() for item in sorted(records, key=lambda value: value.evidence_id))


def build_xiji_fixture(day_stem: str, month_branch: str) -> dict[str, object]:
    graph, strength, pattern = build_regulation_fixture_inputs(day_stem, month_branch)
    return evaluate_bazi_regulation(graph, strength, pattern).to_dict()


def benchmark_phase12() -> Phase12BenchmarkResult:
    failures = list(validate_phase12_profiles())
    passed = assertions_total = 0
    hashes: set[str] = set()

    def check(condition: bool, message: str) -> None:
        nonlocal passed, assertions_total
        assertions_total += 1
        if condition:
            passed += 1
        else:
            failures.append(message)

    for day_stem in STEMS:
        for month_branch in BRANCHES:
            regulation = build_xiji_fixture(day_stem, month_branch)
            result = evaluate_bazi_xiji_roles(regulation)
            reordered = evaluate_bazi_xiji_roles(json.loads(json.dumps(regulation, ensure_ascii=False, sort_keys=True)))
            payload = result.to_dict()
            buckets = [
                set(result.yongshen_elements), set(result.xishen_elements), set(result.jishen_elements),
                set(result.choushen_elements), set(result.xianshen_elements), set(result.unresolved_elements),
            ]
            flattened = set().union(*buckets)
            checks = (
                result.schema_version == PHASE12_SCHEMA_VERSION,
                result.method_id == PHASE12_METHOD_ID,
                result.calculation_version == PHASE12_CALCULATION_VERSION,
                result.prediction_validity == "not_evaluated",
                result.canonical_hash.startswith("sha256:"),
                result.canonical_hash == reordered.canonical_hash,
                result.regulation_result_hash == regulation["canonical_hash"],
                result.fact_graph_hash == regulation["fact_graph_hash"],
                result.strength_result_hash == regulation["strength_result_hash"],
                result.pattern_result_hash == regulation["pattern_result_hash"],
                len(result.element_assignments) == 5,
                {item.element for item in result.element_assignments} == set(ELEMENTS),
                all(item.role in XIJI_ROLES for item in result.element_assignments),
                flattened == set(ELEMENTS),
                sum(len(bucket) for bucket in buckets) == 5,
                len(result.yongshen_elements) <= 1,
                len(result.stem_carriers) == 10,
                {item.stem for item in result.stem_carriers} == set(STEMS),
                all(item.inheritance_rule == "inherits_element_role" for item in result.stem_carriers),
                all(item.yin_yang_differentiation_status == "not_evaluated" for item in result.stem_carriers),
                bool(result.evidence_records),
                all(item.canonical_digest.startswith("sha256:") for item in result.evidence_records),
                result.profile_id == DEFAULT_PHASE12_PROFILE_ID,
                all(key not in payload for key in BLOCKED_OUTPUTS),
            )
            for index, condition in enumerate(checks):
                check(condition, f"{day_stem}{month_branch}: check {index + 1} failed")
            hashes.add(result.canonical_hash)

    regulation = build_xiji_fixture(STEMS[0], BRANCHES[2])
    try:
        evaluate_bazi_xiji_roles({**regulation, "canonical_hash": "sha256:bad"})
        check(False, "regulation hash mismatch was not blocked")
    except Phase12InputError:
        check(True, "regulation hash mismatch blocked")
    tampered = json.loads(json.dumps(regulation, ensure_ascii=False))
    tampered["candidates"][0]["combined_score"] = "99.9999"
    try:
        evaluate_bazi_xiji_roles(tampered)
        check(False, "nested candidate tampering was not blocked")
    except Phase12InputError:
        check(True, "nested candidate tampering blocked")
    try:
        evaluate_bazi_xiji_roles(regulation, requested_outputs=("event_prediction",))
        check(False, "prediction request was not blocked")
        prediction_boundary_failures = 1
    except Phase12InputError:
        check(True, "prediction request blocked")
        prediction_boundary_failures = 0

    if assertions_total < int(load_phase12_xiji_assertions()["minimum_expected_assertions_total"]):
        failures.append("assertion matrix below declared minimum")
    schema_failures = 0 if PHASE12_SCHEMA_VERSION.startswith("bazi-xiji-role-classification-result@") else 1
    profile = get_xiji_role_profile()
    provenance_failures = 0 if len(set(profile.get("independence_groups", []))) >= 2 else 1
    hash_mismatches = 0 if len(hashes) > 20 else 1
    if schema_failures:
        failures.append("schema version invalid")
    if provenance_failures:
        failures.append("profile provenance insufficient")
    if hash_mismatches:
        failures.append("canonical hash coverage insufficient")
    return Phase12BenchmarkResult(
        assertions_total=assertions_total,
        passed=passed,
        failed=len(failures),
        unresolved=0,
        schema_failures=schema_failures,
        provenance_failures=provenance_failures,
        hash_mismatches=hash_mismatches,
        role_partition_failures=0,
        role_collision_failures=0,
        carrier_failures=0,
        prediction_boundary_failures=prediction_boundary_failures,
        failures=tuple(failures),
    )


__all__ = [
    "PHASE12_CALCULATION_VERSION", "PHASE12_DECISION_ID", "PHASE12_METHOD_ID", "PHASE12_SCHEMA_VERSION",
    "Phase12InputError", "benchmark_phase12", "build_xiji_fixture", "evaluate_bazi_xiji_roles",
    "get_xiji_role_profile", "load_phase12_xiji_assertions", "load_phase12_xiji_profiles",
    "phase12_schema_summary", "validate_import_origin", "validate_phase12_profiles", "xiji_result_to_phase8_evidence",
]
