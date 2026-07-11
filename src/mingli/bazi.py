from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ChartCalculationError
from .models import ChartInput


METHOD_ID = "bazi-deterministic-lichun-jie-noaa-v0.1"
SUPPORTED_YEARS = (1901, 2099)
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
SOLAR_TERM_METHOD = "apparent-solar-longitude-noaa-meeus-low-precision-v0.1"
DAY_BOUNDARY = "00:00 civil or corrected local time"
SOLAR_TERM_UNCERTAINTY_MINUTES = 15

# 1900-2099 lunar month facts encoded as: low nibble = leap month,
# bits 15..4 = regular 30-day months, bit 16 = 30-day leap month.
# Generated from sxtwl 2.0.7 and cross-checked against lunar_python 1.4.8.
LUNAR_YEAR_INFO = (
    0x04BD8, 0x04AE0, 0x0A570, 0x054D5, 0x0D260, 0x0D950, 0x16554, 0x056A0, 0x09AD0, 0x055D2,
    0x04AE0, 0x0A5B6, 0x0A4D0, 0x0D250, 0x1D255, 0x0B540, 0x0D6A0, 0x0ADA2, 0x095B0, 0x14977,
    0x04970, 0x0A4B0, 0x0B4B5, 0x06A50, 0x06D40, 0x1AB54, 0x02B60, 0x09570, 0x052F2, 0x04970,
    0x06566, 0x0D4A0, 0x0EA50, 0x16A95, 0x05AD0, 0x02B60, 0x186E3, 0x092E0, 0x1C8D7, 0x0C950,
    0x0D4A0, 0x1D8A6, 0x0B550, 0x056A0, 0x1A5B4, 0x025D0, 0x092D0, 0x0D2B2, 0x0A950, 0x0B557,
    0x06CA0, 0x0B550, 0x15355, 0x04DA0, 0x0A5B0, 0x14573, 0x052B0, 0x0A9A8, 0x0E950, 0x06AA0,
    0x0AEA6, 0x0AB50, 0x04B60, 0x0AAE4, 0x0A570, 0x05260, 0x0F263, 0x0D950, 0x05B57, 0x056A0,
    0x096D0, 0x04DD5, 0x04AD0, 0x0A4D0, 0x0D4D4, 0x0D250, 0x0D558, 0x0B540, 0x0B6A0, 0x195A6,
    0x095B0, 0x049B0, 0x0A974, 0x0A4B0, 0x0B27A, 0x06A50, 0x06D40, 0x0AF46, 0x0AB60, 0x09570,
    0x04AF5, 0x04970, 0x064B0, 0x074A3, 0x0EA50, 0x06B58, 0x05AC0, 0x0AB60, 0x096D5, 0x092E0,
    0x0C960, 0x0D954, 0x0D4A0, 0x0DA50, 0x07552, 0x056A0, 0x0ABB7, 0x025D0, 0x092D0, 0x0CAB5,
    0x0A950, 0x0B4A0, 0x0BAA4, 0x0AD50, 0x055D9, 0x04BA0, 0x0A5B0, 0x15176, 0x052B0, 0x0A930,
    0x07954, 0x06AA0, 0x0AD50, 0x05B52, 0x04B60, 0x0A6E6, 0x0A4E0, 0x0D260, 0x0EA65, 0x0D530,
    0x05AA0, 0x076A3, 0x096D0, 0x04AFB, 0x04AD0, 0x0A4D0, 0x1D0B6, 0x0D250, 0x0D520, 0x0DD45,
    0x0B5A0, 0x056D0, 0x055B2, 0x049B0, 0x0A577, 0x0A4B0, 0x0AA50, 0x1B255, 0x06D20, 0x0ADA0,
    0x14B63, 0x09370, 0x049F8, 0x04970, 0x064B0, 0x168A6, 0x0EA50, 0x06AA0, 0x1A6C4, 0x0AAE0,
    0x092E0, 0x0D2E3, 0x0C960, 0x0D557, 0x0D4A0, 0x0DA50, 0x05D55, 0x056A0, 0x0A6D0, 0x055D4,
    0x052D0, 0x0A9B8, 0x0A950, 0x0B4A0, 0x0B6A6, 0x0AD50, 0x055A0, 0x0ABA4, 0x0A5B0, 0x052B0,
    0x0B273, 0x06930, 0x07337, 0x06AA0, 0x0AD50, 0x14B55, 0x04B60, 0x0A570, 0x054E4, 0x0D160,
    0x0E968, 0x0D520, 0x0DAA0, 0x16AA6, 0x056D0, 0x04AE0, 0x0A9D4, 0x0A2D0, 0x0D150, 0x0F252,
)

JIE_TERMS = (
    (285, 12, "xiaohan", 1, 5),
    (315, 1, "lichun", 2, 4),
    (345, 2, "jingzhe", 3, 6),
    (15, 3, "qingming", 4, 5),
    (45, 4, "lixia", 5, 6),
    (75, 5, "mangzhong", 6, 6),
    (105, 6, "xiaoshu", 7, 7),
    (135, 7, "liqiu", 8, 8),
    (165, 8, "bailu", 9, 8),
    (195, 9, "hanlu", 10, 8),
    (225, 10, "lidong", 11, 7),
    (255, 11, "daxue", 12, 7),
)

CONVENTIONS: dict[str, Any] = {
    "year_boundary": "lichun exact instant; not Lunar New Year",
    "month_boundaries": [item[2] for item in JIE_TERMS],
    "day_boundary": DAY_BOUNDARY,
    "early_late_zi_distinction": False,
    "true_solar_time": "civil standard time + 4*(longitude-standard_meridian) + equation_of_time - DST",
    "equation_of_time": "NOAA fractional-year approximation",
    "solar_term_method": SOLAR_TERM_METHOD,
    "solar_term_uncertainty_minutes": SOLAR_TERM_UNCERTAINTY_MINUTES,
    "missing_longitude": "fail when true solar time is requested",
    "lunar_leap_month": "explicit leap flag; invalid leap month fails",
    "luck_direction": "yang-year male/yin-year female forward; otherwise reverse",
    "luck_start": "elapsed time to adjacent jie divided by three, reported as decimal years",
    "supported_years": list(SUPPORTED_YEARS),
    "prediction_validity": "not evaluated",
}


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    total: int
    independent: int
    passed: int
    failed: int
    unresolved: int
    source_agreement: float
    categories: Mapping[str, Mapping[str, int]]
    failures: tuple[str, ...]


def _fail(code: str, message: str) -> None:
    raise ChartCalculationError(code, message)


def _lunar_info(year: int) -> int:
    if not 1900 <= year <= 2099:
        _fail("UNSUPPORTED_YEAR", "lunar year must be between 1900 and 2099")
    return LUNAR_YEAR_INFO[year - 1900]


def lunar_leap_month(year: int) -> int:
    return _lunar_info(year) & 0xF


def _lunar_month_days(year: int, month: int, is_leap: bool = False) -> int:
    if not 1 <= month <= 12:
        _fail("INVALID_LUNAR_DATE", "lunar month must be between 1 and 12")
    info = _lunar_info(year)
    if is_leap:
        if (info & 0xF) != month:
            _fail("INVALID_LEAP_MONTH", f"{year} does not have leap month {month}")
        return 30 if info & 0x10000 else 29
    return 30 if info & (0x10000 >> month) else 29


def _lunar_year_days(year: int) -> int:
    total = sum(_lunar_month_days(year, month) for month in range(1, 13))
    leap = lunar_leap_month(year)
    return total + (_lunar_month_days(year, leap, True) if leap else 0)


def lunar_to_solar(year: int, month: int, day: int, is_leap: bool = False) -> date:
    month_days = _lunar_month_days(year, month, is_leap)
    if not 1 <= day <= month_days:
        _fail("INVALID_LUNAR_DATE", f"lunar day must be between 1 and {month_days}")
    offset = sum(_lunar_year_days(item) for item in range(1900, year))
    leap = lunar_leap_month(year)
    for item in range(1, month):
        offset += _lunar_month_days(year, item)
        if leap == item:
            offset += _lunar_month_days(year, item, True)
    if is_leap:
        offset += _lunar_month_days(year, month)
    return date(1900, 1, 31) + timedelta(days=offset + day - 1)


def _julian_day(moment: datetime) -> float:
    utc = moment.astimezone(UTC)
    year, month = utc.year, utc.month
    day = utc.day + (utc.hour + (utc.minute + (utc.second + utc.microsecond / 1_000_000) / 60) / 60) / 24
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5


def _apparent_solar_longitude(moment: datetime) -> float:
    t = (_julian_day(moment) - 2451545.0) / 36525
    mean_longitude = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360
    anomaly = math.radians((357.52911 + t * (35999.05029 - 0.0001537 * t)) % 360)
    center = (
        math.sin(anomaly) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * anomaly) * (0.019993 - 0.000101 * t)
        + math.sin(3 * anomaly) * 0.000289
    )
    omega = math.radians(125.04 - 1934.136 * t)
    return (mean_longitude + center - 0.00569 - 0.00478 * math.sin(omega)) % 360


def solar_term_utc(year: int, target_longitude: int) -> datetime:
    matching = next((item for item in JIE_TERMS if item[0] == target_longitude), None)
    if matching is None:
        _fail("INTERNAL_SOLAR_TERM", f"unsupported jie longitude {target_longitude}")
    guess = datetime(year, matching[3], matching[4], 12, tzinfo=UTC)
    lower, upper = guess - timedelta(days=4), guess + timedelta(days=4)

    def difference(moment: datetime) -> float:
        return (_apparent_solar_longitude(moment) - target_longitude + 180) % 360 - 180

    if difference(lower) >= 0 or difference(upper) <= 0:
        _fail("INTERNAL_SOLAR_TERM", f"could not bracket solar term {target_longitude} for {year}")
    for _ in range(48):
        middle = lower + (upper - lower) / 2
        if difference(middle) < 0:
            lower = middle
        else:
            upper = middle
    return lower + (upper - lower) / 2


def _jie_instants(year: int) -> list[tuple[datetime, int, str]]:
    return sorted((solar_term_utc(year, longitude), month, name) for longitude, month, name, _, _ in JIE_TERMS)


def _sexagenary(index: int) -> str:
    return STEMS[index % 10] + BRANCHES[index % 12]


def _parse_time(value: object) -> time:
    if not isinstance(value, str) or re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", value) is None:
        _fail("INVALID_TIME", "birth_time must use HH:MM or HH:MM:SS")
    return time.fromisoformat(value)


def _parse_timezone(value: object) -> tzinfo:
    if not isinstance(value, str) or not value:
        _fail("INVALID_TIMEZONE", "timezone is required")
    match = re.fullmatch(r"([+-])(\d{2}):(\d{2})", value)
    if match:
        hours, minutes = int(match.group(2)), int(match.group(3))
        if hours > 14 or minutes > 59:
            _fail("INVALID_TIMEZONE", "fixed UTC offset is out of range")
        delta = timedelta(hours=hours, minutes=minutes)
        return timezone(delta if match.group(1) == "+" else -delta)
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        _fail("INVALID_TIMEZONE", f"unknown IANA timezone {value}")


def _aware_local(naive: datetime, zone: tzinfo, fold: object) -> datetime:
    if fold not in (0, 1):
        _fail("INVALID_FOLD", "fold must be 0 or 1")
    aware = naive.replace(tzinfo=zone, fold=int(fold))
    if aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive:
        _fail("NONEXISTENT_LOCAL_TIME", "local time does not exist in the selected timezone")
    return aware


def _number(value: object, name: str, lower: float, upper: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lower <= float(value) <= upper:
        _fail("INVALID_COORDINATE", f"{name} must be between {lower} and {upper}")
    return float(value)


def equation_of_time_minutes(moment: datetime) -> float:
    day_number = moment.timetuple().tm_yday
    days = date(moment.year, 12, 31).timetuple().tm_yday
    hour = moment.hour + moment.minute / 60 + moment.second / 3600
    gamma = 2 * math.pi / days * (day_number - 1 + (hour - 12) / 24)
    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )


def _true_solar_time(moment: datetime, longitude: float) -> tuple[datetime, float, float]:
    utc_offset = moment.utcoffset() or timedelta()
    dst = moment.dst() or timedelta()
    standard_offset = utc_offset - dst
    standard_meridian = standard_offset.total_seconds() / 240
    equation = equation_of_time_minutes(moment)
    correction = 4 * (longitude - standard_meridian) + equation - dst.total_seconds() / 60
    return moment + timedelta(minutes=correction), correction, equation


def _normalize_input(value: ChartInput | Mapping[str, object]) -> dict[str, object]:
    if isinstance(value, ChartInput):
        return {
            "gender": value.gender,
            "calendar": value.calendar,
            "birth_date": value.birth_date,
            "birth_time": value.birth_time,
            "timezone": value.timezone,
            "birth_location": dict(value.birth_location),
            "true_solar_time": value.solar_time_adjustment,
        }
    if not isinstance(value, Mapping):
        _fail("INVALID_INPUT", "chart input must be an object")
    return dict(value)


class DeterministicBaziEngine:
    def calculate(self, chart_input: ChartInput | Mapping[str, object]) -> Mapping[str, object]:
        data = _normalize_input(chart_input)
        calendar = data.get("calendar")
        if calendar not in {"solar", "lunar"}:
            _fail("INVALID_CALENDAR", "calendar must be solar or lunar")
        gender = data.get("gender")
        if gender not in {"male", "female"}:
            _fail("INVALID_GENDER", "gender must be male or female")
        raw_date = data.get("birth_date")
        if not isinstance(raw_date, str):
            _fail("INVALID_DATE", "birth_date must use YYYY-MM-DD")
        if calendar == "solar":
            try:
                entered_year, entered_month, entered_day = date.fromisoformat(raw_date).timetuple()[:3]
            except ValueError:
                _fail("INVALID_DATE", "solar birth_date must be a valid YYYY-MM-DD date")
        else:
            match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw_date)
            if match is None:
                _fail("INVALID_DATE", "lunar birth_date must use YYYY-MM-DD")
            entered_year, entered_month, entered_day = map(int, match.groups())
        if not SUPPORTED_YEARS[0] <= entered_year <= SUPPORTED_YEARS[1]:
            _fail("UNSUPPORTED_YEAR", "supported input years are 1901-2099")
        is_leap = data.get("is_leap_month", False)
        if not isinstance(is_leap, bool):
            _fail("INVALID_LEAP_MONTH", "is_leap_month must be boolean")
        solar_date = (
            lunar_to_solar(entered_year, entered_month, entered_day, is_leap)
            if calendar == "lunar"
            else date(entered_year, entered_month, entered_day)
        )
        if not SUPPORTED_YEARS[0] <= solar_date.year <= SUPPORTED_YEARS[1]:
            _fail("UNSUPPORTED_YEAR", "converted solar date is outside 1901-2099")
        birth_time = _parse_time(data.get("birth_time"))
        zone = _parse_timezone(data.get("timezone"))
        civil = _aware_local(datetime.combine(solar_date, birth_time), zone, data.get("fold", 0))

        location = data.get("birth_location", {})
        if location is None:
            location = {}
        if not isinstance(location, Mapping):
            _fail("INVALID_COORDINATE", "birth_location must be an object")
        longitude = _number(data.get("longitude", location.get("longitude")), "longitude", -180, 180)
        latitude = _number(data.get("latitude", location.get("latitude")), "latitude", -90, 90)
        apply_solar = data.get("true_solar_time", data.get("solar_time_adjustment", False))
        if not isinstance(apply_solar, bool):
            _fail("INVALID_INPUT", "true_solar_time must be boolean")
        warnings: list[str] = []
        corrected, correction, equation = civil, 0.0, equation_of_time_minutes(civil)
        if apply_solar:
            if longitude is None:
                _fail("MISSING_LONGITUDE", "longitude is required for true solar time")
            corrected, correction, equation = _true_solar_time(civil, longitude)
            if not SUPPORTED_YEARS[0] <= corrected.year <= SUPPORTED_YEARS[1]:
                _fail("UNSUPPORTED_YEAR", "true-solar corrected datetime is outside 1901-2099")
        elif longitude is None:
            warnings.append("longitude_missing_true_solar_time_not_applied")

        instant = civil.astimezone(UTC)
        li_chun = solar_term_utc(civil.year, 315)
        pillar_year = civil.year if instant >= li_chun else civil.year - 1
        year_index = (pillar_year - 4) % 60
        year_stem = year_index % 10

        jie = [item for year in (civil.year - 1, civil.year, civil.year + 1) for item in _jie_instants(year)]
        nearest = min(jie, key=lambda item: abs((item[0] - instant).total_seconds()))
        if abs((nearest[0] - instant).total_seconds()) < SOLAR_TERM_UNCERTAINTY_MINUTES * 60:
            _fail(
                "SOLAR_TERM_UNCERTAIN",
                f"input is within {SOLAR_TERM_UNCERTAINTY_MINUTES} minutes of {nearest[2]}",
            )
        previous = max((item for item in jie if item[0] <= instant), key=lambda item: item[0])
        month_number, month_term = previous[1], previous[2]
        month_stem = (year_stem % 5 * 2 + month_number + 1) % 10
        month_branch = (month_number + 1) % 12

        day_index = (corrected.date().toordinal() + 14) % 60
        hour_branch = ((corrected.hour + 1) // 2) % 12
        hour_stem = ((day_index % 10) * 2 + hour_branch) % 10

        forward = (year_stem % 2 == 0 and gender == "male") or (year_stem % 2 == 1 and gender == "female")
        adjacent = min((item for item in jie if item[0] > instant), key=lambda item: item[0]) if forward else previous
        start_days = abs((adjacent[0] - instant).total_seconds()) / 86400

        return {
            "method_id": METHOD_ID,
            "calculation_version": "0.1.0",
            "calendar": {
                "input_calendar": calendar,
                "input_date": raw_date,
                "solar_date": solar_date.isoformat(),
                "input_datetime": civil.isoformat(),
                "corrected_datetime": corrected.isoformat(),
                "timezone": str(data.get("timezone")),
                "longitude": longitude,
                "latitude": latitude,
                "true_solar_time_applied": apply_solar,
                "true_solar_correction_minutes": round(correction, 6),
                "equation_of_time_minutes": round(equation, 6),
            },
            "pillars": {
                "year": _sexagenary(year_index),
                "month": STEMS[month_stem] + BRANCHES[month_branch],
                "day": _sexagenary(day_index),
                "hour": STEMS[hour_stem] + BRANCHES[hour_branch],
            },
            "boundaries": {
                "lichun_utc": li_chun.isoformat(),
                "active_month_term": month_term,
                "active_month_term_utc": previous[0].isoformat(),
            },
            "luck": {
                "direction": "forward" if forward else "reverse",
                "start_age_years": round(start_days / 3, 6),
                "adjacent_jie": adjacent[2],
                "adjacent_jie_utc": adjacent[0].isoformat(),
            },
            "conventions": CONVENTIONS,
            "warnings": warnings,
            "prediction_validity": "not_evaluated",
        }


def load_benchmarks(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: benchmark must be an object")
        records.append(record)
    return records


def validate_benchmarks(path: Path, *, strict: bool = False) -> tuple[str, ...]:
    issues: list[str] = []
    required = {
        "id", "category", "input", "expected_pillars", "verification_source", "source_version",
        "timezone", "longitude", "latitude", "calendar_convention", "day_boundary_convention",
        "solar_term_method", "independent", "status", "source_agreement",
    }
    records = load_benchmarks(path)
    seen: set[str] = set()
    for index, record in enumerate(records, 1):
        missing = required - set(record)
        if missing:
            issues.append(f"line {index}: missing {', '.join(sorted(missing))}")
        case_id = record.get("id")
        if not isinstance(case_id, str) or not case_id:
            issues.append(f"line {index}: invalid id")
        elif case_id in seen:
            issues.append(f"line {index}: duplicate id {case_id}")
        else:
            seen.add(case_id)
        sources = record.get("verification_source")
        if not isinstance(sources, list) or len(sources) < 2 or any(not isinstance(item, str) for item in sources):
            issues.append(f"line {index}: at least two verification sources are required")
        if record.get("independent") is not True:
            issues.append(f"line {index}: independent must be true")
        if record.get("status") not in {"verified", "unresolved"}:
            issues.append(f"line {index}: invalid status")
        if (
            record.get("status") == "verified"
            and record.get("expected_pillars") is None
            and not isinstance(record.get("expected_error"), str)
        ):
            issues.append(f"line {index}: expected pillars or expected_error is required")
    if strict and len(records) < 50:
        issues.append(f"strict mode requires at least 50 benchmarks; found {len(records)}")
    return tuple(issues)


def benchmark_charts(path: Path, *, independent_only: bool = False) -> BenchmarkResult:
    engine = DeterministicBaziEngine()
    records = load_benchmarks(path)
    failures: list[str] = []
    passed = failed = unresolved = independent = agreements = agreement_total = 0
    category_counts: dict[str, dict[str, int]] = {}
    for record in records:
        if independent_only and record.get("independent") is not True:
            continue
        independent += int(record.get("independent") is True)
        category = str(record.get("category", "unknown"))
        counts = category_counts.setdefault(category, {"passed": 0, "failed": 0, "unresolved": 0})
        if record.get("status") == "unresolved":
            unresolved += 1
            counts["unresolved"] += 1
            continue
        agreement_total += 1
        agreements += int(record.get("source_agreement") is True)
        expected_error = record.get("expected_error")
        try:
            actual = engine.calculate(record["input"])
        except ChartCalculationError as exc:
            if expected_error == exc.code:
                passed += 1
                counts["passed"] += 1
            else:
                failed += 1
                counts["failed"] += 1
                failures.append(f"{record.get('id')}: unexpected {exc.code}; expected {expected_error or 'pillars'}")
            continue
        if expected_error:
            failed += 1
            counts["failed"] += 1
            failures.append(f"{record.get('id')}: expected error {expected_error}")
        elif actual["pillars"] == record.get("expected_pillars"):
            passed += 1
            counts["passed"] += 1
        else:
            failed += 1
            counts["failed"] += 1
            failures.append(f"{record.get('id')}: expected {record.get('expected_pillars')}, got {actual['pillars']}")
    return BenchmarkResult(
        total=passed + failed + unresolved,
        independent=independent,
        passed=passed,
        failed=failed,
        unresolved=unresolved,
        source_agreement=round(agreements / agreement_total, 6) if agreement_total else 0.0,
        categories=category_counts,
        failures=tuple(failures),
    )


def benchmark_file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
