from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
import json
from importlib.resources import files
from typing import Mapping, Sequence

from .bazi import DeterministicBaziEngine
from .contracts.serialization import digest
from .derived.static_engine import BRANCHES, HIDDEN_STEMS, STEMS, STEM_ELEMENT
from .phase7 import build_bazi_fact_graph, branch_pair_relation, stem_pair_relation
from .phase8_engine import validate_import_origin
from .phase9 import calculate_day_master_strength
from .phase10 import build_pattern_fixture_inputs, evaluate_bazi_pattern
from .phase11 import evaluate_bazi_regulation
from .phase12 import evaluate_bazi_xiji_roles
from .phase12_contracts import record_digest as phase12_record_digest
from .phase13_contracts import (
    BaziLuckCycleRoleInteractionResult,
    CombinedCycleWindow,
    CycleInteractionEvidenceRecord,
    CycleRoleHit,
    NatalRelationRecord,
    PHASE13_CALCULATION_VERSION,
    PHASE13_DECISION_ID,
    PHASE13_METHOD_ID,
    PHASE13_SCHEMA_VERSION,
    Phase13BenchmarkResult,
    Phase13InputError,
    PeriodRoleInteraction,
    STRUCTURAL_STATES,
    record_digest,
)

DEFAULT_PHASE13_PROFILE_ID = "luck-cycle-role-interaction-r1@0.1"
PROFILE_RESOURCE = "phase13_luck_cycle_interaction_profiles_v0.1.json"
ASSERTION_RESOURCE = "phase13_luck_cycle_interaction_assertions_v0.1.json"
METADATA_FIELDS = {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}
BLOCKED_OUTPUTS = {
    "auspiciousness",
    "good_bad",
    "fortune_judgement",
    "event_prediction",
    "career_prediction",
    "wealth_prediction",
    "relationship_prediction",
    "health_prediction",
    "natural_language_renderer",
}
ELEMENTS = {"wood", "fire", "earth", "metal", "water"}


def _decimal(value: object, name: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise Phase13InputError(f"{name} must be decimal-compatible") from exc
    if not number.is_finite():
        raise Phase13InputError(f"{name} must be finite")
    return number


def _score(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")


def _load_resource(name: str, label: str) -> dict[str, object]:
    value = json.loads(files("mingli.derived.data").joinpath(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def load_phase13_interaction_profiles() -> dict[str, object]:
    return _load_resource(PROFILE_RESOURCE, "Phase 13 profile manifest")


def load_phase13_interaction_assertions() -> dict[str, object]:
    return _load_resource(ASSERTION_RESOURCE, "Phase 13 assertion manifest")


def get_interaction_profile(profile_id: str = DEFAULT_PHASE13_PROFILE_ID) -> dict[str, object]:
    raw_profiles = load_phase13_interaction_profiles().get("profiles")
    if not isinstance(raw_profiles, list):
        raise ValueError("profiles must be an array")
    for raw in raw_profiles:
        if isinstance(raw, dict) and raw.get("profile_id") == profile_id:
            profile = dict(raw)
            profile["canonical_hash"] = digest({
                "record_type": "LuckCycleInteractionProfile",
                "payload": {key: value for key, value in profile.items() if key != "canonical_hash"},
            })
            return profile
    raise ValueError(f"unsupported Phase 13 profile: {profile_id}")


def validate_phase13_profiles() -> tuple[str, ...]:
    issues: list[str] = []
    try:
        profile = get_interaction_profile()
        expected_roles = {"yongshen", "xishen", "jishen", "choushen", "xianshen", "unresolved"}
        if profile.get("reviewed") is not True:
            issues.append("reviewed must be true")
        if set(profile.get("role_directions", {})) != expected_roles:
            issues.append("role_directions must cover all Phase 12 roles")
        if set(profile.get("role_multipliers", {})) != expected_roles:
            issues.append("role_multipliers must cover all Phase 12 roles")
        if set(profile.get("source_weights", {})) != {"stem", "branch_primary", "branch_secondary", "branch_tertiary"}:
            issues.append("source_weights are incomplete")
        if set(profile.get("state_thresholds", {})) != {"aligned_support_min", "opposed_conflict_min", "mixed_support_min", "mixed_conflict_min"}:
            issues.append("state_thresholds are incomplete")
        if set(profile.get("window_weights", {})) != {"dayun", "liunian"}:
            issues.append("window_weights are incomplete")
        for field_name in ("role_multipliers", "source_weights", "state_thresholds", "window_weights"):
            values = profile.get(field_name)
            if isinstance(values, Mapping):
                for key, value in values.items():
                    if _decimal(value, f"{field_name}.{key}") < 0:
                        issues.append(f"{field_name}.{key} must be non-negative")
        window_weights = profile.get("window_weights")
        if isinstance(window_weights, Mapping):
            total = sum((_decimal(value, "window_weight") for value in window_weights.values()), Decimal("0"))
            if total != Decimal("1"):
                issues.append("window_weights must sum to 1")
        if len(set(profile.get("independence_groups", []))) < 2:
            issues.append("at least two independence groups are required")
        if not str(profile.get("canonical_hash", "")).startswith("sha256:"):
            issues.append("profile canonical hash is invalid")
    except (ValueError, Phase13InputError) as exc:
        issues.append(str(exc))
    return tuple(issues)


def phase13_schema_summary() -> dict[str, object]:
    return {
        "decision_id": PHASE13_DECISION_ID,
        "schema_version": PHASE13_SCHEMA_VERSION,
        "method_id": PHASE13_METHOD_ID,
        "calculation_version": PHASE13_CALCULATION_VERSION,
        "profile_id": DEFAULT_PHASE13_PROFILE_ID,
        "prediction_validity": "not_evaluated",
        "structural_states": list(STRUCTURAL_STATES),
        "output_boundary": "timeline_role_interaction_only_no_auspiciousness_or_event_prediction",
    }


def _verify_fact_graph(value: Mapping[str, object]) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase13InputError("Phase 7 Fact Graph missing canonical_hash")
    if value.get("schema_version") != "bazi-fact-graph-result@0.1":
        raise Phase13InputError("unsupported Phase 7 Fact Graph schema")
    if value.get("prediction_validity") != "not_evaluated":
        raise Phase13InputError("Phase 7 Fact Graph prediction_validity must be not_evaluated")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    expected = digest({"record_type": "BaziFactGraphResult", "payload": body})
    if found != expected:
        raise Phase13InputError("Phase 7 Fact Graph canonical_hash mismatch")
    timeline = value.get("timeline")
    if not isinstance(timeline, Mapping):
        raise Phase13InputError("Phase 7 Fact Graph timeline is required")
    dayun = timeline.get("dayun_periods")
    liunian = timeline.get("liunian_periods")
    if not isinstance(dayun, list) or not dayun or not isinstance(liunian, list) or not liunian:
        raise Phase13InputError("Phase 7 Fact Graph timeline periods are required")
    if int(timeline.get("interval_gaps", 0)) != 0 or int(timeline.get("interval_overlaps", 0)) != 0:
        raise Phase13InputError("Phase 7 timeline contains gaps or overlaps")
    return found


def _verify_xiji(value: Mapping[str, object], fact_graph_hash: str) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase13InputError("Phase 12 XiJi Result missing canonical_hash")
    if value.get("schema_version") != "bazi-xiji-role-classification-result@0.1":
        raise Phase13InputError("unsupported Phase 12 XiJi Result schema")
    if value.get("prediction_validity") != "not_evaluated":
        raise Phase13InputError("Phase 12 XiJi Result prediction_validity must be not_evaluated")
    if value.get("fact_graph_hash") != fact_graph_hash:
        raise Phase13InputError("Phase 7 and Phase 12 fact_graph_hash mismatch")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    if found != phase12_record_digest("BaziXiJiEvaluationResult", body):
        raise Phase13InputError("Phase 12 XiJi Result canonical_hash mismatch")
    assignments = value.get("element_assignments")
    if not isinstance(assignments, list) or len(assignments) != 5:
        raise Phase13InputError("Phase 12 XiJi Result must contain five assignments")
    for item in assignments:
        if not isinstance(item, Mapping):
            raise Phase13InputError("Phase 12 assignment must be an object")
        if item.get("canonical_digest") != phase12_record_digest("ElementRoleAssignment", item):
            raise Phase13InputError("Phase 12 assignment canonical_digest mismatch")
    return found


def _role_assignments(xiji: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    assignments = xiji.get("element_assignments")
    assert isinstance(assignments, list)
    result: dict[str, Mapping[str, object]] = {}
    for item in assignments:
        assert isinstance(item, Mapping)
        element = str(item.get("element"))
        if element in result:
            raise Phase13InputError("duplicate Phase 12 element assignment")
        result[element] = item
    if set(result) != ELEMENTS:
        raise Phase13InputError("Phase 12 assignments must cover five elements")
    return result


def _natal_pillars(graph: Mapping[str, object]) -> tuple[tuple[str, str, str], ...]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise Phase13InputError("Fact Graph nodes are required")
    positions = ("year", "month", "day", "hour")
    records: list[tuple[str, str, str]] = []
    for node in nodes:
        if isinstance(node, Mapping) and node.get("node_type") == "Pillar":
            position = str(node.get("position"))
            stem = str(node.get("stem"))
            branch = str(node.get("branch"))
            if position in positions and stem in STEMS and branch in BRANCHES:
                records.append((position, stem, branch))
    if {item[0] for item in records} != set(positions):
        raise Phase13InputError("Fact Graph must contain four natal pillars")
    return tuple(sorted(records, key=lambda item: positions.index(item[0])))


def _state(profile: Mapping[str, object], support: Decimal, conflict: Decimal, unresolved_count: int) -> str:
    thresholds = profile["state_thresholds"]
    assert isinstance(thresholds, Mapping)
    if unresolved_count:
        return "unresolved"
    mixed_support = _decimal(thresholds["mixed_support_min"], "mixed_support_min")
    mixed_conflict = _decimal(thresholds["mixed_conflict_min"], "mixed_conflict_min")
    if support >= mixed_support and conflict >= mixed_conflict:
        return "mixed"
    if support >= _decimal(thresholds["aligned_support_min"], "aligned_support_min") and conflict < mixed_conflict:
        return "aligned"
    if conflict >= _decimal(thresholds["opposed_conflict_min"], "opposed_conflict_min") and support < mixed_support:
        return "opposed"
    return "neutral"


def _role_hit(
    period_id: str,
    source_type: str,
    symbol: str,
    ordinal: int,
    element: str,
    assignment: Mapping[str, object],
    base_weight: Decimal,
    profile: Mapping[str, object],
) -> CycleRoleHit:
    role = str(assignment.get("role"))
    directions = profile["role_directions"]
    multipliers = profile["role_multipliers"]
    assert isinstance(directions, Mapping) and isinstance(multipliers, Mapping)
    direction = str(directions[role])
    multiplier = _decimal(multipliers[role], f"role_multiplier.{role}")
    payload = {
        "hit_id": f"hit:{period_id}:{source_type}:{ordinal}:{symbol}",
        "period_id": period_id,
        "source_type": source_type,
        "source_symbol": symbol,
        "ordinal": ordinal,
        "element": element,
        "role": role,
        "direction": direction,
        "base_weight": _score(base_weight),
        "role_multiplier": _score(multiplier),
        "weighted_score": _score(base_weight * multiplier),
        "source_assignment_id": str(assignment.get("assignment_id")),
    }
    return CycleRoleHit(canonical_digest=record_digest("CycleRoleHit", payload), **payload)  # type: ignore[arg-type]


def _natal_relations(period_id: str, stem: str, branch: str, natal: tuple[tuple[str, str, str], ...]) -> tuple[NatalRelationRecord, ...]:
    records: list[NatalRelationRecord] = []
    for position, natal_stem, natal_branch in natal:
        for symbol_type, source_symbol, natal_symbol, facts in (
            ("stem", stem, natal_stem, stem_pair_relation(stem, natal_stem)),
            ("branch", branch, natal_branch, branch_pair_relation(branch, natal_branch)),
        ):
            payload = {
                "relation_id": f"relation:{period_id}:{symbol_type}:{position}",
                "period_id": period_id,
                "source_symbol_type": symbol_type,
                "source_symbol": source_symbol,
                "natal_position": position,
                "natal_symbol": natal_symbol,
                "relation_types": sorted(fact.relation_type for fact in facts),
                "relation_statuses": sorted({status for fact in facts for status in fact.status}),
            }
            records.append(NatalRelationRecord(
                relation_id=payload["relation_id"],
                period_id=period_id,
                source_symbol_type=symbol_type,  # type: ignore[arg-type]
                source_symbol=source_symbol,
                natal_position=position,
                natal_symbol=natal_symbol,
                relation_types=tuple(payload["relation_types"]),
                relation_statuses=tuple(payload["relation_statuses"]),
                canonical_digest=record_digest("NatalRelationRecord", payload),
            ))
    return tuple(sorted(records, key=lambda item: item.relation_id))


def _period_interaction(
    raw: Mapping[str, object],
    period_type: str,
    assignments: Mapping[str, Mapping[str, object]],
    natal: tuple[tuple[str, str, str], ...],
    graph_hash: str,
    xiji_hash: str,
    profile: Mapping[str, object],
) -> PeriodRoleInteraction:
    period_id = str(raw.get("period_id"))
    ganzhi = str(raw.get("ganzhi"))
    if len(ganzhi) != 2 or ganzhi[0] not in STEMS or ganzhi[1] not in BRANCHES:
        raise Phase13InputError(f"malformed period ganzhi: {period_id}")
    stem, branch = ganzhi[0], ganzhi[1]
    weights = profile["source_weights"]
    assert isinstance(weights, Mapping)
    hits: list[CycleRoleHit] = []
    stem_element = STEM_ELEMENT[stem]
    hits.append(_role_hit(
        period_id,
        "stem",
        stem,
        0,
        stem_element,
        assignments[stem_element],
        _decimal(weights["stem"], "stem_weight"),
        profile,
    ))
    for ordinal, hidden_stem in enumerate(HIDDEN_STEMS[branch], 1):
        weight_key = "branch_primary" if ordinal == 1 else "branch_secondary" if ordinal == 2 else "branch_tertiary"
        element = STEM_ELEMENT[hidden_stem]
        hits.append(_role_hit(
            period_id,
            "branch_hidden",
            hidden_stem,
            ordinal,
            element,
            assignments[element],
            _decimal(weights[weight_key], weight_key),
            profile,
        ))
    support = sum((_decimal(hit.weighted_score, "hit_score") for hit in hits if hit.direction == "support"), Decimal("0"))
    conflict = sum((_decimal(hit.weighted_score, "hit_score") for hit in hits if hit.direction == "conflict"), Decimal("0"))
    neutral = sum((_decimal(hit.weighted_score, "hit_score") for hit in hits if hit.direction == "neutral"), Decimal("0"))
    unresolved_count = sum(1 for hit in hits if hit.direction == "unresolved")
    relations = _natal_relations(period_id, stem, branch, natal)
    payload = {
        "interaction_id": f"interaction:{period_id}",
        "period_id": period_id,
        "period_type": period_type,
        "sequence_index": int(raw["sequence_index"]) if period_type == "dayun" else None,
        "label_year": int(raw["label_year"]) if period_type == "liunian" else None,
        "dayun_period_id": str(raw["dayun_period_id"]) if raw.get("dayun_period_id") else None,
        "ganzhi": ganzhi,
        "stem": stem,
        "branch": branch,
        "start_instant_utc": str(raw.get("start_instant_utc")),
        "end_instant_utc": str(raw.get("end_instant_utc")),
        "role_hits": [hit.to_dict() for hit in hits],
        "support_score": _score(support),
        "conflict_score": _score(conflict),
        "neutral_score": _score(neutral),
        "unresolved_count": unresolved_count,
        "structural_state": _state(profile, support, conflict, unresolved_count),
        "natal_relations": [relation.to_dict() for relation in relations],
        "source_result_hashes": [graph_hash, xiji_hash],
        "profile_id": str(profile["profile_id"]),
    }
    return PeriodRoleInteraction(
        interaction_id=payload["interaction_id"],
        period_id=period_id,
        period_type=period_type,  # type: ignore[arg-type]
        sequence_index=payload["sequence_index"],
        label_year=payload["label_year"],
        dayun_period_id=payload["dayun_period_id"],
        ganzhi=ganzhi,
        stem=stem,
        branch=branch,
        start_instant_utc=payload["start_instant_utc"],
        end_instant_utc=payload["end_instant_utc"],
        role_hits=tuple(hits),
        support_score=payload["support_score"],
        conflict_score=payload["conflict_score"],
        neutral_score=payload["neutral_score"],
        unresolved_count=unresolved_count,
        structural_state=payload["structural_state"],  # type: ignore[arg-type]
        natal_relations=relations,
        source_result_hashes=(graph_hash, xiji_hash),
        profile_id=payload["profile_id"],
        canonical_digest=record_digest("PeriodRoleInteraction", payload),
    )


def _combined_window(dayun: PeriodRoleInteraction, liunian: PeriodRoleInteraction, profile: Mapping[str, object]) -> CombinedCycleWindow:
    weights = profile["window_weights"]
    assert isinstance(weights, Mapping)
    dayun_weight = _decimal(weights["dayun"], "window.dayun")
    liunian_weight = _decimal(weights["liunian"], "window.liunian")
    support = _decimal(dayun.support_score, "dayun.support") * dayun_weight + _decimal(liunian.support_score, "liunian.support") * liunian_weight
    conflict = _decimal(dayun.conflict_score, "dayun.conflict") * dayun_weight + _decimal(liunian.conflict_score, "liunian.conflict") * liunian_weight
    neutral = _decimal(dayun.neutral_score, "dayun.neutral") * dayun_weight + _decimal(liunian.neutral_score, "liunian.neutral") * liunian_weight
    unresolved_count = dayun.unresolved_count + liunian.unresolved_count
    stem_relations = tuple(sorted(fact.relation_type for fact in stem_pair_relation(dayun.stem, liunian.stem)))
    branch_relations = tuple(sorted(fact.relation_type for fact in branch_pair_relation(dayun.branch, liunian.branch)))
    payload = {
        "window_id": f"window:{dayun.period_id}:{liunian.period_id}",
        "dayun_period_id": dayun.period_id,
        "liunian_period_id": liunian.period_id,
        "start_instant_utc": liunian.start_instant_utc,
        "end_instant_utc": liunian.end_instant_utc,
        "dayun_ganzhi": dayun.ganzhi,
        "liunian_ganzhi": liunian.ganzhi,
        "support_score": _score(support),
        "conflict_score": _score(conflict),
        "neutral_score": _score(neutral),
        "unresolved_count": unresolved_count,
        "stem_relation_types": list(stem_relations),
        "branch_relation_types": list(branch_relations),
        "structural_state": _state(profile, support, conflict, unresolved_count),
    }
    return CombinedCycleWindow(
        window_id=payload["window_id"],
        dayun_period_id=dayun.period_id,
        liunian_period_id=liunian.period_id,
        start_instant_utc=liunian.start_instant_utc,
        end_instant_utc=liunian.end_instant_utc,
        dayun_ganzhi=dayun.ganzhi,
        liunian_ganzhi=liunian.ganzhi,
        support_score=payload["support_score"],
        conflict_score=payload["conflict_score"],
        neutral_score=payload["neutral_score"],
        unresolved_count=unresolved_count,
        stem_relation_types=stem_relations,
        branch_relation_types=branch_relations,
        structural_state=payload["structural_state"],  # type: ignore[arg-type]
        canonical_digest=record_digest("CombinedCycleWindow", payload),
    )


def evaluate_luck_cycle_role_interactions(
    fact_graph: Mapping[str, object],
    xiji_result: Mapping[str, object],
    *,
    profile_id: str = DEFAULT_PHASE13_PROFILE_ID,
    requested_outputs: Sequence[str] = (),
) -> BaziLuckCycleRoleInteractionResult:
    if set(requested_outputs) & BLOCKED_OUTPUTS:
        raise Phase13InputError("Phase 13 cannot return auspiciousness, event, domain, or renderer outputs")
    if not isinstance(fact_graph, Mapping) or not fact_graph:
        raise Phase13InputError("Phase 7 Fact Graph is required")
    if not isinstance(xiji_result, Mapping) or not xiji_result:
        raise Phase13InputError("Phase 12 XiJi Result is required")
    profile = get_interaction_profile(profile_id)
    graph_hash = _verify_fact_graph(fact_graph)
    xiji_hash = _verify_xiji(xiji_result, graph_hash)
    assignments = _role_assignments(xiji_result)
    natal = _natal_pillars(fact_graph)
    timeline = fact_graph["timeline"]
    assert isinstance(timeline, Mapping)
    raw_dayun = timeline["dayun_periods"]
    raw_liunian = timeline["liunian_periods"]
    assert isinstance(raw_dayun, list) and isinstance(raw_liunian, list)
    dayun = tuple(sorted(
        (_period_interaction(item, "dayun", assignments, natal, graph_hash, xiji_hash, profile) for item in raw_dayun if isinstance(item, Mapping)),
        key=lambda item: item.sequence_index or 0,
    ))
    liunian = tuple(sorted(
        (_period_interaction(item, "liunian", assignments, natal, graph_hash, xiji_hash, profile) for item in raw_liunian if isinstance(item, Mapping)),
        key=lambda item: item.label_year or 0,
    ))
    dayun_by_id = {item.period_id: item for item in dayun}
    windows: list[CombinedCycleWindow] = []
    unresolved: list[dict[str, object]] = []
    for item in liunian:
        if item.dayun_period_id and item.dayun_period_id in dayun_by_id:
            windows.append(_combined_window(dayun_by_id[item.dayun_period_id], item, profile))
        else:
            unresolved.append({"code": "liunian_without_active_dayun", "period_id": item.period_id, "source": "phase7"})
    if xiji_result.get("unresolved"):
        unresolved.append({"code": "phase12_unresolved_retained", "source": "phase12"})
    evidence: list[CycleInteractionEvidenceRecord] = []
    for interaction in (*dayun, *liunian):
        for hit in interaction.role_hits:
            if hit.direction not in {"support", "conflict"}:
                continue
            direction = "support" if hit.direction == "support" else "contradict"
            payload = {
                "evidence_id": f"evidence:{hit.hit_id}",
                "period_id": interaction.period_id,
                "element": hit.element,
                "role": hit.role,
                "evidence_type": "cycle_role_support" if hit.direction == "support" else "cycle_role_conflict",
                "direction": direction,
                "contribution": hit.weighted_score,
                "priority": 85 if hit.source_type == "stem" else 75,
                "source_result_hashes": [graph_hash, xiji_hash],
                "profile_id": profile_id,
            }
            evidence.append(CycleInteractionEvidenceRecord(
                evidence_id=payload["evidence_id"],
                period_id=interaction.period_id,
                element=hit.element,
                role=hit.role,
                evidence_type=payload["evidence_type"],
                direction=direction,  # type: ignore[arg-type]
                contribution=hit.weighted_score,
                priority=payload["priority"],
                source_result_hashes=(graph_hash, xiji_hash),
                profile_id=profile_id,
                canonical_digest=record_digest("CycleInteractionEvidenceRecord", payload),
            ))
    evidence.sort(key=lambda item: item.evidence_id)
    state_counts = {state: 0 for state in STRUCTURAL_STATES}
    for item in (*dayun, *liunian, *windows):
        state_counts[item.structural_state] += 1
    provenance = {
        "profile_hash": profile["canonical_hash"],
        "fact_graph_hash": graph_hash,
        "xiji_result_hash": xiji_hash,
        "phase7_timeline_profile_ids": sorted({str(item.get("profile_id")) for item in raw_dayun if isinstance(item, Mapping)}),
        "phase12_profile_id": xiji_result.get("profile_id"),
        "source_ids": list(profile.get("source_ids", [])),
    }
    body = {
        "fact_graph_hash": graph_hash,
        "xiji_result_hash": xiji_hash,
        "profile_id": profile_id,
        "dayun_interactions": [item.to_dict() for item in dayun],
        "liunian_interactions": [item.to_dict() for item in liunian],
        "combined_windows": [item.to_dict() for item in windows],
        "state_counts": state_counts,
        "evidence_records": [item.to_dict() for item in evidence],
        "provenance_index": provenance,
        "warnings": [
            "structural_role_interaction_only",
            "stem_branch_relations_do_not_imply_transformation",
            "prediction_validity_not_evaluated",
            "no_auspiciousness_or_event_prediction",
        ],
        "unresolved": unresolved,
    }
    return BaziLuckCycleRoleInteractionResult(
        fact_graph_hash=graph_hash,
        xiji_result_hash=xiji_hash,
        profile_id=profile_id,
        dayun_interactions=dayun,
        liunian_interactions=liunian,
        combined_windows=tuple(windows),
        state_counts=state_counts,
        evidence_records=tuple(evidence),
        provenance_index=provenance,
        warnings=tuple(body["warnings"]),
        unresolved=tuple(unresolved),
        canonical_hash=record_digest("BaziLuckCycleRoleInteractionResult", body),
    )


def interaction_result_to_phase8_evidence(result: BaziLuckCycleRoleInteractionResult | Mapping[str, object]):
    if isinstance(result, BaziLuckCycleRoleInteractionResult):
        return tuple(item.to_phase8_evidence() for item in result.evidence_records)
    raw = result.get("evidence_records")
    if not isinstance(raw, list):
        raise Phase13InputError("evidence_records must be an array")
    records: list[CycleInteractionEvidenceRecord] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise Phase13InputError("evidence record must be an object")
        records.append(CycleInteractionEvidenceRecord(
            evidence_id=str(item["evidence_id"]),
            period_id=str(item["period_id"]),
            element=str(item["element"]),
            role=str(item["role"]),
            evidence_type=str(item["evidence_type"]),
            direction=str(item["direction"]),  # type: ignore[arg-type]
            contribution=str(item["contribution"]),
            priority=int(item["priority"]),
            source_result_hashes=tuple(str(value) for value in item["source_result_hashes"]),
            profile_id=str(item["profile_id"]),
            canonical_digest=str(item["canonical_digest"]),
        ))
    return tuple(item.to_phase8_evidence() for item in sorted(records, key=lambda value: value.evidence_id))


@lru_cache(maxsize=1)
def _phase7_timeline_template() -> dict[str, object]:
    base = DeterministicBaziEngine().calculate({
        "birth_date": "2000-01-07",
        "birth_time": "12:00",
        "timezone": "+08:00",
        "gender": "male",
        "calendar": "solar",
        "longitude": 121.4737,
        "latitude": 31.2304,
        "true_solar_time": False,
    })
    return build_bazi_fact_graph(base).to_dict()


def _fixture_graph(day_stem: str, month_branch: str) -> dict[str, object]:
    structural_graph, _ = build_pattern_fixture_inputs(day_stem, month_branch)
    template = _phase7_timeline_template()
    graph = json.loads(json.dumps(structural_graph, ensure_ascii=False))
    graph["base_chart_ref"] = dict(template["base_chart_ref"])
    graph["derived_structure_ref"] = dict(template["derived_structure_ref"])
    graph["profiles"] = list(template["profiles"])
    graph["timeline"] = dict(template["timeline"])
    graph["provenance_index"] = {
        "fixture": "phase13-matrix",
        "timeline_source_hash": template["canonical_hash"],
        "day_stem": day_stem,
        "month_branch": month_branch,
    }
    graph["warnings"] = ["phase13_fixture_uses_reviewed_phase7_timeline_template"]
    graph["unresolved"] = []
    graph["schema_version"] = "bazi-fact-graph-result@0.1"
    graph["method_id"] = "bazi-deterministic-fact-graph@0.1.0"
    graph["calculation_version"] = "0.1.0"
    graph["prediction_validity"] = "not_evaluated"
    body = {key: value for key, value in graph.items() if key not in METADATA_FIELDS}
    graph["canonical_hash"] = digest({"record_type": "BaziFactGraphResult", "payload": body})
    return graph


def build_phase13_fixture(day_stem: str, month_branch: str) -> tuple[dict[str, object], dict[str, object]]:
    graph = _fixture_graph(day_stem, month_branch)
    strength = calculate_day_master_strength(graph).to_dict()
    pattern = evaluate_bazi_pattern(graph, strength).to_dict()
    regulation = evaluate_bazi_regulation(graph, strength, pattern).to_dict()
    xiji = evaluate_bazi_xiji_roles(regulation).to_dict()
    return graph, xiji


def benchmark_phase13() -> Phase13BenchmarkResult:
    failures = list(validate_phase13_profiles())
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
            graph, xiji = build_phase13_fixture(day_stem, month_branch)
            result = evaluate_luck_cycle_role_interactions(graph, xiji)
            reordered = evaluate_luck_cycle_role_interactions(
                json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True)),
                json.loads(json.dumps(xiji, ensure_ascii=False, sort_keys=True)),
            )
            payload = result.to_dict()
            all_periods = (*result.dayun_interactions, *result.liunian_interactions)
            dayun_ids = {item.period_id for item in result.dayun_interactions}
            liunian_ids = {item.period_id for item in result.liunian_interactions}
            checks = (
                result.schema_version == PHASE13_SCHEMA_VERSION,
                result.method_id == PHASE13_METHOD_ID,
                result.calculation_version == PHASE13_CALCULATION_VERSION,
                result.prediction_validity == "not_evaluated",
                result.canonical_hash.startswith("sha256:"),
                result.canonical_hash == reordered.canonical_hash,
                result.fact_graph_hash == graph["canonical_hash"],
                result.xiji_result_hash == xiji["canonical_hash"],
                len(result.dayun_interactions) == 10,
                len(result.liunian_interactions) == 10,
                all(item.period_type in {"dayun", "liunian"} for item in all_periods),
                len({item.period_id for item in all_periods}) == len(all_periods),
                all(len(item.ganzhi) == 2 for item in all_periods),
                all(item.stem in STEMS and item.branch in BRANCHES for item in all_periods),
                all(bool(item.role_hits) for item in all_periods),
                all(item.role_hits[0].source_type == "stem" for item in all_periods),
                all(len(item.role_hits) == 1 + len(HIDDEN_STEMS[item.branch]) for item in all_periods),
                all(_decimal(item.support_score, "support") >= 0 for item in all_periods),
                all(_decimal(item.conflict_score, "conflict") >= 0 for item in all_periods),
                all(item.structural_state in STRUCTURAL_STATES for item in all_periods),
                all(len(item.natal_relations) == 8 for item in all_periods),
                all(item.source_result_hashes == (graph["canonical_hash"], xiji["canonical_hash"]) for item in all_periods),
                result.profile_id == DEFAULT_PHASE13_PROFILE_ID,
                len(result.combined_windows) <= len(result.liunian_interactions),
                all(window.dayun_period_id in dayun_ids for window in result.combined_windows),
                all(window.liunian_period_id in liunian_ids for window in result.combined_windows),
                sum(result.state_counts.values()) == len(all_periods) + len(result.combined_windows),
                all(item.canonical_digest.startswith("sha256:") for item in all_periods),
                all(item.canonical_digest.startswith("sha256:") for item in result.combined_windows),
                all(key not in payload for key in BLOCKED_OUTPUTS),
            )
            for index, condition in enumerate(checks):
                check(condition, f"{day_stem}{month_branch}: check {index + 1} failed")
            hashes.add(result.canonical_hash)

    graph, xiji = build_phase13_fixture(STEMS[0], BRANCHES[2])
    try:
        evaluate_luck_cycle_role_interactions({**graph, "canonical_hash": "sha256:bad"}, xiji)
        check(False, "fact graph hash mismatch was not blocked")
    except Phase13InputError:
        check(True, "fact graph hash mismatch blocked")
    try:
        evaluate_luck_cycle_role_interactions(graph, {**xiji, "canonical_hash": "sha256:bad"})
        check(False, "xiji hash mismatch was not blocked")
    except Phase13InputError:
        check(True, "xiji hash mismatch blocked")
    tampered = json.loads(json.dumps(xiji, ensure_ascii=False))
    tampered["element_assignments"][0]["role"] = "unresolved"
    try:
        evaluate_luck_cycle_role_interactions(graph, tampered)
        check(False, "nested assignment tampering was not blocked")
    except Phase13InputError:
        check(True, "nested assignment tampering blocked")
    try:
        evaluate_luck_cycle_role_interactions(graph, xiji, requested_outputs=("event_prediction",))
        check(False, "prediction request was not blocked")
        prediction_boundary_failures = 1
    except Phase13InputError:
        check(True, "prediction request blocked")
        prediction_boundary_failures = 0

    if assertions_total < int(load_phase13_interaction_assertions()["minimum_expected_assertions_total"]):
        failures.append("assertion matrix below declared minimum")
    schema_failures = 0 if PHASE13_SCHEMA_VERSION.startswith("bazi-luck-cycle-role-interaction-result@") else 1
    profile = get_interaction_profile()
    provenance_failures = 0 if len(set(profile.get("independence_groups", []))) >= 2 else 1
    hash_mismatches = 0 if len(hashes) > 20 else 1
    if schema_failures:
        failures.append("schema version invalid")
    if provenance_failures:
        failures.append("profile provenance insufficient")
    if hash_mismatches:
        failures.append("canonical hash coverage insufficient")
    return Phase13BenchmarkResult(
        assertions_total=assertions_total,
        passed=passed,
        failed=len(failures),
        unresolved=0,
        schema_failures=schema_failures,
        provenance_failures=provenance_failures,
        hash_mismatches=hash_mismatches,
        timeline_failures=0,
        partition_failures=0,
        relation_failures=0,
        prediction_boundary_failures=prediction_boundary_failures,
        failures=tuple(failures),
    )


__all__ = [
    "PHASE13_CALCULATION_VERSION",
    "PHASE13_DECISION_ID",
    "PHASE13_METHOD_ID",
    "PHASE13_SCHEMA_VERSION",
    "Phase13InputError",
    "benchmark_phase13",
    "build_phase13_fixture",
    "evaluate_luck_cycle_role_interactions",
    "get_interaction_profile",
    "interaction_result_to_phase8_evidence",
    "load_phase13_interaction_assertions",
    "load_phase13_interaction_profiles",
    "phase13_schema_summary",
    "validate_import_origin",
    "validate_phase13_profiles",
]
