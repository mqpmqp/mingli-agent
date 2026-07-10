from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Mapping

from .errors import ModelValidationError

CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})
RULE_STATUSES = frozenset({"draft", "reviewed", "verified", "deprecated"})
SOURCE_TYPES = frozenset({"chart", "timing", "rule", "case", "reality"})
DIRECTIONS = frozenset({"support", "contradict"})


def _require_non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelValidationError(f"{field_name} 必须是非空字符串")
    return value


def _require_enum(value: object, allowed: frozenset[str], field_name: str) -> str:
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ModelValidationError(f"{field_name} 必须是以下值之一：{choices}")
    return str(value)


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ModelValidationError(f"{field_name} 必须是字符串数组")
    result = tuple(value)
    if any(not isinstance(item, str) for item in result):
        raise ModelValidationError(f"{field_name} 只能包含字符串")
    return result


@dataclass(frozen=True, slots=True)
class ChartInput:
    gender: str
    calendar: str
    birth_date: str
    birth_time: str
    birth_location: Mapping[str, object]
    timezone: str = "+08:00"
    solar_time_adjustment: bool = False
    source: str = "user"

    def __post_init__(self) -> None:
        _require_enum(self.gender, frozenset({"male", "female"}), "gender")
        _require_enum(self.calendar, frozenset({"solar", "lunar"}), "calendar")
        try:
            date.fromisoformat(self.birth_date)
        except (TypeError, ValueError) as exc:
            raise ModelValidationError("birth_date 必须是 YYYY-MM-DD 格式的有效日期") from exc
        if not isinstance(self.birth_time, str) or re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", self.birth_time) is None:
            raise ModelValidationError("birth_time 必须是 HH:MM 格式的有效时间")
        if not isinstance(self.birth_location, Mapping):
            raise ModelValidationError("birth_location 必须是对象")
        location = dict(self.birth_location)
        allowed = {"country", "province", "city", "longitude", "latitude"}
        unknown = set(location) - allowed
        if unknown:
            raise ModelValidationError(f"birth_location 含未知字段：{', '.join(sorted(unknown))}")
        _require_non_empty(location.get("country"), "birth_location.country")
        _require_non_empty(location.get("city"), "birth_location.city")
        for key, lower, upper in (("longitude", -180, 180), ("latitude", -90, 90)):
            if key in location:
                number = location[key]
                if isinstance(number, bool) or not isinstance(number, (int, float)) or not lower <= number <= upper:
                    raise ModelValidationError(f"birth_location.{key} 超出允许范围")
        _require_non_empty(self.timezone, "timezone")
        if not isinstance(self.solar_time_adjustment, bool):
            raise ModelValidationError("solar_time_adjustment 必须是布尔值")
        _require_enum(self.source, frozenset({"user", "image_confirmed", "external_calculator"}), "source")
        object.__setattr__(self, "birth_location", MappingProxyType(location))


@dataclass(frozen=True, slots=True)
class RealityContext:
    relationship_status: str = "unknown"
    contact_status: str = "unknown"
    career_status: str = "unknown"
    education: str | None = None
    major: str | None = None
    income_stability: str = "unknown"
    capital_level: str = "unknown"
    major_events: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_enum(
            self.relationship_status,
            frozenset({"single", "dating", "married", "divorced", "unknown"}),
            "relationship_status",
        )
        _require_enum(
            self.contact_status,
            frozenset({"active", "low_contact", "no_contact", "blocked", "unknown"}),
            "contact_status",
        )
        _require_enum(
            self.career_status,
            frozenset({"employed", "unemployed", "student", "entrepreneur", "transition", "unknown"}),
            "career_status",
        )
        _require_enum(self.income_stability, frozenset({"stable", "unstable", "none", "unknown"}), "income_stability")
        _require_enum(self.capital_level, frozenset({"low", "medium", "high", "unknown"}), "capital_level")
        for field_name in ("education", "major"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, str):
                raise ModelValidationError(f"{field_name} 必须是字符串或 null")
        object.__setattr__(self, "major_events", _string_tuple(self.major_events, "major_events"))
        object.__setattr__(self, "constraints", _string_tuple(self.constraints, "constraints"))


@dataclass(frozen=True, slots=True)
class Evidence:
    source_type: str
    detail: str
    direction: str
    weight: float
    source_id: str | None = None
    verified: bool = False

    def __post_init__(self) -> None:
        _require_enum(self.source_type, SOURCE_TYPES, "source_type")
        _require_non_empty(self.detail, "detail")
        _require_enum(self.direction, DIRECTIONS, "direction")
        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)) or not 0 <= self.weight <= 10:
            raise ModelValidationError("weight 必须是 0 到 10 的数字")
        if self.source_id is not None and not isinstance(self.source_id, str):
            raise ModelValidationError("source_id 必须是字符串或 null")
        if not isinstance(self.verified, bool):
            raise ModelValidationError("verified 必须是布尔值")


@dataclass(frozen=True, slots=True)
class Judgement:
    claim: str
    confidence: str
    evidence: tuple[Evidence, ...]
    plain_language: str
    reality_dependencies: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.claim, "claim")
        _require_enum(self.confidence, CONFIDENCE_LEVELS, "confidence")
        evidence = tuple(self.evidence)
        if any(not isinstance(item, Evidence) for item in evidence):
            raise ModelValidationError("evidence 只能包含 Evidence")
        object.__setattr__(self, "evidence", evidence)
        _require_non_empty(self.plain_language, "plain_language")
        for field_name in ("reality_dependencies", "risks", "recommended_actions"):
            object.__setattr__(self, field_name, _string_tuple(getattr(self, field_name), field_name))


@dataclass(frozen=True, slots=True)
class DecisionOption:
    name: str
    advantages: tuple[str, ...]
    risks: tuple[str, ...]
    reality_prerequisites: tuple[str, ...]
    fit: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
        for field_name in ("advantages", "risks", "reality_prerequisites"):
            object.__setattr__(self, field_name, _string_tuple(getattr(self, field_name), field_name))
        if self.fit is not None:
            _require_enum(self.fit, CONFIDENCE_LEVELS, "fit")


@dataclass(frozen=True, slots=True)
class DecisionReport:
    decision: str
    confidence: str
    options: tuple[DecisionOption, ...]
    recommended_action: str
    minimum_reversible_step: str | None = None
    professional_advice_required: bool = False

    def __post_init__(self) -> None:
        _require_non_empty(self.decision, "decision")
        _require_enum(self.confidence, CONFIDENCE_LEVELS, "confidence")
        options = tuple(self.options)
        if len(options) < 2 or any(not isinstance(item, DecisionOption) for item in options):
            raise ModelValidationError("options 至少需要两个 DecisionOption")
        object.__setattr__(self, "options", options)
        _require_non_empty(self.recommended_action, "recommended_action")
        if self.minimum_reversible_step is not None:
            _require_non_empty(self.minimum_reversible_step, "minimum_reversible_step")
        if not isinstance(self.professional_advice_required, bool):
            raise ModelValidationError("professional_advice_required 必须是布尔值")


@dataclass(frozen=True, slots=True)
class RuleCard:
    id: str
    domain: str
    trigger: tuple[str, ...]
    judgement: str
    plain_language: str
    confidence: str
    status: str
    support: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    priority: int = 1
    source: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "id")
        _require_non_empty(self.domain, "domain")
        object.__setattr__(self, "trigger", _string_tuple(self.trigger, "trigger"))
        object.__setattr__(self, "support", _string_tuple(self.support, "support"))
        object.__setattr__(self, "exclude", _string_tuple(self.exclude, "exclude"))
        _require_non_empty(self.judgement, "judgement")
        _require_non_empty(self.plain_language, "plain_language")
        _require_enum(self.confidence, CONFIDENCE_LEVELS, "confidence")
        _require_enum(self.status, RULE_STATUSES, "status")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int) or not 1 <= self.priority <= 100:
            raise ModelValidationError("priority 必须是 1 到 100 的整数")
        if self.source is not None:
            _require_non_empty(self.source, "source")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuleCard":
        allowed = {
            "id",
            "domain",
            "trigger",
            "support",
            "exclude",
            "judgement",
            "plain_language",
            "confidence",
            "priority",
            "source",
            "status",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ModelValidationError(f"规则含未知字段：{', '.join(sorted(unknown))}")
        required = {"id", "domain", "trigger", "judgement", "plain_language", "confidence", "status"}
        missing = required - set(value)
        if missing:
            raise ModelValidationError(f"规则缺少字段：{', '.join(sorted(missing))}")
        return cls(
            id=value["id"],
            domain=value["domain"],
            trigger=tuple(value["trigger"]) if isinstance(value["trigger"], list) else value["trigger"],
            support=tuple(value.get("support", ())) if isinstance(value.get("support", ()), list) else value.get("support", ()),
            exclude=tuple(value.get("exclude", ())) if isinstance(value.get("exclude", ()), list) else value.get("exclude", ()),
            judgement=value["judgement"],
            plain_language=value["plain_language"],
            confidence=value["confidence"],
            priority=value.get("priority", 1),
            source=value.get("source"),
            status=value["status"],
        )
