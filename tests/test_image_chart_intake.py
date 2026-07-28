from __future__ import annotations

import inspect

import pytest

from mingli.intake.image_chart import (
    HEAVENLY_STEMS,
    VALID_GANZHI,
    ImageChartIntakeRequest,
    confirm_image_chart_candidate,
    intake_image_chart,
)
from mingli.confirmed_pillar_runtime import run_confirmed_pillar_agent
from mingli.derived.static_engine import SEXAGENARY
from mingli.phase23 import run_mingli_agent


VALID_TEXT = "性别：女 年柱：甲子 月柱：丙寅 日柱：乙亥 时柱：庚辰 日主：乙木"


def provider_field(
    value: str,
    *,
    confidence: str = "high",
    source: str = "visible",
    warning: str = "",
) -> dict[str, str]:
    return {
        "value": value,
        "confidence": confidence,
        "source": source,
        "warning": warning,
    }


def provider_result() -> dict[str, object]:
    return {
        "success": True,
        "candidates": {
            "year_pillar": provider_field("甲子"),
            "month_pillar": provider_field("乙丑"),
            "day_pillar": provider_field("丙寅"),
            "hour_pillar": provider_field("丁卯"),
            "day_master": provider_field("丙"),
        },
    }


def test_telegram_compatibility_exports_match_static_contract() -> None:
    assert HEAVENLY_STEMS == frozenset("甲乙丙丁戊己庚辛壬癸")
    assert VALID_GANZHI == frozenset(SEXAGENARY)


def test_provider_result_is_accepted_only_after_strict_candidate_validation() -> None:
    result = intake_image_chart(
        ImageChartIntakeRequest(source="telegram", provider_result=provider_result())
    )

    assert result.accepted is True
    assert result.candidate is not None
    assert result.candidate.pillars == {
        "year_pillar": "甲子",
        "month_pillar": "乙丑",
        "day_pillar": "丙寅",
        "hour_pillar": "丁卯",
    }
    assert result.candidate.display_lines() == (
        "年柱：甲子",
        "月柱：乙丑",
        "日柱：丙寅",
        "时柱：丁卯",
        "日主：丙",
    )


@pytest.mark.parametrize(
    ("field", "attribute", "value"),
    [
        ("hour_pillar", "missing", None),
        ("year_pillar", "confidence", "low"),
        ("year_pillar", "source", "inferred"),
        ("year_pillar", "warning", "blurred"),
        ("year_pillar", "value", "甲丑"),
        ("day_master", "value", "丁"),
    ],
)
def test_untrusted_provider_candidates_are_rejected(
    field: str,
    attribute: str,
    value: str | None,
) -> None:
    payload = provider_result()
    candidates = payload["candidates"]
    assert isinstance(candidates, dict)
    if attribute == "missing":
        candidates.pop(field)
    else:
        candidate_field = candidates[field]
        assert isinstance(candidate_field, dict)
        candidate_field[attribute] = value

    result = intake_image_chart(
        ImageChartIntakeRequest(source="telegram", provider_result=payload)
    )

    assert result.accepted is False
    assert result.candidate is None
    assert result.runtime_request is None


def test_one_analysis_wrapper_is_supported_but_nested_wrapper_is_rejected() -> None:
    once = {"success": True, "analysis": provider_result()}
    twice = {"success": True, "analysis": once}

    accepted = intake_image_chart(
        ImageChartIntakeRequest(source="telegram", provider_result=once)
    )
    rejected = intake_image_chart(
        ImageChartIntakeRequest(source="telegram", provider_result=twice)
    )

    assert accepted.accepted is True
    assert rejected.accepted is False


def test_public_intake_and_runtime_signatures_remain_compatible() -> None:
    assert tuple(inspect.signature(intake_image_chart).parameters) == ("request",)
    assert tuple(inspect.signature(confirm_image_chart_candidate).parameters) == (
        "candidate",
        "reply",
        "reality_context",
    )
    assert tuple(inspect.signature(run_mingli_agent).parameters) == ("raw",)
    assert tuple(inspect.signature(run_confirmed_pillar_agent).parameters) == ("raw",)


def test_valid_extracted_text_requires_confirmation_without_runtime_request() -> None:
    result = intake_image_chart(ImageChartIntakeRequest(source="test", ocr_text=VALID_TEXT))
    assert result.status == "candidate_requires_confirmation"
    assert result.candidate is not None
    assert result.candidate.pillars == {"year": "甲子", "month": "丙寅", "day": "乙亥", "hour": "庚辰"}
    assert result.candidate.gender == "female"
    assert result.runtime_request is None


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("元女", "female"),
        ("女命", "female"),
        ("坤造", "female"),
        ("元男", "male"),
        ("男命", "male"),
        ("乾造", "male"),
    ],
)
def test_chart_gender_labels_are_normalized(label: str, expected: str) -> None:
    result = intake_image_chart(
        ImageChartIntakeRequest(
            source="test",
            ocr_text=f"年柱：甲子 月柱：丙寅 日柱：乙亥 时柱：庚辰 {label}",
        )
    )

    assert result.status == "candidate_requires_confirmation"
    assert result.candidate is not None
    assert result.candidate.gender == expected
    expected_label = "女" if expected == "female" else "男"
    assert f"性别：{expected_label}" in result.user_message


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("女主", "female"),
        ("男主", "male"),
    ],
)
def test_primary_gender_labels_are_normalized_from_visible_chart_text(
    label: str, expected: str
) -> None:
    result = intake_image_chart(
        ImageChartIntakeRequest(
            source="test",
            ocr_text=f"年柱：乙酉 月柱：癸未 日柱：壬子 时柱：甲辰 日主：壬 {label}",
        )
    )

    assert result.status == "candidate_requires_confirmation"
    assert result.candidate is not None
    assert result.candidate.gender == expected


def test_unknown_optional_provider_gender_keeps_complete_candidate() -> None:
    payload = provider_result()
    payload["candidates"]["gender"] = {  # type: ignore[index]
        "value": "未标注",
        "confidence": "high",
        "source": "visible",
        "warning": "",
    }

    result = intake_image_chart(
        ImageChartIntakeRequest(source="telegram", provider_result=payload)
    )

    assert result.status == "candidate_requires_confirmation"
    assert result.accepted is True
    assert result.candidate is not None
    assert result.candidate.gender is None
    assert result.candidate.warnings == ("unsupported_gender_label",)


def test_confirmation_returns_handoff_but_never_calls_runtime() -> None:
    candidate = intake_image_chart(ImageChartIntakeRequest(source="test", ocr_text=VALID_TEXT)).candidate
    assert candidate is not None
    result = confirm_image_chart_candidate(candidate, "确认", reality_context={"image_confirmed": True})
    assert result.status == "confirmed_runtime_ready"
    assert result.runtime_request is not None
    assert result.runtime_request["confirmation_status"] == "confirmed"
    assert result.runtime_request["runtime_dispatch"] == "confirmed_pillars"
    assert result.runtime_request["contract"] == "mingli-image-chart-confirmation@1.2"
    chart_candidate = result.runtime_request["chart_candidate"]
    assert list(chart_candidate["pillars"]) == ["year", "month", "day", "hour"]
    assert chart_candidate["day_master"] == chart_candidate["pillars"]["day"][0]
    assert chart_candidate["requires_confirmation"] is False
    assert chart_candidate["confidence"] == "high"
    assert chart_candidate["warnings"] == ()
    assert chart_candidate["gender"] == "female"
    for field in ("birth_datetime", "birth_place", "calendar_type"):
        assert chart_candidate[field] is None


def test_correction_updates_candidate_and_requires_new_confirmation() -> None:
    candidate = intake_image_chart(ImageChartIntakeRequest(source="test", ocr_text=VALID_TEXT)).candidate
    assert candidate is not None
    result = confirm_image_chart_candidate(candidate, "日柱是丁酉 日主为丁火")
    assert result.status == "candidate_requires_confirmation"
    assert result.candidate is not None
    assert result.candidate.pillars["day"] == "丁酉"
    assert result.candidate.day_master == "丁"
    assert result.candidate.gender == "female"
    assert result.runtime_request is None


def test_gender_correction_is_explicit_and_requires_new_confirmation() -> None:
    candidate = intake_image_chart(
        ImageChartIntakeRequest(
            source="test",
            ocr_text=VALID_TEXT.replace("性别：女 ", ""),
        )
    ).candidate
    assert candidate is not None
    assert candidate.gender is None

    result = confirm_image_chart_candidate(candidate, "性别：男")

    assert result.status == "candidate_requires_confirmation"
    assert result.candidate is not None
    assert result.candidate.gender == "male"
    assert result.runtime_request is None


@pytest.mark.parametrize(
    "correction",
    (
        "日柱：乙孩",
        "时柱：甲X",
        "年柱：甲丑",
        "日柱：丁酉 日主：乙",
    ),
)
def test_invalid_correction_never_reenters_confirmation(
    correction: str,
) -> None:
    candidate = intake_image_chart(
        ImageChartIntakeRequest(source="test", ocr_text=VALID_TEXT)
    ).candidate
    assert candidate is not None
    result = confirm_image_chart_candidate(candidate, correction)
    assert result.status == "invalid_chart"
    assert result.runtime_request is None
    assert result.candidate == candidate


def test_invalid_or_non_chart_text_is_rejected() -> None:
    invalid = intake_image_chart(ImageChartIntakeRequest(source="test", ocr_text="年柱：乙孑 月柱：丙寅 日柱：乙亥 时柱：庚辰"))
    assert invalid.status in {"not_a_chart", "low_confidence"}
    invalid_cycle = intake_image_chart(
        ImageChartIntakeRequest(
            source="test",
            ocr_text=VALID_TEXT.replace("年柱：甲子", "年柱：甲丑"),
        )
    )
    assert invalid_cycle.status != "candidate_requires_confirmation"
    assert invalid_cycle.runtime_request is None
    non_chart = intake_image_chart(ImageChartIntakeRequest(source="test", ocr_text="今天下雨，晚饭吃什么？"))
    assert non_chart.status == "not_a_chart"


def test_missing_provider_and_messages_do_not_echo_ocr_or_birth_data() -> None:
    raw = "年柱：甲子 月柱：丙寅 日柱：乙亥 时柱：庚辰 出生：1990-03-15 10:30"
    missing = intake_image_chart(ImageChartIntakeRequest(source="telegram", image_ref="telegram:file:opaque"))
    parsed = intake_image_chart(ImageChartIntakeRequest(source="test", ocr_text=raw))
    assert missing.status == "provider_missing"
    assert missing.user_message == (
        "图片命盘识别暂不可用。请手动输入四柱或完整出生资料；"
        "如果是从图片读出的四柱，请先确认：请确认我读的四柱和日主是否正确？"
    )
    assert raw not in missing.user_message
    assert "1990-03-15" not in parsed.user_message
