from __future__ import annotations

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from mingli.service_app import MAX_REQUEST_BYTES, create_app

MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
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


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as value:
        yield value


def test_health_and_capabilities_expose_no_store_read_only_service(client) -> None:
    health = client.get("/healthz")
    capabilities = client.get("/v1/capabilities")

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "service": "mingli-runtime-service@1.0.0",
    }
    assert capabilities.status_code == 200
    assert capabilities.json()["request_storage"] == "none"
    assert capabilities.json()["prediction_validity"] == "not_evaluated"
    for response in (health, capabilities):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-request-id"]


def test_http_api_runs_mingli_and_chains_ziwei_chart_into_rules(client) -> None:
    runtime = client.post("/v1/mingli/analyze", json=mingli_payload())
    chart = client.post("/v1/ziwei/chart", json=ziwei_birth_payload())
    evaluation = client.post("/v1/ziwei/rules/evaluate", json=chart.json())
    coverage = client.get("/v1/ziwei/coverage")

    assert runtime.status_code == 200
    assert runtime.json()["prediction_validity"] == "not_evaluated"
    assert runtime.json()["final_answer"]
    assert chart.status_code == 200
    assert chart.json()["calculation_status"] == "complete"
    assert evaluation.status_code == 200
    assert evaluation.json()["evaluated_rules"] == 184
    assert evaluation.json()["effective_match_count"] >= 14
    assert coverage.status_code == 200
    assert coverage.json()["release_gate"] == "REVIEW_REQUIRED"


def test_http_api_maps_invalid_json_domain_errors_and_large_requests(client) -> None:
    invalid_json = client.post(
        "/v1/ziwei/chart",
        content=b"{",
        headers={"content-type": "application/json"},
    )
    wrong_shape = client.post("/v1/ziwei/chart", json=[])

    degraded_input = ziwei_birth_payload()
    degraded_input.update(birth_time=None, birth_time_known=False)
    degraded = client.post("/v1/ziwei/chart", json=degraded_input).json()
    domain_error = client.post("/v1/ziwei/rules/evaluate", json=degraded)

    too_large = client.post(
        "/v1/ziwei/chart",
        content=b"x" * (MAX_REQUEST_BYTES + 1),
        headers={"content-type": "application/json"},
    )

    assert invalid_json.status_code == 400
    assert invalid_json.json()["error"]["code"] == "invalid_json"
    assert wrong_shape.status_code == 400
    assert wrong_shape.json()["error"]["code"] == "invalid_request"
    assert domain_error.status_code == 422
    assert domain_error.json()["error"]["code"] == "domain_validation_failed"
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "request_too_large"


def _mcp_request(client: TestClient, method: str, params: dict[str, object], call_id: int):
    return client.post(
        "/mcp",
        headers=MCP_HEADERS,
        json={"jsonrpc": "2.0", "id": call_id, "method": method, "params": params},
    )


def test_mcp_lists_precise_read_only_tools_and_calls_real_coverage(client) -> None:
    initialized = _mcp_request(
        client,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "mingli-tests", "version": "1.0.0"},
        },
        1,
    )
    tools = _mcp_request(client, "tools/list", {}, 2)
    coverage = _mcp_request(
        client,
        "tools/call",
        {"name": "get_ziwei_rule_coverage", "arguments": {}},
        3,
    )

    assert initialized.status_code == 200
    assert initialized.json()["result"]["serverInfo"]["name"] == "MingLi Agent Runtime"
    assert tools.status_code == 200
    descriptors = tools.json()["result"]["tools"]
    assert {item["name"] for item in descriptors} == {
        "analyze_mingli",
        "create_ziwei_chart",
        "evaluate_ziwei_chart",
        "get_ziwei_rule_coverage",
    }
    for descriptor in descriptors:
        assert descriptor["description"].startswith("Use this when")
        assert descriptor["annotations"] == {
            "title": descriptor["annotations"]["title"],
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
    assert coverage.status_code == 200
    result = coverage.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["release_gate"] == "REVIEW_REQUIRED"


def test_mcp_analyze_tool_has_explicit_machine_friendly_input_schema(client) -> None:
    _mcp_request(
        client,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "mingli-tests", "version": "1.0.0"},
        },
        1,
    )
    descriptors = _mcp_request(client, "tools/list", {}, 2).json()["result"]["tools"]
    analyze = next(item for item in descriptors if item["name"] == "analyze_mingli")

    assert set(analyze["inputSchema"]["required"]) == {
        "calendar",
        "birth_date",
        "birth_time",
        "timezone",
        "gender",
        "longitude",
        "latitude",
        "anchor_year",
    }
    assert analyze["inputSchema"]["properties"]["calendar"]["enum"] == [
        "solar",
        "lunar",
    ]
