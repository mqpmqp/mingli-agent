from __future__ import annotations

import json
import re

import pytest

from mingli.delivery_contracts import (
    CaseInput,
    ConfidenceProfile,
    EvidenceQuality,
    PaidTier,
    validate_case_input,
)
from mingli.paid_delivery import (
    PAID_SECTION_TITLES,
    build_confidence_profile,
    run_paid_delivery,
)
from mingli.renderer import DISCLAIMER, find_forbidden


def birth_input(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "gender": "female",
        "calendar": "solar",
        "birth_date": "1990-03-15",
        "birth_time": "10:30",
        "timezone": "Asia/Shanghai",
        "birth_location": {
            "country": "中国",
            "city": "上海",
            "longitude": 121.47,
            "latitude": 31.23,
        },
        "true_solar_time": False,
        "source": "user",
    }
    value.update(overrides)
    return value


def paid_case(
    *,
    domain: str = "career",
    question: str = "只看事业",
    render_intent: str = "focused_question",
    tier: str = "paid_699",
    birth: dict[str, object] | None = None,
    reality: dict[str, object] | None = None,
    bone_weight_requested: bool = False,
) -> dict[str, object]:
    return {
        "case_id": "synthetic:paid-delivery-v1",
        "created_at": "2026-08-29T12:00:00+08:00",
        "anchor_year": 2026,
        "paid_tier": tier,
        "question_intent": {
            "question": question,
            "domain": domain,
            "render_intent": render_intent,
            "bone_weight_requested": bone_weight_requested,
        },
        "birth": birth_input() if birth is None else birth,
        "reality_constraints": reality or {},
        "evidence_quality": "verified_reality",
        "review_checkpoint": {
            "checkpoint_id": "review:2026-10",
            "review_at": "2026-10-01T00:00:00+08:00",
            "criteria": ["核对现实进展", "复核反证"],
        },
    }


def test_unified_case_input_supports_birth_image_divination_and_reality() -> None:
    raw = paid_case(
        domain="relationship",
        question="只看复合",
        birth={
            "gender": "female",
            "source": "image_confirmed",
            "confirmation_status": "confirmed",
            "pillars": {"year": "戊辰", "month": "乙卯", "day": "壬午", "hour": "丙午"},
        },
        reality={
            "relationship_status": "single",
            "contact_status": "no_contact",
            "no_contact_months": 4,
            "other_party_status": "single",
            "family_opposition": True,
        },
    )
    raw["divination"] = {
        "line_results": [7, 8, 8, 7, 9, 6],
        "cast_at": "2026-08-29T11:30:00+08:00",
        "location": "台北",
        "target_event": "未来三个月是否恢复联系",
    }

    case = CaseInput.from_mapping(raw)
    validation = validate_case_input(case)

    assert validation.errors == ()
    assert case.paid_tier is PaidTier.PAID_699
    assert case.evidence_quality is EvidenceQuality.VERIFIED_REALITY
    assert case.birth is not None and case.birth.confirmation_status == "confirmed"
    assert case.divination is not None and case.divination.line_results == (7, 8, 8, 7, 9, 6)
    assert case.reality.facts["family_opposition"] is True
    assert "liuyao_engine_unavailable" in validation.degradation_reasons


def test_missing_birth_fields_degrade_instead_of_fabricating() -> None:
    case = CaseInput.from_mapping(
        paid_case(birth={"gender": "female", "calendar": "solar", "birth_date": "1990-03-15"})
    )

    validation = validate_case_input(case)

    assert validation.degraded is True
    assert "birth.birth_time" in validation.missing_fields
    assert "birth_metadata_incomplete" in validation.degradation_reasons


def test_unconfirmed_image_chart_is_low_confidence_and_not_precise() -> None:
    raw = paid_case(
        birth={
            "gender": "female",
            "source": "image_confirmed",
            "confirmation_status": "pending",
            "pillars": {"year": "戊辰", "month": "乙卯", "day": "壬午", "hour": "丙午"},
        }
    )

    result = run_paid_delivery(raw)

    assert result.confidence.chart_confidence == "low"
    assert result.runtime.status == "degraded"
    assert "图片四柱尚未确认" in result.rendered_text
    assert "精确时间" not in result.rendered_text


def test_confidence_profile_has_four_independent_dimensions() -> None:
    high = build_confidence_profile(
        input_reliable=True,
        algorithm_deterministic=True,
        rule_statuses=("production",),
        evidence_chain=("chart:deterministic", "reality:verified"),
        strong_reality_counterevidence=False,
        external_variables=False,
        event_data_complete=True,
        action_prerequisites_met=True,
    )
    medium = build_confidence_profile(
        input_reliable=True,
        algorithm_deterministic=True,
        rule_statuses=("production",),
        evidence_chain=("chart:deterministic",),
        strong_reality_counterevidence=False,
        external_variables=True,
        event_data_complete=True,
        action_prerequisites_met=True,
    )
    low = build_confidence_profile(
        input_reliable=False,
        algorithm_deterministic=False,
        rule_statuses=("draft",),
        evidence_chain=(),
        strong_reality_counterevidence=True,
        external_variables=True,
        event_data_complete=False,
        action_prerequisites_met=False,
    )

    assert high == ConfidenceProfile("high", "high", "high", "high", high.reasons)
    assert medium.interpretation_confidence == "medium"
    assert medium.event_confidence == "medium"
    assert low.chart_confidence == "low"
    assert low.interpretation_confidence == "low"
    assert low.event_confidence == "low"
    assert low.action_confidence == "low"
    assert not re.search(r"\d+(?:\.\d+)?%", json.dumps(high.to_dict(), ensure_ascii=False))


def test_paid_699_is_focused_nine_part_contract_without_fixed_eight_or_bone_weight() -> None:
    result = run_paid_delivery(paid_case())

    assert result.render_intent == "focused_question"
    assert tuple(section.title for section in result.sections) == PAID_SECTION_TITLES
    assert len(result.sections) == 9
    assert "事业" in result.rendered_text
    assert "感情主题深断" not in result.rendered_text
    assert "八段" not in result.rendered_text
    for token in ("称骨", "骨重", "称骨歌诀"):
        assert token not in result.rendered_text
        assert token not in json.dumps(result.to_dict(), ensure_ascii=False)


def test_explicit_bone_weight_request_is_the_only_opt_in_path() -> None:
    result = run_paid_delivery(paid_case(bone_weight_requested=True))

    assert "骨重" in result.rendered_text
    assert result.optional_modules == ("bone_weight",)


def test_follow_up_stays_focused_and_does_not_repeat_full_paid_report() -> None:
    result = run_paid_delivery(
        paid_case(
            domain="relationship",
            question="继续看复合后的稳定性",
            render_intent="follow_up",
            reality={"contact_status": "active", "both_willing": True},
        )
    )

    titles = tuple(section.title for section in result.sections)
    assert result.render_intent == "follow_up"
    assert len(titles) < len(PAID_SECTION_TITLES)
    assert "资料确认" not in titles
    assert "复盘" in result.rendered_text
    assert "财运" not in result.rendered_text


@pytest.mark.parametrize(
    ("domain", "question", "expected_labels"),
    [
        (
            "relationship",
            "只看复合",
            ("缘分牵引", "复联可能", "复合可能", "稳定可能"),
        ),
        (
            "civil_service_and_public_institution",
            "只看考公考编",
            ("体制适配度", "上岸可能", "考试运", "岗位方向", "备考策略", "文昌与功名辅助"),
        ),
    ],
)
def test_special_paid_topics_cover_required_independent_layers(
    domain: str,
    question: str,
    expected_labels: tuple[str, ...],
) -> None:
    result = run_paid_delivery(paid_case(domain=domain, question=question))
    deep = next(section.content for section in result.sections if section.title == "当前主题深断")

    for label in expected_labels:
        assert label in deep


def test_reality_counterevidence_has_priority_over_symbolic_interpretation() -> None:
    result = run_paid_delivery(
        paid_case(
            domain="relationship",
            question="只看复合",
            reality={
                "other_party_status": "married",
                "contact_status": "blocked",
                "no_contact_months": 18,
            },
        )
    )

    assert result.confidence.event_confidence == "low"
    assert "现实边界优先" in result.rendered_text
    assert "对方已婚" in result.rendered_text
    assert "成立条件" in result.rendered_text
    assert "反证" in result.rendered_text


def test_paid_output_has_conditions_counterevidence_review_point_and_safe_language() -> None:
    result = run_paid_delivery(paid_case())

    assert "成立条件" in result.rendered_text
    assert "反证" in result.rendered_text
    assert "复盘点" in result.rendered_text
    assert result.rendered_text.count(DISCLAIMER) == 1
    assert result.rendered_text.endswith(DISCLAIMER)
    assert find_forbidden(result.rendered_text) == ()
    assert not re.search(r"\d+(?:\.\d+)?%", result.rendered_text)


def test_same_input_has_deterministic_golden_contract() -> None:
    raw = paid_case(birth={"gender": "female", "calendar": "solar", "birth_date": "1990-03-15"})

    left = run_paid_delivery(raw)
    right = run_paid_delivery(json.loads(json.dumps(raw)))

    assert left.to_dict() == right.to_dict()
    assert left.canonical_hash.startswith("sha256:")
    assert tuple(section.title for section in left.sections) == PAID_SECTION_TITLES
    assert left.confidence.to_dict() == {
        "chart_confidence": "low",
        "interpretation_confidence": "low",
        "event_confidence": "low",
        "action_confidence": "low",
        "reasons": list(left.confidence.reasons),
    }
