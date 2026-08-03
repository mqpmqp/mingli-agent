"""Select compact user-facing views from already computed MingLi artifacts.

This module deliberately does not calculate, classify, or alter any chart
artifact.  It only selects a bounded rendering based on an explicit intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .confirmed_pillar_runtime import ConfirmedPillarRuntimeResult
from .phase23 import MingLiRuntimeResult
from .renderer import DISCLAIMER, ensure_safe_text


class RenderIntent(str, Enum):
    FULL_READING = "full_reading"
    FOCUSED_QUESTION = "focused_question"
    FOLLOW_UP = "follow_up"
    COMMENT = "comment"


@dataclass(frozen=True)
class RenderIntentResult:
    intent: RenderIntent
    answer: str
    supported: bool
    topic: str | None
    runtime_result_hash: str


_DOMAIN_TOPICS = (
    ("career_exam", "考公", "考编", "上岸"),
    ("relationship_reunion", "复合", "复联"),
    ("career", "事业", "工作", "职业", "岗位"),
    ("wealth", "财运", "财富", "收入", "钱"),
    ("relationship", "感情", "恋爱", "婚姻", "桃花"),
)
_DOMAIN_LABELS = {
    "career": "事业",
    "wealth": "财运",
    "relationship": "感情",
    "career_exam": "考公考编",
    "relationship_reunion": "复合",
}
_STATUS_LABELS = {
    "supportive": "相对顺畅",
    "challenging": "需要审慎应对",
    "mixed": "有起伏",
    "unresolved": "暂不确定",
}
_CONFIDENCE_LABELS = {"high": "高", "medium": "中", "low": "低"}


def classify_render_intent(
    text: str,
    *,
    has_active_case: bool,
    comment: bool = False,
) -> RenderIntent:
    """Classify only the user-facing view; chart calculations stay unchanged."""

    normalized = text.strip()
    if normalized == "/new" or any(token in normalized for token in ("完整", "全盘", "完整报告")):
        return RenderIntent.FULL_READING
    if comment or "评论区" in normalized:
        return RenderIntent.COMMENT
    if has_active_case and any(token in normalized for token in ("继续", "再看", "那", "还有")):
        return RenderIntent.FOLLOW_UP
    return RenderIntent.FOCUSED_QUESTION


def _topic_for(question: str) -> str | None:
    normalized = question.strip()
    for topic, *tokens in _DOMAIN_TOPICS:
        if any(token in normalized for token in tokens):
            return topic
    return None


def _with_disclaimer(body: str) -> str:
    answer = body.replace(DISCLAIMER, "").strip() + "\n\n" + DISCLAIMER
    ensure_safe_text(answer)
    return answer


def _unsupported_answer(question: str) -> str:
    label = question.strip() or "这个问题"
    return _with_disclaimer(
        f"“{label}”目前不在已确认命盘的正式支持范围。"
        "当前可支持事业、财运、感情、考公考编和复合的定向阅读；"
        "其余主题不会由通用回复补写。"
    )


def _domain_answer(
    runtime: MingLiRuntimeResult,
    topic: str,
    intent: RenderIntent,
) -> str:
    domain = topic
    if topic in {"career_exam", "relationship_reunion"}:
        scenario = runtime.scenario_assessment
        if not scenario:
            return _unsupported_answer(_DOMAIN_LABELS[topic])
        layers = scenario.get("layers")
        if not isinstance(layers, list):
            return _unsupported_answer(_DOMAIN_LABELS[topic])
        entries = [
            f"{item.get('layer')}：{item.get('label')}"
            for item in layers
            if isinstance(item, dict)
        ]
        if not entries:
            return _unsupported_answer(_DOMAIN_LABELS[topic])
        heading = "继续看" if intent is RenderIntent.FOLLOW_UP else ""
        return _with_disclaimer(
            f"{heading}{_DOMAIN_LABELS[topic]}：" + "；".join(entries) + "。"
        )

    status = runtime.effective_domain_statuses.get(domain)
    confidence = runtime.effective_domain_confidence.get(domain)
    if status not in _STATUS_LABELS or confidence not in _CONFIDENCE_LABELS:
        return _unsupported_answer(_DOMAIN_LABELS[topic])
    prefix = "继续看" if intent is RenderIntent.FOLLOW_UP else ""
    body = (
        f"{prefix}{_DOMAIN_LABELS[topic]}：当前可见趋势为{_STATUS_LABELS[status]}，"
        f"置信度{_CONFIDENCE_LABELS[confidence]}。"
    )
    if intent is not RenderIntent.COMMENT:
        body += "请结合现实条件作出决定。"
    return _with_disclaimer(body)


def render_phase23_intent(
    runtime: MingLiRuntimeResult,
    intent: RenderIntent,
    *,
    question: str,
) -> RenderIntentResult:
    """Render a selected view from a completed Phase23 result only."""

    if intent is RenderIntent.FULL_READING:
        return RenderIntentResult(
            intent=intent,
            answer=runtime.final_answer,
            supported=True,
            topic=None,
            runtime_result_hash=runtime.canonical_hash,
        )

    topic = _topic_for(question)
    if topic is None:
        return RenderIntentResult(
            intent=intent,
            answer=_unsupported_answer(question),
            supported=False,
            topic=None,
            runtime_result_hash=runtime.canonical_hash,
        )
    answer = _domain_answer(runtime, topic, intent)
    return RenderIntentResult(
        intent=intent,
        answer=answer,
        supported="支持范围" not in answer,
        topic=topic,
        runtime_result_hash=runtime.canonical_hash,
    )


def render_confirmed_pillar_follow_up(
    runtime: ConfirmedPillarRuntimeResult,
    question: str,
) -> RenderIntentResult:
    """Return the formal static-runtime boundary for a confirmed-pillar follow-up."""

    topic = _topic_for(question)
    label = _DOMAIN_LABELS.get(topic or "", question.strip() or "这个问题")
    answer = _with_disclaimer(
        f"已确认四柱的静态 Runtime 当前支持命局结构、日主强弱、格局与喜忌。"
        f"“{label}”的定向或时间性结论不在支持范围，本次不会补写。"
    )
    return RenderIntentResult(
        intent=RenderIntent.FOLLOW_UP,
        answer=answer,
        supported=False,
        topic=topic,
        runtime_result_hash=runtime.canonical_hash,
    )
