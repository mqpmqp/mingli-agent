from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from .contracts.serialization import digest
from .derived.static_engine import STEMS, map_hidden_stems, map_ten_god
from .phase10_contracts import (
    BaziPatternEvaluationResult,
    PatternCandidateResult,
    PatternCondition,
    PatternConditionResult,
    PatternEvidenceRecord,
    PatternProfile,
    PatternSourceCandidate,
    Phase10InputError,
    SPECIAL_PATTERN_TYPES,
    record_digest,
)
from .phase10_profiles import DEFAULT_PHASE10_PROFILE_ID, get_pattern_profile
from .phase10_resolution import resolve_candidate_conflicts

TEN_GOD_TO_PATTERN = {
    "authority_opposite_polarity": "zheng_guan",
    "authority_same_polarity": "qi_sha",
    "resource_opposite_polarity": "zheng_yin",
    "resource_same_polarity": "pian_yin",
    "output_same_polarity": "shi_shen",
    "output_opposite_polarity": "shang_guan",
    "wealth_opposite_polarity": "zheng_cai",
    "wealth_same_polarity": "pian_cai",
}
PATTERN_TO_TEN_GOD = {value: key for key, value in TEN_GOD_TO_PATTERN.items()}
FAMILY = {
    "zheng_guan": "authority", "qi_sha": "authority", "zheng_yin": "resource", "pian_yin": "resource",
    "shi_shen": "output", "shang_guan": "output", "zheng_cai": "wealth", "pian_cai": "wealth",
}


def _nodes(fact_graph: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw = fact_graph.get("nodes")
    if not isinstance(raw, list):
        raise Phase10InputError("Fact Graph missing nodes")
    result: dict[str, Mapping[str, object]] = {}
    for node in raw:
        if not isinstance(node, Mapping) or not isinstance(node.get("node_id"), str):
            raise Phase10InputError("Fact Graph node is malformed")
        result[str(node["node_id"])] = node
    return result


def _pillars(nodes: Mapping[str, Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    result = {
        str(node.get("position")): node for node in nodes.values()
        if node.get("node_type") == "Pillar" and isinstance(node.get("position"), str)
    }
    missing = [position for position in ("year", "month", "day", "hour") if position not in result]
    if missing:
        raise Phase10InputError(f"Fact Graph missing four pillars: {', '.join(missing)}")
    return result


def _canonical_input_hash(value: Mapping[str, object], name: str) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase10InputError(f"{name} missing canonical_hash")
    return found


def _verify_input_hash(value: Mapping[str, object], name: str, record_type: str, *, allow_plain_digest: bool = False) -> str:
    found = _canonical_input_hash(value, name)
    metadata = {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}
    body = {key: child for key, child in value.items() if key not in metadata}
    expected = record_digest(record_type, body)
    plain_body = {key: child for key, child in value.items() if key != "canonical_hash"}
    valid = found == expected or (allow_plain_digest and found in {digest(body), digest(plain_body)})
    if not valid:
        raise Phase10InputError(f"{name} canonical_hash mismatch")
    return found


def _validate_inputs(
    fact_graph: Mapping[str, object], strength: Mapping[str, object], profile_id: str
) -> tuple[PatternProfile, dict[str, Mapping[str, object]], dict[str, Mapping[str, object]], str, str]:
    if not isinstance(fact_graph, Mapping) or not fact_graph:
        raise Phase10InputError("Fact Graph is required")
    if not isinstance(strength, Mapping) or not strength:
        raise Phase10InputError("Strength Result is required")
    try:
        profile = get_pattern_profile(profile_id)
    except ValueError as exc:
        raise Phase10InputError(str(exc)) from exc
    if fact_graph.get("prediction_validity") != "not_evaluated" or strength.get("prediction_validity") != "not_evaluated":
        raise Phase10InputError("input prediction_validity must be not_evaluated")
    if strength.get("classification") == "unresolved":
        raise Phase10InputError("Strength Result classification is unresolved")
    if strength.get("classification") not in {"very_weak", "weak", "balanced", "strong", "very_strong"}:
        raise Phase10InputError("Strength Result classification is missing or unsupported")
    nodes = _nodes(fact_graph)
    pillars = _pillars(nodes)
    day_master = pillars["day"].get("stem")
    if not isinstance(day_master, str) or day_master not in STEMS:
        raise Phase10InputError("Fact Graph day master is missing")
    if strength.get("day_master") != day_master:
        raise Phase10InputError("Fact Graph and Strength Result day master mismatch")
    ten_god_codes = {
        str(node_id).split(":", 2)[1]: node.get("code")
        for node_id, node in nodes.items()
        if node.get("node_type") == "TenGod" and str(node_id).startswith("ten-god:") and len(str(node_id).split(":", 2)) == 3
    }
    if set(ten_god_codes) != {"year", "month", "day", "hour"}:
        raise Phase10InputError("Fact Graph ten-god structure is incomplete")
    if any(ten_god_codes[position] != map_ten_god(day_master, str(pillars[position].get("stem"))).code for position in ten_god_codes):
        raise Phase10InputError("Fact Graph ten-god structure does not match the reviewed static mapping")
    graph_hash = _verify_input_hash(fact_graph, "Fact Graph", "BaziFactGraphResult", allow_plain_digest=True)
    strength_hash = _verify_input_hash(strength, "Strength Result", "DayMasterStrengthResult")
    strength_graph_hash = strength.get("fact_graph_hash")
    if strength_graph_hash is not None and strength_graph_hash != graph_hash:
        raise Phase10InputError("Fact Graph hash reference mismatch")
    node_ids = set(nodes)
    referenced = {
        str(node_id)
        for collection in ("roots", "visible_stems", "hidden_stems", "contribution_records")
        for item in strength.get(collection, []) if isinstance(item, Mapping)
        for node_id in item.get("source_node_ids", [])
    }
    if referenced and not referenced.issubset(node_ids):
        raise Phase10InputError("Strength Result contains unknown Fact Graph node references")
    month_branch = pillars["month"].get("branch")
    if not isinstance(month_branch, str):
        raise Phase10InputError("Fact Graph month branch is missing")
    expected_hidden = map_hidden_stems(month_branch, day_master=day_master)
    month_hidden = {
        int(node.get("ordinal", 0)): node for node in nodes.values()
        if node.get("node_type") == "HiddenStem" and str(node.get("node_id", "")).startswith("hidden-stem:month:")
    }
    if len(month_hidden) != len(expected_hidden) or any(
        ordinal not in month_hidden or month_hidden[ordinal].get("stem") != item.stem
        for ordinal, item in enumerate(expected_hidden, 1)
    ):
        raise Phase10InputError("Fact Graph month hidden-stem structure is incomplete")
    return profile, nodes, pillars, graph_hash, strength_hash


def _source_candidate(
    *, pattern_type: str, month_branch: str, hidden_stem: str | None, ordinal: int | None,
    source_kind: str, transparent_positions: Sequence[str], ten_god: str | None,
    node_ids: Sequence[str], strength_hash: str, profile: PatternProfile,
) -> PatternSourceCandidate:
    candidate_id = f"pattern:{pattern_type}:{source_kind}:{ordinal or 0}:{hidden_stem or 'none'}"
    payload = {
        "candidate_id": candidate_id, "pattern_type": pattern_type, "month_branch": month_branch,
        "hidden_stem": hidden_stem, "hidden_stem_ordinal": ordinal, "source_kind": source_kind,
        "is_transparent": bool(transparent_positions), "transparent_positions": sorted(transparent_positions),
        "ten_god": ten_god, "source_node_ids": sorted(set(node_ids)), "strength_result_hash": strength_hash,
        "profile_id": profile.profile_id, "source_ids": list(profile.source_ids),
    }
    return PatternSourceCandidate(canonical_digest=record_digest("PatternSourceCandidate", payload), **payload)  # type: ignore[arg-type]


def generate_pattern_candidates(
    nodes: Mapping[str, Mapping[str, object]], pillars: Mapping[str, Mapping[str, object]],
    strength: Mapping[str, object], strength_hash: str, profile: PatternProfile,
) -> tuple[PatternSourceCandidate, ...]:
    day_master = str(pillars["day"]["stem"])
    month_branch = str(pillars["month"]["branch"])
    visible = {position: str(node["stem"]) for position, node in pillars.items() if position != "day"}
    hidden = sorted(
        (node for node in nodes.values() if node.get("node_type") == "HiddenStem" and str(node.get("node_id", "")).startswith("hidden-stem:month:")),
        key=lambda node: int(node["ordinal"]),
    )
    candidates: list[PatternSourceCandidate] = []
    for node in hidden:
        stem = str(node["stem"])
        ordinal = int(node["ordinal"])
        ten_god = str(node["ten_god"])
        pattern_type = TEN_GOD_TO_PATTERN.get(ten_god)
        positions = tuple(sorted(position for position, value in visible.items() if value == stem))
        if pattern_type and (positions or ordinal == 1):
            source_kind = (
                ("month_principal_transparent", "month_middle_transparent", "month_residual_transparent")[ordinal - 1]
                if positions else "month_principal_structural"
            )
            source_nodes = [str(node["node_id"]), f"branch:month:{month_branch}"] + [f"stem:{position}:{stem}" for position in positions]
            candidates.append(_source_candidate(
                pattern_type=pattern_type, month_branch=month_branch, hidden_stem=stem, ordinal=ordinal,
                source_kind=source_kind, transparent_positions=positions, ten_god=ten_god,
                node_ids=source_nodes, strength_hash=strength_hash, profile=profile,
            ))
    principal = hidden[0]
    if principal.get("ten_god") == profile.jianlu_rules.get("principal_hidden_ten_god"):
        candidates.append(_source_candidate(
            pattern_type="jian_lu", month_branch=month_branch, hidden_stem=str(principal["stem"]), ordinal=1,
            source_kind="jian_lu_or_yang_ren", transparent_positions=(), ten_god=str(principal["ten_god"]),
            node_ids=(str(principal["node_id"]), f"branch:month:{month_branch}"), strength_hash=strength_hash, profile=profile,
        ))
    yangren_map = profile.yangren_rules.get("month_branches_by_day_stem", {})
    if isinstance(yangren_map, Mapping) and yangren_map.get(day_master) == month_branch:
        candidates.append(_source_candidate(
            pattern_type="yang_ren", month_branch=month_branch, hidden_stem=str(principal["stem"]), ordinal=1,
            source_kind="jian_lu_or_yang_ren", transparent_positions=(), ten_god=str(principal["ten_god"]),
            node_ids=(str(principal["node_id"]), f"branch:month:{month_branch}"), strength_hash=strength_hash, profile=profile,
        ))
    classification = str(strength["classification"])
    special_types = profile.special_pattern_candidate_rules.get(classification, [])
    if isinstance(special_types, list):
        for pattern_type in special_types:
            candidates.append(_source_candidate(
                pattern_type=str(pattern_type), month_branch=month_branch, hidden_stem=None, ordinal=None,
                source_kind="special_pattern_candidate", transparent_positions=(), ten_god=None,
                node_ids=("pillar:day", f"branch:month:{month_branch}"), strength_hash=strength_hash, profile=profile,
            ))
    relations = fact_graph_relations(nodes)
    if "stem_five_combine" in relations:
        candidates.append(_source_candidate(
            pattern_type="hua_qi_candidate", month_branch=month_branch, hidden_stem=None, ordinal=None,
            source_kind="special_pattern_candidate", transparent_positions=(), ten_god=None,
            node_ids=relations["stem_five_combine"], strength_hash=strength_hash, profile=profile,
        ))
    if not candidates:
        candidates.append(_source_candidate(
            pattern_type="special_pattern_unresolved", month_branch=month_branch, hidden_stem=None, ordinal=None,
            source_kind="unresolved", transparent_positions=(), ten_god=None,
            node_ids=("pillar:day", f"branch:month:{month_branch}"), strength_hash=strength_hash, profile=profile,
        ))
    return tuple(sorted(candidates, key=lambda item: item.candidate_id))


def fact_graph_relations(nodes: Mapping[str, Mapping[str, object]]) -> dict[str, tuple[str, ...]]:
    found: dict[str, list[str]] = {}
    for node in nodes.values():
        if node.get("node_type") != "Relation":
            continue
        relation_type = node.get("relation_type")
        if isinstance(relation_type, str):
            found.setdefault(relation_type, []).append(str(node["node_id"]))
    return {key: tuple(sorted(value)) for key, value in found.items()}


def _condition_result(
    candidate_id: str, kind: str, code: str, met: bool | None, weight: Decimal,
    observed: object, node_ids: Sequence[str], profile: PatternProfile,
) -> PatternConditionResult:
    condition = PatternCondition(
        condition_id=f"{candidate_id}:{kind}:{code}", condition_type=kind, description=code,
        weight=format(weight, "f"), source_ids=profile.source_ids,
    )
    payload = {
        "condition": condition.to_dict(), "outcome": "unresolved" if met is None else ("met" if met else "not_met"),
        "observed_value": observed, "source_node_ids": sorted(set(node_ids)),
    }
    return PatternConditionResult(canonical_digest=record_digest("PatternConditionResult", payload), condition=condition, outcome=payload["outcome"], observed_value=observed, source_node_ids=tuple(payload["source_node_ids"]))  # type: ignore[arg-type]


def _score_status(profile: PatternProfile, purity: Decimal) -> str:
    for band in profile.purity_thresholds:
        lower = Decimal(str(band["min_inclusive"]))
        upper_key = "max_inclusive" if "max_inclusive" in band else "max_exclusive"
        upper = Decimal(str(band[upper_key]))
        if purity >= lower and (purity <= upper if upper_key == "max_inclusive" else purity < upper):
            return str(band["status"])
    return "unresolved"


def evaluate_candidate(
    source: PatternSourceCandidate, all_sources: Sequence[PatternSourceCandidate], strength: Mapping[str, object],
    fact_graph_hash: str, strength_hash: str, profile: PatternProfile,
) -> tuple[PatternCandidateResult, tuple[PatternEvidenceRecord, ...]]:
    pattern_type = source.pattern_type
    visible_types = {
        TEN_GOD_TO_PATTERN.get(map_ten_god(strength["day_master"], str(item.get("stem"))).code)
        for item in strength.get("visible_stems", []) if isinstance(item, Mapping) and item.get("position") != "day"
    }
    visible_types.discard(None)
    est_weight = Decimal(profile.establishment_weights["month_source"])
    establishment = [
        _condition_result(source.candidate_id, "establishment", "month_command_source_present", True, est_weight, source.source_kind, source.source_node_ids, profile),
        _condition_result(source.candidate_id, "establishment", "transparent_stem", source.is_transparent, Decimal(profile.establishment_weights["transparent"]), list(source.transparent_positions), source.source_node_ids, profile),
        _condition_result(source.candidate_id, "establishment", "strength_context_recorded", True, Decimal(profile.establishment_weights["strength_context"]), strength["classification"], ("pillar:day",), profile),
    ]
    if not source.is_transparent:
        establishment.append(_condition_result(source.candidate_id, "establishment", "principal_structure_explicit", source.hidden_stem_ordinal == 1, Decimal(profile.establishment_weights["structural"]), source.hidden_stem_ordinal, source.source_node_ids, profile))
    breaking: list[PatternConditionResult] = []
    rescue: list[PatternConditionResult] = []
    unresolved: list[PatternConditionResult] = []
    if pattern_type in profile.ordinary_pattern_rules:
        rule = profile.ordinary_pattern_rules[pattern_type]
        assert isinstance(rule, Mapping)
        family = FAMILY[pattern_type]
        family_count = sum(1 for value in visible_types if value and FAMILY.get(value) == family)
        mixing = family_count > 1
        breaking.append(_condition_result(source.candidate_id, "breaking", f"{family}_mixing", mixing, Decimal(profile.break_weights["mixing"]), sorted(value for value in visible_types if value and FAMILY.get(value) == family), source.source_node_ids, profile))
        for breaker in rule.get("break", []):
            if str(breaker).endswith("_mixing"):
                continue
            met = breaker in visible_types or (breaker in {"jian_lu", "yang_ren"} and any(item.pattern_type == breaker for item in all_sources))
            weight_key = "direct_attack"
            if breaker in {"jian_lu", "yang_ren"}: weight_key = "peer_wealth"
            if breaker == "pian_yin": weight_key = "resource_output"
            breaking.append(_condition_result(source.candidate_id, "breaking", str(breaker), met, Decimal(profile.break_weights[weight_key]), sorted(visible_types), source.source_node_ids, profile))
        for rescuer in rule.get("rescue", []):
            met = rescuer in visible_types
            rescue_code = str(rescuer)
            weight_key = "resource_controls_output" if FAMILY.get(rescue_code) == "resource" else "wealth_generates_authority"
            if FAMILY.get(rescue_code) == "output": weight_key = "output_controls_killing"
            rescue.append(_condition_result(source.candidate_id, "rescue", rescue_code, met, Decimal(profile.rescue_weights[weight_key]), sorted(visible_types), source.source_node_ids, profile))
    elif pattern_type in SPECIAL_PATTERN_TYPES:
        unresolved.append(_condition_result(source.candidate_id, "unresolved", "special_pattern_final_judgement_not_implemented", None, Decimal("0"), profile.unresolved_conditions, source.source_node_ids, profile))
    elif pattern_type in {"jian_lu", "yang_ren"}:
        establishment.append(_condition_result(source.candidate_id, "establishment", f"{pattern_type}_specialized_month_condition", True, Decimal(profile.establishment_weights["structural"]), source.month_branch, source.source_node_ids, profile))
    establishment_score = sum((Decimal(item.condition.weight) for item in establishment if item.outcome == "met"), Decimal("0"))
    break_score = sum((Decimal(item.condition.weight) for item in breaking if item.outcome == "met"), Decimal("0"))
    rescue_score = sum((Decimal(item.condition.weight) for item in rescue if item.outcome == "met"), Decimal("0"))
    purity = min(Decimal("100"), max(Decimal("0"), establishment_score - break_score + rescue_score))
    status = _score_status(profile, purity)
    if pattern_type in SPECIAL_PATTERN_TYPES:
        status = "conditionally_supported" if pattern_type not in {"hua_qi_candidate", "special_pattern_unresolved"} else "unresolved"
    records: list[PatternEvidenceRecord] = []
    for item in (*establishment, *breaking, *rescue, *unresolved):
        kind = item.condition.condition_type
        active = item.outcome in {"met", "unresolved"}
        direction = "contradict" if kind in {"breaking", "unresolved"} and active else "support"
        contribution = item.condition.weight if active else "0"
        evidence_id = f"evidence:{item.condition.condition_id}"
        payload = {
            "evidence_id": evidence_id, "candidate_id": source.candidate_id, "pattern_type": pattern_type,
            "evidence_type": f"{kind}:{item.condition.description}", "direction": direction, "contribution": contribution,
            "priority": 80 if kind == "establishment" else 70 if kind == "breaking" else 60,
            "source_node_ids": list(item.source_node_ids), "source_result_hashes": [fact_graph_hash, strength_hash],
            "profile_id": profile.profile_id, "source_ids": list(profile.source_ids),
        }
        records.append(PatternEvidenceRecord(canonical_digest=record_digest("PatternEvidenceRecord", payload), **payload))  # type: ignore[arg-type]
    purity_payload = {
        "evidence_id": f"evidence:{source.candidate_id}:purity", "candidate_id": source.candidate_id,
        "pattern_type": pattern_type, "evidence_type": "pattern_purity", "direction": "support" if purity >= Decimal("70") else "contradict",
        "contribution": format(purity, "f"), "priority": 65, "source_node_ids": list(source.source_node_ids),
        "source_result_hashes": [fact_graph_hash, strength_hash], "profile_id": profile.profile_id,
        "source_ids": list(profile.source_ids),
    }
    records.append(PatternEvidenceRecord(canonical_digest=record_digest("PatternEvidenceRecord", purity_payload), **purity_payload))  # type: ignore[arg-type]
    payload = {
        "candidate": source.to_dict(), "pattern_type": pattern_type, "status": status,
        "purity_score": format(purity, "f"), "establishment_score": format(establishment_score, "f"),
        "break_score": format(break_score, "f"), "rescue_score": format(rescue_score, "f"),
        "establishment_conditions": [item.to_dict() for item in establishment],
        "breaking_conditions": [item.to_dict() for item in breaking],
        "rescue_conditions": [item.to_dict() for item in rescue],
        "unresolved_conditions": [item.to_dict() for item in unresolved],
        "evidence_ids": [item.evidence_id for item in records],
    }
    result = PatternCandidateResult(
        candidate=source, pattern_type=pattern_type, status=status, purity_score=format(purity, "f"),
        establishment_score=format(establishment_score, "f"), break_score=format(break_score, "f"), rescue_score=format(rescue_score, "f"),
        establishment_conditions=tuple(payload["establishment_conditions"]), breaking_conditions=tuple(payload["breaking_conditions"]),
        rescue_conditions=tuple(payload["rescue_conditions"]), unresolved_conditions=tuple(payload["unresolved_conditions"]),
        evidence_ids=tuple(payload["evidence_ids"]), canonical_digest=record_digest("PatternCandidateResult", payload),
    )
    return result, tuple(records)


def evaluate_bazi_pattern(
    fact_graph: Mapping[str, object], strength_result: Mapping[str, object], *,
    profile_id: str = DEFAULT_PHASE10_PROFILE_ID,
) -> BaziPatternEvaluationResult:
    profile, nodes, pillars, graph_hash, strength_hash = _validate_inputs(fact_graph, strength_result, profile_id)
    sources = generate_pattern_candidates(nodes, pillars, strength_result, strength_hash, profile)
    results: list[PatternCandidateResult] = []
    evidence: list[PatternEvidenceRecord] = []
    for source in sources:
        result, records = evaluate_candidate(source, sources, strength_result, graph_hash, strength_hash, profile)
        results.append(result)
        evidence.extend(records)
    results.sort(key=lambda item: item.candidate_id)
    evidence.sort(key=lambda item: item.evidence_id)
    conflicts, primary = resolve_candidate_conflicts(results, profile)
    result_by_id = {item.candidate_id: item for item in results}
    for conflict in conflicts:
        for candidate_id in conflict.candidate_ids:
            candidate = result_by_id[candidate_id]
            won = candidate_id in conflict.winning_candidate_ids
            conflict_payload = {
                "evidence_id": f"evidence:{conflict.conflict_id}:{candidate_id}", "candidate_id": candidate_id,
                "pattern_type": candidate.pattern_type, "evidence_type": "candidate_conflict",
                "direction": "support" if won and conflict.resolution_status == "resolved" else "contradict",
                "contribution": "0", "priority": 100,
                "source_node_ids": sorted({node_id for item_id in conflict.candidate_ids for node_id in result_by_id[item_id].candidate.source_node_ids}),
                "source_result_hashes": [graph_hash, strength_hash], "profile_id": profile.profile_id,
                "source_ids": list(profile.source_ids),
            }
            evidence.append(PatternEvidenceRecord(canonical_digest=record_digest("PatternEvidenceRecord", conflict_payload), **conflict_payload))  # type: ignore[arg-type]
    evidence.sort(key=lambda item: item.evidence_id)
    unresolved_conflicts = [item for item in conflicts if item.resolution_status == "unresolved"]
    unresolved = tuple(
        {"code": "equal_priority_candidate_conflict", "conflict_id": item.conflict_id}
        for item in unresolved_conflicts
    )
    body = {
        "fact_graph_hash": graph_hash, "strength_result_hash": strength_hash, "profile_id": profile.profile_id,
        "candidates": [item.to_dict() for item in results], "primary_candidates": list(primary),
        "rejected_candidates": [item.candidate_id for item in results if item.status in {"rejected", "contradicted"}],
        "unresolved_candidates": [item.candidate_id for item in results if item.status == "unresolved"],
        "conflicts": [item.to_dict() for item in conflicts], "evidence_records": [item.to_dict() for item in evidence],
        "provenance_index": {"profile_hash": profile.canonical_hash, "fact_graph_hash": graph_hash, "strength_result_hash": strength_hash, "source_ids": list(profile.source_ids)},
        "warnings": ["structural_pattern_evaluation_only", "no_prediction_or_favorable_unfavorable_judgement", "special_patterns_are_candidate_boundaries_only"],
        "unresolved": list(unresolved),
    }
    canonical_hash = record_digest("BaziPatternEvaluationResult", body)
    return BaziPatternEvaluationResult(
        fact_graph_hash=graph_hash, strength_result_hash=strength_hash, profile_id=profile.profile_id,
        candidates=tuple(results), primary_candidates=primary,
        rejected_candidates=tuple(body["rejected_candidates"]), unresolved_candidates=tuple(body["unresolved_candidates"]),
        conflicts=conflicts, evidence_records=tuple(evidence), provenance_index=body["provenance_index"],
        warnings=tuple(body["warnings"]), unresolved=unresolved, canonical_hash=canonical_hash,
    )


def pattern_result_to_phase8_evidence(result: BaziPatternEvaluationResult | Mapping[str, object]):
    if isinstance(result, BaziPatternEvaluationResult):
        return tuple(item.to_phase8_evidence() for item in result.evidence_records)
    raw = result.get("evidence_records")
    if not isinstance(raw, list):
        raise Phase10InputError("evidence_records must be an array")
    records: list[PatternEvidenceRecord] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise Phase10InputError("evidence record must be an object")
        records.append(PatternEvidenceRecord(
            evidence_id=str(item["evidence_id"]), candidate_id=str(item["candidate_id"]), pattern_type=str(item["pattern_type"]),
            evidence_type=str(item["evidence_type"]), direction=str(item["direction"]), contribution=str(item["contribution"]),
            priority=int(item["priority"]), source_node_ids=tuple(str(value) for value in item["source_node_ids"]),
            source_result_hashes=tuple(str(value) for value in item["source_result_hashes"]), profile_id=str(item["profile_id"]),
            source_ids=tuple(str(value) for value in item["source_ids"]), canonical_digest=str(item["canonical_digest"]),
        ))
    return tuple(item.to_phase8_evidence() for item in sorted(records, key=lambda value: value.evidence_id))
