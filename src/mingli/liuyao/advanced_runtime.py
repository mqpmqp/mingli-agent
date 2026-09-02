from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .advanced_facts import (
    ADVANCED_FACT_METHOD_ID,
    ADVANCED_FACT_PRODUCTION_ALLOWED,
    ADVANCED_FACT_STATUS,
    ADVANCED_FACT_TABLE_SHA256,
    AdvancedFact,
    build_advanced_fact_report,
)
from .case_record import LiuYaoCaseRecord
from .tables import PREDICTION_VALIDITY, digest
from .validation import LiuYaoError, _reject_unknown, _string_tuple

ADVANCED_RUNTIME_METHOD_ID = "liuyao-advanced-fact-runtime@0.1.0"
ADVANCED_RUNTIME_STATUS = "review_only"
ADVANCED_RUNTIME_PRODUCTION_ALLOWED = False

_CALENDAR_DEPENDENT_CATEGORIES = frozenset({"growth_stage"})


@dataclass(frozen=True, slots=True)
class AdvancedContextRequest:
    calendar_context_confirmed: bool = False
    calendar_source_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.calendar_context_confirmed, bool):
            raise LiuYaoError("INVALID_INPUT", "calendar_context_confirmed 必须是布尔值")
        refs = _string_tuple(self.calendar_source_refs, "calendar_source_refs")
        object.__setattr__(self, "calendar_source_refs", refs)
        if self.calendar_context_confirmed and not refs:
            raise LiuYaoError(
                "CALENDAR_SOURCE_REQUIRED",
                "确认月建或日柱上下文时必须提供 calendar_source_refs",
            )
        if refs and not self.calendar_context_confirmed:
            raise LiuYaoError(
                "CALENDAR_CONFIRMATION_REQUIRED",
                "提供 calendar_source_refs 时必须显式设置 calendar_context_confirmed=true",
            )

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "calendar_context_confirmed": self.calendar_context_confirmed,
            "calendar_source_refs": list(self.calendar_source_refs),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AdvancedContextRequest":
        allowed = {
            "calendar_context_confirmed",
            "calendar_source_refs",
            "canonical_sha256",
        }
        _reject_unknown(value, allowed, "advanced_context_request")
        request = cls(
            calendar_context_confirmed=value.get("calendar_context_confirmed", False),
            calendar_source_refs=_string_tuple(
                value.get("calendar_source_refs", ()),
                "calendar_source_refs",
            ),
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != request.canonical_sha256:
            raise LiuYaoError(
                "RECORD_TAMPERED",
                "advanced_context_request canonical_sha256 与重算结果不一致",
            )
        return request


@dataclass(frozen=True, slots=True)
class AdvancedRuntimeReport:
    case_id: str
    chart_sha256: str
    request: AdvancedContextRequest
    raw_fact_report_sha256: str
    facts: tuple[AdvancedFact, ...]
    missing_relations: tuple[str, ...]
    context_status: str
    provenance_status: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "method_id": ADVANCED_RUNTIME_METHOD_ID,
            "fact_method_id": ADVANCED_FACT_METHOD_ID,
            "advanced_runtime_status": ADVANCED_RUNTIME_STATUS,
            "advanced_fact_status": ADVANCED_FACT_STATUS,
            "production_allowed": ADVANCED_RUNTIME_PRODUCTION_ALLOWED,
            "fact_production_allowed": ADVANCED_FACT_PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "advanced_table_sha256": ADVANCED_FACT_TABLE_SHA256,
            "case_id": self.case_id,
            "chart_sha256": self.chart_sha256,
            "request": self.request.to_dict(),
            "raw_fact_report_sha256": self.raw_fact_report_sha256,
            "facts": [fact.to_dict() for fact in self.facts],
            "missing_relations": list(self.missing_relations),
            "context_status": self.context_status,
            "provenance_status": self.provenance_status,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def build_advanced_runtime_report(
    record: LiuYaoCaseRecord,
    request: AdvancedContextRequest,
) -> AdvancedRuntimeReport:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    if not isinstance(request, AdvancedContextRequest):
        raise LiuYaoError("INVALID_INPUT", "request 必须是 AdvancedContextRequest")

    raw = build_advanced_fact_report(record)
    has_month = record.chart.month_branch is not None
    has_day = record.chart.day_ganzhi is not None
    has_calendar = has_month or has_day

    if request.calendar_context_confirmed and not has_calendar:
        raise LiuYaoError(
            "CALENDAR_CONTEXT_MISSING",
            "不能确认不存在的月建或日柱上下文",
        )

    warnings = list(raw.warnings)
    if has_calendar and not request.calendar_context_confirmed:
        facts = tuple(
            fact
            for fact in raw.facts
            if fact.category not in _CALENDAR_DEPENDENT_CATEGORIES
        )
        context_status = "provided_unconfirmed"
        provenance_status = "blocked_unconfirmed"
        warnings.append(
            "cast 中虽有月建或日柱，但未通过来源确认门禁；十二长生事实已从可用输出中移除。"
        )
    elif has_calendar:
        facts = raw.facts
        context_status = "confirmed_complete" if has_month and has_day else "confirmed_partial"
        provenance_status = "declared_sources_present_not_runtime_verified"
        warnings.append(
            "calendar_source_refs 只证明调用方声明了来源；当前运行时不核验链接、文件或历法计算的真实性。"
        )
    else:
        facts = raw.facts
        context_status = "missing"
        provenance_status = "not_provided"

    limits = tuple(
        dict.fromkeys(
            raw.limits
            + (
                "高级运行时只检查历法来源引用是否存在，不验证来源内容或计算正确性。",
                "未确认的月建、日柱不能驱动十二长生、旺衰、墓绝或后续应期判断。",
                "本报告仍是结构事实收据，不是吉凶预测、成功概率或生产断卦结论。",
            )
        )
    )
    return AdvancedRuntimeReport(
        case_id=record.cast.case_id,
        chart_sha256=record.chart.canonical_sha256,
        request=request,
        raw_fact_report_sha256=raw.canonical_sha256,
        facts=tuple(sorted(facts, key=lambda fact: fact.fact_id)),
        missing_relations=raw.missing_relations,
        context_status=context_status,
        provenance_status=provenance_status,
        warnings=tuple(dict.fromkeys(warnings)),
        limits=limits,
    )


__all__ = [
    "ADVANCED_RUNTIME_METHOD_ID",
    "ADVANCED_RUNTIME_PRODUCTION_ALLOWED",
    "ADVANCED_RUNTIME_STATUS",
    "AdvancedContextRequest",
    "AdvancedRuntimeReport",
    "build_advanced_runtime_report",
]
