from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
import json
from importlib.resources import files
import re
from typing import Literal, Mapping

from .bazi import BRANCHES, STEMS, _lunar_month_days, _lunar_year_days, lunar_leap_month, lunar_to_solar
from .contracts.serialization import canonical_json, digest

PHASE19_SCHEMA_VERSION = "chenggu-deterministic-result@0.1"
PHASE19_METHOD_ID = "chenggu-deterministic-integer-qian@0.1.0"
PHASE19_CALCULATION_VERSION = "0.1.0"
PHASE19_DECISION_ID = "PHASE_19_CHENGGU_DETERMINISTIC_ALGORITHM_R1_APPROVED"
TABLE_RESOURCE = "phase19_chenggu_table_v0.1.json"


class Phase19InputError(ValueError):
    pass


@dataclass(frozen=True)
class LunarDate:
    year: int
    month: int
    day: int
    is_leap_month: bool


@dataclass(frozen=True)
class ChengGuResult:
    input_calendar: Literal["solar", "lunar"]
    entered_birth_date: str
    birth_time: str
    lunar_date: str
    is_leap_month: bool
    year_ganzhi: str
    hour_branch: str
    components_qian: Mapping[str, int]
    total_qian: int
    total_liang: int
    remaining_qian: int
    display_weight: str
    table_id: str
    conventions: Mapping[str, object]
    verse_available: bool
    warnings: tuple[str, ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE19_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE19_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE19_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return json.loads(canonical_json(asdict(self)))


def load_chenggu_table() -> dict[str, object]:
    return json.loads(files("mingli.derived.data").joinpath(TABLE_RESOURCE).read_text(encoding="utf-8"))


def solar_to_lunar(value: date) -> LunarDate:
    epoch = date(1900, 1, 31)
    if value < epoch or value > lunar_to_solar(2099, 12, _lunar_month_days(2099, 12)):
        raise Phase19InputError("solar birth_date is outside the supported lunar table range")
    offset = (value - epoch).days
    year = 1900
    while year <= 2099:
        days = _lunar_year_days(year)
        if offset < days:
            break
        offset -= days
        year += 1
    if year > 2099:
        raise Phase19InputError("solar birth_date is outside the supported lunar table range")
    leap = lunar_leap_month(year)
    sequence = [(month, False) for month in range(1, 13)]
    if leap:
        sequence.insert(leap, (leap, True))
    for month, is_leap in sequence:
        days = _lunar_month_days(year, month, is_leap)
        if offset < days:
            return LunarDate(year, month, offset + 1, is_leap)
        offset -= days
    raise Phase19InputError("failed to convert solar date")


def _parse_date(raw: object, calendar: str, is_leap: bool) -> LunarDate:
    if not isinstance(raw, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) is None:
        raise Phase19InputError("birth_date must use YYYY-MM-DD")
    try:
        year, month, day = map(int, raw.split("-"))
        if calendar == "solar":
            return solar_to_lunar(date(year, month, day))
        month_days = _lunar_month_days(year, month, is_leap)
        if not 1 <= day <= month_days:
            raise Phase19InputError(f"lunar day must be between 1 and {month_days}")
        lunar_to_solar(year, month, day, is_leap)
        return LunarDate(year, month, day, is_leap)
    except Phase19InputError:
        raise
    except Exception as exc:
        raise Phase19InputError(f"invalid birth_date: {exc}") from exc


def calculate_chenggu(raw: Mapping[str, object]) -> ChengGuResult:
    if not isinstance(raw, Mapping):
        raise Phase19InputError("input must be an object")
    calendar = raw.get("calendar")
    if calendar not in {"solar", "lunar"}:
        raise Phase19InputError("calendar must be solar or lunar")
    leap = raw.get("is_leap_month", False)
    if not isinstance(leap, bool):
        raise Phase19InputError("is_leap_month must be boolean")
    if calendar == "solar" and leap:
        raise Phase19InputError("is_leap_month is only valid for lunar input")
    lunar = _parse_date(raw.get("birth_date"), str(calendar), leap)
    birth_time = raw.get("birth_time")
    if not isinstance(birth_time, str) or re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", birth_time) is None:
        raise Phase19InputError("birth_time must use HH:MM or HH:MM:SS")
    hour = int(birth_time[:2])
    hour_branch = BRANCHES[((hour + 1) // 2) % 12]
    year_ganzhi = STEMS[(lunar.year - 4) % 10] + BRANCHES[(lunar.year - 4) % 12]
    table = load_chenggu_table()
    year_weights = table["year_weights"]
    month_weights = table["month_weights"]
    day_weights = table["day_weights"]
    hour_weights = table["hour_weights"]
    components = {
        "year": int(year_weights[year_ganzhi]),
        "month": int(month_weights[lunar.month - 1]),
        "day": int(day_weights[lunar.day - 1]),
        "hour": int(hour_weights[hour_branch]),
    }
    total = sum(components.values())
    warnings = ["chenggu_is_a_traditional_cultural_algorithm_not_scientific_prediction"]
    if lunar.is_leap_month:
        warnings.append("leap_month_uses_same_numeric_month_weight")
    body = {
        "input_calendar": calendar,
        "entered_birth_date": raw["birth_date"],
        "birth_time": birth_time,
        "lunar_date": f"{lunar.year:04d}-{lunar.month:02d}-{lunar.day:02d}",
        "is_leap_month": lunar.is_leap_month,
        "year_ganzhi": year_ganzhi,
        "hour_branch": hour_branch,
        "components_qian": components,
        "total_qian": total,
        "total_liang": total // 10,
        "remaining_qian": total % 10,
        "display_weight": f"{total // 10}两{total % 10}钱",
        "table_id": table["table_id"],
        "conventions": {
            "date_basis": "lunar_year_month_day",
            "hour_basis": "local_civil_time_two_hour_branches",
            "zi_hour": "23:00-00:59",
            "leap_month": "same_weight_as_numeric_month",
            "arithmetic": "integer_qian",
        },
        "verse_available": False,
        "warnings": warnings,
    }
    return ChengGuResult(**body, canonical_hash=digest({"record_type": "ChengGuResult", "payload": body}))  # type: ignore[arg-type]


def validate_phase19_table() -> dict[str, object]:
    table = load_chenggu_table()
    failures: list[str] = []
    if len(table.get("year_weights", {})) != 60:
        failures.append("year_weights_count")
    if len(table.get("month_weights", [])) != 12:
        failures.append("month_weights_count")
    if len(table.get("day_weights", [])) != 30:
        failures.append("day_weights_count")
    if set(table.get("hour_weights", {})) != set(BRANCHES):
        failures.append("hour_weights_branches")
    return {"valid": not failures, "failures": failures, "table_id": table.get("table_id")}


def benchmark_phase19() -> dict[str, object]:
    checks: list[tuple[bool, str]] = []
    lunar = calculate_chenggu({"calendar": "lunar", "birth_date": "1984-01-01", "birth_time": "23:00"})
    checks.extend([
        (lunar.year_ganzhi == "甲子", "ganzhi"),
        (lunar.total_qian == 39, "classic_sum"),
        (lunar.display_weight == "3两9钱", "display"),
        (sum(lunar.components_qian.values()) == lunar.total_qian, "components"),
        (lunar.prediction_validity == "not_evaluated", "prediction_boundary"),
    ])
    solar = calculate_chenggu({"calendar": "solar", "birth_date": "1990-03-15", "birth_time": "10:30"})
    checks.extend([
        (solar.lunar_date == "1990-02-19", "solar_to_lunar"),
        (solar.year_ganzhi == "庚午", "solar_ganzhi"),
        (solar.hour_branch == "巳", "hour_branch"),
        (solar.total_qian == 37, "solar_sum"),
        (solar.canonical_hash == calculate_chenggu({"birth_time": "10:30", "birth_date": "1990-03-15", "calendar": "solar"}).canonical_hash, "determinism"),
        (solar.verse_available is False, "verse_boundary"),
    ])
    valid = validate_phase19_table()
    checks.append((valid["valid"] is True, "table_validation"))
    failures = [name for ok, name in checks if not ok]
    return {"assertions_total": len(checks), "passed": len(checks) - len(failures), "failed": len(failures), "unresolved": 0, "failures": failures}
