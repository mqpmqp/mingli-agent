from __future__ import annotations

from copy import deepcopy

import pytest

from mingli.phase20 import DISCLAIMER
from mingli.service import (
    MINGLI_SERVICE_VERSION,
    analyze_mingli_payload,
    build_ziwei_chart_payload,
    evaluate_ziwei_chart_payload,
    get_service_capabilities,
    get_ziwei_coverage,
)


def mingli_payload() -> dict[str, object]:
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
        "anchor_year": 2028,
        "reality": {"cash_runway_months": 2},
        "fusion_evidence": [],
    }


def ziwei_birth_payload() -> dict[str, object]:
    return {
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


def test_service_capabilities_are_tool_only_read_only_and_hold_aware() -> None:
    value = get_service_capabilities()

    assert value["service_version"] == MINGLI_SERVICE_VERSION
    assert value["archetype"] == "tool-only"
    assert value["transports"] == ["http", "streamable-http-mcp"]
    assert value["request_storage"] == "none"
    assert value["external_network_calls"] is False
    assert value["prediction_validity"] == "not_evaluated"
    assert value["commercial_release_hold"] == "ACTIVE"
    assert {item["name"] for item in value["tools"]} == {
        "analyze_mingli",
        "create_ziwei_chart",
        "evaluate_ziwei_chart",
        "get_ziwei_rule_coverage",
    }
    assert all(item["read_only"] is True for item in value["tools"])


def test_full_runtime_adapter_is_deterministic_and_preserves_safety_contract() -> None:
    first = analyze_mingli_payload(mingli_payload())
    second = analyze_mingli_payload(mingli_payload())

    assert first == second
    assert first["schema_version"] == "mingli-agent-runtime-result@0.3"
    assert first["prediction_validity"] == "not_evaluated"
    assert first["final_answer"].endswith(DISCLAIMER)
    assert first["final_answer"].count(DISCLAIMER) == 1
    assert "no_external_llm_or_network" in first["warnings"]
    assert str(first["canonical_hash"]).startswith("sha256:")


def test_ziwei_chart_and_rule_adapters_chain_with_real_structured_output() -> None:
    chart = build_ziwei_chart_payload(ziwei_birth_payload())
    evaluation = evaluate_ziwei_chart_payload(chart)
    coverage = get_ziwei_coverage()

    assert chart["calculation_status"] == "complete"
    assert chart["algorithm_version"] == "ziwei-traditional-natal@1.0.0"
    assert evaluation["schema_version"] == "ziwei-rule-evaluation@1.0"
    assert evaluation["evaluated_rules"] == 184
    assert evaluation["matched_rules"] >= 14
    assert evaluation["effective_match_count"] == len(evaluation["effective_matches"])
    assert evaluation["prediction_validity"] == "not_evaluated"
    assert coverage["star_palace_behaviorally_evaluated"] == 168
    assert coverage["transformation_behaviorally_evaluated"] == 4
    assert coverage["brightness_behaviorally_evaluated"] == 7
    assert coverage["combination_behaviorally_evaluated"] == 5
    assert coverage["release_gate"] == "REVIEW_REQUIRED"
    assert coverage["rule_content_hold"] == "ACTIVE"


@pytest.mark.parametrize(
    ("call", "payload", "message"),
    [
        (analyze_mingli_payload, [], "object"),
        (build_ziwei_chart_payload, [], "object"),
        (evaluate_ziwei_chart_payload, [], "object"),
    ],
)
def test_service_adapters_reject_non_object_payloads(call, payload, message) -> None:
    with pytest.raises(ValueError, match=message):
        call(payload)


def test_rule_adapter_rejects_degraded_and_tampered_complete_charts() -> None:
    degraded_input = ziwei_birth_payload()
    degraded_input.update(birth_time=None, birth_time_known=False)
    degraded = build_ziwei_chart_payload(degraded_input)
    with pytest.raises(ValueError, match="complete"):
        evaluate_ziwei_chart_payload(degraded)

    chart = build_ziwei_chart_payload(ziwei_birth_payload())
    tampered = deepcopy(chart)
    tampered["palaces"][1]["palace_name"] = tampered["palaces"][0]["palace_name"]
    with pytest.raises(ValueError, match="palace"):
        evaluate_ziwei_chart_payload(tampered)
