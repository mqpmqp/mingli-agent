from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping, Sequence

from .contracts.serialization import digest
from .derived.static_engine import BRANCHES, CONTROLS, GENERATES, STEMS, STEM_ELEMENT
from .phase11_contracts import (
    BaziRegulationEvaluationResult,
    CandidateAvailability,
    CandidateContribution,
    CandidateResolution,
    ElementPassageNeed,
    Phase11InputError,
    PatternRemedyNeed,
    RegulationEvidenceRecord,
    RegulationLensProfile,
    RegulationNeed,
    RegulationProfile,
    SeasonalClimateNeed,
    StrengthBalanceNeed,
    YongShenCandidate,
    record_digest,
)
from .phase11_profiles import DEFAULT_PHASE11_PROFILE_ID, get_regulation_profile
from .phase11_resolution import build_candidate_conflicts, candidate_rank, primary_candidate_ids
from .phase9_contracts import ELEMENTS

SCORE_ZERO = Decimal("0")
SCORE_HUNDRED = Decimal("100")
PATTERN_REMEDY_RELATIONS = {
    "zheng_guan": ("resource", "wealth"),
    "qi_sha": ("output", "resource"),
    "zheng_yin": ("peer", "authority"),
    "pian_yin": ("wealth", "authority"),
    "shi_shen": ("wealth",),
    "shang_guan": ("resource", "wealth"),
    "zheng_cai": ("authority",),
    "pian_cai": ("authority",),
    "jian_lu": ("output", "wealth", "authority"),
    "yang_ren": ("output", "wealth", "authority"),
}
PASSAGE_CHAINS = (
    ("wood", "earth", "fire"),
    ("earth", "water", "metal"),
    ("water", "fire", "wood"),
    ("fire", "metal", "earth"),
    ("metal", "wood", "water"),
)
FORBIDDEN_REQUESTS = {
    "final_yongshen",
    "definite_yongshen",
    "absolute_favorable",
    "absolute_unfavorable",
    "xiji",
    "luck_cycle_prediction",
    "event_prediction",
    "natural_language_prediction",
}


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _quantize(profile: RegulationProfile, value: Decimal) -> Decimal:
    return value.quantize(Decimal(profile.score_precision), rounding=ROUND_HALF_UP)


def _score(profile: RegulationProfile, value: Decimal) -> str:
    return format(_quantize(profile, value), "f")


def _nodes(fact_graph: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw = fact_graph.get("nodes")
    if not isinstance(raw, list):
        raise Phase11InputError("Fact Graph missing nodes")
    result: dict[str, Mapping[str, object]] = {}
    for node in raw:
        if not isinstance(node, Mapping) or not isinstance(node.get("node_id"), str):
            raise Phase11InputError("Fact Graph node is malformed")
        result[str(node["node_id"])] = node
    return result


def _pillars(nodes: Mapping[str, Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    result = {
        str(node.get("position")): node for node in nodes.values()
        if node.get("node_type") == "Pillar" and isinstance(node.get("position"), str)
    }
    missing = [position for position in ("year", "month", "day", "hour") if position not in result]
    if missing:
        raise Phase11InputError(f"Fact Graph missing four pillars: {', '.join(missing)}")
    return result


def _canonical_input_hash(value: Mapping[str, object], name: str) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase11InputError(f"{name} missing canonical_hash")
    return found


def _verify_input_hash(value: Mapping[str, object], name: str, record_type: str, *, allow_plain_digest: bool = False) -> str:
    found = _canonical_input_hash(value, name)
    metadata = {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}
    body = {key: child for key, child in value.items() if key not in metadata}
    expected = record_digest(record_type, body)
    plain_body = {key: child for key, child in value.items() if key != "canonical_hash"}
    valid = found == expected or (allow_plain_digest and found in {digest(body), digest(plain_body)})
    if not valid:
        raise Phase11InputError(f"{name} canonical_hash mismatch")
    return found


def _lens_profile(profile: RegulationProfile, lens: str) -> RegulationLensProfile:
    for item in profile.lens_profiles:
        if item.lens == lens:
            return item
    raise Phase11InputError(f"Profile missing lens: {lens}")


def _validate_inputs(
    fact_graph: Mapping[str, object],
    strength_result: Mapping[str, object],
    pattern_result: Mapping[str, object],
    profile_id: str,
    requested_outputs: Sequence[str],
) -> tuple[RegulationProfile, dict[str, Mapping[str, object]], dict[str, Mapping[str, object]], str, str, str]:
    if set(requested_outputs) & FORBIDDEN_REQUESTS:
        raise Phase11InputError("Phase 11 cannot return final XiJi, luck-cycle, event, or natural-language prediction outputs")
    if not isinstance(fact_graph, Mapping) or not fact_graph:
        raise Phase11InputError("Fact Graph is required")
    if not isinstance(strength_result, Mapping) or not strength_result:
        raise Phase11InputError("Strength Result is required")
    if not isinstance(pattern_result, Mapping) or not pattern_result:
        raise Phase11InputError("Pattern Result is required")
    try:
        profile = get_regulation_profile(profile_id)
    except ValueError as exc:
        raise Phase11InputError(str(exc)) from exc
    if not profile.reviewed:
        raise Phase11InputError("Profile must be reviewed")
    for name, value in (("Fact Graph", fact_graph), ("Strength Result", strength_result), ("Pattern Result", pattern_result)):
        if value.get("prediction_validity") != "not_evaluated":
            raise Phase11InputError(f"{name} prediction_validity must be not_evaluated")
    if strength_result.get("classification") == "unresolved":
        raise Phase11InputError("Strength Result classification is unresolved")
    if strength_result.get("classification") not in {"very_weak", "weak", "balanced", "strong", "very_strong"}:
        raise Phase11InputError("Strength Result classification is missing or unsupported")
    nodes = _nodes(fact_graph)
    pillars = _pillars(nodes)
    day_master = pillars["day"].get("stem")
    month_branch = pillars["month"].get("branch")
    if not isinstance(day_master, str) or day_master not in STEMS:
        raise Phase11InputError("Fact Graph day master is missing")
    if not isinstance(month_branch, str) or month_branch not in BRANCHES:
        raise Phase11InputError("Fact Graph month branch is missing")
    if strength_result.get("day_master") != day_master:
        raise Phase11InputError("Fact Graph and Strength Result day master mismatch")
    graph_hash = _verify_input_hash(fact_graph, "Fact Graph", "BaziFactGraphResult", allow_plain_digest=True)
    strength_hash = _verify_input_hash(strength_result, "Strength Result", "DayMasterStrengthResult")
    pattern_hash = _verify_input_hash(pattern_result, "Pattern Result", "BaziPatternEvaluationResult")
    if strength_result.get("fact_graph_hash") not in (None, graph_hash):
        raise Phase11InputError("Strength Result Fact Graph hash reference mismatch")
    if pattern_result.get("fact_graph_hash") != graph_hash or pattern_result.get("strength_result_hash") != strength_hash:
        raise Phase11InputError("Pattern Result hash reference mismatch")
    return profile, nodes, pillars, graph_hash, strength_hash, pattern_hash


def _element_for_relationship(day_master_element: str, relationship: str) -> str:
    if relationship == "peer":
        return day_master_element
    if relationship == "output":
        return GENERATES[day_master_element]
    if relationship == "wealth":
        return CONTROLS[day_master_element]
    if relationship == "resource":
        return next(element for element, generated in GENERATES.items() if generated == day_master_element)
    if relationship == "authority":
        return next(element for element, controlled in CONTROLS.items() if controlled == day_master_element)
    raise Phase11InputError(f"unsupported relationship: {relationship}")


def _relationship_to_day_master(day_master_element: str, target_element: str) -> str:
    if target_element == day_master_element:
        return "peer"
    if GENERATES[target_element] == day_master_element:
        return "resource"
    if GENERATES[day_master_element] == target_element:
        return "output"
    if CONTROLS[day_master_element] == target_element:
        return "wealth"
    if CONTROLS[target_element] == day_master_element:
        return "authority"
    raise Phase11InputError(f"cannot classify relationship: {day_master_element}->{target_element}")


def _make_need(cls, record_type: str, payload: Mapping[str, object]):
    return cls(canonical_digest=record_digest(record_type, payload), **payload)


def _strength_balance_needs(
    strength: Mapping[str, object],
    graph_hash: str,
    strength_hash: str,
    profile: RegulationProfile,
) -> tuple[StrengthBalanceNeed, ...]:
    lens = _lens_profile(profile, "strength_balance")
    classification = str(strength["classification"])
    day_master_element = str(strength["day_master_element"])
    relationships: tuple[str, ...]
    if classification in {"very_weak", "weak"}:
        relationships = ("resource", "peer")
    elif classification in {"strong", "very_strong"}:
        relationships = ("output", "wealth", "authority")
    else:
        relationships = ()
    target_elements = tuple(dict.fromkeys(_element_for_relationship(day_master_element, relationship) for relationship in relationships))
    need_type = "no_dominant_balance_need" if not target_elements else f"{classification}_balance_regulation_need"
    severity = str(lens.weights.get(classification, "0"))
    payload = {
        "need_id": f"need:strength_balance:{classification}",
        "lens": "strength_balance",
        "need_type": need_type,
        "target_elements": list(target_elements),
        "severity": severity,
        "description": "Phase 9 strength balance regulation need",
        "confidence_ceiling": lens.confidence_ceiling,
        "source_node_ids": ["pillar:day"],
        "source_result_hashes": [graph_hash, strength_hash],
        "profile_id": lens.profile_id,
        "source_ids": list(lens.source_ids),
        "strength_classification": classification,
        "day_master_element": day_master_element,
        "support_relationships": list(relationships),
    }
    return (_make_need(StrengthBalanceNeed, "StrengthBalanceNeed", payload),)


def _seasonal_climate_need(
    pillars: Mapping[str, Mapping[str, object]],
    graph_hash: str,
    strength_hash: str,
    profile: RegulationProfile,
) -> SeasonalClimateNeed:
    lens = _lens_profile(profile, "seasonal_climate")
    month_branch = str(pillars["month"]["branch"])
    index = BRANCHES.index(month_branch)
    if index in {11, 0, 1}:
        season = "winter"
    elif index in {2, 3, 4}:
        season = "spring"
    elif index in {5, 6, 7}:
        season = "summer"
    else:
        season = "autumn"
    cold = "high" if index in {11, 0, 1} else "medium" if index in {2, 10} else "low"
    heat = "high" if index in {5, 6, 7} else "medium" if index in {4, 8} else "low"
    dry = "high" if index in {5, 8, 9, 10} else "medium" if index in {6, 7} else "low"
    damp = "high" if index in {1, 4, 7, 10} else "medium" if index in {11, 0} else "low"
    target_elements: list[str] = []
    contraindicated: list[str] = []
    severity = Decimal("25")
    if cold in {"high", "medium"}:
        target_elements.append("fire")
        contraindicated.append("water")
        severity = max(severity, Decimal(str(lens.weights["cold"] if cold == "high" else lens.weights["mild"])))
    if heat in {"high", "medium"}:
        target_elements.append("water")
        contraindicated.append("fire")
        severity = max(severity, Decimal(str(lens.weights["heat"] if heat == "high" else lens.weights["mild"])))
    if dry in {"high", "medium"}:
        target_elements.extend(("water", "wood"))
        contraindicated.extend(("fire", "earth"))
        severity = max(severity, Decimal(str(lens.weights["dry"] if dry == "high" else lens.weights["mild"])))
    if damp in {"high", "medium"}:
        target_elements.extend(("earth", "fire"))
        contraindicated.append("water")
        severity = max(severity, Decimal(str(lens.weights["damp"] if damp == "high" else lens.weights["mild"])))
    payload = {
        "need_id": f"need:seasonal_climate:{month_branch}",
        "lens": "seasonal_climate",
        "need_type": "structural_seasonal_climate",
        "target_elements": sorted(set(target_elements)),
        "severity": _score(profile, severity),
        "description": "Structural cold heat dryness dampness regulation need",
        "confidence_ceiling": lens.confidence_ceiling,
        "source_node_ids": [f"branch:month:{month_branch}", "pillar:month"],
        "source_result_hashes": [graph_hash, strength_hash],
        "profile_id": lens.profile_id,
        "source_ids": list(lens.source_ids),
        "month_branch": month_branch,
        "season": season,
        "cold_tendency": cold,
        "heat_tendency": heat,
        "dryness_tendency": dry,
        "dampness_tendency": damp,
        "contraindicated_overcorrections": sorted(set(contraindicated)),
        "structural_seasonal_climate_status": "evaluated",
        "classical_daymaster_month_tiaohou_status": "not_evaluated",
        "explicit_exclusions": list(lens.explicit_exclusions),
    }
    return _make_need(SeasonalClimateNeed, "SeasonalClimateNeed", payload)


def _source_nodes_for_elements(strength: Mapping[str, object], elements: Sequence[str]) -> tuple[str, ...]:
    found: set[str] = set()
    for collection in ("visible_stems", "hidden_stems", "roots", "contribution_records"):
        for item in strength.get(collection, []):
            if isinstance(item, Mapping) and item.get("element") in elements:
                found.update(str(node_id) for node_id in item.get("source_node_ids", []))
    return tuple(sorted(found))


def _element_passage_needs(
    strength: Mapping[str, object],
    graph_hash: str,
    strength_hash: str,
    profile: RegulationProfile,
) -> tuple[ElementPassageNeed, ...]:
    lens = _lens_profile(profile, "element_passage")
    minimum = Decimal(str(lens.thresholds["minimum_side_score"]))
    element_scores = strength.get("element_scores")
    if not isinstance(element_scores, Mapping):
        raise Phase11InputError("Strength Result element_scores is missing")
    needs: list[ElementPassageNeed] = []
    for left, right, mediator in PASSAGE_CHAINS:
        left_score = Decimal(str(element_scores.get(left, "0")))
        right_score = Decimal(str(element_scores.get(right, "0")))
        if left_score < minimum or right_score < minimum:
            continue
        source_nodes = _source_nodes_for_elements(strength, (left, right, mediator))
        if not source_nodes:
            continue
        payload = {
            "need_id": f"need:element_passage:{left}-{right}:{mediator}",
            "lens": "element_passage",
            "need_type": "structural_passage",
            "target_elements": [mediator],
            "severity": str(lens.weights["active_passage"]),
            "description": "Five-element passage mediator for structural control-chain blockage",
            "confidence_ceiling": lens.confidence_ceiling,
            "source_node_ids": list(source_nodes),
            "source_result_hashes": [graph_hash, strength_hash],
            "profile_id": lens.profile_id,
            "source_ids": list(lens.source_ids),
            "conflict_elements": [left, right],
            "blocked_chain": f"{left}_controls_{right}",
            "mediator_element": mediator,
            "chain_before": [left, right],
            "chain_after": [left, mediator, right],
            "supporting_facts": [f"{left}_score={left_score}", f"{right}_score={right_score}"],
            "contradicting_facts": [],
            "availability": "thresholds_met",
        }
        needs.append(_make_need(ElementPassageNeed, "ElementPassageNeed", payload))
    return tuple(sorted(needs, key=lambda item: item.need_id))


def _pattern_remedy_needs(
    pattern_result: Mapping[str, object],
    pattern_hash: str,
    profile: RegulationProfile,
    day_master_element: str,
) -> tuple[PatternRemedyNeed, ...]:
    lens = _lens_profile(profile, "pattern_remedy")
    candidates = pattern_result.get("candidates")
    if not isinstance(candidates, list):
        raise Phase11InputError("Pattern Result candidates are missing")
    primary = set(str(item) for item in pattern_result.get("primary_candidates", []) if isinstance(item, str))
    needs: list[PatternRemedyNeed] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        pattern_type = str(candidate.get("pattern_type", ""))
        status = str(candidate.get("status", ""))
        relationships = PATTERN_REMEDY_RELATIONS.get(pattern_type)
        if not relationships:
            continue
        if status == "unresolved":
            severity = Decimal(str(lens.weights["unresolved_pattern"]))
        elif status in {"rejected", "contradicted"}:
            severity = Decimal(str(lens.weights["rejected_pattern"]))
        elif status == "weakened":
            severity = Decimal(str(lens.weights["weakened_pattern"]))
        elif status == "conditionally_supported":
            severity = Decimal(str(lens.weights["conditional_pattern"]))
        else:
            severity = Decimal(str(lens.weights["supported_pattern"]))
        if str(candidate.get("candidate_id")) not in primary:
            severity *= Decimal(str(lens.weights["secondary_multiplier"]))
        target_elements = tuple(dict.fromkeys(_element_for_relationship(day_master_element, relation) for relation in relationships))
        breaking_ids = tuple(
            str(item.get("condition", {}).get("condition_id"))
            for item in candidate.get("breaking_conditions", [])
            if isinstance(item, Mapping)
        )
        rescue_ids = tuple(
            str(item.get("condition", {}).get("condition_id"))
            for item in candidate.get("rescue_conditions", [])
            if isinstance(item, Mapping)
        )
        source_node_ids = tuple(
            str(node_id)
            for evidence in pattern_result.get("evidence_records", [])
            if isinstance(evidence, Mapping) and evidence.get("candidate_id") == candidate.get("candidate_id")
            for node_id in evidence.get("source_node_ids", [])
        )
        payload = {
            "need_id": f"need:pattern_remedy:{candidate.get('candidate_id')}",
            "lens": "pattern_remedy",
            "need_type": "pattern_breaking_rescue_remedy",
            "target_elements": list(target_elements),
            "severity": _score(profile, severity),
            "description": "Phase 10 pattern remedy candidate contribution",
            "confidence_ceiling": lens.confidence_ceiling,
            "source_node_ids": sorted(set(source_node_ids)),
            "source_result_hashes": [pattern_hash],
            "profile_id": lens.profile_id,
            "source_ids": list(lens.source_ids),
            "pattern_candidate_id": str(candidate.get("candidate_id")),
            "pattern_type": pattern_type,
            "pattern_status": status,
            "purity_score": str(candidate.get("purity_score", "0")),
            "breaking_evidence_ids": sorted(set(breaking_ids)),
            "rescue_evidence_ids": sorted(set(rescue_ids)),
            "rescue_role": "low_confidence_boundary" if status in {"rejected", "contradicted", "unresolved"} else "candidate_contribution",
        }
        needs.append(_make_need(PatternRemedyNeed, "PatternRemedyNeed", payload))
    return tuple(sorted(needs, key=lambda item: item.need_id))


def _availability_base(
    element: str,
    strength: Mapping[str, object],
    graph_hash: str,
    strength_hash: str,
    profile: RegulationProfile,
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], Decimal]:
    visible = tuple(
        sorted(
            str(item.get("position"))
            for item in strength.get("visible_stems", [])
            if isinstance(item, Mapping) and item.get("element") == element and item.get("position") != "day"
        )
    )
    hidden = tuple(
        sorted(
            f"{item.get('branch_position')}:{item.get('hidden_stem_ordinal')}"
            for item in strength.get("hidden_stems", [])
            if isinstance(item, Mapping) and item.get("element") == element
        )
    )
    roots = tuple(
        sorted(
            str(item.get("branch_position"))
            for item in strength.get("roots", [])
            if isinstance(item, Mapping) and item.get("element") == element
        )
    )
    source_nodes = _source_nodes_for_elements(strength, (element,))
    if len(roots) >= 2:
        status = "multiple_rooted"
    elif len(visible) >= 2:
        status = "multiple_visible"
    elif visible and roots:
        status = "visible_rooted"
    elif roots and not visible:
        status = "rooted_hidden"
    elif visible:
        status = "visible_unrooted"
    elif hidden:
        status = "hidden_only"
    else:
        status = "absent"
    element_scores = strength.get("element_scores", {})
    element_score = Decimal(str(element_scores.get(element, "0"))) if isinstance(element_scores, Mapping) else Decimal("0")
    excess = Decimal("0")
    if element_score >= Decimal("220"):
        excess = Decimal("70")
    elif element_score >= Decimal("180"):
        excess = Decimal("45")
    elif element_score >= Decimal("140"):
        excess = Decimal("20")
    return status, visible, hidden, roots, source_nodes, excess


def _contribution(
    candidate_id: str,
    element: str,
    lens: str,
    direction: str,
    contribution_type: str,
    score: Decimal,
    priority: int,
    need: RegulationNeed,
    profile: RegulationProfile,
) -> CandidateContribution:
    payload = {
        "contribution_id": f"contribution:{candidate_id}:{lens}:{contribution_type}:{need.need_id}",
        "candidate_id": candidate_id,
        "element": element,
        "stem_carrier": None,
        "lens": lens,
        "direction": direction,
        "contribution_type": contribution_type,
        "score": _score(profile, score),
        "priority": priority,
        "need_id": need.need_id,
        "source_node_ids": list(need.source_node_ids),
        "source_result_hashes": list(need.source_result_hashes),
        "profile_id": need.profile_id,
        "source_ids": list(need.source_ids),
    }
    return CandidateContribution(canonical_digest=record_digest("CandidateContribution", payload), **payload)  # type: ignore[arg-type]


def _build_contributions(
    strength_needs: Sequence[StrengthBalanceNeed],
    climate_needs: Sequence[SeasonalClimateNeed],
    passage_needs: Sequence[ElementPassageNeed],
    remedy_needs: Sequence[PatternRemedyNeed],
    profile: RegulationProfile,
) -> tuple[CandidateContribution, ...]:
    records: list[CandidateContribution] = []
    for need in strength_needs:
        for element in need.target_elements:
            records.append(_contribution(f"regulation:element:{element}", element, "strength_balance", "support", "strength_balance_need", Decimal(need.severity), 80, need, profile))
    for need in climate_needs:
        for element in need.target_elements:
            records.append(_contribution(f"regulation:element:{element}", element, "seasonal_climate", "support", "structural_climate_need", Decimal(need.severity), 70, need, profile))
        for element in need.contraindicated_overcorrections:
            records.append(_contribution(f"regulation:element:{element}", element, "seasonal_climate", "contradict", "climate_overcorrection_risk", Decimal("35"), 70, need, profile))
    for need in passage_needs:
        records.append(_contribution(f"regulation:element:{need.mediator_element}", need.mediator_element, "element_passage", "support", "passage_mediator_need", Decimal(need.severity), 60, need, profile))
    for need in remedy_needs:
        direction = "unresolved" if need.pattern_status == "unresolved" else "support"
        score = Decimal(need.severity)
        for element in need.target_elements:
            records.append(_contribution(f"regulation:element:{element}", element, "pattern_remedy", direction, "pattern_remedy_need", score, 90, need, profile))
    return tuple(sorted(records, key=lambda item: item.contribution_id))


def _availability(
    candidate_id: str,
    element: str,
    need_score: Decimal,
    strength: Mapping[str, object],
    graph_hash: str,
    strength_hash: str,
    profile: RegulationProfile,
) -> CandidateAvailability:
    status, visible, hidden, roots, source_nodes, excess = _availability_base(element, strength, graph_hash, strength_hash, profile)
    payload = {
        "candidate_id": candidate_id,
        "element": element,
        "status": status,
        "candidate_need": _score(profile, need_score),
        "candidate_presence": _score(profile, Decimal(str(profile.availability_weights[status]))),
        "candidate_accessibility": _score(profile, Decimal(str(profile.availability_weights[status]))),
        "candidate_excess_risk": _score(profile, excess),
        "visible_positions": list(visible),
        "hidden_positions": list(hidden),
        "root_positions": list(roots),
        "source_node_ids": list(source_nodes),
        "source_result_hashes": [graph_hash, strength_hash],
        "profile_id": profile.profile_id,
        "source_ids": list(profile.source_ids),
    }
    return CandidateAvailability(canonical_digest=record_digest("CandidateAvailability", payload), **payload)  # type: ignore[arg-type]


def _status_from_score(score: Decimal, support_lenses: Sequence[str], contradiction_score: Decimal, unresolved: bool, availability: CandidateAvailability, profile: RegulationProfile) -> str:
    hard = Decimal(str(profile.conflict_thresholds["hard_contradiction"]))
    if unresolved:
        return "unresolved"
    if contradiction_score >= hard and support_lenses:
        return "conflicted"
    if contradiction_score >= hard:
        return "contradicted"
    if not support_lenses:
        return "unavailable" if availability.status == "absent" else "secondary"
    capped = min(SCORE_HUNDRED, max(SCORE_ZERO, score))
    for band in profile.candidate_thresholds:
        lower = Decimal(str(band["min_inclusive"]))
        upper_key = "max_inclusive" if "max_inclusive" in band else "max_exclusive"
        upper = Decimal(str(band[upper_key]))
        if capped >= lower and (capped <= upper if upper_key == "max_inclusive" else capped < upper):
            status = str(band["status"])
            if status == "supported" and len(support_lenses) < 2:
                return "conditionally_supported"
            return status
    return "unresolved"


def _candidate(
    element: str,
    contributions: Sequence[CandidateContribution],
    strength: Mapping[str, object],
    pattern: Mapping[str, object],
    graph_hash: str,
    strength_hash: str,
    pattern_hash: str,
    profile: RegulationProfile,
) -> YongShenCandidate:
    candidate_id = f"regulation:element:{element}"
    own = tuple(item for item in contributions if item.element == element)
    support_lenses = tuple(sorted({item.lens for item in own if item.direction == "support"}))
    contradict_lenses = tuple(sorted({item.lens for item in own if item.direction == "contradict"}))
    unresolved_lenses = tuple(sorted({item.lens for item in own if item.direction == "unresolved"}))
    weighted_by_lens: dict[str, Decimal] = {lens: Decimal("0") for lens in ("strength_balance", "seasonal_climate", "element_passage", "pattern_remedy")}
    contradiction_score = Decimal("0")
    for item in own:
        weight = Decimal(str(profile.per_lens_weights[item.lens]))
        score = Decimal(item.score) * weight
        if item.direction == "support":
            weighted_by_lens[item.lens] += score
        elif item.direction == "contradict":
            contradiction_score += score
    need_score = sum(weighted_by_lens.values(), Decimal("0"))
    availability = _availability(candidate_id, element, need_score, strength, graph_hash, strength_hash, profile)
    availability_score = Decimal(availability.candidate_accessibility)
    consensus_bonus = Decimal(str(profile.conflict_thresholds["consensus_bonus"])) if len(support_lenses) >= 2 else Decimal("0")
    unresolved_penalty = Decimal(str(profile.conflict_thresholds["unresolved_penalty"])) if unresolved_lenses else Decimal("0")
    excess = Decimal(availability.candidate_excess_risk)
    if excess >= Decimal("60"):
        excess_penalty = Decimal(str(profile.overcorrection_penalties["severe"]))
    elif excess >= Decimal("30"):
        excess_penalty = Decimal(str(profile.overcorrection_penalties["strong"]))
    elif excess > 0:
        excess_penalty = Decimal(str(profile.overcorrection_penalties["mild"]))
    else:
        excess_penalty = Decimal("0")
    combined = need_score + availability_score + consensus_bonus - contradiction_score - unresolved_penalty - excess_penalty
    combined = min(SCORE_HUNDRED, max(SCORE_ZERO, combined))
    status = _status_from_score(combined, support_lenses, contradiction_score, bool(unresolved_lenses), availability, profile)
    stem_carriers = tuple(stem for stem in STEMS if STEM_ELEMENT[stem] == element)
    source_node_ids = tuple(sorted({node_id for item in own for node_id in item.source_node_ids} | set(availability.source_node_ids)))
    source_result_hashes = tuple(sorted({graph_hash, strength_hash, pattern_hash}))
    pattern_types = tuple(
        sorted(
            str(item.get("pattern_type"))
            for item in pattern.get("candidates", [])
            if isinstance(item, Mapping) and str(item.get("candidate_id")) in {
                need_id.rsplit(":", 1)[-1] for need_id in [contribution.need_id for contribution in own if contribution.lens == "pattern_remedy"]
            }
        )
    )
    payload = {
        "candidate_id": candidate_id,
        "element": element,
        "stem_carriers": list(stem_carriers),
        "supporting_lenses": list(support_lenses),
        "contradicting_lenses": list(contradict_lenses),
        "score_by_lens": {lens: _score(profile, score) for lens, score in sorted(weighted_by_lens.items())},
        "combined_score": _score(profile, combined),
        "balance_score": _score(profile, weighted_by_lens["strength_balance"]),
        "climate_score": _score(profile, weighted_by_lens["seasonal_climate"]),
        "passage_score": _score(profile, weighted_by_lens["element_passage"]),
        "remedy_score": _score(profile, weighted_by_lens["pattern_remedy"]),
        "availability_score": _score(profile, availability_score),
        "contradiction_score": _score(profile, contradiction_score),
        "consensus_bonus": _score(profile, consensus_bonus),
        "unresolved_penalty": _score(profile, unresolved_penalty),
        "availability": availability.to_dict(),
        "visible_positions": list(availability.visible_positions),
        "hidden_positions": list(availability.hidden_positions),
        "root_positions": list(availability.root_positions),
        "strength_context": {
            "classification": strength.get("classification"),
            "day_master_element": strength.get("day_master_element"),
            "element_score": strength.get("element_scores", {}).get(element) if isinstance(strength.get("element_scores"), Mapping) else None,
            "relationship_to_day_master": _relationship_to_day_master(str(strength["day_master_element"]), element),
        },
        "pattern_context": {
            "pattern_result_hash": pattern_hash,
            "pattern_types_considered": list(pattern_types),
            "pattern_unresolved_candidates": list(pattern.get("unresolved_candidates", [])),
        },
        "status": status,
        "confidence_input": {
            "supporting_lens_count": len(support_lenses),
            "contradicting_lens_count": len(contradict_lenses),
            "availability_status": availability.status,
            "excess_risk": availability.candidate_excess_risk,
            "confidence_ceiling": _lens_profile(profile, "fusion").confidence_ceiling,
        },
        "source_node_ids": list(source_node_ids),
        "source_result_hashes": list(source_result_hashes),
        "profile_id": profile.profile_id,
        "source_ids": list(profile.source_ids),
    }
    return YongShenCandidate(
        candidate_id=candidate_id,
        element=element,
        stem_carriers=stem_carriers,
        supporting_lenses=support_lenses,
        contradicting_lenses=contradict_lenses,
        score_by_lens=payload["score_by_lens"],  # type: ignore[arg-type]
        combined_score=payload["combined_score"],  # type: ignore[arg-type]
        balance_score=payload["balance_score"],  # type: ignore[arg-type]
        climate_score=payload["climate_score"],  # type: ignore[arg-type]
        passage_score=payload["passage_score"],  # type: ignore[arg-type]
        remedy_score=payload["remedy_score"],  # type: ignore[arg-type]
        availability_score=payload["availability_score"],  # type: ignore[arg-type]
        contradiction_score=payload["contradiction_score"],  # type: ignore[arg-type]
        consensus_bonus=payload["consensus_bonus"],  # type: ignore[arg-type]
        unresolved_penalty=payload["unresolved_penalty"],  # type: ignore[arg-type]
        availability=availability,
        visible_positions=availability.visible_positions,
        hidden_positions=availability.hidden_positions,
        root_positions=availability.root_positions,
        strength_context=payload["strength_context"],  # type: ignore[arg-type]
        pattern_context=payload["pattern_context"],  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        confidence_input=payload["confidence_input"],  # type: ignore[arg-type]
        source_node_ids=source_node_ids,
        source_result_hashes=source_result_hashes,
        profile_id=profile.profile_id,
        source_ids=profile.source_ids,
        canonical_digest=record_digest("YongShenCandidate", payload),
    )


def _evidence_from_contribution(contribution: CandidateContribution, profile: RegulationProfile) -> RegulationEvidenceRecord:
    evidence_type = {
        "strength_balance": "strength_balance_evidence",
        "seasonal_climate": "seasonal_climate_evidence" if contribution.direction == "support" else "excess_risk_evidence",
        "element_passage": "element_passage_evidence",
        "pattern_remedy": "pattern_rescue_evidence" if contribution.direction == "support" else "unresolved_evidence",
    }[contribution.lens]
    payload = {
        "evidence_id": f"evidence:{contribution.contribution_id}",
        "candidate_id": contribution.candidate_id,
        "element": contribution.element,
        "stem_carrier": contribution.stem_carrier,
        "lens": contribution.lens,
        "evidence_type": evidence_type,
        "direction": "contradict" if contribution.direction in {"contradict", "unresolved"} else "support",
        "contribution": contribution.score,
        "priority": contribution.priority,
        "source_node_ids": list(contribution.source_node_ids),
        "source_result_hashes": list(contribution.source_result_hashes),
        "profile_id": contribution.profile_id,
        "source_ids": list(contribution.source_ids),
    }
    return RegulationEvidenceRecord(canonical_digest=record_digest("RegulationEvidenceRecord", payload), **payload)  # type: ignore[arg-type]


def _evidence_for_candidate(candidate: YongShenCandidate, evidence_type: str, direction: str, contribution: str, priority: int, profile: RegulationProfile) -> RegulationEvidenceRecord:
    payload = {
        "evidence_id": f"evidence:{candidate.candidate_id}:{evidence_type}",
        "candidate_id": candidate.candidate_id,
        "element": candidate.element,
        "stem_carrier": None,
        "lens": "fusion",
        "evidence_type": evidence_type,
        "direction": direction,
        "contribution": contribution,
        "priority": priority,
        "source_node_ids": list(candidate.source_node_ids),
        "source_result_hashes": list(candidate.source_result_hashes),
        "profile_id": profile.profile_id,
        "source_ids": list(profile.source_ids),
    }
    return RegulationEvidenceRecord(canonical_digest=record_digest("RegulationEvidenceRecord", payload), **payload)  # type: ignore[arg-type]


def _candidate_resolutions(candidates: Sequence[YongShenCandidate]) -> tuple[CandidateResolution, ...]:
    ranked = sorted(candidates, key=lambda item: (candidate_rank(item), item.candidate_id), reverse=True)
    records: list[CandidateResolution] = []
    for rank, candidate in enumerate(ranked, 1):
        payload = {
            "candidate_id": candidate.candidate_id,
            "status": candidate.status,
            "resolution_rule": "profile_weighted_four_lens_fusion",
            "score_rank": rank,
        }
        records.append(CandidateResolution(canonical_digest=record_digest("CandidateResolution", payload), **payload))
    return tuple(sorted(records, key=lambda item: item.candidate_id))


def evaluate_bazi_regulation(
    fact_graph: Mapping[str, object],
    strength_result: Mapping[str, object],
    pattern_result: Mapping[str, object],
    *,
    profile_id: str = DEFAULT_PHASE11_PROFILE_ID,
    requested_outputs: Sequence[str] = (),
) -> BaziRegulationEvaluationResult:
    profile, nodes, pillars, graph_hash, strength_hash, pattern_hash = _validate_inputs(
        fact_graph, strength_result, pattern_result, profile_id, requested_outputs
    )
    day_master_element = str(strength_result["day_master_element"])
    strength_needs = _strength_balance_needs(strength_result, graph_hash, strength_hash, profile)
    climate_needs = (_seasonal_climate_need(pillars, graph_hash, strength_hash, profile),)
    passage_needs = _element_passage_needs(strength_result, graph_hash, strength_hash, profile)
    remedy_needs = _pattern_remedy_needs(pattern_result, pattern_hash, profile, day_master_element)
    contributions = _build_contributions(strength_needs, climate_needs, passage_needs, remedy_needs, profile)
    candidates = tuple(
        sorted(
            (_candidate(element, contributions, strength_result, pattern_result, graph_hash, strength_hash, pattern_hash, profile) for element in ELEMENTS),
            key=lambda item: item.candidate_id,
        )
    )
    evidence = [_evidence_from_contribution(item, profile) for item in contributions]
    for candidate in candidates:
        evidence.append(_evidence_for_candidate(candidate, "availability_evidence", "support", candidate.availability_score, 50, profile))
        if Decimal(candidate.availability.candidate_excess_risk) > 0:
            evidence.append(_evidence_for_candidate(candidate, "excess_risk_evidence", "contradict", candidate.availability.candidate_excess_risk, 55, profile))
        if len(candidate.supporting_lenses) >= 2:
            evidence.append(_evidence_for_candidate(candidate, "candidate_consensus_evidence", "support", candidate.consensus_bonus, 95, profile))
        if candidate.status in {"unresolved", "conflicted", "contradicted"}:
            evidence.append(_evidence_for_candidate(candidate, "candidate_conflict_evidence", "contradict", candidate.contradiction_score, 96, profile))
        if "pattern_remedy" in candidate.supporting_lenses:
            evidence.append(_evidence_for_candidate(candidate, "pattern_breaking_evidence", "contradict", "0", 91, profile))
    evidence.sort(key=lambda item: item.evidence_id)
    evidence_ids_by_candidate: dict[str, list[str]] = {}
    for item in evidence:
        evidence_ids_by_candidate.setdefault(item.candidate_id, []).append(item.evidence_id)
    conflicts = build_candidate_conflicts(candidates, evidence_ids_by_candidate, profile_id=profile.profile_id)
    for conflict in conflicts:
        for candidate_id in conflict.candidate_ids:
            candidate = next(item for item in candidates if item.candidate_id == candidate_id)
            evidence.append(_evidence_for_candidate(candidate, "candidate_conflict_evidence", "contradict", "0", 100, profile))
    evidence = tuple(sorted({item.evidence_id: item for item in evidence}.values(), key=lambda item: item.evidence_id))
    primary = primary_candidate_ids(candidates)
    secondary = tuple(sorted(item.candidate_id for item in candidates if item.status in {"conditionally_supported", "secondary"} and item.candidate_id not in primary))
    conflicted = tuple(sorted(item.candidate_id for item in candidates if item.status == "conflicted"))
    contradicted = tuple(sorted(item.candidate_id for item in candidates if item.status == "contradicted"))
    unresolved_candidates = tuple(sorted(item.candidate_id for item in candidates if item.status == "unresolved"))
    unresolved = []
    if any(str(item.get("status")) == "unresolved" for item in pattern_result.get("candidates", []) if isinstance(item, Mapping)):
        unresolved.append({"code": "phase10_pattern_unresolved_retained", "source": "phase10"})
    if any(conflict.resolution_status == "unresolved" for conflict in conflicts):
        unresolved.append({"code": "equal_rank_candidate_conflict", "source": "phase11"})
    regulation_needs = tuple(
        item.to_dict()
        for item in (
            *strength_needs,
            *climate_needs,
            *passage_needs,
            *remedy_needs,
        )
    )
    provenance = {
        "profile_hash": profile.canonical_hash,
        "lens_profile_hashes": {item.profile_id: item.canonical_hash for item in profile.lens_profiles},
        "fact_graph_hash": graph_hash,
        "strength_result_hash": strength_hash,
        "pattern_result_hash": pattern_hash,
        "source_ids": sorted(set(profile.source_ids)),
        "candidate_resolutions": [item.to_dict() for item in _candidate_resolutions(candidates)],
    }
    body = {
        "fact_graph_hash": graph_hash,
        "strength_result_hash": strength_hash,
        "pattern_result_hash": pattern_hash,
        "profile_id": profile.profile_id,
        "regulation_needs": list(regulation_needs),
        "strength_balance_needs": [item.to_dict() for item in strength_needs],
        "seasonal_climate_needs": [item.to_dict() for item in climate_needs],
        "element_passage_needs": [item.to_dict() for item in passage_needs],
        "pattern_remedy_needs": [item.to_dict() for item in remedy_needs],
        "candidates": [item.to_dict() for item in candidates],
        "primary_candidates": list(primary),
        "secondary_candidates": list(secondary),
        "conflicted_candidates": list(conflicted),
        "contradicted_candidates": list(contradicted),
        "unresolved_candidates": list(unresolved_candidates),
        "candidate_conflicts": [item.to_dict() for item in conflicts],
        "evidence_records": [item.to_dict() for item in evidence],
        "provenance_index": provenance,
        "warnings": [
            "structural_regulation_candidate_evaluation_only",
            "prediction_validity_not_evaluated",
            "no_final_favorable_unfavorable_classification",
            "classical_daymaster_month_tiaohou_not_evaluated",
        ],
        "unresolved": unresolved,
    }
    canonical_hash = record_digest("BaziRegulationEvaluationResult", body)
    return BaziRegulationEvaluationResult(
        fact_graph_hash=graph_hash,
        strength_result_hash=strength_hash,
        pattern_result_hash=pattern_hash,
        profile_id=profile.profile_id,
        regulation_needs=regulation_needs,
        strength_balance_needs=strength_needs,
        seasonal_climate_needs=climate_needs,
        element_passage_needs=passage_needs,
        pattern_remedy_needs=remedy_needs,
        candidates=candidates,
        primary_candidates=primary,
        secondary_candidates=secondary,
        conflicted_candidates=conflicted,
        contradicted_candidates=contradicted,
        unresolved_candidates=unresolved_candidates,
        candidate_conflicts=conflicts,
        evidence_records=evidence,
        provenance_index=provenance,
        warnings=tuple(body["warnings"]),
        unresolved=tuple(unresolved),
        canonical_hash=canonical_hash,
    )


def regulation_result_to_phase8_evidence(result: BaziRegulationEvaluationResult | Mapping[str, object]):
    if isinstance(result, BaziRegulationEvaluationResult):
        return tuple(item.to_phase8_evidence() for item in result.evidence_records)
    raw = result.get("evidence_records")
    if not isinstance(raw, list):
        raise Phase11InputError("evidence_records must be an array")
    records: list[RegulationEvidenceRecord] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise Phase11InputError("evidence record must be an object")
        records.append(RegulationEvidenceRecord(
            evidence_id=str(item["evidence_id"]),
            candidate_id=str(item["candidate_id"]),
            element=str(item["element"]),
            stem_carrier=str(item["stem_carrier"]) if item.get("stem_carrier") is not None else None,
            lens=str(item["lens"]),
            evidence_type=str(item["evidence_type"]),
            direction=str(item["direction"]),  # type: ignore[arg-type]
            contribution=str(item["contribution"]),
            priority=int(item["priority"]),
            source_node_ids=tuple(str(value) for value in item["source_node_ids"]),
            source_result_hashes=tuple(str(value) for value in item["source_result_hashes"]),
            profile_id=str(item["profile_id"]),
            source_ids=tuple(str(value) for value in item["source_ids"]),
            canonical_digest=str(item["canonical_digest"]),
        ))
    return tuple(item.to_phase8_evidence() for item in sorted(records, key=lambda value: value.evidence_id))
