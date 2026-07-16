from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator, ValidationError

from mingli.contracts import get_schema
from mingli.ziwei import (
    ZIWEI_ALGORITHM_VERSION,
    ZiweiContractError,
    build_temporal_context,
    build_ziwei_chart,
    normalize_ziwei_birth,
)


def birth(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "calendar_type": "solar",
        "birth_date": "2023-03-22",
        "birth_time": "01:30",
        "timezone": "Asia/Shanghai",
        "longitude": 104.0665,
        "latitude": 30.5728,
        "solar_time_mode": "civil",
        "late_zi_policy": "midnight",
        "gender": "male",
    }
    value.update(overrides)
    return value


def test_solar_and_equivalent_lunar_inputs_share_chart_identity() -> None:
    solar = build_ziwei_chart(birth())
    lunar = build_ziwei_chart(
        birth(calendar_type="lunar", birth_date="2023-02-01", leap_month=True)
    )

    assert solar["time_correction"]["solar_date"] == "2023-03-22"
    assert lunar["time_correction"]["solar_date"] == "2023-03-22"
    assert solar["chart_fingerprint"] == lunar["chart_fingerprint"]


def test_solar_time_components_are_separate_and_apparent_can_cross_shichen() -> None:
    civil = normalize_ziwei_birth(birth())
    mean = normalize_ziwei_birth(birth(solar_time_mode="local_mean"))
    apparent = normalize_ziwei_birth(birth(solar_time_mode="apparent_solar"))

    assert civil["longitude_correction_minutes"] == 0
    assert civil["equation_of_time_applied"] is False
    assert mean["longitude_correction_minutes"] < -60
    assert mean["equation_of_time_minutes"] == 0
    assert apparent["longitude_correction_minutes"] == mean["longitude_correction_minutes"]
    assert apparent["equation_of_time_applied"] is True
    assert apparent["equation_of_time_minutes"] != 0
    assert civil["shichen_index"] != apparent["shichen_index"]


def test_apparent_solar_time_can_cross_civil_day_without_losing_input() -> None:
    value = normalize_ziwei_birth(
        birth(
            birth_date="2024-06-18",
            birth_time="00:20",
            longitude=74.0,
            solar_time_mode="apparent_solar",
        )
    )

    assert value["input_datetime"].startswith("2024-06-18T00:20")
    assert value["corrected_datetime"].startswith("2024-06-17T")
    assert value["crossed_civil_day"] is True


def test_late_zi_policy_is_explicit_and_changes_chart_day() -> None:
    midnight = normalize_ziwei_birth(birth(birth_time="23:30", late_zi_policy="midnight"))
    next_day = normalize_ziwei_birth(birth(birth_time="23:30", late_zi_policy="late_zi_next_day"))

    assert midnight["chart_date"] == "2023-03-22"
    assert next_day["chart_date"] == "2023-03-23"
    assert build_ziwei_chart(birth(birth_time="23:30"))["chart_fingerprint"] != build_ziwei_chart(
        birth(birth_time="23:30", late_zi_policy="late_zi_next_day")
    )["chart_fingerprint"]


def test_unknown_birth_time_degrades_without_defaulting_to_a_shichen() -> None:
    chart = build_ziwei_chart(birth(birth_time=None, birth_time_known=False))

    assert chart["calculation_status"] == "degraded"
    assert chart["time_correction"]["corrected_datetime"] is None
    assert chart["time_correction"]["shichen_index"] is None
    assert "birth_time" in chart["unsupported_fields"]
    assert all(palace["primary_stars"] == [] for palace in chart["palaces"])


def test_partial_chart_has_twelve_explicit_unsupported_palaces_and_stable_json() -> None:
    first = build_ziwei_chart(birth(name="Alice", display_age=20))
    second = build_ziwei_chart(birth(name="Bob", display_age=99))

    assert first["calculation_status"] == "partial"
    assert len(first["palaces"]) == 12
    assert [item["palace_index"] for item in first["palaces"]] == list(range(12))
    assert first["chart_fingerprint"] == second["chart_fingerprint"]
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        build_ziwei_chart(birth(name="Alice", display_age=20)), ensure_ascii=False, sort_keys=True
    )
    assert first["algorithm_version"] == ZIWEI_ALGORITHM_VERSION
    assert {"life_palace", "body_palace", "bureau", "primary_stars"}.issubset(
        first["unsupported_fields"]
    )


def test_algorithm_version_participates_in_fingerprint() -> None:
    current = build_ziwei_chart(birth())
    changed = build_ziwei_chart(birth(), algorithm_version="ziwei-contracts@99")
    assert current["chart_fingerprint"] != changed["chart_fingerprint"]


def test_temporal_context_requires_complete_parent_context() -> None:
    assert build_temporal_context("natal") == {"level": "natal"}
    assert build_temporal_context("annual", year=2028)["year"] == 2028
    monthly = build_temporal_context("monthly", year=2028, month=4, leap_month=True)
    assert monthly == {"level": "monthly", "year": 2028, "month": 4, "leap_month": True}
    daily = build_temporal_context("daily", date="2028-04-03")
    assert daily["date"] == "2028-04-03"
    hourly = build_temporal_context(
        "hourly", datetime="2028-04-03T10:15:00+08:00", timezone="Asia/Shanghai"
    )
    assert hourly["datetime"].endswith("+08:00")

    with pytest.raises(ZiweiContractError, match="year and month"):
        build_temporal_context("monthly", month=4)
    with pytest.raises(ZiweiContractError, match="timezone-aware"):
        build_temporal_context("hourly", datetime="2028-04-03T10:15:00", timezone="Asia/Shanghai")


def test_schema_bundle_accepts_partial_chart_and_rejects_invalid_values() -> None:
    birth_schema = get_schema("ziwei_birth_input.schema.json")
    chart_schema = get_schema("ziwei_chart.schema.json")
    Draft202012Validator(birth_schema).validate(birth())
    Draft202012Validator(chart_schema).validate(build_ziwei_chart(birth()))

    with pytest.raises(ValidationError):
        Draft202012Validator(birth_schema).validate([])
    with pytest.raises(ValidationError):
        Draft202012Validator(birth_schema).validate(birth(solar_time_mode="guess"))
    with pytest.raises(ValidationError):
        Draft202012Validator(chart_schema).validate({"calculation_status": "complete"})


def test_invalid_leap_month_and_missing_longitude_fail_explicitly() -> None:
    with pytest.raises(ZiweiContractError, match="leap_month"):
        normalize_ziwei_birth(birth(leap_month=True))
    with pytest.raises(ZiweiContractError, match="longitude"):
        normalize_ziwei_birth(birth(longitude=None, solar_time_mode="apparent_solar"))
