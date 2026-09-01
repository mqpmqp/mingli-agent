from __future__ import annotations

import hashlib
import json
from typing import Mapping

METHOD_ID = "liuyao-wenwang-najia@1.0.0"
PREDICTION_VALIDITY = "not_evaluated"
INPUT_ORDER = "bottom_to_top"
COIN_CONVENTION = "text_yin_flower_yang"

STEMS = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")
BRANCHES = ("子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥")
ELEMENTS = ("木", "火", "土", "金", "水")
CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})
PREDICTION_STATUSES = frozenset({"draft", "pending", "invalid", "settled"})
SETTLEMENT_OUTCOMES = frozenset({"hit", "miss", "partial", "indeterminate"})

_LINE_TYPES = {6: "老阴", 7: "少阳", 8: "少阴", 9: "老阳"}
_ORIGINAL_YANG = {6: False, 7: True, 8: False, 9: True}
_COIN_LABEL_VALUES = {
    "6": 6,
    "三字": 6,
    "三个字": 6,
    "三枚字": 6,
    "7": 7,
    "两字一花": 7,
    "二字一花": 7,
    "两枚字一枚花": 7,
    "8": 8,
    "一字两花": 8,
    "一字二花": 8,
    "一枚字两枚花": 8,
    "9": 9,
    "三花": 9,
    "三个花": 9,
    "三枚花": 9,
}
_CONVENTION_ALIASES = {
    COIN_CONVENTION: COIN_CONVENTION,
    "字阴花阳": COIN_CONVENTION,
    "字为阴花为阳": COIN_CONVENTION,
    "字为阴，花为阳": COIN_CONVENTION,
}
_CASTING_MODE_ALIASES = {
    "self": "self",
    "本人": "self",
    "本人摇": "self",
    "proxy": "proxy",
    "代摇": "proxy",
    "替人摇": "proxy",
}

TRIGRAM_BITS: Mapping[str, tuple[bool, bool, bool]] = {
    "乾": (True, True, True),
    "兑": (True, True, False),
    "离": (True, False, True),
    "震": (True, False, False),
    "巽": (False, True, True),
    "坎": (False, True, False),
    "艮": (False, False, True),
    "坤": (False, False, False),
}
_BITS_TO_TRIGRAM = {value: key for key, value in TRIGRAM_BITS.items()}

# Key order is (upper trigram, lower trigram).
_HEXAGRAM_ROWS: Mapping[str, tuple[str, ...]] = {
    "乾": ("乾为天", "天泽履", "天火同人", "天雷无妄", "天风姤", "天水讼", "天山遁", "天地否"),
    "兑": ("泽天夬", "兑为泽", "泽火革", "泽雷随", "泽风大过", "泽水困", "泽山咸", "泽地萃"),
    "离": ("火天大有", "火泽睽", "离为火", "火雷噬嗑", "火风鼎", "火水未济", "火山旅", "火地晋"),
    "震": ("雷天大壮", "雷泽归妹", "雷火丰", "震为雷", "雷风恒", "雷水解", "雷山小过", "雷地豫"),
    "巽": ("风天小畜", "风泽中孚", "风火家人", "风雷益", "巽为风", "风水涣", "风山渐", "风地观"),
    "坎": ("水天需", "水泽节", "水火既济", "水雷屯", "水风井", "坎为水", "水山蹇", "水地比"),
    "艮": ("山天大畜", "山泽损", "山火贲", "山雷颐", "山风蛊", "山水蒙", "艮为山", "山地剥"),
    "坤": ("地天泰", "地泽临", "地火明夷", "地雷复", "地风升", "地水师", "地山谦", "坤为地"),
}
_TRIGRAM_ORDER = ("乾", "兑", "离", "震", "巽", "坎", "艮", "坤")
HEXAGRAM_NAMES: Mapping[tuple[str, str], str] = {
    (upper, lower): row[index]
    for upper, row in _HEXAGRAM_ROWS.items()
    for index, lower in enumerate(_TRIGRAM_ORDER)
}

PALACE_SEQUENCES: Mapping[str, tuple[str, ...]] = {
    "乾": ("乾为天", "天风姤", "天山遁", "天地否", "风地观", "山地剥", "火地晋", "火天大有"),
    "兑": ("兑为泽", "泽水困", "泽地萃", "泽山咸", "水山蹇", "地山谦", "雷山小过", "雷泽归妹"),
    "离": ("离为火", "火山旅", "火风鼎", "火水未济", "山水蒙", "风水涣", "天水讼", "天火同人"),
    "震": ("震为雷", "雷地豫", "雷水解", "雷风恒", "地风升", "水风井", "泽风大过", "泽雷随"),
    "巽": ("巽为风", "风天小畜", "风火家人", "风雷益", "天雷无妄", "火雷噬嗑", "山雷颐", "山风蛊"),
    "坎": ("坎为水", "水泽节", "水雷屯", "水火既济", "泽火革", "雷火丰", "地火明夷", "地水师"),
    "艮": ("艮为山", "山火贲", "山天大畜", "山泽损", "火泽睽", "天泽履", "风泽中孚", "风山渐"),
    "坤": ("坤为地", "地雷复", "地泽临", "地天泰", "雷天大壮", "泽天夬", "水天需", "水地比"),
}
PALACE_ELEMENTS = {"乾": "金", "兑": "金", "离": "火", "震": "木", "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
PALACE_STAGES = ("本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂")
SHI_YING_BY_STAGE = ((6, 3), (1, 4), (2, 5), (3, 6), (4, 1), (5, 2), (4, 1), (3, 6))

# Each tuple is line 1 -> line 3 for inner, line 4 -> line 6 for outer.
NAJIA_TABLE: Mapping[str, Mapping[str, tuple[tuple[str, str], ...]]] = {
    "乾": {"inner": (("甲", "子"), ("甲", "寅"), ("甲", "辰")), "outer": (("壬", "午"), ("壬", "申"), ("壬", "戌"))},
    "坤": {"inner": (("乙", "未"), ("乙", "巳"), ("乙", "卯")), "outer": (("癸", "丑"), ("癸", "亥"), ("癸", "酉"))},
    "震": {"inner": (("庚", "子"), ("庚", "寅"), ("庚", "辰")), "outer": (("庚", "午"), ("庚", "申"), ("庚", "戌"))},
    "巽": {"inner": (("辛", "丑"), ("辛", "亥"), ("辛", "酉")), "outer": (("辛", "未"), ("辛", "巳"), ("辛", "卯"))},
    "坎": {"inner": (("戊", "寅"), ("戊", "辰"), ("戊", "午")), "outer": (("戊", "申"), ("戊", "戌"), ("戊", "子"))},
    "离": {"inner": (("己", "卯"), ("己", "丑"), ("己", "亥")), "outer": (("己", "酉"), ("己", "未"), ("己", "巳"))},
    "艮": {"inner": (("丙", "辰"), ("丙", "午"), ("丙", "申")), "outer": (("丙", "戌"), ("丙", "子"), ("丙", "寅"))},
    "兑": {"inner": (("丁", "巳"), ("丁", "卯"), ("丁", "丑")), "outer": (("丁", "亥"), ("丁", "酉"), ("丁", "未"))},
}
BRANCH_ELEMENTS = {
    "子": "水", "亥": "水", "寅": "木", "卯": "木", "巳": "火", "午": "火",
    "申": "金", "酉": "金", "辰": "土", "戌": "土", "丑": "土", "未": "土",
}
GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
SIX_SPIRIT_CYCLE = ("青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武")
SIX_SPIRIT_START = {"甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2, "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5}
VOID_BRANCHES_BY_XUN = (("戌", "亥"), ("申", "酉"), ("午", "未"), ("辰", "巳"), ("寅", "卯"), ("子", "丑"))
SEXAGENARY_CYCLE = tuple(STEMS[index % 10] + BRANCHES[index % 12] for index in range(60))


def _validate_static_tables() -> None:
    if set(_LINE_TYPES) != {6, 7, 8, 9} or set(_ORIGINAL_YANG) != {6, 7, 8, 9}:
        raise RuntimeError("line value tables must cover 6, 7, 8 and 9")
    if len(TRIGRAM_BITS) != 8 or len(set(TRIGRAM_BITS.values())) != 8:
        raise RuntimeError("trigram table must contain eight unique entries")
    if len(HEXAGRAM_NAMES) != 64 or len(set(HEXAGRAM_NAMES.values())) != 64:
        raise RuntimeError("hexagram table must contain 64 unique entries")
    palace_names = [name for sequence in PALACE_SEQUENCES.values() for name in sequence]
    if len(palace_names) != 64 or set(palace_names) != set(HEXAGRAM_NAMES.values()):
        raise RuntimeError("eight-palace table must cover each hexagram exactly once")
    if len(PALACE_STAGES) != 8 or len(SHI_YING_BY_STAGE) != 8:
        raise RuntimeError("palace stages and shi-ying table must contain eight entries")
    if set(PALACE_ELEMENTS) != set(TRIGRAM_BITS):
        raise RuntimeError("palace element table must cover all palaces")
    if set(NAJIA_TABLE) != set(TRIGRAM_BITS):
        raise RuntimeError("najia table must cover all trigrams")
    for trigram, sections in NAJIA_TABLE.items():
        if set(sections) != {"inner", "outer"} or any(len(entries) != 3 for entries in sections.values()):
            raise RuntimeError(f"invalid najia table for {trigram}")
        if any(stem not in STEMS or branch not in BRANCHES for entries in sections.values() for stem, branch in entries):
            raise RuntimeError(f"invalid najia stem or branch for {trigram}")
    if set(BRANCH_ELEMENTS) != set(BRANCHES):
        raise RuntimeError("branch element table must cover all branches")
    if set(GENERATES) != set(ELEMENTS) or set(CONTROLS) != set(ELEMENTS):
        raise RuntimeError("five-element relation tables must cover all elements")
    if len(SIX_SPIRIT_CYCLE) != 6 or set(SIX_SPIRIT_START) != set(STEMS):
        raise RuntimeError("six-spirit tables are incomplete")
    if len(VOID_BRANCHES_BY_XUN) != 6 or any(len(pair) != 2 for pair in VOID_BRANCHES_BY_XUN):
        raise RuntimeError("void branch table must contain six pairs")
    if len(SEXAGENARY_CYCLE) != 60 or len(set(SEXAGENARY_CYCLE)) != 60:
        raise RuntimeError("sexagenary cycle must contain 60 unique entries")


_validate_static_tables()


def digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


STATIC_TABLE_SHA256 = digest(
    {
        "line_types": {str(value): name for value, name in sorted(_LINE_TYPES.items())},
        "original_yang": {str(value): int(is_yang) for value, is_yang in sorted(_ORIGINAL_YANG.items())},
        "trigram_bits": {name: [int(bit) for bit in bits] for name, bits in sorted(TRIGRAM_BITS.items())},
        "hexagrams": [
            {"upper": upper, "lower": lower, "name": name}
            for (upper, lower), name in sorted(HEXAGRAM_NAMES.items())
        ],
        "palaces": {name: list(sequence) for name, sequence in sorted(PALACE_SEQUENCES.items())},
        "palace_elements": dict(sorted(PALACE_ELEMENTS.items())),
        "palace_stages": list(PALACE_STAGES),
        "shi_ying_by_stage": [list(value) for value in SHI_YING_BY_STAGE],
        "najia": {
            trigram: {
                section: [list(item) for item in entries]
                for section, entries in sorted(sections.items())
            }
            for trigram, sections in sorted(NAJIA_TABLE.items())
        },
        "branch_elements": dict(sorted(BRANCH_ELEMENTS.items())),
        "generates": dict(sorted(GENERATES.items())),
        "controls": dict(sorted(CONTROLS.items())),
        "six_spirit_cycle": list(SIX_SPIRIT_CYCLE),
        "six_spirit_start": dict(sorted(SIX_SPIRIT_START.items())),
        "void_branches_by_xun": [list(value) for value in VOID_BRANCHES_BY_XUN],
        "sexagenary_cycle": list(SEXAGENARY_CYCLE),
    }
)
