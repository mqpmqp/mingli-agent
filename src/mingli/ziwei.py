from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
import re
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .bazi import BRANCHES, STEMS, equation_of_time_minutes, lunar_to_solar
from .contracts.serialization import digest
from .phase19 import solar_to_lunar
from .ziwei_engine import (
    ALGORITHM_PROFILE,
    PALACE_BRANCHES,
    PALACE_NAMES,
    ZIWEI_ENGINE_VERSION,
    build_traditional_ziwei,
)

ZIWEI_SCHEMA_VERSION = "ziwei-chart@1.0"
ZIWEI_METHOD_ID = "ziwei-traditional-natal@1.0.0"
ZIWEI_ALGORITHM_VERSION = ZIWEI_ENGINE_VERSION
UNSUPPORTED_CHART_FIELDS = (
    "life_palace", "body_palace", "bureau", "heavenly_stems", "earthly_branches",
    "primary_stars", "supporting_stars", "malefic_stars", "transformations", "brightness_state",
)


class ZiweiContractError(ValueError):
    pass


def _fail(message: str) -> None:
    raise ZiweiContractError(message)


def _zone(value: object) -> ZoneInfo | timezone:
    if not isinstance(value, str) or not value:
        _fail("timezone is required")
    match = re.fullmatch(r"([+-])(\d{2}):(\d{2})", value)
    if match:
        hours, minutes = int(match.group(2)), int(match.group(3))
        if hours > 14 or minutes > 59:
            _fail("timezone offset is invalid")
        delta = timedelta(hours=hours, minutes=minutes)
        return timezone(delta if match.group(1) == "+" else -delta)
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ZiweiContractError(f"unknown timezone: {value}") from exc


def _number(value: object, name: str, low: float, high: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= float(value) <= high:
        _fail(f"{name} must be between {low} and {high}")
    return float(value)


def _solar_date(raw: Mapping[str, object]) -> tuple[date, str, bool]:
    calendar = raw.get("calendar_type")
    if calendar not in {"solar", "lunar"}:
        _fail("calendar_type must be solar or lunar")
    entered = raw.get("birth_date")
    if not isinstance(entered, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", entered) is None:
        _fail("birth_date must use YYYY-MM-DD")
    leap = raw.get("leap_month", False)
    if not isinstance(leap, bool):
        _fail("leap_month must be boolean")
    if calendar == "solar" and leap:
        _fail("leap_month is only valid for lunar input")
    try:
        if calendar == "solar":
            result = date.fromisoformat(entered)
        else:
            year, month, day = map(int, entered.split("-"))
            result = lunar_to_solar(year, month, day, leap)
    except (ValueError, TypeError) as exc:
        raise ZiweiContractError(f"invalid birth_date: {exc}") from exc
    if not 1901 <= result.year <= 2099:
        _fail("supported birth years are 1901-2099")
    return result, str(calendar), leap


def _birth_time(raw: Mapping[str, object]) -> tuple[time | None, bool]:
    entered = raw.get("birth_time")
    known = raw.get("birth_time_known", entered is not None)
    if not isinstance(known, bool):
        _fail("birth_time_known must be boolean")
    if not known:
        if entered not in {None, ""}:
            _fail("birth_time must be empty when birth_time_known is false")
        return None, False
    if not isinstance(entered, str) or re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", entered) is None:
        _fail("birth_time must use HH:MM or HH:MM:SS")
    try:
        return time.fromisoformat(entered), True
    except ValueError as exc:
        raise ZiweiContractError(f"invalid birth_time: {exc}") from exc


def normalize_ziwei_birth(raw: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        _fail("birth input must be an object")
    solar_date, calendar, input_leap = _solar_date(raw)
    entered_time, known = _birth_time(raw)
    gender = raw.get("gender")
    if gender not in {"male", "female", "other", "unspecified"}:
        _fail("gender must be male, female, other, or unspecified")
    mode = raw.get("solar_time_mode", "civil")
    if mode not in {"civil", "local_mean", "apparent_solar"}:
        _fail("solar_time_mode must be civil, local_mean, or apparent_solar")
    late_zi = raw.get("late_zi_policy", "midnight")
    if late_zi not in {"midnight", "late_zi_next_day"}:
        _fail("late_zi_policy must be midnight or late_zi_next_day")
    longitude = _number(raw.get("longitude"), "longitude", -180, 180)
    latitude = _number(raw.get("latitude"), "latitude", -90, 90)
    if mode != "civil" and longitude is None:
        _fail("longitude is required for solar time correction")
    zone_name = raw.get("timezone")
    zone = _zone(zone_name)
    lunar = solar_to_lunar(solar_date)

    body: dict[str, object] = {
        "calendar_type": calendar,
        "input_birth_date": str(raw["birth_date"]),
        "solar_date": solar_date.isoformat(),
        "canonical_lunar_date": f"{lunar.year:04d}-{lunar.month:02d}-{lunar.day:02d}",
        "canonical_lunar_leap_month": lunar.is_leap_month,
        "input_leap_month": input_leap,
        "birth_time_known": known,
        "timezone": str(zone_name),
        "longitude": longitude,
        "latitude": latitude,
        "solar_time_mode": mode,
        "late_zi_policy": late_zi,
        "gender": gender,
        "input_datetime": None,
        "corrected_datetime": None,
        "longitude_correction_minutes": 0.0,
        "equation_of_time_minutes": 0.0,
        "equation_of_time_applied": False,
        "dst_correction_minutes": 0.0,
        "total_correction_minutes": 0.0,
        "crossed_civil_day": False,
        "chart_date": solar_date.isoformat(),
        "shichen_index": None,
        "correction_reasons": [],
    }
    if not known or entered_time is None:
        body["correction_reasons"] = ["birth_time_unknown_no_time_correction_applied"]
        return body

    civil = datetime.combine(solar_date, entered_time).replace(tzinfo=zone)
    if civil.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != civil.replace(tzinfo=None):
        _fail("birth time does not exist in the selected timezone")
    dst = civil.dst() or timedelta()
    utc_offset = civil.utcoffset() or timedelta()
    standard_offset = utc_offset - dst
    standard_meridian = standard_offset.total_seconds() / 240
    longitude_minutes = 0.0
    equation_minutes = 0.0
    dst_minutes = 0.0
    reasons: list[str] = []
    if mode in {"local_mean", "apparent_solar"}:
        assert longitude is not None
        longitude_minutes = 4 * (longitude - standard_meridian)
        reasons.append("longitude_to_standard_meridian")
    if mode == "apparent_solar":
        equation_minutes = equation_of_time_minutes(civil)
        dst_minutes = -dst.total_seconds() / 60
        reasons.extend(("equation_of_time", "daylight_saving_removal"))
    total = longitude_minutes + equation_minutes + dst_minutes
    corrected = civil + timedelta(minutes=total)
    chart_date = corrected.date()
    if late_zi == "late_zi_next_day" and corrected.hour == 23:
        chart_date += timedelta(days=1)
    body.update(
        {
            "input_datetime": civil.isoformat(),
            "corrected_datetime": corrected.isoformat(),
            "longitude_correction_minutes": round(longitude_minutes, 6),
            "equation_of_time_minutes": round(equation_minutes, 6),
            "equation_of_time_applied": mode == "apparent_solar",
            "dst_correction_minutes": round(dst_minutes, 6),
            "total_correction_minutes": round(total, 6),
            "crossed_civil_day": corrected.date() != civil.date(),
            "chart_date": chart_date.isoformat(),
            "shichen_index": ((corrected.hour + 1) // 2) % 12,
            "correction_reasons": reasons or ["civil_time_retained"],
        }
    )
    return body


def _fingerprint(normalized: Mapping[str, object], algorithm_version: str) -> str:
    payload = {
        "calendar_basis": "solar_with_canonical_lunar_identity",
        "solar_date": normalized["solar_date"],
        "canonical_lunar_date": normalized["canonical_lunar_date"],
        "canonical_lunar_leap_month": normalized["canonical_lunar_leap_month"],
        "corrected_datetime": normalized["corrected_datetime"],
        "birth_time_known": normalized["birth_time_known"],
        "timezone": normalized["timezone"],
        "longitude": normalized["longitude"],
        "latitude": normalized["latitude"],
        "solar_time_mode": normalized["solar_time_mode"],
        "late_zi_policy": normalized["late_zi_policy"],
        "gender": normalized["gender"],
        "algorithm_version": algorithm_version,
    }
    return digest({"record_type": "ZiweiChartIdentity", "payload": payload})


def build_temporal_context(level: str, **values: object) -> dict[str, object]:
    if level == "natal":
        return {"level": "natal"}
    if level == "decade":
        start, end = values.get("start_year"), values.get("end_year")
        if isinstance(start, bool) or not isinstance(start, int) or isinstance(end, bool) or not isinstance(end, int) or end < start:
            _fail("decade requires valid start_year and end_year")
        return {"level": level, "start_year": start, "end_year": end}
    if level == "annual":
        year = values.get("year")
        if isinstance(year, bool) or not isinstance(year, int):
            _fail("annual context requires year")
        return {"level": level, "year": year}
    if level == "monthly":
        year, month = values.get("year"), values.get("month")
        leap = values.get("leap_month", False)
        if isinstance(year, bool) or not isinstance(year, int) or isinstance(month, bool) or not isinstance(month, int):
            _fail("monthly context requires year and month")
        if not 1 <= month <= 12 or not isinstance(leap, bool):
            _fail("monthly month/leap_month is invalid")
        return {"level": level, "year": year, "month": month, "leap_month": leap}
    if level == "daily":
        raw_date = values.get("date")
        if not isinstance(raw_date, str):
            _fail("daily context requires date")
        try:
            parsed = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ZiweiContractError("daily context requires ISO date") from exc
        return {"level": level, "date": parsed.isoformat()}
    if level == "hourly":
        raw_datetime, zone_name = values.get("datetime"), values.get("timezone")
        if not isinstance(raw_datetime, str) or not isinstance(zone_name, str):
            _fail("hourly context requires datetime and timezone")
        try:
            parsed = datetime.fromisoformat(raw_datetime)
        except ValueError as exc:
            raise ZiweiContractError("hourly context requires ISO datetime") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            _fail("hourly datetime must be timezone-aware")
        _zone(zone_name)
        return {"level": level, "datetime": parsed.isoformat(), "timezone": zone_name}
    _fail("temporal level must be natal, decade, annual, monthly, daily, or hourly")


def build_ziwei_chart(raw: Mapping[str, object], *, algorithm_version: str = ZIWEI_ALGORITHM_VERSION) -> dict[str, object]:
    normalized = normalize_ziwei_birth(raw)
    known = bool(normalized["birth_time_known"])
    placement_date = solar_to_lunar(date.fromisoformat(str(normalized["chart_date"])))
    placement_lunar_date = {
        "year": placement_date.year,
        "month": placement_date.month,
        "day": placement_date.day,
        "leap_month": placement_date.is_leap_month,
        "year_stem": STEMS[(placement_date.year - 4) % 10],
        "year_branch": BRANCHES[(placement_date.year - 4) % 12],
    }
    if known:
        engine = build_traditional_ziwei(normalized)
        unsupported: list[str] = []
        warnings = [
            "traditional_rule_content_not_included_in_engine_v1",
            "prediction_validity_not_evaluated",
        ]
        status = "complete"
        confidence = "medium"
    else:
        unsupported = ["birth_time", *UNSUPPORTED_CHART_FIELDS]
        warnings = [
            "unknown_birth_time_degraded_without_default_shichen",
            "no_interpretation_may_be_derived_from_empty_palace_fields",
        ]
        status = "degraded"
        confidence = "low"
        engine = {
            "placement_lunar_date": placement_lunar_date,
            "life_palace": None,
            "body_palace": None,
            "bureau": None,
            "palaces": [
                {
                    "palace_index": index,
                    "palace_name": name,
                    "heavenly_stem": None,
                    "earthly_branch": PALACE_BRANCHES[index],
                    "is_body_palace": None,
                    "primary_stars": [],
                    "supporting_stars": [],
                    "malefic_stars": [],
                    "transformations": [],
                    "brightness_state": [],
                    "field_status": "unsupported",
                }
                for index, name in enumerate(PALACE_NAMES)
            ],
        }
    result: dict[str, object] = {
        "schema_version": ZIWEI_SCHEMA_VERSION,
        "method_id": ZIWEI_METHOD_ID,
        "algorithm_version": algorithm_version,
        "algorithm_profile": dict(ALGORITHM_PROFILE),
        "calculation_status": status,
        "chart_fingerprint": _fingerprint(normalized, algorithm_version),
        "time_correction": normalized,
        "temporal_context": build_temporal_context("natal"),
        "placement_lunar_date": engine["placement_lunar_date"],
        "life_palace": engine["life_palace"],
        "body_palace": engine["body_palace"],
        "bureau": engine["bureau"],
        "palaces": engine["palaces"],
        "unsupported_fields": unsupported,
        "warnings": warnings,
        "source_provenance": [
            {"source_id": "mingli:bazi:calendar-conversion", "role": "calendar_normalization"},
            {"source_id": "mingli:bazi:noaa-eot", "role": "equation_of_time"},
            {"source_id": "mingli:phase19:solar-lunar", "role": "canonical_lunar_identity"},
            {"source_id": "classical:ziwei-placement", "role": "traditional_formula_profile"},
            {
                "source_id": "public:zhwiki:ziwei-calculation@2026-07-16",
                "role": "reviewable_formula_transcription",
            },
            {
                "source_id": "oss:iztro@f3dc6c547420b063109251d7c7132fa3cb41e06e",
                "role": "independent_cross_check",
                "license": "MIT",
            },
        ],
        "confidence": confidence,
        "prediction_validity": "not_evaluated",
    }
    result["canonical_hash"] = digest({"record_type": "ZiweiChart", "payload": result})
    return result


__all__ = [
    "PALACE_NAMES", "ZIWEI_ALGORITHM_VERSION", "ZiweiContractError",
    "build_temporal_context", "build_ziwei_chart", "normalize_ziwei_birth",
]
