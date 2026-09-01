from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .case_record import LiuYaoCaseRecord
from .models import LiuYaoChart, LiuYaoLine
from .tables import BRANCH_ELEMENTS, CONTROLS, GENERATES, PREDICTION_VALIDITY, digest
from .validation import LiuYaoError, _non_empty, _reject_unknown, _string_tuple

INTERPRETATION_METHOD_ID = "liuyao-structural-evidence@0.1.0"
INTERPRETATION_STATUS = "review_only"
PRODUCTION_ALLOWED = False

SIX_RELATIONS = frozenset({"父母", "兄弟", "子孙", "妻财", "官鬼"})
EVIDENCE_POLARITIES = frozenset({"supportive", "restrictive", "ambiguous", "neutral"})
REALITY_STATUSES = frozenset({"unknown", "supportive", "blocking", "mixed"})

_TOPIC_ALIASES = {
    "general": "general",
    "综合": "general",
    "career": "career",
    "事业": "career",
    "exam": "exam",
    "考公考编": "exam",
    "考试": "exam",
    "wealth": "wealth",
    "财运": "wealth",
    "relationship_reconciliation": "relationship_reconciliation",
    "感情复合": "relationship_reconciliation",
    "复合": "relationship_reconciliation",
    "pregnancy": "pregnancy",
    "求孕": "pregnancy",
    "documents": "documents",
    "文书": "documents",
    "health": "health",
    "健康": "health",
}

_REALITY_STATUS_ALIASES = {
    "unknown": "unknown",
    "未知": "unknown",
    "supportive": "supportive",
    "支持": "supportive",
    "blocking": "blocking",
    "阻断": "blocking",
    "mixed": "mixed",
    "混合": "mixed",
}

_TOPIC_DIMENSIONS: Mapping[str, tuple[tuple[str, str, str], ...]] = {
    "general": (
        ("current_event", "structural", "只分析事件合同所冻结的当前事件。"),
    ),
    "career": (
        ("current_position_event", "structural", "只分析当前岗位或录用事件，不能替代长期职业规划。"),
        ("career_fit", "reality_required", "长期职业适配需要履历、能力、行业和岗位约束。"),
    ),
    "exam": (
        ("system_fit", "outside_single_cast", "体制适配度不能由一次六爻单独推出。"),
        ("current_exam", "structural", "仅对应事件合同中冻结的本次考试或录用结果。"),
        ("position_direction", "reality_required", "岗位方向必须结合专业、地区、资格和竞争数据。"),
        ("preparation_strategy", "reality_required", "备考策略必须结合真实成绩、剩余时间和薄弱科目。"),
    ),
    "wealth": (
        ("current_money_event", "structural", "仅对应当前合同冻结的收入、回款或支出事件。"),
        ("risk_capacity", "reality_required", "风险承受能力必须根据真实财务状况判断。"),
    ),
    "relationship_reconciliation": (
        ("bond", "structural", "缘分牵引只作为单独一层，不等于会复联。"),
        ("recontact", "structural", "复联必须与复合分开判断。"),
        ("reconciliation", "structural", "复合不自动代表关系能够稳定。"),
        ("stability", "structural", "稳定性必须另看现实关系条件并单独冻结标准。"),
    ),
    "pregnancy": (
        ("conception_opportunity", "structural", "只提供传统结构观察，不替代医学检查。"),
        ("medical_confirmation", "professional_only", "是否临床妊娠只能由医学检查确认。"),
        ("pregnancy_stability", "professional_only", "妊娠稳定性不能由受孕机会自动推出。"),
        ("medical_factors", "professional_only", "年龄、周期和生殖健康等现实医学因素优先。"),
    ),
    "documents": (
        ("current_document_event", "structural", "仅对应当前合同中的成绩、证书、合同或材料事件。"),
    ),
    "health": (
        ("traditional_structure", "advisory_only", "只能记录传统结构，不能诊断疾病或决定治疗。"),
        ("medical_assessment", "professional_only", "症状、检查和治疗必须由医疗专业人员判断。"),
    ),
}

_DEFAULT_FOCUS = {
    "general": "current_event",
    "career": "current_position_event",
    "exam": "current_exam",
    "wealth": "current_money_event",
    "relationship_reconciliation": "reconciliation",
    "pregnancy": "conception_opportunity",
    "documents": "current_document_event",
    "health": "traditional_structure",
}

_STRUCTURAL_SCOPES = frozenset({"structural", "advisory_only"})

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


@dataclass(frozen=True, slots=True)
class InterpretationRequest:
    topic: str
    use_relation: str
    focus_dimension: str | None = None
    primary_position: int | None = None
    secondary_relations: tuple[str, ...] = ()
    calendar_context_confirmed: bool = False
    reality_status: str = "unknown"
    reality_facts: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        topic_text = _non_empty(self.topic, "topic")
        topic = _TOPIC_ALIASES.get(topic_text)
        if topic is None:
            raise LiuYaoError("INVALID_INPUT", f"不支持的 topic：{topic_text}")
        object.__setattr__(self, "topic", topic)

        relation = _non_empty(self.use_relation, "use_relation")
        if relation not in SIX_RELATIONS:
            raise LiuYaoError("INVALID_INPUT", "use_relation 必须是父母、兄弟、子孙、妻财或官鬼")
        object.__setattr__(self, "use_relation", relation)

        dimension_ids = {item[0] for item in _TOPIC_DIMENSIONS[topic]}
        focus = self.focus_dimension or _DEFAULT_FOCUS[topic]
        if focus not in dimension_ids:
            raise LiuYaoError("INVALID_INPUT", f"focus_dimension 不属于 {topic}：{focus}")
        object.__setattr__(self, "focus_dimension", focus)

        if self.primary_position is not None:
            if isinstance(self.primary_position, bool) or not isinstance(self.primary_position, int) or not 1 <= self.primary_position <= 6:
                raise LiuYaoError("INVALID_INPUT", "primary_position 必须是 1 到 6 的整数")

        secondary = _string_tuple(self.secondary_relations, "secondary_relations")
        if any(item not in SIX_RELATIONS for item in secondary):
            raise LiuYaoError("INVALID_INPUT", "secondary_relations 只能包含六亲名称")
        object.__setattr__(self, "secondary_relations", tuple(dict.fromkeys(item for item in secondary if item != relation)))

        if not isinstance(self.calendar_context_confirmed, bool):
            raise LiuYaoError("INVALID_INPUT", "calendar_context_confirmed 必须是布尔值")

        reality_text = _non_empty(self.reality_status, "reality_status")
        reality_status = _REALITY_STATUS_ALIASES.get(reality_text)
        if reality_status is None:
            raise LiuYaoError("INVALID_INPUT", "reality_status 必须是 unknown、supportive、blocking 或 mixed")
        object.__setattr__(self, "reality_status", reality_status)
        object.__setattr__(self, "reality_facts", _string_tuple(self.reality_facts, "reality_facts"))
        object.__setattr__(self, "notes", _string_tuple(self.notes, "notes"))
        if reality_status in {"supportive", "blocking", "mixed"} and not self.reality_facts:
            raise LiuYaoError("INVALID_INPUT", "非 unknown 的 reality_status 必须附带 reality_facts")

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "topic": self.topic,
            "focus_dimension": self.focus_dimension,
            "use_relation": self.use_relation,
            "primary_position": self.primary_position,
            "secondary_relations": list(self.secondary_relations),
            "calendar_context_confirmed": self.calendar_context_confirmed,
            "reality_status": self.reality_status,
            "reality_facts": list(self.reality_facts),
            "notes": list(self.notes),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "InterpretationRequest":
        allowed = {
            "topic",
            "focus_dimension",
            "use_relation",
            "primary_position",
            "secondary_relations",
            "calendar_context_confirmed",
            "reality_status",
            "reality_facts",
            "notes",
            "canonical_sha256",
        }
        _reject_unknown(value, allowed, "interpretation_request")
        missing = {"topic", "use_relation"} - set(value)
        if missing:
            raise LiuYaoError("INVALID_INPUT", f"interpretation_request 缺少字段：{', '.join(sorted(missing))}")
        request = cls(
            topic=value["topic"],
            focus_dimension=value.get("focus_dimension"),
            use_relation=value["use_relation"],
            primary_position=value.get("primary_position"),
            secondary_relations=_string_tuple(value.get("secondary_relations", ()), "secondary_relations"),
            calendar_context_confirmed=value.get("calendar_context_confirmed", False),
            reality_status=value.get("reality_status", "unknown"),
            reality_facts=_string_tuple(value.get("reality_facts", ()), "reality_facts"),
            notes=_string_tuple(value.get("notes", ()), "notes"),
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != request.canonical_sha256:
            raise LiuYaoError("RECORD_TAMPERED", "interpretation_request canonical_sha256 与重算结果不一致")
        return request


@dataclass(frozen=True, slots=True)
class UseLineSelection:
    relation: str
    status: str
    selected_position: int | None
    candidate_positions: tuple[int, ...]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "relation": self.relation,
            "status": self.status,
            "selected_position": self.selected_position,
            "candidate_positions": list(self.candidate_positions),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class UseActor:
    position: int
    six_relation: str
    element: str
    moving: bool
    role_to_use: str

    def to_dict(self) -> dict[str, object]:
        return {
            "position": self.position,
            "six_relation": self.six_relation,
            "element": self.element,
            "moving": self.moving,
            "role_to_use": self.role_to_use,
        }


@dataclass(frozen=True, slots=True)
class InterpretationEvidence:
    evidence_id: str
    rule_id: str
    source_kind: str
    target_position: int
    actor_position: int | None
    relation: str
    polarity: str
    weight: int
    technical: str
    plain: str

    def __post_init__(self) -> None:
        if self.polarity not in EVIDENCE_POLARITIES:
            raise LiuYaoError("INVALID_INTERPRETATION", f"未知 evidence polarity：{self.polarity}")
        if isinstance(self.weight, bool) or not isinstance(self.weight, int) or self.weight < 0:
            raise LiuYaoError("INVALID_INTERPRETATION", "evidence weight 必须是非负整数")

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "rule_id": self.rule_id,
            "source_kind": self.source_kind,
            "target_position": self.target_position,
            "actor_position": self.actor_position,
            "relation": self.relation,
            "polarity": self.polarity,
            "weight": self.weight,
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class InterpretationConflict:
    conflict_id: str
    code: str
    evidence_ids: tuple[str, ...]
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "conflict_id": self.conflict_id,
            "code": self.code,
            "evidence_ids": list(self.evidence_ids),
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class InterpretationResult:
    case_id: str
    chart_sha256: str
    request: InterpretationRequest
    use_selection: UseLineSelection
    actors: tuple[UseActor, ...]
    evidence: tuple[InterpretationEvidence, ...]
    conflicts: tuple[InterpretationConflict, ...]
    topic_dimensions: tuple[Mapping[str, str], ...]
    status: str
    structural_balance: str
    support_score: int
    restrict_score: int
    confidence: str
    context_completeness: str
    headline: str
    plain_explanation: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "method_id": INTERPRETATION_METHOD_ID,
            "interpretation_status": INTERPRETATION_STATUS,
            "production_allowed": PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "case_id": self.case_id,
            "chart_sha256": self.chart_sha256,
            "request": self.request.to_dict(),
            "use_selection": self.use_selection.to_dict(),
            "actors": [item.to_dict() for item in self.actors],
            "evidence": [item.to_dict() for item in self.evidence],
            "conflicts": [item.to_dict() for item in self.conflicts],
            "topic_dimensions": [dict(item) for item in self.topic_dimensions],
            "status": self.status,
            "structural_balance": self.structural_balance,
            "support_score": self.support_score,
            "restrict_score": self.restrict_score,
            "confidence": self.confidence,
            "context_completeness": self.context_completeness,
            "headline": self.headline,
            "plain_explanation": self.plain_explanation,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def _focus_scope(request: InterpretationRequest) -> str:
    for dimension_id, scope, _plain in _TOPIC_DIMENSIONS[request.topic]:
        if dimension_id == request.focus_dimension:
            return scope
    raise RuntimeError("validated focus dimension disappeared")


def _topic_dimensions(request: InterpretationRequest) -> tuple[Mapping[str, str], ...]:
    result: list[Mapping[str, str]] = []
    for dimension_id, scope, plain in _TOPIC_DIMENSIONS[request.topic]:
        if dimension_id == request.focus_dimension:
            state = "focused"
        elif request.topic == "relationship_reconciliation":
            state = "separate_contract_required"
        else:
            state = "not_inferred"
        result.append({"dimension_id": dimension_id, "scope": scope, "state": state, "plain": plain})
    return tuple(result)


def _select_use_line(chart: LiuYaoChart, request: InterpretationRequest) -> UseLineSelection:
    candidates = tuple(line.position for line in chart.lines if line.six_relation == request.use_relation)
    if request.primary_position is not None:
        line = chart.lines[request.primary_position - 1]
        if line.six_relation != request.use_relation:
            raise LiuYaoError(
                "USE_GOD_MISMATCH",
                f"第 {request.primary_position} 爻六亲为{line.six_relation}，与 use_relation={request.use_relation} 不一致",
            )
        return UseLineSelection(
            relation=request.use_relation,
            status="confirmed",
            selected_position=request.primary_position,
            candidate_positions=candidates,
            reason="调用方已明确确认主用神爻位。",
        )
    if len(candidates) == 1:
        return UseLineSelection(
            relation=request.use_relation,
            status="unique_candidate",
            selected_position=candidates[0],
            candidate_positions=candidates,
            reason="该六亲在本卦中只有一个候选爻，自动选为结构分析对象。",
        )
    if not candidates:
        return UseLineSelection(
            relation=request.use_relation,
            status="not_found",
            selected_position=None,
            candidate_positions=(),
            reason="本卦没有对应六亲，当前版本不自动启用伏神或跨体系补位。",
        )
    return UseLineSelection(
        relation=request.use_relation,
        status="ambiguous",
        selected_position=None,
        candidate_positions=candidates,
        reason="同一六亲存在多个候选爻，必须由调用方确认 primary_position，系统不代替取用。",
    )


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
        return "generates_target"
    if CONTROLS[actor] == target:
        return "controls_target"
    if GENERATES[target] == actor:
        return "drains_target"
    if CONTROLS[target] == actor:
        return "target_controls_actor"
    raise RuntimeError(f"unknown element relation: {actor}/{target}")


def _role_to_use(line: LiuYaoLine, target: LiuYaoLine) -> str:
    if line.position == target.position:
        return "用神候选"
    relation = _element_relation(line.element, target.element)
    return {
        "generates_target": "元神候选",
        "controls_target": "忌神候选",
        "peer": "同类候选",
        "drains_target": "泄耗候选",
        "target_controls_actor": "受用神所制候选",
    }[relation]


def _context_completeness(chart: LiuYaoChart, request: InterpretationRequest) -> str:
    available = int(chart.month_branch is not None) + int(chart.day_ganzhi is not None)
    if not request.calendar_context_confirmed:
        return "unverified" if available else "missing"
    if available == 2:
        return "complete"
    if available == 1:
        return "partial"
    return "missing"


def interpret_case(record: LiuYaoCaseRecord, request: InterpretationRequest) -> InterpretationResult:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    if not isinstance(request, InterpretationRequest):
        raise LiuYaoError("INVALID_INPUT", "request 必须是 InterpretationRequest")

    chart = record.chart
    selection = _select_use_line(chart, request)
    dimensions = _topic_dimensions(request)
    context = _context_completeness(chart, request)
    warnings: list[str] = []
    limits = (
        "本层只整理传统结构证据，不判断事件必成或必败。",
        "六合、日冲、旬空等存在条件分支时只标记歧义，不自动解释为合起、合绊、冲起或冲散。",
        "本层不计算合化、伏神、进退神、反吟伏吟、墓绝或应期。",
        "现实事实和专业意见优先于盘面结构。",
        "结果固定为 review_only 与 prediction_validity=not_evaluated，不能用于准确率宣传。",
    )

    if not request.calendar_context_confirmed:
        if chart.month_branch is not None or chart.day_ganzhi is not None:
            warnings.append("月建或日柱虽已提供，但尚未确认来源，本次不用于解释。")
        else:
            warnings.append("缺少经确认的月建、日柱，月日旺衰相关证据不参与。")
    elif chart.month_branch is None or chart.day_ganzhi is None:
        warnings.append("月建或日柱不完整，只能使用现有部分，整体置信度降低。")

    all_reality_facts = tuple(dict.fromkeys((*record.cast.reality_facts, *request.reality_facts)))
    if request.reality_status == "unknown" and not all_reality_facts:
        warnings.append("未提供可核验现实条件，不能用盘面替代现实调查。")

    focus_scope = _focus_scope(request)
    if focus_scope not in _STRUCTURAL_SCOPES:
        return InterpretationResult(
            case_id=record.cast.case_id,
            chart_sha256=chart.canonical_sha256,
            request=request,
            use_selection=selection,
            actors=(),
            evidence=(),
            conflicts=(),
            topic_dimensions=dimensions,
            status="unsupported_focus",
            structural_balance="undetermined",
            support_score=0,
            restrict_score=0,
            confidence="low",
            context_completeness=context,
            headline="当前焦点不应由单次六爻解释。",
            plain_explanation="这一维度需要现实资料或专业判断，本层拒绝用盘面补出结论。",
            warnings=tuple(warnings),
            limits=limits,
        )

    if selection.selected_position is None:
        conflict = InterpretationConflict(
            conflict_id="LYC-001",
            code="USE_GOD_SELECTION_REQUIRED",
            evidence_ids=(),
            technical=selection.reason,
            plain="用神候选没有唯一确定，继续评分会把取用假设伪装成结论。",
        )
        return InterpretationResult(
            case_id=record.cast.case_id,
            chart_sha256=chart.canonical_sha256,
            request=request,
            use_selection=selection,
            actors=(),
            evidence=(),
            conflicts=(conflict,),
            topic_dimensions=dimensions,
            status="needs_confirmation",
            structural_balance="undetermined",
            support_score=0,
            restrict_score=0,
            confidence="low",
            context_completeness=context,
            headline="需要先确认用神爻位。",
            plain_explanation=selection.reason,
            warnings=tuple(warnings),
            limits=limits,
        )

    target = chart.lines[selection.selected_position - 1]
    actors = tuple(_build_actor(line, target) for line in chart.lines)
    evidence: list[InterpretationEvidence] = []

    def add_evidence(
        *,
        rule_id: str,
        source_kind: str,
        relation: str,
        polarity: str,
        weight: int,
        technical: str,
        plain: str,
        actor_position: int | None = None,
    ) -> None:
        evidence.append(
            InterpretationEvidence(
                evidence_id=f"LYE-{len(evidence) + 1:03d}",
                rule_id=rule_id,
                source_kind=source_kind,
                target_position=target.position,
                actor_position=actor_position,
                relation=relation,
                polarity=polarity,
                weight=weight,
                technical=technical,
                plain=plain,
            )
        )

    if request.calendar_context_confirmed:
        if chart.month_branch is not None:
            _add_environment_evidence(
                source_kind="month",
                branch=chart.month_branch,
                target=target,
                add=add_evidence,
            )
        if chart.day_ganzhi is not None:
            _add_environment_evidence(
                source_kind="day",
                branch=chart.day_ganzhi[1],
                target=target,
                add=add_evidence,
            )
            if target.is_void:
                add_evidence(
                    rule_id="LYI-VOID-001",
                    source_kind="day",
                    relation="void",
                    polarity="ambiguous",
                    weight=0,
                    technical=f"第{target.position}爻{target.najia_branch}落入旬空。",
                    plain="该爻处于旬空，但旺空、动空、冲空等例外尚未实现，因此只列为条件性疑点。",
                )

    for actor in chart.lines:
        if not actor.moving or actor.position == target.position:
            continue
        branch_relation = _branch_relation(actor.najia_branch, target.najia_branch)
        if branch_relation == "combine":
            add_evidence(
                rule_id="LYI-MOVING-COMBINE-001",
                source_kind="moving_line",
                actor_position=actor.position,
                relation="moving_combines_use",
                polarity="ambiguous",
                weight=0,
                technical=f"动爻第{actor.position}爻{actor.najia_branch}与用神候选{target.najia_branch}六合。",
                plain="存在牵连关系，但不能仅凭六合判断是助力还是牵制。",
            )
        elif branch_relation == "clash":
            add_evidence(
                rule_id="LYI-MOVING-CLASH-001",
                source_kind="moving_line",
                actor_position=actor.position,
                relation="moving_clashes_use",
                polarity="ambiguous",
                weight=0,
                technical=f"动爻第{actor.position}爻{actor.najia_branch}与用神候选{target.najia_branch}六冲。",
                plain="存在主动冲击，但强弱、冲起或冲散仍需更完整条件。",
            )
        _add_element_evidence(
            rule_prefix="LYI-MOVING",
            source_kind="moving_line",
            actor_element=actor.element,
            target=target,
            actor_position=actor.position,
            add=add_evidence,
            strong_weight=2,
            weak_weight=1,
        )

    if target.moving and target.changed_element is not None and target.changed_najia_branch is not None:
        changed_relation = _element_relation(target.changed_element, target.element)
        if changed_relation == "generates_target":
            add_evidence(
                rule_id="LYI-CHANGE-RETURN-GENERATE-001",
                source_kind="changed_line",
                relation="return_generates",
                polarity="supportive",
                weight=2,
                technical=f"用神候选发动，变爻{target.changed_element}回头生本爻{target.element}。",
                plain="变化后的力量反过来支持原用神候选，属于结构性支持因素。",
                actor_position=target.position,
            )
        elif changed_relation == "controls_target":
            add_evidence(
                rule_id="LYI-CHANGE-RETURN-CONTROL-001",
                source_kind="changed_line",
                relation="return_controls",
                polarity="restrictive",
                weight=2,
                technical=f"用神候选发动，变爻{target.changed_element}回头克本爻{target.element}。",
                plain="变化后的力量反过来压制原用神候选，属于结构性约束因素。",
                actor_position=target.position,
            )
        elif changed_relation == "drains_target":
            add_evidence(
                rule_id="LYI-CHANGE-DRAIN-001",
                source_kind="changed_line",
                relation="transforms_to_drain",
                polarity="restrictive",
                weight=1,
                technical=f"本爻{target.element}生变爻{target.changed_element}，存在化泄。",
                plain="原用神候选需要向变化结果输出力量，列为较弱的消耗因素。",
                actor_position=target.position,
            )
        elif changed_relation == "peer":
            add_evidence(
                rule_id="LYI-CHANGE-PEER-001",
                source_kind="changed_line",
                relation="transforms_to_peer",
                polarity="supportive",
                weight=1,
                technical=f"本爻与变爻同属{target.element}，形成比和。",
                plain="变化前后五行同类，列为较弱的连续性支持。",
                actor_position=target.position,
            )
        else:
            add_evidence(
                rule_id="LYI-CHANGE-CONSUMPTION-001",
                source_kind="changed_line",
                relation="use_controls_change",
                polarity="ambiguous",
                weight=0,
                technical=f"本爻{target.element}克变爻{target.changed_element}。",
                plain="原用神候选能够制约变化结果，但也可能需要耗力，本层不作单向判断。",
                actor_position=target.position,
            )

        changed_branch_relation = _branch_relation(target.changed_najia_branch, target.najia_branch)
        if changed_branch_relation == "combine":
            add_evidence(
                rule_id="LYI-CHANGE-COMBINE-001",
                source_kind="changed_line",
                relation="change_combines_original",
                polarity="ambiguous",
                weight=0,
                technical=f"变爻{target.changed_najia_branch}与本爻{target.najia_branch}六合。",
                plain="本变之间有合，但合起、合绊或合化条件未完成，因此不改变评分。",
                actor_position=target.position,
            )
        elif changed_branch_relation == "clash":
            add_evidence(
                rule_id="LYI-CHANGE-CLASH-001",
                source_kind="changed_line",
                relation="change_clashes_original",
                polarity="ambiguous",
                weight=0,
                technical=f"变爻{target.changed_najia_branch}与本爻{target.najia_branch}六冲。",
                plain="本变之间出现冲击，但本层不自动解释为冲散或冲动。",
                actor_position=target.position,
            )
        if request.calendar_context_confirmed and target.changed_is_void:
            add_evidence(
                rule_id="LYI-CHANGE-VOID-001",
                source_kind="changed_line",
                relation="changed_void",
                polarity="ambiguous",
                weight=0,
                technical=f"变爻{target.changed_najia_branch}落入旬空。",
                plain="变爻旬空存在例外条件，本层只作为疑点登记。",
                actor_position=target.position,
            )

    support_score = sum(item.weight for item in evidence if item.polarity == "supportive")
    restrict_score = sum(item.weight for item in evidence if item.polarity == "restrictive")
    if support_score == 0 and restrict_score == 0:
        balance = "undetermined"
    elif support_score - restrict_score >= 2:
        balance = "supportive"
    elif restrict_score - support_score >= 2:
        balance = "restrictive"
    else:
        balance = "mixed"

    conflicts: list[InterpretationConflict] = []
    supportive_ids = tuple(item.evidence_id for item in evidence if item.polarity == "supportive")
    restrictive_ids = tuple(item.evidence_id for item in evidence if item.polarity == "restrictive")
    ambiguous_ids = tuple(item.evidence_id for item in evidence if item.polarity == "ambiguous")
    if supportive_ids and restrictive_ids:
        conflicts.append(
            InterpretationConflict(
                conflict_id=f"LYC-{len(conflicts) + 1:03d}",
                code="MIXED_POLARITY",
                evidence_ids=supportive_ids + restrictive_ids,
                technical="支持与约束证据同时存在。",
                plain="盘内因素并非单向，不能只挑有利或不利的一边下结论。",
            )
        )
    if ambiguous_ids:
        conflicts.append(
            InterpretationConflict(
                conflict_id=f"LYC-{len(conflicts) + 1:03d}",
                code="CONDITIONAL_RULES_UNRESOLVED",
                evidence_ids=ambiguous_ids,
                technical="存在需要旺衰、动静或其他条件才能定向的传统结构。",
                plain="这些因素暂时只登记，不参与支持或约束评分。",
            )
        )
    if request.reality_status == "blocking" and support_score:
        conflicts.append(
            InterpretationConflict(
                conflict_id=f"LYC-{len(conflicts) + 1:03d}",
                code="REALITY_OVERRIDES_STRUCTURE",
                evidence_ids=supportive_ids,
                technical="已确认现实阻断与盘面支持因素并存。",
                plain="现实阻断优先，不能用盘面支持因素覆盖已经确认的客观条件。",
            )
        )

    scored_count = len(supportive_ids) + len(restrictive_ids)
    confidence = "medium"
    if context != "complete" or scored_count < 2 or len(ambiguous_ids) > scored_count or request.reality_status == "unknown":
        confidence = "low"

    if request.reality_status == "blocking":
        status = "reality_blocked"
        headline = "现实条件构成阻断，盘面结构不能覆盖现实事实。"
        explanation = "结构证据仍保留供复核，但当前行动判断应以已确认的现实阻断为先。"
    elif not evidence or balance == "undetermined":
        status = "insufficient_context"
        headline = "现有结构证据不足，不能形成方向性判断。"
        explanation = "需要补齐经确认的月建、日柱，或确认用神与现实条件后再复核。"
    elif balance == "supportive":
        status = "analyzed"
        headline = "结构性支持因素多于约束因素。"
        explanation = "这只说明当前传统结构偏支持，不等于事件会成功，也不生成概率或应期。"
    elif balance == "restrictive":
        status = "analyzed"
        headline = "结构性约束因素多于支持因素。"
        explanation = "这只说明当前传统结构偏受限，不等于事件会失败，也不替代现实证据。"
    else:
        status = "analyzed"
        headline = "支持与约束因素接近，结构呈混合状态。"
        explanation = "目前不具备把结果压成单向结论的条件，应保留分歧并降低置信度。"

    return InterpretationResult(
        case_id=record.cast.case_id,
        chart_sha256=chart.canonical_sha256,
        request=request,
        use_selection=selection,
        actors=actors,
        evidence=tuple(evidence),
        conflicts=tuple(conflicts),
        topic_dimensions=dimensions,
        status=status,
        structural_balance=balance,
        support_score=support_score,
        restrict_score=restrict_score,
        confidence=confidence,
        context_completeness=context,
        headline=headline,
        plain_explanation=explanation,
        warnings=tuple(warnings),
        limits=limits,
    )


def _build_actor(line: LiuYaoLine, target: LiuYaoLine) -> UseActor:
    return UseActor(
        position=line.position,
        six_relation=line.six_relation,
        element=line.element,
        moving=line.moving,
        role_to_use=_role_to_use(line, target),
    )


def _add_environment_evidence(*, source_kind: str, branch: str, target: LiuYaoLine, add: Any) -> None:
    branch_relation = _branch_relation(branch, target.najia_branch)
    label = "月建" if source_kind == "month" else "日辰"
    if branch_relation == "same":
        add(
            rule_id=f"LYI-{source_kind.upper()}-SAME-001",
            source_kind=source_kind,
            relation=f"{source_kind}_same_branch",
            polarity="supportive",
            weight=3 if source_kind == "month" else 2,
            technical=f"用神候选{target.najia_branch}临{label}{branch}。",
            plain=f"该爻与{label}同支，列为较明确的结构性支持。",
        )
        return
    if branch_relation == "clash":
        if source_kind == "month":
            add(
                rule_id="LYI-MONTH-BREAK-001",
                source_kind=source_kind,
                relation="month_break",
                polarity="restrictive",
                weight=3,
                technical=f"月建{branch}冲用神候选{target.najia_branch}，构成月破结构。",
                plain="该爻受到月令直接冲击，列为较强约束；是否有解仍需其他条件。",
            )
        else:
            add(
                rule_id="LYI-DAY-CLASH-001",
                source_kind=source_kind,
                relation="day_clash",
                polarity="ambiguous",
                weight=0,
                technical=f"日辰{branch}冲用神候选{target.najia_branch}。",
                plain="日冲可能表现为触发，也可能表现为冲散，当前条件不足以定向。",
            )
        return
    if branch_relation == "combine":
        add(
            rule_id=f"LYI-{source_kind.upper()}-COMBINE-001",
            source_kind=source_kind,
            relation=f"{source_kind}_combine",
            polarity="ambiguous",
            weight=0,
            technical=f"{label}{branch}与用神候选{target.najia_branch}六合。",
            plain="存在六合牵连，但不能仅凭这一点判断合起、合绊或合化。",
        )
        return
    _add_element_evidence(
        rule_prefix=f"LYI-{source_kind.upper()}",
        source_kind=source_kind,
        actor_element=BRANCH_ELEMENTS[branch],
        target=target,
        actor_position=None,
        add=add,
        strong_weight=2 if source_kind == "month" else 1,
        weak_weight=1,
    )


def _add_element_evidence(
    *,
    rule_prefix: str,
    source_kind: str,
    actor_element: str,
    target: LiuYaoLine,
    actor_position: int | None,
    add: Any,
    strong_weight: int,
    weak_weight: int,
) -> None:
    relation = _element_relation(actor_element, target.element)
    source_label = {"month": "月建", "day": "日辰", "moving_line": "动爻"}.get(source_kind, source_kind)
    if relation == "generates_target":
        add(
            rule_id=f"{rule_prefix}-GENERATE-001",
            source_kind=source_kind,
            actor_position=actor_position,
            relation="generates_use",
            polarity="supportive",
            weight=strong_weight,
            technical=f"{source_label}{actor_element}生用神候选{target.element}。",
            plain="该力量生扶用神候选，列为结构性支持。",
        )
    elif relation == "controls_target":
        add(
            rule_id=f"{rule_prefix}-CONTROL-001",
            source_kind=source_kind,
            actor_position=actor_position,
            relation="controls_use",
            polarity="restrictive",
            weight=strong_weight,
            technical=f"{source_label}{actor_element}克用神候选{target.element}。",
            plain="该力量直接压制用神候选，列为结构性约束。",
        )
    elif relation == "drains_target":
        add(
            rule_id=f"{rule_prefix}-DRAIN-001",
            source_kind=source_kind,
            actor_position=actor_position,
            relation="drains_use",
            polarity="restrictive",
            weight=weak_weight,
            technical=f"用神候选{target.element}生{source_label}{actor_element}。",
            plain="用神候选向外输出力量，列为较弱消耗。",
        )
    elif relation == "peer":
        add(
            rule_id=f"{rule_prefix}-PEER-001",
            source_kind=source_kind,
            actor_position=actor_position,
            relation="same_element",
            polarity="supportive",
            weight=weak_weight,
            technical=f"{source_label}与用神候选同属{target.element}。",
            plain="同类力量列为较弱支持。",
        )
    else:
        add(
            rule_id=f"{rule_prefix}-CONSUMPTION-001",
            source_kind=source_kind,
            actor_position=actor_position,
            relation="use_controls_actor",
            polarity="ambiguous",
            weight=0,
            technical=f"用神候选{target.element}克{source_label}{actor_element}。",
            plain="用神候选能够制约对方，但也可能耗力，当前不作单向评分。",
        )


__all__ = [
    "INTERPRETATION_METHOD_ID",
    "INTERPRETATION_STATUS",
    "PRODUCTION_ALLOWED",
    "InterpretationConflict",
    "InterpretationEvidence",
    "InterpretationRequest",
    "InterpretationResult",
    "UseActor",
    "UseLineSelection",
    "interpret_case",
]
