from __future__ import annotations

from .advanced_facts import (
    ADVANCED_FACT_PRODUCTION_ALLOWED,
    build_advanced_fact_report,
    classify_progression,
    growth_stage,
)
from .case_record import create_case_record
from .models import EventContract, LiuYaoCastInput
from .tables import PREDICTION_VALIDITY


def benchmark_liuyao_advanced_facts() -> dict[str, object]:
    contract = EventContract(
        target_event="synthetic advanced fact event",
        deadline="2099-12-31",
        success_criteria="synthetic criterion",
        evidence_requirement="synthetic evidence",
    )
    cast = LiuYaoCastInput(
        case_id="SYNTHETIC-ADVANCED-FACTS",
        question="synthetic advanced fact benchmark",
        line_values=(7, 8, 8, 6, 7, 7),
        event_contract=contract,
        completed_at="2026-08-31T21:12:00+08:00",
        location="synthetic",
        month_branch="亥",
        day_ganzhi="甲申",
    )
    report = build_advanced_fact_report(create_case_record(cast))
    hidden = [fact for fact in report.facts if fact.category == "hidden_spirit"]
    checks = {
        "missing_officer": report.missing_relations == ("官鬼",),
        "hidden_officer_position": any(
            fact.positions == (3,) and fact.branches[0] == "酉" for fact in hidden
        ),
        "wood_birth": growth_stage("木", "亥") == "长生",
        "wood_tomb": growth_stage("木", "未") == "墓",
        "wood_absolute": growth_stage("木", "申") == "绝",
        "advance": classify_progression("寅", "卯") == "advance",
        "retreat": classify_progression("卯", "寅") == "retreat",
        "review_only": report.to_dict()["advanced_fact_status"] == "review_only",
        "not_production": ADVANCED_FACT_PRODUCTION_ALLOWED is False,
        "not_prediction": report.to_dict()["prediction_validity"] == PREDICTION_VALIDITY,
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "method_id": report.to_dict()["method_id"],
        "prediction_validity": PREDICTION_VALIDITY,
    }


__all__ = ["benchmark_liuyao_advanced_facts"]
