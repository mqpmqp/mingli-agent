"""Focused user-facing renderers controlled by the existing RenderIntent enum."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re

from .phase20 import DISCLAIMER
from .render_intent import RenderIntent
from .renderer import ensure_safe_text


def _z(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


YEAR = _z(r"\u5e74")
CAREER = _z(r"\u4e8b\u4e1a")
WEALTH = _z(r"\u8d22\u8fd0")
RELATIONSHIP = _z(r"\u611f\u60c5")
CAREER_EXAM = _z(r"\u8003\u516c\u8003\u7f16")
REUNION = _z(r"\u590d\u5408")
HEALTH = _z(r"\u5065\u5eb7\u53c2\u8003")
STUDY = _z(r"\u5b66\u4e1a")
FAMILY = _z(r"\u5bb6\u5ead")
SOCIAL = _z(r"\u4eba\u9645")
CONCLUSION = _z(r"\u7ed3\u8bba\uff1a")
CONFIDENCE = _z(r"\u7f6e\u4fe1\u5ea6\uff1a")
KEY_BASIS = _z(r"\u5173\u952e\u4f9d\u636e\uff1a")
ADVICE = _z(r"\u5efa\u8bae\uff1a")
TIME_WINDOW = _z(r"\u65f6\u95f4\u7a97\u53e3\uff1a")
FIT = _z(r"\u4f53\u5236\u9002\u914d\u5ea6")
EXAM = _z(r"\u8003\u8bd5\u8fd0")
POSITION = _z(r"\u5c97\u4f4d\u65b9\u5411")
PREPARATION = _z(r"\u5907\u8003\u7b56\u7565")
ATTRACTION = _z(r"\u7f18\u5206\u7275\u5f15")
RECONTACT = _z(r"\u590d\u8054\u53ef\u80fd")
REUNION_POSSIBLE = _z(r"\u590d\u5408\u53ef\u80fd")
STABILITY = _z(r"\u7a33\u5b9a\u53ef\u80fd")
ADMISSION = _z(r"\u4e0a\u5cb8\u5224\u65ad")
SUPPORTIVE = _z(r"\u76f8\u5bf9\u6709\u5229")
CHALLENGING = _z(r"\u9700\u8981\u66f4\u8c28\u614e")
MIXED = _z(r"\u6709\u5229\u5f0a\u5e76\u5b58")
UNRESOLVED = _z(r"\u6682\u4e0d\u4e0b\u5b9a\u8bba")
HIGH = _z(r"\u9ad8\u7f6e\u4fe1")
MEDIUM = _z(r"\u4e2d\u7f6e\u4fe1")
LOW = _z(r"\u4f4e\u7f6e\u4fe1")

_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?:\u5e74)?")
_TOPIC_RULES = (
    ("career_exam", (_z(r"\u8003\u516c"), _z(r"\u8003\u7f16"), _z(r"\u6559\u5e08\u7f16"), _z(r"\u4e8b\u4e1a\u5355\u4f4d"), _z(r"\u4f53\u5236\u5185"), _z(r"\u8fdb\u4f53\u5236"))),
    ("relationship_reunion", (_z(r"\u590d\u5408"), _z(r"\u590d\u8054"), _z(r"\u633d\u56de"))),
    ("career", (CAREER, _z(r"\u5de5\u4f5c"), _z(r"\u804c\u4e1a"), _z(r"\u5c97\u4f4d"), _z(r"\u5347\u804c"), _z(r"\u6362\u5de5\u4f5c"))),
    ("wealth", (WEALTH, _z(r"\u6536\u5165"), _z(r"\u8d22\u5bcc"), _z(r"\u8d5a\u94b1"), _z(r"\u94b1"))),
    ("relationship", (RELATIONSHIP, _z(r"\u604b\u7231"), _z(r"\u5a5a\u59fb"), _z(r"\u6843\u82b1"), _z(r"\u5173\u7cfb"))),
    ("study", (STUDY, _z(r"\u8bfb\u4e66"), _z(r"\u8003\u8bd5"), _z(r"\u5b66\u4e60"))),
    ("health", (_z(r"\u5065\u5eb7"), _z(r"\u8eab\u4f53"), _z(r"\u75be\u75c5"), _z(r"\u75c7\u72b6"))),
    ("family", (FAMILY, _z(r"\u7236\u6bcd"), _z(r"\u5b50\u5973"), _z(r"\u5bb6\u4eba"))),
    ("social", (SOCIAL, _z(r"\u670b\u53cb"), _z(r"\u540c\u4e8b"), _z(r"\u793e\u4ea4"))),
)
_TOPIC_LABELS = {"career": CAREER, "wealth": WEALTH, "relationship": RELATIONSHIP, "career_exam": CAREER_EXAM, "relationship_reunion": REUNION, "study": STUDY, "health": HEALTH, "family": FAMILY, "social": SOCIAL}
_STATUS_TEXT = {"supportive": SUPPORTIVE, "challenging": CHALLENGING, "mixed": MIXED, "unresolved": UNRESOLVED}
_CONFIDENCE_TEXT = {"high": HIGH, "medium": MEDIUM, "low": LOW}
_SCENARIO_TEXT = {"support": SUPPORTIVE, "conflict": _z(r"\u73b0\u5b9e\u6761\u4ef6\u53d7\u9650"), "conditional": _z(r"\u9700\u7ed3\u5408\u73b0\u5b9e\u6761\u4ef6"), "unresolved": _z(r"\u6682\u4e0d\u786e\u5b9a"), "not_applicable": _z(r"\u4e0d\u9002\u7528")}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def detect_topic(question: object, *, inherited_topic: object = None) -> str | None:
    normalized = _text(question)
    for topic, tokens in _TOPIC_RULES:
        if any(token in normalized for token in tokens):
            return topic
    inherited = _text(inherited_topic)
    return inherited if inherited in _TOPIC_LABELS else None


def requested_year(question: object) -> int | None:
    match = _YEAR_RE.search(_text(question))
    return int(match.group(1)) if match else None


def _explicit_full(normalized: str) -> bool:
    phrases = (
        _z(r"\u5b8c\u6574\u5206\u6790\u8fd9\u4e2a\u547d\u76d8"), _z(r"\u5b8c\u6574\u5206\u6790\u547d\u76d8"), _z(r"\u5168\u76d8\u5206\u6790"),
        _z(r"\u5168\u9762\u770b\u6574\u4e2a\u547d\u76d8"), _z(r"\u7ed9\u6211\u4e00\u4efd\u5b8c\u6574\u547d\u76d8\u62a5\u544a"),
        _z(r"\u5b8c\u6574\u547d\u76d8\u62a5\u544a"), _z(r"\u6309\u516b\u6bb5\u62a5\u544a"), _z(r"\u516b\u6bb5\u62a5\u544a"),
        _z(r"\u4ece\u6574\u4f53\u683c\u5c40\u5230\u5927\u8fd0\u6d41\u5e74\u5b8c\u6574\u5206\u6790"),
    )
    if any(phrase in normalized for phrase in phrases):
        return True
    if any(token in normalized for token in (_z(r"\u5168\u76d8"), _z(r"\u6574\u76d8"))) and any(token in normalized for token in (_z(r"\u5206\u6790"), _z(r"\u770b\u770b"), _z(r"\u62a5\u544a"), _z(r"\u89e3\u8bfb"))):
        return True
    return sum(token in normalized for token in (CAREER, WEALTH, RELATIONSHIP, _z(r"\u5065\u5eb7"))) >= 3 and any(token in normalized for token in (_z(r"\u90fd\u770b"), _z(r"\u5168\u90e8"), _z(r"\u5168\u90fd"), _z(r"\u5b8c\u6574")))


def classify_question_intent(text: object, *, has_active_case: bool, comment: bool = False) -> RenderIntent:
    normalized = _text(text)
    if normalized == "/new":
        return RenderIntent.FOCUSED_QUESTION
    if _explicit_full(normalized):
        return RenderIntent.FULL_READING
    if comment or any(token in normalized for token in (_z(r"\u7b80\u5355\u8bf4"), _z(r"\u4e00\u53e5\u8bdd"), _z(r"\u7b80\u8bc4"), _z(r"\u4e0d\u8981\u5c55\u5f00"), _z(r"\u8bc4\u8bba\u533a"))):
        return RenderIntent.COMMENT
    if has_active_case and (normalized.startswith((_z(r"\u90a3"), _z(r"\u7136\u540e"), _z(r"\u63a5\u7740"))) or any(token in normalized for token in (_z(r"\u7ee7\u7eed"), _z(r"\u518d\u770b"), _z(r"\u8fd8\u6709")))):
        return RenderIntent.FOLLOW_UP
    if requested_year(normalized) is not None or any(token in normalized for token in (_z(r"\u4ec0\u4e48\u65f6\u5019"), _z(r"\u54ea\u4e00\u5e74"), _z(r"\u672a\u6765\u51e0\u5e74"), _z(r"\u67d0\u5e74"), _z(r"\u67d0\u6708"), _z(r"\u65f6\u95f4\u7a97\u53e3"))):
        return RenderIntent.TIMING
    if any(token in normalized for token in (_z(r"\u4e24\u4e2a\u4eba"), _z(r"\u4e24\u4e2a"), _z(r"\u54ea\u4e2a\u66f4"), _z(r"\u6bd4\u8f83"), _z(r"\u5bf9\u6bd4"))):
        return RenderIntent.COMPARISON
    if any(token in normalized for token in (_z(r"\u80fd\u4e0d\u80fd"), _z(r"\u9002\u4e0d\u9002\u5408"), _z(r"\u8981\u4e0d\u8981"), _z(r"\u8be5\u4e0d\u8be5"), _z(r"\u662f\u5426\u503c\u5f97"), _z(r"\u80fd\u8fdb\u4f53\u5236"))):
        return RenderIntent.DECISION
    return RenderIntent.FOCUSED_QUESTION


def _answer(body: str) -> str:
    answer = body.replace(DISCLAIMER, "").strip() + "\n\n" + DISCLAIMER
    ensure_safe_text(answer)
    return answer


def clarification_answer() -> str:
    return _answer(_z(r"\u8bf7\u8bf4\u660e\u60f3\u770b\u7684\u4e3b\u9898\uff1a") + "、".join((CAREER, WEALTH, RELATIONSHIP, CAREER_EXAM, YEAR)) + _z(r"\u3002\u63d0\u4f9b\u51fa\u751f\u8d44\u6599\u6216\u56db\u67f1\u672c\u8eab\u4e0d\u4f1a\u81ea\u52a8\u751f\u6210\u6574\u76d8\u62a5\u544a\u3002"))


def reset_answer() -> str:
    return _answer(_z(r"\u5df2\u65b0\u5efa\u4f1a\u8bdd\u5e76\u6e05\u7a7a\u4e0a\u4e00\u8f6e\u6848\u4f8b\u4e0a\u4e0b\u6587\u3002") + clarification_answer().replace(DISCLAIMER, "").strip())


def _domain(runtime: object, topic: str) -> tuple[str, str]:
    domain = {"career_exam": "career", "relationship_reunion": "relationship"}.get(topic, topic)
    statuses = getattr(runtime, "effective_domain_statuses", {})
    confidence = getattr(runtime, "effective_domain_confidence", {})
    status = statuses.get(domain) if isinstance(statuses, Mapping) else None
    level = confidence.get(domain) if isinstance(confidence, Mapping) else None
    return (str(status) if status in _STATUS_TEXT else "unresolved", str(level) if level in _CONFIDENCE_TEXT else "low")


def _layers(runtime: object) -> dict[str, tuple[str, str]]:
    scenario = getattr(runtime, "scenario_assessment", None)
    values = scenario.get("layers") if isinstance(scenario, Mapping) else None
    result: dict[str, tuple[str, str]] = {}
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return result
    for item in values:
        if isinstance(item, Mapping) and isinstance(item.get("layer"), str):
            status, confidence = item.get("label"), item.get("confidence")
            result[str(item["layer"])] = (str(status) if status in _SCENARIO_TEXT else "unresolved", str(confidence) if confidence in _CONFIDENCE_TEXT else "low")
    return result


def _layer(label: str, value: tuple[str, str] | None) -> str:
    status, confidence = value or ("unresolved", "low")
    return f"{label}：{_SCENARIO_TEXT[status]}（{_CONFIDENCE_TEXT[confidence]}）。"


def _career_exam(runtime: object, *, static: bool = False) -> str:
    layers = _layers(runtime)
    prefix = _z(r"\u53ef\u5c06\u4f53\u5236\u9002\u914d\u4e0e\u5b9e\u9645\u62a5\u8003\u6761\u4ef6\u5206\u5f00\u8bc4\u4f30\u3002")
    if static:
        prefix = _z(r"\u53ef\u5c06\u4f53\u5236\u9002\u914d\u4e0e\u4e0a\u5cb8\u6761\u4ef6\u5206\u5f00\u770b\uff1b\u9759\u6001\u56db\u67f1\u4e0d\u66ff\u4ee3\u8d44\u683c\u3001\u6210\u7ee9\u548c\u5c97\u4f4d\u7ade\u4e89\u3002")
    return _answer("\n".join((
        CONCLUSION + prefix,
        _layer(FIT, layers.get("system_fit")), _layer(EXAM, layers.get("exam_outlook")),
        _layer(POSITION, layers.get("position_direction")), _layer(PREPARATION, layers.get("preparation_strategy")),
        ADMISSION + "：" + FIT + _z(r"\u4e0d\u80fd\u66ff\u4ee3\u4e0a\u5cb8\u7ed3\u679c\u3002"),
        ADVICE + _z(r"\u8bf7\u4f18\u5148\u6838\u5bf9\u8d44\u683c\u6761\u4ef6\u3001\u5c97\u4f4d\u7ade\u4e89\u548c\u53ef\u6267\u884c\u7684\u590d\u4e60\u8ba1\u5212\u3002"),
    )))


def _reunion(runtime: object, *, static: bool = False) -> str:
    layers = _layers(runtime)
    prefix = _z(r"\u5173\u7cfb\u662f\u5426\u6062\u590d\u8981\u5206\u5c42\u770b\uff0c\u73b0\u5b9e\u5173\u7cfb\u72b6\u6001\u4f18\u5148\u4e8e\u76d8\u9762\u8c61\u610f\u3002")
    if static:
        prefix = _z(r"\u590d\u5408\u8981\u4ee5\u73b0\u5b9e\u5173\u7cfb\u72b6\u6001\u4e3a\u5148\uff0c\u9759\u6001\u56db\u67f1\u4e0d\u66ff\u4ee3\u53cc\u65b9\u610f\u613f\u4e0e\u8fb9\u754c\u3002")
    return _answer("\n".join((
        CONCLUSION + prefix,
        _layer(ATTRACTION, layers.get("attraction")), _layer(RECONTACT, layers.get("recontact")),
        _layer(REUNION_POSSIBLE, layers.get("reunion")), _layer(STABILITY, layers.get("stability")),
        ADVICE + _z(r"\u5148\u786e\u8ba4\u53cc\u65b9\u610f\u613f\u3001\u8fb9\u754c\u4e0e\u95ee\u9898\u662f\u5426\u5df2\u88ab\u5904\u7406\u3002"),
    )))


def _timing(runtime: object, topic: str | None, year: int | None) -> str:
    label = _TOPIC_LABELS.get(topic or "", _z(r"\u5f53\u524d\u4e3b\u9898"))
    if year is None:
        return _answer(CONCLUSION + _z(r"\u8bf7\u8865\u5145\u5177\u4f53\u5e74\u4efd\u6216\u6708\u4efd\uff0c\u624d\u80fd\u9650\u5b9a\u65f6\u95f4\u7a97\u53e3\u3002"))
    five_year = getattr(runtime, "five_year", {})
    records = five_year.get("years") if isinstance(five_year, Mapping) else None
    selected = (
        next(
            (
                item
                for item in records
                if isinstance(item, Mapping) and item.get("year") == year
            ),
            None,
        )
        if isinstance(records, Sequence) and not isinstance(records, (str, bytes))
        else None
    )
    status = selected.get("status") if isinstance(selected, Mapping) else None
    confidence = selected.get("confidence") if isinstance(selected, Mapping) else None
    status = str(status) if status in _STATUS_TEXT else "unresolved"
    confidence = str(confidence) if confidence in _CONFIDENCE_TEXT else "low"
    scoped = _z(r"\u4ec5\u8986\u76d6")
    no_expand = _z(r"\uff1b\u4e0d\u81ea\u52a8\u6269\u5c55\u5230\u5176\u4ed6\u5e74\u4efd\u3002")
    advice = _z(r"\u8bf7\u6838\u5bf9\u5f53\u5e74\u73b0\u5b9e\u6761\u4ef6\u4e0e\u53ef\u6267\u884c\u8ba1\u5212\u3002")
    return _answer("\n".join((
        f"{CONCLUSION}{year}{YEAR}{label}{_STATUS_TEXT[status]}.",
        f"{CONFIDENCE}{_CONFIDENCE_TEXT[confidence]}.",
        f"{TIME_WINDOW}{scoped}{year}{YEAR}{no_expand}",
        f"{ADVICE}{advice}",
    )))

def _domain_answer(runtime: object, topic: str, intent: RenderIntent) -> str:
    status, confidence = _domain(runtime, topic)
    label = _TOPIC_LABELS[topic]
    if intent is RenderIntent.COMMENT:
        return _answer(
            _z(r"\u7b80\u8bc4\uff1a")
            + label
            + _STATUS_TEXT[status]
            + _z(r"\uff08")
            + _CONFIDENCE_TEXT[confidence]
            + _z(r"\uff09\u3002")
        )
    advice = (
        _z(r"\u8bf7\u7ed3\u5408\u73b0\u5b9e\u7ea6\u675f\u518d\u4f5c\u51b3\u5b9a\u3002")
        if intent is RenderIntent.DECISION
        else _z(r"\u5148\u6838\u5bf9\u73b0\u5b9e\u6761\u4ef6\uff0c\u518d\u5b89\u6392\u4e0b\u4e00\u6b65\u884c\u52a8\u3002")
    )
    basis_start = _z(r"\u53ea\u4f7f\u7528")
    basis_end = _z(r"\u7684\u786e\u5b9a\u6027\u9886\u57df\u89c4\u5219\u7ed3\u679c\uff0c\u4e0d\u91cd\u590d\u6574\u5f20\u547d\u76d8\u3002")
    return _answer("\n".join((
        f"{CONCLUSION}{label}{_STATUS_TEXT[status]}.",
        f"{CONFIDENCE}{_CONFIDENCE_TEXT[confidence]}.",
        f"{KEY_BASIS}{basis_start}{label}{basis_end}",
        f"{ADVICE}{advice}",
    )))

def _comparison(topic: str | None) -> str:
    label = _TOPIC_LABELS.get(topic or "", _z(r"\u8fd9\u4e2a\u9009\u62e9"))
    conclusion = _z(r"\u6bd4\u8f83") + label + _z(r"\u9700\u8981\u4e24\u4efd\u5206\u522b\u786e\u8ba4\u7684\u7ed3\u6784\u5316\u8d44\u6599\uff1b\u5f53\u524d\u8f93\u5165\u4e0d\u8db3\u4ee5\u4ee3\u66ff\u7b2c\u4e8c\u4eba\u6216\u7b2c\u4e8c\u65b9\u6848\u7684\u4fe1\u606f\u3002")
    basis = _z(r"\u53ea\u80fd\u4f7f\u7528\u5df2\u786e\u8ba4\u7684\u4e00\u4efd\u8d44\u6599\uff0c\u4e0d\u4f5c\u66ff\u4ee3\u6027\u63a8\u65ad\u3002")
    advice = _z(r"\u8bf7\u8865\u5145\u4e24\u4efd\u5404\u81ea\u786e\u8ba4\u7684\u547d\u76d8\u6216\u65b9\u6848\u4fe1\u606f\uff0c\u518d\u6309\u540c\u4e00\u7ef4\u5ea6\u6bd4\u8f83\u3002")
    return _answer("\n".join((
        CONCLUSION + conclusion,
        CONFIDENCE + LOW + ".",
        KEY_BASIS + basis,
        ADVICE + advice,
    )))


def _limited_topic_answer(runtime: object, topic: str, intent: RenderIntent) -> str:
    label = _TOPIC_LABELS[topic]
    if intent is RenderIntent.COMMENT:
        return _answer(_z(r"\u7b80\u8bc4\uff1a") + label + _z(r"\u53ef\u4f5c\u4f4e\u7f6e\u4fe1\u6587\u5316\u53c2\u8003\u3002"))
    chart = getattr(runtime, "chart", {})
    master = chart.get("day_master") if isinstance(chart, Mapping) else None
    pillars = chart.get("pillars") if isinstance(chart, Mapping) else None
    day_pillar = pillars.get("day") if isinstance(pillars, Mapping) else None
    if not master and isinstance(day_pillar, str) and day_pillar:
        master = day_pillar[0]
    basis = _z(r"\u5f53\u524d\u786e\u5b9a\u6027\u6838\u5fc3\u5c1a\u672a\u4e3a") + label + _z(r"\u5efa\u7acb\u72ec\u7acb\u9886\u57df\u89c4\u5219\uff1b\u5df2\u8ba1\u7b97\u7684\u65e5\u4e3b\u4e3a") + str(master or _z(r"\u672a\u51b3")) + _z(r"\u3002")
    if topic == "health":
        advice = _z(r"\u82e5\u6709\u75c7\u72b6\u3001\u68c0\u67e5\u6216\u7528\u836f\u95ee\u9898\uff0c\u8bf7\u4ee5\u533b\u7597\u4e13\u4e1a\u610f\u89c1\u4e3a\u51c6\u3002")
    else:
        advice = _z(r"\u8bf7\u5148\u6838\u5bf9\u5f53\u524d\u7684\u73b0\u5b9e\u6761\u4ef6\uff0c\u518d\u53d6\u7528\u53ef\u6267\u884c\u7684\u4e0b\u4e00\u6b65\u3002")
    return _answer("\n".join((
        CONCLUSION + label + _z(r"\u53ea\u63d0\u4f9b\u4f4e\u7f6e\u4fe1\u7684\u5b9a\u5411\u6587\u5316\u53c2\u8003\uff0c\u4e0d\u5c55\u5f00\u4e3a\u6574\u76d8\u62a5\u544a\u3002"),
        CONFIDENCE + LOW + ".",
        KEY_BASIS + basis,
        ADVICE + advice,
    )))


def render_phase23_focused_answer(runtime: object, intent: RenderIntent, *, question: object, topic: str | None) -> str:
    if intent is RenderIntent.FULL_READING:
        answer = getattr(runtime, "final_answer", "")
        if not isinstance(answer, str) or not answer:
            raise ValueError("full_reading requires a completed Yuan renderer result")
        return answer
    if intent is RenderIntent.COMPARISON:
        return _comparison(topic)
    if topic is None:
        return clarification_answer()
    if intent in {RenderIntent.TIMING, RenderIntent.FOLLOW_UP} and requested_year(question) is not None:
        return _timing(runtime, topic, requested_year(question))
    if topic == "career_exam":
        return _career_exam(runtime)
    if topic == "relationship_reunion":
        return _reunion(runtime)
    if topic in {"career", "wealth", "relationship"}:
        return _domain_answer(runtime, topic, intent)
    return _limited_topic_answer(runtime, topic, intent)

def _confirmed_basis(runtime: object) -> str:
    chart = getattr(runtime, "chart", {})
    master = chart.get("day_master") if isinstance(chart, Mapping) else None
    return KEY_BASIS + _z(r"\u5df2\u786e\u8ba4\u56db\u67f1\u7684\u65e5\u4e3b\u4e3a") + str(master or _z(r"\u672a\u51b3")) + _z(r"\uff1b\u672c\u6b21\u53ea\u4f7f\u7528\u9759\u6001\u547d\u5c40\u4e8b\u5b9e\u3002")


def _with_confirmed_basis(answer: str, runtime: object) -> str:
    return _answer(answer.replace(DISCLAIMER, "").strip() + "\n" + _confirmed_basis(runtime))


def render_confirmed_pillar_focused_answer(
    runtime: object,
    intent: RenderIntent,
    *,
    question: object,
    topic: str | None,
) -> str:
    if intent is RenderIntent.FULL_READING:
        return _answer(_z(r"\u5b8c\u6574\u516b\u6bb5\u62a5\u544a\u9700\u8981\u51fa\u751f\u5e74\u6708\u65e5\u65f6\u3001\u5730\u70b9\u548c\u5386\u6cd5\u4fe1\u606f\uff1b\u4ec5\u51ed\u56db\u67f1\u4e0d\u4f1a\u8865\u9020\u79f0\u9aa8\u3001\u5927\u8fd0\u6216\u6d41\u5e74\u6570\u636e\u3002"))
    if intent is RenderIntent.COMPARISON:
        return _comparison(topic)
    if topic is None:
        return clarification_answer()
    year = requested_year(question)
    if intent in {RenderIntent.TIMING, RenderIntent.FOLLOW_UP} and year is not None:
        scoped = _z(r"\u5df2\u786e\u8ba4\u56db\u67f1\u7684\u9759\u6001\u6a21\u5f0f\u65e0\u6cd5\u4ee3\u66ff\u6307\u5b9a\u5e74\u4efd\u7684\u73b0\u5b9e\u6761\u4ef6\uff1b\u672c\u6b21\u53ea\u9650\u5b9a\u5728")
        return _with_confirmed_basis(_answer(CONCLUSION + scoped + str(year) + YEAR + _z(r"\u3002")), runtime)
    if topic == "career_exam":
        return _with_confirmed_basis(_career_exam(runtime, static=True), runtime)
    if topic == "relationship_reunion":
        return _with_confirmed_basis(_reunion(runtime, static=True), runtime)
    if topic in {"career", "wealth", "relationship"}:
        static_note = _z(r"\u53ef\u505a\u9759\u6001\u7ed3\u6784\u53c2\u8003\uff0c\u4e0d\u5ef6\u4f38\u4e3a\u6574\u76d8\u62a5\u544a\u3002")
        advice = _z(r"\u5148\u6838\u5bf9\u73b0\u5b9e\u7ea6\u675f\uff0c\u518d\u91c7\u53d6\u53ef\u590d\u76d8\u7684\u5c0f\u6b65\u9aa4\u3002")
        return _with_confirmed_basis(_answer("\n".join((f"{CONCLUSION}{_TOPIC_LABELS[topic]}{static_note}", f"{CONFIDENCE}{MEDIUM}.", f"{ADVICE}{advice}"))), runtime)
    return _with_confirmed_basis(_limited_topic_answer(runtime, topic, intent), runtime)

def response_confidence(runtime: object, topic: str | None) -> str:
    if topic in {"career", "wealth", "relationship"}:
        return _domain(runtime, topic)[1]
    if topic in {"career_exam", "relationship_reunion"}:
        levels = [item[1] for item in _layers(runtime).values()]
        return "low" if "low" in levels or not levels else "medium" if "medium" in levels else "high"
    return "low"


__all__ = ["classify_question_intent", "clarification_answer", "detect_topic", "render_confirmed_pillar_focused_answer", "render_phase23_focused_answer", "requested_year", "reset_answer", "response_confidence"]
