from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from .errors import RouterError

SUPPORTED_INTENTS = frozenset(
    {
        "full_bazi",
        "career_exam",
        "relationship_reunion",
        "startup",
        "wealth",
        "education",
        "migration",
        "fengshui",
    }
)


@dataclass(frozen=True, slots=True)
class IntentRoute:
    intent: str
    required_fields: tuple[str, ...]
    sections: tuple[str, ...]
    capabilities: tuple[str, ...]
    note: str | None = None


class IntentRouter:
    def __init__(self, routes: Mapping[str, IntentRoute]):
        if set(routes) != SUPPORTED_INTENTS:
            missing = SUPPORTED_INTENTS - set(routes)
            extra = set(routes) - SUPPORTED_INTENTS
            details = []
            if missing:
                details.append(f"缺少意图：{', '.join(sorted(missing))}")
            if extra:
                details.append(f"未知意图：{', '.join(sorted(extra))}")
            raise RouterError("；".join(details))
        self._routes = MappingProxyType(dict(routes))

    @classmethod
    def from_file(cls, path: str | Path) -> "IntentRouter":
        source = Path(path)
        try:
            document = yaml.safe_load(source.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RouterError(f"无法读取路由规范 {source}：{exc}") from exc
        if not isinstance(document, dict) or not isinstance(document.get("intents"), dict):
            raise RouterError("路由规范缺少 intents 对象")
        routes: dict[str, IntentRoute] = {}
        for intent, raw in document["intents"].items():
            if not isinstance(intent, str) or not isinstance(raw, dict):
                raise RouterError("路由意图必须是对象")
            required = _string_list(raw.get("required"), f"{intent}.required")
            agents = _string_list(raw.get("agents"), f"{intent}.agents")
            sections = _string_list(raw.get("sections", []), f"{intent}.sections")
            note = raw.get("note")
            if note is not None and not isinstance(note, str):
                raise RouterError(f"{intent}.note 必须是字符串")
            routes[intent] = IntentRoute(intent, required, sections, agents, note)
        return cls(routes)

    def route(self, intent: str) -> IntentRoute:
        try:
            return self._routes[intent]
        except KeyError as exc:
            raise RouterError(f"不支持的意图：{intent}") from exc


def _string_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise RouterError(f"{name} 必须是非空字符串数组")
    return tuple(value)
