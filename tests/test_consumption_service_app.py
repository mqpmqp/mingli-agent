from __future__ import annotations

from pathlib import Path
import tempfile

from starlette.testclient import TestClient

from mingli.consumption_service_app import create_app
from mingli.consumption_v1 import ConsumptionV1
from mingli.training import TrainingStore


NOW = "2026-09-16T08:30:00+00:00"
TOKEN = "consumption-test-token-with-at-least-32-characters"
APPROVAL_TOKEN = "consumption-approval-test-token-with-at-least-32-characters"
REVIEWER = "reviewer:" + "a" * 64
MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
}


def _call(
    client: TestClient,
    name: str,
    arguments: dict[str, object],
    call_id: int,
    *,
    token: str | None = None,
):
    headers = dict(MCP_HEADERS)
    if token:
        headers["authorization"] = f"Bearer {token}"
    return client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


def test_consumption_mcp_exposes_gated_review_publish_and_retrieval() -> None:
    with tempfile.TemporaryDirectory() as value:
        root = Path(value)
        repo = root / "repo"
        repo.mkdir()
        manager = ConsumptionV1(TrainingStore(root / "training", repository_root=repo))
        app = create_app(
            manager=manager,
            bearer_token=TOKEN,
            approval_token=APPROVAL_TOKEN,
        )
        with TestClient(app, base_url="http://127.0.0.1:8010") as client:
            client.post(
                "/mcp",
                headers=MCP_HEADERS,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "consumption-tests", "version": "1.0"},
                    },
                },
            )
            tools = client.post(
                "/mcp",
                headers=MCP_HEADERS,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            ).json()["result"]["tools"]
            denied = _call(client, "get_consumption_status", {}, 3)
            staged = _call(
                client,
                "stage_consumption_review_asset",
                {
                    "asset": {
                        "domain": "bazi",
                        "scenario": "career_exam",
                        "topic": "civil_service_exam",
                        "outcome_class": "FAILURE",
                        "content": "把考试动作扩大成最终录用。",
                        "source_case_ids": ["case-ref-1"],
                        "source_prediction_ids": ["prediction-ref-1"],
                        "error_types": ["result_overreach"],
                        "created_at": NOW,
                    }
                },
                4,
                token=TOKEN,
            ).json()["result"]["structuredContent"]
            review_id = staged["review_id"]

            automated_approval = _call(
                client,
                "decide_consumption_review",
                {
                    "decision": {
                        "review_id": review_id,
                        "decision": "approved",
                        "reviewer_id": REVIEWER,
                        "review_note": "自动凭证不应具有人工批准权限。",
                        "decided_at": NOW,
                    }
                },
                5,
                token=TOKEN,
            )
            assert automated_approval.json()["result"]["isError"] is True

            approval = _call(
                client,
                "decide_consumption_review",
                {
                    "decision": {
                        "review_id": review_id,
                        "decision": "approved",
                        "reviewer_id": REVIEWER,
                        "review_note": "人工确认作为失败反例。",
                        "decided_at": NOW,
                    }
                },
                6,
                token=APPROVAL_TOKEN,
            ).json()["result"]["structuredContent"]
            published = _call(
                client,
                "publish_consumption_asset",
                {
                    "publication": {
                        "review_id": review_id,
                        "approval_id": approval["approval_id"],
                        "published_at": NOW,
                    }
                },
                7,
                token=APPROVAL_TOKEN,
            )
            context = _call(
                client,
                "retrieve_training_context",
                {
                    "domain": "bazi",
                    "scenario": "career_exam",
                    "topic": "civil_service_exam",
                    "query_id": "query-mcp-1",
                    "consumed_at": NOW,
                    "mode": "SHADOW",
                },
                8,
                token=TOKEN,
            ).json()["result"]["structuredContent"]

        names = {item["name"] for item in tools}
        assert names >= {
            "stage_consumption_review_asset",
            "decide_consumption_review",
            "publish_consumption_asset",
            "retrieve_training_context",
            "get_consumption_status",
        }
        assert denied.json()["result"]["isError"] is True
        assert published.json()["result"]["isError"] is False
        assert context["status"] == "CONTEXT_AVAILABLE"
        assert len(context["failure_cases"]) == 1
        assert context["failure_cases"][0]["content"] == "把考试动作扩大成最终录用。"
        assert context["usage_policy"]["failure_cases"] == "risk_warning_only_do_not_imitate"
