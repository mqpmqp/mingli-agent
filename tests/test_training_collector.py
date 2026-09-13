from __future__ import annotations

import asyncio
import json
from pathlib import Path
import tempfile
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
import pytest
from starlette.testclient import TestClient

from mingli.integrated_service_app import (
    analyze_mingli,
    create_app,
    get_integrated_capabilities,
)
from mingli.oauth_resource import OIDCJWTVerifier
from mingli.rule_runtime_v1 import RuleAwareRuntime
from mingli.training import TrainingError, TrainingStore
from mingli.training_cli import main as training_main
from mingli.training_collector import TrainingReportCollector
from mingli.rule_runtime_cli import main as rule_runtime_main


NOW = "2026-09-13T12:00:00+00:00"
TOKEN = "collector-test-token-with-at-least-32-characters"
REVIEWER = "reviewer:" + "a" * 64
MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
}


def test_integrated_runtime_exposes_correct_day_master_and_luck_periods() -> None:
    result = analyze_mingli(
        calendar="lunar",
        birth_date="1988-03-11",
        birth_time="13:15",
        timezone="Asia/Shanghai",
        gender="male",
        longitude=117.638,
        latitude=35.506,
        anchor_year=2026,
        true_solar_time=True,
        is_leap_month=False,
    )

    assert result["chart"]["pillars"] == {
        "year": "戊辰",
        "month": "丙辰",
        "day": "辛亥",
        "hour": "甲午",
    }
    assert result["day_master"] == "辛"
    assert result["luck_anchor"]["direction"] == "forward"
    assert [period["ganzhi"] for period in result["dayun_periods"]] == [
        "丁巳",
        "戊午",
        "己未",
        "庚申",
        "辛酉",
        "壬戌",
        "癸亥",
        "甲子",
        "乙丑",
        "丙寅",
    ]
    assert result["prediction_validity"] == "not_evaluated"


def hourly_report(source_id: str) -> dict[str, object]:
    return {
        "automation_id": "qimen-hourly-training",
        "domain": "qimen",
        "window_start": "2026-09-13T11:00:00+00:00",
        "window_end": NOW,
        "generated_at": NOW,
        "run_count": 1,
        "summary": "合成小时训练报告，仅验证采集闭环。",
        "findings": ["不要把单一凶象直接翻译成具体事件。"],
        "source_ids": [source_id],
        "proposed_rules": [
            {
                "kind": "output_required_notice",
                "statement": "保留现实核验提示。",
                "value": "请结合现实反馈继续核验。",
                "supporting_source_ids": [source_id],
                "counter_evidence": ["合成合同测试不证明预测效果。"],
                "regression_examples": [
                    {"text": "普通输出", "expected_violation": True},
                    {
                        "text": "普通输出。请结合现实反馈继续核验。",
                        "expected_violation": False,
                    },
                ],
            }
        ],
        "synthetic": True,
    }


@pytest.fixture
def configured_collector() -> tuple[TrainingReportCollector, Path, Path, str]:
    with tempfile.TemporaryDirectory() as value:
        root = Path(value)
        repo = root / "repo"
        repo.mkdir()
        source_file = root / "source.pdf"
        source_file.write_bytes(b"synthetic collector source")
        store = TrainingStore(root / "training", repository_root=repo)
        collector = TrainingReportCollector(store)
        source = collector.pipeline.register_source_file(
            source_file,
            {
                "title": "合成奇门来源",
                "source_type": "pdf",
                "source_family": "synthetic-qimen-family",
                "scope_note": "仅验证采集与门禁合同",
                "registered_at": NOW,
            },
        )
        yield collector, repo, store.root, str(source["source_id"])


def test_collector_ingests_dedupes_and_stops_before_human_approval(
    configured_collector: tuple[TrainingReportCollector, Path, Path, str],
) -> None:
    collector, _repo, _store, source_id = configured_collector

    first = collector.collect(hourly_report(source_id), received_at=NOW)
    replay = collector.collect(hourly_report(source_id), received_at=NOW)

    assert first["status"] == "accepted"
    assert first["report_id"] == replay["report_id"]
    assert first["created_candidates"] == 1
    assert replay["deduplicated_candidates"] == 1
    gate: Any = first["candidate_gates"][0]
    assert gate["source_status"] == "failed"
    assert gate["regression_status"] == "passed"
    assert gate["promotion_state"] == "blocked_source_review"
    assert first["auto_approved"] is False
    assert first["auto_published"] is False
    status: Any = collector.status()
    assert status["pipeline"]["hourly_reports"] == 1
    assert status["pipeline"]["approvals"] == 0
    assert status["pipeline"]["releases"] == 0


def test_reviewed_source_reaches_manual_queue_then_release_binds_phase4_1(
    configured_collector: tuple[TrainingReportCollector, Path, Path, str],
) -> None:
    collector, repo, store_root, source_id = configured_collector
    collector.pipeline.review_source(
        {
            "source_id": source_id,
            "review_state": "reviewed",
            "reviewer_id": REVIEWER,
            "reviewed_at": NOW,
            "review_note": "已人工核对合成来源身份和作用范围。",
        }
    )
    receipt: Any = collector.collect(hourly_report(source_id), received_at=NOW)
    gate = receipt["candidate_gates"][0]
    assert gate["promotion_state"] == "awaiting_human_approval"
    assert receipt["human_approval_required"] is True
    queue: Any = collector.review_queue()
    assert queue["candidates"][0]["promotion_state"] == "awaiting_human_approval"

    candidate_id = gate["candidate_id"]
    collector.pipeline.decide_candidate(
        {
            "candidate_id": candidate_id,
            "source_check_id": gate["source_check_id"],
            "regression_id": gate["regression_id"],
            "decision": "approved",
            "reviewer_id": REVIEWER,
            "review_note": "人工批准进入开发与真人试点。",
            "decided_at": NOW,
        }
    )
    collector.pipeline.publish(
        {
            "version": "hourly-rules@2026.09.1",
            "created_at": NOW,
            "candidate_ids": [candidate_id],
        }
    )
    published: Any = collector.review_queue()["candidates"][0]
    assert published["promotion_state"] == "published"
    assert published["published_release_versions"] == ["hourly-rules@2026.09.1"]

    runtime = RuleAwareRuntime(
        store_root, repository_root=repo, version="hourly-rules@2026.09.1"
    )
    prediction = runtime.bind_phase4_1_prediction(
        {"prediction_id": "prediction:synthetic", "rule_set_version": ""}
    )
    assert prediction["rule_set_version"] == "hourly-rules@2026.09.1"
    assert runtime.phase4_1_binding()["registered_real_cases"] == 0
    with pytest.raises(TrainingError, match="PHASE4_1_RULE_VERSION_CONFLICT"):
        runtime.bind_phase4_1_prediction(
            {"rule_set_version": "hourly-rules@2026.08.9"}
        )


def test_collector_rejects_unknown_automation_and_domain_spoofing(
    configured_collector: tuple[TrainingReportCollector, Path, Path, str],
) -> None:
    collector, _repo, _store, source_id = configured_collector
    unknown = hourly_report(source_id)
    unknown["automation_id"] = "unregistered-hourly-task"
    with pytest.raises(TrainingError, match="AUTOMATION_NOT_ALLOWED"):
        collector.collect(unknown, received_at=NOW)

    spoofed = hourly_report(source_id)
    spoofed["domain"] = "bazi"
    with pytest.raises(TrainingError, match="AUTOMATION_DOMAIN_MISMATCH"):
        collector.collect(spoofed, received_at=NOW)


def test_integrated_http_collector_requires_auth_and_exposes_review_queue(
    configured_collector: tuple[TrainingReportCollector, Path, Path, str],
) -> None:
    collector, _repo, _store, source_id = configured_collector
    app = create_app(collector=collector, bearer_token=TOKEN)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        unauthorized = client.post(
            "/v1/training/hourly-reports", json=hourly_report(source_id)
        )
        accepted = client.post(
            "/v1/training/hourly-reports",
            json=hourly_report(source_id),
            headers={"authorization": f"Bearer {TOKEN}"},
        )
        queue = client.get(
            "/v1/training/review-queue",
            headers={"authorization": f"Bearer {TOKEN}"},
        )
        health = client.get("/healthz")

    assert unauthorized.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert queue.status_code == 200
    assert len(queue.json()["candidates"]) == 1
    assert health.json()["collector_configured"] is True
    assert health.json()["collector_auth_configured"] is True


def _mcp_request(
    client: TestClient,
    method: str,
    params: dict[str, object],
    call_id: int,
    *,
    authorized: bool = False,
):
    headers = dict(MCP_HEADERS)
    if authorized:
        headers["authorization"] = f"Bearer {TOKEN}"
    return client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": call_id, "method": method, "params": params},
    )


def test_integrated_mcp_adds_authenticated_idempotent_write_tool(
    configured_collector: tuple[TrainingReportCollector, Path, Path, str],
) -> None:
    collector, _repo, _store, source_id = configured_collector
    app = create_app(collector=collector, bearer_token=TOKEN)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        _mcp_request(
            client,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "collector-tests", "version": "1.0"},
            },
            1,
        )
        tools = _mcp_request(client, "tools/list", {}, 2).json()["result"]["tools"]
        denied = _mcp_request(
            client,
            "tools/call",
            {
                "name": "submit_hourly_training_report",
                "arguments": {"report": hourly_report(source_id)},
            },
            3,
        )
        accepted = _mcp_request(
            client,
            "tools/call",
            {
                "name": "submit_hourly_training_report",
                "arguments": {"report": hourly_report(source_id)},
            },
            4,
            authorized=True,
        )

    submit = next(item for item in tools if item["name"] == "submit_hourly_training_report")
    assert {item["name"] for item in tools} >= {
        "analyze_mingli",
        "submit_hourly_training_report",
        "get_rule_promotion_status",
        "list_rule_review_queue",
    }
    assert submit["annotations"]["readOnlyHint"] is False
    assert submit["annotations"]["idempotentHint"] is True
    assert denied.json()["result"]["isError"] is True
    assert accepted.json()["result"]["isError"] is False
    assert accepted.json()["result"]["structuredContent"]["status"] == "accepted"


def test_report_collect_cli_runs_automatic_gates(
    configured_collector: tuple[TrainingReportCollector, Path, Path, str],
    capsys: Any,
) -> None:
    _collector, repo, store_root, source_id = configured_collector
    report_file = store_root.parent / "hourly-report.json"
    report_file.write_text(
        json.dumps(hourly_report(source_id), ensure_ascii=False), encoding="utf-8"
    )

    code = training_main(
        [
            "report-collect",
            "--input",
            str(report_file),
            "--received-at",
            NOW,
            "--store",
            str(store_root),
            "--repository-root",
            str(repo),
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result["status"] == "ok"
    assert result["data"]["candidate_gates"][0]["regression_status"] == "passed"
    assert result["data"]["auto_approved"] is False


def test_phase4_1_bind_prediction_cli_uses_exact_published_version(
    configured_collector: tuple[TrainingReportCollector, Path, Path, str],
    capsys: Any,
) -> None:
    collector, repo, store_root, source_id = configured_collector
    collector.pipeline.review_source(
        {
            "source_id": source_id,
            "review_state": "reviewed",
            "reviewer_id": REVIEWER,
            "reviewed_at": NOW,
            "review_note": "已人工核对合成来源。",
        }
    )
    receipt: Any = collector.collect(hourly_report(source_id), received_at=NOW)
    gate = receipt["candidate_gates"][0]
    collector.pipeline.decide_candidate(
        {
            "candidate_id": gate["candidate_id"],
            "source_check_id": gate["source_check_id"],
            "regression_id": gate["regression_id"],
            "decision": "approved",
            "reviewer_id": REVIEWER,
            "review_note": "人工批准。",
            "decided_at": NOW,
        }
    )
    collector.pipeline.publish(
        {
            "version": "hourly-rules@2026.09.1",
            "created_at": NOW,
            "candidate_ids": [gate["candidate_id"]],
        }
    )
    prediction_file = store_root.parent / "prediction.json"
    prediction_file.write_text(
        json.dumps({"prediction_id": "prediction:synthetic"}), encoding="utf-8"
    )

    code = rule_runtime_main(
        [
            "phase4-1-bind-prediction",
            "--input",
            str(prediction_file),
            "--store",
            str(store_root),
            "--repository-root",
            str(repo),
            "--version",
            "hourly-rules@2026.09.1",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result["data"]["rule_set_version"] == "hourly-rules@2026.09.1"


def test_integrated_runtime_auto_loads_latest_release_from_training_store(
    configured_collector: tuple[TrainingReportCollector, Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, repo, store_root, source_id = configured_collector
    collector.pipeline.review_source(
        {
            "source_id": source_id,
            "review_state": "reviewed",
            "reviewer_id": REVIEWER,
            "reviewed_at": NOW,
            "review_note": "已人工核对合成来源。",
        }
    )
    receipt: Any = collector.collect(hourly_report(source_id), received_at=NOW)
    gate = receipt["candidate_gates"][0]
    collector.pipeline.decide_candidate(
        {
            "candidate_id": gate["candidate_id"],
            "source_check_id": gate["source_check_id"],
            "regression_id": gate["regression_id"],
            "decision": "approved",
            "reviewer_id": REVIEWER,
            "review_note": "人工批准。",
            "decided_at": NOW,
        }
    )
    collector.pipeline.publish(
        {
            "version": "hourly-rules@2026.09.1",
            "created_at": NOW,
            "candidate_ids": [gate["candidate_id"]],
        }
    )
    monkeypatch.setenv("MINGLI_TRAINING_STORE", str(store_root))
    monkeypatch.setenv("MINGLI_REPOSITORY_ROOT", str(repo))
    monkeypatch.delenv("MINGLI_RULE_RELEASE_STORE", raising=False)
    monkeypatch.delenv("MINGLI_RULE_RELEASE_VERSION", raising=False)

    capabilities: Any = get_integrated_capabilities()

    assert capabilities["rule_release"]["status"] == "loaded"
    assert capabilities["rule_release"]["version"] == "hourly-rules@2026.09.1"
    assert capabilities["rule_release"]["phase4_1_validation"][
        "commercial_release_hold"
    ] == "ACTIVE"


class _StaticSigningKey:
    def __init__(self, key: object) -> None:
        self.key = key


class _StaticJWKClient:
    def __init__(self, key: object) -> None:
        self.key = key

    def get_signing_key_from_jwt(self, token: str) -> _StaticSigningKey:
        return _StaticSigningKey(self.key)


def test_oidc_verifier_checks_signature_issuer_audience_expiry_and_scopes() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    payload = {
        "iss": "https://issuer.example/",
        "aud": "https://runtime.example.com",
        "sub": "user:synthetic",
        "azp": "chatgpt-client",
        "iat": now,
        "exp": now + 300,
        "scope": "runtime:read training:write training:read",
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test"})
    verifier = OIDCJWTVerifier(
        issuer="https://issuer.example/",
        audience="https://runtime.example.com",
        jwks_url="https://issuer.example/.well-known/jwks.json",
        jwk_client=_StaticJWKClient(private_key.public_key()),  # type: ignore[arg-type]
    )
    verified = asyncio.run(verifier.verify_token(token))

    assert verified is not None
    assert verified.client_id == "chatgpt-client"
    assert verified.resource == "https://runtime.example.com"
    assert verified.scopes == ["runtime:read", "training:read", "training:write"]

    wrong_audience = OIDCJWTVerifier(
        issuer="https://issuer.example/",
        audience="https://other.example.com",
        jwks_url="https://issuer.example/.well-known/jwks.json",
        jwk_client=_StaticJWKClient(private_key.public_key()),  # type: ignore[arg-type]
    )
    assert asyncio.run(wrong_audience.verify_token(token)) is None


class _TestTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        if token != "valid-oauth-token":
            return None
        return AccessToken(
            token=token,
            client_id="chatgpt-client",
            scopes=["runtime:read", "training:read", "training:write"],
            expires_at=int(time.time()) + 300,
            resource="http://127.0.0.1:8000",
            subject="user:synthetic",
            claims={"iss": "https://issuer.example/"},
        )


def test_oauth_resource_server_protects_mcp_and_allows_training_write_scope(
    configured_collector: tuple[TrainingReportCollector, Path, Path, str],
) -> None:
    collector, _repo, _store, source_id = configured_collector
    auth = AuthSettings(
        issuer_url="https://issuer.example/",
        resource_server_url="http://127.0.0.1:8000",
        required_scopes=["runtime:read"],
        validate_token_resource=True,
    )
    app = create_app(
        collector=collector,
        token_verifier=_TestTokenVerifier(),
        auth_settings=auth,
    )
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        denied = _mcp_request(
            client,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "oauth-tests", "version": "1.0"},
            },
            1,
        )
        oauth_headers = {
            **MCP_HEADERS,
            "authorization": "Bearer valid-oauth-token",
        }
        initialized = client.post(
            "/mcp",
            headers=oauth_headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "oauth-tests", "version": "1.0"},
                },
            },
        )
        tools_response = client.post(
            "/mcp",
            headers=oauth_headers,
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
        )
        submitted = client.post(
            "/mcp",
            headers=oauth_headers,
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "submit_hourly_training_report",
                    "arguments": {"report": hourly_report(source_id)},
                },
            },
        )
        denied_http = client.post(
            "/v1/training/hourly-reports",
            json=hourly_report(source_id),
        )
        submitted_http = client.post(
            "/v1/training/hourly-reports",
            headers={"authorization": "Bearer valid-oauth-token"},
            json=hourly_report(source_id),
        )

    assert denied.status_code == 401
    assert "resource_metadata" in denied.headers["www-authenticate"]
    assert initialized.status_code == 200
    tools = tools_response.json()["result"]["tools"]
    submit = next(item for item in tools if item["name"] == "submit_hourly_training_report")
    assert submit["_meta"]["securitySchemes"][0]["scopes"] == [
        "runtime:read",
        "training:write",
    ]
    assert submitted.json()["result"]["isError"] is False
    assert denied_http.status_code == 401
    assert submitted_http.status_code == 200
    assert submitted_http.json()["status"] == "accepted"
