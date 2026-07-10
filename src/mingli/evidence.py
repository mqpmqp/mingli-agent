from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Evidence

SOURCE_MULTIPLIERS = {
    "reality": 1.0,
    "chart": 1.0,
    "timing": 0.9,
    "rule": 0.8,
    "case": 0.7,
}


@dataclass(frozen=True, slots=True)
class FusionResult:
    support_score: float
    contradict_score: float
    has_conflict: bool
    evidence_count: int


def fuse_evidence(items: Iterable[Evidence]) -> FusionResult:
    """按固定来源权重汇总证据，不从分数推导新的命理事实。"""
    support_score = 0.0
    contradict_score = 0.0
    evidence_count = 0
    for item in items:
        if not isinstance(item, Evidence):
            raise TypeError("items 只能包含 Evidence")
        multiplier = SOURCE_MULTIPLIERS[item.source_type]
        effective_weight = float(item.weight) * multiplier
        if item.source_type == "reality" and item.verified:
            # Schema 中普通证据最高为 10；额外基数确保已核验现实硬事实优先。
            effective_weight += 11.0
        if item.direction == "support":
            support_score += effective_weight
        else:
            contradict_score += effective_weight
        evidence_count += 1
    return FusionResult(
        support_score=round(support_score, 4),
        contradict_score=round(contradict_score, 4),
        has_conflict=support_score > 0 and contradict_score > 0,
        evidence_count=evidence_count,
    )
