from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from mingli.contracts import get_schema
from mingli.ziwei import build_ziwei_chart
from mingli.ziwei_benchmark import run_ziwei_engine_benchmarks
from mingli.ziwei_engine import (
    AUXILIARY_STAR_IDS,
    PALACE_BRANCHES,
    PRIMARY_STAR_IDS,
    calculate_bureau,
    calculate_life_body_palaces,
    four_transformations,
    place_auxiliary_stars,
    place_primary_stars,
)


def lunar_birth(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "calendar_type": "lunar",
        "birth_date": "1984-01-13",
        "birth_time": "00:30",
        "timezone": "Asia/Shanghai",
        "longitude": 121.4737,
        "latitude": 31.2304,
        "solar_time_mode": "civil",
        "late_zi_policy": "midnight",
        "leap_month": False,
        "gender": "male",
    }
    value.update(overrides)
    return value


def star_branches(chart: dict[str, object], field: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for palace in chart["palaces"]:
        assert isinstance(palace, dict)
        branch = palace["earthly_branch"]
        assert isinstance(branch, str)
        stars = palace[field]
        assert isinstance(stars, list)
        for star in stars:
            assert isinstance(star, dict)
            result[str(star["star_id"])] = branch
    return result


def test_life_and_body_formula_covers_every_month_hour_pair() -> None:
    seen_life: set[int] = set()
    seen_body: set[int] = set()
    for lunar_month in range(1, 13):
        for shichen_index in range(12):
            life, body = calculate_life_body_palaces(lunar_month, shichen_index)
            assert life == (lunar_month - 1 - shichen_index) % 12
            assert body == (lunar_month - 1 + shichen_index) % 12
            seen_life.add(life)
            seen_body.add(body)
    assert seen_life == set(range(12))
    assert seen_body == set(range(12))


def test_five_bureaus_are_derived_from_year_stem_and_life_palace() -> None:
    expected = {
        "甲": ("火", 6, "火六局", "丙"),
        "乙": ("土", 5, "土五局", "戊"),
        "丙": ("木", 3, "木三局", "庚"),
        "丁": ("金", 4, "金四局", "壬"),
        "戊": ("水", 2, "水二局", "甲"),
    }
    for year_stem, values in expected.items():
        bureau = calculate_bureau(year_stem, 0)
        assert (
            bureau["element"],
            bureau["number"],
            bureau["label"],
            bureau["life_palace_stem"],
        ) == values
        assert bureau["life_palace_branch"] == "寅"


def test_reviewed_ziwei_formula_anchors_match_source_examples() -> None:
    assert place_primary_stars(27, 3)["ziwei"] == "戌"
    assert place_primary_stars(13, 6)["ziwei"] == "亥"
    assert place_primary_stars(6, 5)["ziwei"] == "未"


def test_primary_placement_properties_cover_all_days_and_bureaus() -> None:
    for bureau_number in (2, 3, 4, 5, 6):
        for lunar_day in range(1, 31):
            stars = place_primary_stars(lunar_day, bureau_number)
            assert set(stars) == set(PRIMARY_STAR_IDS)
            assert len(stars) == 14
            assert set(stars.values()).issubset(PALACE_BRANCHES)
            ziwei_index = PALACE_BRANCHES.index(stars["ziwei"])
            tianfu_index = PALACE_BRANCHES.index(stars["tianfu"])
            assert tianfu_index == (-ziwei_index) % 12


def test_auxiliary_stars_and_four_transformations_are_complete() -> None:
    stars = place_auxiliary_stars("甲", "子", 1, 0)
    assert set(stars) == set(AUXILIARY_STAR_IDS)
    assert stars == {
        "zuofu": "辰",
        "youbi": "戌",
        "wenchang": "戌",
        "wenqu": "辰",
        "tiankui": "丑",
        "tianyue": "未",
        "lucun": "寅",
        "tianma": "寅",
        "dikong": "亥",
        "dijie": "亥",
        "huoxing": "寅",
        "lingxing": "戌",
        "qingyang": "卯",
        "tuoluo": "丑",
    }
    assert four_transformations("甲") == {
        "lu": "lianzhen",
        "quan": "pojun",
        "ke": "wuqu",
        "ji": "taiyang",
    }
    for stem in "甲乙丙丁戊己庚辛壬癸":
        transformations = four_transformations(stem)
        assert set(transformations) == {"lu", "quan", "ke", "ji"}
        assert len(set(transformations.values())) == 4


def test_known_time_builds_complete_versioned_chart_with_exact_jiazi_fixture() -> None:
    chart = build_ziwei_chart(lunar_birth())

    assert chart["schema_version"] == "ziwei-chart@1.0"
    assert chart["method_id"] == "ziwei-traditional-natal@1.0.0"
    assert chart["algorithm_version"] == "ziwei-traditional-natal@1.0.0"
    assert chart["calculation_status"] == "complete"
    assert chart["life_palace"] == 0
    assert chart["body_palace"] == 0
    assert chart["unsupported_fields"] == []
    assert chart["bureau"] == {
        "element": "火",
        "number": 6,
        "label": "火六局",
        "life_palace_stem": "丙",
        "life_palace_branch": "寅",
        "field_status": "supported",
        "source_provenance": [
            "classical:ziwei-doushu-quanji-placement",
            "oss:iztro@f3dc6c5",
        ],
    }
    assert chart["placement_lunar_date"] == {
        "year": 1984,
        "month": 1,
        "day": 13,
        "leap_month": False,
        "year_stem": "甲",
        "year_branch": "子",
    }
    assert [(p["palace_name"], p["earthly_branch"]) for p in chart["palaces"]] == [
        ("命宫", "寅"),
        ("父母宫", "卯"),
        ("福德宫", "辰"),
        ("田宅宫", "巳"),
        ("官禄宫", "午"),
        ("交友宫", "未"),
        ("迁移宫", "申"),
        ("疾厄宫", "酉"),
        ("财帛宫", "戌"),
        ("子女宫", "亥"),
        ("夫妻宫", "子"),
        ("兄弟宫", "丑"),
    ]
    assert star_branches(chart, "primary_stars") == {
        "ziwei": "亥",
        "tianji": "戌",
        "taiyang": "申",
        "wuqu": "未",
        "tiantong": "午",
        "lianzhen": "卯",
        "tianfu": "巳",
        "taiyin": "午",
        "tanlang": "未",
        "jumen": "申",
        "tianxiang": "酉",
        "tianliang": "戌",
        "qisha": "亥",
        "pojun": "卯",
    }
    auxiliary = {
        **star_branches(chart, "supporting_stars"),
        **star_branches(chart, "malefic_stars"),
    }
    assert auxiliary == place_auxiliary_stars("甲", "子", 1, 0)
    transformations = {
        item["transformation"]: (item["star_id"], palace["earthly_branch"])
        for palace in chart["palaces"]
        for item in palace["transformations"]
    }
    assert transformations == {
        "lu": ("lianzhen", "卯"),
        "quan": ("pojun", "卯"),
        "ke": ("wuqu", "未"),
        "ji": ("taiyang", "申"),
    }
    assert chart["algorithm_profile"]["leap_month_policy"] == "same_numeric_month"
    assert chart["algorithm_profile"]["year_boundary"] == "lunar_new_year"
    assert chart["algorithm_profile"]["transformation_profile"] == "ziwei-doushu-quanji"


def test_table_driven_properties_stay_in_domain_for_all_supported_inputs() -> None:
    labels: set[str] = set()
    for year_stem in "甲乙丙丁戊己庚辛壬癸":
        for life_index in range(12):
            bureau = calculate_bureau(year_stem, life_index)
            assert bureau["number"] in {2, 3, 4, 5, 6}
            assert bureau["life_palace_branch"] == PALACE_BRANCHES[life_index]
            labels.add(str(bureau["label"]))
        for year_branch in "子丑寅卯辰巳午未申酉戌亥":
            for lunar_month in range(1, 13):
                for shichen_index in range(12):
                    stars = place_auxiliary_stars(
                        year_stem, year_branch, lunar_month, shichen_index
                    )
                    assert set(stars) == set(AUXILIARY_STAR_IDS)
                    assert set(stars.values()).issubset(PALACE_BRANCHES)
    assert labels == {"水二局", "木三局", "金四局", "土五局", "火六局"}


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: calculate_life_body_palaces(0, 0), "lunar_month"),
        (lambda: calculate_life_body_palaces(1, 12), "shichen_index"),
        (lambda: calculate_bureau("?", 0), "heavenly stem"),
        (lambda: place_primary_stars(0, 2), "lunar_day"),
        (lambda: place_primary_stars(1, 1), "bureau_number"),
        (lambda: place_auxiliary_stars("甲", "?", 1, 0), "earthly branch"),
        (lambda: four_transformations("?"), "heavenly stem"),
    ],
)
def test_pure_engine_rejects_out_of_domain_inputs(call, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        call()


def test_complete_chart_and_nested_objects_validate_against_schemas() -> None:
    chart = build_ziwei_chart(lunar_birth())
    Draft202012Validator(get_schema("ziwei_chart.schema.json")).validate(chart)
    palace_validator = Draft202012Validator(get_schema("ziwei_palace.schema.json"))
    star_validator = Draft202012Validator(get_schema("ziwei_star.schema.json"))
    transformation_validator = Draft202012Validator(
        get_schema("ziwei_transformation.schema.json")
    )
    brightness_validator = Draft202012Validator(get_schema("ziwei_brightness.schema.json"))
    for palace in chart["palaces"]:
        palace_validator.validate(palace)
        for field in ("primary_stars", "supporting_stars", "malefic_stars"):
            for star in palace[field]:
                star_validator.validate(star)
        for transformation in palace["transformations"]:
            transformation_validator.validate(transformation)
        for brightness in palace["brightness_state"]:
            brightness_validator.validate(brightness)


def test_brightness_normalization_preserves_seven_level_source_order() -> None:
    chart = build_ziwei_chart(lunar_birth())
    brightness = {
        item["star_id"]: (item["state"], item["source_value"])
        for palace in chart["palaces"]
        for item in palace["brightness_state"]
    }
    assert brightness["ziwei"] == ("prosperous", "旺")
    assert brightness["lianzhen"] == ("weak", "平")
    assert brightness["taiyin"] == ("unfavorable", "不")
    assert brightness["tiantong"] == ("fallen", "陷")


def test_fixed_engine_benchmark_covers_all_five_bureaus() -> None:
    report = run_ziwei_engine_benchmarks()
    assert report["schema_version"] == "ziwei-engine-benchmark-report@1.0"
    assert report["total_cases"] == 5
    assert report["passed_cases"] == 5
    assert report["failed_cases"] == 0
    assert set(report["covered_bureaus"]) == {"水二局", "木三局", "金四局", "土五局", "火六局"}
    assert report["prediction_validity"] == "not_evaluated"
