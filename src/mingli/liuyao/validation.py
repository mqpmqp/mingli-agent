from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from ..errors import MingLiError
from .tables import (
    BRANCHES, COIN_CONVENTION, SEXAGENARY_CYCLE, _CASTING_MODE_ALIASES,
    _COIN_LABEL_VALUES, _CONVENTION_ALIASES, _LINE_TYPES,
)

class LiuYaoError(MingLiError, ValueError):
    """六爻确定性层的可机器识别错误。"""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class LiuYaoInputConflictError(LiuYaoError):
    """同一 case_id 收到不同六摇或不同事件合同时阻断。"""

def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LiuYaoError("INVALID_INPUT", f"{field_name} 必须是非空字符串")
    return value.strip()


def _aware_datetime(value: object, field_name: str) -> str:
    text = _non_empty(value, field_name)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise LiuYaoError("INVALID_INPUT", f"{field_name} 必须是 ISO 8601 日期时间") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LiuYaoError("INVALID_INPUT", f"{field_name} 必须包含时区偏移")
    return parsed.isoformat()


def _iso_date(value: object, field_name: str) -> str:
    text = _non_empty(value, field_name)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise LiuYaoError("INVALID_INPUT", f"{field_name} 必须是 YYYY-MM-DD 格式的有效日期") from exc


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise LiuYaoError("INVALID_INPUT", f"{field_name} 必须是字符串数组")
    result = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise LiuYaoError("INVALID_INPUT", f"{field_name} 只能包含非空字符串")
    return tuple(item.strip() for item in result)


def _clean_label(value: str) -> str:
    return re.sub(r"[\s,，。;；:：]+", "", value.strip())


def normalize_line_value(value: object) -> int:
    if isinstance(value, bool):
        raise LiuYaoError("INVALID_INPUT", "爻值不能是布尔值")
    if isinstance(value, int):
        if value in _LINE_TYPES:
            return value
        raise LiuYaoError("INVALID_INPUT", "爻值只能是 6、7、8、9")
    if isinstance(value, str):
        normalized = _clean_label(value)
        if normalized in _COIN_LABEL_VALUES:
            return _COIN_LABEL_VALUES[normalized]
    raise LiuYaoError("INVALID_INPUT", f"无法识别爻值：{value!r}")


def normalize_line_values(values: object) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise LiuYaoError("INVALID_INPUT", "line_values 必须是六项数组")
    normalized = tuple(normalize_line_value(value) for value in values)
    if len(normalized) != 6:
        raise LiuYaoError("INVALID_INPUT", "line_values 必须恰好包含六项，顺序为初爻到上爻")
    return normalized


def _normalize_convention(value: object) -> str:
    text = _non_empty(value, "coin_convention")
    normalized = _CONVENTION_ALIASES.get(text) or _CONVENTION_ALIASES.get(_clean_label(text))
    if normalized is None:
        raise LiuYaoError("UNSUPPORTED_CONVENTION", "当前版本只支持字为阴、花为阳")
    return normalized


def _normalize_casting_mode(value: object) -> str:
    text = _non_empty(value, "casting_mode")
    normalized = _CASTING_MODE_ALIASES.get(text)
    if normalized is None:
        raise LiuYaoError("INVALID_INPUT", "casting_mode 只能是 self/本人 或 proxy/代摇")
    return normalized


def _normalize_day_ganzhi(value: object | None) -> str | None:
    if value is None:
        return None
    text = _clean_label(_non_empty(value, "day_ganzhi"))
    if text.endswith("日"):
        text = text[:-1]
    if text not in SEXAGENARY_CYCLE:
        raise LiuYaoError("INVALID_INPUT", "day_ganzhi 必须是有效的六十甲子日柱，例如丙午")
    return text


def _normalize_month_branch(value: object | None) -> str | None:
    if value is None:
        return None
    text = _clean_label(_non_empty(value, "month_branch"))
    if text.endswith("月"):
        text = text[:-1]
    if text not in BRANCHES:
        raise LiuYaoError("INVALID_INPUT", "month_branch 必须是十二地支之一")
    return text


def _require_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LiuYaoError("INVALID_INPUT", f"{field_name} 必须是对象")
    return value


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], field_name: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise LiuYaoError("INVALID_INPUT", f"{field_name} 含未知字段：{', '.join(sorted(unknown))}")
