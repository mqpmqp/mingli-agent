from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Mapping, Sequence

from .contracts.serialization import digest
from .derived.static_engine import (
    BRANCHES,
    CONTROLS,
    GENERATES,
    STEMS,
    STEM_ELEMENT,
    map_hidden_stems,
)
from .phase8_engine import validate_import_origin
from .phase9_contracts import (
    ELEMENTS,
    PHASE9_DECISION_ID,
    BranchContribution,
    DayMasterStrengthResult,
    ElementContribution,
    Phase9InputError,
    RootContribution,
    SeasonalContribution,
    StemContribution,
    StrengthEvidenceRecord,
    SupportOppositionSummary,
    _record_digest,
)
from .phase9_profiles import (
    DEFAULT_PHASE9_PROFILE_ID,
    classify_ratio,
    element_zero_scores,
    get_strength_profile,
    profile_decimal,
)

POSITIONS = ("year", "month", "day", "hour")
ROOT_LEVEL_BY_ORDINAL = {1: "principal", 2: "middle", 3: "residual"}


def _quantize(profile, value: Decimal, key: str = "score_precision") -> Decimal:
    precision = Decimal(str(profile.quantity.get(key, "0.0001")))
    return value.quantize(precision, rounding=ROUND_HALF_UP)


def _score_string(profile, value: Decimal) -> str:
    return format(_quantize(profile, value), "f")


def _ratio_string(profile, value: Decimal) -> str:
    return format(_quantize(profile, value, "ratio_precision"), "f")


def relationship_to_day_master(day_master_element: str, target_element: str) -> tuple[str, str]:
    if target_element == day_master_element:
        return "peer", "support"
    if GENERATES[target_element] == day_master_element:
        return "resource", "support"
    if GENERATES[day_master_element] == target_element:
        return "output", "oppose"
    if CONTROLS[day_master_element] == target_element:
        return "wealth", "oppose"
    if CONTROLS[target_element] == day_master_element:
        return "authority", "oppose"
    raise Phase9InputError(f"cannot classify element relationship: {day_master_element}->{target_element}")


def _nodes_by_id(fact_graph: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw_nodes = fact_graph.get("nodes")
    if not isinstance(raw_nodes, list):
        raise Phase9InputError("fact_graph.nodes must be an array")
    nodes: dict[str, Mapping[str, object]] = {}
    for item in raw_nodes:
        if not isinstance(item, Mapping):
            raise Phase9InputError("fact_graph.nodes entries must be objects")
        node_id = item.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            raise Phase9InputError("fact_graph node is missing node_id")
        nodes[node_id] = item
    return nodes


def _contains_edges(fact_graph: Mapping[str, object]) -> dict[str, tuple[str, ...]]:
    raw_edges = fact_graph.get("edges")
    if not isinstance(raw_edges, list):
        raise Phase9InputError("fact_graph.edges must be an array")
    contains: dict[str, list[str]] = {}
    for item in raw_edges:
        if not isinstance(item, Mapping):
            raise Phase9InputError("fact_graph.edges entries must be objects")
        if item.get("edge_type") != "contains":
            continue
        source = item.get("source")
        target = item.get("target")
        if isinstance(source, str) and isinstance(target, str):
            contains.setdefault(source, []).append(target)
    return {key: tuple(sorted(value)) for key, value in contains.items()}


def _pillar_nodes(nodes: Mapping[str, Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    pillars: dict[str, Mapping[str, object]] = {}
    for node in nodes.values():
        if node.get("node_type") == "Pillar":
            position = node.get("position")
            if isinstance(position, str):
                pillars[position] = node
    missing = [position for position in POSITIONS if position not in pillars]
    if missing:
        raise Phase9InputError(f"Fact Graph missing four pillars: {', '.join(missing)}")
    return pillars


def _node_string(node: Mapping[str, object], field_name: str) -> str:
    value = node.get(field_name)
    if not isinstance(value, str) or not value:
        raise Phase9InputError(f"node missing {field_name}")
    return value


def _hidden_nodes_for_branch(
    *,
    nodes: Mapping[str, Mapping[str, object]],
    contains: Mapping[str, tuple[str, ...]],
    position: str,
    branch: str,
) -> tuple[Mapping[str, object], ...]:
    branch_id = f"branch:{position}:{branch}"
    child_ids = contains.get(branch_id, ())
    hidden_nodes = [nodes[item] for item in child_ids if item in nodes and nodes[item].get("node_type") == "HiddenStem"]
    hidden_nodes.sort(key=lambda item: int(item.get("ordinal", 0)))
    expected = map_hidden_stems(branch)
    if len(hidden_nodes) != len(expected):
        raise Phase9InputError(f"hidden-stem structure incomplete for {position} branch")
    for node, expected_record in zip(hidden_nodes, expected, strict=True):
        if node.get("stem") != expected_record.stem or node.get("ordinal") != expected_record.ordinal:
            raise Phase9InputError(f"hidden-stem structure does not match reviewed static mapping for {position}")
    return tuple(hidden_nodes)


def _make_element_contribution(
    contribution_type: str,
    contribution_id: str,
    element: str,
    relationship: str,
    direction: str,
    score: str,
    source_node_ids: Sequence[str],
    profile_id: str,
    source_ids: Sequence[str],
) -> ElementContribution:
    payload = {
        "contribution_id": contribution_id,
        "contribution_type": contribution_type,
        "element": element,
        "relationship_to_day_master": relationship,
        "direction": direction,
        "score": score,
        "source_node_ids": list(source_node_ids),
        "profile_id": profile_id,
        "source_ids": list(source_ids),
    }
    return ElementContribution(canonical_digest=_record_digest("ElementContribution", payload), **payload)  # type: ignore[arg-type]


def _evidence(
    evidence_id: str,
    source_type: str,
    source_node_ids: Sequence[str],
    direction: str,
    contribution: str,
    profile_id: str,
    source_ids: Sequence[str],
) -> StrengthEvidenceRecord:
    payload = {
        "evidence_id": evidence_id,
        "claim_id": "day-master-strength",
        "source_type": source_type,
        "source_node_ids": list(source_node_ids),
        "direction": "support" if direction == "support" else "contradict",
        "contribution": contribution,
        "profile_id": profile_id,
        "source_ids": list(source_ids),
    }
    return StrengthEvidenceRecord(canonical_digest=_record_digest("StrengthEvidenceRecord", payload), **payload)  # type: ignore[arg-type]


def _check_graph_contract(fact_graph: Mapping[str, object], profile_id: str) -> None:
    if not isinstance(fact_graph.get("nodes"), list):
        raise Phase9InputError("Fact Graph missing nodes")
    if not isinstance(fact_graph.get("edges"), list):
        raise Phase9InputError("Fact Graph missing edges")
    if fact_graph.get("prediction_validity") != "not_evaluated":
        raise Phase9InputError("input prediction_validity must be not_evaluated")
    if profile_id != DEFAULT_PHASE9_PROFILE_ID:
        raise Phase9InputError(f"unsupported strength profile requested: {profile_id}")


def calculate_day_master_strength(
    fact_graph: Mapping[str, object],
    *,
    profile_id: str = DEFAULT_PHASE9_PROFILE_ID,
) -> DayMasterStrengthResult:
    if not isinstance(fact_graph, Mapping):
        raise TypeError("fact_graph must be a JSON object")
    _check_graph_contract(fact_graph, profile_id)
    profile = get_strength_profile(profile_id)
    if not profile.reviewed:
        raise Phase9InputError("profile must be reviewed")
    if profile.toggles.get("combination_transformation_affect_score") is True:
        raise Phase9InputError("combination transformation scoring is not supported in Phase 9 V1")
    if profile.toggles.get("climate_adjustment_affect_score") is True:
        raise Phase9InputError("climate adjustment scoring is not supported in Phase 9 V1")
    if profile.toggles.get("follower_pattern_final_judgement") is True:
        raise Phase9InputError("follower-pattern final judgement is not supported in Phase 9 V1")

    nodes = _nodes_by_id(fact_graph)
    contains = _contains_edges(fact_graph)
    pillars = _pillar_nodes(nodes)
    day_master = _node_string(pillars["day"], "stem")
    if day_master not in STEM_ELEMENT:
        raise Phase9InputError("day master stem is unsupported")
    day_master_element = STEM_ELEMENT[day_master]
    element_scores = element_zero_scores()
    contribution_records: list[Mapping[str, object]] = []
    seasonal_records: list[Mapping[str, object]] = []
    visible_stems: list[Mapping[str, object]] = []
    hidden_stems: list[Mapping[str, object]] = []
    roots: list[Mapping[str, object]] = []
    evidence_records: list[StrengthEvidenceRecord] = []

    source_ids = profile.source_ids

    def add_score(element: str, direction: str, score: Decimal, source_type: str, source_node_ids: Sequence[str]) -> None:
        element_scores[element] += score
        if score == 0:
            return
        evidence_records.append(
            _evidence(
                f"phase9-evidence:{source_type}:{len(evidence_records) + 1}",
                source_type,
                source_node_ids,
                direction,
                _score_string(profile, score),
                profile.profile_id,
                source_ids,
            )
        )

    month_branch = _node_string(pillars["month"], "branch")
    month_hidden = _hidden_nodes_for_branch(nodes=nodes, contains=contains, position="month", branch=month_branch)
    month_branch_node_id = f"branch:month:{month_branch}"
    for hidden in month_hidden:
        ordinal = int(hidden["ordinal"])
        stem = _node_string(hidden, "stem")
        element = STEM_ELEMENT[stem]
        relationship, direction = relationship_to_day_master(day_master_element, element)
        score = profile_decimal(profile, "weights.month_branch_weight") * profile_decimal(profile, f"weights.seasonal_hidden_stem_weights.{ordinal}")
        source_node_ids = (month_branch_node_id, str(hidden["node_id"]))
        payload = {
            "contribution_id": f"seasonal:month:{ordinal}:{stem}",
            "month_branch": month_branch,
            "hidden_stem": stem,
            "hidden_stem_ordinal": ordinal,
            "element": element,
            "relationship_to_day_master": relationship,
            "direction": direction,
            "score": _score_string(profile, score),
            "source_node_ids": source_node_ids,
            "profile_id": profile.profile_id,
            "source_ids": source_ids,
        }
        record = SeasonalContribution(canonical_digest=_record_digest("SeasonalContribution", payload), **payload)  # type: ignore[arg-type]
        seasonal_records.append(record.to_dict())
        contribution_records.append(
            _make_element_contribution(
                "seasonal",
                str(payload["contribution_id"]),
                element,
                relationship,
                direction,
                str(payload["score"]),
                source_node_ids,
                profile.profile_id,
                source_ids,
            ).to_dict()
        )
        add_score(element, direction, score, "month_order_support" if direction == "support" else "month_order_opposition", source_node_ids)

    for position in POSITIONS:
        stem = _node_string(pillars[position], "stem")
        stem_node_id = f"stem:{position}:{stem}"
        element = STEM_ELEMENT[stem]
        relationship, direction = relationship_to_day_master(day_master_element, element)
        score = profile_decimal(profile, f"weights.visible_stem_weights.{position}")
        stem_payload = {
            "contribution_id": f"visible-stem:{position}:{stem}",
            "position": position,
            "stem": stem,
            "element": element,
            "relationship_to_day_master": relationship,
            "direction": direction,
            "score": _score_string(profile, score),
            "source_node_ids": (stem_node_id,),
            "profile_id": profile.profile_id,
            "source_ids": source_ids,
        }
        stem_record = StemContribution(canonical_digest=_record_digest("StemContribution", stem_payload), **stem_payload)  # type: ignore[arg-type]
        visible_stems.append(stem_record.to_dict())
        contribution_records.append(
            _make_element_contribution(
                "visible_stem",
                str(stem_payload["contribution_id"]),
                element,
                relationship,
                direction,
                str(stem_payload["score"]),
                (stem_node_id,),
                profile.profile_id,
                source_ids,
            ).to_dict()
        )
        add_score(element, direction, score, "visible_stem_support" if direction == "support" else "visible_stem_opposition", (stem_node_id,))

        branch = _node_string(pillars[position], "branch")
        branch_node_id = f"branch:{position}:{branch}"
        hidden_nodes = _hidden_nodes_for_branch(nodes=nodes, contains=contains, position=position, branch=branch)
        for hidden in hidden_nodes:
            ordinal = int(hidden["ordinal"])
            hidden_stem = _node_string(hidden, "stem")
            hidden_element = STEM_ELEMENT[hidden_stem]
            relationship, direction = relationship_to_day_master(day_master_element, hidden_element)
            score = (
                profile_decimal(profile, f"weights.branch_position_weights.{position}")
                * profile_decimal(profile, f"weights.hidden_stem_ordinal_weights.{ordinal}")
            )
            source_node_ids = (branch_node_id, str(hidden["node_id"]))
            branch_payload = {
                "contribution_id": f"hidden-stem:{position}:{ordinal}:{hidden_stem}",
                "position": position,
                "branch": branch,
                "hidden_stem": hidden_stem,
                "hidden_stem_ordinal": ordinal,
                "element": hidden_element,
                "relationship_to_day_master": relationship,
                "direction": direction,
                "score": _score_string(profile, score),
                "source_node_ids": source_node_ids,
                "profile_id": profile.profile_id,
                "source_ids": source_ids,
            }
            branch_record = BranchContribution(canonical_digest=_record_digest("BranchContribution", branch_payload), **branch_payload)  # type: ignore[arg-type]
            hidden_stems.append(branch_record.to_dict())
            contribution_records.append(
                _make_element_contribution(
                    "hidden_stem",
                    str(branch_payload["contribution_id"]),
                    hidden_element,
                    relationship,
                    direction,
                    str(branch_payload["score"]),
                    source_node_ids,
                    profile.profile_id,
                    source_ids,
                ).to_dict()
            )
            add_score(hidden_element, direction, score, "hidden_stem_support" if direction == "support" else "hidden_stem_opposition", source_node_ids)
            if hidden_element == day_master_element:
                level = ROOT_LEVEL_BY_ORDINAL[ordinal]
                root_score = profile_decimal(profile, f"weights.root_level_weights.{level}")
                root_payload = {
                    "contribution_id": f"root:{position}:{ordinal}:{hidden_stem}",
                    "branch_position": position,
                    "branch": branch,
                    "hidden_stem": hidden_stem,
                    "hidden_stem_ordinal": ordinal,
                    "root_level": level,
                    "element": hidden_element,
                    "score": _score_string(profile, root_score),
                    "source_node_ids": source_node_ids,
                    "profile_id": profile.profile_id,
                    "source_ids": source_ids,
                }
                root_record = RootContribution(canonical_digest=_record_digest("RootContribution", root_payload), **root_payload)  # type: ignore[arg-type]
                roots.append(root_record.to_dict())
                contribution_records.append(
                    _make_element_contribution(
                        "root",
                        str(root_payload["contribution_id"]),
                        hidden_element,
                        "peer",
                        "support",
                        str(root_payload["score"]),
                        source_node_ids,
                        profile.profile_id,
                        source_ids,
                    ).to_dict()
                )
                add_score(hidden_element, "support", root_score, "root_support", source_node_ids)

    support_score = Decimal("0")
    opposition_score = Decimal("0")
    for item in contribution_records:
        score = Decimal(str(item["score"]))
        if item["direction"] == "support":
            support_score += score
        elif item["direction"] == "oppose":
            opposition_score += score
    denominator = support_score + opposition_score
    unresolved: list[Mapping[str, object]] = []
    if denominator == 0:
        support_ratio = opposition_ratio = Decimal("0")
        classification = "unresolved"
        classification_band: Mapping[str, object] = {"reason": "zero_total_contribution"}
        unresolved.append({"code": "PHASE9_ZERO_TOTAL_CONTRIBUTION", "message": "no support or opposition contribution could be computed"})
    else:
        support_ratio = support_score / denominator
        opposition_ratio = opposition_score / denominator
        classification, classification_band = classify_ratio(profile, support_ratio)
    net_score = support_score - opposition_score
    summary = SupportOppositionSummary(
        support_score=_score_string(profile, support_score),
        opposition_score=_score_string(profile, opposition_score),
        support_ratio=_ratio_string(profile, support_ratio),
        opposition_ratio=_ratio_string(profile, opposition_ratio),
        net_score=_score_string(profile, net_score),
    )
    classification_evidence = _evidence(
        "phase9-evidence:classification:summary",
        "combined_strength_classification",
        tuple(sorted({node_id for item in contribution_records for node_id in item["source_node_ids"]})),  # type: ignore[index]
        "support" if classification in {"balanced", "strong", "very_strong"} else "oppose",
        _score_string(profile, abs(net_score)),
        profile.profile_id,
        source_ids,
    )
    evidence_records.append(classification_evidence)
    supporting_evidence = tuple(sorted((item.to_dict() for item in evidence_records if item.direction == "support"), key=lambda item: str(item["evidence_id"])))
    contradicting_evidence = tuple(sorted((item.to_dict() for item in evidence_records if item.direction == "contradict"), key=lambda item: str(item["evidence_id"])))
    element_score_strings = {element: _score_string(profile, element_scores[element]) for element in ELEMENTS}
    seasonal_state = {
        "month_branch": month_branch,
        "dominant_hidden_stem": _node_string(month_hidden[0], "stem"),
        "dominant_element": STEM_ELEMENT[_node_string(month_hidden[0], "stem")],
        "contributions": sorted(seasonal_records, key=lambda item: str(item["contribution_id"])),
        "profile_id": profile.profile_id,
    }
    payload = {
        "day_master": day_master,
        "day_master_element": day_master_element,
        "profile_id": profile.profile_id,
        "element_scores": element_score_strings,
        **summary.to_dict(),
        "classification": classification,
        "classification_band": dict(classification_band),
        "seasonal_state": seasonal_state,
        "roots": sorted(roots, key=lambda item: str(item["contribution_id"])),
        "visible_stems": sorted(visible_stems, key=lambda item: str(item["contribution_id"])),
        "hidden_stems": sorted(hidden_stems, key=lambda item: str(item["contribution_id"])),
        "contribution_records": sorted(contribution_records, key=lambda item: str(item["contribution_id"])),
        "supporting_evidence": list(supporting_evidence),
        "contradicting_evidence": list(contradicting_evidence),
        "warnings": [
            "structural_relations_retained_but_do_not_change_score",
            "xunkong_and_twelve_growth_retained_but_do_not_change_score",
            "follower_pattern_candidate_not_evaluated",
        ],
        "unresolved": list(unresolved),
    }
    canonical_hash = _record_digest("DayMasterStrengthResult", payload)
    return DayMasterStrengthResult(
        day_master=day_master,
        day_master_element=day_master_element,
        profile_id=profile.profile_id,
        element_scores=element_score_strings,
        support_score=summary.support_score,
        opposition_score=summary.opposition_score,
        support_ratio=summary.support_ratio,
        opposition_ratio=summary.opposition_ratio,
        net_score=summary.net_score,
        classification=classification,  # type: ignore[arg-type]
        classification_band=dict(classification_band),
        seasonal_state=seasonal_state,
        roots=tuple(payload["roots"]),  # type: ignore[arg-type]
        visible_stems=tuple(payload["visible_stems"]),  # type: ignore[arg-type]
        hidden_stems=tuple(payload["hidden_stems"]),  # type: ignore[arg-type]
        contribution_records=tuple(payload["contribution_records"]),  # type: ignore[arg-type]
        supporting_evidence=supporting_evidence,
        contradicting_evidence=contradicting_evidence,
        warnings=tuple(payload["warnings"]),  # type: ignore[arg-type]
        unresolved=tuple(unresolved),
        canonical_hash=canonical_hash,
    )


def strength_result_to_phase8_evidence(result: DayMasterStrengthResult | Mapping[str, object]):
    payload = result.to_dict() if isinstance(result, DayMasterStrengthResult) else dict(result)
    records: list[StrengthEvidenceRecord] = []
    for key in ("supporting_evidence", "contradicting_evidence"):
        raw_records = payload.get(key, [])
        if not isinstance(raw_records, list):
            raise Phase9InputError(f"{key} must be an array")
        for item in raw_records:
            if not isinstance(item, Mapping):
                raise Phase9InputError(f"{key} entries must be objects")
            records.append(
                StrengthEvidenceRecord(
                    evidence_id=str(item["evidence_id"]),
                    claim_id=str(item["claim_id"]),
                    source_type=str(item["source_type"]),
                    source_node_ids=tuple(str(node_id) for node_id in item["source_node_ids"]),  # type: ignore[index]
                    direction=str(item["direction"]),  # type: ignore[arg-type]
                    contribution=str(item["contribution"]),
                    profile_id=str(item["profile_id"]),
                    source_ids=tuple(str(source_id) for source_id in item["source_ids"]),  # type: ignore[index]
                    canonical_digest=str(item["canonical_digest"]),
                )
            )
    return tuple(record.to_phase8_evidence() for record in sorted(records, key=lambda item: item.evidence_id))


def build_strength_fixture_fact_graph(
    *,
    year: tuple[str, str],
    month: tuple[str, str],
    day: tuple[str, str],
    hour: tuple[str, str],
) -> dict[str, object]:
    pillars = {"year": year, "month": month, "day": day, "hour": hour}
    day_master = day[0]
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    for position, (stem, branch) in pillars.items():
        pillar_id = f"pillar:{position}"
        stem_id = f"stem:{position}:{stem}"
        branch_id = f"branch:{position}:{branch}"
        nodes.extend(
            [
                {"node_id": pillar_id, "node_type": "Pillar", "position": position, "stem": stem, "branch": branch},
                {"node_id": stem_id, "node_type": "Stem", "value": stem, "position": position},
                {"node_id": branch_id, "node_type": "Branch", "value": branch, "position": position},
            ]
        )
        edges.extend(
            [
                {"edge_id": f"contains:{pillar_id}->{stem_id}", "edge_type": "contains", "source": pillar_id, "target": stem_id},
                {"edge_id": f"contains:{pillar_id}->{branch_id}", "edge_type": "contains", "source": pillar_id, "target": branch_id},
            ]
        )
        for hidden in map_hidden_stems(branch, day_master=day_master):
            hidden_id = f"hidden-stem:{position}:{branch}:{hidden.ordinal}:{hidden.stem}"
            nodes.append(
                {
                    "node_id": hidden_id,
                    "node_type": "HiddenStem",
                    "stem": hidden.stem,
                    "ordinal": hidden.ordinal,
                    "ten_god": hidden.ten_god.code if hidden.ten_god else None,
                }
            )
            edges.append({"edge_id": f"contains:{branch_id}->{hidden_id}", "edge_type": "contains", "source": branch_id, "target": hidden_id})
    for node in nodes:
        node["canonical_digest"] = digest({"record_type": "GraphNode", "payload": {key: value for key, value in node.items() if key != "canonical_digest"}})
    for edge in edges:
        edge["canonical_digest"] = digest({"record_type": "GraphEdge", "payload": {key: value for key, value in edge.items() if key != "canonical_digest"}})
    payload = {
        "base_chart_ref": {"fixture": "phase9"},
        "derived_structure_ref": {"fixture": "phase9"},
        "profiles": [],
        "nodes": sorted(nodes, key=lambda item: item["node_id"]),
        "edges": sorted(edges, key=lambda item: item["edge_id"]),
        "timeline": {},
        "relations": [],
        "growth_stages": [],
        "provenance_index": {"decision_id": PHASE9_DECISION_ID},
        "warnings": [],
        "unresolved": [],
        "prediction_validity": "not_evaluated",
    }
    payload["canonical_hash"] = digest(payload)
    return payload


def write_json(path: Path, value: Mapping[str, object]) -> None:
    path.write_text(__import__("json").dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
