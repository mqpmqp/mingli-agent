from __future__ import annotations

import json

import pytest

from mingli.liuyao.advanced_runtime import (
    AdvancedContextRequest,
    build_advanced_runtime_report,
)
from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.interpretation import InterpretationRequest
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.tables import PREDICTION_VALIDITY, digest
from mingli.liuyao.validation import LiuYaoError
from mingli.liuyao.validity_matrix import (
    VALIDITY_ENGINEERING_POLICY,
    VALIDITY_ENGINEERING_POLICY_ID,
    VALIDITY_ENGINEERING_POLICY_SHA256,
    VALIDITY_MATRIX_PRODUCTION_ALLOWED,
    VALIDITY_PRECONDITION_GATES,
    VALIDITY_PRIORITY_BANDS,
    VALIDITY_PRIORITY_TABLE_SHA256,
    VALIDITY_RULE_PROFILE_ID,
    VALIDITY_RULE_PROFILE_SHA256,
    VALIDITY_RULE_CONTRACT,
    ValidityRequest,
    build_validity_matrix,
)


def _record(
    *,
    case_id: str,
    lines: tuple[int, ...],
    month_branch: str | None,
    day_ganzhi: str | None,
):
    return create_case_record(
        LiuYaoCastInput(
            case_id=case_id,
            question="合成验收事件的结构有效性如何",
            line_values=lines,
            event_contract=EventContract(
                target_event="合成验收事件",
                deadline="2099-12-31",
                success_criteria="满足冻结的合成标准",
                evidence_requirement="提供可核验的合成证据",
            ),
            completed_at="2026-09-02T12:00:00+00:00",
            location="合成测试地点",
            month_branch=month_branch,
            day_ganzhi=day_ganzhi,
        )
    )


def _validity_request(
    *,
    relation: str,
    position: int | None,
    confirmed: bool = True,
    reality_status: str = "unknown",
    secondary_relations: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
    calendar_source_refs: tuple[str, ...] = ("source:calendar-receipt",),
) -> ValidityRequest:
    reality_facts = (
        ()
        if reality_status == "unknown"
        else ("已核验的合成现实条件",)
    )
    reality_evidence_refs = (
        ()
        if reality_status == "unknown"
        else ("source:reality-receipt",)
    )
    return ValidityRequest(
        interpretation=InterpretationRequest(
            topic="general",
            use_relation=relation,
            primary_position=position,
            secondary_relations=secondary_relations,
            calendar_context_confirmed=confirmed,
            reality_status=reality_status,
            reality_facts=reality_facts,
            notes=notes,
        ),
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=confirmed,
            calendar_source_refs=calendar_source_refs if confirmed else (),
        ),
        reality_evidence_refs=reality_evidence_refs,
        reality_evidence_confirmed=reality_status != "unknown",
    )


def _vbm_record():
    # 乾为天 -> 风天小畜；original:4 午火官鬼同时发动、旬空、月破。
    return _record(
        case_id="VALIDITY-VBM",
        lines=(7, 7, 7, 9, 7, 7),
        month_branch="子",
        day_ganzhi="甲申",
    )


def _hidden_record(*, flying_constrained: bool):
    # 风雷益 -> 天雷无妄；缺官鬼，伏神酉金在 original:3 辰土之下。
    return _record(
        case_id="VALIDITY-HIDDEN-F" if flying_constrained else "VALIDITY-HIDDEN-H",
        lines=(7, 8, 8, 6, 7, 7),
        month_branch="戌" if flying_constrained else "卯",
        day_ganzhi="甲子" if flying_constrained else "乙亥",
    )


def _cross_record():
    # original:4 午火发动，original:5 申金兄弟为静态用神；三者均无空破墓绝。
    return _record(
        case_id="VALIDITY-CROSS",
        lines=(7, 7, 7, 9, 7, 7),
        month_branch="卯",
        day_ganzhi="丁卯",
    )


def _graph_record():
    # 六爻全动；用于路径长度、循环与枚举边界验收。
    return _record(
        case_id="VALIDITY-GRAPH",
        lines=(9, 9, 9, 9, 9, 9),
        month_branch="卯",
        day_ganzhi="丁卯",
    )


def _static_qian_record():
    return _record(
        case_id="VALIDITY-STATIC-QIAN",
        lines=(7, 7, 7, 7, 7, 7),
        month_branch="申",
        day_ganzhi="戊申",
    )


def _node(report, node_id: str):
    return next(item for item in report.nodes if item.node_id == node_id)


def _edge(report, edge_id: str):
    return next(item for item in report.edges if item.edge_id == edge_id)


def test_validity_request_does_not_mutate_or_extend_frozen_interpretation_request() -> None:
    interpretation = InterpretationRequest(
        topic="general",
        use_relation="兄弟",
        primary_position=5,
        calendar_context_confirmed=True,
    )
    before = interpretation.to_dict()
    before_hash = interpretation.canonical_sha256
    request = ValidityRequest(
        interpretation=interpretation,
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=True,
            calendar_source_refs=("source:calendar-receipt",),
        ),
    )

    build_validity_matrix(_cross_record(), request)

    assert interpretation.to_dict() == before
    assert interpretation.canonical_sha256 == before_hash
    assert set(before) == {
        "topic",
        "focus_dimension",
        "use_relation",
        "primary_position",
        "secondary_relations",
        "calendar_context_confirmed",
        "reality_status",
        "reality_facts",
        "notes",
        "canonical_sha256",
    }
    assert "calendar_source_refs" not in before
    assert "rule_profile_id" not in before


@pytest.mark.parametrize(
    ("scope", "field", "value"),
    [
        ("validity", "priority_override", {"reality_gate": 0}),
        ("validity", "production_allowed", True),
        ("interpretation", "calendar_source_refs", ["source:injected"]),
        ("interpretation", "max_path_hops", 99),
        ("advanced_context", "prediction_validity", "validated"),
    ],
)
def test_validity_request_rejects_unknown_override_fields(
    scope: str,
    field: str,
    value: object,
) -> None:
    payload = _validity_request(relation="兄弟", position=5).to_dict()
    if scope == "validity":
        payload[field] = value
    else:
        nested = payload[scope]
        assert isinstance(nested, dict)
        nested[field] = value

    with pytest.raises(LiuYaoError) as raised:
        ValidityRequest.from_mapping(payload)

    assert raised.value.code == "INVALID_INPUT"


@pytest.mark.parametrize("nested", ["interpretation", "advanced_context", None])
def test_validity_request_rejects_nested_and_outer_hash_tampering(
    nested: str | None,
) -> None:
    payload = _validity_request(relation="兄弟", position=5).to_dict()
    if nested == "interpretation":
        payload["interpretation"]["primary_position"] = 4  # type: ignore[index]
    elif nested == "advanced_context":
        payload["advanced_context"]["calendar_source_refs"] = ["source:changed"]  # type: ignore[index]
    else:
        payload["canonical_sha256"] = "0" * 64

    with pytest.raises(LiuYaoError) as raised:
        ValidityRequest.from_mapping(payload)

    assert raised.value.code == "RECORD_TAMPERED"


def test_legacy_secondary_relations_and_notes_do_not_activate_paths() -> None:
    record = _cross_record()
    baseline = build_validity_matrix(
        record,
        _validity_request(relation="兄弟", position=5),
    )
    decorated = build_validity_matrix(
        record,
        _validity_request(
            relation="兄弟",
            position=5,
            secondary_relations=("父母", "官鬼"),
            notes=("旧字段只用于审计，不是路径指令",),
        ),
    )

    assert [item.to_dict() for item in decorated.edges] == [
        item.to_dict() for item in baseline.edges
    ]
    assert [item.to_dict() for item in decorated.paths] == [
        item.to_dict() for item in baseline.paths
    ]
    assert decorated.request.canonical_sha256 != baseline.request.canonical_sha256


def test_confirmed_and_unique_candidate_use_states_both_pass_selection_gate() -> None:
    explicit = build_validity_matrix(
        _cross_record(),
        _validity_request(relation="兄弟", position=5),
    )
    unique = build_validity_matrix(
        _vbm_record(),
        _validity_request(relation="官鬼", position=None),
    )

    assert explicit.focus_selection.status == "confirmed"
    assert explicit.focus_selection.selected_position == 5
    assert explicit.focus_status != "needs_confirmation"
    assert unique.focus_selection.status == "unique_candidate"
    assert unique.focus_selection.selected_position == 4
    assert unique.focus_status != "needs_confirmation"


def test_ambiguous_and_not_found_use_states_fail_closed_without_hidden_promotion() -> None:
    ambiguous = build_validity_matrix(
        _static_qian_record(),
        _validity_request(relation="父母", position=None),
    )
    hidden = build_validity_matrix(
        _hidden_record(flying_constrained=False),
        _validity_request(relation="官鬼", position=None),
    )

    assert ambiguous.focus_selection.status == "ambiguous"
    assert ambiguous.focus_selection.candidate_positions == (3, 6)
    assert ambiguous.focus_status == "needs_confirmation"
    assert ambiguous.paths == ()
    assert hidden.focus_selection.status == "not_found"
    assert hidden.focus_selection.selected_position is None
    assert hidden.focus_status == "needs_confirmation"
    assert hidden.hidden_candidates[0].visibility_state == "hidden_candidate"
    assert hidden.paths == ()


def test_moving_void_month_broken_use_remains_one_unresolved_subject() -> None:
    report = build_validity_matrix(
        _vbm_record(),
        _validity_request(relation="官鬼", position=None),
    )
    original = _node(report, "original:4")
    changed = _node(report, "changed:4")
    conflicts = {item.code: item for item in report.conflicts}

    assert original.motion_kind == "moving"
    assert original.state == "unresolved"
    assert (
        original.structural_eligibility,
        original.current_force,
        original.manifestation_state,
        original.role_polarity,
    ) == ("retained_candidate", "unresolved", "unresolved", "selected_use")
    assert {
        "MONTH_BREAK_OPEN",
        "VOID_EFFECT_OPEN",
        "RULE_EFFECT_CONFLICT",
    }.issubset(original.open_obligations)
    assert changed.open_obligations == ("VOID_EFFECT_OPEN",)
    assert (
        changed.structural_eligibility,
        changed.current_force,
        changed.manifestation_state,
        changed.role_polarity,
    ) == ("retained_candidate", "constrained", "deferred", "unassigned")
    assert "MONTH_BREAK_OPEN" not in changed.open_obligations
    assert conflicts["VOID_AND_MONTH_BREAK"].subjects == ("original:4",)
    assert conflicts["VOID_AND_MONTH_BREAK"].resolution == "unresolved"
    assert conflicts["AUTHOR_INTERNAL_CONFLICT"].subjects == ("original:4",)
    assert report.focus_status == "unresolved"
    assert not any(
        path.validity_status == "active_candidate" for path in report.paths
    )
    affected_paths = tuple(
        path for path in report.paths if path.target_node_id == original.node_id
    )
    assert affected_paths
    assert all(
        path.candidate_graph_reaches_focus is False
        and path.validity_status == "deferred"
        and path.enumeration_status == "retained"
        and path.enumeration_reason is None
        for path in affected_paths
    )


@pytest.mark.parametrize(
    (
        "case_suffix",
        "month_branch",
        "day_ganzhi",
        "stage_field",
        "stage",
        "obligation",
    ),
    [
        ("MU", "未", "戊辰", "month_growth_stage", "墓", "MONTH_TOMB_EFFECT_OPEN"),
        ("JUE", "辰", "甲申", "day_growth_stage", "绝", "DAY_ABSOLUTE_EFFECT_OPEN"),
    ],
)
def test_tomb_and_absolute_are_unresolved_labels_not_hard_invalidity(
    case_suffix: str,
    month_branch: str,
    day_ganzhi: str,
    stage_field: str,
    stage: str,
    obligation: str,
) -> None:
    record = _record(
        case_id=f"VALIDITY-GROWTH-{case_suffix}",
        lines=(7, 8, 8, 6, 7, 7),
        month_branch=month_branch,
        day_ganzhi=day_ganzhi,
    )
    report = build_validity_matrix(
        record,
        _validity_request(relation="兄弟", position=6),
    )
    use = _node(report, "original:6")

    assert getattr(use, stage_field) == stage
    assert use.open_obligations == (obligation,)
    assert use.state == "unresolved"
    assert use.structural_eligibility == "retained_candidate"
    assert use.current_force == "unresolved"
    assert use.manifestation_state == "deferred"
    assert use.role_polarity == "selected_use"
    assert report.focus_status == "unresolved"
    assert "invalid" not in json.dumps(use.to_dict(), ensure_ascii=False).lower()
    affected_paths = tuple(
        path for path in report.paths if path.target_node_id == use.node_id
    )
    assert affected_paths
    assert all(
        path.candidate_graph_reaches_focus is False
        and path.validity_status == "deferred"
        and path.enumeration_status == "retained"
        and path.enumeration_reason is None
        for path in affected_paths
    )


def test_hidden_constraints_do_not_leak_to_flying_subject() -> None:
    report = build_validity_matrix(
        _hidden_record(flying_constrained=False),
        _validity_request(relation="官鬼", position=None),
    )
    hidden = report.hidden_candidates[0]
    flying = _node(report, "original:3")

    assert hidden.hidden_node.node_id == "hidden:官鬼:3"
    assert hidden.hidden_node.branch == "酉"
    assert set(hidden.hidden_node.open_obligations) == {
        "MONTH_BREAK_OPEN",
        "VOID_EFFECT_OPEN",
    }
    assert flying.node_id == "original:3"
    assert flying.branch == "辰"
    assert flying.state == "available_candidate"
    assert flying.open_obligations == ()
    assert hidden.flying_node_id == flying.node_id
    assert hidden.flying_to_hidden == "generates"
    assert hidden.hidden_to_flying == "generated_by"


def test_flying_constraints_do_not_leak_to_hidden_subject() -> None:
    report = build_validity_matrix(
        _hidden_record(flying_constrained=True),
        _validity_request(relation="妻财", position=3),
    )
    hidden = report.hidden_candidates[0]
    flying = _node(report, "original:3")

    assert hidden.hidden_node.state == "available_candidate"
    assert hidden.hidden_node.open_obligations == ()
    assert flying.state == "conditional"
    assert flying.open_obligations == ("MONTH_BREAK_OPEN",)
    assert "FLYING_MONTH_BREAK_OPEN" in hidden.release_candidates
    assert "HIDDEN_SELF_VALIDITY_OPEN" not in hidden.open_obligations


def test_changed_line_is_same_position_only_and_cross_position_is_audited() -> None:
    report = build_validity_matrix(
        _cross_record(),
        _validity_request(relation="兄弟", position=5),
    )
    same_position = _edge(report, "changed:4:self")
    cross_position = _edge(report, "changed:4:cross-to-use:5")

    assert same_position.source_node_id == "changed:4"
    assert same_position.target_node_id == "original:4"
    assert same_position.status == "active_candidate"
    assert cross_position.source_node_id == "changed:4"
    assert cross_position.target_node_id == "original:5"
    assert cross_position.status == "pruned"
    assert cross_position.prune_reason == "CHANGED_CROSS_POSITION_EXCLUDED"
    source_scope, engineering_enforcement = cross_position.rule_hits
    assert source_scope.effect == "defer"
    assert source_scope.outcome == "source_scope_exclusion"
    assert source_scope.policy_id == VALIDITY_RULE_PROFILE_ID
    assert engineering_enforcement.effect == "exclude"
    assert engineering_enforcement.outcome == "engineering_profile_exclusion"
    assert engineering_enforcement.policy_id == VALIDITY_ENGINEERING_POLICY_ID
    assert engineering_enforcement.source_refs == ()
    assert all(
        edge.status == "pruned"
        for edge in report.edges
        if edge.source_node_id.startswith("changed:")
        and edge.source_node_id.split(":")[1]
        != edge.target_node_id.split(":")[1]
    )


def test_moving_original_can_act_on_static_use_and_return_path_has_two_edges() -> None:
    report = build_validity_matrix(
        _cross_record(),
        _validity_request(relation="兄弟", position=5),
    )
    direct = _edge(report, "moving:4:to-use:5")
    target = _node(report, "original:5")

    assert target.motion_kind == "static"
    assert direct.source_node_id == "original:4"
    assert direct.target_node_id == target.node_id
    assert direct.status == "active_candidate"
    assert any(
        path.edge_ids == ("moving:4:to-use:5",)
        and path.validity_status == "active_candidate"
        and path.enumeration_status == "retained"
        and path.candidate_graph_reaches_focus
        for path in report.paths
    )
    assert any(
        path.edge_ids == ("changed:4:self", "moving:4:to-use:5")
        and path.validity_status == "active_candidate"
        and path.enumeration_status == "retained"
        and path.candidate_graph_reaches_focus
        for path in report.paths
    )


def test_multi_moving_paths_are_limited_to_two_edges_and_long_paths_are_audited() -> None:
    report = build_validity_matrix(
        _graph_record(),
        _validity_request(relation="官鬼", position=4),
    )
    retained = tuple(
        path for path in report.paths if path.enumeration_status == "retained"
    )
    length_excluded = tuple(
        path
        for path in report.paths
        if path.enumeration_reason == "PATH_LENGTH_LIMIT"
    )
    conflict_codes = {item.code for item in report.conflicts}

    assert any(len(path.edge_ids) == 2 for path in retained)
    assert all(len(path.edge_ids) <= 2 for path in retained)
    assert length_excluded
    assert all(
        len(path.edge_ids) == 2
        and path.enumeration_status == "profile_excluded"
        for path in length_excluded
    )
    assert "PATH_LENGTH_LIMIT" in conflict_codes
    assert "PATH_ENUMERATION_LIMIT" not in conflict_codes


def test_multi_moving_cycles_are_pruned_and_preserved_for_audit() -> None:
    report = build_validity_matrix(
        _graph_record(),
        _validity_request(relation="官鬼", position=4),
    )
    cycles = tuple(
        path
        for path in report.paths
        if path.enumeration_reason == "PATH_CYCLE_PRUNED"
    )

    assert cycles
    assert all(path.enumeration_status == "profile_excluded" for path in cycles)
    assert any(item.code == "PATH_CYCLE_PRUNED" for item in report.conflicts)
    assert not any(
        path.enumeration_status == "retained" and path.enumeration_reason is not None
        for path in report.paths
    )


def test_priority_reality_then_provenance_then_use_then_node_then_path() -> None:
    ambiguous_record = _static_qian_record()
    reality_first = build_validity_matrix(
        ambiguous_record,
        _validity_request(
            relation="父母",
            position=None,
            confirmed=False,
            reality_status="blocking",
        ),
    )
    provenance_before_use = build_validity_matrix(
        ambiguous_record,
        _validity_request(relation="父母", position=None, confirmed=False),
    )
    use_before_paths = build_validity_matrix(
        ambiguous_record,
        _validity_request(relation="父母", position=None),
    )
    node_before_paths = build_validity_matrix(
        _vbm_record(),
        _validity_request(relation="官鬼", position=None),
    )
    path_last = build_validity_matrix(
        _cross_record(),
        _validity_request(relation="兄弟", position=5),
    )

    assert reality_first.focus_status == "reality_blocked"
    assert reality_first.reality_override == "blocking_confirmed_with_bound_refs"
    assert provenance_before_use.focus_selection.status == "ambiguous"
    assert provenance_before_use.focus_status == "calendar_unconfirmed"
    assert use_before_paths.focus_status == "needs_confirmation"
    assert use_before_paths.paths == ()
    assert node_before_paths.focus_status == "unresolved"
    assert not any(
        path.validity_status == "active_candidate"
        for path in node_before_paths.paths
    )
    assert path_last.focus_status == "available_candidate"
    assert _edge(path_last, "changed:4:cross-to-use:5").status == "pruned"
    assert _edge(path_last, "moving:4:to-use:5").status == "active_candidate"


def test_priority_profile_is_closed_hashed_and_not_request_configurable() -> None:
    request = _validity_request(relation="兄弟", position=5)
    payload = request.to_dict()
    payload["rule_profile_id"] = "caller-controlled-profile"

    with pytest.raises(LiuYaoError) as raised:
        ValidityRequest.from_mapping(payload)

    assert raised.value.code == "UNSUPPORTED_RULE_PROFILE"
    report = build_validity_matrix(
        _cross_record(),
        _validity_request(relation="兄弟", position=5),
    )
    report_payload = report.to_dict()
    profile = report_payload["rule_profile"]
    engineering = report_payload["engineering_policy"]
    assert profile["profile_id"] == VALIDITY_RULE_PROFILE_ID
    assert profile["profile_sha256"] == VALIDITY_RULE_PROFILE_SHA256
    assert engineering["policy_id"] == VALIDITY_ENGINEERING_POLICY_ID
    assert engineering["policy_sha256"] == VALIDITY_ENGINEERING_POLICY_SHA256
    assert engineering["precondition_gates"] == list(VALIDITY_PRECONDITION_GATES)
    assert profile["rule_contract"]["changed_line_scope"] == (
        "same_position_original_only"
    )
    assert engineering["policy_contract"]["changed_line_enforcement"] == (
        "exclude_cross_position_edges_with_receipt"
    )
    assert engineering["policy_contract"]["maximum_path_hops"] == 2
    assert [item.order for item in VALIDITY_PRIORITY_BANDS] == sorted(
        (item.order for item in VALIDITY_PRIORITY_BANDS), reverse=True
    )
    assert len(VALIDITY_RULE_PROFILE_SHA256) == 64


def test_result_binds_case_chart_requests_runtime_policy_and_canonical_hashes() -> None:
    record = _cross_record()
    request = _validity_request(relation="兄弟", position=5)
    report = build_validity_matrix(record, request)
    advanced = build_advanced_runtime_report(record, request.advanced_context)
    payload = report.to_dict()

    assert payload["case_record_sha256"] == record.canonical_sha256
    assert payload["priority_table_sha256"] == VALIDITY_PRIORITY_TABLE_SHA256
    assert payload["chart_sha256"] == record.chart.canonical_sha256
    assert payload["interpretation_request_sha256"] == request.interpretation.canonical_sha256
    assert payload["advanced_runtime_sha256"] == advanced.canonical_sha256
    assert payload["rule_profile"]["profile_sha256"] == VALIDITY_RULE_PROFILE_SHA256
    assert (
        payload["engineering_policy"]["priority_table_sha256"]
        == VALIDITY_PRIORITY_TABLE_SHA256
    )
    assert payload["engineering_policy_sha256"] == VALIDITY_ENGINEERING_POLICY_SHA256
    profile_payload = dict(payload["rule_profile"])
    assert profile_payload.pop("profile_sha256") == VALIDITY_RULE_PROFILE_SHA256
    engineering_payload = dict(payload["engineering_policy"])
    assert (
        engineering_payload.pop("policy_sha256")
        == VALIDITY_ENGINEERING_POLICY_SHA256
    )
    assert digest(profile_payload) == VALIDITY_RULE_PROFILE_SHA256
    assert digest(engineering_payload) == VALIDITY_ENGINEERING_POLICY_SHA256
    assert digest(
        {
            "priority_bands": payload["engineering_policy"]["priority_bands"],
            "precondition_gates": payload["engineering_policy"]["precondition_gates"],
            "gate_priority": payload["engineering_policy"]["gate_priority"],
        }
    ) == VALIDITY_PRIORITY_TABLE_SHA256
    assert payload["canonical_sha256"] == digest(report.to_dict(include_hash=False))
    assert len(payload["trace_sha256"]) == 64
    assert len(payload["canonical_sha256"]) == 64


def test_public_policy_contracts_and_report_payload_are_mutation_safe() -> None:
    report = build_validity_matrix(
        _cross_record(),
        _validity_request(relation="兄弟", position=5),
    )
    original_hash = report.canonical_sha256

    with pytest.raises(TypeError):
        VALIDITY_RULE_CONTRACT["single_condition_policy"] = "mutated"  # type: ignore[index]
    with pytest.raises(TypeError):
        VALIDITY_ENGINEERING_POLICY["maximum_path_hops"] = 99  # type: ignore[index]

    payload = report.to_dict()
    payload["rule_profile"]["rule_contract"]["single_condition_policy"] = "mutated"
    payload["rule_profile"]["rule_source_evidence"]["void"][0][
        "source_level"
    ] = "mutated"
    payload["engineering_policy"]["policy_contract"]["maximum_path_hops"] = 99
    repeated = report.to_dict()

    assert repeated["rule_profile"]["rule_contract"]["single_condition_policy"] == (
        "open_obligation_never_hard_prune"
    )
    assert repeated["engineering_policy"]["policy_contract"]["maximum_path_hops"] == 2
    assert repeated["rule_profile"]["rule_source_evidence"]["void"][0][
        "source_level"
    ] != "mutated"
    assert report.canonical_sha256 == original_hash


def test_rule_trace_has_structured_provenance_scope_and_obligation_ledger() -> None:
    report = build_validity_matrix(
        _vbm_record(),
        _validity_request(relation="官鬼", position=None),
    )
    payload = report.to_dict()
    original = _node(report, "original:4")
    month_break = next(
        hit for hit in original.rule_hits if hit.reason_code == "MONTH_BREAK_OPEN"
    )
    endpoint = next(
        hit
        for hit in _edge(report, "changed:4:self").rule_hits
        if hit.rule_id == "LYV-PATH-ENDPOINT-GATE-001"
    )

    assert month_break.policy_id == VALIDITY_RULE_PROFILE_ID
    assert month_break.source_family == "shaoweihua-liuyao-lineage"
    assert month_break.source_level == "per_reference"
    assert month_break.priority_policy_id == VALIDITY_ENGINEERING_POLICY_ID
    assert month_break.topic_scope == "general_structure_scope_unresolved"
    assert month_break.node_role == "selected_use"
    assert month_break.opened_obligations == ("MONTH_BREAK_OPEN",)
    assert month_break.discharged_obligations == ()
    assert month_break.remaining_obligations == ("MONTH_BREAK_OPEN",)
    assert month_break.outcome == "obligation_open"
    assert all("print" in ref and "pdf" in ref for ref in month_break.source_refs)
    assert {item.source_level for item in month_break.source_evidence} == {
        "author_rule",
        "author_case",
    }
    assert all(
        item.source_family == "shaoweihua-liuyao-lineage"
        for item in month_break.source_evidence
    )
    assert endpoint.policy_id == VALIDITY_ENGINEERING_POLICY_ID
    assert endpoint.priority_policy_id == VALIDITY_ENGINEERING_POLICY_ID
    assert endpoint.source_refs == ()
    assert endpoint.source_evidence == ()
    assert endpoint.source_level == "engineering_policy"
    anomalies = payload["rule_profile"]["source_text_anomalies"]
    assert payload["rule_profile"]["source_family_aliases"] == {
        "shaoweihua-liuyao-lineage": "F_SHAO_PARALLEL_TEXT",
        "zhangzhichun-commentary": "F_ZHANG_COMMENTARY",
    }
    assert {
        item["source_level"]
        for item in payload["rule_profile"]["rule_source_evidence"]["month_break"]
    } == {"author_rule", "author_case"}
    assert {item["anomaly_id"] for item in anomalies} == {
        "VOID_FILL_WORDING_219_202",
        "HIDDEN_TOMB_ABSOLUTE_GRAMMAR_172",
    }
    assert all(
        item["reason_code"] == "SOURCE_TEXT_ANOMALY"
        and item["activates_rules"] is False
        for item in anomalies
    )
    scope_rule = next(
        item
        for item in payload["rule_profile"]["supplementary_scope_audit"]["rules"]
        if item["audit_id"] == "ZHANG-LIFELONG-SELF-VOID-SCOPE"
    )
    assert scope_rule["topic_scope"] == "lifelong"
    assert scope_rule["node_role"] == "self_line"
    assert scope_rule["source_level"] == "author_rule"
    assert scope_rule["activates_rules"] is False


def test_storage_release_preserves_normalized_relation_and_source_terms() -> None:
    record = _record(
        case_id="VALIDITY-STORAGE-RELEASE",
        lines=(7, 8, 8, 6, 7, 7),
        month_branch="未",
        day_ganzhi="乙丑",
    )
    report = build_validity_matrix(
        record,
        _validity_request(relation="兄弟", position=6),
    )
    use = _node(report, "original:6")
    release = next(
        hit for hit in use.rule_hits if hit.reason_code == "TOMB_RELEASE_CANDIDATE"
    )

    assert release.normalized_relation == "storage_release_by_clash"
    assert release.source_terms == ("冲库", "冲开库", "库之破")
    assert any(
        "print296/pdf296" in item.source_ref
        and "冲开库" in item.source_terms
        for item in release.source_evidence
    )
    assert any(
        "print358/pdf373" in item.source_ref
        and "冲开库" in item.source_terms
        for item in release.source_evidence
    )
    assert "冲墓" not in json.dumps(release.to_dict(), ensure_ascii=False)
    assert release.discharged_obligations == ()
    assert release.remaining_obligations == ("MONTH_TOMB_EFFECT_OPEN",)
    assert "MONTH_TOMB_EFFECT_OPEN" in use.open_obligations


def test_unconfirmed_calendar_cannot_leak_void_or_other_calendar_rules() -> None:
    vbm_record = _vbm_record()
    hidden_record = _hidden_record(flying_constrained=False)
    assert vbm_record.chart.lines[3].is_void is True
    assert hidden_record.chart.void_branches is not None
    assert "酉" in hidden_record.chart.void_branches

    reports = (
        build_validity_matrix(
            vbm_record,
            _validity_request(relation="官鬼", position=None, confirmed=False),
        ),
        build_validity_matrix(
            hidden_record,
            _validity_request(relation="官鬼", position=None, confirmed=False),
        ),
    )
    forbidden_reasons = {
        "VOID_EFFECT_OPEN",
        "RULE_EFFECT_CONFLICT",
        "MONTH_BREAK_OPEN",
        "DAY_CLASH_EFFECT_OPEN",
        "MONTH_TOMB_EFFECT_OPEN",
        "DAY_TOMB_EFFECT_OPEN",
        "MONTH_ABSOLUTE_EFFECT_OPEN",
        "DAY_ABSOLUTE_EFFECT_OPEN",
    }

    for report in reports:
        assert report.focus_status == "calendar_unconfirmed"
        evaluated = list(report.nodes) + [
            item.hidden_node for item in report.hidden_candidates
        ]
        assert evaluated
        assert all(
            not forbidden_reasons.intersection(
                hit.reason_code for hit in node.rule_hits
            )
            for node in evaluated
        )
        assert all(
            node.open_obligations == ("CALENDAR_PROVENANCE_UNCONFIRMED",)
            for node in evaluated
        )
        assert all(
            hit.policy_id == VALIDITY_ENGINEERING_POLICY_ID
            for node in evaluated
            for hit in node.rule_hits
        )


def test_every_open_obligation_and_relief_candidate_has_a_trace_receipt() -> None:
    reports = (
        build_validity_matrix(
            _vbm_record(),
            _validity_request(relation="官鬼", position=None),
        ),
        build_validity_matrix(
            _hidden_record(flying_constrained=True),
            _validity_request(relation="妻财", position=3),
        ),
        build_validity_matrix(
            _record(
                case_id="VALIDITY-LEDGER-STORAGE",
                lines=(7, 8, 8, 6, 7, 7),
                month_branch="未",
                day_ganzhi="乙丑",
            ),
            _validity_request(relation="兄弟", position=6),
        ),
    )

    for report in reports:
        for node in tuple(report.nodes) + tuple(
            item.hidden_node for item in report.hidden_candidates
        ):
            opened = {
                obligation
                for hit in node.rule_hits
                for obligation in hit.opened_obligations
            }
            reasons = {hit.reason_code for hit in node.rule_hits}
            assert set(node.open_obligations).issubset(opened)
            assert set(node.relief_candidates).issubset(reasons)
        for hidden in report.hidden_candidates:
            opened = {
                obligation
                for hit in hidden.rule_hits
                for obligation in hit.opened_obligations
            }
            reasons = {hit.reason_code for hit in hidden.rule_hits}
            assert set(hidden.open_obligations).issubset(opened)
            assert set(hidden.release_candidates).issubset(reasons)
            assert set(
                hidden.hidden_node.open_obligations + hidden.open_obligations
            ).issubset(report.inventory_dependencies)

        nodes_by_id = {item.node_id: item for item in report.nodes}
        for edge in report.edges:
            if edge.status != "deferred":
                continue
            endpoint = next(
                hit
                for hit in edge.rule_hits
                if hit.rule_id == "LYV-PATH-ENDPOINT-GATE-001"
            )
            expected = set(nodes_by_id[edge.source_node_id].open_obligations) | set(
                nodes_by_id[edge.target_node_id].open_obligations
            )
            assert set(endpoint.remaining_obligations) == expected


def test_opposing_active_direct_paths_propagate_to_focus_unresolved() -> None:
    record = _record(
        case_id="VALIDITY-OPPOSING-PATHS",
        lines=(7, 7, 7, 7, 6, 9),
        month_branch="子",
        day_ganzhi="甲子",
    )
    report = build_validity_matrix(
        record,
        _validity_request(relation="兄弟", position=4),
    )
    conflict = next(
        item for item in report.conflicts if item.code == "OPPOSING_DIRECT_PATHS"
    )
    subject_paths = tuple(
        path for path in report.paths if path.path_id in conflict.subjects
    )

    assert report.focus_status == "unresolved"
    assert "OPPOSING_DIRECT_PATHS" in report.focus_dependencies
    assert {path.direction for path in subject_paths} == {"supportive", "restrictive"}
    assert all(
        path.validity_status == "active_candidate"
        and path.enumeration_status == "retained"
        and path.candidate_graph_reaches_focus
        for path in subject_paths
    )


def test_result_is_deterministic_but_hash_changes_with_semantic_inputs() -> None:
    record = _cross_record()
    base_request = _validity_request(relation="兄弟", position=5)
    first = build_validity_matrix(record, base_request)
    second = build_validity_matrix(record, ValidityRequest.from_mapping(base_request.to_dict()))
    changed_source = build_validity_matrix(
        record,
        _validity_request(
            relation="兄弟",
            position=5,
            calendar_source_refs=("source:different-calendar-receipt",),
        ),
    )
    reality_blocked = build_validity_matrix(
        record,
        _validity_request(
            relation="兄弟",
            position=5,
            reality_status="blocking",
        ),
    )

    assert first.to_dict() == second.to_dict()
    assert first.canonical_sha256 == second.canonical_sha256
    assert len(
        {
            first.canonical_sha256,
            changed_source.canonical_sha256,
            reality_blocked.canonical_sha256,
        }
    ) == 3


@pytest.mark.parametrize(
    "report",
    [
        pytest.param(
            lambda: build_validity_matrix(
                _cross_record(), _validity_request(relation="兄弟", position=5)
            ),
            id="available",
        ),
        pytest.param(
            lambda: build_validity_matrix(
                _vbm_record(), _validity_request(relation="官鬼", position=None)
            ),
            id="unresolved",
        ),
        pytest.param(
            lambda: build_validity_matrix(
                _static_qian_record(),
                _validity_request(relation="父母", position=None),
            ),
            id="needs-confirmation",
        ),
        pytest.param(
            lambda: build_validity_matrix(
                _cross_record(),
                _validity_request(
                    relation="兄弟", position=5, reality_status="blocking"
                ),
            ),
            id="reality-blocked",
        ),
    ],
)
def test_every_terminal_status_remains_review_only(report) -> None:
    payload = report().to_dict()
    text = json.dumps(payload, ensure_ascii=False)

    assert payload["validity_matrix_status"] == "review_only"
    assert payload["production_allowed"] is False
    assert VALIDITY_MATRIX_PRODUCTION_ALLOWED is False
    assert payload["prediction_validity"] == PREDICTION_VALIDITY == "not_evaluated"
    for forbidden_key in ("probability", "success_probability", "timing", "exact_date"):
        assert forbidden_key not in payload
    for forbidden_claim in ("必然成功", "必然失败", "百分百", "必上岸", "必怀孕", "必复合", "注定"):
        assert forbidden_claim not in text
