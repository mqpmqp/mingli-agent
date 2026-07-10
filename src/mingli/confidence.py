from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Evidence


@dataclass(frozen=True, slots=True)
class ConfidenceDecision:
    level: str
    rationale: str
    scope: str = "命理辅助判断"


def evaluate_confidence(
    items: Iterable[Evidence],
    *,
    missing_information: bool = False,
    image_unconfirmed: bool = False,
    single_symbol: bool = False,
    high_stakes: str | None = None,
) -> ConfidenceDecision:
    evidence = tuple(items)
    if missing_information or image_unconfirmed or single_symbol:
        return ConfidenceDecision("low", "信息缺失、图片盘未确认或只有单一象意。")

    supports = tuple(item for item in evidence if item.direction == "support")
    contradictions = tuple(item for item in evidence if item.direction == "contradict")
    verified_reality = any(item.source_type == "reality" and item.verified for item in supports)

    if supports and contradictions:
        return ConfidenceDecision("medium", "存在多项支持，同时也有反证。")
    if len(supports) >= 2 and verified_reality:
        scope = "现实处置" if high_stakes in {"medical", "investment"} else "命理辅助判断"
        rationale = "现实硬事实与多项证据一致。"
        if scope == "现实处置":
            rationale += "高置信仅针对现实处置，不代表命理预测。"
        return ConfidenceDecision("high", rationale, scope)
    if len(supports) >= 2:
        return ConfidenceDecision("medium", "有多项支持，但缺少已核验的现实硬事实。")
    return ConfidenceDecision("low", "证据不足，不能形成高置信判断。")
