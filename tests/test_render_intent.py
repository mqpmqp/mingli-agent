from __future__ import annotations

from mingli.confirmed_pillar_runtime import run_confirmed_pillar_agent
from mingli.phase23 import run_mingli_agent
from mingli.render_intent import (
    RenderIntent,
    classify_render_intent,
    render_confirmed_pillar_follow_up,
    render_phase23_intent,
)


def phase23_request() -> dict[str, object]:
    return {
        "chart_input": {
            "gender": "male",
            "calendar": "solar",
            "birth_date": "1990-03-15",
            "birth_time": "10:30",
            "timezone": "Asia/Shanghai",
            "birth_location": {"longitude": 121.47, "latitude": 31.23},
            "true_solar_time": False,
        },
        "anchor_year": 2026,
        "reality": {},
        "fusion_evidence": [],
        "render_intent": "full_reading",
    }


def confirmed_request() -> dict[str, object]:
    return {
        "pillars": {
            "year": "戊辰",
            "month": "乙卯",
            "day": "壬午",
            "hour": "丙午",
        },
        "day_master": "壬",
        "gender": "female",
        "source": "image_confirmed",
        "confirmation_status": "confirmed",
        "trace_id": "trace-render-intent",
        "idempotency_key": "image-render-intent",
    }


def test_selection_rules_are_explicit_and_state_aware() -> None:
    assert classify_render_intent("请完整分析命盘", has_active_case=False) is RenderIntent.FULL_READING
    assert classify_render_intent("只看财运", has_active_case=False) is RenderIntent.FOCUSED_QUESTION
    assert classify_render_intent("继续看感情", has_active_case=True) is RenderIntent.FOLLOW_UP
    assert classify_render_intent("评论区回复：事业怎么样", has_active_case=False) is RenderIntent.COMMENT


def test_full_reading_preserves_existing_yuan_answer() -> None:
    runtime = run_mingli_agent(phase23_request())

    rendered = render_phase23_intent(
        runtime,
        RenderIntent.FULL_READING,
        question="完整分析",
    )

    assert rendered.answer == runtime.final_answer
    assert rendered.intent is RenderIntent.FULL_READING
    assert rendered.supported is True
    assert rendered.answer.count("仅供文化研究与娱乐参考。") == 1


def test_focused_and_follow_up_use_only_the_requested_topic() -> None:
    runtime = run_mingli_agent(phase23_request())

    focused = render_phase23_intent(
        runtime,
        RenderIntent.FOCUSED_QUESTION,
        question="只看财运",
    )
    follow_up = render_phase23_intent(
        runtime,
        RenderIntent.FOLLOW_UP,
        question="继续看感情",
    )

    assert focused.supported is True
    assert "财运" in focused.answer
    assert "五年" not in focused.answer
    assert "感情" not in focused.answer
    assert follow_up.supported is True
    assert "感情" in follow_up.answer
    assert "五年" not in follow_up.answer
    assert "财运" not in follow_up.answer
    assert focused.answer.count("仅供文化研究与娱乐参考。") == 1
    assert follow_up.answer.count("仅供文化研究与娱乐参考。") == 1


def test_special_scenario_uses_user_facing_labels_only() -> None:
    request = phase23_request()
    request["scenario"] = "career_exam"
    runtime = run_mingli_agent(request)

    rendered = render_phase23_intent(
        runtime,
        RenderIntent.FOCUSED_QUESTION,
        question="只看考公",
    )

    assert rendered.supported is True
    assert "体制适配度" in rendered.answer
    assert "system_fit" not in rendered.answer
    assert "admission_outlook" not in rendered.answer


def test_unsupported_topic_fails_closed_without_generic_conclusion() -> None:
    runtime = run_mingli_agent(phase23_request())

    rendered = render_phase23_intent(
        runtime,
        RenderIntent.FOLLOW_UP,
        question="继续看出国留学",
    )

    assert rendered.supported is False
    assert "请说明想看的主题" in rendered.answer
    assert "五年" not in rendered.answer
    assert rendered.answer.count("仅供文化研究与娱乐参考。") == 1


def test_confirmed_pillar_follow_up_is_an_official_limited_runtime() -> None:
    confirmed = run_confirmed_pillar_agent(confirmed_request())

    rendered = render_confirmed_pillar_follow_up(confirmed, "继续看财运")

    assert rendered.intent is RenderIntent.FOLLOW_UP
    assert rendered.supported is True
    assert "财运" in rendered.answer
    assert "出生日期" not in rendered.answer
    assert rendered.answer.count("仅供文化研究与娱乐参考。") == 1
