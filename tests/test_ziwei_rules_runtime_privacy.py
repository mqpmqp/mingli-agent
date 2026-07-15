from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator, ValidationError

from mingli.contracts import get_schema
from mingli.phase20 import DISCLAIMER
from mingli.ziwei import build_ziwei_chart
from mingli.ziwei_benchmark import summarize_ziwei_cases
from mingli.ziwei_rules import (
    ZiweiRuleError,
    build_rule_coverage,
    evaluate_ziwei_rules,
    validate_rule_card,
)
from mingli.ziwei_runtime import run_ziwei_runtime


def chart() -> dict[str, object]:
    return build_ziwei_chart(
        {
            "calendar_type": "solar",
            "birth_date": "2000-01-07",
            "birth_time": "12:00",
            "timezone": "Asia/Shanghai",
            "longitude": 121.4737,
            "latitude": 31.2304,
            "solar_time_mode": "civil",
            "late_zi_policy": "midnight",
            "gender": "male",
        }
    )


def rule(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "rule_id": "ziwei:test:1",
        "domain": "career",
        "trigger": {"fact": "verified_signal", "equals": True},
        "required_facts": ["verified_signal"],
        "exclusions": [{"fact": "blocked", "equals": True}],
        "priority": 50,
        "confidence": "low",
        "deterministic_or_inferential": "inferential",
        "traditional_claim": "仓库内已审核来源所支持的条件性倾向。",
        "plain_language": "现有证据只支持低置信趋势，应结合现实条件。",
        "evidence_refs": ["source:test:reviewed"],
        "source_level": "reviewed_repository_source",
        "lifecycle": "active",
        "conflict_policy": "higher_priority_then_unresolved",
        "output_constraints": ["no_absolute_claims", "reality_override"],
        "direction": "support",
    }
    value.update(overrides)
    return value


def test_rule_contract_requires_provenance_and_rejects_strong_low_confidence_language() -> None:
    assert validate_rule_card(rule())["rule_id"] == "ziwei:test:1"
    with pytest.raises(ZiweiRuleError, match="evidence_refs"):
        validate_rule_card(rule(evidence_refs=[]))
    with pytest.raises(ZiweiRuleError, match="absolute"):
        validate_rule_card(rule(plain_language="一定会成功"))


def test_rule_required_facts_exclusions_priority_and_conflicts_are_stable() -> None:
    low = rule(rule_id="low", priority=10)
    high = rule(rule_id="high", priority=90)
    assert evaluate_ziwei_rules({}, [low]) == ()
    assert evaluate_ziwei_rules({"verified_signal": True, "blocked": True}, [low]) == ()
    matches = evaluate_ziwei_rules({"verified_signal": True}, [low, high])
    assert [item.rule_id for item in matches] == ["high", "low"]

    conflict = evaluate_ziwei_rules(
        {"verified_signal": True},
        [high, rule(rule_id="opposite", priority=90, direction="contradict")],
    )
    assert all(item.resolution == "unresolved_conflict" for item in conflict[:2])


def test_rule_coverage_is_honest_instead_of_filling_unverified_content() -> None:
    coverage = build_rule_coverage([])
    assert len(coverage["primary_stars"]) == 14
    assert len(coverage["palaces"]) == 12
    assert coverage["star_palace_total"] == 168
    assert coverage["star_palace_implemented"] == 0
    assert coverage["release_gate"] == "NO-GO"
    assert set(coverage["primary_stars"].values()) == {"research_required"}


def test_runtime_preserves_reality_hard_override_and_yuan_contract() -> None:
    result = run_ziwei_runtime(
        chart(),
        facts={"verified_signal": True},
        rules=[rule()],
        reality={"job_requirements_met": False},
        reality_evidence=[
            {
                "evidence_id": "reality:career",
                "claim_id": "ziwei:test:1",
                "scope": "career",
                "source_type": "reality",
                "source_id": "user-confirmed",
                "direction": "contradict",
                "weight": 0,
                "priority": 100,
                "verified": True,
                "detail_code": "requirements_not_met",
            }
        ],
        start_year=2028,
    )

    claim = result["evidence_fusion"]["claims"][0]
    assert claim["status"] == "resolved_by_reality_override"
    assert claim["hard_override_direction"] == "contradict"
    assert len(result["yuan"]["sections"]) == 8
    assert result["yuan"]["rendered_text"].count(DISCLAIMER) == 1
    assert result["yuan"]["rendered_text"].endswith(DISCLAIMER)
    assert result["deterministic"]["calculation_status"] == "partial"
    assert result["inference"]["confidence_gate"] == "low_only"
    assert "internal_reasoning" not in result


def test_anonymous_case_schema_requires_consent_and_withdrawal_state() -> None:
    schema = get_schema("ziwei_anonymous_case.schema.json")
    valid = {
        "case_id": "anonymous:001",
        "chart_fingerprint": "sha256:" + "a" * 64,
        "consent": {
            "consent_for_storage": True,
            "consent_for_model_improvement": False,
            "consent_for_public_case": False,
            "anonymization_status": "anonymized",
            "retention_policy": "delete_on_withdrawal",
            "withdrawal_status": "not_requested",
        },
        "event_timeline": [],
        "assessments": [],
        "reviewer_notes": [],
        "confidence_calibration": "not_evaluated",
    }
    Draft202012Validator(schema).validate(valid)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate({**valid, "consent": {}})


def test_benchmark_framework_does_not_invent_cases_or_count_withdrawn_data() -> None:
    empty = summarize_ziwei_cases([])
    assert empty["total_cases"] == 0
    assert empty["accuracy_rate"] is None

    withdrawn = {
        "case_id": "anonymous:withdrawn",
        "chart_fingerprint": "sha256:" + "b" * 64,
        "consent": {
            "consent_for_storage": False,
            "consent_for_model_improvement": False,
            "consent_for_public_case": False,
            "anonymization_status": "anonymized",
            "retention_policy": "delete_on_withdrawal",
            "withdrawal_status": "deleted",
        },
        "event_timeline": [],
        "assessments": [{"classification": "hit"}],
        "reviewer_notes": [],
        "confidence_calibration": "not_evaluated",
    }
    result = summarize_ziwei_cases([withdrawn])
    assert result["eligible_cases"] == 0
    assert result["excluded_withdrawn_or_unconsented"] == 1
    assert result["classifications"]["hit"] == 0
