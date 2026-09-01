from __future__ import annotations

from dataclasses import replace
from itertools import product
import json

import pytest

from mingli.liuyao import (
    ADVANCED_PRODUCTION_ALLOWED,
    ADVANCED_STATIC_TABLE_SHA256,
    ADVANCED_STRUCTURE_STATUS,
    EventContract,
    InterpretationRequest,
    LiuYaoCastInput,
    LiuYaoError,
    benchmark_liuyao_advanced_structure,
    build_advanced_structure,
    create_case_record,
    derive_calendar_context,
    growth_stage,
    interpret_case,
)
from mingli.liuyao.advanced import _advance_retreat, _fan_fu, _hidden_spirits
from mingli.liuyao_cli import main


def _contract() -> EventContract:
    return EventContract(
        target_event="synthetic event",
        deadline="2099-12-31",
        success_criteria="synthetic success",
        evidence_requirement="synthetic evidence",
    )


def _record(
    values: tuple[int, ...] = (7, 8, 8, 6, 7, 7),
    *,
    month_branch: str | None = None,
    day_ganzhi: str | None = None,
):
    return create_case_record(
        LiuYaoCastInput(
            case_id="SYNTHETIC-ADVANCED",
            question="synthetic question",
            line_values=values,
            event_contract=_contract(),
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
            month_branch=month_branch,
            day_ganzhi=day_ganzhi,
        )
    )


def test_calendar_context_is_derived_from_verified_internal_engine() -> None:
    receipt = derive_calendar_context(_record())

    assert receipt.month_branch == "申"
    assert receipt.day_ganzhi == "丁丑"
    assert receipt.day_branch == "丑"
    assert receipt.void_branches == ("申", "酉")
    assert receipt.active_month_term == "liqiu"
    assert receipt.timezone_offset == "+08:00"
    assert "bazi-deterministic-lichun-jie-noaa-v0.1" in receipt.source_method_id
    assert receipt.to_dict()["true_solar_time_applied"] is False


def test_matching_manual_context_is_accepted_and_wrong_context_is_blocked() -> None:
    matching = derive_calendar_context(_record(month_branch="申", day_ganzhi="丁丑"))
    assert matching.to_dict()["manual_context_matches"] is True

    with pytest.raises(LiuYaoError) as month_error:
        derive_calendar_context(_record(month_branch="酉", day_ganzhi="丁丑"))
    assert month_error.value.code == "CALENDAR_CONTEXT_CONFLICT"

    with pytest.raises(LiuYaoError) as day_error:
        derive_calendar_context(_record(month_branch="申", day_ganzhi="戊寅"))
    assert day_error.value.code == "CALENDAR_CONTEXT_CONFLICT"


def test_twelve_growth_stage_profile_uses_five_element_forward_cycle() -> None:
    assert growth_stage("木", "亥") == "长生"
    assert growth_stage("木", "卯") == "帝旺"
    assert growth_stage("木", "未") == "墓"
    assert growth_stage("火", "寅") == "长生"
    assert growth_stage("火", "戌") == "墓"
    assert growth_stage("金", "巳") == "长生"
    assert growth_stage("金", "丑") == "墓"
    assert growth_stage("水", "申") == "长生"
    assert growth_stage("土", "申") == "长生"
    assert growth_stage("水", "辰") == "墓"
    assert growth_stage("土", "辰") == "墓"

    for element in "木火土金水":
        stages = {growth_stage(element, branch) for branch in "子丑寅卯辰巳午未申酉戌亥"}
        assert len(stages) == 12


def test_hidden_and_flying_spirits_fill_only_missing_relations() -> None:
    record = _record()
    context = derive_calendar_context(record)
    hidden = _hidden_spirits(record, context)

    assert len(hidden) == 1
    item = hidden[0]
    assert item.relation == "官鬼"
    assert item.hidden_position == 3
    assert item.hidden_stem + item.hidden_branch == "辛酉"
    assert item.flying_position == 3
    assert item.flying_relation == "妻财"
    assert item.flying_to_hidden == "generates"
    assert item.to_dict()["status"] == "hidden_candidate"


def test_advanced_result_exposes_growth_tomb_extinction_and_hidden_records() -> None:
    result = build_advanced_structure(
        _record(),
        InterpretationRequest(topic="exam", focus_dimension="current_exam", use_relation="官鬼"),
    )

    assert len(result.growth_stages) == 6
    assert any(
        item.month_is_tomb
        or item.month_is_extinction
        or item.day_is_tomb
        or item.day_is_extinction
        for item in result.growth_stages
    )
    assert result.hidden_spirits[0].relation == "官鬼"
    assert result.status == "needs_confirmation"
    assert result.ranking_status == "hidden_leader_requires_confirmation"
    assert result.recommended_position is None


def test_advance_and_retreat_are_detected_without_declaring_good_or_bad() -> None:
    result = build_advanced_structure(
        _record((6, 6, 6, 6, 9, 6)),
        InterpretationRequest(topic="general", use_relation="父母"),
    )

    kinds = {(item.position, item.kind) for item in result.advance_retreat}
    assert (4, "advance") in kinds
    assert (5, "retreat") in kinds
    assert all(item.to_dict()["directional_judgement"] == "not_inferred" for item in result.advance_retreat)


def test_line_fanyin_and_fuyin_profiles_are_detected() -> None:
    fanyin = build_advanced_structure(
        _record((6, 6, 6, 8, 6, 6)),
        InterpretationRequest(topic="general", use_relation="父母"),
    )
    fuyin = build_advanced_structure(
        _record((6, 6, 6, 7, 6, 6)),
        InterpretationRequest(topic="general", use_relation="父母"),
    )

    assert any(item.kind == "fanyin" and item.scope == "line" for item in fanyin.fan_fu)
    assert any(item.kind == "fuyin" and item.scope == "line" for item in fuyin.fan_fu)
    assert all(item.to_dict()["directional_judgement"] == "not_inferred" for item in (*fanyin.fan_fu, *fuyin.fan_fu))


def test_multi_moving_graph_contains_cross_position_original_and_changed_edges() -> None:
    result = build_advanced_structure(
        _record((6, 6, 6, 6, 9, 6)),
        InterpretationRequest(topic="general", use_relation="父母"),
    )

    assert any(edge.actor_id == "line:4" and edge.target_id == "line:5" for edge in result.relation_graph)
    assert any(edge.actor_id == "changed:4" and edge.target_id == "line:5" for edge in result.relation_graph)
    assert len({edge.edge_id for edge in result.relation_graph}) == len(result.relation_graph)
    assert any(edge.active_state.startswith("conditional") for edge in result.relation_graph)


def test_spirit_roles_include_original_taboo_enemy_and_use_candidates() -> None:
    result = build_advanced_structure(
        _record((6, 6, 6, 6, 6, 6)),
        InterpretationRequest(topic="general", use_relation="兄弟"),
    )
    roles = {item.role for item in result.spirit_roles}

    assert "用神候选" in roles
    assert "原神候选" in roles
    assert "忌神候选" in roles
    assert "仇神候选" in roles
    assert all(item.to_dict()["directional_judgement"] == "not_inferred" for item in result.spirit_roles)


def test_use_ranking_finds_clear_leader_but_does_not_claim_prediction() -> None:
    result = build_advanced_structure(
        _record((6, 6, 6, 6, 6, 6)),
        InterpretationRequest(topic="general", use_relation="兄弟"),
    )

    assert result.ranking_status == "provisional_leader"
    assert result.status == "needs_confirmation"
    assert result.recommended_position == 4
    assert result.use_candidates[0].position == 4
    assert result.use_candidates[0].score > result.use_candidates[1].score
    payload = result.to_dict()
    assert payload["production_allowed"] is False
    assert payload["prediction_validity"] == "not_evaluated"


def test_use_ranking_keeps_ties_and_narrow_margins_unresolved() -> None:
    tied = build_advanced_structure(
        _record((6, 6, 6, 6, 7, 6)),
        InterpretationRequest(topic="general", use_relation="兄弟"),
    )
    narrow = build_advanced_structure(
        _record((6, 6, 6, 6, 6, 9)),
        InterpretationRequest(topic="general", use_relation="父母"),
    )

    assert tied.ranking_status == "tie"
    assert tied.recommended_position is None
    assert narrow.ranking_status == "narrow_margin"
    assert narrow.recommended_position is None
    assert any(conflict.code == "USE_RANKING_UNRESOLVED" for conflict in tied.conflicts)
    assert any(conflict.code == "USE_RANKING_UNRESOLVED" for conflict in narrow.conflicts)


def test_explicit_primary_is_preserved_even_when_ranking_prefers_another_line() -> None:
    result = build_advanced_structure(
        _record((6, 6, 6, 6, 6, 6)),
        InterpretationRequest(topic="general", use_relation="兄弟", primary_position=1),
    )

    assert result.ranking_status == "explicit_primary"
    assert result.recommended_position == 1
    assert result.use_candidates[0].position == 4
    assert any(conflict.code == "EXPLICIT_PRIMARY_DIFFERS_FROM_RANKING" for conflict in result.conflicts)


def test_rule_conflict_matrix_preserves_reality_override() -> None:
    result = build_advanced_structure(
        _record((6, 6, 6, 6, 6, 6)),
        InterpretationRequest(
            topic="general",
            use_relation="兄弟",
            reality_status="blocking",
            reality_facts=("synthetic verified blocker",),
        ),
    )

    assert result.status == "reality_blocked"
    assert result.recommended_position is None
    assert result.conflicts[0].code == "REALITY_OVERRIDE"
    assert result.conflicts[0].priority == 100


def test_manual_month_break_and_moving_conflict_is_retained() -> None:
    # 2026-08-31 is 申月; an 寅 candidate is month-broken. Search the fixed cast for such a moving use candidate.
    selected = None
    for values in product((6, 7, 8, 9), repeat=6):
        record = _record(values)
        for relation in ("父母", "兄弟", "子孙", "妻财", "官鬼"):
            candidate_positions = [
                line.position
                for line in record.chart.lines
                if line.six_relation == relation and line.moving and line.najia_branch == "寅"
            ]
            if candidate_positions:
                selected = (record, relation, candidate_positions[0])
                break
        if selected is not None:
            break
    assert selected is not None
    record, relation, position = selected
    result = build_advanced_structure(
        record,
        InterpretationRequest(topic="general", use_relation=relation, primary_position=position),
    )

    target = next(item for item in result.use_candidates if item.position == position and item.candidate_kind == "visible")
    codes = {factor.code for factor in target.factors}
    assert {"month_break", "moving"} <= codes
    assert any(conflict.code == "MONTH_BREAK_MOVING_CONDITIONAL" for conflict in result.conflicts)


def test_non_structural_exam_focus_uses_single_cast_boundary_wording() -> None:
    result = interpret_case(
        _record(),
        InterpretationRequest(topic="exam", focus_dimension="system_fit", use_relation="官鬼"),
    )

    assert result.status == "unsupported_focus"
    system_fit = next(item for item in result.topic_dimensions if item["dimension_id"] == "system_fit")
    assert "不能由单次六爻" in system_fit["plain"]



def test_auto_calendar_is_applied_to_base_interpretation_with_audit_hashes() -> None:
    record = _record()
    request = InterpretationRequest(topic="general", use_relation="妻财")
    result = build_advanced_structure(record, request)
    context = derive_calendar_context(record)
    effective_record = create_case_record(
        replace(
            record.cast,
            month_branch=context.month_branch,
            day_ganzhi=context.day_ganzhi,
        )
    )
    effective_request = replace(request, calendar_context_confirmed=True)
    expected_base = interpret_case(effective_record, effective_request)

    assert result.chart_sha256 == record.chart.canonical_sha256
    assert result.effective_chart_sha256 == effective_record.chart.canonical_sha256
    assert result.chart_sha256 != result.effective_chart_sha256
    assert result.request_sha256 == request.canonical_sha256
    assert result.effective_request_sha256 == effective_request.canonical_sha256
    assert result.base_interpretation_sha256 == expected_base.canonical_sha256
    assert result.to_dict()["ranking_semantics"] == "heuristic_review_score_not_probability"


def test_calendar_offset_with_seconds_is_rejected() -> None:
    record = _record()
    invalid = create_case_record(replace(record.cast, completed_at="2026-08-31T21:12:00+08:00:30"))

    with pytest.raises(LiuYaoError) as raised:
        derive_calendar_context(invalid)

    assert raised.value.code == "CALENDAR_CONTEXT_UNAVAILABLE"


def test_return_effect_and_advance_retreat_validity_conflicts_are_retained() -> None:
    return_effect = build_advanced_structure(
        _record((6, 6, 6, 6, 6, 6)),
        InterpretationRequest(topic="general", use_relation="父母", primary_position=2),
    )
    advance = build_advanced_structure(
        _record((6, 6, 6, 6, 9, 6)),
        InterpretationRequest(topic="general", use_relation="子孙", primary_position=4),
    )

    return_codes = {
        factor.code
        for candidate in return_effect.use_candidates
        if candidate.position == 2 and candidate.candidate_kind == "visible"
        for factor in candidate.factors
    }
    advance_codes = {
        factor.code
        for candidate in advance.use_candidates
        if candidate.position == 4 and candidate.candidate_kind == "visible"
        for factor in candidate.factors
    }
    assert {"return_generate", "changed_month_break"} <= return_codes
    assert {"advance", "void"} <= advance_codes
    assert any(conflict.code == "RETURN_EFFECT_VALIDITY_CONDITIONAL" for conflict in return_effect.conflicts)
    assert any(conflict.code == "ADVANCE_RETREAT_VALIDITY_CONDITIONAL" for conflict in advance.conflicts)


def test_flying_controls_hidden_is_not_treated_as_automatic_failure() -> None:
    result = build_advanced_structure(
        _record((6, 6, 6, 6, 7, 7)),
        InterpretationRequest(topic="general", use_relation="兄弟"),
    )

    assert any(item.relation == "兄弟" and item.flying_to_hidden == "controls" for item in result.hidden_spirits)
    conflict = next(item for item in result.conflicts if item.code == "HIDDEN_FLYING_CONSTRAINT")
    assert conflict.resolution == "manual_confirmation_required"
    assert "不能仅凭飞克伏判失败" in conflict.plain

def test_advanced_hash_and_profiles_are_stable() -> None:
    result = build_advanced_structure(
        _record(),
        InterpretationRequest(topic="exam", focus_dimension="current_exam", use_relation="官鬼"),
    )
    first = result.to_dict()
    second = build_advanced_structure(
        _record(),
        InterpretationRequest(topic="exam", focus_dimension="current_exam", use_relation="官鬼"),
    ).to_dict()

    assert first == second
    assert ADVANCED_STATIC_TABLE_SHA256 == "14c2792232fb3a8d06d29e85a566b7aba477ba368edc266acf8e9044d8e001ee"
    assert first["advanced_static_table_sha256"] == ADVANCED_STATIC_TABLE_SHA256
    assert first["interpretation_status"] == ADVANCED_STRUCTURE_STATUS
    assert ADVANCED_PRODUCTION_ALLOWED is False
    assert first["canonical_sha256"] == second["canonical_sha256"]



def test_cli_calendar_advanced_and_benchmark_commands(tmp_path, capsys) -> None:
    record = _record()
    request = InterpretationRequest(topic="exam", focus_dimension="current_exam", use_relation="官鬼")
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False), encoding="utf-8")
    request_path.write_text(json.dumps(request.to_dict(), ensure_ascii=False), encoding="utf-8")

    assert main(["calendar-context", "--record", str(record_path)]) == 0
    calendar_payload = json.loads(capsys.readouterr().out)
    assert calendar_payload["month_branch"] == "申"
    assert calendar_payload["day_ganzhi"] == "丁丑"

    assert main(["advanced-interpret", "--record", str(record_path), "--request", str(request_path)]) == 0
    advanced_payload = json.loads(capsys.readouterr().out)
    assert advanced_payload["method_id"] == "liuyao-advanced-structure@0.2.0"
    assert advanced_payload["hidden_spirits"][0]["relation"] == "官鬼"

    assert main(["advanced-benchmark"]) == 0
    benchmark_payload = json.loads(capsys.readouterr().out)
    assert benchmark_payload["status"] == "passed"

def test_advanced_benchmark_passes() -> None:
    assert benchmark_liuyao_advanced_structure()["status"] == "passed"


@pytest.mark.benchmark
def test_advanced_tables_and_detectors_cover_all_4096_cast_patterns() -> None:
    relations = {"父母", "兄弟", "子孙", "妻财", "官鬼"}
    saw_advance = saw_retreat = saw_fanyin = saw_fuyin = False
    context_record = _record()
    context = derive_calendar_context(context_record)

    for pattern in range(4**6):
        remaining = pattern
        values = []
        for _ in range(6):
            values.append(6 + remaining % 4)
            remaining //= 4
        record = _record(tuple(values))
        hidden = _hidden_spirits(record, context)
        assert all(item.relation in relations for item in hidden)
        assert all(item.relation not in {line.six_relation for line in record.chart.lines} for item in hidden)
        for item in _advance_retreat(record):
            assert item.kind in {"advance", "retreat", "none"}
            saw_advance |= item.kind == "advance"
            saw_retreat |= item.kind == "retreat"
        for item in _fan_fu(record):
            assert item.kind in {"fanyin", "fuyin"}
            saw_fanyin |= item.kind == "fanyin"
            saw_fuyin |= item.kind == "fuyin"

    assert saw_advance and saw_retreat and saw_fanyin and saw_fuyin
