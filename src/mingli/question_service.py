"""Stable MingLi Core question entrypoint for Hermes, HTTP, and MCP."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from .confirmed_pillar_runtime import run_confirmed_pillar_agent
from .contracts.serialization import digest
from .focused_renderer import (
    clarification_answer,
    detect_topic,
    render_confirmed_pillar_focused_answer,
    render_phase23_focused_answer,
    requested_year,
    reset_answer,
    response_confidence,
)
from .phase23 import (
    PHASE23_CALCULATION_VERSION,
    PHASE23_METHOD_ID,
    PHASE23_SCHEMA_VERSION,
    run_mingli_agent,
)
from .render_intent import RenderIntent, classify_render_intent

DEFAULT_RENDER_INTENT = RenderIntent.FOCUSED_QUESTION
FULL_READING_EXPLICIT_ONLY = True
YUAN_EIGHT_SECTIONS_DEFAULT = False


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _question(value: Mapping[str, object]) -> str:
    raw = value.get("question", "")
    return raw.strip() if isinstance(raw, str) else ""


def _context(value: Mapping[str, object]) -> Mapping[str, object]:
    raw = value.get("context", {})
    return raw if isinstance(raw, Mapping) else {}


def _presentation_response(
    *, answer: str, intent: RenderIntent, topic: str | None, reset: bool, warnings: list[str]
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": PHASE23_SCHEMA_VERSION,
        "method_id": PHASE23_METHOD_ID,
        "calculation_version": PHASE23_CALCULATION_VERSION,
        "run_id": digest({"record_type": "MingLiPresentation", "payload": {"intent": intent.value, "topic": topic, "reset": reset, "answer": answer}})[7:31],
        "stages": [],
        "chart": {},
        "artifacts": {},
        "scenario_assessment": None,
        "chenggu": {},
        "evidence_fusion": {},
        "five_year": {},
        "renderer": {"sections": [], "rendered_text": "", "full_report_generated": False},
        "final_answer": answer,
        "effective_domain_statuses": {},
        "effective_domain_confidence": {},
        "warnings": warnings,
        "prediction_validity": "not_evaluated",
        "render_intent": intent.value,
        "topic": topic,
        "sections": [],
        "full_report_generated": False,
        "confidence": "low",
        "conversation_reset": reset,
    }
    body["canonical_hash"] = digest({"record_type": "MingLiPresentation", "payload": body})
    return body


def _confirmed_input(value: Mapping[str, object]) -> dict[str, object]:
    pillars = _mapping(value.get("pillars"), "pillars")
    ordered = {name: pillars.get(name) for name in ("year", "month", "day", "hour")}
    day = ordered["day"]
    if not isinstance(day, str) or not day:
        raise ValueError("pillars.day is required")
    seed = digest({"record_type": "HermesDirectPillars", "payload": ordered})
    return {
        "pillars": ordered,
        "day_master": day[0],
        "gender": value.get("gender"),
        "source": "text_confirmed",
        "confirmation_status": "confirmed",
        "text_confirmation_id": f"hermes-direct-{seed[7:23]}",
        "trace_id": f"hermes-direct-{seed[23:39]}",
        "idempotency_key": f"hermes-direct-{seed[39:55]}",
    }


def _confirmed_response(
    value: Mapping[str, object], *, question: str, intent: RenderIntent, topic: str | None
) -> dict[str, object]:
    runtime = run_confirmed_pillar_agent(_confirmed_input(value))
    answer = render_confirmed_pillar_focused_answer(runtime, intent, question=question, topic=topic)
    return {
        "schema_version": runtime.schema_version,
        "method_id": runtime.method_id,
        "calculation_version": runtime.calculation_version,
        "run_id": runtime.canonical_hash[7:31],
        "stages": [],
        "chart": dict(runtime.chart),
        "artifacts": dict(runtime.artifacts),
        "scenario_assessment": None,
        "chenggu": {},
        "evidence_fusion": {},
        "five_year": {},
        "renderer": {"sections": [], "rendered_text": "", "full_report_generated": False},
        "final_answer": answer,
        "effective_domain_statuses": {},
        "effective_domain_confidence": {},
        "warnings": list(runtime.warnings),
        "canonical_hash": runtime.canonical_hash,
        "prediction_validity": runtime.prediction_validity,
        "render_intent": intent.value,
        "topic": topic,
        "sections": [],
        "full_report_generated": False,
        "confidence": "low" if intent is RenderIntent.TIMING else "medium",
        "conversation_reset": False,
    }


def _runtime_input(
    value: Mapping[str, object], *, intent: RenderIntent, topic: str | None, question: str
) -> dict[str, object]:
    result = {
        key: item
        for key, item in value.items()
        if key not in {"question", "context", "gender", "pillars", "render_intent"}
    }
    year = requested_year(question)
    if year is not None:
        result["anchor_year"] = year
    elif "anchor_year" not in result:
        result["anchor_year"] = date.today().year
    if topic in {"career_exam", "relationship_reunion"}:
        result["scenario"] = topic
    result["render_intent"] = intent.value
    return result


def _phase23_response(
    value: Mapping[str, object], *, question: str, context: Mapping[str, object], intent: RenderIntent, topic: str | None
) -> dict[str, object]:
    runtime = run_mingli_agent(_runtime_input(value, intent=intent, topic=topic, question=question))
    answer = render_phase23_focused_answer(runtime, intent, question=question, topic=topic)
    result = runtime.to_dict()
    runtime_sections = runtime.renderer.get("sections", [])
    generated = (
        intent is RenderIntent.FULL_READING
        and isinstance(runtime_sections, list)
        and bool(runtime_sections)
    )
    sections = runtime_sections if generated else []
    result.update({
        "final_answer": answer,
        "render_intent": intent.value,
        "topic": topic,
        "sections": list(sections) if isinstance(sections, list) else [],
        "full_report_generated": generated,
        "confidence": response_confidence(runtime, topic),
        "conversation_reset": False,
        "runtime_result_hash": runtime.canonical_hash,
        "conversation_context_used": bool(context),
    })
    return result


def analyze_question_payload(payload: object) -> dict[str, object]:
    """Run a focused question or explicitly requested full report.

    The boundary accepts existing birth-metadata payloads and the minimal
    ``question + gender + pillars + context`` Hermes structure.  It contains no
    Telegram, Vision, OCR, session, token, or image-confirmation dependency.
    """
    value = _mapping(payload, "runtime input")
    question = _question(value)
    context = _context(value)
    intent = classify_render_intent(
        question,
        has_active_case=(context.get("has_active_case") is True or context.get("previous_topic") is not None),
        comment=context.get("comment") is True,
    )
    inherited_topic = context.get("topic")
    if not isinstance(inherited_topic, str) or not inherited_topic.strip():
        inherited_topic = context.get("previous_topic")
    topic = detect_topic(question, inherited_topic=inherited_topic)
    if intent is RenderIntent.FULL_READING:
        topic = None
    if question == "/new":
        return _presentation_response(
            answer=reset_answer(), intent=DEFAULT_RENDER_INTENT, topic=None, reset=True,
            warnings=["conversation_context_reset", "no_runtime_report_generated"],
        )
    if not question:
        return _presentation_response(
            answer=clarification_answer(), intent=DEFAULT_RENDER_INTENT, topic=None, reset=False,
            warnings=["question_required_for_rendering", "no_runtime_report_generated"],
        )
    if topic is None and intent not in {RenderIntent.FULL_READING, RenderIntent.COMPARISON}:
        return _presentation_response(
            answer=clarification_answer(), intent=DEFAULT_RENDER_INTENT, topic=None, reset=False,
            warnings=["topic_required_for_rendering", "no_runtime_report_generated"],
        )
    if "pillars" in value and "chart_input" not in value:
        return _confirmed_response(value, question=question, intent=intent, topic=topic)
    return _phase23_response(value, question=question, context=context, intent=intent, topic=topic)


__all__ = [
    "DEFAULT_RENDER_INTENT", "FULL_READING_EXPLICIT_ONLY", "YUAN_EIGHT_SECTIONS_DEFAULT",
    "analyze_question_payload",
]
