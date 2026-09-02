from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .case_record import LiuYaoCaseRecord
from .models import HexagramIdentity, LiuYaoChart
from .tables import (
    BRANCHES,
    BRANCH_ELEMENTS,
    CONTROLS,
    ELEMENTS,
    GENERATES,
    HEXAGRAM_NAMES,
    NAJIA_TABLE,
    PALACE_ELEMENTS,
    PALACE_SEQUENCES,
    PREDICTION_VALIDITY,
    digest,
)
from .validation import LiuYaoError

ADVANCED_FACT_METHOD_ID = "liuyao-advanced-structural-facts@0.1.0"
ADVANCED_FACT_STATUS = "review_only"
ADVANCED_FACT_PRODUCTION_ALLOWED = False

SIX_RELATION_ORDER = ("父母", "兄弟", "子孙", "妻财", "官鬼")
TWELVE_GROWTH_STAGES = (
    "长生",
    "沐浴",
    "冠带",
    "临官",
    "帝旺",
    "衰",
    "病",
    "死",
    "墓",
    "绝",
    "胎",
    "养",
)

# v1 明确采用五行顺行口径：木长生亥、火长生寅、金长生巳、水土长生申。
# 不同流派若采用其他口径，必须另建版本化 profile，不能在运行时静默混用。
_GROWTH_START = {"木": "亥", "火": "寅", "土": "申", "金": "巳", "水": "申"}

# 土支进退循环在不同资料中可能有口径差异，因此单独纳入版本化表摘要。
# 本层只识别地支变化，不附加吉凶或成败判断。
ADVANCE_PAIRS = frozenset(
    {
        ("寅", "卯"),
        ("巳", "午"),
        ("申", "酉"),
        ("亥", "子"),
        ("丑", "辰"),
        ("辰", "未"),
        ("未", "戌"),
        ("戌", "丑"),
    }
)
RETREAT_PAIRS = frozenset((target, source) for source, target in ADVANCE_PAIRS)

SIX_CLASHES = frozenset(
    {
        frozenset(("子", "午")),
        frozenset(("丑", "未")),
        frozenset(("寅", "申")),
        frozenset(("卯", "酉")),
        frozenset(("辰", "戌")),
        frozenset(("巳", "亥")),
    }
)
SIX_COMBINATIONS = frozenset(
    {
        frozenset(("子", "丑")),
        frozenset(("寅", "亥")),
        frozenset(("卯", "戌")),
        frozenset(("辰", "酉")),
        frozenset(("巳", "申")),
        frozenset(("午", "未")),
    }
)


def _growth_table() -> Mapping[str, Mapping[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for element, start in _GROWTH_START.items():
        start_index = BRANCHES.index(start)
        result[element] = {
            BRANCHES[(start_index + offset) % len(BRANCHES)]: stage
            for offset, stage in enumerate(TWELVE_GROWTH_STAGES)
        }
    return result


GROWTH_STAGE_BY_ELEMENT = _growth_table()


def _validate_advanced_tables() -> None:
    if set(_GROWTH_START) != set(ELEMENTS):
        raise RuntimeError("growth-stage profile must cover all five elements")
    for element, table in GROWTH_STAGE_BY_ELEMENT.items():
        if set(table) != set(BRANCHES) or set(table.values()) != set(TWELVE_GROWTH_STAGES):
            raise RuntimeError(f"invalid growth-stage table for {element}")
    if ADVANCE_PAIRS & RETREAT_PAIRS:
        raise RuntimeError("advance and retreat pairs must not overlap")
    for source, target in ADVANCE_PAIRS | RETREAT_PAIRS:
        if source not in BRANCHES or target not in BRANCHES:
            raise RuntimeError("advance/retreat pair contains unknown branch")
        if BRANCH_ELEMENTS[source] != BRANCH_ELEMENTS[target]:
            raise RuntimeError("advance/retreat pair must stay within one element")


_validate_advanced_tables()

ADVANCED_FACT_TABLE_SHA256 = digest(
    {
        "growth_stages": {
            element: dict(sorted(values.items()))
            for element, values in sorted(GROWTH_STAGE_BY_ELEMENT.items())
        },
        "advance_pairs": sorted([list(pair) for pair in ADVANCE_PAIRS]),
        "retreat_pairs": sorted([list(pair) for pair in RETREAT_PAIRS]),
        "six_clashes": sorted([sorted(pair) for pair in SIX_CLASHES]),
        "six_combinations": sorted([sorted(pair) for pair in SIX_COMBINATIONS]),
        "hidden_spirit_profile": "palace-pure-hexagram@1.0.0",
        "repetition_profile": "branchwise-fanyin-fuyin@1.0.0",
    }
)


def growth_stage(element: str, branch: str) -> str:
    if element not in GROWTH_STAGE_BY_ELEMENT:
        raise LiuYaoError("INVALID_INPUT", f"未知五行：{element}")
    if branch not in BRANCHES:
        raise LiuYaoError("INVALID_INPUT", f"未知地支：{branch}")
    return GROWTH_STAGE_BY_ELEMENT[element][branch]


def classify_progression(original_branch: str, changed_branch: str) -> str:
    pair = (original_branch, changed_branch)
    if pair in ADVANCE_PAIRS:
        return "advance"
    if pair in RETREAT_PAIRS:
        return "retreat"
    return "none"


def classify_branch_relation(first: str, second: str) -> str:
    if first not in BRANCHES or second not in BRANCHES:
        raise LiuYaoError("INVALID_INPUT", "branch relation requires two valid earthly branches")
    if first == second:
        return "same"
    pair = frozenset((first, second))
    if pair in SIX_COMBINATIONS:
        return "combine"
    if pair in SIX_CLASHES:
        return "clash"
    return "none"


def classify_element_relation(actor: str, target: str) -> str:
    if actor not in ELEMENTS or target not in ELEMENTS:
        raise LiuYaoError("INVALID_INPUT", "element relation requires two valid five elements")
    if actor == target:
        return "same_element"
    if GENERATES[actor] == target:
        return "generates"
    if GENERATES[target] == actor:
        return "generated_by"
    if CONTROLS[actor] == target:
        return "controls"
    if CONTROLS[target] == actor:
        return "controlled_by"
    raise RuntimeError(f"unclassified five-element relation: {actor}/{target}")


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
    raise RuntimeError(f"unknown six relation: {palace_element}/{line_element}")


def _najia(identity: HexagramIdentity, position: int) -> tuple[str, str]:
    if position <= 3:
        return NAJIA_TABLE[identity.lower_trigram]["inner"][position - 1]
    return NAJIA_TABLE[identity.upper_trigram]["outer"][position - 4]


def _identity_for_name(name: str, palace: str) -> HexagramIdentity:
    for (upper, lower), candidate in HEXAGRAM_NAMES.items():
        if candidate == name:
            return HexagramIdentity(
                name=name,
                upper_trigram=upper,
                lower_trigram=lower,
                palace=palace,
                palace_element=PALACE_ELEMENTS[palace],
                palace_stage="本宫",
                shi_line=6,
                ying_line=3,
            )
    raise RuntimeError(f"hexagram not found: {name}")


@dataclass(frozen=True, slots=True)
class AdvancedFact:
    fact_id: str
    category: str
    scope: str
    positions: tuple[int, ...]
    relation: str
    branches: tuple[str, ...]
    elements: tuple[str, ...]
    value: str
    profile: str
    conditional: bool
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "category": self.category,
            "scope": self.scope,
            "positions": list(self.positions),
            "relation": self.relation,
            "branches": list(self.branches),
            "elements": list(self.elements),
            "value": self.value,
            "profile": self.profile,
            "conditional": self.conditional,
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class AdvancedFactReport:
    case_id: str
    chart_sha256: str
    facts: tuple[AdvancedFact, ...]
    missing_relations: tuple[str, ...]
    context_status: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "method_id": ADVANCED_FACT_METHOD_ID,
            "advanced_fact_status": ADVANCED_FACT_STATUS,
            "production_allowed": ADVANCED_FACT_PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "advanced_table_sha256": ADVANCED_FACT_TABLE_SHA256,
            "case_id": self.case_id,
            "chart_sha256": self.chart_sha256,
            "facts": [fact.to_dict() for fact in self.facts],
            "missing_relations": list(self.missing_relations),
            "context_status": self.context_status,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def _fact(
    *,
    fact_id: str,
    category: str,
    scope: str,
    positions: tuple[int, ...],
    relation: str,
    branches: tuple[str, ...],
    elements: tuple[str, ...],
    value: str,
    profile: str,
    conditional: bool,
    technical: str,
    plain: str,
) -> AdvancedFact:
    return AdvancedFact(
        fact_id=fact_id,
        category=category,
        scope=scope,
        positions=positions,
        relation=relation,
        branches=branches,
        elements=elements,
        value=value,
        profile=profile,
        conditional=conditional,
        technical=technical,
        plain=plain,
    )


def _hidden_spirit_facts(chart: LiuYaoChart) -> tuple[tuple[str, ...], list[AdvancedFact]]:
    present = {line.six_relation for line in chart.lines}
    missing = tuple(relation for relation in SIX_RELATION_ORDER if relation not in present)
    if not missing:
        return (), []

    palace = chart.original.palace
    pure_name = PALACE_SEQUENCES[palace][0]
    pure_identity = _identity_for_name(pure_name, palace)
    facts: list[AdvancedFact] = []
    for relation in missing:
        for position in range(1, 7):
            stem, branch = _najia(pure_identity, position)
            element = BRANCH_ELEMENTS[branch]
            if _six_relation(chart.original.palace_element, element) != relation:
                continue
            flying = chart.lines[position - 1]
            element_relation = classify_element_relation(element, flying.element)
            facts.append(
                _fact(
                    fact_id=f"hidden:{relation}:{position}",
                    category="hidden_spirit",
                    scope="line",
                    positions=(position,),
                    relation=relation,
                    branches=(branch, flying.najia_branch),
                    elements=(element, flying.element),
                    value=element_relation,
                    profile="palace-pure-hexagram-hidden-spirit@1.0.0",
                    conditional=True,
                    technical=(
                        f"本卦缺{relation}；按{palace}宫纯卦{pure_name}，"
                        f"{stem}{branch}{element}伏于第{position}爻，飞神为"
                        f"{flying.najia_stem}{flying.najia_branch}{flying.element}。"
                    ),
                    plain="这里只定位伏神候选和飞伏五行关系，不代表伏神已经有力、出伏或能成事。",
                )
            )
    return missing, facts


def _growth_facts(chart: LiuYaoChart) -> list[AdvancedFact]:
    contexts: list[tuple[str, str]] = []
    if chart.month_branch is not None:
        contexts.append(("month", chart.month_branch))
    if chart.day_ganzhi is not None:
        contexts.append(("day", chart.day_ganzhi[1]))
    facts: list[AdvancedFact] = []
    for context_name, context_branch in contexts:
        for line in chart.lines:
            stage = growth_stage(line.element, context_branch)
            facts.append(
                _fact(
                    fact_id=f"growth:{context_name}:original:{line.position}",
                    category="growth_stage",
                    scope=f"{context_name}_original",
                    positions=(line.position,),
                    relation=context_name,
                    branches=(line.najia_branch, context_branch),
                    elements=(line.element,),
                    value=stage,
                    profile="five-element-forward-water-earth-shared@1.0.0",
                    conditional=True,
                    technical=f"第{line.position}爻{line.element}在{context_branch}支对应十二长生阶段：{stage}。",
                    plain="这是版本化的阶段标签，不能单独换算成旺衰分数或吉凶。",
                )
            )
            if line.moving and line.changed_element is not None and line.changed_najia_branch is not None:
                changed_stage = growth_stage(line.changed_element, context_branch)
                facts.append(
                    _fact(
                        fact_id=f"growth:{context_name}:changed:{line.position}",
                        category="growth_stage",
                        scope=f"{context_name}_changed",
                        positions=(line.position,),
                        relation=context_name,
                        branches=(line.changed_najia_branch, context_branch),
                        elements=(line.changed_element,),
                        value=changed_stage,
                        profile="five-element-forward-water-earth-shared@1.0.0",
                        conditional=True,
                        technical=(
                            f"第{line.position}爻变爻{line.changed_element}在{context_branch}支"
                            f"对应十二长生阶段：{changed_stage}。"
                        ),
                        plain="变爻阶段同样只是结构标签，需与月日、空破和作用链合看。",
                    )
                )
    return facts


def _change_facts(chart: LiuYaoChart) -> list[AdvancedFact]:
    facts: list[AdvancedFact] = []
    moving = {line.position for line in chart.lines if line.moving}
    original_branches = [line.najia_branch for line in chart.lines]
    changed_branches = [_najia(chart.changed, position)[1] for position in range(1, 7)]

    for line in chart.lines:
        if not line.moving or line.changed_najia_branch is None or line.changed_element is None:
            continue
        original_branch = line.najia_branch
        changed_branch = line.changed_najia_branch
        progression = classify_progression(original_branch, changed_branch)
        if progression != "none":
            facts.append(
                _fact(
                    fact_id=f"progression:{line.position}",
                    category="progression",
                    scope="self_change",
                    positions=(line.position,),
                    relation="branch_progression",
                    branches=(original_branch, changed_branch),
                    elements=(line.element, line.changed_element),
                    value=progression,
                    profile="branch-progression@1.0.0",
                    conditional=True,
                    technical=f"第{line.position}爻由{original_branch}变{changed_branch}，标记为{progression}。",
                    plain="进退神这里只做结构识别；是否真正推进或衰退仍取决于空破、月日和作用对象。",
                )
            )

        branch_relation = classify_branch_relation(original_branch, changed_branch)
        facts.append(
            _fact(
                fact_id=f"self-branch:{line.position}",
                category="self_change_branch",
                scope="self_change",
                positions=(line.position,),
                relation="branch_relation",
                branches=(original_branch, changed_branch),
                elements=(line.element, line.changed_element),
                value=branch_relation,
                profile="branchwise-change-relation@1.0.0",
                conditional=branch_relation in {"combine", "clash"},
                technical=f"第{line.position}爻原支{original_branch}与变支{changed_branch}关系：{branch_relation}。",
                plain="同、合、冲只是关系事实；本层不把它直接解释成成败。",
            )
        )
        facts.append(
            _fact(
                fact_id=f"self-element:{line.position}",
                category="self_change_element",
                scope="self_change",
                positions=(line.position,),
                relation="element_relation",
                branches=(original_branch, changed_branch),
                elements=(line.element, line.changed_element),
                value=classify_element_relation(line.changed_element, line.element),
                profile="changed-to-original-element@1.0.0",
                conditional=True,
                technical=(
                    f"第{line.position}爻变爻{line.changed_element}相对原爻{line.element}的"
                    f"五行关系已登记。"
                ),
                plain="这是回头生克候选事实，不表示该变爻已经具备实际作用力。",
            )
        )

    scopes = {
        "inner": tuple(range(1, 4)),
        "outer": tuple(range(4, 7)),
        "whole": tuple(range(1, 7)),
    }
    for scope, positions in scopes.items():
        if not moving.intersection(positions):
            continue
        relations = tuple(
            classify_branch_relation(original_branches[position - 1], changed_branches[position - 1])
            for position in positions
        )
        value: str | None = None
        if all(relation == "same" for relation in relations):
            value = "fuyin"
        elif all(relation == "clash" for relation in relations):
            value = "fanyin"
        if value is not None:
            facts.append(
                _fact(
                    fact_id=f"repetition:{scope}:{value}",
                    category="repetition",
                    scope=scope,
                    positions=positions,
                    relation="branchwise_repetition",
                    branches=tuple(
                        branch
                        for position in positions
                        for branch in (original_branches[position - 1], changed_branches[position - 1])
                    ),
                    elements=(),
                    value=value,
                    profile="branchwise-fanyin-fuyin@1.0.0",
                    conditional=True,
                    technical=f"{scope}范围内逐爻地支关系全部满足{value}结构条件。",
                    plain="这是逐支结构识别，不直接等同于反复、灾祸、失败或必然变动。",
                )
            )

    moving_lines = [line for line in chart.lines if line.moving]
    for index, first in enumerate(moving_lines):
        for second in moving_lines[index + 1 :]:
            facts.append(
                _fact(
                    fact_id=f"graph:element:{first.position}:{second.position}",
                    category="moving_graph_element",
                    scope="moving_pair",
                    positions=(first.position, second.position),
                    relation="first_to_second",
                    branches=(first.najia_branch, second.najia_branch),
                    elements=(first.element, second.element),
                    value=classify_element_relation(first.element, second.element),
                    profile="moving-line-graph@1.0.0",
                    conditional=True,
                    technical=f"动爻第{first.position}爻到第{second.position}爻的五行有向关系已登记。",
                    plain="多动爻之间的关系只形成图边；本层不决定哪条边最终有效。",
                )
            )
            branch_relation = classify_branch_relation(first.najia_branch, second.najia_branch)
            if branch_relation != "none":
                facts.append(
                    _fact(
                        fact_id=f"graph:branch:{first.position}:{second.position}",
                        category="moving_graph_branch",
                        scope="moving_pair",
                        positions=(first.position, second.position),
                        relation="pair_branch_relation",
                        branches=(first.najia_branch, second.najia_branch),
                        elements=(first.element, second.element),
                        value=branch_relation,
                        profile="moving-line-graph@1.0.0",
                        conditional=True,
                        technical=f"动爻第{first.position}爻与第{second.position}爻地支关系：{branch_relation}。",
                        plain="多动爻合冲只记录为条件边，不单独决定用神得失。",
                    )
                )
    return facts


def build_advanced_fact_report(record: LiuYaoCaseRecord) -> AdvancedFactReport:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")

    missing_relations, hidden = _hidden_spirit_facts(record.chart)
    growth = _growth_facts(record.chart)
    changes = _change_facts(record.chart)
    facts = tuple(sorted(hidden + growth + changes, key=lambda fact: fact.fact_id))

    has_month = record.chart.month_branch is not None
    has_day = record.chart.day_ganzhi is not None
    context_status = "complete" if has_month and has_day else "partial" if has_month or has_day else "missing"
    warnings: list[str] = []
    if not has_month:
        warnings.append("缺少经确认的月建，未生成月令十二长生事实。")
    if not has_day:
        warnings.append("缺少经确认的日柱，未生成日辰十二长生事实。")
    if missing_relations:
        warnings.append("伏神只按本宫纯卦定位候选，尚未判断飞伏旺衰、出伏或可用性。")
    if record.chart.moving_lines:
        warnings.append("进退神、反吟伏吟和多动爻关系均为条件事实，尚未进入作用优先级。")

    limits = (
        "本层不自动推算月建或日柱，也不核验调用方提供的历法来源。",
        "十二长生采用版本化五行顺行口径，流派口径不同应另建 profile，不得静默混用。",
        "伏神、进退神、反吟伏吟和多动爻图均不直接产生吉凶、成败或应期。",
        "未实现三合成局、合化、入墓作用条件、暗动、复杂旺衰优先级和跨位变爻传递。",
        "不得把结构事实分数换算为成功概率；当前没有合格前瞻样本支持概率校准。",
    )
    return AdvancedFactReport(
        case_id=record.cast.case_id,
        chart_sha256=record.chart.canonical_sha256,
        facts=facts,
        missing_relations=missing_relations,
        context_status=context_status,
        warnings=tuple(warnings),
        limits=limits,
    )


__all__ = [
    "ADVANCED_FACT_METHOD_ID",
    "ADVANCED_FACT_PRODUCTION_ALLOWED",
    "ADVANCED_FACT_STATUS",
    "ADVANCED_FACT_TABLE_SHA256",
    "ADVANCE_PAIRS",
    "RETREAT_PAIRS",
    "AdvancedFact",
    "AdvancedFactReport",
    "build_advanced_fact_report",
    "classify_branch_relation",
    "classify_element_relation",
    "classify_progression",
    "growth_stage",
]
