from __future__ import annotations

from pathlib import Path
import tempfile

from starlette.testclient import TestClient

from mingli.integrated_consumption_service_app import create_app
from mingli.training import TrainingStore
from mingli.training_collector import TrainingReportCollector


NOW = "2026-09-16T08:30:00+00:00"
TOKEN = "integrated-consumption-test-token-at-least-32-chars"
APPROVAL_TOKEN = "integrated-consumption-approval-token-at-least-32-chars"
REVIEWER = "reviewer:" + "a" * 64
MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
}


def _request(
    client: TestClient,
    method: str,
    params: dict[str, object],
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
        json={"jsonrpc": "2.0", "id": call_id, "method": method, "params": params},
    )


def _call(
    client: TestClient,
    name: str,
    arguments: dict[str, object],
    call_id: int,
    *,
    token: str | None = TOKEN,
):
    return _request(
        client,
        "tools/call",
        {"name": name, "arguments": arguments},
        call_id,
        token=token,
    )


def test_existing_integrated_service_exposes_consumption_tools_in_shadow_mode() -> None:
    with tempfile.TemporaryDirectory() as value:
        root = Path(value)
        repo = root / "repo"
        repo.mkdir()
        store = TrainingStore(root / "training", repository_root=repo)
        collector = TrainingReportCollector(store)
        app = create_app(
            collector=collector,
            bearer_token=TOKEN,
            approval_token=APPROVAL_TOKEN,
        )

        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            _request(
                client,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "integrated-consumption-tests", "version": "1.0"},
                },
                1,
            )
            tools = _request(client, "tools/list", {}, 2).json()["result"]["tools"]
            names = {item["name"] for item in tools}
            assert names >= {
                "analyze_mingli",
                "submit_hourly_training_report",
                "get_rule_promotion_status",
                "list_rule_review_queue",
                "submit_phase4_1_candidate_intake",
                "stage_consumption_review_asset",
                "decide_consumption_review",
                "publish_consumption_asset",
                "retrieve_training_context",
                "get_consumption_status",
            }

            denied = _call(client, "get_consumption_status", {}, 3, token=None)
            assert denied.json()["result"]["isError"] is True

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
                        "source_case_ids": ["case-ref-integrated-1"],
                        "source_prediction_ids": ["prediction-ref-integrated-1"],
                        "error_types": ["result_overreach"],
                        "created_at": NOW,
                    }
                },
                4,
            ).json()["result"]["structuredContent"]

            automated_approval = _call(
                client,
                "decide_consumption_review",
                {
                    "decision": {
                        "review_id": staged["review_id"],
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
                        "review_id": staged["review_id"],
                        "decision": "approved",
                        "reviewer_id": REVIEWER,
                        "review_note": "人工确认，仅供 SHADOW 检索。",
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
                        "review_id": staged["review_id"],
                        "approval_id": approval["approval_id"],
                        "published_at": NOW,
                    }
                },
                7,
                token=APPROVAL_TOKEN,
            )
            assert published.json()["result"]["isError"] is False

            context = _call(
                client,
                "retrieve_training_context",
                {
                    "domain": "bazi",
                    "scenario": "career_exam",
                    "topic": "civil_service_exam",
                    "query_id": "query-integrated-1",
                    "consumed_at": NOW,
                },
                8,
            ).json()["result"]["structuredContent"]
            assert context["mode"] == "SHADOW"
            assert context["status"] == "CONTEXT_AVAILABLE"
            assert len(context["failure_cases"]) == 1
            assert context["usage_policy"]["failure_cases"] == "risk_warning_only_do_not_imitate"

            status = _call(
                client,
                "get_consumption_status",
                {},
                9,
            ).json()["result"]["structuredContent"]
            assert status["mode_default"] == "SHADOW"
            assert status["retrievable_assets"] == 1


def test_reused_collector_token_cannot_approve_or_publish() -> None:
    with tempfile.TemporaryDirectory() as value:
        root = Path(value)
        repo = root / "repo"
        repo.mkdir()
        store = TrainingStore(root / "training", repository_root=repo)
        app = create_app(
            collector=TrainingReportCollector(store),
            bearer_token=TOKEN,
            approval_token=TOKEN,
        )

        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            _request(
                client,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "reused-token-test", "version": "1.0"},
                },
                1,
            )
            staged = _call(
                client,
                "stage_consumption_review_asset",
                {
                    "asset": {
                        "domain": "bazi",
                        "scenario": "career_exam",
                        "topic": "civil_service_exam",
                        "outcome_class": "VERIFIED_HIT",
                        "content": "凭证隔离测试资产。",
                        "source_case_ids": ["case-ref-token-separation-1"],
                        "source_prediction_ids": ["prediction-ref-token-separation-1"],
                        "error_types": [],
                        "created_at": NOW,
                    }
                },
                2,
            ).json()["result"]["structuredContent"]
            decision = _call(
                client,
                "decide_consumption_review",
                {
                    "decision": {
                        "review_id": staged["review_id"],
                        "decision": "approved",
                        "reviewer_id": REVIEWER,
                        "review_note": "复用采集 token 必须拒绝。",
                        "decided_at": NOW,
                    }
                },
                3,
                token=TOKEN,
            )
            assert decision.json()["result"]["isError"] is True
