from __future__ import annotations

from .models import HexagramIdentity, LiuYaoCastInput, LiuYaoChart, LiuYaoLine
from .tables import (
    BRANCH_ELEMENTS, CONTROLS, GENERATES, HEXAGRAM_NAMES, NAJIA_TABLE,
    PALACE_ELEMENTS, PALACE_SEQUENCES, PALACE_STAGES, SEXAGENARY_CYCLE,
    SHI_YING_BY_STAGE, SIX_SPIRIT_CYCLE, SIX_SPIRIT_START, TRIGRAM_BITS,
    VOID_BRANCHES_BY_XUN, _BITS_TO_TRIGRAM, _LINE_TYPES, _ORIGINAL_YANG,
)

def _hexagram_identity(bits: tuple[bool, ...]) -> HexagramIdentity:
    lower = _BITS_TO_TRIGRAM[bits[:3]]
    upper = _BITS_TO_TRIGRAM[bits[3:]]
    name = HEXAGRAM_NAMES[(upper, lower)]
    for palace, sequence in PALACE_SEQUENCES.items():
        if name in sequence:
            stage_index = sequence.index(name)
            shi_line, ying_line = SHI_YING_BY_STAGE[stage_index]
            return HexagramIdentity(
                name=name,
                upper_trigram=upper,
                lower_trigram=lower,
                palace=palace,
                palace_element=PALACE_ELEMENTS[palace],
                palace_stage=PALACE_STAGES[stage_index],
                shi_line=shi_line,
                ying_line=ying_line,
            )
    raise RuntimeError(f"hexagram missing from palace table: {name}")


def _najia_for_line(identity: HexagramIdentity, position: int) -> tuple[str, str]:
    if not 1 <= position <= 6:
        raise ValueError("line position must be 1..6")
    if position <= 3:
        return NAJIA_TABLE[identity.lower_trigram]["inner"][position - 1]
    return NAJIA_TABLE[identity.upper_trigram]["outer"][position - 4]


def _six_relation(palace_element: str, line_element: str) -> str:
    if line_element == palace_element:
        return "兄弟"
    if GENERATES[line_element] == palace_element:
        return "父母"
    if GENERATES[palace_element] == line_element:
        return "子孙"
    if CONTROLS[line_element] == palace_element:
        return "官鬼"
    if CONTROLS[palace_element] == line_element:
        return "妻财"
    raise RuntimeError(f"unknown five-element relation: {palace_element}/{line_element}")


def _six_spirits(day_ganzhi: str | None) -> tuple[str | None, ...]:
    if day_ganzhi is None:
        return (None,) * 6
    start = SIX_SPIRIT_START[day_ganzhi[0]]
    return tuple(SIX_SPIRIT_CYCLE[(start + offset) % 6] for offset in range(6))


def _void_branches(day_ganzhi: str | None) -> tuple[str, str] | None:
    if day_ganzhi is None:
        return None
    cycle_index = SEXAGENARY_CYCLE.index(day_ganzhi)
    return VOID_BRANCHES_BY_XUN[cycle_index // 10]


def build_liuyao_chart(cast: LiuYaoCastInput) -> LiuYaoChart:
    original_bits = tuple(_ORIGINAL_YANG[value] for value in cast.line_values)
    changed_bits = tuple((not bit) if value in (6, 9) else bit for bit, value in zip(original_bits, cast.line_values, strict=True))
    original = _hexagram_identity(original_bits)
    changed = _hexagram_identity(changed_bits)
    void = _void_branches(cast.day_ganzhi)
    spirits = _six_spirits(cast.day_ganzhi)
    lines: list[LiuYaoLine] = []
    for position, value in enumerate(cast.line_values, start=1):
        moving = value in (6, 9)
        original_stem, original_branch = _najia_for_line(original, position)
        element = BRANCH_ELEMENTS[original_branch]
        relation = _six_relation(original.palace_element, element)
        changed_stem: str | None = None
        changed_branch: str | None = None
        changed_element: str | None = None
        changed_relation: str | None = None
        changed_void: bool | None = None
        if moving:
            changed_stem, changed_branch = _najia_for_line(changed, position)
            changed_element = BRANCH_ELEMENTS[changed_branch]
            # Traditional 六亲 for a transformed line remains relative to the original palace element.
            changed_relation = _six_relation(original.palace_element, changed_element)
            changed_void = changed_branch in void if void is not None else None
        lines.append(
            LiuYaoLine(
                position=position,
                value=value,
                line_type=_LINE_TYPES[value],
                yin_yang="阳" if _ORIGINAL_YANG[value] else "阴",
                moving=moving,
                changed_yin_yang="阳" if changed_bits[position - 1] else "阴",
                najia_stem=original_stem,
                najia_branch=original_branch,
                element=element,
                six_relation=relation,
                six_spirit=spirits[position - 1],
                is_void=original_branch in void if void is not None else None,
                changed_najia_stem=changed_stem,
                changed_najia_branch=changed_branch,
                changed_element=changed_element,
                changed_six_relation=changed_relation,
                changed_is_void=changed_void,
            )
        )
    moving_lines = tuple(line.position for line in lines if line.moving)
    return LiuYaoChart(
        original=original,
        changed=changed,
        lines=tuple(lines),
        moving_lines=moving_lines,
        void_branches=void,
        month_branch=cast.month_branch,
        day_ganzhi=cast.day_ganzhi,
        input_sha256=cast.canonical_sha256,
    )
