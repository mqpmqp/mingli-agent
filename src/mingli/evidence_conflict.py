from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


PRIORITY = {
    "single_traditional_claim": 10,
    "multi_case_observation": 20,
    "user_confirmed_event": 30,
    "reality_fact": 40,
}


@dataclass(frozen=True, slots=True)
class ConflictResolution:
    status: str
    priority_class: str
    accepted_ids: tuple[str, ...]
    overridden_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]


def resolve_evidence(records: Sequence[Mapping[str, object]]) -> ConflictResolution:
    """按证据层级解决同一主张的冲突；不生成或扩大任何预测。"""
    if not records:
        raise ValueError("至少需要一条 evidence")
    claims = {item.get("claim") for item in records}
    if len(claims) != 1 or None in claims:
        raise ValueError("所有 evidence 必须针对同一非空 claim")
    for item in records:
        if item.get("priority_class") not in PRIORITY:
            raise ValueError(f"未知 evidence priority：{item.get('priority_class')}")
        if item.get("polarity") not in {"support", "contradict"}:
            raise ValueError(f"未知 evidence polarity：{item.get('polarity')}")
        if not isinstance(item.get("id"), str):
            raise ValueError("evidence id 必须是字符串")

    highest = max(PRIORITY[str(item["priority_class"])] for item in records)
    decisive = [item for item in records if PRIORITY[str(item["priority_class"])] == highest]
    priority_class = str(decisive[0]["priority_class"])
    polarities = {item["polarity"] for item in decisive}
    decisive_ids = tuple(sorted(str(item["id"]) for item in decisive))
    lower_ids = tuple(
        sorted(
            str(item["id"])
            for item in records
            if PRIORITY[str(item["priority_class"])] < highest
        )
    )
    if len(polarities) > 1:
        return ConflictResolution("unresolved", priority_class, (), lower_ids, decisive_ids)
    return ConflictResolution("resolved", priority_class, decisive_ids, lower_ids, ())
