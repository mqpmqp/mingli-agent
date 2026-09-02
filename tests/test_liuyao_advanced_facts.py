from __future__ import annotations

from mingli.liuyao.advanced_benchmark import benchmark_liuyao_advanced_facts
from mingli.liuyao.advanced_facts import (
    ADVANCED_FACT_PRODUCTION_ALLOWED,
    ADVANCED_FACT_TABLE_SHA256,
    ADVANCE_PAIRS,
    RETREAT_PAIRS,
    build_advanced_fact_report,
    classify_branch_relation,
    classify_element_relation,
    classify_progression,
    growth_stage,
)
from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.tables import PREDICTION_VALIDITY


def _contract() -> EventContract:
    return EventContract(
        target_event="synthetic",
        deadline="2099-12-31",
        success_criteria="synthetic criterion",
        evidence_requirement="synthetic evidence",
    )


def _record(
    lines: tuple[int, ...] = (7, 8, 8, 6, 7, 7),
    *,
    month_branch: str | None = "亥",
    day_ganzhi: str | None = "甲申",
):
    return create_case_record(
        LiuYaoCastInput(
            case_id="ADVANCED-TEST",
            question="synthetic",
            line_values=lines,
            event_contract=_contract(),
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
            month_branch=month_branch,
            day_ganzhi=day_ganzhi,
        )
    )


def test_growth_stage_profile_has_expected_landmarks() -> None:
    assert growth_stage("木", "亥") == "长生"
    assert growth_stage("木", "未") == "墓"
    assert growth_stage("木", "申") == "绝"
    assert growth_stage("火", "寅") == "长生"
    assert growth_stage("金", "巳") == "长生"
    assert growth_stage("水", "申") == "长生"
    assert growth_stage("土", "申") == "长生"


def test_progression_and_branch_relations_are_frozen() -> None:
    for source, target in ADVANCE_PAIRS:
        assert classify_progression(source, target) == "advance"
        assert classify_progression(target, source) == "retreat"
    assert set((target, source) for source, target in ADVANCE_PAIRS) == set(RETREAT_PAIRS)
    assert classify_branch_relation("巳", "申") == "combine"
    assert classify_branch_relation("子", "午") == "clash"
    assert classify_branch_relation("辰", "辰") == "same"
    assert classify_branch_relation("子", "卯") == "none"


def test_element_relation_is_directional() -> None:
    assert classify_element_relation("木", "火") == "generates"
    assert classify_element_relation("火", "木") == "generated_by"
    assert classify_element_relation("木", "土") == "controls"
    assert classify_element_relation("土", "木") == "controlled_by"
    assert classify_element_relation("金", "金") == "same_element"


def test_missing_officer_is_located_as_hidden_spirit_candidate() -> None:
    report = build_advanced_fact_report(_record())
    hidden = [fact for fact in report.facts if fact.category == "hidden_spirit"]

    assert report.missing_relations == ("官鬼",)
    assert any(
        fact.positions == (3,)
        and fact.relation == "官鬼"
        and fact.branches == ("酉", "辰")
        and fact.elements == ("金", "土")
        for fact in hidden
    )
    assert any("不代表伏神已经有力" in fact.plain for fact in hidden)


def test_complete_hexagram_does_not_invent_hidden_spirit() -> None:
    report = build_advanced_fact_report(_record(lines=(6, 7, 7, 8, 7, 7)))
    assert report.missing_relations == ()
    assert not [fact for fact in report.facts if fact.category == "hidden_spirit"]


def test_growth_facts_include_original_and_changed_lines() -> None:
    report = build_advanced_fact_report(_record())
    growth = [fact for fact in report.facts if fact.category == "growth_stage"]

    assert report.context_status == "complete"
    assert len([fact for fact in growth if fact.scope == "month_original"]) == 6
    assert len([fact for fact in growth if fact.scope == "day_original"]) == 6
    assert len([fact for fact in growth if fact.scope == "month_changed"]) == 1
    assert len([fact for fact in growth if fact.scope == "day_changed"]) == 1


def test_missing_calendar_context_fails_closed_without_stage_facts() -> None:
    report = build_advanced_fact_report(_record(month_branch=None, day_ganzhi=None))
    assert report.context_status == "missing"
    assert not [fact for fact in report.facts if fact.category == "growth_stage"]
    assert len(report.warnings) >= 2


def test_static_hexagram_is_not_mislabeled_as_fuyin() -> None:
    report = build_advanced_fact_report(_record(lines=(7, 7, 7, 7, 7, 7)))
    assert not [fact for fact in report.facts if fact.category == "repetition"]


def test_multi_moving_lines_emit_graph_edges() -> None:
    report = build_advanced_fact_report(_record(lines=(9, 9, 9, 9, 9, 9)))
    element_edges = [fact for fact in report.facts if fact.category == "moving_graph_element"]
    self_edges = [fact for fact in report.facts if fact.category == "self_change_element"]

    assert len(element_edges) == 15
    assert len(self_edges) == 6
    assert all(fact.conditional for fact in element_edges)


def test_report_is_deterministic_review_only_and_not_a_prediction() -> None:
    first = build_advanced_fact_report(_record())
    second = build_advanced_fact_report(_record())
    payload = first.to_dict()

    assert first.to_dict() == second.to_dict()
    assert payload["advanced_fact_status"] == "review_only"
    assert payload["production_allowed"] is False
    assert ADVANCED_FACT_PRODUCTION_ALLOWED is False
    assert payload["prediction_validity"] == PREDICTION_VALIDITY
    assert payload["advanced_table_sha256"] == ADVANCED_FACT_TABLE_SHA256
    assert len(payload["canonical_sha256"]) == 64


def test_advanced_benchmark_passes() -> None:
    assert benchmark_liuyao_advanced_facts()["status"] == "passed"
