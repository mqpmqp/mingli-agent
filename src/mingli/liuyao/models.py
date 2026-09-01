from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

from .tables import COIN_CONVENTION, INPUT_ORDER, METHOD_ID, PREDICTION_VALIDITY, STATIC_TABLE_SHA256, digest
from .validation import (
    LiuYaoError, _aware_datetime, _iso_date, _non_empty, _normalize_casting_mode,
    _normalize_convention, _normalize_day_ganzhi, _normalize_month_branch,
    _reject_unknown, _require_mapping, _string_tuple, normalize_line_values,
)

_digest = digest

@dataclass(frozen=True, slots=True)
class EventContract:
    target_event: str
    deadline: str
    success_criteria: str
    evidence_requirement: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_event", _non_empty(self.target_event, "event_contract.target_event"))
        object.__setattr__(self, "deadline", _iso_date(self.deadline, "event_contract.deadline"))
        object.__setattr__(self, "success_criteria", _non_empty(self.success_criteria, "event_contract.success_criteria"))
        object.__setattr__(self, "evidence_requirement", _non_empty(self.evidence_requirement, "event_contract.evidence_requirement"))

    def to_dict(self) -> dict[str, object]:
        return {
            "target_event": self.target_event,
            "deadline": self.deadline,
            "success_criteria": self.success_criteria,
            "evidence_requirement": self.evidence_requirement,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EventContract":
        allowed = {"target_event", "deadline", "success_criteria", "evidence_requirement"}
        _reject_unknown(value, allowed, "event_contract")
        missing = allowed - set(value)
        if missing:
            raise LiuYaoError("INVALID_INPUT", f"event_contract 缺少字段：{', '.join(sorted(missing))}")
        return cls(
            target_event=value["target_event"],
            deadline=value["deadline"],
            success_criteria=value["success_criteria"],
            evidence_requirement=value["evidence_requirement"],
        )


@dataclass(frozen=True, slots=True)
class LiuYaoCastInput:
    case_id: str
    question: str
    line_values: tuple[int, ...]
    event_contract: EventContract
    completed_at: str
    location: str
    casting_mode: str = "self"
    proxy_relationship: str | None = None
    coin_convention: str = COIN_CONVENTION
    month_branch: str | None = None
    day_ganzhi: str | None = None
    reality_facts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        case_id = _non_empty(self.case_id, "case_id")
        if re.fullmatch(r"[A-Za-z0-9._-]+", case_id) is None:
            raise LiuYaoError("INVALID_INPUT", "case_id 只能包含英文字母、数字、点、下划线和短横线")
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "question", _non_empty(self.question, "question"))
        object.__setattr__(self, "line_values", normalize_line_values(self.line_values))
        if not isinstance(self.event_contract, EventContract):
            raise LiuYaoError("INVALID_INPUT", "event_contract 必须是 EventContract")
        object.__setattr__(self, "completed_at", _aware_datetime(self.completed_at, "completed_at"))
        if date.fromisoformat(self.event_contract.deadline) < datetime.fromisoformat(self.completed_at).date():
            raise LiuYaoError("INVALID_INPUT", "event_contract.deadline 不能早于 completed_at 的当地日期")
        object.__setattr__(self, "location", _non_empty(self.location, "location"))
        mode = _normalize_casting_mode(self.casting_mode)
        object.__setattr__(self, "casting_mode", mode)
        if mode == "proxy":
            object.__setattr__(self, "proxy_relationship", _non_empty(self.proxy_relationship, "proxy_relationship"))
        elif self.proxy_relationship is not None:
            raise LiuYaoError("INVALID_INPUT", "本人摇卦时 proxy_relationship 必须为空")
        object.__setattr__(self, "coin_convention", _normalize_convention(self.coin_convention))
        object.__setattr__(self, "month_branch", _normalize_month_branch(self.month_branch))
        object.__setattr__(self, "day_ganzhi", _normalize_day_ganzhi(self.day_ganzhi))
        object.__setattr__(self, "reality_facts", _string_tuple(self.reality_facts, "reality_facts"))

    @property
    def canonical_sha256(self) -> str:
        return _digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "case_id": self.case_id,
            "question": self.question,
            "line_values": list(self.line_values),
            "event_contract": self.event_contract.to_dict(),
            "completed_at": self.completed_at,
            "location": self.location,
            "casting_mode": self.casting_mode,
            "proxy_relationship": self.proxy_relationship,
            "coin_convention": self.coin_convention,
            "month_branch": self.month_branch,
            "day_ganzhi": self.day_ganzhi,
            "reality_facts": list(self.reality_facts),
            "input_order": INPUT_ORDER,
        }
        if include_hash:
            payload["canonical_sha256"] = _digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LiuYaoCastInput":
        allowed = {
            "case_id", "question", "line_values", "event_contract", "completed_at", "location",
            "casting_mode", "proxy_relationship", "coin_convention", "month_branch", "day_ganzhi",
            "reality_facts", "input_order", "canonical_sha256",
        }
        _reject_unknown(value, allowed, "cast")
        required = {"case_id", "question", "line_values", "event_contract", "completed_at", "location"}
        missing = required - set(value)
        if missing:
            raise LiuYaoError("INVALID_INPUT", f"cast 缺少字段：{', '.join(sorted(missing))}")
        if value.get("input_order", INPUT_ORDER) != INPUT_ORDER:
            raise LiuYaoError("INVALID_INPUT", "input_order 必须是 bottom_to_top（初爻到上爻）")
        cast = cls(
            case_id=value["case_id"],
            question=value["question"],
            line_values=normalize_line_values(value["line_values"]),
            event_contract=EventContract.from_mapping(_require_mapping(value["event_contract"], "event_contract")),
            completed_at=value["completed_at"],
            location=value["location"],
            casting_mode=value.get("casting_mode", "self"),
            proxy_relationship=value.get("proxy_relationship"),
            coin_convention=value.get("coin_convention", COIN_CONVENTION),
            month_branch=value.get("month_branch"),
            day_ganzhi=value.get("day_ganzhi"),
            reality_facts=_string_tuple(value.get("reality_facts", ()), "reality_facts"),
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != cast.canonical_sha256:
            raise LiuYaoError("RECORD_TAMPERED", "cast canonical_sha256 与重算结果不一致")
        return cast


@dataclass(frozen=True, slots=True)
class HexagramIdentity:
    name: str
    upper_trigram: str
    lower_trigram: str
    palace: str
    palace_element: str
    palace_stage: str
    shi_line: int
    ying_line: int

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "upper_trigram": self.upper_trigram,
            "lower_trigram": self.lower_trigram,
            "palace": self.palace,
            "palace_element": self.palace_element,
            "palace_stage": self.palace_stage,
            "shi_line": self.shi_line,
            "ying_line": self.ying_line,
        }


@dataclass(frozen=True, slots=True)
class LiuYaoLine:
    position: int
    value: int
    line_type: str
    yin_yang: str
    moving: bool
    changed_yin_yang: str
    najia_stem: str
    najia_branch: str
    element: str
    six_relation: str
    six_spirit: str | None
    is_void: bool | None
    changed_najia_stem: str | None
    changed_najia_branch: str | None
    changed_element: str | None
    changed_six_relation: str | None
    changed_is_void: bool | None

    def to_dict(self) -> dict[str, object]:
        return {
            "position": self.position,
            "value": self.value,
            "line_type": self.line_type,
            "yin_yang": self.yin_yang,
            "moving": self.moving,
            "changed_yin_yang": self.changed_yin_yang,
            "najia": self.najia_stem + self.najia_branch,
            "element": self.element,
            "six_relation": self.six_relation,
            "six_spirit": self.six_spirit,
            "is_void": self.is_void,
            "changed_najia": None if self.changed_najia_stem is None else self.changed_najia_stem + str(self.changed_najia_branch),
            "changed_element": self.changed_element,
            "changed_six_relation": self.changed_six_relation,
            "changed_is_void": self.changed_is_void,
        }


@dataclass(frozen=True, slots=True)
class LiuYaoChart:
    original: HexagramIdentity
    changed: HexagramIdentity
    lines: tuple[LiuYaoLine, ...]
    moving_lines: tuple[int, ...]
    void_branches: tuple[str, str] | None
    month_branch: str | None
    day_ganzhi: str | None
    input_sha256: str

    @property
    def canonical_sha256(self) -> str:
        return _digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "method_id": METHOD_ID,
            "static_table_sha256": STATIC_TABLE_SHA256,
            "prediction_validity": PREDICTION_VALIDITY,
            "input_order": INPUT_ORDER,
            "line_values": [line.value for line in self.lines],
            "calendar_context": {"month_branch": self.month_branch, "day_ganzhi": self.day_ganzhi},
            "original": self.original.to_dict(),
            "changed": self.changed.to_dict(),
            "moving_lines": list(self.moving_lines),
            "void_branches": None if self.void_branches is None else list(self.void_branches),
            "lines": [line.to_dict() for line in self.lines],
            "input_sha256": self.input_sha256,
        }
        if include_hash:
            payload["canonical_sha256"] = _digest(payload)
        return payload
