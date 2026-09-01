from __future__ import annotations

from .advanced import (
    ADVANCED_PRODUCTION_ALLOWED,
    ADVANCED_STATIC_TABLE_SHA256,
    build_advanced_structure,
    derive_calendar_context,
    growth_stage,
)
from .case_record import create_case_record
from .interpretation import InterpretationRequest
from .models import EventContract, LiuYaoCastInput
from .tables import PREDICTION_VALIDITY


def benchmark_liuyao_advanced_structure() -> dict[str, object]:
    contract = EventContract(
        target_event="synthetic event",
        deadline="2099-12-31",
        success_criteria="synthetic criterion",
        evidence_requirement="synthetic evidence",
    )
    exam_record = create_case_record(
        LiuYaoCastInput(
            case_id="SYNTHETIC-ADVANCED-EXAM",
            question="synthetic exam event",
            line_values=(7, 8, 8, 6, 7, 7),
            event_contract=contract,
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
        )
    )
    exam = build_advanced_structure(
        exam_record,
        InterpretationRequest(topic="exam", focus_dimension="current_exam", use_relation="官鬼"),
    )

    advance_record = create_case_record(
        LiuYaoCastInput(
            case_id="SYNTHETIC-ADVANCED-JIN-TUI",
            question="synthetic advance-retreat event",
            line_values=(6, 6, 6, 6, 9, 6),
            event_contract=contract,
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
        )
    )
    advance = build_advanced_structure(
        advance_record,
        InterpretationRequest(topic="general", use_relation="父母"),
    )

    fanyin_record = create_case_record(
        LiuYaoCastInput(
            case_id="SYNTHETIC-ADVANCED-FANYIN",
            question="synthetic fan-yin event",
            line_values=(6, 6, 6, 8, 6, 6),
            event_contract=contract,
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
        )
    )
    fanyin = build_advanced_structure(
        fanyin_record,
        InterpretationRequest(topic="general", use_relation="父母"),
    )

    context = derive_calendar_context(exam_record)
    checks = {
        "calendar_month": context.month_branch == "申",
        "calendar_day": context.day_ganzhi == "丁丑",
        "calendar_void": context.void_branches == ("申", "酉"),
        "hidden_spirit": any(item.relation == "官鬼" and item.hidden_position == 3 for item in exam.hidden_spirits),
        "growth_profile": (
            growth_stage("木", "亥") == "长生"
            and growth_stage("火", "寅") == "长生"
            and growth_stage("金", "巳") == "长生"
            and growth_stage("水", "申") == "长生"
            and growth_stage("土", "申") == "长生"
        ),
        "advance_detected": any(item.kind == "advance" for item in advance.advance_retreat),
        "retreat_detected": any(item.kind == "retreat" for item in advance.advance_retreat),
        "fanyin_detected": any(item.kind == "fanyin" for item in fanyin.fan_fu),
        "cross_position_graph": any(
            item.actor_id.startswith("changed:") and item.target_id.startswith("line:")
            for item in advance.relation_graph
        ),
        "spirit_roles_include_enemy": any(item.role == "仇神候选" for item in advance.spirit_roles),
        "ranking_is_not_confirmation": exam.ranking_status == "hidden_leader_requires_confirmation",
        "review_only": exam.to_dict()["interpretation_status"] == "review_only",
        "not_production": ADVANCED_PRODUCTION_ALLOWED is False and exam.to_dict()["production_allowed"] is False,
        "not_prediction": exam.to_dict()["prediction_validity"] == PREDICTION_VALIDITY,
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "advanced_static_table_sha256": ADVANCED_STATIC_TABLE_SHA256,
        "prediction_validity": PREDICTION_VALIDITY,
        "production_allowed": ADVANCED_PRODUCTION_ALLOWED,
    }


__all__ = ["benchmark_liuyao_advanced_structure"]
