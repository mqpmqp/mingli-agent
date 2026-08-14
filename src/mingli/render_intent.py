"""Formal render-intent adapter for MingLi Core answer selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .confirmed_pillar_runtime import ConfirmedPillarRuntimeResult
from .phase23 import MingLiRuntimeResult


class RenderIntent(str, Enum):
    FULL_READING = "full_reading"
    FOCUSED_QUESTION = "focused_question"
    FOLLOW_UP = "follow_up"
    TIMING = "timing"
    COMPARISON = "comparison"
    DECISION = "decision"
    COMMENT = "comment"


@dataclass(frozen=True)
class RenderIntentResult:
    intent: RenderIntent
    answer: str
    supported: bool
    topic: str | None
    runtime_result_hash: str


def classify_render_intent(
    text: object,
    *,
    has_active_case: bool,
    comment: bool = False,
) -> RenderIntent:
    """Select an answer shape without changing deterministic calculation."""
    normalized = text.strip() if isinstance(text, str) else ""
    from .focused_renderer import classify_question_intent

    return classify_question_intent(
        normalized,
        has_active_case=has_active_case,
        comment=comment,
    )


def render_phase23_intent(
    runtime: MingLiRuntimeResult,
    intent: RenderIntent,
    *,
    question: str,
) -> RenderIntentResult:
    """Compatibility adapter using the same focused renderer as the service."""
    from .focused_renderer import detect_topic, render_phase23_focused_answer

    topic = None if intent is RenderIntent.FULL_READING else detect_topic(question)
    answer = render_phase23_focused_answer(
        runtime,
        intent,
        question=question,
        topic=topic,
    )
    return RenderIntentResult(
        intent=intent,
        answer=answer,
        supported=intent is RenderIntent.FULL_READING or topic is not None,
        topic=topic,
        runtime_result_hash=runtime.canonical_hash,
    )


def render_confirmed_pillar_follow_up(
    runtime: ConfirmedPillarRuntimeResult,
    question: str,
) -> RenderIntentResult:
    """Compatibility adapter for a confirmed-pillar follow-up."""
    from .focused_renderer import detect_topic, render_confirmed_pillar_focused_answer

    topic = detect_topic(question)
    answer = render_confirmed_pillar_focused_answer(
        runtime,
        RenderIntent.FOLLOW_UP,
        question=question,
        topic=topic,
    )
    return RenderIntentResult(
        intent=RenderIntent.FOLLOW_UP,
        answer=answer,
        supported=topic is not None,
        topic=topic,
        runtime_result_hash=runtime.canonical_hash,
    )


__all__ = [
    "RenderIntent",
    "RenderIntentResult",
    "classify_render_intent",
    "render_confirmed_pillar_follow_up",
    "render_phase23_intent",
]
