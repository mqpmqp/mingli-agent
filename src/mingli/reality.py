from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RealityOverride:
    code: str
    message: str
    confidence: str = "high"


def _contains(value: object, candidates: set[str]) -> bool:
    if isinstance(value, str):
        return value in candidates
    if isinstance(value, Sequence):
        return any(isinstance(item, str) and item in candidates for item in value)
    return False


def apply_reality_overrides(
    intent: str,
    facts: Mapping[str, object],
    chart_signals: Sequence[str] = (),
) -> tuple[RealityOverride, ...]:
    """返回现实硬条件校正；不修改输入，也不生成盘面事实。"""
    overrides: list[RealityOverride] = []
    signals = " ".join(item for item in chart_signals if isinstance(item, str))

    if facts.get("relationship_status") == "married" and "桃花" in signals:
        overrides.append(
            RealityOverride(
                "married_taohua",
                "已婚状态下，桃花信号优先解释为社交、合作或关系互动，不能直接推断出轨。",
            )
        )

    if intent == "relationship_reunion":
        if facts.get("other_party_status") == "married":
            overrides.append(RealityOverride("other_party_married", "对方已婚，复联、复合与稳定判断均须降低，并尊重婚姻边界。"))
        if facts.get("contact_status") == "blocked":
            overrides.append(RealityOverride("blocked", "对方已拉黑；除非对方主动解除边界，不建议推动联系。"))
        duration = facts.get("no_contact_months", facts.get("no_contact_duration_months", 0))
        if isinstance(duration, (int, float)) and duration >= 12:
            overrides.append(RealityOverride("long_no_contact", "长期失联显著降低复联、复合与稳定的现实可行性。"))

    if facts.get("career_status") == "unemployed":
        overrides.append(RealityOverride("unemployed", "当前失业，事业主题应解释为求职、资格要求与责任重建，不能写成升职。"))

    if intent == "career_exam" and (facts.get("major_eligible") is False or facts.get("major_not_eligible") is True):
        overrides.append(RealityOverride("major_ineligible", "专业不符合属于岗位硬限制，该岗位当前不可行。"))

    validation = facts.get("customer_validation", facts.get("product_or_customer_validation"))
    runway = facts.get("cash_runway_months")
    low_resources = facts.get("capital_level") == "low" or (
        isinstance(runway, (int, float)) and runway <= 2
    )
    if intent == "startup" and low_resources and validation is not True:
        overrides.append(RealityOverride("low_cost_validation", "资本与客户验证不足，只适合先做副业或低成本客户验证，不宜重投入。"))

    symptoms = facts.get("symptoms", facts.get("symptom"))
    urgent_symptoms = {"持续胸痛", "persistent_chest_pain", "high_fever", "difficulty_breathing"}
    if intent == "health" and _contains(symptoms, urgent_symptoms):
        overrides.append(RealityOverride("urgent_medical", "持续胸痛或其他急症信号应优先及时接受医疗评估，命理不能诊断疾病。"))

    leveraged = facts.get("contract_leverage") is True or facts.get("financial_risk") == "high"
    if intent in {"investment", "wealth"} and leveraged:
        overrides.append(RealityOverride("leverage_risk", "命理不能决定合约重仓或杠杆；仓位、止损与可承受损失必须由现实风控决定。"))

    return tuple(overrides)
