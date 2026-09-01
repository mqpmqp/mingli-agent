from __future__ import annotations

import json
from pathlib import Path

import pytest

from mingli.liuyao import (
    EventContract,
    InterpretationRequest,
    LiuYaoError,
    LiuYaoCastInput,
    benchmark_liuyao_interpretation,
    create_case_record,
    interpret_case,
)
from mingli.liuyao_cli import main


def _record(
    *,
    case_id: str = "INTERPRET-CASE",
    lines: tuple[int, ...] = (6, 7, 7, 8, 7, 7),
    month_branch: str | None = None,
    day_ganzhi: str | None = None,
    reality_facts: tuple[str, ...] = (),
):
    contract = EventContract(
        target_event="当前冻结事件",
        deadline="2099-12-31",
        success_criteria="可核验证据满足冻结标准",
        evidence_requirement="可核验现实证据",
    )
    cast = LiuYaoCastInput(
        case_id=case_id,
        question="当前事件的结构证据如何",
        line_values=lines,
        event_contract=contract,
        completed_at="2026-08-31T21:57:00+08:00",
        location="测试地点",
        month_branch=month_branch,
        day_ganzhi=day_ganzhi,
        reality_facts=reality_facts,
    )
    return create_case_record(cast)


def _request(**overrides: object) -> InterpretationRequest:
    values: dict[str, object] = {
        "topic": "general",
        "use_relation": "官鬼",
        "calendar_context_confirmed": False,
        "reality_status": "unknown",
    }
    values.update(overrides)
    return InterpretationRequest(**values)  # type: ignore[arg-type]


def test_unique_use_relation_is_selected_without_guessing_between_lines() -> None:
    result = interpret_case(_record(), _request())

    assert result.use_selection.status == "unique_candidate"
    assert result.use_selection.selected_position == 3
    assert result.confidence == "low"
    assert result.to_dict()["prediction_validity"] == "not_evaluated"
    assert result.to_dict()["production_allowed"] is False


def test_multiple_use_candidates_require_primary_position() -> None:
    result = interpret_case(_record(), _request(use_relation="妻财"))

    assert result.status == "needs_confirmation"
    assert result.use_selection.status == "ambiguous"
    assert result.use_selection.candidate_positions == (1, 4)
    assert result.evidence == ()
    assert result.conflicts[0].code == "USE_GOD_SELECTION_REQUIRED"


def test_confirmed_primary_position_must_match_relation() -> None:
    with pytest.raises(LiuYaoError) as raised:
        interpret_case(_record(), _request(use_relation="官鬼", primary_position=5))

    assert raised.value.code == "USE_GOD_MISMATCH"


def test_month_combination_is_ambiguous_and_not_scored() -> None:
    result = interpret_case(
        _record(month_branch="申", day_ganzhi="丁酉"),
        _request(
            topic="pregnancy",
            focus_dimension="conception_opportunity",
            use_relation="子孙",
            primary_position=5,
            calendar_context_confirmed=True,
        ),
    )

    month_combine = next(item for item in result.evidence if item.relation == "month_combine")
    assert month_combine.polarity == "ambiguous"
    assert month_combine.weight == 0
    assert "合起、合绊或合化" in month_combine.plain


def test_month_clash_is_recorded_as_month_break_constraint() -> None:
    result = interpret_case(
        _record(month_branch="亥", day_ganzhi="丁酉"),
        _request(
            topic="pregnancy",
            focus_dimension="conception_opportunity",
            use_relation="子孙",
            primary_position=5,
            calendar_context_confirmed=True,
        ),
    )

    month_break = next(item for item in result.evidence if item.relation == "month_break")
    assert month_break.polarity == "restrictive"
    assert month_break.weight == 3


def test_day_clash_stays_ambiguous_instead_of_becoming_hidden_motion_or_dispersion() -> None:
    result = interpret_case(
        _record(month_branch="申", day_ganzhi="乙亥"),
        _request(
            topic="pregnancy",
            focus_dimension="conception_opportunity",
            use_relation="子孙",
            primary_position=5,
            calendar_context_confirmed=True,
        ),
    )

    day_clash = next(item for item in result.evidence if item.relation == "day_clash")
    assert day_clash.polarity == "ambiguous"
    assert day_clash.weight == 0
    assert "触发" in day_clash.plain and "冲散" in day_clash.plain


def test_void_is_a_conditional_flag_not_a_binary_failure_rule() -> None:
    result = interpret_case(
        _record(month_branch="申", day_ganzhi="甲午"),
        _request(
            topic="pregnancy",
            focus_dimension="conception_opportunity",
            use_relation="子孙",
            primary_position=5,
            calendar_context_confirmed=True,
        ),
    )

    void = next(item for item in result.evidence if item.relation == "void")
    assert void.polarity == "ambiguous"
    assert void.weight == 0


def test_moving_use_line_return_generation_is_supportive() -> None:
    result = interpret_case(
        _record(lines=(7, 8, 8, 6, 7, 7), month_branch="午", day_ganzhi="丙午"),
        _request(
            use_relation="妻财",
            primary_position=4,
            calendar_context_confirmed=True,
            reality_status="supportive",
            reality_facts=("合成测试中的现实支持条件",),
        ),
    )

    return_generate = next(item for item in result.evidence if item.relation == "return_generates")
    assert return_generate.polarity == "supportive"
    assert return_generate.weight == 2
    assert result.structural_balance == "supportive"


def test_other_moving_line_element_effect_is_explicit() -> None:
    result = interpret_case(_record(), _request(use_relation="官鬼", primary_position=3))

    moving_support = next(item for item in result.evidence if item.source_kind == "moving_line")
    assert moving_support.actor_position == 1
    assert moving_support.relation == "generates_use"
    assert moving_support.polarity == "supportive"


def test_unconfirmed_calendar_context_is_skipped() -> None:
    result = interpret_case(
        _record(month_branch="申", day_ganzhi="丁酉"),
        _request(use_relation="子孙", primary_position=5, calendar_context_confirmed=False),
    )

    assert result.context_completeness == "unverified"
    assert not any(item.source_kind in {"month", "day"} for item in result.evidence)
    assert any("尚未确认来源" in warning for warning in result.warnings)


def test_confirmed_reality_blocker_overrides_supportive_structure() -> None:
    result = interpret_case(
        _record(lines=(7, 8, 8, 6, 7, 7), month_branch="午", day_ganzhi="丙午"),
        _request(
            use_relation="妻财",
            primary_position=4,
            calendar_context_confirmed=True,
            reality_status="blocking",
            reality_facts=("资格审核已确认不通过",),
        ),
    )

    assert result.structural_balance == "supportive"
    assert result.status == "reality_blocked"
    assert result.headline.startswith("现实条件构成阻断")
    assert any(item.code == "REALITY_OVERRIDES_STRUCTURE" for item in result.conflicts)


def test_exam_profile_keeps_four_dimensions_separate() -> None:
    result = interpret_case(
        _record(),
        _request(topic="exam", focus_dimension="current_exam", use_relation="官鬼", primary_position=3),
    )

    dimensions = {item["dimension_id"]: item for item in result.topic_dimensions}
    assert set(dimensions) == {"system_fit", "current_exam", "position_direction", "preparation_strategy"}
    assert dimensions["system_fit"]["scope"] == "outside_single_cast"
    assert dimensions["current_exam"]["state"] == "focused"


def test_relationship_profile_keeps_four_layers_separate() -> None:
    result = interpret_case(
        _record(),
        _request(
            topic="relationship_reconciliation",
            focus_dimension="reconciliation",
            use_relation="官鬼",
            primary_position=3,
        ),
    )

    dimensions = {item["dimension_id"]: item for item in result.topic_dimensions}
    assert set(dimensions) == {"bond", "recontact", "reconciliation", "stability"}
    assert dimensions["reconciliation"]["state"] == "focused"
    assert dimensions["stability"]["state"] == "separate_contract_required"


def test_non_structural_exam_focus_is_rejected_without_fake_reading() -> None:
    result = interpret_case(
        _record(),
        _request(topic="exam", focus_dimension="system_fit", use_relation="官鬼", primary_position=3),
    )

    assert result.status == "unsupported_focus"
    assert result.evidence == ()
    assert "不能由单次六爻" in result.topic_dimensions[0]["plain"]


def test_medical_confirmation_focus_is_professional_only() -> None:
    result = interpret_case(
        _record(),
        _request(
            topic="pregnancy",
            focus_dimension="medical_confirmation",
            use_relation="子孙",
            primary_position=5,
        ),
    )

    assert result.status == "unsupported_focus"
    assert result.evidence == ()
    assert result.headline == "当前焦点不应由单次六爻解释。"


def test_actor_roles_identify_candidates_without_claiming_final_usefulness() -> None:
    result = interpret_case(
        _record(),
        _request(use_relation="子孙", primary_position=5),
    )

    actors = {item.position: item.role_to_use for item in result.actors}
    assert actors[5] == "用神候选"
    assert actors[6] == "元神候选"
    assert actors[2] == "忌神候选"


def test_result_hash_is_stable_for_same_record_and_request() -> None:
    record = _record(month_branch="午", day_ganzhi="丙午")
    request = _request(
        use_relation="妻财",
        primary_position=4,
        calendar_context_confirmed=True,
        reality_status="supportive",
        reality_facts=("测试现实事实",),
    )

    first = interpret_case(record, request)
    second = interpret_case(record, request)
    assert first.to_dict() == second.to_dict()
    assert first.canonical_sha256 == second.canonical_sha256


def test_request_hash_tampering_is_rejected() -> None:
    payload = _request(use_relation="官鬼", primary_position=3).to_dict()
    payload["primary_position"] = 5

    with pytest.raises(LiuYaoError) as raised:
        InterpretationRequest.from_mapping(payload)

    assert raised.value.code == "RECORD_TAMPERED"


def test_output_contains_no_absolute_prediction_claims() -> None:
    result = interpret_case(
        _record(month_branch="申", day_ganzhi="丁酉"),
        _request(use_relation="子孙", primary_position=5, calendar_context_confirmed=True),
    )
    text = json.dumps(result.to_dict(), ensure_ascii=False)

    for forbidden in ("必然成功", "必然失败", "百分百", "必上岸", "必怀孕", "必复合", "注定"):
        assert forbidden not in text


def test_cli_interpret_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text(json.dumps(_record().to_dict(), ensure_ascii=False), encoding="utf-8")
    request_path.write_text(
        json.dumps(_request(use_relation="官鬼", primary_position=3).to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )

    assert main(["interpret", "--record", str(record_path), "--request", str(request_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["use_selection"]["selected_position"] == 3
    assert output["interpretation_status"] == "review_only"
    assert output["production_allowed"] is False


@pytest.mark.benchmark
def test_interpretation_benchmark_passes() -> None:
    result = benchmark_liuyao_interpretation()

    assert result["status"] == "passed"
    assert result["checks"]["combination_is_ambiguous"] is True
    assert result["checks"]["reality_blocks_structure"] is True
