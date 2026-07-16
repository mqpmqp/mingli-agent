from __future__ import annotations

from datetime import date
from typing import Mapping

from .phase19 import solar_to_lunar

ZIWEI_ENGINE_VERSION = "ziwei-traditional-natal@1.0.0"
CLASSICAL_SOURCE_ID = "classical:ziwei-doushu-quanji-placement"
CROSS_CHECK_SOURCE_ID = "oss:iztro@f3dc6c5"
FULL_CROSS_CHECK_SOURCE_ID = "oss:iztro@f3dc6c547420b063109251d7c7132fa3cb41e06e"

HEAVENLY_STEMS = tuple("甲乙丙丁戊己庚辛壬癸")
EARTHLY_BRANCHES = tuple("子丑寅卯辰巳午未申酉戌亥")
PALACE_BRANCHES = tuple("寅卯辰巳午未申酉戌亥子丑")
PALACE_NAMES = (
    "命宫",
    "兄弟宫",
    "夫妻宫",
    "子女宫",
    "财帛宫",
    "疾厄宫",
    "迁移宫",
    "交友宫",
    "官禄宫",
    "田宅宫",
    "福德宫",
    "父母宫",
)

PRIMARY_STAR_NAMES = {
    "ziwei": "紫微",
    "tianji": "天机",
    "taiyang": "太阳",
    "wuqu": "武曲",
    "tiantong": "天同",
    "lianzhen": "廉贞",
    "tianfu": "天府",
    "taiyin": "太阴",
    "tanlang": "贪狼",
    "jumen": "巨门",
    "tianxiang": "天相",
    "tianliang": "天梁",
    "qisha": "七杀",
    "pojun": "破军",
}
PRIMARY_STAR_IDS = tuple(PRIMARY_STAR_NAMES)

SUPPORTING_STAR_NAMES = {
    "zuofu": "左辅",
    "youbi": "右弼",
    "wenchang": "文昌",
    "wenqu": "文曲",
    "tiankui": "天魁",
    "tianyue": "天钺",
    "lucun": "禄存",
    "tianma": "天马",
}
MALEFIC_STAR_NAMES = {
    "dikong": "地空",
    "dijie": "地劫",
    "huoxing": "火星",
    "lingxing": "铃星",
    "qingyang": "擎羊",
    "tuoluo": "陀罗",
}
AUXILIARY_STAR_NAMES = {**SUPPORTING_STAR_NAMES, **MALEFIC_STAR_NAMES}
AUXILIARY_STAR_IDS = tuple(AUXILIARY_STAR_NAMES)

TIGER_RULE = {
    "甲": "丙",
    "乙": "戊",
    "丙": "庚",
    "丁": "壬",
    "戊": "甲",
    "己": "丙",
    "庚": "戊",
    "辛": "庚",
    "壬": "壬",
    "癸": "甲",
}

TRANSFORMATION_TABLE = {
    "甲": ("lianzhen", "pojun", "wuqu", "taiyang"),
    "乙": ("tianji", "tianliang", "ziwei", "taiyin"),
    "丙": ("tiantong", "tianji", "wenchang", "lianzhen"),
    "丁": ("taiyin", "tiantong", "tianji", "jumen"),
    "戊": ("tanlang", "taiyin", "youbi", "tianji"),
    "己": ("wuqu", "tanlang", "tianliang", "wenqu"),
    "庚": ("taiyang", "wuqu", "taiyin", "tiantong"),
    "辛": ("jumen", "taiyang", "wenqu", "wenchang"),
    "壬": ("tianliang", "ziwei", "zuofu", "wuqu"),
    "癸": ("pojun", "jumen", "taiyin", "tanlang"),
}

_BRIGHTNESS_CODES = {
    "ziwei": ("wang", "wang", "de", "wang", "miao", "miao", "wang", "wang", "de", "wang", "ping", "miao"),
    "tianji": ("de", "wang", "li", "ping", "miao", "xian", "de", "wang", "li", "ping", "miao", "xian"),
    "taiyang": ("wang", "miao", "wang", "wang", "wang", "de", "de", "xian", "bu", "xian", "xian", "bu"),
    "wuqu": ("de", "li", "miao", "ping", "wang", "miao", "de", "li", "miao", "ping", "wang", "miao"),
    "tiantong": ("li", "ping", "ping", "miao", "xian", "bu", "wang", "ping", "ping", "miao", "wang", "bu"),
    "lianzhen": ("miao", "ping", "li", "xian", "ping", "li", "miao", "ping", "li", "xian", "ping", "li"),
    "tianfu": ("miao", "de", "miao", "de", "wang", "miao", "de", "wang", "miao", "de", "miao", "miao"),
    "taiyin": ("wang", "xian", "xian", "xian", "bu", "bu", "li", "bu", "wang", "miao", "miao", "miao"),
    "tanlang": ("ping", "li", "miao", "xian", "wang", "miao", "ping", "li", "miao", "xian", "wang", "miao"),
    "jumen": ("miao", "miao", "xian", "wang", "wang", "bu", "miao", "miao", "xian", "wang", "wang", "bu"),
    "tianxiang": ("miao", "xian", "de", "de", "miao", "de", "miao", "xian", "de", "de", "miao", "miao"),
    "tianliang": ("miao", "miao", "miao", "xian", "miao", "wang", "xian", "de", "miao", "xian", "miao", "wang"),
    "qisha": ("miao", "wang", "miao", "ping", "wang", "miao", "miao", "miao", "miao", "ping", "wang", "miao"),
    "pojun": ("de", "xian", "wang", "ping", "miao", "wang", "de", "xian", "wang", "ping", "miao", "wang"),
    "wenchang": ("xian", "li", "de", "miao", "xian", "li", "de", "miao", "xian", "li", "de", "miao"),
    "wenqu": ("ping", "wang", "de", "miao", "xian", "wang", "de", "miao", "xian", "wang", "de", "miao"),
    "huoxing": ("miao", "li", "xian", "de", "miao", "li", "xian", "de", "miao", "li", "xian", "de"),
    "lingxing": ("miao", "li", "xian", "de", "miao", "li", "xian", "de", "miao", "li", "xian", "de"),
    "qingyang": ("", "xian", "miao", "", "xian", "miao", "", "xian", "miao", "", "xian", "miao"),
    "tuoluo": ("xian", "", "miao", "xian", "", "miao", "xian", "", "miao", "xian", "", "miao"),
}
_BRIGHTNESS_NORMALIZATION = {
    "miao": ("temple", "庙"),
    "wang": ("prosperous", "旺"),
    "de": ("beneficial", "得"),
    "li": ("neutral", "利"),
    "ping": ("weak", "平"),
    "bu": ("unfavorable", "不"),
    "xian": ("fallen", "陷"),
}

ALGORITHM_PROFILE = {
    "profile_id": ZIWEI_ENGINE_VERSION,
    "calendar_basis": "canonical_lunar_after_time_correction",
    "year_boundary": "lunar_new_year",
    "leap_month_policy": "same_numeric_month",
    "late_zi_policy": "input_selected",
    "palace_ring": "yin_clockwise",
    "transformation_profile": "ziwei-doushu-quanji",
    "brightness_profile": FULL_CROSS_CHECK_SOURCE_ID,
}


def _require_index(value: object, *, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def _palace_index(branch: str) -> int:
    try:
        return PALACE_BRANCHES.index(branch)
    except ValueError as exc:
        raise ValueError(f"unknown earthly branch: {branch}") from exc


def _year_stem_branch(lunar_year: int) -> tuple[str, str]:
    if isinstance(lunar_year, bool) or not isinstance(lunar_year, int):
        raise ValueError("lunar_year must be an integer")
    return HEAVENLY_STEMS[(lunar_year - 4) % 10], EARTHLY_BRANCHES[(lunar_year - 4) % 12]


def calculate_life_body_palaces(lunar_month: int, shichen_index: int) -> tuple[int, int]:
    month = _require_index(lunar_month, name="lunar_month", low=1, high=12)
    hour = _require_index(shichen_index, name="shichen_index", low=0, high=11)
    month_index = month - 1
    return (month_index - hour) % 12, (month_index + hour) % 12


def calculate_bureau(year_stem: str, life_palace_index: int) -> dict[str, object]:
    if year_stem not in TIGER_RULE:
        raise ValueError(f"unknown heavenly stem: {year_stem}")
    life_index = _require_index(life_palace_index, name="life_palace_index", low=0, high=11)
    start_stem = TIGER_RULE[year_stem]
    life_stem = HEAVENLY_STEMS[(HEAVENLY_STEMS.index(start_stem) + life_index) % 10]
    life_branch = PALACE_BRANCHES[life_index]
    stem_number = HEAVENLY_STEMS.index(life_stem) // 2 + 1
    branch_number = (EARTHLY_BRANCHES.index(life_branch) % 6) // 2 + 1
    nayin_number = stem_number + branch_number
    if nayin_number > 5:
        nayin_number -= 5
    element, bureau_number = {
        1: ("木", 3),
        2: ("金", 4),
        3: ("水", 2),
        4: ("火", 6),
        5: ("土", 5),
    }[nayin_number]
    return {
        "element": element,
        "number": bureau_number,
        "label": f"{element}{'二三四五六'[bureau_number - 2]}局",
        "life_palace_stem": life_stem,
        "life_palace_branch": life_branch,
        "field_status": "supported",
        "source_provenance": [CLASSICAL_SOURCE_ID, CROSS_CHECK_SOURCE_ID],
    }


def place_primary_stars(lunar_day: int, bureau_number: int) -> dict[str, str]:
    day = _require_index(lunar_day, name="lunar_day", low=1, high=30)
    bureau = _require_index(bureau_number, name="bureau_number", low=2, high=6)
    if bureau not in {2, 3, 4, 5, 6}:
        raise ValueError("bureau_number must be one of 2, 3, 4, 5, 6")
    offset = 0
    while (day + offset) % bureau:
        offset += 1
    quotient = (day + offset) // bureau
    ziwei_index = (quotient - 1 + (offset if offset % 2 == 0 else -offset)) % 12
    tianfu_index = (-ziwei_index) % 12
    positions = {
        "ziwei": ziwei_index,
        "tianji": ziwei_index - 1,
        "taiyang": ziwei_index - 3,
        "wuqu": ziwei_index - 4,
        "tiantong": ziwei_index - 5,
        "lianzhen": ziwei_index - 8,
        "tianfu": tianfu_index,
        "taiyin": tianfu_index + 1,
        "tanlang": tianfu_index + 2,
        "jumen": tianfu_index + 3,
        "tianxiang": tianfu_index + 4,
        "tianliang": tianfu_index + 5,
        "qisha": tianfu_index + 6,
        "pojun": tianfu_index + 10,
    }
    return {star_id: PALACE_BRANCHES[index % 12] for star_id, index in positions.items()}


def place_auxiliary_stars(
    year_stem: str,
    year_branch: str,
    lunar_month: int,
    shichen_index: int,
) -> dict[str, str]:
    if year_stem not in HEAVENLY_STEMS:
        raise ValueError(f"unknown heavenly stem: {year_stem}")
    if year_branch not in EARTHLY_BRANCHES:
        raise ValueError(f"unknown earthly branch: {year_branch}")
    month = _require_index(lunar_month, name="lunar_month", low=1, high=12)
    hour = _require_index(shichen_index, name="shichen_index", low=0, high=11)

    kui_yue = {
        "甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
        "乙": ("子", "申"), "己": ("子", "申"),
        "辛": ("午", "寅"),
        "丙": ("亥", "酉"), "丁": ("亥", "酉"),
        "壬": ("卯", "巳"), "癸": ("卯", "巳"),
    }[year_stem]
    lucun_branch = {
        "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
        "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
    }[year_stem]
    if year_branch in {"寅", "午", "戌"}:
        tianma, huo_start, ling_start = "申", "丑", "卯"
    elif year_branch in {"申", "子", "辰"}:
        tianma, huo_start, ling_start = "寅", "寅", "戌"
    elif year_branch in {"巳", "酉", "丑"}:
        tianma, huo_start, ling_start = "亥", "卯", "戌"
    else:
        tianma, huo_start, ling_start = "巳", "酉", "戌"
    lu_index = _palace_index(lucun_branch)
    positions = {
        "zuofu": _palace_index("辰") + month - 1,
        "youbi": _palace_index("戌") - month + 1,
        "wenchang": _palace_index("戌") - hour,
        "wenqu": _palace_index("辰") + hour,
        "tiankui": _palace_index(kui_yue[0]),
        "tianyue": _palace_index(kui_yue[1]),
        "lucun": lu_index,
        "tianma": _palace_index(tianma),
        "dikong": _palace_index("亥") - hour,
        "dijie": _palace_index("亥") + hour,
        "huoxing": _palace_index(huo_start) + hour,
        "lingxing": _palace_index(ling_start) + hour,
        "qingyang": lu_index + 1,
        "tuoluo": lu_index - 1,
    }
    return {star_id: PALACE_BRANCHES[index % 12] for star_id, index in positions.items()}


def four_transformations(year_stem: str) -> dict[str, str]:
    try:
        stars = TRANSFORMATION_TABLE[year_stem]
    except KeyError as exc:
        raise ValueError(f"unknown heavenly stem: {year_stem}") from exc
    return dict(zip(("lu", "quan", "ke", "ji"), stars, strict=True))


def _star_record(star_id: str, category: str) -> dict[str, object]:
    names = PRIMARY_STAR_NAMES if category == "primary" else AUXILIARY_STAR_NAMES
    return {
        "star_id": star_id,
        "star_name": names[star_id],
        "category": category,
        "field_status": "supported",
        "source_provenance": [CLASSICAL_SOURCE_ID, CROSS_CHECK_SOURCE_ID],
    }


def _brightness_record(star_id: str, palace_index: int) -> dict[str, object] | None:
    codes = _BRIGHTNESS_CODES.get(star_id)
    if codes is None or not codes[palace_index]:
        return None
    code = codes[palace_index]
    state, source_value = _BRIGHTNESS_NORMALIZATION[code]
    return {
        "star_id": star_id,
        "state": state,
        "source_value": source_value,
        "field_status": "supported",
        "source_provenance": [FULL_CROSS_CHECK_SOURCE_ID],
    }


def build_traditional_ziwei(normalized: Mapping[str, object]) -> dict[str, object]:
    shichen_index = normalized.get("shichen_index")
    if isinstance(shichen_index, bool) or not isinstance(shichen_index, int):
        raise ValueError("known birth time requires shichen_index")
    raw_chart_date = normalized.get("chart_date")
    if not isinstance(raw_chart_date, str):
        raise ValueError("normalized chart_date is required")
    lunar = solar_to_lunar(date.fromisoformat(raw_chart_date))
    year_stem, year_branch = _year_stem_branch(lunar.year)
    life_index, body_index = calculate_life_body_palaces(lunar.month, shichen_index)
    bureau = calculate_bureau(year_stem, life_index)
    bureau_number = bureau["number"]
    assert isinstance(bureau_number, int)
    primary = place_primary_stars(lunar.day, bureau_number)
    auxiliary = place_auxiliary_stars(year_stem, year_branch, lunar.month, shichen_index)
    transformations = four_transformations(year_stem)

    primary_by_branch: dict[str, list[dict[str, object]]] = {branch: [] for branch in PALACE_BRANCHES}
    supporting_by_branch: dict[str, list[dict[str, object]]] = {branch: [] for branch in PALACE_BRANCHES}
    malefic_by_branch: dict[str, list[dict[str, object]]] = {branch: [] for branch in PALACE_BRANCHES}
    for star_id, branch in primary.items():
        primary_by_branch[branch].append(_star_record(star_id, "primary"))
    for star_id, branch in auxiliary.items():
        category = "supporting" if star_id in SUPPORTING_STAR_NAMES else "malefic"
        target = supporting_by_branch if category == "supporting" else malefic_by_branch
        target[branch].append(_star_record(star_id, category))

    star_branches = {**primary, **auxiliary}
    transformations_by_branch: dict[str, list[dict[str, object]]] = {
        branch: [] for branch in PALACE_BRANCHES
    }
    for transformation, star_id in transformations.items():
        transformations_by_branch[star_branches[star_id]].append(
            {
                "transformation": transformation,
                "star_id": star_id,
                "field_status": "supported",
                "source_provenance": [CLASSICAL_SOURCE_ID, CROSS_CHECK_SOURCE_ID],
            }
        )

    start_stem_index = HEAVENLY_STEMS.index(TIGER_RULE[year_stem])
    palaces: list[dict[str, object]] = []
    for palace_index, branch in enumerate(PALACE_BRANCHES):
        star_ids = [
            *(item["star_id"] for item in primary_by_branch[branch]),
            *(item["star_id"] for item in supporting_by_branch[branch]),
            *(item["star_id"] for item in malefic_by_branch[branch]),
        ]
        brightness = [
            record
            for star_id in star_ids
            if (record := _brightness_record(str(star_id), palace_index)) is not None
        ]
        palaces.append(
            {
                "palace_index": palace_index,
                "palace_name": PALACE_NAMES[(life_index - palace_index) % 12],
                "heavenly_stem": HEAVENLY_STEMS[(start_stem_index + palace_index) % 10],
                "earthly_branch": branch,
                "is_body_palace": palace_index == body_index,
                "primary_stars": primary_by_branch[branch],
                "supporting_stars": supporting_by_branch[branch],
                "malefic_stars": malefic_by_branch[branch],
                "transformations": transformations_by_branch[branch],
                "brightness_state": brightness,
                "field_status": "supported",
            }
        )
    return {
        "placement_lunar_date": {
            "year": lunar.year,
            "month": lunar.month,
            "day": lunar.day,
            "leap_month": lunar.is_leap_month,
            "year_stem": year_stem,
            "year_branch": year_branch,
        },
        "life_palace": life_index,
        "body_palace": body_index,
        "bureau": bureau,
        "palaces": palaces,
    }


__all__ = [
    "ALGORITHM_PROFILE",
    "AUXILIARY_STAR_IDS",
    "PALACE_BRANCHES",
    "PALACE_NAMES",
    "PRIMARY_STAR_IDS",
    "ZIWEI_ENGINE_VERSION",
    "build_traditional_ziwei",
    "calculate_bureau",
    "calculate_life_body_palaces",
    "four_transformations",
    "place_auxiliary_stars",
    "place_primary_stars",
]
