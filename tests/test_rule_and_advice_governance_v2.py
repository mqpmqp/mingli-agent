from __future__ import annotations

from dataclasses import replace

import pytest

from mingli.rule_governance import (
    RULE_DOMAINS,
    RULE_LIFECYCLE_STATUSES,
    RuleGovernanceError,
    load_advice_rules,
    load_domain_rules,
    match_advice,
    production_rules,
    validate_rule_catalogs,
)


def test_rule_statuses_are_the_fixed_six_state_lifecycle() -> None:
    assert RULE_LIFECYCLE_STATUSES == (
        "raw",
        "draft",
        "reviewed",
        "production",
        "rejected",
        "pending_forward_test",
    )


def test_nine_domain_rule_packs_have_source_scope_counterexample_and_review() -> None:
    rules = load_domain_rules()

    assert {rule.domain for rule in rules} == set(RULE_DOMAINS)
    assert all(rule.source_refs for rule in rules)
    assert all(rule.applicability for rule in rules)
    assert all(rule.counterexamples for rule in rules)
    assert all(rule.review.reviewer and rule.review.reviewed_at and rule.review.decision_id for rule in rules)
    assert validate_rule_catalogs() == ()


def test_only_production_rules_can_enter_paid_runtime() -> None:
    source = load_domain_rules()
    draft = replace(source[0], rule_id="test:draft", status="draft")
    pending = replace(source[0], rule_id="test:pending", status="pending_forward_test")

    selected = production_rules((*source, draft, pending))

    assert selected
    assert all(rule.status == "production" for rule in selected)
    assert {rule.rule_id for rule in selected}.isdisjoint({"test:draft", "test:pending"})


def test_unknown_rule_status_fails_closed() -> None:
    rule = load_domain_rules()[0]
    with pytest.raises(RuleGovernanceError, match="unknown rule status"):
        production_rules((replace(rule, status="verified"),))


def test_advice_rules_implement_the_full_structured_contract() -> None:
    required = {
        "advice_id",
        "domain",
        "triggers",
        "contraindications",
        "required_inputs",
        "metaphysical_rationale",
        "real_world_problem",
        "recommended_action",
        "execution_steps",
        "frequency_cap",
        "budget_cap",
        "required_real_world_actions",
        "prohibited_claims",
        "scam_red_flags",
        "evidence_status",
    }
    rules = load_advice_rules()

    assert {rule.domain for rule in rules} == set(RULE_DOMAINS)
    for rule in rules:
        assert required <= set(rule.to_dict())
        assert rule.source_refs and rule.applicability and rule.counterexamples
        assert rule.review.reviewer and rule.status == "production"


@pytest.mark.parametrize("domain", RULE_DOMAINS)
def test_every_paid_domain_has_deterministic_advice_matching(domain: str) -> None:
    matches = match_advice(domain, {})

    assert matches
    assert all(rule.domain == domain and rule.status == "production" for rule in matches)


def test_finance_advice_does_not_default_everyone_to_wealth_ritual() -> None:
    ordinary = match_advice("finance", {})
    constrained = match_advice(
        "finance",
        {"cashflow_status": "critical", "borrowing_for_ritual": True},
    )

    assert all("补财库" not in rule.recommended_action for rule in ordinary)
    assert any("当前不建议具体仪式" in rule.recommended_action for rule in constrained)
    assert all("借钱" in " ".join(rule.scam_red_flags) for rule in constrained)


def test_health_and_fengshui_advice_are_fail_closed() -> None:
    health = match_advice("health", {"symptoms": ["持续胸痛"]})[0]
    fengshui = match_advice("fengshui", {})[0]

    assert "医疗" in health.recommended_action
    assert "精确方位" not in fengshui.recommended_action
    assert "资料不足" in fengshui.recommended_action

