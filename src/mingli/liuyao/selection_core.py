from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .advanced_runtime import AdvancedContextRequest
from .case_record import LiuYaoCaseRecord
from .interpretation import InterpretationRequest
from .tables import PREDICTION_VALIDITY, digest
from .validation import LiuYaoError, _non_empty, _reject_unknown, _string_tuple
from .validity_matrix import ValidityMatrixReport, ValidityRequest, build_validity_matrix

SELECTION_METHOD_ID = "liuyao-contract-driven-selection@0.1.0"
SELECTION_STATUS = "review_only"
SELECTION_PRODUCTION_ALLOWED = False

_TOPIC_ALIASES = {
    "general": "general",
    "综合": "general",
    "career": "career",
    "事业": "career",
    "exam": "exam",
    "考试": "exam",
    "考公考编": "exam",
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

# relation=None 表示该焦点不允许单次六爻自动取用。
_FOCUS_PROFILE: Mapping[tuple[str, str], tuple[str | None, tuple[str, ...], str]] = {
    ("general", "current_event"): (None, (), "manual_relation_required"),
    ("career", "current_position_event"): ("官鬼", ("父母",), "structural"),
    ("career", "career_fit"): (None, (), "reality_required"),
    ("exam", "system_fit"): (None, (), "outside_single_cast"),
    ("exam", "current_exam"): ("官鬼", ("父母", "兄弟"), "structural"),
    ("exam", "position_direction"): (None, (), "reality_required"),
    ("exam", "preparation_strategy"): (None, (), "reality_required"),
    ("wealth", "current_money_event"): ("妻财", ("子孙", "兄弟"), "structural"),
    ("wealth", "risk_capacity"): (None, (), "reality_required"),
    ("relationship_reconciliation", "bond"): ("gender_spouse", (), "structural"),
    ("relationship_reconciliation", "recontact"): ("gender_spouse", (), "structural"),
    ("relationship_reconciliation", "reconciliation"): ("gender_spouse", (), "structural"),
    ("relationship_reconciliation", "stability"): ("gender_spouse", (), "structural_reality_required"),
    ("pregnancy", "conception_opportunity"): ("子孙", (), "structural_advisory"),
    ("pregnancy", "medical_confirmation"): (None, (), "professional_only"),
    ("pregnancy", "pregnancy_stability"): (None, (), "professional_only"),
    ("pregnancy", "medical_factors"): (None, (), "professional_only"),
    ("documents", "current_document_event"): ("父母", (), "structural"),
    ("health", "traditional_structure"): (None, (), "advisory_only"),
    ("health", "medical_assessment"): (None, (), "professional_only"),
}

_AVAILABILITY_RANK = {
    "available_candidate": 0,
    "unresolved": 1,
    "conditional": 2,
    "unknown_context": 3,
}


@dataclass(frozen=True, slots=True)
class AutoSelectionRequest:
    topic: str
    focus_dimension: str | None = None
    querent_gender: str = "unknown"
    primary_relation_override: str | None = None
    override_reason: str | None = None
    primary_position: int | None = None
    subject_mapping_confirmed: bool = False
    subject_position: int | None = None
    contract_focus_confirmed: bool = False
    contract_source_refs: tuple[str, ...] = ()
    calendar_context_confirmed: bool = False
    calendar_source_refs: tuple[str, ...] = ()
    reality_status: str = "unknown"
    reality_facts: tuple[str, ...] = ()
    reality_evidence_refs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        topic_text = _non_empty(self.topic, "topic")
        topic = _TOPIC_ALIASES.get(topic_text)
        if topic is None:
            raise LiuYaoError("INVALID_INPUT", f"不支持的 topic：{topic_text}")
        object.__setattr__(self, "topic", topic)

        focus = self.focus_dimension or _DEFAULT_FOCUS[topic]
        if (topic, focus) not in _FOCUS_PROFILE:
            raise LiuYaoError("INVALID_INPUT", f"focus_dimension 不属于 {topic}：{focus}")
        object.__setattr__(self, "focus_dimension", focus)

        gender = _non_empty(self.querent_gender, "querent_gender")
        gender_aliases = {"unknown": "unknown", "未知": "unknown", "male": "male", "男": "male", "female": "female", "女": "female"}
        if gender not in gender_aliases:
            raise LiuYaoError("INVALID_INPUT", "querent_gender 必须是 male、female 或 unknown")
        object.__setattr__(self, "querent_gender", gender_aliases[gender])

        if self.primary_relation_override is not None:
            relation = _non_empty(self.primary_relation_override, "primary_relation_override")
            if relation not in {"父母", "兄弟", "子孙", "妻财", "官鬼"}:
                raise LiuYaoError("INVALID_INPUT", "primary_relation_override 必须是有效六亲")
            object.__setattr__(self, "primary_relation_override", relation)
            object.__setattr__(self, "override_reason", _non_empty(self.override_reason, "override_reason"))
        elif self.override_reason is not None:
            raise LiuYaoError("INVALID_INPUT", "没有 relation override 时不能填写 override_reason")

        for field_name in ("primary_position", "subject_position"):
            value = getattr(self, field_name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 6):
                raise LiuYaoError("INVALID_INPUT", f"{field_name} 必须是1到6的整数")

        for field_name in ("subject_mapping_confirmed", "contract_focus_confirmed", "calendar_context_confirmed"):
            if not isinstance(getattr(self, field_name), bool):
                raise LiuYaoError("INVALID_INPUT", f"{field_name} 必须是布尔值")

        contract_refs = _string_tuple(self.contract_source_refs, "contract_source_refs")
        calendar_refs = _string_tuple(self.calendar_source_refs, "calendar_source_refs")
        reality_facts = _string_tuple(self.reality_facts, "reality_facts")
        reality_refs = _string_tuple(self.reality_evidence_refs, "reality_evidence_refs")
        notes = _string_tuple(self.notes, "notes")
        object.__setattr__(self, "contract_source_refs", contract_refs)
        object.__setattr__(self, "calendar_source_refs", calendar_refs)
        object.__setattr__(self, "reality_facts", reality_facts)
        object.__setattr__(self, "reality_evidence_refs", reality_refs)
        object.__setattr__(self, "notes", notes)

        if self.contract_focus_confirmed and not contract_refs:
            raise LiuYaoError("CONTRACT_SOURCE_REQUIRED", "确认事件焦点时必须提供 contract_source_refs")
        if contract_refs and not self.contract_focus_confirmed:
            raise LiuYaoError("CONTRACT_CONFIRMATION_REQUIRED", "提供事件合同来源时必须确认焦点")
        if self.calendar_context_confirmed and not calendar_refs:
            raise LiuYaoError("CALENDAR_SOURCE_REQUIRED", "确认月日上下文时必须提供 calendar_source_refs")
        if calendar_refs and not self.calendar_context_confirmed:
            raise LiuYaoError("CALENDAR_CONFIRMATION_REQUIRED", "提供历法来源时必须确认月日上下文")

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "topic": self.topic,
            "focus_dimension": self.focus_dimension,
            "querent_gender": self.querent_gender,
            "primary_relation_override": self.primary_relation_override,
            "override_reason": self.override_reason,
            "primary_position": self.primary_position,
            "subject_mapping_confirmed": self.subject_mapping_confirmed,
            "subject_position": self.subject_position,
            "contract_focus_confirmed": self.contract_focus_confirmed,
            "contract_source_refs": list(self.contract_source_refs),
            "calendar_context_confirmed": self.calendar_context_confirmed,
            "calendar_source_refs": list(self.calendar_source_refs),
            "reality_status": self.reality_status,
            "reality_facts": list(self.reality_facts),
            "reality_evidence_refs": list(self.reality_evidence_refs),
            "notes": list(self.notes),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AutoSelectionRequest":
        allowed = {
            "topic", "focus_dimension", "querent_gender", "primary_relation_override",
            "override_reason", "primary_position", "subject_mapping_confirmed",
            "subject_position", "contract_focus_confirmed", "contract_source_refs",
            "calendar_context_confirmed", "calendar_source_refs", "reality_status",
            "reality_facts", "reality_evidence_refs", "notes", "canonical_sha256",
        }
        _reject_unknown(value, allowed, "auto_selection_request")
        if "topic" not in value:
            raise LiuYaoError("INVALID_INPUT", "auto_selection_request 缺少字段：topic")
        request = cls(
            topic=value["topic"],
            focus_dimension=value.get("focus_dimension"),
            querent_gender=value.get("querent_gender", "unknown"),
            primary_relation_override=value.get("primary_relation_override"),
            override_reason=value.get("override_reason"),
            primary_position=value.get("primary_position"),
            subject_mapping_confirmed=value.get("subject_mapping_confirmed", False),
            subject_position=value.get("subject_position"),
            contract_focus_confirmed=value.get("contract_focus_confirmed", False),
            contract_source_refs=_string_tuple(value.get("contract_source_refs", ()), "contract_source_refs"),
            calendar_context_confirmed=value.get("calendar_context_confirmed", False),
            calendar_source_refs=_string_tuple(value.get("calendar_source_refs", ()), "calendar_source_refs"),
            reality_status=value.get("reality_status", "unknown"),
            reality_facts=_string_tuple(value.get("reality_facts", ()), "reality_facts"),
            reality_evidence_refs=_string_tuple(value.get("reality_evidence_refs", ()), "reality_evidence_refs"),
            notes=_string_tuple(value.get("notes", ()), "notes"),
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != request.canonical_sha256:
            raise LiuYaoError("RECORD_TAMPERED", "auto_selection_request canonical_sha256 与重算结果不一致")
        return request


@dataclass(frozen=True, slots=True)
class SelectionCandidate:
    position: int
    relation: str
    source: str
    availability: str
    moving: bool
    is_shi: bool
    is_ying: bool
    rank_vector: tuple[int, int]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "position": self.position,
            "relation": self.relation,
            "source": self.source,
            "availability": self.availability,
            "moving": self.moving,
            "is_shi": self.is_shi,
            "is_ying": self.is_ying,
            "rank_vector": list(self.rank_vector),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class TopicDimension:
    dimension_id: str
    mode: str
    primary_relation: str | None
    secondary_relations: tuple[str, ...]
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "dimension_id": self.dimension_id,
            "mode": self.mode,
            "primary_relation": self.primary_relation,
            "secondary_relations": list(self.secondary_relations),
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class SelectionReport:
    case_id: str
    chart_sha256: str
    request: AutoSelectionRequest
    primary_relation: str | None
    relation_source: str
    secondary_relations: tuple[str, ...]
    shi_position: int
    ying_position: int
    subject_position: int | None
    counterparty_position: int | None
    candidates: tuple[SelectionCandidate, ...]
    recommended_position: int | None
    recommendation_status: str
    topic_dimensions: tuple[TopicDimension, ...]
    validity_matrix_sha256: str | None
    headline: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "method_id": SELECTION_METHOD_ID,
            "selection_status": SELECTION_STATUS,
            "production_allowed": SELECTION_PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "case_id": self.case_id,
            "chart_sha256": self.chart_sha256,
            "request": self.request.to_dict(),
            "primary_relation": self.primary_relation,
            "relation_source": self.relation_source,
            "secondary_relations": list(self.secondary_relations),
            "shi_position": self.shi_position,
            "ying_position": self.ying_position,
            "subject_position": self.subject_position,
            "counterparty_position": self.counterparty_position,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "recommended_position": self.recommended_position,
            "recommendation_status": self.recommendation_status,
            "topic_dimensions": [dimension.to_dict() for dimension in self.topic_dimensions],
            "validity_matrix_sha256": self.validity_matrix_sha256,
            "headline": self.headline,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def _gender_spouse_relation(gender: str) -> str | None:
    if gender == "male":
        return "妻财"
    if gender == "female":
        return "官鬼"
    return None


def _topic_dimensions(topic: str, gender: str) -> tuple[TopicDimension, ...]:
    dimensions: list[TopicDimension] = []
    for (candidate_topic, dimension), (relation, secondary, mode) in _FOCUS_PROFILE.items():
        if candidate_topic != topic:
            continue
        resolved = _gender_spouse_relation(gender) if relation == "gender_spouse" else relation
        plain = {
            "outside_single_cast": "该维度不能由单次六爻单独推出。",
            "reality_required": "该维度必须结合现实资格、履历、数据或计划。",
            "professional_only": "该维度必须由相应专业检查或专业意见确认。",
            "advisory_only": "只允许记录传统结构，不生成诊断或治疗结论。",
            "structural_reality_required": "可记录结构候选，但稳定性必须结合真实关系条件。",
            "structural_advisory": "只提供传统结构观察，不能替代医学检查。",
            "manual_relation_required": "综合事件必须由调用方明确说明取用关系和理由。",
            "structural": "可进入结构候选排序，但不等于成败结论。",
        }[mode]
        dimensions.append(
            TopicDimension(
                dimension_id=dimension,
                mode=mode,
                primary_relation=resolved,
                secondary_relations=secondary,
                plain=plain,
            )
        )
    return tuple(dimensions)


def _resolve_relation(request: AutoSelectionRequest) -> tuple[str | None, tuple[str, ...], str, str]:
    profile_relation, secondary, mode = _FOCUS_PROFILE[(request.topic, request.focus_dimension)]
    if request.primary_relation_override is not None:
        return request.primary_relation_override, secondary, "manual_override", mode
    if profile_relation == "gender_spouse":
        relation = _gender_spouse_relation(request.querent_gender)
        return relation, secondary, "gender_profile" if relation else "missing_gender", mode
    return profile_relation, secondary, "topic_profile" if profile_relation else "unsupported_profile", mode


def _build_interpretation_request(
    request: AutoSelectionRequest,
    relation: str,
    secondary: tuple[str, ...],
) -> InterpretationRequest:
    payload: dict[str, object] = {
        "topic": request.topic,
        "focus_dimension": request.focus_dimension,
        "use_relation": relation,
        "primary_position": request.primary_position,
        "secondary_relations": list(secondary),
        "calendar_context_confirmed": request.calendar_context_confirmed,
        "calendar_source_refs": list(request.calendar_source_refs),
        "reality_status": request.reality_status,
        "reality_facts": list(request.reality_facts),
        "reality_evidence_refs": list(request.reality_evidence_refs),
        "notes": list(request.notes),
    }
    return InterpretationRequest.from_mapping(payload)


def _subject_positions(
    record: LiuYaoCaseRecord,
    request: AutoSelectionRequest,
) -> tuple[int | None, int | None, tuple[str, ...]]:
    shi = record.chart.original.shi_line
    ying = record.chart.original.ying_line
    warnings: list[str] = []
    if record.cast.casting_mode == "self":
        if request.subject_position is not None and request.subject_position != shi:
            raise LiuYaoError("SUBJECT_MAPPING_CONFLICT", "本人摇卦时显式 subject_position 必须等于世爻")
        return shi, ying, ()
    if not request.subject_mapping_confirmed or request.subject_position is None:
        warnings.append("代摇案例尚未确认被测者对应爻位，世应主体不能自动归属。")
        return None, None, tuple(warnings)
    counterparty = ying if request.subject_position == shi else shi if request.subject_position == ying else None
    return request.subject_position, counterparty, ()


def _candidate_list(
    record: LiuYaoCaseRecord,
    matrix: ValidityMatrixReport,
    relation: str,
) -> tuple[SelectionCandidate, ...]:
    validity = {item.position: item for item in matrix.line_validity}
    candidates: list[SelectionCandidate] = []
    for line in record.chart.lines:
        if line.six_relation != relation:
            continue
        status = validity[line.position].availability
        candidates.append(
            SelectionCandidate(
                position=line.position,
                relation=relation,
                source="visible",
                availability=status,
                moving=line.moving,
                is_shi=line.position == record.chart.original.shi_line,
                is_ying=line.position == record.chart.original.ying_line,
                rank_vector=(_AVAILABILITY_RANK[status], 0 if line.moving else 1),
                reasons=(
                    f"visible_{relation}",
                    f"availability_{status}",
                    "moving_tiebreak_only" if line.moving else "static_candidate",
                ),
            )
        )
    if candidates:
        return tuple(sorted(candidates, key=lambda item: (item.rank_vector, item.position)))

    for hidden in matrix.hidden_candidates:
        if hidden.relation != relation:
            continue
        hidden_rank = {
            "candidate_only": 2,
            "unresolved_candidate": 3,
            "constrained_candidate": 4,
            "unknown_context": 5,
        }.get(hidden.status, 5)
        candidates.append(
            SelectionCandidate(
                position=hidden.position,
                relation=relation,
                source="hidden",
                availability=hidden.status,
                moving=False,
                is_shi=hidden.position == record.chart.original.shi_line,
                is_ying=hidden.position == record.chart.original.ying_line,
                rank_vector=(hidden_rank, 1),
                reasons=("hidden_relation_candidate", f"hidden_status_{hidden.status}"),
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.rank_vector, item.position)))


def build_selection_report(
    record: LiuYaoCaseRecord,
    request: AutoSelectionRequest,
) -> SelectionReport:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    if not isinstance(request, AutoSelectionRequest):
        raise LiuYaoError("INVALID_INPUT", "request 必须是 AutoSelectionRequest")

    shi = record.chart.original.shi_line
    ying = record.chart.original.ying_line
    subject, counterparty, subject_warnings = _subject_positions(record, request)
    dimensions = _topic_dimensions(request.topic, request.querent_gender)
    relation, secondary, relation_source, mode = _resolve_relation(request)
    warnings = list(subject_warnings)
    limits = [
        "候选排序使用离散优先级，不是成功概率、命中率或吉凶分数。",
        "动爻只作为同等有效性下的次级排序提示，不能覆盖空破墓绝和现实阻断。",
        "推荐位置仍需人工确认事件合同、主体映射和传统取用口径。",
        "本层不生成应期、确定日期或付费吉凶成品。",
    ]

    if not request.contract_focus_confirmed:
        return SelectionReport(
            case_id=record.cast.case_id,
            chart_sha256=record.chart.canonical_sha256,
            request=request,
            primary_relation=relation,
            relation_source=relation_source,
            secondary_relations=secondary,
            shi_position=shi,
            ying_position=ying,
            subject_position=subject,
            counterparty_position=counterparty,
            candidates=(),
            recommended_position=None,
            recommendation_status="contract_unconfirmed",
            topic_dimensions=dimensions,
            validity_matrix_sha256=None,
            headline="事件焦点尚未与冻结合同核对，不能自动取用。",
            warnings=tuple(warnings),
            limits=tuple(limits),
        )

    if record.cast.casting_mode == "proxy" and subject is None:
        return SelectionReport(
            case_id=record.cast.case_id,
            chart_sha256=record.chart.canonical_sha256,
            request=request,
            primary_relation=relation,
            relation_source=relation_source,
            secondary_relations=secondary,
            shi_position=shi,
            ying_position=ying,
            subject_position=None,
            counterparty_position=None,
            candidates=(),
            recommended_position=None,
            recommendation_status="subject_mapping_required",
            topic_dimensions=dimensions,
            validity_matrix_sha256=None,
            headline="代摇主体尚未确认，不能把世爻自动当成被测者。",
            warnings=tuple(warnings),
            limits=tuple(limits),
        )

    if relation is None:
        status = "gender_required" if relation_source == "missing_gender" else "unsupported_focus"
        if mode == "manual_relation_required":
            status = "manual_relation_required"
        return SelectionReport(
            case_id=record.cast.case_id,
            chart_sha256=record.chart.canonical_sha256,
            request=request,
            primary_relation=None,
            relation_source=relation_source,
            secondary_relations=secondary,
            shi_position=shi,
            ying_position=ying,
            subject_position=subject,
            counterparty_position=counterparty,
            candidates=(),
            recommended_position=None,
            recommendation_status=status,
            topic_dimensions=dimensions,
            validity_matrix_sha256=None,
            headline="当前焦点不能仅凭单次六爻自动确定用神。",
            warnings=tuple(warnings),
            limits=tuple(limits),
        )

    interpretation_request = _build_interpretation_request(request, relation, secondary)
    validity_request = ValidityRequest(
        interpretation=interpretation_request,
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=request.calendar_context_confirmed,
            calendar_source_refs=request.calendar_source_refs,
        ),
    )
    matrix = build_validity_matrix(record, validity_request)
    candidates = _candidate_list(record, matrix, relation)
    recommended: int | None = None

    if matrix.matrix_status == "reality_blocked":
        status = "reality_blocked"
        headline = "现实阻断优先，候选排序不构成可执行判断。"
    elif request.primary_position is not None:
        recommended = request.primary_position
        status = "explicit_position_confirmed"
        headline = "已校验显式用神位置；仍需结合有效性矩阵，不等于事情能成。"
    elif not candidates:
        status = "no_candidate"
        headline = "本卦和当前伏神候选中均未找到对应六亲。"
    elif candidates[0].source == "hidden":
        status = "hidden_candidate_needs_confirmation"
        headline = "只找到伏神候选，不能自动升级为最终用神。"
    else:
        best_rank = candidates[0].rank_vector
        best = [candidate for candidate in candidates if candidate.rank_vector == best_rank]
        if len(best) == 1:
            recommended = best[0].position
            status = "recommended_visible_candidate"
            headline = "已给出唯一最高排序的可见候选；这是待确认建议，不是自动最终取用。"
        else:
            status = "tie_needs_confirmation"
            headline = "多个可见候选处于同一排序层级，需要人工确认。"

    if relation_source == "manual_override":
        warnings.append("本次六亲来自人工 override，必须保留 override_reason 并接受复核。")
    if recommended is not None:
        selected = next((candidate for candidate in candidates if candidate.position == recommended), None)
        if selected and selected.availability != "available_candidate":
            warnings.append("推荐候选仍存在未决或约束条件，不得直接进入成败结论。")

    return SelectionReport(
        case_id=record.cast.case_id,
        chart_sha256=record.chart.canonical_sha256,
        request=request,
        primary_relation=relation,
        relation_source=relation_source,
        secondary_relations=secondary,
        shi_position=shi,
        ying_position=ying,
        subject_position=subject,
        counterparty_position=counterparty,
        candidates=candidates,
        recommended_position=recommended,
        recommendation_status=status,
        topic_dimensions=dimensions,
        validity_matrix_sha256=matrix.canonical_sha256,
        headline=headline,
        warnings=tuple(dict.fromkeys(warnings + list(matrix.warnings))),
        limits=tuple(dict.fromkeys(limits + list(matrix.limits))),
    )


__all__ = [
    "SELECTION_METHOD_ID",
    "SELECTION_PRODUCTION_ALLOWED",
    "SELECTION_STATUS",
    "AutoSelectionRequest",
    "SelectionCandidate",
    "SelectionReport",
    "TopicDimension",
    "build_selection_report",
]
