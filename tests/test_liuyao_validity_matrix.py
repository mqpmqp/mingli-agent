from __future__ import annotations

from mingli.liuyao.advanced_runtime import AdvancedContextRequest
from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.interpretation import InterpretationRequest
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.tables import PREDICTION_VALIDITY
from mingli.liuyao.validation import LiuYaoError
from mingli.liuyao.validity_matrix import (
    VALIDITY_MATRIX_PRODUCTION_ALLOWED,
    ValidityRequest,
    build_validity_matrix,
)


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
    month_branch: str | None = "丑",
    day_ganzhi: str | None = "甲申",
):
    return create_case_record(
        LiuYaoCastInput(
            case_id="VALIDITY-MATRIX-TEST",
            question="synthetic",
            line_values=lines,
            event_contract=_contract(),
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
            month_branch=month_branch,
            day_ganzhi=day_ganzhi,
        )
    )


def _interpretation(
    *,
    relation: str = "妻财",
    position: int | None = 4,
    confirmed: bool = True,
    reality_status: str = "unknown",
) -> InterpretationRequest:
    payload: dict[str, object] = {
        "topic": "general",
        "use_relation": relation,
        "primary_position": position,
        "calendar_context_confirmed": confirmed,
        "reality_status": reality_status,
    }
    if confirmed:
        payload["calendar_source_refs"] = ["source:calendar"]
    if reality_status != "unknown":
        payload["reality_facts"] = ["synthetic verified blocker"]
        payload["reality_evidence_refs"] = ["source:reality"]
    return InterpretationRequest.from_mapping(payload)


def _request(
    *,
    relation: str = "妻财",
    position: int | None = 4,
    confirmed: bool = True,
    reality_status: str = "unknown",
) -> ValidityRequest:
    return ValidityRequest(
        interpretation=_interpretation(
            relation=relation,
            position=position,
            confirmed=confirmed,
            reality_status=reality_status,
        ),
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=confirmed,
            calendar_source_refs=("source:calendar",) if confirmed else (),
        ),
    )


def test_calendar_confirmation_mismatch_is_rejected() -> None:
    try:
        ValidityRequest(
            interpretation=_interpretation(confirmed=True),
            advanced_context=AdvancedContextRequest(),
        )
    except LiuYaoError as exc:
        assert exc.code == "CALENDAR_CONFIRMATION_MISMATCH"
    else:
        raise AssertionError("mismatched calendar confirmation must be rejected")


def test_moving_use_line_with_month_break_and_void_stays_conditional() -> None:
    report = build_validity_matrix(_record(), _request())
    use_line = next(line for line in report.line_validity if line.position == 4)
    codes = {conflict.code for conflict in report.conflicts}

    assert report.selected_use_position == 4
    assert use_line.selected_use is True
    assert use_line.moving is True
    assert "month_break" in use_line.conditions
    assert "void_effect_unresolved" in use_line.ambiguous_conditions
    assert use_line.availability == "conditional"
    assert use_line.changed_availability == "unresolved"
    assert "VOID_AND_MONTH_BREAK" in codes
    assert "MOVING_BUT_CONDITIONAL" in codes
    assert "CHANGED_LINE_CONDITIONAL" in codes
    assert report.matrix_status == "conditional"


def test_changed_line_edge_is_not_activated_while_changed_line_is_void() -> None:
    report = build_validity_matrix(_record(), _request())
    edge = next(item for item in report.influence_edges if item.edge_id == "changed:4:4")

    assert edge.source_kind == "changed_line"
    assert edge.source_availability == "unresolved"
    assert edge.edge_status == "conditional"


def test_unconfirmed_calendar_context_keeps_all_line_effectiveness_unknown() -> None:
    report = build_validity_matrix(
        _record(),
        _request(confirmed=False),
    )

    assert report.matrix_status == "calendar_unconfirmed"
    assert all(line.availability == "unknown_context" for line in report.line_validity)
    assert "calendar_context_not_confirmed" in report.unresolved_dependencies


def test_reality_block_overrides_structural_candidates() -> None:
    report = build_validity_matrix(
        _record(month_branch="未", day_ganzhi="甲子"),
        _request(reality_status="blocking"),
    )

    assert report.matrix_status == "reality_blocked"
    assert report.reality_override == "blocking"
    assert any(conflict.code == "REALITY_HARD_BLOCK" for conflict in report.conflicts)
    assert "结构候选不得覆盖现实事实" in report.headline


def test_hidden_spirit_remains_candidate_not_an_automatic_use_line() -> None:
    report = build_validity_matrix(
        _record(),
        _request(relation="官鬼", position=None),
    )

    assert report.matrix_status == "needs_confirmation"
    assert report.selected_use_position is None
    assert report.hidden_candidates
    assert any(item.relation == "官鬼" and item.position == 3 for item in report.hidden_candidates)
    assert all("candidate" in item.status or item.status == "unknown_context" for item in report.hidden_candidates)


def test_multi_moving_graph_emits_pair_and_changed_edges_without_final_path_claim() -> None:
    report = build_validity_matrix(
        _record(lines=(9, 9, 9, 9, 9, 9), month_branch="辰", day_ganzhi="甲子"),
        _request(relation="官鬼", position=4),
    )

    moving_edges = [edge for edge in report.influence_edges if edge.source_kind == "moving_line"]
    changed_edges = [edge for edge in report.influence_edges if edge.source_kind == "changed_line"]
    assert len(moving_edges) == 15
    assert len(changed_edges) == 6
    assert set(edge.edge_status for edge in report.influence_edges) <= {
        "active_candidate",
        "conditional",
        "unknown_context",
    }
    assert "dynamic_paths_not_fully_active" in report.unresolved_dependencies


def test_report_is_deterministic_review_only_and_has_no_probability_field() -> None:
    first = build_validity_matrix(_record(), _request())
    second = build_validity_matrix(_record(), _request())
    payload = first.to_dict()

    assert first.to_dict() == second.to_dict()
    assert payload["validity_matrix_status"] == "review_only"
    assert payload["production_allowed"] is False
    assert VALIDITY_MATRIX_PRODUCTION_ALLOWED is False
    assert payload["prediction_validity"] == PREDICTION_VALIDITY
    assert "probability" not in payload
    assert "timing" not in payload
    assert len(payload["canonical_sha256"]) == 64
