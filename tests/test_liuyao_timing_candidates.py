from __future__ import annotations

import pytest

from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.selection_core import AutoSelectionRequest
from mingli.liuyao.selection_runtime import SelectionRuntimeRequest
from mingli.liuyao.tables import PREDICTION_VALIDITY, digest
from mingli.liuyao.timing_candidates import (
    TIMING_PRODUCTION_ALLOWED,
    TimingAnchor,
    TimingRequest,
    build_timing_report,
)
from mingli.liuyao.validation import LiuYaoError


def _contract(deadline: str = "2026-12-31") -> EventContract:
    return EventContract(
        target_event="进入最终公示名单",
        deadline=deadline,
        success_criteria="官方最终公示名单包含目标人",
        evidence_requirement="官方公示或可核验录用通知",
    )


def _record(
    lines: tuple[int, ...] = (6, 7, 7, 8, 7, 7),
    *,
    month_branch: str | None = "卯",
    day_ganzhi: str | None = "甲申",
    deadline: str = "2026-12-31",
):
    return create_case_record(
        LiuYaoCastInput(
            case_id="TIMING-TEST",
            question="本批次是否最终录用",
            line_values=lines,
            event_contract=_contract(deadline),
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
            month_branch=month_branch,
            day_ganzhi=day_ganzhi,
        )
    )


def _selection(
    record,
    *,
    topic: str = "exam",
    focus_dimension: str = "current_exam",
    calendar_confirmed: bool = True,
    reality_status: str = "unknown",
    reality_facts: tuple[str, ...] = (),
    reality_evidence_refs: tuple[str, ...] = (),
) -> SelectionRuntimeRequest:
    selection = AutoSelectionRequest(
        topic=topic,
        focus_dimension=focus_dimension,
        contract_focus_confirmed=True,
        contract_source_refs=("source:event-contract",),
        calendar_context_confirmed=calendar_confirmed,
        calendar_source_refs=("source:calendar",) if calendar_confirmed else (),
        reality_status=reality_status,
        reality_facts=reality_facts,
        reality_evidence_refs=reality_evidence_refs,
    )
    return SelectionRuntimeRequest(
        selection=selection,
        event_contract_sha256=digest(record.cast.event_contract.to_dict()),
    )


def _anchor(
    anchor_id: str = "exam-stage",
    *,
    branches: tuple[str, ...] = ("酉",),
    start: str = "2026-09-01",
    end: str = "2026-09-30",
) -> TimingAnchor:
    return TimingAnchor(
        anchor_id=anchor_id,
        label="官方考试流程窗口",
        start_date=start,
        end_date=end,
        branch_tags=branches,
        source_refs=("source:official-schedule", "source:verified-branch-map"),
    )


def test_symbolic_triggers_are_generated_without_invented_dates() -> None:
    record = _record()
    report = build_timing_report(
        record,
        TimingRequest(selection=_selection(record)),
    )

    assert report.timing_state == "symbolic_only"
    assert report.selected_position == 3
    assert report.selected_branch == "酉"
    assert report.candidates == ()
    assert {trigger.target_branch for trigger in report.symbolic_triggers} == {"酉", "卯", "辰"}
    assert all(trigger.priority_band in {"primary", "conditional", "secondary"} for trigger in report.symbolic_triggers)


def test_sourced_anchor_can_match_symbolic_trigger_as_candidate_only() -> None:
    record = _record()
    report = build_timing_report(
        record,
        TimingRequest(selection=_selection(record), anchors=(_anchor(),)),
    )

    assert report.timing_state == "anchored_candidates"
    assert len(report.candidates) == 1
    candidate = report.candidates[0]
    assert candidate.status == "candidate_only"
    assert candidate.start_date == "2026-09-01"
    assert candidate.end_date == "2026-09-30"
    assert candidate.matched_branches == ("酉",)
    assert candidate.trigger_ids
    assert report.unmatched_anchor_ids == ()


def test_unmatched_anchor_does_not_become_a_date_window() -> None:
    record = _record()
    report = build_timing_report(
        record,
        TimingRequest(
            selection=_selection(record),
            anchors=(_anchor(branches=("子",)),),
        ),
    )
    assert report.timing_state == "no_matching_anchor"
    assert report.candidates == ()
    assert report.unmatched_anchor_ids == ("exam-stage",)


def test_anchor_requires_source_and_valid_branch_tags() -> None:
    with pytest.raises(LiuYaoError) as raised:
        TimingAnchor(
            anchor_id="bad",
            label="bad",
            start_date="2026-09-01",
            end_date="2026-09-02",
            branch_tags=("酉",),
            source_refs=(),
        )
    assert raised.value.code == "TIMING_SOURCE_REQUIRED"

    with pytest.raises(LiuYaoError):
        TimingAnchor(
            anchor_id="bad-branch",
            label="bad",
            start_date="2026-09-01",
            end_date="2026-09-02",
            branch_tags=("不存在",),
            source_refs=("source:x",),
        )


def test_anchor_must_stay_inside_cast_and_contract_window() -> None:
    record = _record()
    with pytest.raises(LiuYaoError) as raised:
        build_timing_report(
            record,
            TimingRequest(
                selection=_selection(record),
                anchors=(_anchor(start="2026-08-01", end="2026-08-02"),),
            ),
        )
    assert raised.value.code == "TIMING_ANCHOR_BEFORE_CAST"

    with pytest.raises(LiuYaoError) as raised:
        build_timing_report(
            record,
            TimingRequest(
                selection=_selection(record),
                anchors=(_anchor(start="2027-01-01", end="2027-01-02"),),
            ),
        )
    assert raised.value.code == "TIMING_ANCHOR_OUTSIDE_CONTRACT"


def test_unconfirmed_calendar_blocks_all_timing_candidates() -> None:
    record = _record()
    report = build_timing_report(
        record,
        TimingRequest(
            selection=_selection(record, calendar_confirmed=False),
            anchors=(_anchor(),),
        ),
    )
    assert report.timing_state == "calendar_unconfirmed"
    assert report.symbolic_triggers == ()
    assert report.candidates == ()


def test_unresolved_use_selection_blocks_timing() -> None:
    record = _record()
    report = build_timing_report(
        record,
        TimingRequest(
            selection=_selection(
                record,
                topic="wealth",
                focus_dimension="current_money_event",
            ),
            anchors=(_anchor(),),
        ),
    )
    assert report.timing_state == "selection_unresolved"
    assert report.selected_position is None
    assert report.symbolic_triggers == ()


def test_reality_block_prevents_timing_output() -> None:
    record = _record()
    report = build_timing_report(
        record,
        TimingRequest(
            selection=_selection(
                record,
                reality_status="blocking",
                reality_facts=("资格审核已确认不通过",),
                reality_evidence_refs=("source:official-review",),
            ),
            anchors=(_anchor(),),
        ),
    )
    assert report.timing_state == "reality_blocked"
    assert report.symbolic_triggers == ()
    assert report.candidates == ()


def test_moving_use_line_adds_changed_branch_only_as_secondary_trigger() -> None:
    record = _record(lines=(7, 7, 9, 8, 7, 7))
    report = build_timing_report(record, TimingRequest(selection=_selection(record)))
    changed = [trigger for trigger in report.symbolic_triggers if trigger.trigger_kind == "changed_branch_value"]
    assert changed
    assert all(trigger.priority_band == "secondary" for trigger in changed)


def test_duplicate_anchor_ids_are_rejected() -> None:
    record = _record()
    with pytest.raises(LiuYaoError) as raised:
        TimingRequest(
            selection=_selection(record),
            anchors=(_anchor("same"), _anchor("same", branches=("辰",))),
        )
    assert raised.value.code == "DUPLICATE_TIMING_ANCHOR"


def test_report_is_deterministic_review_only_and_has_no_probability() -> None:
    record = _record()
    request = TimingRequest(selection=_selection(record), anchors=(_anchor(),))
    first = build_timing_report(record, request)
    second = build_timing_report(record, request)
    payload = first.to_dict()

    assert first.to_dict() == second.to_dict()
    assert payload["timing_status"] == "review_only"
    assert payload["production_allowed"] is False
    assert TIMING_PRODUCTION_ALLOWED is False
    assert payload["prediction_validity"] == PREDICTION_VALIDITY
    assert "probability" not in payload
    assert "confidence" not in payload
    assert len(payload["canonical_sha256"]) == 64
    assert all(candidate["status"] == "candidate_only" for candidate in payload["candidates"])
