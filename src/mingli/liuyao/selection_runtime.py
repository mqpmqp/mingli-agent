from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .case_record import LiuYaoCaseRecord
from .selection_core import (
    SELECTION_PRODUCTION_ALLOWED,
    AutoSelectionRequest,
    SelectionCandidate,
    SelectionReport,
    TopicDimension,
    build_selection_report,
)
from .tables import PREDICTION_VALIDITY, digest
from .validation import LiuYaoError, _reject_unknown, _require_mapping

SELECTION_RUNTIME_METHOD_ID = "liuyao-contract-driven-selection-runtime@0.1.0"
SELECTION_RUNTIME_STATUS = "review_only"
SELECTION_RUNTIME_PRODUCTION_ALLOWED = False

_DIRECTIONAL_MODES = frozenset(
    {
        "structural",
        "structural_reality_required",
        "structural_advisory",
        "manual_relation_required",
    }
)
_REALITY_STATUSES = frozenset({"unknown", "supportive", "blocking", "mixed"})


@dataclass(frozen=True, slots=True)
class SelectionRuntimeRequest:
    selection: AutoSelectionRequest
    event_contract_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.selection, AutoSelectionRequest):
            raise LiuYaoError("INVALID_INPUT", "selection 必须是 AutoSelectionRequest")
        if self.selection.contract_focus_confirmed:
            if not isinstance(self.event_contract_sha256, str) or re.fullmatch(
                r"[0-9a-f]{64}", self.event_contract_sha256
            ) is None:
                raise LiuYaoError(
                    "CONTRACT_HASH_REQUIRED",
                    "确认事件焦点时必须提供64位小写十六进制 event_contract_sha256",
                )
        elif self.event_contract_sha256 is not None:
            raise LiuYaoError(
                "CONTRACT_CONFIRMATION_REQUIRED",
                "未确认事件焦点时不能填写 event_contract_sha256",
            )

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "selection": self.selection.to_dict(),
            "event_contract_sha256": self.event_contract_sha256,
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SelectionRuntimeRequest":
        allowed = {"selection", "event_contract_sha256", "canonical_sha256"}
        _reject_unknown(value, allowed, "selection_runtime_request")
        if "selection" not in value:
            raise LiuYaoError("INVALID_INPUT", "selection_runtime_request 缺少字段：selection")
        request = cls(
            selection=AutoSelectionRequest.from_mapping(
                _require_mapping(value["selection"], "selection")
            ),
            event_contract_sha256=value.get("event_contract_sha256"),
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != request.canonical_sha256:
            raise LiuYaoError(
                "RECORD_TAMPERED",
                "selection_runtime_request canonical_sha256 与重算结果不一致",
            )
        return request


@dataclass(frozen=True, slots=True)
class SelectionRuntimeReport:
    case_id: str
    chart_sha256: str
    request: SelectionRuntimeRequest
    event_contract_sha256: str
    core_report_sha256: str
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
    policy_checks: tuple[str, ...]
    headline: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "method_id": SELECTION_RUNTIME_METHOD_ID,
            "selection_runtime_status": SELECTION_RUNTIME_STATUS,
            "core_selection_status": "review_only",
            "production_allowed": SELECTION_RUNTIME_PRODUCTION_ALLOWED,
            "core_production_allowed": SELECTION_PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "case_id": self.case_id,
            "chart_sha256": self.chart_sha256,
            "request": self.request.to_dict(),
            "event_contract_sha256": self.event_contract_sha256,
            "core_report_sha256": self.core_report_sha256,
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
            "policy_checks": list(self.policy_checks),
            "headline": self.headline,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def _validate_reality(request: AutoSelectionRequest) -> None:
    status = request.reality_status
    if status not in _REALITY_STATUSES:
        raise LiuYaoError(
            "INVALID_INPUT",
            "reality_status 必须是 unknown、supportive、blocking 或 mixed",
        )
    facts = request.reality_facts
    refs = request.reality_evidence_refs
    if status == "unknown":
        if facts or refs:
            raise LiuYaoError(
                "REALITY_STATUS_REQUIRED",
                "提供现实事实或证据引用时，reality_status 不能是 unknown",
            )
        return
    if not facts or not refs:
        raise LiuYaoError(
            "REALITY_EVIDENCE_REQUIRED",
            "非 unknown 的 reality_status 必须同时提供 reality_facts 和 reality_evidence_refs",
        )


def _focus_mode(report: SelectionReport, focus_dimension: str) -> str:
    for dimension in report.topic_dimensions:
        if dimension.dimension_id == focus_dimension:
            return dimension.mode
    raise RuntimeError(f"selection report missing focus dimension: {focus_dimension}")


def _runtime_policy(
    core: SelectionReport,
    request: AutoSelectionRequest,
) -> tuple[int | None, str, str, tuple[str, ...]]:
    recommended = core.recommended_position
    status = core.recommendation_status
    headline = core.headline
    checks: list[str] = [
        "event_contract_hash_bound",
        "reality_evidence_shape_validated",
        "proxy_subject_policy_checked",
    ]

    mode = _focus_mode(core, request.focus_dimension)
    if mode not in _DIRECTIONAL_MODES:
        checks.append("unsupported_focus_override_blocked")
        return (
            None,
            "unsupported_focus",
            "该维度不允许通过六亲 override 绕过现实或专业边界。",
            tuple(checks),
        )

    if mode == "structural_reality_required" and request.reality_status == "unknown":
        checks.append("reality_context_required")
        return (
            None,
            "reality_context_required",
            "该维度必须补充现实关系条件后，候选排序才可进入人工复核。",
            tuple(checks),
        )

    if request.primary_position is None and core.candidates:
        visible = [candidate for candidate in core.candidates if candidate.source == "visible"]
        if visible:
            best_availability = min(candidate.rank_vector[0] for candidate in visible)
            same_tier = [
                candidate
                for candidate in visible
                if candidate.rank_vector[0] == best_availability
            ]
            if len(same_tier) > 1:
                checks.append("moving_tiebreak_does_not_resolve_use_line")
                return (
                    None,
                    "tie_needs_confirmation",
                    "多个可见候选处于同一有效性层级；发动只能作为提示，不能自动决定最终用神。",
                    tuple(checks),
                )

    checks.append("core_recommendation_preserved")
    return recommended, status, headline, tuple(checks)


def build_selection_runtime_report(
    record: LiuYaoCaseRecord,
    request: SelectionRuntimeRequest,
) -> SelectionRuntimeReport:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    if not isinstance(request, SelectionRuntimeRequest):
        raise LiuYaoError("INVALID_INPUT", "request 必须是 SelectionRuntimeRequest")

    selection = request.selection
    _validate_reality(selection)
    contract_hash = digest(record.cast.event_contract.to_dict())
    if selection.contract_focus_confirmed and request.event_contract_sha256 != contract_hash:
        raise LiuYaoError(
            "CONTRACT_BINDING_MISMATCH",
            "event_contract_sha256 与冻结案例的事件合同不一致",
        )

    core = build_selection_report(record, selection)
    recommended, status, headline, policy_checks = _runtime_policy(core, selection)
    warnings = list(core.warnings)
    if status == "tie_needs_confirmation" and core.recommended_position is not None:
        warnings.append(
            "底层候选排序曾因发动状态产生唯一排序；运行时策略已撤销该自动决定。"
        )
    if status == "unsupported_focus" and selection.primary_relation_override is not None:
        warnings.append(
            "人工六亲 override 已留痕，但不允许越过专业判断或现实资料边界。"
        )
    limits = tuple(
        dict.fromkeys(
            core.limits
            + (
                "运行时只验证事件合同哈希与请求绑定，不核验 contract_source_refs 的外部内容。",
                "同一有效性层级的多候选不会因单纯发动而自动决胜。",
                "推荐候选仍不是最终用神、吉凶结论、应期或成功概率。",
            )
        )
    )
    return SelectionRuntimeReport(
        case_id=core.case_id,
        chart_sha256=core.chart_sha256,
        request=request,
        event_contract_sha256=contract_hash,
        core_report_sha256=core.canonical_sha256,
        primary_relation=core.primary_relation,
        relation_source=core.relation_source,
        secondary_relations=core.secondary_relations,
        shi_position=core.shi_position,
        ying_position=core.ying_position,
        subject_position=core.subject_position,
        counterparty_position=core.counterparty_position,
        candidates=core.candidates,
        recommended_position=recommended,
        recommendation_status=status,
        topic_dimensions=core.topic_dimensions,
        validity_matrix_sha256=core.validity_matrix_sha256,
        policy_checks=policy_checks,
        headline=headline,
        warnings=tuple(dict.fromkeys(warnings)),
        limits=limits,
    )


__all__ = [
    "SELECTION_RUNTIME_METHOD_ID",
    "SELECTION_RUNTIME_PRODUCTION_ALLOWED",
    "SELECTION_RUNTIME_STATUS",
    "SelectionRuntimeReport",
    "SelectionRuntimeRequest",
    "build_selection_runtime_report",
]
