from __future__ import annotations

from copy import deepcopy
import runpy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mingli.contracts import get_schema
from mingli.ziwei import build_ziwei_chart
from mingli.ziwei_rules import (
    PALACES,
    PRIMARY_STAR_IDS,
    ZIWEI_RULE_CONTENT_VERSION,
    ZiweiRuleError,
    build_rule_coverage,
    evaluate_ziwei_chart_rules,
    evaluate_ziwei_rules,
    extract_ziwei_rule_facts,
    load_ziwei_rule_content,
    load_ziwei_rule_payload,
    validate_rule_card,
)
from mingli.ziwei_runtime import run_ziwei_runtime


def complete_chart() -> dict[str, object]:
    return build_ziwei_chart(
        {
            "calendar_type": "lunar",
            "birth_date": "1984-01-13",
            "birth_time": "00:30",
            "timezone": "Asia/Shanghai",
            "longitude": 121.4737,
            "latitude": 31.2304,
            "solar_time_mode": "civil",
            "late_zi_policy": "midnight",
            "leap_month": False,
            "gender": "male",
        }
    )


def degraded_chart() -> dict[str, object]:
    return build_ziwei_chart(
        {
            "calendar_type": "solar",
            "birth_date": "2000-01-07",
            "birth_time": None,
            "birth_time_known": False,
            "timezone": "Asia/Shanghai",
            "longitude": 121.4737,
            "latitude": 31.2304,
            "solar_time_mode": "civil",
            "late_zi_policy": "midnight",
            "gender": "unspecified",
        }
    )


def test_packaged_rule_payload_has_real_versioned_source_backed_content() -> None:
    payload = load_ziwei_rule_payload()
    rules = load_ziwei_rule_content()
    source_ids = {item["source_id"] for item in payload["sources"]}
    schema = Draft202012Validator(get_schema("ziwei_rule_card.schema.json"))

    assert payload["schema_version"] == "ziwei-traditional-rules@1.0"
    assert payload["content_version"] == ZIWEI_RULE_CONTENT_VERSION
    assert len(rules) == 184
    assert len({rule["rule_id"] for rule in rules}) == len(rules)
    assert {rule["source_id"] for rule in rules}.issubset(source_ids)
    assert {rule["lifecycle"] for rule in rules} == {"draft"}
    assert {rule["confidence"] for rule in rules}.issubset({"low", "medium"})
    assert all(
        rule["compatibility"]["chart_algorithm"]
        == "ziwei-traditional-natal@1.0.0"
        for rule in rules
    )
    for rule in rules:
        schema.validate(rule)
        validate_rule_card(rule)


def test_tracked_rule_resource_matches_deterministic_generator() -> None:
    script = Path(__file__).parents[1] / "scripts" / "build_ziwei_traditional_rules.py"
    generated = runpy.run_path(str(script))["build_payload"]()
    assert generated == load_ziwei_rule_payload()


def test_primary_star_palace_matrix_is_complete_unique_and_not_name_only_templates() -> None:
    rules = [
        rule
        for rule in load_ziwei_rule_content()
        if rule["subject"] == "primary_star_palace"
    ]
    pairs = {(rule["star"], rule["palace"]) for rule in rules}
    expected = {(star, palace) for star in PRIMARY_STAR_IDS for palace in PALACES}
    labels = tuple(PALACES) + (
        "紫微", "天机", "太阳", "武曲", "天同", "廉贞", "天府",
        "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军",
    )

    assert len(rules) == 168
    assert pairs == expected
    assert len({rule["plain_language"] for rule in rules}) == 168
    normalized: set[str] = set()
    for rule in rules:
        text = rule["plain_language"]
        assert 18 <= len(text) <= 120
        assert not any(token in text for token in ("TODO", "占位", "模板", "一定", "必然", "注定", "保证"))
        for label in labels:
            text = text.replace(label, "")
        normalized.add(text)
        assert rule["exclusions"]
        assert rule["themes"]
    assert len(normalized) == 168


def test_chart_fact_extraction_and_rules_are_behaviorally_evaluable() -> None:
    rules = load_ziwei_rule_content()
    facts = extract_ziwei_rule_facts(complete_chart())
    matches = evaluate_ziwei_rules(facts, rules)
    base_matches = [item for item in matches if item.subject == "primary_star_palace"]

    assert len(facts["star_palace_pairs"]) == 14
    assert len(base_matches) == 14
    assert {item.star for item in base_matches} == set(PRIMARY_STAR_IDS)
    assert {item.subject for item in matches}.issuperset(
        {"primary_star_palace", "transformation", "brightness"}
    )

    without_ziwei = dict(facts)
    without_ziwei["star_palace_pairs"] = [
        item for item in facts["star_palace_pairs"] if item["star"] != "ziwei"
    ]
    assert not any(
        item.star == "ziwei" and item.subject == "primary_star_palace"
        for item in evaluate_ziwei_rules(without_ziwei, rules)
    )


def test_exclusions_priority_conflict_and_combination_rules_are_executable() -> None:
    rules = load_ziwei_rule_content()
    combo = next(rule for rule in rules if rule["subject"] == "combination")
    facts = {
        "algorithm_version": "ziwei-traditional-natal@1.0.0",
        "calculation_status": "complete",
        "unsupported_fields": [],
        "star_palace_pairs": [],
        "transformations": [],
        "brightness_states": [],
        "co_locations": [combo["trigger"]["value"]],
    }
    assert [item.rule_id for item in evaluate_ziwei_rules(facts, [combo])] == [
        combo["rule_id"]
    ]
    assert evaluate_ziwei_rules({**facts, "calculation_status": "degraded"}, [combo]) == ()

    high = deepcopy(combo)
    high.update(
        rule_id="ziwei:v1:test:high",
        domain="career",
        priority=90,
        direction="support",
    )
    low = deepcopy(combo)
    low.update(
        rule_id="ziwei:v1:test:low",
        domain="career",
        priority=10,
        direction="contradict",
    )
    ranked = evaluate_ziwei_rules(facts, [low, high])
    assert [(item.rule_id, item.resolution) for item in ranked] == [
        ("ziwei:v1:test:high", "matched"),
        ("ziwei:v1:test:low", "suppressed_by_higher_priority"),
    ]
    peer = deepcopy(high)
    peer.update(rule_id="ziwei:v1:test:peer", direction="contradict")
    conflict = evaluate_ziwei_rules(facts, [high, peer])
    assert {item.resolution for item in conflict} == {"unresolved_conflict"}


def test_unsupported_and_algorithm_mismatch_fail_closed() -> None:
    with pytest.raises(ZiweiRuleError, match="complete"):
        extract_ziwei_rule_facts(degraded_chart())
    with pytest.raises(ZiweiRuleError, match="complete"):
        evaluate_ziwei_chart_rules(degraded_chart())

    chart = complete_chart()
    chart["algorithm_version"] = "ziwei-traditional-natal@99"
    with pytest.raises(ZiweiRuleError, match="algorithm"):
        evaluate_ziwei_chart_rules(chart)


def test_coverage_is_computed_from_real_records_and_behavior_not_hardcoded() -> None:
    rules = list(load_ziwei_rule_content())
    coverage = build_rule_coverage(rules)
    assert coverage["star_palace_total"] == 168
    assert coverage["star_palace_records"] == 168
    assert coverage["star_palace_behaviorally_evaluated"] == 168
    assert coverage["star_palace_implemented"] == 168
    assert coverage["duplicate_pairs"] == 0
    assert coverage["release_gate"] == "REVIEW_REQUIRED"

    removed = build_rule_coverage(rules[1:])
    assert removed["star_palace_implemented"] == 167
    assert removed["release_gate"] == "NO-GO"

    mutated_rules = deepcopy(rules)
    target = next(
        item for item in mutated_rules if item["subject"] == "primary_star_palace"
    )
    target["trigger"]["value"] = {"star": "tianji", "palace": "命宫"}
    mutated = build_rule_coverage(mutated_rules)
    assert mutated["star_palace_records"] == 168
    assert mutated["star_palace_behaviorally_evaluated"] == 167
    assert mutated["release_gate"] == "NO-GO"

    duplicate_rules = deepcopy(rules)
    duplicate = deepcopy(target)
    duplicate["rule_id"] = "ziwei:v1:duplicate:pair"
    duplicate_rules.append(duplicate)
    duplicated = build_rule_coverage(duplicate_rules)
    assert duplicated["duplicate_pairs"] == 1
    assert duplicated["release_gate"] == "NO-GO"


def test_reality_evidence_still_hard_overrides_effective_packaged_rule() -> None:
    chart = complete_chart()
    rules = load_ziwei_rule_content()
    matches = evaluate_ziwei_chart_rules(chart, rules)
    target = next(
        item
        for item in matches
        if item.domain == "career" and item.resolution == "matched"
    )
    result = run_ziwei_runtime(
        chart,
        facts={},
        rules=rules,
        reality={"job_requirements_met": False},
        reality_evidence=[
            {
                "evidence_id": "reality:career:override",
                "claim_id": target.rule_id,
                "scope": "career",
                "source_type": "reality",
                "source_id": "user-confirmed",
                "direction": "contradict",
                "weight": 0,
                "priority": 100,
                "verified": True,
                "detail_code": "verified_constraint",
            }
        ],
        start_year=2028,
    )
    claim = next(
        item
        for item in result["evidence_fusion"]["claims"]
        if item["claim_id"] == target.rule_id
    )
    assert claim["status"] == "resolved_by_reality_override"
    assert claim["hard_override_direction"] == "contradict"


def test_invalid_rule_model_and_unknown_source_are_rejected() -> None:
    payload = load_ziwei_rule_payload()
    rule = deepcopy(payload["rules"][0])
    rule.pop("compatibility")
    with pytest.raises(ZiweiRuleError, match="compatibility"):
        validate_rule_card(rule)

    rule = deepcopy(payload["rules"][0])
    rule["source_id"] = "source:missing"
    with pytest.raises(ZiweiRuleError, match="source"):
        load_ziwei_rule_content(payload={**payload, "rules": [rule]})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_version", "ziwei-traditional-rule-content@99"),
        ("subject", "unknown"),
        ("domain", "health"),
        ("themes", []),
        ("trigger", {"fact": "x", "operator": "unknown", "value": True}),
        ("exclusions", []),
        ("priority", True),
        ("confidence", "certain"),
        ("evidence_level", "verified_prediction"),
        ("lifecycle", "verified"),
        ("conflict_policy", "first_wins"),
        ("output_constraints", ["no_absolute_claims"]),
        ("direction", "neutral"),
    ],
)
def test_rule_model_rejects_invalid_enums_and_boundaries(field: str, value: object) -> None:
    rule = deepcopy(load_ziwei_rule_content()[0])
    rule[field] = value
    with pytest.raises(ZiweiRuleError):
        validate_rule_card(rule)


def test_rule_model_rejects_subject_field_inconsistency_and_unexpected_fields() -> None:
    base = deepcopy(load_ziwei_rule_content()[0])
    invalid_cards = []
    primary_with_transformation = deepcopy(base)
    primary_with_transformation["transformation"] = "lu"
    invalid_cards.append(primary_with_transformation)
    transformation_with_star = deepcopy(base)
    transformation_with_star.update(subject="transformation", transformation="lu")
    invalid_cards.append(transformation_with_star)
    brightness_without_state = deepcopy(base)
    brightness_without_state.update(
        subject="brightness", star=None, palace=None, state=None
    )
    invalid_cards.append(brightness_without_state)
    combination_with_star = deepcopy(base)
    combination_with_star.update(subject="combination", palace=None)
    invalid_cards.append(combination_with_star)
    unexpected = deepcopy(base)
    unexpected["placeholder"] = True
    invalid_cards.append(unexpected)

    for card in invalid_cards:
        with pytest.raises(ZiweiRuleError):
            validate_rule_card(card)


def test_loader_rejects_invalid_payload_shapes_and_duplicate_ids(tmp_path) -> None:
    payload = load_ziwei_rule_payload()
    first = deepcopy(payload["rules"][0])
    invalid_payloads = [
        {**payload, "schema_version": "unknown"},
        {**payload, "content_version": "unknown"},
        {**payload, "sources": []},
        {**payload, "sources": ["not-an-object"]},
        {**payload, "sources": [{"source_id": ""}]},
        {**payload, "sources": [payload["sources"][0], payload["sources"][0]]},
        {**payload, "rules": []},
        {**payload, "rules": ["not-an-object"]},
        {**payload, "rules": [first, first]},
    ]
    for document in invalid_payloads:
        with pytest.raises(ZiweiRuleError):
            load_ziwei_rule_content(payload=document)

    path = tmp_path / "rules.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ZiweiRuleError, match="path or payload"):
        load_ziwei_rule_content(path, payload=payload)


def test_condition_groups_and_negative_operators_are_executable() -> None:
    card = deepcopy(load_ziwei_rule_content()[0])
    card["rule_id"] = "ziwei:v1:test:condition-tree"
    card["trigger"] = {
        "any": [
            {"fact": "signal", "operator": "equals", "value": "secondary"},
            {
                "all": [
                    {"fact": "signal", "operator": "equals", "value": "primary"},
                    {"fact": "flags", "operator": "not_contains", "value": "blocked"},
                ]
            },
        ]
    }
    facts = {
        "algorithm_version": "ziwei-traditional-natal@1.0.0",
        "calculation_status": "complete",
        "unsupported_fields": [],
        "signal": "primary",
        "flags": [],
    }
    assert evaluate_ziwei_rules(facts, [card])[0].rule_id == card["rule_id"]
    assert evaluate_ziwei_rules({**facts, "flags": ["blocked"]}, [card]) == ()


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.update(palaces="invalid"),
        lambda value: value.update(palaces=[]),
        lambda value: value["palaces"].__setitem__(0, "invalid"),
        lambda value: value["palaces"][0].update(palace_name="未知宫"),
        lambda value: value["palaces"][0].update(primary_stars=[{"star_id": "unknown"}]),
        lambda value: value["palaces"][0].update(transformations=["invalid"]),
        lambda value: value["palaces"][0].update(
            transformations=[{"star_id": "ziwei", "transformation": "unknown"}]
        ),
        lambda value: value["palaces"][0].update(brightness_state=["invalid"]),
        lambda value: value["palaces"][0].update(
            brightness_state=[{"star_id": "ziwei", "state": "unknown"}]
        ),
    ],
)
def test_chart_fact_extraction_rejects_malformed_nested_contracts(mutator) -> None:
    chart = complete_chart()
    mutator(chart)
    with pytest.raises(ZiweiRuleError):
        extract_ziwei_rule_facts(chart)


def test_runtime_rejects_protected_fact_override() -> None:
    with pytest.raises(ValueError, match="cannot be overridden"):
        run_ziwei_runtime(
            complete_chart(),
            facts={"algorithm_version": "wrong"},
            rules=load_ziwei_rule_content(),
            reality={},
            reality_evidence=[],
            start_year=2028,
        )
