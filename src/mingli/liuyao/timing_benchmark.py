from __future__ import annotations

from .case_record import create_case_record
from .models import EventContract, LiuYaoCastInput
from .selection_core import AutoSelectionRequest
from .selection_runtime import SelectionRuntimeRequest
from .tables import PREDICTION_VALIDITY, digest
from .timing_candidates import (
    TIMING_PRODUCTION_ALLOWED,
    TimingAnchor,
    TimingRequest,
    build_timing_report,
)


def benchmark_liuyao_timing_candidates() -> dict[str, object]:
    contract = EventContract(
        target_event="synthetic timing event",
        deadline="2026-12-31",
        success_criteria="synthetic criterion",
        evidence_requirement="synthetic evidence",
    )
    record = create_case_record(
        LiuYaoCastInput(
            case_id="SYNTHETIC-TIMING",
            question="synthetic timing benchmark",
            line_values=(6, 7, 7, 8, 7, 7),
            event_contract=contract,
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
            month_branch="卯",
            day_ganzhi="甲申",
        )
    )
    selection = SelectionRuntimeRequest(
        selection=AutoSelectionRequest(
            topic="exam",
            focus_dimension="current_exam",
            contract_focus_confirmed=True,
            contract_source_refs=("source:synthetic-contract",),
            calendar_context_confirmed=True,
            calendar_source_refs=("source:synthetic-calendar",),
        ),
        event_contract_sha256=digest(contract.to_dict()),
    )
    symbolic = build_timing_report(record, TimingRequest(selection=selection))
    anchored = build_timing_report(
        record,
        TimingRequest(
            selection=selection,
            anchors=(
                TimingAnchor(
                    anchor_id="synthetic-stage",
                    label="synthetic process stage",
                    start_date="2026-09-01",
                    end_date="2026-09-30",
                    branch_tags=("酉",),
                    source_refs=("source:synthetic-schedule", "source:synthetic-branch-map"),
                ),
            ),
        ),
    )
    checks = {
        "symbolic_only_without_anchor": symbolic.timing_state == "symbolic_only",
        "selected_branch": symbolic.selected_branch == "酉",
        "symbolic_has_value_clash_combine": {trigger.target_branch for trigger in symbolic.symbolic_triggers} == {"酉", "卯", "辰"},
        "anchored_candidate": anchored.timing_state == "anchored_candidates" and len(anchored.candidates) == 1,
        "candidate_only": anchored.candidates[0].status == "candidate_only",
        "dates_from_input": anchored.candidates[0].start_date == "2026-09-01" and anchored.candidates[0].end_date == "2026-09-30",
        "review_only": anchored.to_dict()["timing_status"] == "review_only",
        "not_production": TIMING_PRODUCTION_ALLOWED is False,
        "not_prediction": anchored.to_dict()["prediction_validity"] == PREDICTION_VALIDITY,
        "no_probability": "probability" not in anchored.to_dict(),
        "no_confidence": "confidence" not in anchored.to_dict(),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "method_id": anchored.to_dict()["method_id"],
        "prediction_validity": PREDICTION_VALIDITY,
    }


__all__ = ["benchmark_liuyao_timing_candidates"]
