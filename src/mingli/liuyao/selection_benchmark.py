from __future__ import annotations

from .case_record import create_case_record
from .models import EventContract, LiuYaoCastInput
from .selection_core import AutoSelectionRequest
from .selection_runtime import (
    SELECTION_RUNTIME_PRODUCTION_ALLOWED,
    SelectionRuntimeRequest,
    build_selection_runtime_report,
)
from .tables import PREDICTION_VALIDITY, digest


def _record(lines: tuple[int, ...]):
    contract = EventContract(
        target_event="synthetic selection event",
        deadline="2099-12-31",
        success_criteria="synthetic criterion",
        evidence_requirement="synthetic evidence",
    )
    return create_case_record(
        LiuYaoCastInput(
            case_id="SYNTHETIC-SELECTION",
            question="synthetic selection benchmark",
            line_values=lines,
            event_contract=contract,
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
        )
    )


def _request(record, **overrides: object) -> SelectionRuntimeRequest:
    values: dict[str, object] = {
        "topic": "exam",
        "focus_dimension": "current_exam",
        "contract_focus_confirmed": True,
        "contract_source_refs": ("source:synthetic-contract",),
    }
    values.update(overrides)
    selection = AutoSelectionRequest(**values)
    return SelectionRuntimeRequest(
        selection=selection,
        event_contract_sha256=digest(record.cast.event_contract.to_dict()),
    )


def benchmark_liuyao_selection_runtime() -> dict[str, object]:
    visible = _record((6, 7, 7, 8, 7, 7))
    hidden = _record((7, 8, 8, 6, 7, 7))

    exam = build_selection_runtime_report(visible, _request(visible))
    hidden_exam = build_selection_runtime_report(hidden, _request(hidden))
    wealth_tie = build_selection_runtime_report(
        visible,
        _request(
            visible,
            topic="wealth",
            focus_dimension="current_money_event",
        ),
    )
    system_fit = build_selection_runtime_report(
        visible,
        _request(
            visible,
            focus_dimension="system_fit",
            primary_relation_override="官鬼",
            override_reason="synthetic bypass attempt",
        ),
    )

    checks = {
        "exam_four_dimensions": len(exam.topic_dimensions) == 4,
        "visible_officer_selected": exam.recommended_position == 3,
        "hidden_not_auto_selected": (
            hidden_exam.recommended_position is None
            and hidden_exam.recommendation_status == "hidden_candidate_needs_confirmation"
        ),
        "moving_does_not_break_tie": (
            wealth_tie.recommended_position is None
            and wealth_tie.recommendation_status == "tie_needs_confirmation"
        ),
        "unsupported_override_blocked": system_fit.recommendation_status == "unsupported_focus",
        "contract_hash_bound": "event_contract_hash_bound" in exam.policy_checks,
        "review_only": exam.to_dict()["selection_runtime_status"] == "review_only",
        "not_production": SELECTION_RUNTIME_PRODUCTION_ALLOWED is False,
        "not_prediction": exam.to_dict()["prediction_validity"] == PREDICTION_VALIDITY,
        "no_probability": "probability" not in exam.to_dict(),
        "no_timing": "timing" not in exam.to_dict(),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "method_id": exam.to_dict()["method_id"],
        "prediction_validity": PREDICTION_VALIDITY,
    }


__all__ = ["benchmark_liuyao_selection_runtime"]
