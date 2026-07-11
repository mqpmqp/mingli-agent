"""Build the Phase 5 oracle fixture without importing the MingLi engine.

Requires the deliberately uncommitted verification tools:
    pip install sxtwl==2.0.7 lunar_python==1.4.8
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path

import sxtwl
from lunar_python import Lunar, Solar


STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
VERSIONS = {"sxtwl": "2.0.7", "lunar_python": "1.4.8", "HKO": "1901-2100 tables", "NOAA": "solareqns.PDF"}
HKO_CALENDAR = "Hong Kong Observatory Gregorian-Lunar Calendar Conversion Table"
HKO_STEMS = "Hong Kong Observatory Heavenly Stems and Earthly Branches Table 5"
NOAA = "NOAA General Solar Position Calculations"
OUTPUT = Path("tests/fixtures/bazi_independent_benchmarks_v0.1.jsonl")


def gz(value: object) -> str:
    return STEMS[value.tg] + BRANCHES[value.dz]


def oracle_pillars(moment: datetime) -> dict[str, str]:
    day = sxtwl.fromSolar(moment.year, moment.month, moment.day)
    eight = Solar.fromYmdHms(
        moment.year, moment.month, moment.day, moment.hour, moment.minute, moment.second
    ).getLunar().getEightChar()
    eight.setSect(2)
    day_pillar = gz(day.getDayGZ())
    if day_pillar != eight.getDay():
        raise RuntimeError(f"day oracle conflict at {moment}")
    return {
        "year": eight.getYear(),
        "month": eight.getMonth(),
        "day": day_pillar,
        "hour": gz(day.getHourGZ(moment.hour, False)),
    }


def base_input(moment: datetime, *, longitude: float = 116.4074, latitude: float = 39.9042) -> dict[str, object]:
    return {
        "gender": "male",
        "calendar": "solar",
        "birth_date": moment.date().isoformat(),
        "birth_time": moment.time().isoformat(),
        "timezone": "Asia/Shanghai",
        "longitude": longitude,
        "latitude": latitude,
        "true_solar_time": False,
    }


def record(
    case_id: str,
    category: str,
    input_data: dict[str, object],
    expected: dict[str, str] | None,
    sources: list[str],
    *,
    expected_error: str | None = None,
    status: str = "verified",
    source_agreement: bool = True,
    notes: str = "",
) -> dict[str, object]:
    item: dict[str, object] = {
        "id": case_id,
        "category": category,
        "input": input_data,
        "expected_pillars": expected,
        "verification_source": sources,
        "source_version": VERSIONS,
        "timezone": input_data.get("timezone"),
        "longitude": input_data.get("longitude"),
        "latitude": input_data.get("latitude"),
        "calendar_convention": "LiChun year boundary; twelve jie month boundaries",
        "day_boundary_convention": "00:00; no early/late Zi split",
        "solar_term_method": "sxtwl exact JieQi JD cross-checked with lunar_python and HKO dates",
        "independent": True,
        "status": status,
        "source_agreement": source_agreement,
        "notes": notes,
    }
    if expected_error is not None:
        item["expected_error"] = expected_error
    return item


def term_instants(year: int) -> list[tuple[int, str, datetime]]:
    names = {
        1: "xiaohan", 3: "lichun", 5: "jingzhe", 7: "qingming", 9: "lixia", 11: "mangzhong",
        13: "xiaoshu", 15: "liqiu", 17: "bailu", 19: "hanlu", 21: "lidong", 23: "daxue",
    }
    found: dict[tuple[int, int, int, int, int, int], tuple[int, str, datetime]] = {}
    for source_year in (year - 1, year):
        for item in sxtwl.getJieQiByYear(source_year):
            if item.jqIndex not in names:
                continue
            value = sxtwl.JD2DD(item.jd)
            if value.Y != year:
                continue
            moment = datetime(value.Y, value.M, value.D, int(value.h), int(value.m), int(value.s))
            key = (item.jqIndex, moment.year, moment.month, moment.day, moment.hour, moment.minute)
            found[key] = (item.jqIndex, names[item.jqIndex], moment)
    values = sorted(found.values(), key=lambda item: item[2])
    if len(values) != 12:
        raise RuntimeError(f"expected 12 jie in {year}, got {len(values)}")
    return values


def equation_of_time_minutes(moment: datetime) -> float:
    days = date(moment.year, 12, 31).timetuple().tm_yday
    gamma = 2 * math.pi / days * (
        moment.timetuple().tm_yday - 1 + (moment.hour + moment.minute / 60 - 12) / 24
    )
    return 229.18 * (
        0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma)
    )


def true_solar_expected(moment: datetime, longitude: float) -> tuple[dict[str, str], datetime]:
    correction = 4 * (longitude - 120) + equation_of_time_minutes(moment)
    corrected = moment + timedelta(minutes=correction)
    original = oracle_pillars(moment)
    shifted = oracle_pillars(corrected)
    return {"year": original["year"], "month": original["month"], "day": shifted["day"], "hour": shifted["hour"]}, corrected


def lunar_input(year: int, month: int, day: int, is_leap: bool) -> tuple[dict[str, object], dict[str, str]]:
    first = sxtwl.fromLunar(year, month, day, is_leap)
    second = Lunar.fromYmd(year, -month if is_leap else month, day).getSolar()
    solar_one = (first.getSolarYear(), first.getSolarMonth(), first.getSolarDay())
    solar_two = (second.getYear(), second.getMonth(), second.getDay())
    if solar_one != solar_two:
        raise RuntimeError(f"lunar conversion conflict: {solar_one} != {solar_two}")
    moment = datetime(*solar_one, 12)
    data = base_input(moment)
    data.update({"calendar": "lunar", "birth_date": f"{year:04}-{month:02}-{day:02}", "is_leap_month": is_leap})
    return data, oracle_pillars(moment)


def build() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for _, name, instant in term_instants(2024):
        for side, minutes in (("before", -30), ("after", 30)):
            moment = instant + timedelta(minutes=minutes)
            cases.append(record(
                f"jie_2024_{name}_{side}", "solar_term_boundary", base_input(moment), oracle_pillars(moment),
                ["sxtwl 2.0.7 exact JieQi JD", "lunar_python 1.4.8 exact EightChar", HKO_CALENDAR],
                notes=f"30 minutes {side} the independent sxtwl term instant {instant.isoformat()}",
            ))

    for case_id, moment in (
        ("day_boundary_2259", datetime(2000, 1, 7, 22, 59)),
        ("day_boundary_2300", datetime(2000, 1, 7, 23, 0)),
        ("day_boundary_0000", datetime(2000, 1, 8, 0, 0)),
        ("day_boundary_0100", datetime(2000, 1, 8, 1, 0)),
    ):
        cases.append(record(
            case_id, "day_boundary", base_input(moment), oracle_pillars(moment),
            ["sxtwl 2.0.7 isZaoWanZiShi=false", "lunar_python 1.4.8 sect=2 day pillar", HKO_STEMS],
        ))
    conflict_input = base_input(datetime(2000, 1, 7, 23, 0))
    cases.append(record(
        "day_boundary_2300_lunar_python_hour_conflict", "external_source_conflict", conflict_input, None,
        ["sxtwl 2.0.7 isZaoWanZiShi=false", "lunar_python 1.4.8 default hour pillar"],
        status="unresolved", source_agreement=False,
        notes="lunar_python advances the Zi-hour stem at 23:00 while the selected 00:00 convention does not; no automatic choice",
    ))

    for case_id, moment in (
        ("gregorian_year_1999_end", datetime(1999, 12, 31, 23, 59)),
        ("gregorian_year_2000_start", datetime(2000, 1, 1, 0, 1)),
        ("spring_festival_2024_before", datetime(2024, 2, 9, 23, 59)),
        ("spring_festival_2024_after", datetime(2024, 2, 10, 0, 1)),
    ):
        category = "spring_festival" if "spring" in case_id else "gregorian_year_boundary"
        cases.append(record(case_id, category, base_input(moment), oracle_pillars(moment), ["sxtwl 2.0.7", "lunar_python 1.4.8", HKO_CALENDAR]))

    for day in (1, 15, 29):
        data, expected = lunar_input(2023, 2, day, True)
        cases.append(record(f"valid_leap_month_2023_02_{day:02}", "lunar_leap_month", data, expected, ["sxtwl 2.0.7", "lunar_python 1.4.8", HKO_CALENDAR]))
    invalid_leap = base_input(datetime(2024, 3, 10, 12))
    invalid_leap.update({"calendar": "lunar", "birth_date": "2024-02-01", "is_leap_month": True})
    cases.append(record("invalid_leap_month_2024_02", "invalid_lunar_input", invalid_leap, None, ["sxtwl 2.0.7 leap-month table", "lunar_python 1.4.8 lunar-year table", HKO_CALENDAR], expected_error="INVALID_LEAP_MONTH"))
    invalid_day = dict(invalid_leap)
    invalid_day.update({"birth_date": "2023-02-30", "is_leap_month": True})
    cases.append(record("invalid_leap_month_day_2023_02_30", "invalid_lunar_input", invalid_day, None, ["sxtwl 2.0.7 month-length table", "lunar_python 1.4.8 lunar-year table", HKO_CALENDAR], expected_error="INVALID_LUNAR_DATE"))

    solar_locations = (
        ("shanghai_west_shift", datetime(2024, 2, 20, 1, 5), 121.4737, 31.2304),
        ("chengdu_west_shift", datetime(2024, 6, 18, 1, 30), 104.0665, 30.5728),
        ("urumqi_west_shift", datetime(2024, 9, 10, 3, 0), 87.6168, 43.8256),
        ("fuyuan_east_shift", datetime(2024, 11, 15, 0, 50), 134.3079, 48.3647),
    )
    for case_id, moment, longitude, latitude in solar_locations:
        expected, corrected = true_solar_expected(moment, longitude)
        data = base_input(moment, longitude=longitude, latitude=latitude)
        data["true_solar_time"] = True
        cases.append(record(
            case_id, "true_solar_time", data, expected,
            [NOAA, "sxtwl 2.0.7 applied to independently corrected time", "lunar_python 1.4.8 cross-check"],
            notes=f"independent NOAA correction produces {corrected.isoformat()}",
        ))
    missing = base_input(datetime(2024, 6, 18, 12))
    missing.pop("longitude")
    missing["true_solar_time"] = True
    cases.append(record("true_solar_missing_longitude", "true_solar_time_contract", missing, None, [NOAA, "Phase 5 calculation convention"], expected_error="MISSING_LONGITUDE"))

    for year in (1901, 1950, 2000, 2050, 2099):
        moment = datetime(year, 7, 15, 12)
        cases.append(record(f"supported_year_{year}", "supported_year", base_input(moment), oracle_pillars(moment), ["sxtwl 2.0.7", "lunar_python 1.4.8", HKO_CALENDAR]))
    for year in (1900, 2100):
        moment = datetime(year, 7, 15, 12)
        cases.append(record(f"unsupported_year_{year}", "unsupported_year", base_input(moment), None, [HKO_CALENDAR, "Phase 5 supported-range contract"], expected_error="UNSUPPORTED_YEAR"))

    for case_id, zone in (("fixed_offset_timezone", "+08:00"), ("iana_timezone", "Asia/Shanghai")):
        moment = datetime(2024, 8, 20, 14)
        data = base_input(moment)
        data["timezone"] = zone
        cases.append(record(case_id, "timezone", data, oracle_pillars(moment), ["sxtwl 2.0.7", "lunar_python 1.4.8"]))
    return cases


def main() -> None:
    cases = build()
    if len(cases) < 50:
        raise RuntimeError(f"expected at least 50 cases, got {len(cases)}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in cases), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "cases": len(cases)}, sort_keys=True))


if __name__ == "__main__":
    main()
