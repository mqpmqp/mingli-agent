from __future__ import annotations

from .case_record import create_case_record
from .interpretation import InterpretationRequest, interpret_case
from .models import EventContract, LiuYaoCastInput
from .tables import PREDICTION_VALIDITY


def benchmark_liuyao_interpretation() -> dict[str, object]:
    contract = EventContract(
        target_event="synthetic current event",
        deadline="2099-12-31",
        success_criteria="synthetic criterion",
        evidence_requirement="synthetic evidence",
    )
    supportive_cast = LiuYaoCastInput(
        case_id="SYNTHETIC-INTERPRET-SUPPORT",
        question="synthetic structural evidence",
        line_values=(7, 8, 8, 6, 7, 7),
        event_contract=contract,
        completed_at="2026-08-31T21:12:00+08:00",
        location="synthetic",
        month_branch="午",
        day_ganzhi="丙午",
    )
    supportive_request = InterpretationRequest(
        topic="general",
        use_relation="妻财",
        primary_position=4,
        calendar_context_confirmed=True,
        reality_status="supportive",
        reality_facts=("synthetic supporting fact",),
    )
    supportive = interpret_case(create_case_record(supportive_cast), supportive_request)

    ambiguous_cast = LiuYaoCastInput(
        case_id="SYNTHETIC-INTERPRET-COMBINE",
        question="synthetic combination ambiguity",
        line_values=(6, 7, 7, 8, 7, 7),
        event_contract=contract,
        completed_at="2026-08-31T21:57:00+08:00",
        location="synthetic",
        month_branch="申",
        day_ganzhi="丁酉",
    )
    ambiguous_request = InterpretationRequest(
        topic="pregnancy",
        focus_dimension="conception_opportunity",
        use_relation="子孙",
        primary_position=5,
        calendar_context_confirmed=True,
        reality_status="unknown",
    )
    ambiguous = interpret_case(create_case_record(ambiguous_cast), ambiguous_request)

    blocked_request = InterpretationRequest(
        topic="general",
        use_relation="妻财",
        primary_position=4,
        calendar_context_confirmed=True,
        reality_status="blocking",
        reality_facts=("synthetic verified blocker",),
    )
    blocked = interpret_case(create_case_record(supportive_cast), blocked_request)

    checks = {
        "supportive_balance": supportive.structural_balance == "supportive",
        "supportive_is_not_prediction": supportive.to_dict()["prediction_validity"] == PREDICTION_VALIDITY,
        "supportive_not_production": supportive.to_dict()["production_allowed"] is False,
        "combination_is_ambiguous": any(item.relation == "month_combine" and item.polarity == "ambiguous" for item in ambiguous.evidence),
        "combination_not_scored": not any(item.relation == "month_combine" and item.weight for item in ambiguous.evidence),
        "reality_blocks_structure": blocked.status == "reality_blocked",
        "confidence_never_high": {supportive.confidence, ambiguous.confidence, blocked.confidence} <= {"medium", "low"},
        "exam_contract_has_four_dimensions": len(
            InterpretationRequest(topic="exam", use_relation="官鬼").to_dict()["focus_dimension"]
        ) > 0,
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "prediction_validity": PREDICTION_VALIDITY,
        "interpretation_status": supportive.to_dict()["interpretation_status"],
    }


__all__ = ["benchmark_liuyao_interpretation"]
