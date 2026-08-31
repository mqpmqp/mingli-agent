from __future__ import annotations

from .chart import build_liuyao_chart
from .models import EventContract, LiuYaoCastInput
from .tables import HEXAGRAM_NAMES, METHOD_ID, PALACE_SEQUENCES, PREDICTION_VALIDITY

def benchmark_liuyao() -> dict[str, object]:
    contract = EventContract(
        target_event="synthetic event",
        deadline="2099-12-31",
        success_criteria="synthetic criterion",
        evidence_requirement="synthetic evidence",
    )
    wind = LiuYaoCastInput(
        case_id="SYNTHETIC-WIND",
        question="synthetic wind case",
        line_values=(6, 7, 7, 8, 7, 7),
        event_contract=contract,
        completed_at="2026-08-31T21:57:00+08:00",
        location="synthetic",
    )
    benefit = LiuYaoCastInput(
        case_id="SYNTHETIC-BENEFIT",
        question="synthetic benefit case",
        line_values=(7, 8, 8, 6, 7, 7),
        event_contract=contract,
        completed_at="2026-08-31T21:12:00+08:00",
        location="synthetic",
    )
    wind_chart = build_liuyao_chart(wind)
    benefit_chart = build_liuyao_chart(benefit)
    checks = {
        "static_hexagrams": len(HEXAGRAM_NAMES) == 64,
        "static_palaces": len({name for values in PALACE_SEQUENCES.values() for name in values}) == 64,
        "wind_original": wind_chart.original.name == "巽为风",
        "wind_changed": wind_chart.changed.name == "风天小畜",
        "wind_moving": wind_chart.moving_lines == (1,),
        "benefit_original": benefit_chart.original.name == "风雷益",
        "benefit_changed": benefit_chart.changed.name == "天雷无妄",
        "benefit_moving": benefit_chart.moving_lines == (4,),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "method_id": METHOD_ID,
        "prediction_validity": PREDICTION_VALIDITY,
    }
