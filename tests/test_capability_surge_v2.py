from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from starlette.testclient import TestClient

from mingli.capability_surge_service_v2 import create_capability_surge_app
from mingli.capability_surge_v2 import (
    CAPABILITY_SURGE_V2_INPUT_SCHEMA_VERSION,
    CAPABILITY_SURGE_V2_METHOD_ID,
    CAPABILITY_SURGE_V2_SCHEMA_VERSION,
    CapabilitySurgeV2Error,
    load_capability_surge_v2_schema,
    run_capability_surge_v2,
)
from mingli.derived.static_engine import BRANCHES, STEMS
from mingli.phase13 import build_phase13_fixture
from mingli.phase20 import DISCLAIMER, FORBIDDEN_PROMISES
from mingli.ziwei import build_ziwei_chart

MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
}


def bazi_request() -> dict[str, object]:
    graph, _ = build_phase13_fixture(STEMS[0], BRANCHES[2])
    timeline = graph["timeline"]
    assert isinstance(timeline, dict)
    years = timeline["liunian_periods"]
    assert isinstance(years, list)
    first = years[0]
    assert isinstance(first, dict)
    return {
        "schema_version": "bazi-expert-orchestration-input@2.0",
        "fact_graph": graph,
        "target_id": first["period_id"],
        "reality_context": {},
        "renderer_context": {
            "profile": {
                "calendar": "solar",
                "birth_date": "2000-01-01",
                "birth_time": "12:00",
            },
            "chenggu": {"display_weight": "not-calculated", "verse_available": False},
            "start_year": first["label_year"],
            "advice_codes": ["verify_reality", "build_plan"],
        },
        "fixture_provenance": {
            "synthetic": True,
            "purpose": "contract_test_only",
            "accuracy_eligible": False,
        },
    }


def ziwei_chart() -> dict[str, object]:
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
            "gender": "unspecified",
        }
    )


def ziwei_overlays(chart: dict[str, object]) -> list[dict[str, object]]:
    palaces = chart["palaces"]
    assert isinstance(palaces, list)
    names = [str(item["palace_name"]) for item in palaces[:3]]
    return [
        {
            "overlay_id": "synthetic-decade-2024",
            "level": "decade",
            "start_year": 2024,
            "end_year": 2033,
            "target_palaces": [names[0]],
            "star_ids": ["wuqu"],
            "transformations": ["quan"],
            "calculation_status": "complete",
            "unsupported_fields": [],
        },
        {
            "overlay_id": "synthetic-year-2028",
            "level": "year",
            "year": 2028,
            "target_palaces": [names[1]],
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
            "target_palaces": [names[2]],
            "star_ids": ["taiyin"],
            "transformations": ["ke"],
            "calculation_status": "complete",
            "unsupported_fields": [],
        },
    ]


def surge_request() -> dict[str, object]:
    chart = ziwei_chart()
    return {
        "schema_version": CAPABILITY_SURGE_V2_INPUT_SCHEMA_VERSION,
        "bazi_request": bazi_request(),
        "ziwei_chart": chart,
        "ziwei_overlays": ziwei_overlays(chart),
        "ziwei_reality_evidence": [],
        "learning_cases": [],
    }


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return run_capability_surge_v2(surge_request()).to_dict()


def test_unified_runtime_is_versioned_deterministic_and_schema_valid(
    result: dict[str, object],
) -> None:
    second = run_capability_surge_v2(surge_request()).to_dict()

    assert result == second
    assert result["schema_version"] == CAPABILITY_SURGE_V2_SCHEMA_VERSION
    assert result["method_id"] == CAPABILITY_SURGE_V2_METHOD_ID
    assert result["prediction_validity"] == "not_evaluated"
    assert result["release_hold"] == "ACTIVE"
    assert result["accuracy_claim_allowed"] is False
    assert result["canonical_hash"].startswith("sha256:")
    assert set(result["component_hashes"]) == {"bazi", "ziwei", "real_case_learning"}
    Draft202012Validator(load_capability_surge_v2_schema()).validate(result)


def test_unified_runtime_preserves_yuan_and_capability_boundaries(
    result: dict[str, object],
) -> None:
    renderer = result["renderer"]
    assert renderer["source"] == "bazi_expert_v2.phase20"
    text = renderer["rendered_text"]
    assert text.count(DISCLAIMER) == 1
    assert text.endswith(DISCLAIMER)
    assert not any(token in text for token in FORBIDDEN_PROMISES)

    matrix = result["capability_matrix"]
    assert set(matrix) == {"bazi", "ziwei", "real_case_learning"}
    assert "five_element_strength" in matrix["bazi"]["implemented"]
    assert "civil_service_exam" in matrix["bazi"]["conditional"]
    assert set(matrix["bazi"]["unsupported"]) == {
        "monthly_scope",
        "marriage",
        "family",
    }
    assert matrix["ziwei"]["behavioral_coverage_complete"] is True
    assert matrix["ziwei"]["accuracy_assessment"] == "not_assessed"
    assert matrix["real_case_learning"]["accuracy_metrics"] is None
    assert matrix["real_case_learning"]["automatic_rule_actions"] == 0
    assert {item["capability"] for item in result["unsupported"]} >= {
        "bazi.monthly_scope",
        "bazi.marriage",
        "bazi.family",
        "real_case_learning.accuracy_claim",
    }


def test_runtime_fail_closes_on_unknown_input_missing_renderer_and_extra_fields() -> None:
    request = surge_request()
    with pytest.raises(CapabilitySurgeV2Error, match="schema_version"):
        run_capability_surge_v2({**request, "schema_version": "unknown@99"})

    extra = {**request, "caller_conclusion": "guaranteed"}
    with pytest.raises(CapabilitySurgeV2Error, match="unsupported input fields"):
        run_capability_surge_v2(extra)

    without_renderer = deepcopy(request)
    del without_renderer["bazi_request"]["renderer_context"]
    with pytest.raises(CapabilitySurgeV2Error, match="Yuan renderer"):
        run_capability_surge_v2(without_renderer)

    tampered = deepcopy(request)
    tampered["ziwei_chart"]["canonical_hash"] = "sha256:" + "0" * 64
    with pytest.raises(CapabilitySurgeV2Error, match="Ziwei"):
        run_capability_surge_v2(tampered)


def test_http_surface_runs_unified_runtime_and_preserves_security_headers() -> None:
    with TestClient(
        create_capability_surge_app(),
        base_url="http://127.0.0.1:8000",
    ) as client:
        capabilities = client.get("/v2/capabilities")
        response = client.post("/v2/capability-surge/analyze", json=surge_request())
        invalid = client.post("/v2/capability-surge/analyze", json=[])

    assert capabilities.status_code == 200
    assert capabilities.json()["release_hold"] == "ACTIVE"
    assert capabilities.json()["request_storage"] == "none"
    assert response.status_code == 200
    assert response.json()["prediction_validity"] == "not_evaluated"
    assert response.json()["renderer"]["rendered_text"].count(DISCLAIMER) == 1
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_request"
    for value in (capabilities, response, invalid):
        assert value.headers["cache-control"] == "no-store"
        assert value.headers["x-request-id"]


def _mcp_request(
    client: TestClient,
    method: str,
    params: dict[str, object],
    call_id: int,
):
    return client.post(
        "/mcp",
        headers=MCP_HEADERS,
        json={"jsonrpc": "2.0", "id": call_id, "method": method, "params": params},
    )


def test_mcp_surface_lists_and_calls_read_only_unified_tool() -> None:
    with TestClient(
        create_capability_surge_app(),
        base_url="http://127.0.0.1:8000",
    ) as client:
        initialized = _mcp_request(
            client,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "surge-v2-tests", "version": "1.0.0"},
            },
            1,
        )
        tools = _mcp_request(client, "tools/list", {}, 2)
        called = _mcp_request(
            client,
            "tools/call",
            {
                "name": "analyze_capability_surge_v2",
                "arguments": {"payload": surge_request()},
            },
            3,
        )

    assert initialized.status_code == 200
    descriptors = tools.json()["result"]["tools"]
    descriptor = next(
        item for item in descriptors if item["name"] == "analyze_capability_surge_v2"
    )
    assert descriptor["annotations"]["readOnlyHint"] is True
    assert descriptor["annotations"]["destructiveHint"] is False
    assert called.status_code == 200
    assert called.json()["result"]["isError"] is False
    content = called.json()["result"]["structuredContent"]
    assert content["prediction_validity"] == "not_evaluated"
    assert content["release_hold"] == "ACTIVE"

