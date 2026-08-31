from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from .tables import CONFIDENCE_LEVELS, PREDICTION_STATUSES, PREDICTION_VALIDITY, SETTLEMENT_OUTCOMES
from .validation import LiuYaoError, _aware_datetime, _non_empty, _reject_unknown, _string_tuple

@dataclass(frozen=True, slots=True)
class PredictionVersion:
    version_id: str
    created_at: str
    status: str
    conclusion: str
    confidence: str
    published_at: str | None = None
    probability_range: tuple[int, int] | None = None
    time_windows: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    falsifiers: tuple[str, ...] = ()
    invalid_reason: str | None = None
    invalidated_at: str | None = None

    def __post_init__(self) -> None:
        version_id = _non_empty(self.version_id, "version_id")
        if re.fullmatch(r"[A-Za-z0-9._-]+", version_id) is None:
            raise LiuYaoError("INVALID_INPUT", "version_id 只能包含英文字母、数字、点、下划线和短横线")
        object.__setattr__(self, "version_id", version_id)
        object.__setattr__(self, "created_at", _aware_datetime(self.created_at, "created_at"))
        if self.status not in PREDICTION_STATUSES:
            raise LiuYaoError("INVALID_INPUT", f"status 必须是：{', '.join(sorted(PREDICTION_STATUSES))}")
        object.__setattr__(self, "conclusion", _non_empty(self.conclusion, "conclusion"))
        if self.confidence not in CONFIDENCE_LEVELS:
            raise LiuYaoError("INVALID_INPUT", "confidence 必须是 high、medium 或 low")
        if self.status in {"pending", "settled"}:
            object.__setattr__(self, "published_at", _aware_datetime(self.published_at, "published_at"))
            if datetime.fromisoformat(self.published_at) < datetime.fromisoformat(self.created_at):
                raise LiuYaoError("INVALID_TRANSITION", "published_at 不能早于 created_at")
        elif self.status == "draft" and self.published_at is not None:
            raise LiuYaoError("INVALID_INPUT", "draft 版本不能填写 published_at")
        elif self.published_at is not None:
            object.__setattr__(self, "published_at", _aware_datetime(self.published_at, "published_at"))
            if datetime.fromisoformat(self.published_at) < datetime.fromisoformat(self.created_at):
                raise LiuYaoError("INVALID_TRANSITION", "published_at 不能早于 created_at")
        if self.probability_range is not None:
            if (
                not isinstance(self.probability_range, Sequence)
                or isinstance(self.probability_range, (str, bytes))
                or len(self.probability_range) != 2
            ):
                raise LiuYaoError("INVALID_INPUT", "probability_range 必须是两个整数")
            low, high = self.probability_range
            if any(isinstance(item, bool) or not isinstance(item, int) for item in (low, high)) or not 0 <= low <= high <= 100:
                raise LiuYaoError("INVALID_INPUT", "probability_range 必须满足 0 <= low <= high <= 100")
            object.__setattr__(self, "probability_range", (low, high))
        for field_name in ("time_windows", "conditions", "falsifiers"):
            object.__setattr__(self, field_name, _string_tuple(getattr(self, field_name), field_name))
        if self.status == "invalid":
            object.__setattr__(self, "invalid_reason", _non_empty(self.invalid_reason, "invalid_reason"))
            object.__setattr__(self, "invalidated_at", _aware_datetime(self.invalidated_at, "invalidated_at"))
            earliest = self.published_at or self.created_at
            if datetime.fromisoformat(self.invalidated_at) < datetime.fromisoformat(earliest):
                boundary = "published_at" if self.published_at is not None else "created_at"
                raise LiuYaoError("INVALID_TRANSITION", f"invalidated_at 不能早于 {boundary}")
        elif self.invalid_reason is not None or self.invalidated_at is not None:
            raise LiuYaoError("INVALID_INPUT", "只有 invalid 版本可以填写 invalid_reason/invalidated_at")

    def to_dict(self) -> dict[str, object]:
        return {
            "version_id": self.version_id,
            "created_at": self.created_at,
            "status": self.status,
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "published_at": self.published_at,
            "probability_range": None if self.probability_range is None else list(self.probability_range),
            "time_windows": list(self.time_windows),
            "conditions": list(self.conditions),
            "falsifiers": list(self.falsifiers),
            "invalid_reason": self.invalid_reason,
            "invalidated_at": self.invalidated_at,
            "prediction_validity": PREDICTION_VALIDITY,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PredictionVersion":
        allowed = {
            "version_id", "created_at", "status", "conclusion", "confidence", "published_at", "probability_range",
            "time_windows", "conditions", "falsifiers", "invalid_reason", "invalidated_at", "prediction_validity",
        }
        _reject_unknown(value, allowed, "prediction")
        required = {"version_id", "created_at", "status", "conclusion", "confidence"}
        missing = required - set(value)
        if missing:
            raise LiuYaoError("INVALID_INPUT", f"prediction 缺少字段：{', '.join(sorted(missing))}")
        if value.get("prediction_validity", PREDICTION_VALIDITY) != PREDICTION_VALIDITY:
            raise LiuYaoError("INVALID_INPUT", "prediction_validity 必须是 not_evaluated")
        probability = value.get("probability_range")
        return cls(
            version_id=value["version_id"],
            created_at=value["created_at"],
            status=value["status"],
            conclusion=value["conclusion"],
            confidence=value["confidence"],
            published_at=value.get("published_at"),
            probability_range=None if probability is None else tuple(probability),
            time_windows=_string_tuple(value.get("time_windows", ()), "time_windows"),
            conditions=_string_tuple(value.get("conditions", ()), "conditions"),
            falsifiers=_string_tuple(value.get("falsifiers", ()), "falsifiers"),
            invalid_reason=value.get("invalid_reason"),
            invalidated_at=value.get("invalidated_at"),
        )


@dataclass(frozen=True, slots=True)
class SettlementRecord:
    version_id: str
    outcome: str
    observed_at: str
    evidence_source: str
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "version_id", _non_empty(self.version_id, "settlement.version_id"))
        if self.outcome not in SETTLEMENT_OUTCOMES:
            raise LiuYaoError("INVALID_INPUT", f"outcome 必须是：{', '.join(sorted(SETTLEMENT_OUTCOMES))}")
        object.__setattr__(self, "observed_at", _aware_datetime(self.observed_at, "settlement.observed_at"))
        object.__setattr__(self, "evidence_source", _non_empty(self.evidence_source, "settlement.evidence_source"))
        object.__setattr__(self, "notes", _string_tuple(self.notes, "settlement.notes"))

    def to_dict(self) -> dict[str, object]:
        return {
            "version_id": self.version_id,
            "outcome": self.outcome,
            "observed_at": self.observed_at,
            "evidence_source": self.evidence_source,
            "notes": list(self.notes),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SettlementRecord":
        allowed = {"version_id", "outcome", "observed_at", "evidence_source", "notes"}
        _reject_unknown(value, allowed, "settlement")
        required = {"version_id", "outcome", "observed_at", "evidence_source"}
        missing = required - set(value)
        if missing:
            raise LiuYaoError("INVALID_INPUT", f"settlement 缺少字段：{', '.join(sorted(missing))}")
        return cls(
            version_id=value["version_id"],
            outcome=value["outcome"],
            observed_at=value["observed_at"],
            evidence_source=value["evidence_source"],
            notes=_string_tuple(value.get("notes", ()), "settlement.notes"),
        )
