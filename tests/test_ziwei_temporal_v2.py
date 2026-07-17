from __future__ import annotations

from copy import deepcopy
import json

from jsonschema import Draft202012Validator
import pytest

from mingli.contracts import get_schema
from mingli.contracts.serialization import digest
from mingli.ziwei import build_ziwei_chart
from mingli.ziwei_temporal_v2 import (
    ZIWEI_TEMPORAL_V2_METHOD_ID,
    ZIWEI_TEMPORAL_V2_RULESET_VERSION,
    ZIWEI_TEMPORAL_V2_SCHEMA_VERSION,
    ZiweiTemporalV2Error,
    build_ziwei_temporal_v2_coverage,
    evaluate_ziwei_temporal_v2,
    load_ziwei_temporal_v2_rule_pack,
)

pytestmark = pytest.mark.fast

SYNTHETIC_FIXTURE_CLASSIFICATION = "synthetic_contract_only"
REQUIRED_CATEGORIES = {
    "four_transformation_combination",
    "primary_supporting_combination",
    "three_directions_four_orthogonals",
    "sandwich",
    "arch",
    "convergence",
    "aspect",
    "life_body_relationship",
    "brightness_state_combination",
    "temporal_overlay",
}
REQUIRED_TOPICS = {
    "career",
    "wealth",
    "relationship",
    "study",
    "family",
    "migration",
}


def synthetic_contract_chart(**birth_overrides: object) -> dict[str, object]:
    """Return synthetic chart data for contract behavior, never accuracy proof."""
    birth: dict[str, object] = {
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
        "name": "Synthetic Contract Person",
        "session_id": "must-not-leak",
    }
    birth.update(birth_overrides)
    return build_ziwei_chart(birth)


def synthetic_contract_overlays() -> list[dict[str, object]]:
    """Return deterministic synthetic temporal overlays for contract tests only."""
    return [
        {
            "overlay_id": "synthetic-decade-2024",
            "level": "decade",
            "start_year": 2024,
            "end_year": 2033,
            "target_palaces": ["官禄宫"],
            "star_ids": ["wuqu"],
            "transformations": ["quan"],
            "calculation_status": "complete",
            "unsupported_fields": [],
        },
        {
            "overlay_id": "synthetic-year-2028",
            "level": "year",
            "year": 2028,
            "target_palaces": ["财帛宫"],
            "star_ids": ["wuqu"],
            "transformations": ["lu"],
            "calculation_status": "complete",
            "unsupported_fields": [],
        },
        {
            "overlay_id": "synthetic-month-2028-05",
            "level": "month",
            "year": 2028,
            "month": 5,
            "target_palaces": ["夫妻宫"],
            "star_ids": ["taiyin"],
            "transformations": ["ke"],
            "calculation_status": "complete",
            "unsupported_fields": [],
        },
    ]


def _rehash_rule(rule: dict[str, object]) -> dict[str, object]:
    body = {key: value for key, value in rule.items() if key != "canonical_hash"}
    rule["canonical_hash"] = digest(
        {"record_type": "ZiweiTemporalCombinationRuleV2", "payload": body}
    )
    return rule


def _rehash_pack(pack: dict[str, object]) -> dict[str, object]:
    body = {key: value for key, value in pack.items() if key != "canonical_hash"}
    pack["canonical_hash"] = digest(
        {"record_type": "ZiweiTemporalCombinationRulePackV2", "payload": body}
    )
    return pack


def _rehash_chart(chart: dict[str, object]) -> dict[str, object]:
    body = {key: value for key, value in chart.items() if key != "canonical_hash"}
    chart["canonical_hash"] = digest(
        {"record_type": "ZiweiChart", "payload": body}
    )
    return chart


def _custom_conflict_pack(*, equal_priority: bool) -> dict[str, object]:
    pack = deepcopy(load_ziwei_temporal_v2_rule_pack())
    winner = deepcopy(pack["rules"][0])
    assert isinstance(winner, dict)
    winner["rule_id"] = "ziwei-temporal-v2:test:priority-winner"
    winner["claim_id"] = "synthetic-contract:priority-conflict"
    winner["conflict_group"] = "synthetic-contract:priority-conflict"
    winner["direction"] = "support"
    winner["priority"] = 80
    winner["canonical_priority"] = 80
    _rehash_rule(winner)

    challenger = deepcopy(winner)
    challenger["rule_id"] = "ziwei-temporal-v2:test:priority-challenger"
    challenger["direction"] = "contradict"
    challenger["priority"] = 80 if equal_priority else 70
    challenger["canonical_priority"] = challenger["priority"]
    _rehash_rule(challenger)

    pack["rules"] = [winner, challenger]
    return _rehash_pack(pack)


def _finding(result: dict[str, object], rule_id: str, scope: str) -> dict[str, object]:
    return next(
        item
        for item in result["findings"]
        if item["rule_id"] == rule_id and item["scope"] == scope
    )


def test_synthetic_contract_evaluation_is_versioned_deterministic_and_private() -> None:
    chart = synthetic_contract_chart()
    overlays = synthetic_contract_overlays()

    first = evaluate_ziwei_temporal_v2(chart, overlays=overlays)
    reordered = evaluate_ziwei_temporal_v2(chart, overlays=list(reversed(overlays)))

    assert first == reordered
    assert first["schema_version"] == ZIWEI_TEMPORAL_V2_SCHEMA_VERSION
    assert first["method_id"] == ZIWEI_TEMPORAL_V2_METHOD_ID
    assert first["ruleset_version"] == ZIWEI_TEMPORAL_V2_RULESET_VERSION
    assert first["prediction_validity"] == "not_evaluated"
    assert first["release_hold"] == "ACTIVE"
    assert first["fixture_classification"] == SYNTHETIC_FIXTURE_CLASSIFICATION
    assert first["accuracy_assessment"] == "not_assessed"
    assert first["canonical_hash"].startswith("sha256:")
    assert first["chart_fingerprint"] == chart["chart_fingerprint"]
    encoded = json.dumps(first, ensure_ascii=False, sort_keys=True)
    for private_value in (
        "Synthetic Contract Person",
        "must-not-leak",
        "1984-01-13",
        "00:30",
        "Asia/Shanghai",
    ):
        assert private_value not in encoded

    Draft202012Validator(
        get_schema("ziwei_temporal_v2_result.schema.json")
    ).validate(first)


def test_all_combination_families_and_six_topics_are_behaviorally_reached() -> None:
    result = evaluate_ziwei_temporal_v2(
        synthetic_contract_chart(), overlays=synthetic_contract_overlays()
    )
    active = [
        item
        for item in result["findings"]
        if item["resolution"] in {"matched", "reality_override"}
    ]

    assert REQUIRED_CATEGORIES <= {item["category"] for item in active}
    assert REQUIRED_TOPICS <= {
        topic for item in active for topic in item["topics"]
    }
    assert all(item["prediction_validity"] == "not_evaluated" for item in active)
    assert {item["temporal_level"] for item in active} >= {
        "natal",
        "decade",
        "year",
        "month",
    }


def test_decade_year_month_overlays_produce_only_bounded_event_windows() -> None:
    result = evaluate_ziwei_temporal_v2(
        synthetic_contract_chart(), overlays=synthetic_contract_overlays()
    )
    windows = {item["scope"]: item for item in result["event_time_windows"]}

    assert windows["synthetic-decade-2024"] == {
        "scope": "synthetic-decade-2024",
        "level": "decade",
        "start": "2024-01",
        "end": "2033-12",
        "bounded": True,
        "precision": "month",
    }
    assert windows["synthetic-year-2028"] == {
        "scope": "synthetic-year-2028",
        "level": "year",
        "start": "2028-01",
        "end": "2028-12",
        "bounded": True,
        "precision": "month",
    }
    assert windows["synthetic-month-2028-05"] == {
        "scope": "synthetic-month-2028-05",
        "level": "month",
        "start": "2028-05",
        "end": "2028-05",
        "bounded": True,
        "precision": "month",
    }
    assert "event_prediction" not in result
    assert all(
        item["event_time_window"] is None
        if item["scope"] == "natal"
        else item["event_time_window"] == windows[item["scope"]]
        for item in result["findings"]
    )


def test_mixed_temporal_overlays_require_parent_window_containment() -> None:
    chart = synthetic_contract_chart()
    overlays = synthetic_contract_overlays()

    year_outside_decade = deepcopy(overlays)
    year_outside_decade[1]["year"] = 2034
    with pytest.raises(ZiweiTemporalV2Error, match="contained.*decade"):
        evaluate_ziwei_temporal_v2(chart, overlays=year_outside_decade)

    month_outside_year = deepcopy(overlays)
    month_outside_year[2]["year"] = 2029
    with pytest.raises(ZiweiTemporalV2Error, match="contained.*year"):
        evaluate_ziwei_temporal_v2(chart, overlays=month_outside_year)


def test_child_temporal_overlays_require_explicit_parent_hierarchy() -> None:
    chart = synthetic_contract_chart()
    decade, year, month = synthetic_contract_overlays()

    with pytest.raises(ZiweiTemporalV2Error, match="supplied decade"):
        evaluate_ziwei_temporal_v2(chart, overlays=[year, month])

    with pytest.raises(ZiweiTemporalV2Error, match="supplied year"):
        evaluate_ziwei_temporal_v2(chart, overlays=[decade, month])

    with pytest.raises(ZiweiTemporalV2Error, match="supplied (decade|year)"):
        evaluate_ziwei_temporal_v2(chart, overlays=[month])


def test_child_temporal_overlays_require_unique_parent_hierarchy() -> None:
    chart = synthetic_contract_chart()
    decade, year, month = synthetic_contract_overlays()

    overlapping_decade = deepcopy(decade)
    overlapping_decade["overlay_id"] = "synthetic-decade-overlap-2020"
    overlapping_decade["start_year"] = 2020
    overlapping_decade["end_year"] = 2029
    with pytest.raises(ZiweiTemporalV2Error, match="exactly one supplied decade"):
        evaluate_ziwei_temporal_v2(
            chart, overlays=[decade, overlapping_decade, year, month]
        )

    duplicate_year = deepcopy(year)
    duplicate_year["overlay_id"] = "synthetic-year-2028-duplicate-parent"
    with pytest.raises(ZiweiTemporalV2Error, match="exactly one supplied year"):
        evaluate_ziwei_temporal_v2(
            chart, overlays=[decade, year, duplicate_year, month]
        )


def test_priority_suppression_and_equal_priority_conflict_demote_confidence() -> None:
    chart = synthetic_contract_chart()

    prioritized = evaluate_ziwei_temporal_v2(
        chart, rule_pack=_custom_conflict_pack(equal_priority=False)
    )
    winner = _finding(
        prioritized, "ziwei-temporal-v2:test:priority-winner", "natal"
    )
    loser = _finding(
        prioritized, "ziwei-temporal-v2:test:priority-challenger", "natal"
    )
    assert winner["resolution"] == "matched"
    assert loser["resolution"] == "suppressed_by_higher_priority"
    assert loser["confidence"] == "low"
    assert "higher_priority_conflict" in loser["confidence_demotion_reasons"]

    conflicted = evaluate_ziwei_temporal_v2(
        chart, rule_pack=_custom_conflict_pack(equal_priority=True)
    )
    peers = [
        item
        for item in conflicted["findings"]
        if item["claim_id"] == "synthetic-contract:priority-conflict"
    ]
    assert len(peers) == 2
    assert {item["resolution"] for item in peers} == {"unresolved_conflict"}
    assert {item["confidence"] for item in peers} == {"low"}
    assert all(
        "equal_priority_direction_conflict" in item["confidence_demotion_reasons"]
        for item in peers
    )


def test_reality_evidence_hard_override_is_claim_and_scope_specific() -> None:
    chart = synthetic_contract_chart()
    overlays = synthetic_contract_overlays()
    second_year = deepcopy(overlays[1])
    second_year["overlay_id"] = "synthetic-year-2029"
    second_year["year"] = 2029
    overlays.append(second_year)
    baseline = evaluate_ziwei_temporal_v2(chart, overlays=overlays)
    targets = [
        item
        for item in baseline["findings"]
        if item["category"] == "temporal_overlay"
        and item["temporal_level"] == "year"
    ]
    assert len(targets) == 2
    selected = next(item for item in targets if item["scope"] == "synthetic-year-2028")
    untouched = next(item for item in targets if item["scope"] == "synthetic-year-2029")
    override_direction = (
        "contradict" if selected["direction"] == "support" else "support"
    )

    overridden = evaluate_ziwei_temporal_v2(
        chart,
        overlays=overlays,
        evaluation_at="2029-01-02T00:00:00Z",
        reality_evidence=[
            {
                "evidence_id": "synthetic-reality-2028",
                "claim_id": selected["claim_id"],
                "scope": selected["scope"],
                "direction": override_direction,
                "verified": True,
                "source_id": "synthetic-contract-observation",
                "event_window": "2028-01-01T00:00:00Z/2028-12-31T23:59:59Z",
                "observed_at": "2029-01-01T00:00:00Z",
                "collected_at": "2029-01-02T00:00:00Z",
            }
        ],
    )

    changed = _finding(overridden, selected["rule_id"], selected["scope"])
    unchanged = _finding(overridden, untouched["rule_id"], untouched["scope"])
    assert changed["direction"] == override_direction
    assert changed["resolution"] == "reality_override"
    assert changed["reality_evidence_ids"] == ["synthetic-reality-2028"]
    assert unchanged["direction"] == untouched["direction"]
    assert unchanged["resolution"] == untouched["resolution"]


@pytest.mark.parametrize(
    ("evaluation_at", "event_window", "observed_at", "collected_at"),
    [
        (None, "2028-01-01T00:00:00Z/2028-12-31T23:59:59Z", "2029-01-01T00:00:00Z", "2029-01-02T00:00:00Z"),
        ("2028-12-31T23:59:59Z", "2028-01-01T00:00:00Z/2028-12-31T23:59:59Z", "2029-01-01T00:00:00Z", "2029-01-02T00:00:00Z"),
        ("2029-01-02T00:00:00Z", "2028-01-01T00:00:00Z/2028-12-31T23:59:59Z", "2027-12-31T23:59:59Z", "2029-01-02T00:00:00Z"),
        ("2029-01-02T00:00:00Z", "2028-01-01T00:00:00Z/2028-12-31T23:59:59Z", "2029-01-02T00:00:00Z", "2029-01-01T00:00:00Z"),
    ],
)
def test_reality_evidence_temporal_availability_fails_closed(
    evaluation_at: str | None,
    event_window: str,
    observed_at: str,
    collected_at: str,
) -> None:
    chart = synthetic_contract_chart()
    overlays = synthetic_contract_overlays()
    baseline = evaluate_ziwei_temporal_v2(chart, overlays=overlays)
    selected = next(
        item
        for item in baseline["findings"]
        if item["category"] == "temporal_overlay"
        and item["scope"] == "synthetic-year-2028"
    )
    evidence = {
        "evidence_id": "synthetic-reality-invalid-time",
        "claim_id": selected["claim_id"],
        "scope": selected["scope"],
        "direction": "contradict",
        "verified": True,
        "source_id": "synthetic-contract-observation",
        "event_window": event_window,
        "observed_at": observed_at,
        "collected_at": collected_at,
    }

    with pytest.raises(ZiweiTemporalV2Error, match="Reality Evidence|evaluation_at"):
        evaluate_ziwei_temporal_v2(
            chart,
            overlays=overlays,
            evaluation_at=evaluation_at,
            reality_evidence=[evidence],
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda chart: _rehash_chart(
                {**chart, "calculation_status": "degraded", "unsupported_fields": ["birth_time"]}
            ),
            "complete",
        ),
        (
            lambda chart: _rehash_chart(
                {**chart, "unsupported_fields": ["temporal_combinations"]}
            ),
            "unsupported",
        ),
        (
            lambda chart: {**chart, "canonical_hash": "sha256:" + "0" * 64},
            "canonical_hash",
        ),
        (
            lambda chart: _rehash_chart(
                {**chart, "algorithm_version": "ziwei-unknown@99.0"}
            ),
            "incompatible",
        ),
    ],
)
def test_unsupported_or_incompatible_charts_fail_closed(mutate, message: str) -> None:
    with pytest.raises(ZiweiTemporalV2Error, match=message):
        evaluate_ziwei_temporal_v2(mutate(synthetic_contract_chart()))


def test_unsupported_and_unbounded_overlay_requests_fail_closed() -> None:
    chart = synthetic_contract_chart()
    unsupported = deepcopy(synthetic_contract_overlays()[1])
    unsupported["unsupported_fields"] = ["year_transformations"]
    with pytest.raises(ZiweiTemporalV2Error, match="unsupported"):
        evaluate_ziwei_temporal_v2(chart, overlays=[unsupported])

    unbounded = deepcopy(synthetic_contract_overlays()[0])
    unbounded["end_year"] = 2040
    with pytest.raises(ZiweiTemporalV2Error, match="ten years"):
        evaluate_ziwei_temporal_v2(chart, overlays=[unbounded])

    with pytest.raises(ZiweiTemporalV2Error, match="cannot return"):
        evaluate_ziwei_temporal_v2(
            chart, requested_outputs=["event_prediction"]
        )


def test_rule_pack_and_behavioral_coverage_are_hashed_and_non_accuracy_claims() -> None:
    pack = load_ziwei_temporal_v2_rule_pack()
    Draft202012Validator(
        get_schema("ziwei_temporal_v2_rule_pack.schema.json")
    ).validate(pack)
    coverage = build_ziwei_temporal_v2_coverage(pack)

    assert pack["content_version"] == ZIWEI_TEMPORAL_V2_RULESET_VERSION
    assert pack["canonical_hash"].startswith("sha256:")
    assert coverage["complete"] is True
    assert coverage["covered_count"] == coverage["rule_count"] == len(pack["rules"])
    assert coverage["required_paths"] == [
        "canonical_trigger",
        "exclusion",
        "priority_conflict",
        "unsupported",
    ]
    assert all(all(item["paths"].values()) for item in coverage["rules"])
    assert coverage["fixture_classification"] == SYNTHETIC_FIXTURE_CLASSIFICATION
    assert coverage["accuracy_assessment"] == "not_assessed"
    assert coverage["prediction_validity"] == "not_evaluated"
    assert coverage["release_hold"] == "ACTIVE"


def _mutated_pack(kind: str) -> tuple[dict[str, object], str]:
    pack = deepcopy(load_ziwei_temporal_v2_rule_pack())
    rule = pack["rules"][0]
    assert isinstance(rule, dict)
    if kind == "trigger":
        rule["trigger"]["all"].append("synthetic:false-pass-token")
        rule["synthetic_contract_fixture"]["tokens"].append(
            "synthetic:false-pass-token"
        )
        failed_path = "canonical_trigger"
    elif kind == "exclusion":
        rule["exclusions"].remove("chart:not_complete")
        failed_path = "exclusion"
    elif kind == "priority":
        rule["priority"] += 1
        failed_path = "priority_conflict"
    elif kind == "unsupported":
        rule["exclusions"].remove("chart:unsupported")
        failed_path = "unsupported"
    elif kind == "conflict_policy":
        rule["conflict_policy"] = "keep_all"
        failed_path = "priority_conflict"
    else:  # pragma: no cover - test helper guard
        raise AssertionError(kind)
    _rehash_rule(rule)
    _rehash_pack(pack)
    return pack, failed_path


@pytest.mark.parametrize(
    "kind",
    ["trigger", "exclusion", "priority", "unsupported", "conflict_policy"],
)
def test_false_pass_mutations_cannot_count_a_rule_as_behaviorally_covered(
    kind: str,
) -> None:
    pack, failed_path = _mutated_pack(kind)
    coverage = build_ziwei_temporal_v2_coverage(pack)
    item = next(
        record
        for record in coverage["rules"]
        if record["rule_id"] == pack["rules"][0]["rule_id"]
    )

    assert item["covered"] is False
    assert item["paths"][failed_path] is False
    assert coverage["complete"] is False
    assert coverage["covered_count"] < coverage["rule_count"]
    assert coverage["accuracy_assessment"] == "not_assessed"


def test_invalid_rule_pack_is_rejected_by_runtime_even_if_coverage_reports_failure() -> None:
    pack, _ = _mutated_pack("conflict_policy")
    coverage = build_ziwei_temporal_v2_coverage(pack)
    assert coverage["complete"] is False
    with pytest.raises(ZiweiTemporalV2Error, match="conflict_policy"):
        evaluate_ziwei_temporal_v2(
            synthetic_contract_chart(), rule_pack=pack
        )


@pytest.mark.parametrize(
    "replacement_tokens",
    [
        ["temporal:natal"],
        [
            "temporal:natal",
            "palace:synthetic:never-derived-by-runtime",
        ],
    ],
)
def test_coordinated_semantic_trigger_rewrites_cannot_reseal_false_coverage(
    replacement_tokens: list[str],
) -> None:
    pack = deepcopy(load_ziwei_temporal_v2_rule_pack())
    rule = pack["rules"][0]
    assert isinstance(rule, dict)
    rule["trigger"]["all"] = list(replacement_tokens)
    rule["canonical_trigger"]["all"] = list(replacement_tokens)
    rule["synthetic_contract_fixture"]["tokens"] = list(replacement_tokens)
    _rehash_rule(rule)
    _rehash_pack(pack)

    coverage = build_ziwei_temporal_v2_coverage(pack)
    item = next(
        record
        for record in coverage["rules"]
        if record["rule_id"] == rule["rule_id"]
    )
    assert item["covered"] is False
    assert item["paths"]["canonical_trigger"] is False
    assert coverage["complete"] is False
    with pytest.raises(ZiweiTemporalV2Error, match="semantic|ruleset"):
        evaluate_ziwei_temporal_v2(synthetic_contract_chart(), rule_pack=pack)


def test_resealed_subset_cannot_claim_complete_ruleset_coverage() -> None:
    pack = deepcopy(load_ziwei_temporal_v2_rule_pack())
    pack["rules"] = pack["rules"][:1]
    _rehash_pack(pack)

    coverage = build_ziwei_temporal_v2_coverage(pack)
    assert coverage["rule_count"] == 1
    assert coverage["complete"] is False
    with pytest.raises(ZiweiTemporalV2Error, match="ruleset"):
        evaluate_ziwei_temporal_v2(synthetic_contract_chart(), rule_pack=pack)
