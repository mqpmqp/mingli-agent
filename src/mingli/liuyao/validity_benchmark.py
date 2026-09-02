from __future__ import annotations

from .advanced_runtime import AdvancedContextRequest
from .case_record import create_case_record
from .interpretation import InterpretationRequest
from .models import EventContract, LiuYaoCastInput
from .tables import PREDICTION_VALIDITY
from .validity_matrix import (
    VALIDITY_MATRIX_PRODUCTION_ALLOWED,
    ValidityRequest,
    build_validity_matrix,
)


def _interpretation(*, reality_status: str = "unknown") -> InterpretationRequest:
    payload: dict[str, object] = {
        "topic": "general",
        "use_relation": "妻财",
        "primary_position": 4,
        "calendar_context_confirmed": True,
        "calendar_source_refs": ["source:synthetic-calendar"],
        "reality_status": reality_status,
    }
    if reality_status != "unknown":
        payload["reality_facts"] = ["synthetic verified blocker"]
        payload["reality_evidence_refs"] = ["source:synthetic-reality"]
    return InterpretationRequest.from_mapping(payload)


def benchmark_liuyao_validity_matrix() -> dict[str, object]:
    contract = EventContract(
        target_event="synthetic validity event",
        deadline="2099-12-31",
        success_criteria="synthetic criterion",
        evidence_requirement="synthetic evidence",
    )
    cast = LiuYaoCastInput(
        case_id="SYNTHETIC-VALIDITY-MATRIX",
        question="synthetic validity benchmark",
        line_values=(7, 8, 8, 6, 7, 7),
        event_contract=contract,
        completed_at="2026-08-31T21:12:00+08:00",
        location="synthetic",
        month_branch="丑",
        day_ganzhi="甲申",
    )
    record = create_case_record(cast)
    context = AdvancedContextRequest(
        calendar_context_confirmed=True,
        calendar_source_refs=("source:synthetic-calendar",),
    )
    report = build_validity_matrix(
        record,
        ValidityRequest(
            interpretation=_interpretation(),
            advanced_context=context,
        ),
    )
    blocked = build_validity_matrix(
        record,
        ValidityRequest(
            interpretation=_interpretation(reality_status="blocking"),
            advanced_context=context,
        ),
    )
    use_line = next(line for line in report.line_validity if line.position == 4)
    codes = {conflict.code for conflict in report.conflicts}
    checks = {
        "use_selected": report.selected_use_position == 4,
        "moving_use_conditional": use_line.availability == "conditional",
        "month_break": "month_break" in use_line.conditions,
        "void_unresolved": "void_effect_unresolved" in use_line.ambiguous_conditions,
        "combined_conflict": "VOID_AND_MONTH_BREAK" in codes,
        "changed_edge_conditional": any(
            edge.edge_id == "changed:4:4" and edge.edge_status == "conditional"
            for edge in report.influence_edges
        ),
        "reality_block": blocked.matrix_status == "reality_blocked",
        "review_only": report.to_dict()["validity_matrix_status"] == "review_only",
        "not_production": VALIDITY_MATRIX_PRODUCTION_ALLOWED is False,
        "not_prediction": report.to_dict()["prediction_validity"] == PREDICTION_VALIDITY,
        "no_probability": "probability" not in report.to_dict(),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "method_id": report.to_dict()["method_id"],
        "prediction_validity": PREDICTION_VALIDITY,
    }


__all__ = ["benchmark_liuyao_validity_matrix"]
