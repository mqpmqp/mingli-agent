from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from .advanced_facts import classify_branch_relation
from .advanced_runtime import AdvancedContextRequest
from .case_record import LiuYaoCaseRecord
from .interpretation import InterpretationRequest
from .selection_runtime import (
    SelectionRuntimeReport,
    SelectionRuntimeRequest,
    build_selection_runtime_report,
)
from .tables import BRANCHES, PREDICTION_VALIDITY, digest
from .validation import (
    LiuYaoError,
    _iso_date,
    _non_empty,
    _reject_unknown,
    _require_mapping,
    _string_tuple,
)
from .validity_matrix import ValidityRequest, build_validity_matrix

TIMING_METHOD_ID = "liuyao-conditional-timing-candidates@0.1.0"
TIMING_STATUS = "review_only"
TIMING_PRODUCTION_ALLOWED = False

_SELECTION_READY = frozenset(
    {
        "recommended_visible_candidate",
        "explicit_position_confirmed",
    }
)


def _partner(branch: str, relation: str) -> str:
    matches = [candidate for candidate in BRANCHES if classify_branch_relation(branch, candidate) == relation]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {relation} partner for {branch}: {matches}")
    return matches[0]


@dataclass(frozen=True, slots=True)
class TimingAnchor:
    anchor_id: str
    label: str
    start_date: str
    end_date: str
    branch_tags: tuple[str, ...]
    source_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchor_id", _non_empty(self.anchor_id, "anchor_id"))
        object.__setattr__(self, "label", _non_empty(self.label, "label"))
        object.__setattr__(self, "start_date", _iso_date(self.start_date, "start_date"))
        object.__setattr__(self, "end_date", _iso_date(self.end_date, "end_date"))
        if date.fromisoformat(self.end_date) < date.fromisoformat(self.start_date):
            raise LiuYaoError("INVALID_INPUT", "end_date 不能早于 start_date")
        tags = _string_tuple(self.branch_tags, "branch_tags")
        if not tags or any(tag not in BRANCHES for tag in tags):
            raise LiuYaoError("INVALID_INPUT", "branch_tags 必须包含至少一个有效地支")
        refs = _string_tuple(self.source_refs, "source_refs")
        if not refs:
            raise LiuYaoError("TIMING_SOURCE_REQUIRED", "每个时间锚点必须提供 source_refs")
        object.__setattr__(self, "branch_tags", tuple(dict.fromkeys(tags)))
        object.__setattr__(self, "source_refs", refs)

    def to_dict(self) -> dict[str, object]:
        return {
            "anchor_id": self.anchor_id,
            "label": self.label,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "branch_tags": list(self.branch_tags),
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TimingAnchor":
        allowed = {"anchor_id", "label", "start_date", "end_date", "branch_tags", "source_refs"}
        _reject_unknown(value, allowed, "timing_anchor")
        missing = allowed - set(value)
        if missing:
            raise LiuYaoError("INVALID_INPUT", f"timing_anchor 缺少字段：{', '.join(sorted(missing))}")
        return cls(
            anchor_id=value["anchor_id"],
            label=value["label"],
            start_date=value["start_date"],
            end_date=value["end_date"],
            branch_tags=_string_tuple(value["branch_tags"], "branch_tags"),
            source_refs=_string_tuple(value["source_refs"], "source_refs"),
        )


@dataclass(frozen=True, slots=True)
class TimingRequest:
    selection: SelectionRuntimeRequest
    anchors: tuple[TimingAnchor, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.selection, SelectionRuntimeRequest):
            raise LiuYaoError("INVALID_INPUT", "selection 必须是 SelectionRuntimeRequest")
        anchors = tuple(self.anchors)
        if any(not isinstance(anchor, TimingAnchor) for anchor in anchors):
            raise LiuYaoError("INVALID_INPUT", "anchors 只能包含 TimingAnchor")
        ids = [anchor.anchor_id for anchor in anchors]
        if len(ids) != len(set(ids)):
            raise LiuYaoError("DUPLICATE_TIMING_ANCHOR", "anchor_id 必须唯一")
        object.__setattr__(self, "anchors", anchors)

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "selection": self.selection.to_dict(),
            "anchors": [anchor.to_dict() for anchor in self.anchors],
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TimingRequest":
        allowed = {"selection", "anchors", "canonical_sha256"}
        _reject_unknown(value, allowed, "timing_request")
        if "selection" not in value:
            raise LiuYaoError("INVALID_INPUT", "timing_request 缺少字段：selection")
        raw_anchors = value.get("anchors", ())
        if isinstance(raw_anchors, (str, bytes)) or not isinstance(raw_anchors, Sequence):
            raise LiuYaoError("INVALID_INPUT", "anchors 必须是数组")
        request = cls(
            selection=SelectionRuntimeRequest.from_mapping(
                _require_mapping(value["selection"], "selection")
            ),
            anchors=tuple(
                TimingAnchor.from_mapping(_require_mapping(item, "timing_anchor"))
                for item in raw_anchors
            ),
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != request.canonical_sha256:
            raise LiuYaoError("RECORD_TAMPERED", "timing_request canonical_sha256 与重算结果不一致")
        return request


@dataclass(frozen=True, slots=True)
class TimingTrigger:
    trigger_id: str
    trigger_kind: str
    target_branch: str
    source_conditions: tuple[str, ...]
    priority_band: str
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_kind": self.trigger_kind,
            "target_branch": self.target_branch,
            "source_conditions": list(self.source_conditions),
            "priority_band": self.priority_band,
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class TimingCandidate:
    candidate_id: str
    anchor_id: str
    label: str
    start_date: str
    end_date: str
    matched_branches: tuple[str, ...]
    trigger_ids: tuple[str, ...]
    status: str
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "anchor_id": self.anchor_id,
            "label": self.label,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "matched_branches": list(self.matched_branches),
            "trigger_ids": list(self.trigger_ids),
            "status": self.status,
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class TimingReport:
    case_id: str
    chart_sha256: str
    request: TimingRequest
    selection_report_sha256: str
    validity_matrix_sha256: str | None
    selected_position: int | None
    selected_branch: str | None
    timing_state: str
    symbolic_triggers: tuple[TimingTrigger, ...]
    candidates: tuple[TimingCandidate, ...]
    unmatched_anchor_ids: tuple[str, ...]
    headline: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "method_id": TIMING_METHOD_ID,
            "timing_status": TIMING_STATUS,
            "production_allowed": TIMING_PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "case_id": self.case_id,
            "chart_sha256": self.chart_sha256,
            "request": self.request.to_dict(),
            "selection_report_sha256": self.selection_report_sha256,
            "validity_matrix_sha256": self.validity_matrix_sha256,
            "selected_position": self.selected_position,
            "selected_branch": self.selected_branch,
            "timing_state": self.timing_state,
            "symbolic_triggers": [trigger.to_dict() for trigger in self.symbolic_triggers],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "unmatched_anchor_ids": list(self.unmatched_anchor_ids),
            "headline": self.headline,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def _interpretation_request(selection: SelectionRuntimeReport) -> InterpretationRequest:
    raw = selection.request.selection
    if selection.primary_relation is None or selection.recommended_position is None:
        raise RuntimeError("selection is not timing-ready")
    payload: dict[str, object] = {
        "topic": raw.topic,
        "focus_dimension": raw.focus_dimension,
        "use_relation": selection.primary_relation,
        "primary_position": selection.recommended_position,
        "secondary_relations": list(selection.secondary_relations),
        "calendar_context_confirmed": raw.calendar_context_confirmed,
        "calendar_source_refs": list(raw.calendar_source_refs),
        "reality_status": raw.reality_status,
        "reality_facts": list(raw.reality_facts),
        "reality_evidence_refs": list(raw.reality_evidence_refs),
        "notes": list(raw.notes),
    }
    return InterpretationRequest.from_mapping(payload)


def _validity(record: LiuYaoCaseRecord, selection: SelectionRuntimeReport):
    raw = selection.request.selection
    request = ValidityRequest(
        interpretation=_interpretation_request(selection),
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=raw.calendar_context_confirmed,
            calendar_source_refs=raw.calendar_source_refs,
        ),
    )
    return build_validity_matrix(record, request)


def _symbolic_triggers(record: LiuYaoCaseRecord, selection: SelectionRuntimeReport, matrix) -> tuple[TimingTrigger, ...]:
    position = selection.recommended_position
    if position is None:
        return ()
    line = record.chart.lines[position - 1]
    validity = next(item for item in matrix.line_validity if item.position == position)
    triggers: dict[str, TimingTrigger] = {}

    def add(kind: str, branch: str, conditions: tuple[str, ...], band: str, plain: str) -> None:
        key = f"{kind}:{branch}"
        triggers[key] = TimingTrigger(
            trigger_id=key,
            trigger_kind=kind,
            target_branch=branch,
            source_conditions=conditions,
            priority_band=band,
            technical=f"第{position}爻{line.najia_branch}支的条件化时间触发：{kind}→{branch}。",
            plain=plain,
        )

    add(
        "use_branch_value",
        line.najia_branch,
        ("selected_use_branch",),
        "primary",
        "候选时间支与所选爻同支时，只列为观察触发，不代表届时一定发生结果。",
    )
    add(
        "use_branch_clash",
        _partner(line.najia_branch, "clash"),
        ("selected_use_branch", "clash_effect_unresolved"),
        "conditional",
        "冲所选爻可能对应冲起、冲散或冲开，具体含义尚未闭合。",
    )
    add(
        "use_branch_combine",
        _partner(line.najia_branch, "combine"),
        ("selected_use_branch", "combine_effect_unresolved"),
        "conditional",
        "合所选爻只表示关系触发，不能直接说成合起、合绊或合化。",
    )

    if "void_effect_unresolved" in validity.ambiguous_conditions:
        add(
            "void_fill",
            line.najia_branch,
            ("void_effect_unresolved",),
            "primary",
            "旬空候选以填实作为观察条件之一；是否有效仍取决于空破、动变和现实流程。",
        )
        add(
            "void_clash",
            _partner(line.najia_branch, "clash"),
            ("void_effect_unresolved", "clash_effect_unresolved"),
            "conditional",
            "冲空只列为传统候选条件，不预判是冲起还是冲散。",
        )
    if "month_break" in validity.conditions:
        add(
            "month_break_value",
            line.najia_branch,
            ("month_break",),
            "primary",
            "月破候选以逢值作为观察条件之一；不表示该窗口自动转为有力。",
        )
        add(
            "month_break_combine",
            _partner(line.najia_branch, "combine"),
            ("month_break", "combine_effect_unresolved"),
            "conditional",
            "月破逢合只列为待验证条件，不能直接解释为解除。",
        )
    if line.moving and line.changed_najia_branch is not None:
        add(
            "changed_branch_value",
            line.changed_najia_branch,
            ("moving_use_line", "changed_line_condition"),
            "secondary",
            "变爻地支逢值可作为次级观察条件，但回头生克必须先通过有效性矩阵。",
        )
    return tuple(triggers[key] for key in sorted(triggers))


def _validate_anchors(record: LiuYaoCaseRecord, anchors: tuple[TimingAnchor, ...]) -> None:
    start = datetime.fromisoformat(record.cast.completed_at).date()
    deadline = date.fromisoformat(record.cast.event_contract.deadline)
    for anchor in anchors:
        anchor_start = date.fromisoformat(anchor.start_date)
        anchor_end = date.fromisoformat(anchor.end_date)
        if anchor_start < start:
            raise LiuYaoError(
                "TIMING_ANCHOR_BEFORE_CAST",
                f"时间锚点 {anchor.anchor_id} 早于起卦完成日期",
            )
        if anchor_end > deadline:
            raise LiuYaoError(
                "TIMING_ANCHOR_OUTSIDE_CONTRACT",
                f"时间锚点 {anchor.anchor_id} 超过事件合同截止日期",
            )


def _anchor_candidates(
    anchors: tuple[TimingAnchor, ...],
    triggers: tuple[TimingTrigger, ...],
) -> tuple[tuple[TimingCandidate, ...], tuple[str, ...]]:
    by_branch: dict[str, list[TimingTrigger]] = {}
    for trigger in triggers:
        by_branch.setdefault(trigger.target_branch, []).append(trigger)

    candidates: list[TimingCandidate] = []
    unmatched: list[str] = []
    for anchor in anchors:
        matched_branches = tuple(branch for branch in anchor.branch_tags if branch in by_branch)
        matched_triggers = tuple(
            sorted(
                {
                    trigger.trigger_id
                    for branch in matched_branches
                    for trigger in by_branch[branch]
                }
            )
        )
        if not matched_triggers:
            unmatched.append(anchor.anchor_id)
            continue
        candidates.append(
            TimingCandidate(
                candidate_id=f"anchor:{anchor.anchor_id}",
                anchor_id=anchor.anchor_id,
                label=anchor.label,
                start_date=anchor.start_date,
                end_date=anchor.end_date,
                matched_branches=matched_branches,
                trigger_ids=matched_triggers,
                status="candidate_only",
                technical=(
                    f"外部时间锚点 {anchor.anchor_id} 的地支标签与"
                    f" {len(matched_triggers)} 个条件触发匹配。"
                ),
                plain="该时间段来自调用方提供的现实日程与地支标签，只是观察候选，不代表结果会在此发生。",
            )
        )
    return tuple(candidates), tuple(unmatched)


def build_timing_report(record: LiuYaoCaseRecord, request: TimingRequest) -> TimingReport:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    if not isinstance(request, TimingRequest):
        raise LiuYaoError("INVALID_INPUT", "request 必须是 TimingRequest")

    selection = build_selection_runtime_report(record, request.selection)
    _validate_anchors(record, request.anchors)
    warnings = list(selection.warnings)
    limits = list(selection.limits)

    if selection.recommendation_status == "reality_blocked":
        state = "reality_blocked"
        headline = "现实阻断已经成立，不生成盘面时间候选。"
        matrix_sha = selection.validity_matrix_sha256
        triggers: tuple[TimingTrigger, ...] = ()
        candidates: tuple[TimingCandidate, ...] = ()
        unmatched = tuple(anchor.anchor_id for anchor in request.anchors)
        selected_branch = None
    elif selection.recommendation_status not in _SELECTION_READY:
        state = "selection_unresolved"
        headline = "候选取用尚未唯一确认，不能继续生成时间候选。"
        matrix_sha = selection.validity_matrix_sha256
        triggers = ()
        candidates = ()
        unmatched = tuple(anchor.anchor_id for anchor in request.anchors)
        selected_branch = None
    elif not request.selection.selection.calendar_context_confirmed:
        state = "calendar_unconfirmed"
        headline = "月日上下文未通过来源门禁，不能生成条件化时间候选。"
        matrix_sha = selection.validity_matrix_sha256
        triggers = ()
        candidates = ()
        unmatched = tuple(anchor.anchor_id for anchor in request.anchors)
        selected_branch = None
    else:
        matrix = _validity(record, selection)
        matrix_sha = matrix.canonical_sha256
        triggers = _symbolic_triggers(record, selection, matrix)
        selected_branch = record.chart.lines[selection.recommended_position - 1].najia_branch
        if not request.anchors:
            state = "symbolic_only"
            headline = "已生成地支触发条件，但没有带来源的现实时间锚点，不能转换为日期窗口。"
            candidates = ()
            unmatched = ()
        else:
            candidates, unmatched = _anchor_candidates(request.anchors, triggers)
            if candidates:
                state = "anchored_candidates"
                headline = "已把条件触发与有来源的现实时间锚点对齐；结果仍仅为观察候选。"
            else:
                state = "no_matching_anchor"
                headline = "现实时间锚点与当前条件触发没有匹配，不生成日期候选。"

    warnings.extend(
        [
            "branch_tags 和 source_refs 只由调用方声明；当前运行时不核验历法映射或外部日程内容。",
            "同一锚点匹配多个触发不代表置信度叠加，也不能换算为成功概率。",
        ]
    )
    limits.extend(
        [
            "本层不自行把地支转换为公历日期；日期范围必须来自外部锚点。",
            "不判断冲空、合破、出墓等条件最终是有利还是不利。",
            "不输出确定日期、必然事件、成功概率或付费断卦成品。",
        ]
    )
    return TimingReport(
        case_id=record.cast.case_id,
        chart_sha256=record.chart.canonical_sha256,
        request=request,
        selection_report_sha256=selection.canonical_sha256,
        validity_matrix_sha256=matrix_sha,
        selected_position=selection.recommended_position,
        selected_branch=selected_branch,
        timing_state=state,
        symbolic_triggers=triggers,
        candidates=candidates,
        unmatched_anchor_ids=unmatched,
        headline=headline,
        warnings=tuple(dict.fromkeys(warnings)),
        limits=tuple(dict.fromkeys(limits)),
    )


__all__ = [
    "TIMING_METHOD_ID",
    "TIMING_PRODUCTION_ALLOWED",
    "TIMING_STATUS",
    "TimingAnchor",
    "TimingCandidate",
    "TimingReport",
    "TimingRequest",
    "TimingTrigger",
    "build_timing_report",
]
