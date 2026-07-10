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
    hard_override_direction: str | None = None


def fuse_evidence(items: Iterable[Evidence]) -> FusionResult:
    """按固定来源权重汇总证据；已核验现实硬事实可覆盖普通证据。"""
    evidence = tuple(items)
    if any(not isinstance(item, Evidence) for item in evidence):
        raise TypeError("items 只能包含 Evidence")

    verified_reality = tuple(
        item for item in evidence if item.source_type == "reality" and item.verified
    )
    reality_directions = {item.direction for item in verified_reality}
    hard_override_direction = (
        next(iter(reality_directions)) if len(reality_directions) == 1 else None
    )

    support_score = 0.0
    contradict_score = 0.0
    for item in evidence:
        effective_weight = float(item.weight) * SOURCE_MULTIPLIERS[item.source_type]
        if item.direction == "support":
            support_score += effective_weight
        else:
            contradict_score += effective_weight

    if hard_override_direction == "support":
        contradict_score = 0.0
        support_score = max(support_score, 1.0)
    elif hard_override_direction == "contradict":
        support_score = 0.0
        contradict_score = max(contradict_score, 1.0)

    return FusionResult(
        support_score=round(support_score, 4),
        contradict_score=round(contradict_score, 4),
        has_conflict=support_score > 0 and contradict_score > 0,
        evidence_count=len(evidence),
        hard_override_direction=hard_override_direction,
    )
