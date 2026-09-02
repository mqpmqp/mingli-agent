from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .advanced_facts import (
    AdvancedFact,
    classify_branch_relation,
    classify_element_relation,
)
from .advanced_runtime import (
    AdvancedContextRequest,
    AdvancedRuntimeReport,
    build_advanced_runtime_report,
)
from .case_record import LiuYaoCaseRecord
from .interpretation import InterpretationRequest, InterpretationResult, interpret_case
from .tables import BRANCH_ELEMENTS, PREDICTION_VALIDITY, digest
from .validation import LiuYaoError, _reject_unknown, _require_mapping

VALIDITY_MATRIX_METHOD_ID = "liuyao-validity-conflict-matrix@0.1.0"
VALIDITY_MATRIX_STATUS = "review_only"
VALIDITY_MATRIX_PRODUCTION_ALLOWED = False

_CONSTRAINING_GROWTH_STAGES = frozenset({"墓", "绝"})
_AMBIGUOUS_BRANCH_RELATIONS = frozenset({"combine", "clash"})


@dataclass(frozen=True, slots=True)
class ValidityRequest:
    interpretation: InterpretationRequest
    advanced_context: AdvancedContextRequest

    def __post_init__(self) -> None:
        if not isinstance(self.interpretation, InterpretationRequest):
            raise LiuYaoError("INVALID_INPUT", "interpretation 必须是 InterpretationRequest")
        if not isinstance(self.advanced_context, AdvancedContextRequest):
            raise LiuYaoError("INVALID_INPUT", "advanced_context 必须是 AdvancedContextRequest")

        interpretation_confirmed = bool(
            getattr(self.interpretation, "calendar_context_confirmed", False)
        )
        if interpretation_confirmed != self.advanced_context.calendar_context_confirmed:
            raise LiuYaoError(
                "CALENDAR_CONFIRMATION_MISMATCH",
                "解释请求和高级事实请求的 calendar_context_confirmed 必须一致",
            )

        interpretation_refs = tuple(
            getattr(self.interpretation, "calendar_source_refs", ())
        )
        if interpretation_confirmed and interpretation_refs:
            if set(interpretation_refs) != set(self.advanced_context.calendar_source_refs):
                raise LiuYaoError(
                    "CALENDAR_SOURCE_MISMATCH",
                    "解释请求和高级事实请求的 calendar_source_refs 必须一致",
                )

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "interpretation": self.interpretation.to_dict(),
            "advanced_context": self.advanced_context.to_dict(),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ValidityRequest":
        allowed = {"interpretation", "advanced_context", "canonical_sha256"}
        _reject_unknown(value, allowed, "validity_request")
        missing = {"interpretation", "advanced_context"} - set(value)
        if missing:
            raise LiuYaoError(
                "INVALID_INPUT",
                f"validity_request 缺少字段：{', '.join(sorted(missing))}",
            )
        request = cls(
            interpretation=InterpretationRequest.from_mapping(
                _require_mapping(value["interpretation"], "interpretation")
            ),
            advanced_context=AdvancedContextRequest.from_mapping(
                _require_mapping(value["advanced_context"], "advanced_context")
            ),
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != request.canonical_sha256:
            raise LiuYaoError(
                "RECORD_TAMPERED",
                "validity_request canonical_sha256 与重算结果不一致",
            )
        return request


@dataclass(frozen=True, slots=True)
class LineValidity:
    position: int
    selected_use: bool
    branch: str
    element: str
    moving: bool
    availability: str
    conditions: tuple[str, ...]
    ambiguous_conditions: tuple[str, ...]
    month_relation: str | None
    day_relation: str | None
    month_growth_stage: str | None
    day_growth_stage: str | None
    changed_branch: str | None
    changed_element: str | None
    changed_availability: str | None
    changed_conditions: tuple[str, ...]
    changed_ambiguous_conditions: tuple[str, ...]
    changed_month_growth_stage: str | None
    changed_day_growth_stage: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "position": self.position,
            "selected_use": self.selected_use,
            "branch": self.branch,
            "element": self.element,
            "moving": self.moving,
            "availability": self.availability,
            "conditions": list(self.conditions),
            "ambiguous_conditions": list(self.ambiguous_conditions),
            "month_relation": self.month_relation,
            "day_relation": self.day_relation,
            "month_growth_stage": self.month_growth_stage,
            "day_growth_stage": self.day_growth_stage,
            "changed_branch": self.changed_branch,
            "changed_element": self.changed_element,
            "changed_availability": self.changed_availability,
            "changed_conditions": list(self.changed_conditions),
            "changed_ambiguous_conditions": list(self.changed_ambiguous_conditions),
            "changed_month_growth_stage": self.changed_month_growth_stage,
            "changed_day_growth_stage": self.changed_day_growth_stage,
        }


@dataclass(frozen=True, slots=True)
class InfluenceEdge:
    edge_id: str
    source_kind: str
    source_position: int
    target_position: int
    relation: str
    source_availability: str
    target_availability: str
    edge_status: str
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "edge_id": self.edge_id,
            "source_kind": self.source_kind,
            "source_position": self.source_position,
            "target_position": self.target_position,
            "relation": self.relation,
            "source_availability": self.source_availability,
            "target_availability": self.target_availability,
            "edge_status": self.edge_status,
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class HiddenCandidateValidity:
    relation: str
    position: int
    hidden_branch: str
    flying_branch: str
    flying_to_hidden: str
    hidden_to_flying: str
    status: str
    conditions: tuple[str, ...]
    ambiguous_conditions: tuple[str, ...]
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "relation": self.relation,
            "position": self.position,
            "hidden_branch": self.hidden_branch,
            "flying_branch": self.flying_branch,
            "flying_to_hidden": self.flying_to_hidden,
            "hidden_to_flying": self.hidden_to_flying,
            "status": self.status,
            "conditions": list(self.conditions),
            "ambiguous_conditions": list(self.ambiguous_conditions),
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class ValidityConflict:
    conflict_id: str
    code: str
    positions: tuple[int, ...]
    severity: str
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "conflict_id": self.conflict_id,
            "code": self.code,
            "positions": list(self.positions),
            "severity": self.severity,
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class ValidityMatrixReport:
    case_id: str
    chart_sha256: str
    request: ValidityRequest
    interpretation_sha256: str
    advanced_runtime_sha256: str
    selected_use_position: int | None
    matrix_status: str
    line_validity: tuple[LineValidity, ...]
    influence_edges: tuple[InfluenceEdge, ...]
    hidden_candidates: tuple[HiddenCandidateValidity, ...]
    conflicts: tuple[ValidityConflict, ...]
    unresolved_dependencies: tuple[str, ...]
    reality_override: str
    headline: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "method_id": VALIDITY_MATRIX_METHOD_ID,
            "validity_matrix_status": VALIDITY_MATRIX_STATUS,
            "production_allowed": VALIDITY_MATRIX_PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "case_id": self.case_id,
            "chart_sha256": self.chart_sha256,
            "request": self.request.to_dict(),
            "interpretation_sha256": self.interpretation_sha256,
            "advanced_runtime_sha256": self.advanced_runtime_sha256,
            "selected_use_position": self.selected_use_position,
            "matrix_status": self.matrix_status,
            "line_validity": [item.to_dict() for item in self.line_validity],
            "influence_edges": [item.to_dict() for item in self.influence_edges],
            "hidden_candidates": [item.to_dict() for item in self.hidden_candidates],
            "conflicts": [item.to_dict() for item in self.conflicts],
            "unresolved_dependencies": list(self.unresolved_dependencies),
            "reality_override": self.reality_override,
            "headline": self.headline,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def _growth_index(report: AdvancedRuntimeReport) -> dict[tuple[str, int], str]:
    return {
        (fact.scope, fact.positions[0]): fact.value
        for fact in report.facts
        if fact.category == "growth_stage" and len(fact.positions) == 1
    }


def _calendar_relations(
    branch: str,
    element: str,
    *,
    month_branch: str | None,
    day_branch: str | None,
) -> tuple[str | None, str | None, list[str], list[str]]:
    conditions: list[str] = []
    ambiguous: list[str] = []
    month_relation: str | None = None
    day_relation: str | None = None

    if month_branch is not None:
        branch_relation = classify_branch_relation(month_branch, branch)
        element_relation = classify_element_relation(BRANCH_ELEMENTS[month_branch], element)
        month_relation = f"{branch_relation}:{element_relation}"
        if branch_relation == "clash":
            conditions.append("month_break")
        elif branch_relation == "combine":
            ambiguous.append("month_combine_effect_unresolved")

    if day_branch is not None:
        branch_relation = classify_branch_relation(day_branch, branch)
        element_relation = classify_element_relation(BRANCH_ELEMENTS[day_branch], element)
        day_relation = f"{branch_relation}:{element_relation}"
        if branch_relation == "clash":
            ambiguous.append("day_clash_effect_unresolved")
        elif branch_relation == "combine":
            ambiguous.append("day_combine_effect_unresolved")

    return month_relation, day_relation, conditions, ambiguous


def _availability(
    *,
    context_confirmed: bool,
    is_void: bool | None,
    conditions: list[str],
    ambiguous: list[str],
    month_growth: str | None,
    day_growth: str | None,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    normalized_conditions = list(conditions)
    normalized_ambiguous = list(ambiguous)
    if not context_confirmed:
        return "unknown_context", (), ()
    if is_void:
        normalized_ambiguous.append("void_effect_unresolved")
    if month_growth in _CONSTRAINING_GROWTH_STAGES:
        normalized_ambiguous.append(f"month_growth_{month_growth}_effect_unresolved")
    if day_growth in _CONSTRAINING_GROWTH_STAGES:
        normalized_ambiguous.append(f"day_growth_{day_growth}_effect_unresolved")

    normalized_conditions = list(dict.fromkeys(normalized_conditions))
    normalized_ambiguous = list(dict.fromkeys(normalized_ambiguous))
    if normalized_conditions:
        status = "conditional"
    elif normalized_ambiguous:
        status = "unresolved"
    else:
        status = "available_candidate"
    return status, tuple(normalized_conditions), tuple(normalized_ambiguous)


def _line_matrix(
    record: LiuYaoCaseRecord,
    interpretation: InterpretationResult,
    advanced: AdvancedRuntimeReport,
) -> tuple[LineValidity, ...]:
    context_confirmed = advanced.context_status.startswith("confirmed_")
    month_branch = record.chart.month_branch if context_confirmed else None
    day_branch = record.chart.day_ganzhi[1] if context_confirmed and record.chart.day_ganzhi else None
    growth = _growth_index(advanced)
    selected = interpretation.use_selection.selected_position
    matrix: list[LineValidity] = []

    for line in record.chart.lines:
        month_relation, day_relation, conditions, ambiguous = _calendar_relations(
            line.najia_branch,
            line.element,
            month_branch=month_branch,
            day_branch=day_branch,
        )
        month_growth = growth.get(("month_original", line.position))
        day_growth = growth.get(("day_original", line.position))
        availability, conditions_tuple, ambiguous_tuple = _availability(
            context_confirmed=context_confirmed,
            is_void=line.is_void,
            conditions=conditions,
            ambiguous=ambiguous,
            month_growth=month_growth,
            day_growth=day_growth,
        )

        changed_availability: str | None = None
        changed_conditions: tuple[str, ...] = ()
        changed_ambiguous: tuple[str, ...] = ()
        changed_month_growth = growth.get(("month_changed", line.position))
        changed_day_growth = growth.get(("day_changed", line.position))
        if line.moving and line.changed_najia_branch is not None and line.changed_element is not None:
            _, _, change_conditions, change_ambiguous = _calendar_relations(
                line.changed_najia_branch,
                line.changed_element,
                month_branch=month_branch,
                day_branch=day_branch,
            )
            changed_availability, changed_conditions, changed_ambiguous = _availability(
                context_confirmed=context_confirmed,
                is_void=line.changed_is_void,
                conditions=change_conditions,
                ambiguous=change_ambiguous,
                month_growth=changed_month_growth,
                day_growth=changed_day_growth,
            )

        matrix.append(
            LineValidity(
                position=line.position,
                selected_use=line.position == selected,
                branch=line.najia_branch,
                element=line.element,
                moving=line.moving,
                availability=availability,
                conditions=conditions_tuple,
                ambiguous_conditions=ambiguous_tuple,
                month_relation=month_relation,
                day_relation=day_relation,
                month_growth_stage=month_growth,
                day_growth_stage=day_growth,
                changed_branch=line.changed_najia_branch,
                changed_element=line.changed_element,
                changed_availability=changed_availability,
                changed_conditions=changed_conditions,
                changed_ambiguous_conditions=changed_ambiguous,
                changed_month_growth_stage=changed_month_growth,
                changed_day_growth_stage=changed_day_growth,
            )
        )
    return tuple(matrix)


def _edge_status(source: str, target: str) -> str:
    if source == "available_candidate" and target == "available_candidate":
        return "active_candidate"
    if "unknown_context" in {source, target}:
        return "unknown_context"
    return "conditional"


def _influence_edges(
    advanced: AdvancedRuntimeReport,
    line_matrix: tuple[LineValidity, ...],
) -> tuple[InfluenceEdge, ...]:
    by_position = {line.position: line for line in line_matrix}
    edges: list[InfluenceEdge] = []

    for fact in advanced.facts:
        if fact.category == "moving_graph_element" and len(fact.positions) == 2:
            source_position, target_position = fact.positions
            source = by_position[source_position]
            target = by_position[target_position]
            edges.append(
                InfluenceEdge(
                    edge_id=f"moving:{source_position}:{target_position}",
                    source_kind="moving_line",
                    source_position=source_position,
                    target_position=target_position,
                    relation=fact.value,
                    source_availability=source.availability,
                    target_availability=target.availability,
                    edge_status=_edge_status(source.availability, target.availability),
                    technical=f"动爻第{source_position}爻到第{target_position}爻的五行关系为{fact.value}。",
                    plain="只有来源和目标都通过有效性门禁时，这条边才是活动候选；仍不代表最终生克成立。",
                )
            )
        elif fact.category == "self_change_element" and len(fact.positions) == 1:
            position = fact.positions[0]
            target = by_position[position]
            changed_status = target.changed_availability or "unknown_context"
            edges.append(
                InfluenceEdge(
                    edge_id=f"changed:{position}:{position}",
                    source_kind="changed_line",
                    source_position=position,
                    target_position=position,
                    relation=fact.value,
                    source_availability=changed_status,
                    target_availability=target.availability,
                    edge_status=_edge_status(changed_status, target.availability),
                    technical=f"第{position}爻变爻相对原爻的五行关系为{fact.value}。",
                    plain="回头生克只有原爻与变爻均通过门禁时才是活动候选，否则保持条件性。",
                )
            )
    return tuple(sorted(edges, key=lambda edge: edge.edge_id))


def _hidden_validity(
    record: LiuYaoCaseRecord,
    advanced: AdvancedRuntimeReport,
) -> tuple[HiddenCandidateValidity, ...]:
    confirmed = advanced.context_status.startswith("confirmed_")
    month = record.chart.month_branch if confirmed else None
    day = record.chart.day_ganzhi[1] if confirmed and record.chart.day_ganzhi else None
    results: list[HiddenCandidateValidity] = []

    for fact in advanced.facts:
        if fact.category != "hidden_spirit" or len(fact.positions) != 1:
            continue
        position = fact.positions[0]
        hidden_branch, flying_branch = fact.branches
        hidden_element, flying_element = fact.elements
        conditions: list[str] = []
        ambiguous: list[str] = []
        if not confirmed:
            status = "unknown_context"
        else:
            if month is not None:
                month_relation = classify_branch_relation(month, hidden_branch)
                if month_relation == "clash":
                    conditions.append("hidden_month_break")
                elif month_relation == "combine":
                    ambiguous.append("hidden_month_combine_effect_unresolved")
            if day is not None:
                day_relation = classify_branch_relation(day, hidden_branch)
                if day_relation == "clash":
                    ambiguous.append("hidden_day_clash_effect_unresolved")
                elif day_relation == "combine":
                    ambiguous.append("hidden_day_combine_effect_unresolved")
            if record.chart.void_branches and hidden_branch in record.chart.void_branches:
                ambiguous.append("hidden_void_effect_unresolved")
            if conditions:
                status = "constrained_candidate"
            elif ambiguous:
                status = "unresolved_candidate"
            else:
                status = "candidate_only"
        results.append(
            HiddenCandidateValidity(
                relation=fact.relation,
                position=position,
                hidden_branch=hidden_branch,
                flying_branch=flying_branch,
                flying_to_hidden=classify_element_relation(flying_element, hidden_element),
                hidden_to_flying=classify_element_relation(hidden_element, flying_element),
                status=status,
                conditions=tuple(dict.fromkeys(conditions)),
                ambiguous_conditions=tuple(dict.fromkeys(ambiguous)),
                technical=(
                    f"{fact.relation}伏神候选在第{position}爻；飞神{flying_branch}{flying_element}，"
                    f"伏神{hidden_branch}{hidden_element}。"
                ),
                plain="这里只评估候选条件，不代表伏神已经出伏、得用或能够决定结果。",
            )
        )
    return tuple(sorted(results, key=lambda item: (item.relation, item.position)))


def _conflicts(
    line_matrix: tuple[LineValidity, ...],
    *,
    reality_blocked: bool,
) -> tuple[ValidityConflict, ...]:
    conflicts: list[ValidityConflict] = []
    if reality_blocked:
        conflicts.append(
            ValidityConflict(
                conflict_id="reality:block",
                code="REALITY_HARD_BLOCK",
                positions=(),
                severity="hard",
                technical="已核验现实条件构成阻断，结构候选不得覆盖。",
                plain="现实条件已经卡住这件事，盘面上的有利结构不能把现实限制抹掉。",
            )
        )
    for line in line_matrix:
        if "month_break" in line.conditions and "void_effect_unresolved" in line.ambiguous_conditions:
            conflicts.append(
                ValidityConflict(
                    conflict_id=f"line:{line.position}:void-month-break",
                    code="VOID_AND_MONTH_BREAK",
                    positions=(line.position,),
                    severity="high",
                    technical=f"第{line.position}爻同时月破且旬空，作用资格未闭合。",
                    plain="这一爻同时受月破和空亡条件影响，不能只凭发动或生克就判它有效。",
                )
            )
        if line.moving and line.availability != "available_candidate":
            conflicts.append(
                ValidityConflict(
                    conflict_id=f"line:{line.position}:moving-conditional",
                    code="MOVING_BUT_CONDITIONAL",
                    positions=(line.position,),
                    severity="medium",
                    technical=f"第{line.position}爻虽动，但有效性为{line.availability}。",
                    plain="动爻不等于一定有力量；它仍受月破、空亡、墓绝或上下文缺失约束。",
                )
            )
        if line.changed_availability not in {None, "available_candidate"}:
            conflicts.append(
                ValidityConflict(
                    conflict_id=f"line:{line.position}:changed-conditional",
                    code="CHANGED_LINE_CONDITIONAL",
                    positions=(line.position,),
                    severity="medium",
                    technical=f"第{line.position}爻变爻有效性为{line.changed_availability}。",
                    plain="变爻的回头生克还没有通过有效性门禁，不能提前计入最终方向。",
                )
            )
        for condition in line.ambiguous_conditions:
            if "combine" in condition:
                conflicts.append(
                    ValidityConflict(
                        conflict_id=f"line:{line.position}:{condition}",
                        code="COMBINE_EFFECT_UNRESOLVED",
                        positions=(line.position,),
                        severity="medium",
                        technical=f"第{line.position}爻存在六合条件，但合起、合绊、合住或合化未判定。",
                        plain="这里只确认有合，不把它直接说成有利或被绊住。",
                    )
                )
            elif "day_clash" in condition:
                conflicts.append(
                    ValidityConflict(
                        conflict_id=f"line:{line.position}:{condition}",
                        code="DAY_CLASH_EFFECT_UNRESOLVED",
                        positions=(line.position,),
                        severity="medium",
                        technical=f"第{line.position}爻受日冲，暗动、冲散等条件尚未闭合。",
                        plain="这里只确认被日冲，暂不选择暗动或冲散其中一种解释。",
                    )
                )
            elif "growth_墓" in condition or "growth_绝" in condition:
                conflicts.append(
                    ValidityConflict(
                        conflict_id=f"line:{line.position}:{condition}",
                        code="GROWTH_STAGE_EFFECT_UNRESOLVED",
                        positions=(line.position,),
                        severity="medium",
                        technical=f"第{line.position}爻出现{condition}，尚未结合旺衰和冲墓条件。",
                        plain="墓或绝只是当前阶段标签，不能单独等同于无力、失败或事情结束。",
                    )
                )
    unique = {item.conflict_id: item for item in conflicts}
    return tuple(unique[key] for key in sorted(unique))


def build_validity_matrix(
    record: LiuYaoCaseRecord,
    request: ValidityRequest,
) -> ValidityMatrixReport:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    if not isinstance(request, ValidityRequest):
        raise LiuYaoError("INVALID_INPUT", "request 必须是 ValidityRequest")

    interpretation = interpret_case(record, request.interpretation)
    advanced = build_advanced_runtime_report(record, request.advanced_context)
    line_matrix = _line_matrix(record, interpretation, advanced)
    edges = _influence_edges(advanced, line_matrix)
    hidden = _hidden_validity(record, advanced)
    reality_blocked = interpretation.status == "reality_blocked"
    conflicts = _conflicts(line_matrix, reality_blocked=reality_blocked)

    unresolved: list[str] = []
    if advanced.context_status in {"missing", "provided_unconfirmed"}:
        unresolved.append("calendar_context_not_confirmed")
    if interpretation.use_selection.status != "selected":
        unresolved.append("use_line_not_uniquely_selected")
    if hidden:
        unresolved.append("hidden_spirit_activation_not_resolved")
    if any(line.availability != "available_candidate" for line in line_matrix):
        unresolved.append("line_effectiveness_conditions_open")
    if any(edge.edge_status != "active_candidate" for edge in edges):
        unresolved.append("dynamic_paths_not_fully_active")
    if conflicts:
        unresolved.append("conflict_matrix_not_closed")

    if reality_blocked:
        matrix_status = "reality_blocked"
        headline = "现实阻断优先，结构候选不得覆盖现实事实。"
        reality_override = "blocking"
    elif interpretation.status == "unsupported_focus":
        matrix_status = "unsupported_focus"
        headline = "当前焦点不适合由单次六爻建立方向判断。"
        reality_override = "none"
    elif interpretation.use_selection.status != "selected":
        matrix_status = "needs_confirmation"
        headline = "用神候选尚未唯一确认，暂不裁定作用链。"
        reality_override = "none"
    elif advanced.context_status in {"missing", "provided_unconfirmed"}:
        matrix_status = "calendar_unconfirmed"
        headline = "月日上下文未通过来源门禁，作用资格保持未决。"
        reality_override = "none"
    elif conflicts or unresolved:
        matrix_status = "conditional"
        headline = "已建立作用条件矩阵，但仍有空破、合冲、墓绝或动变条件未闭合。"
        reality_override = "mixed" if interpretation.request.reality_status == "mixed" else "none"
    else:
        matrix_status = "structurally_available"
        headline = "当前结构候选通过基础门禁；这仍不是成败或应期结论。"
        reality_override = "none"

    warnings = tuple(
        dict.fromkeys(
            advanced.warnings
            + interpretation.warnings
            + (
                "有效性矩阵不使用简单加减分，也不把条件数量换算为成功概率。",
                "active_candidate 只表示通过当前基础门禁，不代表实际作用已经被前瞻案例验证。",
            )
        )
    )
    limits = tuple(
        dict.fromkeys(
            advanced.limits
            + interpretation.limits
            + (
                "尚未实现暗动、冲墓、合化、三合成局、跨位变爻传递和完整旺衰优先级。",
                "本矩阵不生成应期、确定日期、成功概率或付费吉凶成品。",
            )
        )
    )
    return ValidityMatrixReport(
        case_id=record.cast.case_id,
        chart_sha256=record.chart.canonical_sha256,
        request=request,
        interpretation_sha256=interpretation.canonical_sha256,
        advanced_runtime_sha256=advanced.canonical_sha256,
        selected_use_position=interpretation.use_selection.selected_position,
        matrix_status=matrix_status,
        line_validity=line_matrix,
        influence_edges=edges,
        hidden_candidates=hidden,
        conflicts=conflicts,
        unresolved_dependencies=tuple(dict.fromkeys(unresolved)),
        reality_override=reality_override,
        headline=headline,
        warnings=warnings,
        limits=limits,
    )


__all__ = [
    "VALIDITY_MATRIX_METHOD_ID",
    "VALIDITY_MATRIX_PRODUCTION_ALLOWED",
    "VALIDITY_MATRIX_STATUS",
    "HiddenCandidateValidity",
    "InfluenceEdge",
    "LineValidity",
    "ValidityConflict",
    "ValidityMatrixReport",
    "ValidityRequest",
    "build_validity_matrix",
]
