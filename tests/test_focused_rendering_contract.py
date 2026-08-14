from __future__ import annotations

from unittest.mock import patch

import pytest

import mingli.phase23 as phase23
from mingli.phase20 import DISCLAIMER, SECTION_TITLES
from mingli.render_intent import RenderIntent, classify_render_intent
from mingli.service import analyze_mingli_payload


def chart_request(
    question: str,
    *,
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "question": question,
        "context": context or {},
        "chart_input": {
            "gender": "female",
            "calendar": "solar",
            "birth_date": "1990-03-15",
            "birth_time": "10:30",
            "timezone": "Asia/Shanghai",
            "birth_location": {"longitude": 121.47, "latitude": 31.23},
            "true_solar_time": False,
        },
        "anchor_year": 2027,
        "reality": {},
        "fusion_evidence": [],
    }


def pillar_request(question: str) -> dict[str, object]:
    return {
        "question": question,
        "gender": "female",
        "pillars": {
            "year": "庚寅",
            "month": "丙戌",
            "day": "戊午",
            "hour": "丙辰",
        },
        "context": {},
    }


@pytest.mark.parametrize(
    "question",
    [
        "她事业怎么样",
        "详细分析她的事业",
        "她适合考公吗",
        "她能进体制吗",
        "2027年她的感情如何",
        "他俩会复合吗",
        "这个命盘怎么样",
        "简单说说财运",
        "/new",
    ],
)
def test_non_full_questions_never_classify_as_full_reading(question: str) -> None:
    assert (
        classify_render_intent(question, has_active_case=False)
        is not RenderIntent.FULL_READING
    )


@pytest.mark.parametrize(
    "question",
    [
        "完整分析这个命盘",
        "全盘分析",
        "给我一份完整命盘报告",
        "按八段报告",
        "事业财运感情健康都完整看看",
    ],
)
def test_explicit_full_reading_phrases_are_the_only_full_reading_requests(
    question: str,
) -> None:
    assert (
        classify_render_intent(question, has_active_case=False)
        is RenderIntent.FULL_READING
    )


def test_classification_fails_closed_to_focused_question() -> None:
    assert (
        classify_render_intent(None, has_active_case=False)  # type: ignore[arg-type]
        is RenderIntent.FOCUSED_QUESTION
    )


@pytest.mark.parametrize(
    "question",
    [
        "她事业怎么样",
        "那2027年呢",
        "她适合考公吗",
        "他俩会复合吗",
        "两个人哪个更适合这个岗位",
        "她该不该换工作",
        "简单说说财运",
        "/new",
    ],
)
def test_non_full_service_paths_do_not_call_yuan_eight_section_renderer(
    question: str,
) -> None:
    context = {"has_active_case": True, "topic": "career"} if question == "那2027年呢" else {}
    with patch.object(
        phase23,
        "render_yuan_eight_sections",
        wraps=phase23.render_yuan_eight_sections,
    ) as yuan:
        result = analyze_mingli_payload(chart_request(question, context=context))

    assert result["render_intent"] != RenderIntent.FULL_READING.value
    assert result["sections"] == []
    assert result["full_report_generated"] is False
    assert yuan.call_count == 0


def test_full_reading_calls_yuan_once_and_returns_eight_sections() -> None:
    with patch.object(
        phase23,
        "render_yuan_eight_sections",
        wraps=phase23.render_yuan_eight_sections,
    ) as yuan:
        result = analyze_mingli_payload(chart_request("完整分析这个命盘"))

    assert result["render_intent"] == RenderIntent.FULL_READING.value
    assert result["topic"] is None
    assert result["full_report_generated"] is True
    assert len(result["sections"]) == 8
    assert yuan.call_count == 1


def test_hermes_structured_pillars_call_returns_focused_answer_without_sections() -> None:
    result = analyze_mingli_payload(pillar_request("她的事业怎么样"))

    assert result["render_intent"] == RenderIntent.FOCUSED_QUESTION.value
    assert result["topic"] == "career"
    assert result["full_report_generated"] is False
    assert result["sections"] == []
    assert result["final_answer"]
    assert result["chart"]["day_master"] == "戊"
    assert not all(title in result["final_answer"] for title in SECTION_TITLES)


def test_new_resets_without_a_runtime_or_full_report() -> None:
    with patch.object(
        phase23,
        "render_yuan_eight_sections",
        wraps=phase23.render_yuan_eight_sections,
    ) as yuan:
        result = analyze_mingli_payload(chart_request("/new"))

    assert result["conversation_reset"] is True
    assert result["render_intent"] == RenderIntent.FOCUSED_QUESTION.value
    assert result["full_report_generated"] is False
    assert result["sections"] == []
    assert yuan.call_count == 0


def test_follow_up_inherits_career_and_scopes_to_the_requested_year() -> None:
    result = analyze_mingli_payload(
        chart_request(
            "那2027年呢",
            context={"has_active_case": True, "topic": "career"},
        )
    )

    assert result["render_intent"] in {
        RenderIntent.FOLLOW_UP.value,
        RenderIntent.TIMING.value,
    }
    assert result["topic"] == "career"
    assert "2027" in result["final_answer"]
    assert "财运" not in result["final_answer"]
    assert "感情" not in result["final_answer"]
    assert result["sections"] == []


def test_civil_service_answer_keeps_fit_and_admission_separate() -> None:
    result = analyze_mingli_payload(chart_request("她适合考公吗，能不能上岸？"))
    answer = result["final_answer"]

    for label in ("体制适配度", "考试运", "岗位方向", "备考策略"):
        assert label in answer
    assert "\u4f53\u5236\u9002\u914d\u5ea6\u4e0d\u80fd\u66ff\u4ee3\u4e0a\u5cb8\u7ed3\u679c" in answer


def test_reconciliation_answer_has_all_four_independent_layers() -> None:
    result = analyze_mingli_payload(chart_request("他们还能复合吗？"))
    answer = result["final_answer"]

    for label in ("缘分牵引", "复联可能", "复合可能", "稳定可能"):
        assert label in answer



def test_missing_question_returns_one_clarification_without_runtime_or_sections() -> None:
    with patch.object(
        phase23,
        "render_yuan_eight_sections",
        wraps=phase23.render_yuan_eight_sections,
    ) as yuan:
        result = analyze_mingli_payload(pillar_request(""))

    assert result["render_intent"] == RenderIntent.FOCUSED_QUESTION.value
    assert result["topic"] is None
    assert result["sections"] == []
    assert result["full_report_generated"] is False
    assert "\u8bf7\u8bf4\u660e\u60f3\u770b\u7684\u4e3b\u9898" in result["final_answer"]
    assert yuan.call_count == 0


def test_unknown_topic_clarifies_without_reusing_a_previous_full_report() -> None:
    result = analyze_mingli_payload(chart_request("\u8fd9\u4e2a\u547d\u76d8\u600e\u4e48\u6837"))

    assert result["render_intent"] == RenderIntent.FOCUSED_QUESTION.value
    assert result["topic"] is None
    assert result["sections"] == []
    assert result["full_report_generated"] is False
    assert "\u8bf7\u8bf4\u660e\u60f3\u770b\u7684\u4e3b\u9898" in result["final_answer"]


def test_timing_path_is_scoped_and_never_calls_yuan_renderer() -> None:
    with patch.object(
        phase23,
        "render_yuan_eight_sections",
        wraps=phase23.render_yuan_eight_sections,
    ) as yuan:
        result = analyze_mingli_payload(chart_request("2027\u5e74\u5979\u7684\u611f\u60c5\u5982\u4f55"))

    assert result["render_intent"] == RenderIntent.TIMING.value
    assert result["topic"] == "relationship"
    assert "2027" in result["final_answer"]
    assert "\u4e94\u5e74\u65ad\u4e8b" not in result["final_answer"]
    assert result["sections"] == []
    assert yuan.call_count == 0


def test_health_reference_is_targeted_and_keeps_medical_reality_first() -> None:
    result = analyze_mingli_payload(chart_request("\u5979\u7684\u5065\u5eb7\u600e\u4e48\u6837"))

    assert result["render_intent"] == RenderIntent.FOCUSED_QUESTION.value
    assert result["topic"] == "health"
    assert result["sections"] == []
    assert "\u533b\u7597\u4e13\u4e1a\u610f\u89c1" in result["final_answer"]


def test_focused_answer_excludes_yuan_only_section_titles() -> None:
    result = analyze_mingli_payload(pillar_request("\u5979\u7684\u4e8b\u4e1a\u600e\u4e48\u6837"))

    for title in ("\u8d44\u6599\u786e\u8ba4", "\u79f0\u9aa8\u6b4c\u8bc0", "\u4e94\u5e74\u65ad\u4e8b"):
        assert title not in result["final_answer"]

def test_every_user_facing_answer_has_exactly_one_disclaimer() -> None:
    for request in (
        chart_request("她事业怎么样"),
        chart_request("完整分析这个命盘"),
        pillar_request("她的事业怎么样"),
        chart_request("/new"),
    ):
        result = analyze_mingli_payload(request)
        assert result["final_answer"].count(DISCLAIMER) == 1
