from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .errors import ModelValidationError, RuleValidationError
from .models import RULE_STATUSES, RuleCard

PRODUCTION_STATUSES = frozenset({"reviewed", "verified"})


def load_rules(
    root: str | Path,
    *,
    statuses: Iterable[str] | None = None,
) -> tuple[RuleCard, ...]:
    source_root = Path(root).resolve()
    if not source_root.is_dir():
        raise RuleValidationError([f"规则目录不存在或不是目录：{source_root}"])
    selected_statuses = frozenset(PRODUCTION_STATUSES if statuses is None else statuses)
    unknown_statuses = selected_statuses - RULE_STATUSES
    if unknown_statuses:
        raise RuleValidationError([f"未知规则状态：{', '.join(sorted(unknown_statuses))}"])

    issues: list[str] = []
    loaded: list[RuleCard] = []
    locations: dict[str, list[str]] = {}
    for path in sorted(source_root.rglob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            issues.append(f"{path}:1: 无法读取 UTF-8 规则文件：{exc}")
            continue
        for line_no, line in enumerate(lines, 1):
            if not line.strip():
                continue
            location = f"{path.relative_to(source_root).as_posix()}:{line_no}"
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                issues.append(f"{location}: JSONL 解析失败（列 {exc.colno}）：{exc.msg}")
                continue
            if not isinstance(value, dict):
                issues.append(f"{location}: 规则必须是 JSON 对象")
                continue
            rule_id = value.get("id")
            if isinstance(rule_id, str):
                locations.setdefault(rule_id, []).append(location)
            try:
                loaded.append(RuleCard.from_mapping(value))
            except (ModelValidationError, TypeError) as exc:
                issues.append(f"{location}: {exc}")

    for rule_id, rule_locations in locations.items():
        if len(rule_locations) > 1:
            issues.append(f"重复规则 ID {rule_id}：{', '.join(rule_locations)}")
    if issues:
        raise RuleValidationError(issues)

    filtered = (item for item in loaded if item.status in selected_statuses)
    return tuple(sorted(filtered, key=lambda item: (item.domain != "reality", -item.priority, item.id)))
