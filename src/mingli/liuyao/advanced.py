from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Mapping, Sequence

from ..bazi import DeterministicBaziEngine, METHOD_ID as BAZI_CALENDAR_METHOD_ID
from ..errors import ChartCalculationError
from .case_record import LiuYaoCaseRecord, create_case_record
from .interpretation import InterpretationRequest, interpret_case
from .models import HexagramIdentity, LiuYaoLine
from .tables import (
    BRANCHES,
    BRANCH_ELEMENTS,
    CONTROLS,
    GENERATES,
    HEXAGRAM_NAMES,
    NAJIA_TABLE,
    PALACE_ELEMENTS,
    PALACE_SEQUENCES,
    PREDICTION_VALIDITY,
    SEXAGENARY_CYCLE,
    VOID_BRANCHES_BY_XUN,
    digest,
)
from .validation import LiuYaoError

ADVANCED_STRUCTURE_METHOD_ID = "liuyao-advanced-structure@0.2.0"
ADVANCED_STRUCTURE_STATUS = "review_only"
ADVANCED_PRODUCTION_ALLOWED = False
CALENDAR_CONTEXT_METHOD_ID = f"liuyao-calendar-context:{BAZI_CALENDAR_METHOD_ID}"
GROWTH_STAGE_PROFILE_ID = "liuyao-five-element-forward-growth-stage@1.0.0"
ADVANCE_RETREAT_PROFILE_ID = "liuyao-advance-retreat-branch-pairs@1.0.0"
FAN_FU_PROFILE_ID = "liuyao-corresponding-najia-fan-fu@1.0.0"
USE_RANKING_PROFILE_ID = "liuyao-use-candidate-ranking@0.2.0"
CONFLICT_MATRIX_PROFILE_ID = "liuyao-structural-conflict-matrix@0.2.0"

_SIX_CLASHES = frozenset(
    {
        frozenset(("子", "午")),
        frozenset(("丑", "未")),
        frozenset(("寅", "申")),
        frozenset(("卯", "酉")),
        frozenset(("辰", "戌")),
        frozenset(("巳", "亥")),
    }
)
_SIX_COMBINATIONS = frozenset(
    {
        frozenset(("子", "丑")),
        frozenset(("寅", "亥")),
        frozenset(("卯", "戌")),
        frozenset(("辰", "酉")),
        frozenset(("巳", "申")),
        frozenset(("午", "未")),
    }
)

_GROWTH_STAGES = ("长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养")
# 六爻卦象口径按五行顺行：木亥、火寅、金巳、水土申起长生。
_ELEMENT_GROWTH_START = {
    "木": "亥",
    "火": "寅",
    "金": "巳",
    "水": "申",
    "土": "申",
}

_ADVANCE_PAIRS = {
    ("亥", "子"),
    ("寅", "卯"),
    ("巳", "午"),
    ("申", "酉"),
    ("丑", "辰"),
    ("辰", "未"),
    ("未", "戌"),
    ("戌", "丑"),
}
_RETREAT_PAIRS = {(changed, original) for original, changed in _ADVANCE_PAIRS}

_SCORING_WEIGHTS: Mapping[str, int] = {
    "visible_base": 1,
    "hidden_base": -2,
    "month_same": 5,
    "month_generate": 3,
    "month_peer": 2,
    "month_control": -5,
    "month_drain": -2,
    "month_break": -6,
    "day_same": 3,
    "day_generate": 2,
    "day_peer": 1,
    "day_control": -3,
    "day_drain": -1,
    "moving": 1,
    "void": -2,
    "return_generate": 3,
    "return_control": -4,
    "advance": 1,
    "retreat": -1,
    "growth_changsheng": 1,
    "growth_linguan": 1,
    "growth_diwang": 2,
    "growth_tomb": -1,
    "growth_extinction": -2,
}


def _validate_advanced_tables() -> None:
    if len(_GROWTH_STAGES) != 12 or len(set(_GROWTH_STAGES)) != 12:
        raise RuntimeError("growth-stage table must contain twelve unique stages")
    if set(_ELEMENT_GROWTH_START) != {"木", "火", "土", "金", "水"}:
        raise RuntimeError("growth-stage start table must cover five elements")
    if any(branch not in BRANCHES for branch in _ELEMENT_GROWTH_START.values()):
        raise RuntimeError("growth-stage start table contains an invalid branch")
    if _ADVANCE_PAIRS & _RETREAT_PAIRS:
        raise RuntimeError("advance and retreat pairs must not overlap")
    if any(left not in BRANCHES or right not in BRANCHES for left, right in _ADVANCE_PAIRS | _RETREAT_PAIRS):
        raise RuntimeError("advance-retreat table contains an invalid branch")


_validate_advanced_tables()

ADVANCED_STATIC_TABLE_SHA256 = digest(
    {
        "six_clashes": sorted(sorted(pair) for pair in _SIX_CLASHES),
        "six_combinations": sorted(sorted(pair) for pair in _SIX_COMBINATIONS),
        "growth_stages": list(_GROWTH_STAGES),
        "element_growth_start": dict(sorted(_ELEMENT_GROWTH_START.items())),
        "advance_pairs": sorted([list(pair) for pair in _ADVANCE_PAIRS]),
        "retreat_pairs": sorted([list(pair) for pair in _RETREAT_PAIRS]),
        "scoring_weights": dict(sorted(_SCORING_WEIGHTS.items())),
    }
)


@dataclass(frozen=True, slots=True)
class CalendarContextReceipt:
    completed_at: str
    timezone_offset: str
    month_branch: str
    day_ganzhi: str
    day_branch: str
    void_branches: tuple[str, str]
    active_month_term: str
    active_month_term_utc: str
    source_method_id: str
    manual_month_branch: str | None
    manual_day_ganzhi: str | None

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "completed_at": self.completed_at,
            "timezone_offset": self.timezone_offset,
            "month_branch": self.month_branch,
            "day_ganzhi": self.day_ganzhi,
            "day_branch": self.day_branch,
            "void_branches": list(self.void_branches),
            "active_month_term": self.active_month_term,
            "active_month_term_utc": self.active_month_term_utc,
            "source_method_id": self.source_method_id,
            "manual_month_branch": self.manual_month_branch,
            "manual_day_ganzhi": self.manual_day_ganzhi,
            "manual_context_matches": True,
            "true_solar_time_applied": False,
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


@dataclass(frozen=True, slots=True)
class HiddenSpiritRecord:
    relation: str
    hidden_position: int
    hidden_stem: str
    hidden_branch: str
    hidden_element: str
    flying_position: int
    flying_relation: str
    flying_branch: str
    flying_element: str
    flying_to_hidden: str
    hidden_to_flying: str
    month_stage: str
    day_stage: str

    def to_dict(self) -> dict[str, object]:
        return {
            "relation": self.relation,
            "hidden_position": self.hidden_position,
            "hidden_najia": self.hidden_stem + self.hidden_branch,
            "hidden_element": self.hidden_element,
            "flying_position": self.flying_position,
            "flying_relation": self.flying_relation,
            "flying_branch": self.flying_branch,
            "flying_element": self.flying_element,
            "flying_to_hidden": self.flying_to_hidden,
            "hidden_to_flying": self.hidden_to_flying,
            "month_stage": self.month_stage,
            "day_stage": self.day_stage,
            "status": "hidden_candidate",
        }


@dataclass(frozen=True, slots=True)
class GrowthStageRecord:
    position: int
    najia: str
    element: str
    month_stage: str
    day_stage: str
    month_is_tomb: bool
    month_is_extinction: bool
    day_is_tomb: bool
    day_is_extinction: bool
    changed_najia: str | None
    changed_month_stage: str | None
    changed_day_stage: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "position": self.position,
            "najia": self.najia,
            "element": self.element,
            "month_stage": self.month_stage,
            "day_stage": self.day_stage,
            "month_is_tomb": self.month_is_tomb,
            "month_is_extinction": self.month_is_extinction,
            "day_is_tomb": self.day_is_tomb,
            "day_is_extinction": self.day_is_extinction,
            "changed_najia": self.changed_najia,
            "changed_month_stage": self.changed_month_stage,
            "changed_day_stage": self.changed_day_stage,
        }


@dataclass(frozen=True, slots=True)
class AdvanceRetreatRecord:
    position: int
    original_branch: str
    changed_branch: str
    kind: str
    profile_id: str = ADVANCE_RETREAT_PROFILE_ID

    def to_dict(self) -> dict[str, object]:
        return {
            "position": self.position,
            "original_branch": self.original_branch,
            "changed_branch": self.changed_branch,
            "kind": self.kind,
            "profile_id": self.profile_id,
            "directional_judgement": "not_inferred",
        }


@dataclass(frozen=True, slots=True)
class FanFuRecord:
    scope: str
    kind: str
    positions: tuple[int, ...]
    profile_id: str = FAN_FU_PROFILE_ID

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "kind": self.kind,
            "positions": list(self.positions),
            "profile_id": self.profile_id,
            "directional_judgement": "not_inferred",
        }


@dataclass(frozen=True, slots=True)
class RelationEdge:
    edge_id: str
    actor_id: str
    target_id: str
    relation_kind: str
    relation: str
    active_state: str
    technical: str
    caveat: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "edge_id": self.edge_id,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "relation_kind": self.relation_kind,
            "relation": self.relation,
            "active_state": self.active_state,
            "technical": self.technical,
            "caveat": self.caveat,
        }


@dataclass(frozen=True, slots=True)
class SpiritRoleRecord:
    actor_id: str
    position: int
    candidate_kind: str
    branch: str
    element: str
    role: str
    activation_state: str

    def to_dict(self) -> dict[str, object]:
        return {
            "actor_id": self.actor_id,
            "position": self.position,
            "candidate_kind": self.candidate_kind,
            "branch": self.branch,
            "element": self.element,
            "role": self.role,
            "activation_state": self.activation_state,
            "directional_judgement": "not_inferred",
        }


@dataclass(frozen=True, slots=True)
class CandidateFactor:
    code: str
    weight: int
    conditional: bool
    technical: str

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "weight": self.weight,
            "conditional": self.conditional,
            "technical": self.technical,
        }


@dataclass(frozen=True, slots=True)
class UseCandidateScore:
    candidate_id: str
    relation: str
    position: int
    candidate_kind: str
    branch: str
    element: str
    score: int
    rank: int
    factors: tuple[CandidateFactor, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "relation": self.relation,
            "position": self.position,
            "candidate_kind": self.candidate_kind,
            "branch": self.branch,
            "element": self.element,
            "score": self.score,
            "rank": self.rank,
            "factors": [factor.to_dict() for factor in self.factors],
        }


@dataclass(frozen=True, slots=True)
class RuleConflictRecord:
    conflict_id: str
    code: str
    priority: int
    resolution: str
    involved_ids: tuple[str, ...]
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "conflict_id": self.conflict_id,
            "code": self.code,
            "priority": self.priority,
            "resolution": self.resolution,
            "involved_ids": list(self.involved_ids),
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class AdvancedStructureResult:
    case_id: str
    chart_sha256: str
    effective_chart_sha256: str
    request_sha256: str
    effective_request_sha256: str
    base_interpretation_sha256: str
    calendar_context: CalendarContextReceipt
    hidden_spirits: tuple[HiddenSpiritRecord, ...]
    growth_stages: tuple[GrowthStageRecord, ...]
    advance_retreat: tuple[AdvanceRetreatRecord, ...]
    fan_fu: tuple[FanFuRecord, ...]
    relation_graph: tuple[RelationEdge, ...]
    spirit_roles: tuple[SpiritRoleRecord, ...]
    use_candidates: tuple[UseCandidateScore, ...]
    ranking_status: str
    recommended_position: int | None
    conflicts: tuple[RuleConflictRecord, ...]
    status: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "method_id": ADVANCED_STRUCTURE_METHOD_ID,
            "advanced_static_table_sha256": ADVANCED_STATIC_TABLE_SHA256,
            "interpretation_status": ADVANCED_STRUCTURE_STATUS,
            "production_allowed": ADVANCED_PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "case_id": self.case_id,
            "chart_sha256": self.chart_sha256,
            "effective_chart_sha256": self.effective_chart_sha256,
            "request_sha256": self.request_sha256,
            "effective_request_sha256": self.effective_request_sha256,
            "base_interpretation_sha256": self.base_interpretation_sha256,
            "calendar_context": self.calendar_context.to_dict(),
            "hidden_spirits": [item.to_dict() for item in self.hidden_spirits],
            "growth_stages": [item.to_dict() for item in self.growth_stages],
            "advance_retreat": [item.to_dict() for item in self.advance_retreat],
            "fan_fu": [item.to_dict() for item in self.fan_fu],
            "relation_graph": [item.to_dict() for item in self.relation_graph],
            "spirit_roles": [item.to_dict() for item in self.spirit_roles],
            "use_candidates": [item.to_dict() for item in self.use_candidates],
            "ranking_profile_id": USE_RANKING_PROFILE_ID,
            "ranking_semantics": "heuristic_review_score_not_probability",
            "ranking_status": self.ranking_status,
            "recommended_position": self.recommended_position,
            "conflict_matrix_profile_id": CONFLICT_MATRIX_PROFILE_ID,
            "conflicts": [item.to_dict() for item in self.conflicts],
            "status": self.status,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def _timezone_offset_text(moment: datetime) -> str:
    offset = moment.utcoffset()
    if offset is None:
        raise LiuYaoError("CALENDAR_CONTEXT_UNAVAILABLE", "completed_at 缺少有效时区偏移")
    seconds = int(offset.total_seconds())
    sign = "+" if seconds >= 0 else "-"
    absolute = abs(seconds)
    hours, remainder = divmod(absolute, 3600)
    minutes, offset_seconds = divmod(remainder, 60)
    if offset_seconds:
        raise LiuYaoError(
            "CALENDAR_CONTEXT_UNAVAILABLE",
            "completed_at 的 UTC 偏移必须精确到整分钟",
        )
    return f"{sign}{hours:02d}:{minutes:02d}"


def derive_calendar_context(record: LiuYaoCaseRecord) -> CalendarContextReceipt:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    moment = datetime.fromisoformat(record.cast.completed_at)
    timezone_text = _timezone_offset_text(moment)
    try:
        result = DeterministicBaziEngine().calculate(
            {
                "gender": "male",
                "calendar": "solar",
                "birth_date": moment.date().isoformat(),
                "birth_time": moment.replace(tzinfo=None, microsecond=0).time().isoformat(),
                "timezone": timezone_text,
                "birth_location": {},
                "true_solar_time": False,
            }
        )
    except ChartCalculationError as exc:
        raise LiuYaoError("CALENDAR_CONTEXT_UNAVAILABLE", str(exc)) from exc

    pillars = result["pillars"]
    boundaries = result["boundaries"]
    month_branch = str(pillars["month"])[1]
    day_ganzhi = str(pillars["day"])
    day_branch = day_ganzhi[1]
    void_branches = VOID_BRANCHES_BY_XUN[SEXAGENARY_CYCLE.index(day_ganzhi) // 10]

    if record.cast.month_branch is not None and record.cast.month_branch != month_branch:
        raise LiuYaoError(
            "CALENDAR_CONTEXT_CONFLICT",
            f"手工月建为{record.cast.month_branch}，确定性历法重算为{month_branch}",
        )
    if record.cast.day_ganzhi is not None and record.cast.day_ganzhi != day_ganzhi:
        raise LiuYaoError(
            "CALENDAR_CONTEXT_CONFLICT",
            f"手工日柱为{record.cast.day_ganzhi}，确定性历法重算为{day_ganzhi}",
        )

    return CalendarContextReceipt(
        completed_at=record.cast.completed_at,
        timezone_offset=timezone_text,
        month_branch=month_branch,
        day_ganzhi=day_ganzhi,
        day_branch=day_branch,
        void_branches=void_branches,
        active_month_term=str(boundaries["active_month_term"]),
        active_month_term_utc=str(boundaries["active_month_term_utc"]),
        source_method_id=CALENDAR_CONTEXT_METHOD_ID,
        manual_month_branch=record.cast.month_branch,
        manual_day_ganzhi=record.cast.day_ganzhi,
    )


def growth_stage(element: str, branch: str) -> str:
    if element not in _ELEMENT_GROWTH_START:
        raise LiuYaoError("INVALID_GROWTH_STAGE_INPUT", f"不支持的五行：{element}")
    if branch not in BRANCHES:
        raise LiuYaoError("INVALID_GROWTH_STAGE_INPUT", f"不支持的地支：{branch}")
    start = BRANCHES.index(_ELEMENT_GROWTH_START[element])
    target = BRANCHES.index(branch)
    return _GROWTH_STAGES[(target - start) % 12]


def _branch_relation(left: str, right: str) -> str | None:
    if left == right:
        return "same"
    pair = frozenset((left, right))
    if pair in _SIX_CLASHES:
        return "clash"
    if pair in _SIX_COMBINATIONS:
        return "combine"
    return None


def _element_relation(actor: str, target: str) -> str:
    if actor == target:
        return "peer"
    if GENERATES[actor] == target:
        return "generates"
    if CONTROLS[actor] == target:
        return "controls"
    if GENERATES[target] == actor:
        return "drains"
    if CONTROLS[target] == actor:
        return "controlled_by_target"
    raise RuntimeError(f"unknown element relation: {actor}/{target}")


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


def _identity_najia(identity: HexagramIdentity) -> tuple[tuple[str, str], ...]:
    inner = NAJIA_TABLE[identity.lower_trigram]["inner"]
    outer = NAJIA_TABLE[identity.upper_trigram]["outer"]
    return inner + outer


def _palace_root_najia(record: LiuYaoCaseRecord) -> tuple[tuple[str, str, str, str], ...]:
    palace = record.chart.original.palace
    root_name = PALACE_SEQUENCES[palace][0]
    identities = [pair for pair, name in HEXAGRAM_NAMES.items() if name == root_name]
    if len(identities) != 1:
        raise RuntimeError(f"palace root identity is not unique: {root_name}")
    upper, lower = identities[0]
    najia = NAJIA_TABLE[lower]["inner"] + NAJIA_TABLE[upper]["outer"]
    palace_element = PALACE_ELEMENTS[palace]
    return tuple(
        (stem, branch, BRANCH_ELEMENTS[branch], _six_relation(palace_element, BRANCH_ELEMENTS[branch]))
        for stem, branch in najia
    )


def _hidden_spirits(record: LiuYaoCaseRecord, context: CalendarContextReceipt) -> tuple[HiddenSpiritRecord, ...]:
    present_relations = {line.six_relation for line in record.chart.lines}
    root_lines = _palace_root_najia(record)
    result: list[HiddenSpiritRecord] = []
    for position, (stem, branch, element, relation) in enumerate(root_lines, start=1):
        if relation in present_relations:
            continue
        flying = record.chart.lines[position - 1]
        result.append(
            HiddenSpiritRecord(
                relation=relation,
                hidden_position=position,
                hidden_stem=stem,
                hidden_branch=branch,
                hidden_element=element,
                flying_position=position,
                flying_relation=flying.six_relation,
                flying_branch=flying.najia_branch,
                flying_element=flying.element,
                flying_to_hidden=_element_relation(flying.element, element),
                hidden_to_flying=_element_relation(element, flying.element),
                month_stage=growth_stage(element, context.month_branch),
                day_stage=growth_stage(element, context.day_branch),
            )
        )
    return tuple(result)


def _growth_stages(record: LiuYaoCaseRecord, context: CalendarContextReceipt) -> tuple[GrowthStageRecord, ...]:
    result: list[GrowthStageRecord] = []
    for line in record.chart.lines:
        month_stage = growth_stage(line.element, context.month_branch)
        day_stage = growth_stage(line.element, context.day_branch)
        changed_najia: str | None = None
        changed_month_stage: str | None = None
        changed_day_stage: str | None = None
        if line.changed_najia_stem is not None and line.changed_najia_branch is not None:
            changed_najia = line.changed_najia_stem + line.changed_najia_branch
            changed_month_stage = growth_stage(line.changed_element, context.month_branch)
            changed_day_stage = growth_stage(line.changed_element, context.day_branch)
        result.append(
            GrowthStageRecord(
                position=line.position,
                najia=line.najia_stem + line.najia_branch,
                element=line.element,
                month_stage=month_stage,
                day_stage=day_stage,
                month_is_tomb=month_stage == "墓",
                month_is_extinction=month_stage == "绝",
                day_is_tomb=day_stage == "墓",
                day_is_extinction=day_stage == "绝",
                changed_najia=changed_najia,
                changed_month_stage=changed_month_stage,
                changed_day_stage=changed_day_stage,
            )
        )
    return tuple(result)


def _advance_retreat(record: LiuYaoCaseRecord) -> tuple[AdvanceRetreatRecord, ...]:
    result: list[AdvanceRetreatRecord] = []
    for line in record.chart.lines:
        if not line.moving or line.changed_najia_branch is None:
            continue
        pair = (line.najia_branch, line.changed_najia_branch)
        if pair in _ADVANCE_PAIRS:
            kind = "advance"
        elif pair in _RETREAT_PAIRS:
            kind = "retreat"
        else:
            kind = "none"
        result.append(
            AdvanceRetreatRecord(
                position=line.position,
                original_branch=line.najia_branch,
                changed_branch=line.changed_najia_branch,
                kind=kind,
            )
        )
    return tuple(result)


def _fan_fu(record: LiuYaoCaseRecord) -> tuple[FanFuRecord, ...]:
    if not record.chart.moving_lines:
        return ()
    original_najia = _identity_najia(record.chart.original)
    changed_najia = _identity_najia(record.chart.changed)
    moving = set(record.chart.moving_lines)
    result: list[FanFuRecord] = []
    for position in sorted(moving):
        original_branch = original_najia[position - 1][1]
        changed_branch = changed_najia[position - 1][1]
        relation = _branch_relation(original_branch, changed_branch)
        if relation == "same":
            result.append(FanFuRecord(scope="line", kind="fuyin", positions=(position,)))
        elif relation == "clash":
            result.append(FanFuRecord(scope="line", kind="fanyin", positions=(position,)))

    for scope, positions in (("inner", (1, 2, 3)), ("outer", (4, 5, 6)), ("hexagram", (1, 2, 3, 4, 5, 6))):
        if not moving.intersection(positions):
            continue
        relations = tuple(
            _branch_relation(original_najia[position - 1][1], changed_najia[position - 1][1])
            for position in positions
        )
        if all(relation == "same" for relation in relations):
            result.append(FanFuRecord(scope=scope, kind="fuyin", positions=positions))
        elif all(relation == "clash" for relation in relations):
            result.append(FanFuRecord(scope=scope, kind="fanyin", positions=positions))
    return tuple(result)


def _is_month_broken(branch: str, context: CalendarContextReceipt) -> bool:
    return _branch_relation(context.month_branch, branch) == "clash"


def _activation_state(branch: str, moving: bool, is_void: bool, context: CalendarContextReceipt) -> str:
    conditions: list[str] = []
    if is_void:
        conditions.append("void")
    if _is_month_broken(branch, context):
        conditions.append("month_broken")
    if conditions:
        return "conditional_" + "_and_".join(conditions)
    return "moving" if moving else "static"


def _spirit_role(actor_element: str, target_element: str, *, same_actor: bool = False) -> str:
    if same_actor:
        return "用神候选"
    relation = _element_relation(actor_element, target_element)
    return {
        "generates": "原神候选",
        "controls": "忌神候选",
        "peer": "同类候选",
        "drains": "泄神候选",
        "controlled_by_target": "仇神候选",
    }[relation]


def _target_line(record: LiuYaoCaseRecord, request: InterpretationRequest) -> LiuYaoLine | None:
    candidates = [line for line in record.chart.lines if line.six_relation == request.use_relation]
    if request.primary_position is not None:
        line = record.chart.lines[request.primary_position - 1]
        if line.six_relation != request.use_relation:
            raise LiuYaoError(
                "USE_GOD_MISMATCH",
                f"第 {request.primary_position} 爻六亲为{line.six_relation}，与 use_relation={request.use_relation} 不一致",
            )
        return line
    if len(candidates) == 1:
        return candidates[0]
    return None


def _spirit_roles(
    record: LiuYaoCaseRecord,
    request: InterpretationRequest,
    context: CalendarContextReceipt,
    hidden: Sequence[HiddenSpiritRecord],
) -> tuple[SpiritRoleRecord, ...]:
    target = _target_line(record, request)
    visible_targets = [line for line in record.chart.lines if line.six_relation == request.use_relation]
    hidden_targets = [item for item in hidden if item.relation == request.use_relation]
    target_element: str | None = target.element if target is not None else None
    if target_element is None and visible_targets:
        target_element = visible_targets[0].element
    if target_element is None and hidden_targets:
        target_element = hidden_targets[0].hidden_element
    if target_element is None:
        return ()

    result: list[SpiritRoleRecord] = []
    for line in record.chart.lines:
        result.append(
            SpiritRoleRecord(
                actor_id=f"line:{line.position}",
                position=line.position,
                candidate_kind="visible",
                branch=line.najia_branch,
                element=line.element,
                role=_spirit_role(
                    line.element,
                    target_element,
                    same_actor=line.six_relation == request.use_relation,
                ),
                activation_state=_activation_state(
                    line.najia_branch,
                    line.moving,
                    bool(line.najia_branch in context.void_branches),
                    context,
                ),
            )
        )
    for item in hidden:
        result.append(
            SpiritRoleRecord(
                actor_id=f"hidden:{item.hidden_position}:{item.relation}",
                position=item.hidden_position,
                candidate_kind="hidden",
                branch=item.hidden_branch,
                element=item.hidden_element,
                role=_spirit_role(
                    item.hidden_element,
                    target_element,
                    same_actor=item.relation == request.use_relation,
                ),
                activation_state="hidden",
            )
        )
    return tuple(result)


def _add_relation_edges(
    record: LiuYaoCaseRecord,
    context: CalendarContextReceipt,
    hidden: Sequence[HiddenSpiritRecord],
) -> tuple[RelationEdge, ...]:
    edges: list[RelationEdge] = []

    def add(
        actor_id: str,
        target_id: str,
        relation_kind: str,
        relation: str,
        active_state: str,
        technical: str,
        caveat: str | None = None,
    ) -> None:
        edges.append(
            RelationEdge(
                edge_id=f"LYE3-{len(edges) + 1:04d}",
                actor_id=actor_id,
                target_id=target_id,
                relation_kind=relation_kind,
                relation=relation,
                active_state=active_state,
                technical=technical,
                caveat=caveat,
            )
        )

    for source_id, source_branch in (("environment:month", context.month_branch), ("environment:day", context.day_branch)):
        source_element = BRANCH_ELEMENTS[source_branch]
        for line in record.chart.lines:
            branch_relation = _branch_relation(source_branch, line.najia_branch)
            if branch_relation is not None:
                add(
                    source_id,
                    f"line:{line.position}",
                    "branch",
                    branch_relation,
                    "active",
                    f"{source_id} {source_branch} 与第{line.position}爻 {line.najia_branch} 的地支关系为 {branch_relation}。",
                    "六合和日冲仅登记结构，不自动定向。" if branch_relation in {"combine", "clash"} else None,
                )
            add(
                source_id,
                f"line:{line.position}",
                "element",
                _element_relation(source_element, line.element),
                "active",
                f"{source_id} {source_element} 对第{line.position}爻 {line.element} 的五行关系。",
            )

    for actor in record.chart.lines:
        if not actor.moving:
            continue
        actor_state = _activation_state(
            actor.najia_branch,
            True,
            actor.najia_branch in context.void_branches,
            context,
        )
        for target in record.chart.lines:
            if target.position == actor.position:
                continue
            branch_relation = _branch_relation(actor.najia_branch, target.najia_branch)
            if branch_relation is not None:
                add(
                    f"line:{actor.position}",
                    f"line:{target.position}",
                    "branch",
                    branch_relation,
                    actor_state,
                    f"动爻第{actor.position}爻 {actor.najia_branch} 与第{target.position}爻 {target.najia_branch} 的地支关系。",
                    "动爻空破时作用保持条件性。" if actor_state.startswith("conditional") else None,
                )
            add(
                f"line:{actor.position}",
                f"line:{target.position}",
                "element",
                _element_relation(actor.element, target.element),
                actor_state,
                f"动爻第{actor.position}爻 {actor.element} 对第{target.position}爻 {target.element} 的五行关系。",
                "动爻空破时作用保持条件性。" if actor_state.startswith("conditional") else None,
            )

        if actor.changed_najia_branch is None or actor.changed_element is None:
            continue
        changed_state = _activation_state(
            actor.changed_najia_branch,
            True,
            actor.changed_najia_branch in context.void_branches,
            context,
        )
        for target in record.chart.lines:
            branch_relation = _branch_relation(actor.changed_najia_branch, target.najia_branch)
            if branch_relation is not None:
                add(
                    f"changed:{actor.position}",
                    f"line:{target.position}",
                    "branch",
                    branch_relation,
                    changed_state,
                    f"第{actor.position}爻之变爻 {actor.changed_najia_branch} 与第{target.position}爻 {target.najia_branch} 的地支关系。",
                    "跨位变爻关系只登记，不推导传递链终局。",
                )
            add(
                f"changed:{actor.position}",
                f"line:{target.position}",
                "element",
                _element_relation(actor.changed_element, target.element),
                changed_state,
                f"第{actor.position}爻之变爻 {actor.changed_element} 对第{target.position}爻 {target.element} 的五行关系。",
                "跨位变爻关系只登记，不推导传递链终局。",
            )

    for item in hidden:
        state = "hidden"
        add(
            f"line:{item.flying_position}",
            f"hidden:{item.hidden_position}:{item.relation}",
            "element",
            item.flying_to_hidden,
            state,
            f"飞神第{item.flying_position}爻 {item.flying_element} 对伏神 {item.hidden_element} 的五行关系。",
            "伏神能否出伏需要月日、飞神和动变条件共同判断。",
        )
        add(
            f"hidden:{item.hidden_position}:{item.relation}",
            f"line:{item.flying_position}",
            "element",
            item.hidden_to_flying,
            state,
            f"伏神 {item.hidden_element} 对飞神第{item.flying_position}爻 {item.flying_element} 的五行关系。",
            "伏神能否出伏需要月日、飞神和动变条件共同判断。",
        )
    return tuple(edges)


def _candidate_factors_visible(
    line: LiuYaoLine,
    context: CalendarContextReceipt,
    growth: GrowthStageRecord,
    advance: AdvanceRetreatRecord | None,
) -> tuple[CandidateFactor, ...]:
    factors: list[CandidateFactor] = [
        CandidateFactor("visible_base", _SCORING_WEIGHTS["visible_base"], False, "本卦可见用神候选。")
    ]

    month_branch_relation = _branch_relation(context.month_branch, line.najia_branch)
    month_element_relation = _element_relation(BRANCH_ELEMENTS[context.month_branch], line.element)
    if month_branch_relation == "same":
        factors.append(CandidateFactor("month_same", _SCORING_WEIGHTS["month_same"], False, "临月建。"))
    elif month_branch_relation == "clash":
        factors.append(CandidateFactor("month_break", _SCORING_WEIGHTS["month_break"], False, "月建六冲，构成月破结构。"))
    elif month_branch_relation == "combine":
        factors.append(CandidateFactor("month_combine", 0, True, "月建六合，合起、合绊或合化未定。"))
    else:
        month_code = {
            "generates": "month_generate",
            "peer": "month_peer",
            "controls": "month_control",
            "drains": "month_drain",
            "controlled_by_target": "month_controlled_by_use",
        }[month_element_relation]
        factors.append(
            CandidateFactor(
                month_code,
                _SCORING_WEIGHTS.get(month_code, 0),
                month_code == "month_controlled_by_use",
                f"月建与候选五行关系为 {month_element_relation}。",
            )
        )

    day_branch_relation = _branch_relation(context.day_branch, line.najia_branch)
    day_element_relation = _element_relation(BRANCH_ELEMENTS[context.day_branch], line.element)
    if day_branch_relation == "same":
        factors.append(CandidateFactor("day_same", _SCORING_WEIGHTS["day_same"], False, "临日辰。"))
    elif day_branch_relation == "clash":
        factors.append(CandidateFactor("day_clash", 0, True, "日辰六冲，冲起或冲散未定。"))
    elif day_branch_relation == "combine":
        factors.append(CandidateFactor("day_combine", 0, True, "日辰六合，具体作用未定。"))
    else:
        day_code = {
            "generates": "day_generate",
            "peer": "day_peer",
            "controls": "day_control",
            "drains": "day_drain",
            "controlled_by_target": "day_controlled_by_use",
        }[day_element_relation]
        factors.append(
            CandidateFactor(
                day_code,
                _SCORING_WEIGHTS.get(day_code, 0),
                day_code == "day_controlled_by_use",
                f"日辰与候选五行关系为 {day_element_relation}。",
            )
        )

    if line.moving:
        factors.append(CandidateFactor("moving", _SCORING_WEIGHTS["moving"], False, "候选爻发动。"))
    if line.najia_branch in context.void_branches:
        factors.append(CandidateFactor("void", _SCORING_WEIGHTS["void"], True, "候选爻旬空，需考虑旺空、动空、冲空。"))

    for stage in (growth.month_stage, growth.day_stage):
        stage_code = {
            "长生": "growth_changsheng",
            "临官": "growth_linguan",
            "帝旺": "growth_diwang",
            "墓": "growth_tomb",
            "绝": "growth_extinction",
        }.get(stage)
        if stage_code is not None:
            factors.append(CandidateFactor(stage_code, _SCORING_WEIGHTS[stage_code], True, f"十二长生见{stage}。"))

    if line.moving and line.changed_element is not None and line.changed_najia_branch is not None:
        changed_is_void = line.changed_najia_branch in context.void_branches
        changed_is_month_broken = _is_month_broken(line.changed_najia_branch, context)
        if changed_is_void:
            factors.append(CandidateFactor("changed_void", 0, True, "变爻旬空，回头作用保持条件性。"))
        if changed_is_month_broken:
            factors.append(CandidateFactor("changed_month_break", 0, True, "变爻月破，回头作用保持条件性。"))
        return_effect_conditional = changed_is_void or changed_is_month_broken
        changed_relation = _element_relation(line.changed_element, line.element)
        if changed_relation == "generates":
            factors.append(
                CandidateFactor(
                    "return_generate",
                    _SCORING_WEIGHTS["return_generate"],
                    return_effect_conditional,
                    "变爻回头生；变爻空破时不得提前视为有效助力。",
                )
            )
        elif changed_relation == "controls":
            factors.append(
                CandidateFactor(
                    "return_control",
                    _SCORING_WEIGHTS["return_control"],
                    return_effect_conditional,
                    "变爻回头克；变爻空破时不得提前视为有效压制。",
                )
            )
    if advance is not None and advance.kind in {"advance", "retreat"}:
        factors.append(CandidateFactor(advance.kind, _SCORING_WEIGHTS[advance.kind], True, f"动变为{advance.kind}。"))
    return tuple(factors)


def _candidate_factors_hidden(
    item: HiddenSpiritRecord,
    context: CalendarContextReceipt,
) -> tuple[CandidateFactor, ...]:
    factors: list[CandidateFactor] = [
        CandidateFactor("hidden_base", _SCORING_WEIGHTS["hidden_base"], True, "该用神只见于伏神。")
    ]
    month_branch_relation = _branch_relation(context.month_branch, item.hidden_branch)
    month_element_relation = _element_relation(BRANCH_ELEMENTS[context.month_branch], item.hidden_element)
    if month_branch_relation == "same":
        factors.append(CandidateFactor("month_same", _SCORING_WEIGHTS["month_same"], True, "伏神临月建。"))
    elif month_branch_relation == "clash":
        factors.append(CandidateFactor("month_break", _SCORING_WEIGHTS["month_break"], True, "伏神月破。"))
    elif month_branch_relation == "combine":
        factors.append(CandidateFactor("month_combine", 0, True, "伏神与月建六合，具体作用未定。"))
    else:
        month_code = {
            "generates": "month_generate",
            "peer": "month_peer",
            "controls": "month_control",
            "drains": "month_drain",
            "controlled_by_target": "month_controlled_by_use",
        }[month_element_relation]
        factors.append(CandidateFactor(month_code, _SCORING_WEIGHTS.get(month_code, 0), True, f"月建与伏神五行关系为 {month_element_relation}。"))

    day_branch_relation = _branch_relation(context.day_branch, item.hidden_branch)
    day_element_relation = _element_relation(BRANCH_ELEMENTS[context.day_branch], item.hidden_element)
    if day_branch_relation == "same":
        factors.append(CandidateFactor("day_same", _SCORING_WEIGHTS["day_same"], True, "伏神临日辰。"))
    elif day_branch_relation == "clash":
        factors.append(CandidateFactor("day_clash", 0, True, "伏神受日冲，具体作用未定。"))
    elif day_branch_relation == "combine":
        factors.append(CandidateFactor("day_combine", 0, True, "伏神与日辰六合，具体作用未定。"))
    else:
        day_code = {
            "generates": "day_generate",
            "peer": "day_peer",
            "controls": "day_control",
            "drains": "day_drain",
            "controlled_by_target": "day_controlled_by_use",
        }[day_element_relation]
        factors.append(CandidateFactor(day_code, _SCORING_WEIGHTS.get(day_code, 0), True, f"日辰与伏神五行关系为 {day_element_relation}。"))

    if item.hidden_branch in context.void_branches:
        factors.append(CandidateFactor("void", _SCORING_WEIGHTS["void"], True, "伏神旬空。"))
    if item.flying_to_hidden == "generates":
        factors.append(CandidateFactor("flying_generates_hidden", 1, True, "飞神生伏神，但仍需出伏条件。"))
    elif item.flying_to_hidden == "controls":
        factors.append(CandidateFactor("flying_controls_hidden", -2, True, "飞神克伏神，且仍需出伏条件。"))
    for stage in (item.month_stage, item.day_stage):
        stage_code = {
            "长生": "growth_changsheng",
            "临官": "growth_linguan",
            "帝旺": "growth_diwang",
            "墓": "growth_tomb",
            "绝": "growth_extinction",
        }.get(stage)
        if stage_code is not None:
            factors.append(CandidateFactor(stage_code, _SCORING_WEIGHTS[stage_code], True, f"伏神十二长生见{stage}。"))
    return tuple(factors)


def _rank_use_candidates(
    record: LiuYaoCaseRecord,
    request: InterpretationRequest,
    context: CalendarContextReceipt,
    hidden: Sequence[HiddenSpiritRecord],
    growth: Sequence[GrowthStageRecord],
    advance: Sequence[AdvanceRetreatRecord],
) -> tuple[tuple[UseCandidateScore, ...], str, int | None]:
    provisional: list[tuple[str, str, int, str, str, tuple[CandidateFactor, ...]]] = []
    growth_by_position = {item.position: item for item in growth}
    advance_by_position = {item.position: item for item in advance}
    for line in record.chart.lines:
        if line.six_relation != request.use_relation:
            continue
        factors = _candidate_factors_visible(line, context, growth_by_position[line.position], advance_by_position.get(line.position))
        provisional.append(
            (
                f"line:{line.position}",
                "visible",
                line.position,
                line.najia_branch,
                line.element,
                factors,
            )
        )
    for item in hidden:
        if item.relation != request.use_relation:
            continue
        factors = _candidate_factors_hidden(item, context)
        provisional.append(
            (
                f"hidden:{item.hidden_position}:{item.relation}",
                "hidden",
                item.hidden_position,
                item.hidden_branch,
                item.hidden_element,
                factors,
            )
        )

    if not provisional:
        return (), "no_candidate", None

    scored = [(entry, sum(factor.weight for factor in entry[5])) for entry in provisional]
    distinct_scores = sorted({score for _entry, score in scored}, reverse=True)
    rank_by_score = {score: index + 1 for index, score in enumerate(distinct_scores)}
    candidates = tuple(
        UseCandidateScore(
            candidate_id=entry[0],
            relation=request.use_relation,
            position=entry[2],
            candidate_kind=entry[1],
            branch=entry[3],
            element=entry[4],
            score=score,
            rank=rank_by_score[score],
            factors=entry[5],
        )
        for entry, score in sorted(scored, key=lambda item: (-item[1], item[0][1] != "visible", item[0][2], item[0][0]))
    )

    top = [item for item in candidates if item.rank == 1]
    if request.reality_status == "blocking":
        return candidates, "reality_blocked", None
    if request.primary_position is not None:
        explicit = next(
            (item for item in candidates if item.candidate_kind == "visible" and item.position == request.primary_position),
            None,
        )
        if explicit is None:
            raise LiuYaoError("USE_GOD_MISMATCH", "primary_position 未对应可见用神候选")
        return candidates, "explicit_primary", explicit.position
    if len(top) > 1:
        return candidates, "tie", None
    leader = top[0]
    if leader.candidate_kind == "hidden":
        return candidates, "hidden_leader_requires_confirmation", None
    second_score = candidates[1].score if len(candidates) > 1 else None
    if second_score is not None and leader.score - second_score < 2:
        return candidates, "narrow_margin", None
    if any(factor.conditional for factor in leader.factors):
        return candidates, "provisional_leader", leader.position
    return candidates, "ranked_leader", leader.position


def _conflict_matrix(
    record: LiuYaoCaseRecord,
    request: InterpretationRequest,
    context: CalendarContextReceipt,
    candidates: Sequence[UseCandidateScore],
    ranking_status: str,
    hidden: Sequence[HiddenSpiritRecord],
) -> tuple[RuleConflictRecord, ...]:
    conflicts: list[RuleConflictRecord] = []

    def add(code: str, priority: int, resolution: str, involved: Sequence[str], technical: str, plain: str) -> None:
        conflicts.append(
            RuleConflictRecord(
                conflict_id=f"LYC3-{len(conflicts) + 1:03d}",
                code=code,
                priority=priority,
                resolution=resolution,
                involved_ids=tuple(involved),
                technical=technical,
                plain=plain,
            )
        )

    if request.reality_status == "blocking":
        add(
            "REALITY_OVERRIDE",
            100,
            "reality_override",
            tuple(item.candidate_id for item in candidates),
            "已确认现实阻断优先于全部传统结构候选。",
            "现实条件已经阻断时，不允许用盘面排序覆盖客观事实。",
        )
    if ranking_status == "explicit_primary" and request.primary_position is not None:
        selected = next(
            (item for item in candidates if item.candidate_kind == "visible" and item.position == request.primary_position),
            None,
        )
        if selected is not None and selected.rank != 1:
            add(
                "EXPLICIT_PRIMARY_DIFFERS_FROM_RANKING",
                75,
                "preserve_explicit_selection",
                (selected.candidate_id, *(item.candidate_id for item in candidates if item.rank == 1)),
                "调用方明确用神爻位与结构排序领先候选不同。",
                "明确取用优先保留，排序只提示复核，不能静默改换用神。",
            )

    if ranking_status in {"tie", "narrow_margin"}:
        add(
            "USE_RANKING_UNRESOLVED",
            80,
            "manual_confirmation_required",
            tuple(item.candidate_id for item in candidates if item.rank == 1 or ranking_status == "narrow_margin"),
            "用神候选排序并未形成足够区分度。",
            "候选接近或并列，不能把排序强行写成已确认用神。",
        )
    if ranking_status == "hidden_leader_requires_confirmation":
        add(
            "HIDDEN_USE_REQUIRES_CONFIRMATION",
            80,
            "manual_confirmation_required",
            tuple(item.candidate_id for item in candidates if item.rank == 1),
            "最高候选为伏神。",
            "伏神是否能够出伏尚需飞伏、月日和动变条件，不能自动确认为主用神。",
        )

    for candidate in candidates:
        positive = [factor.code for factor in candidate.factors if factor.weight > 0]
        negative = [factor.code for factor in candidate.factors if factor.weight < 0]
        codes = {factor.code for factor in candidate.factors}
        if positive and negative:
            add(
                "MIXED_CANDIDATE_FACTORS",
                50,
                "preserve_both",
                (candidate.candidate_id,),
                f"候选同时存在支持因素 {positive} 与约束因素 {negative}。",
                "候选并非单向旺或弱，排序分只是审查工具，正反因素必须同时保留。",
            )
        if "void" in codes and "day_clash" in codes:
            add(
                "VOID_CLASH_CONDITIONAL",
                70,
                "defer_direction",
                (candidate.candidate_id,),
                "旬空与日冲并见。",
                "冲空可能触发，也可能仍受其他条件限制，本阶段不提前定向。",
            )
        if "month_break" in codes and "moving" in codes:
            add(
                "MONTH_BREAK_MOVING_CONDITIONAL",
                70,
                "defer_direction",
                (candidate.candidate_id,),
                "月破与发动并见。",
                "发动并不自动消除月破，月破也不自动抹掉动爻，保留条件冲突。",
            )
        has_advance_or_retreat = bool({"advance", "retreat"} & codes)
        has_original_validity_limit = bool({"void", "month_break"} & codes)
        if has_advance_or_retreat and has_original_validity_limit:
            add(
                "ADVANCE_RETREAT_VALIDITY_CONDITIONAL",
                70,
                "defer_direction",
                (candidate.candidate_id,),
                "进退神与旬空或月破并见。",
                "进退只记录方向结构；原爻空破时，不能直接把化进当增强或把化退当减弱。",
            )
        has_return_effect = bool({"return_generate", "return_control"} & codes)
        has_changed_validity_limit = bool({"changed_void", "changed_month_break"} & codes)
        if has_return_effect and has_changed_validity_limit:
            add(
                "RETURN_EFFECT_VALIDITY_CONDITIONAL",
                72,
                "defer_direction",
                (candidate.candidate_id,),
                "回头生克与变爻空破并见。",
                "变爻自身空破时，回头生克只能作为待复核结构，不能提前计为终局作用。",
            )
        has_tomb_or_extinction = bool({"growth_tomb", "growth_extinction"} & codes)
        has_direct_environment_support = bool(
            {"month_same", "month_generate", "day_same", "day_generate"} & codes
        )
        if has_tomb_or_extinction and has_direct_environment_support:
            add(
                "GROWTH_STAGE_ENVIRONMENT_CONFLICT",
                60,
                "preserve_both",
                (candidate.candidate_id,),
                "十二长生墓绝与月日直接支持并见。",
                "墓绝不能脱离月日生扶单独判弱；两类结构同时保留，不做一票否决。",
            )
        if "flying_controls_hidden" in codes:
            add(
                "HIDDEN_FLYING_CONSTRAINT",
                55,
                "manual_confirmation_required",
                (candidate.candidate_id,),
                "飞神克制伏神。",
                "伏神受飞神压制，但是否能够出伏仍取决于月日和动变，不能仅凭飞克伏判失败。",
            )
        if ({"month_combine", "day_clash"} <= codes) or ({"day_combine", "month_break"} <= codes):
            add(
                "COMBINE_CLASH_CONCURRENT",
                65,
                "unresolved",
                (candidate.candidate_id,),
                "六合与六冲同时作用于同一候选。",
                "合与冲并见时不能只取其一，需要更完整的先后、旺衰与动静条件。",
            )

    hidden_ids = tuple(f"hidden:{item.hidden_position}:{item.relation}" for item in hidden)
    if hidden_ids:
        add(
            "HIDDEN_SPIRITS_PRESENT",
            30,
            "descriptive_only",
            hidden_ids,
            "本卦存在缺失六亲的伏神结构。",
            "伏神已被计算并留痕，但不会仅凭出现伏神就判断成败。",
        )

    # Stable ordering makes the output auditable when multiple conflict classes coexist.
    return tuple(sorted(conflicts, key=lambda item: (-item.priority, item.conflict_id)))


def build_advanced_structure(
    record: LiuYaoCaseRecord,
    request: InterpretationRequest,
) -> AdvancedStructureResult:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    if not isinstance(request, InterpretationRequest):
        raise LiuYaoError("INVALID_INPUT", "request 必须是 InterpretationRequest")

    context = derive_calendar_context(record)
    effective_cast = replace(
        record.cast,
        month_branch=context.month_branch,
        day_ganzhi=context.day_ganzhi,
    )
    effective_record = create_case_record(effective_cast)
    effective_request = replace(request, calendar_context_confirmed=True)
    base = interpret_case(effective_record, effective_request)
    hidden = _hidden_spirits(effective_record, context)
    growth = _growth_stages(effective_record, context)
    advance = _advance_retreat(effective_record)
    fan_fu = _fan_fu(effective_record)
    graph = _add_relation_edges(effective_record, context, hidden)
    roles = _spirit_roles(effective_record, effective_request, context, hidden)
    candidates, ranking_status, recommended = _rank_use_candidates(
        effective_record,
        effective_request,
        context,
        hidden,
        growth,
        advance,
    )
    conflicts = _conflict_matrix(
        effective_record,
        effective_request,
        context,
        candidates,
        ranking_status,
        hidden,
    )

    warnings: list[str] = []
    if record.cast.month_branch is None or record.cast.day_ganzhi is None:
        warnings.append("月建与日辰由已验证的内部确定性历法模块从 completed_at 自动生成。")
    if record.cast.location and record.cast.completed_at:
        warnings.append("当前自动历法使用 completed_at 内的固定 UTC 偏移；location 文本不自动解析为经纬度或 IANA 时区。")
    if request.primary_position is None and recommended is not None:
        warnings.append("recommended_position 只是排序领先候选，不等于已确认用神。")
    if base.status == "unsupported_focus":
        status = "unsupported_focus"
        recommended = None
    elif request.reality_status == "blocking":
        status = "reality_blocked"
        recommended = None
    elif not candidates:
        status = "no_use_candidate"
    elif ranking_status in {"tie", "narrow_margin", "hidden_leader_requires_confirmation", "provisional_leader"}:
        status = "needs_confirmation"
    else:
        status = "advanced_structure_ready"

    limits = (
        "本层只扩展确定性结构与候选排序，不生成事件成功概率或应期。",
        "十二长生按五行顺行（木亥、火寅、金巳、水土申起长生）的版本化口径；结构出现不自动等于吉凶。",
        "伏神只按本宫纯卦补齐缺失六亲，能否出伏仍需后续经审查的条件树。",
        "合化、三合局、暗动终局、复杂旺衰裁决和跨位传递终局仍未实现。",
        "现实证据与专业意见优先；健康、法律、投资及医学问题不由本层替代专业判断。",
        "结果固定为 review_only、production_allowed=false、prediction_validity=not_evaluated。",
    )

    return AdvancedStructureResult(
        case_id=record.cast.case_id,
        chart_sha256=record.chart.canonical_sha256,
        effective_chart_sha256=effective_record.chart.canonical_sha256,
        request_sha256=request.canonical_sha256,
        effective_request_sha256=effective_request.canonical_sha256,
        base_interpretation_sha256=base.canonical_sha256,
        calendar_context=context,
        hidden_spirits=hidden,
        growth_stages=growth,
        advance_retreat=advance,
        fan_fu=fan_fu,
        relation_graph=graph,
        spirit_roles=roles,
        use_candidates=candidates,
        ranking_status=ranking_status,
        recommended_position=recommended,
        conflicts=conflicts,
        status=status,
        warnings=tuple(warnings),
        limits=limits,
    )


__all__ = [
    "ADVANCED_PRODUCTION_ALLOWED",
    "ADVANCED_STATIC_TABLE_SHA256",
    "ADVANCED_STRUCTURE_METHOD_ID",
    "ADVANCED_STRUCTURE_STATUS",
    "AdvanceRetreatRecord",
    "AdvancedStructureResult",
    "CalendarContextReceipt",
    "CandidateFactor",
    "FanFuRecord",
    "GrowthStageRecord",
    "HiddenSpiritRecord",
    "RelationEdge",
    "RuleConflictRecord",
    "SpiritRoleRecord",
    "UseCandidateScore",
    "build_advanced_structure",
    "derive_calendar_context",
    "growth_stage",
]
