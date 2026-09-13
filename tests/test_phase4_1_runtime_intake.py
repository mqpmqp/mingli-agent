from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mingli.integrated_service_app import create_app
from mingli.phase4_1 import Phase41Pilot
from mingli.training import TrainingError, TrainingStore
from mingli.training_collector import TrainingReportCollector


TOKEN = "phase41-test-token-with-at-least-32-characters"
MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
}
CANDIDATE_A = "candidate:" + "a" * 64
CANDIDATE_B = "candidate:" + "b" * 64
CANDIDATE_C = "candidate:" + "c" * 64
CASE_A = "person:" + "1" * 64
CASE_C = "person:" + "3" * 64
PREDICTION_A = "prediction:" + "4" * 64
PREDICTION_C = "prediction:" + "6" * 64
HASH_A = "sha256:" + "7" * 64
HASH_C = "sha256:" + "9" * 64
T0 = "2026-09-13T12:00:00+00:00"
T1 = "2026-09-13T12:01:00+00:00"
T2 = "2026-09-13T12:02:00+00:00"
T3 = "2026-09-13T12:03:00+00:00"


def pilot(tmp_path: Path) -> Phase41Pilot:
    repo = tmp_path / "repo"
    repo.mkdir()
    return Phase41Pilot(TrainingStore(tmp_path / "private", repository_root=repo))


def intake(candidate_id: str, **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidate_id": candidate_id,
        "received_at": T0,
        "source_timestamp": T0,
        "human": True,
        "synthetic": False,
        "consent_status": "granted",
        "privacy_status": "pass",
        "input_gate_status": "pass",
        "prior_stage": "none",
    }
    value.update(overrides)
    return value


def test_empty_ledger_is_not_evaluated(tmp_path: Path) -> None:
    status = pilot(tmp_path).status()
    assert status["integrity"]["no_selective_enrollment"] == "not_evaluated"
    assert status["phase4_1_validation"]["registered_real_cases"] == 0
    assert status["phase4_1_validation"]["commercial_release_hold"] == "ACTIVE"


def test_candidate_screen_freeze_feedback_assigns_contiguous_slots(tmp_path: Path) -> None:
    store = pilot(tmp_path)
    assert store.intake(intake(CANDIDATE_A))["status"] == "accepted"
    assert store.screen({"candidate_id": CANDIDATE_A, "screened_at": T1})["screen"]["pilot_screen_status"] == "eligible"
    first = store.freeze_prediction(
        {
            "candidate_id": CANDIDATE_A,
            "case_id": CASE_A,
            "prediction_id": PREDICTION_A,
            "frozen_at": T2,
            "prediction_manifest_hash": HASH_A,
            "rule_set_version": "runtime@test",
            "claim_ids": ["career_exam", "family"],
        }
    )
    assert first["prediction"]["pilot_slot"] == "slot_01"
    feedback = store.add_feedback(
        {
            "feedback_id": "sha256:" + "8" * 64,
            "prediction_id": PREDICTION_A,
            "submitted_at": T3,
            "evidence_codes": ["interview_not_admitted", "marriage_harmonious"],
        }
    )
    assert feedback["feedback"]["counts_toward_accuracy"] is False

    store.intake(intake(CANDIDATE_B, consent_status="denied"))
    failed = store.screen({"candidate_id": CANDIDATE_B, "screened_at": T1})
    assert failed["screen"]["pilot_screen_status"] == "ineligible"

    store.intake(intake(CANDIDATE_C))
    store.screen({"candidate_id": CANDIDATE_C, "screened_at": T1})
    second = store.freeze_prediction(
        {
            "candidate_id": CANDIDATE_C,
            "case_id": CASE_C,
            "prediction_id": PREDICTION_C,
            "frozen_at": T2,
            "prediction_manifest_hash": HASH_C,
            "rule_set_version": "runtime@test",
            "claim_ids": ["finance"],
        }
    )
    assert second["prediction"]["pilot_slot"] == "slot_02"
    status = store.status()
    assert status["candidate_ledger"]["candidate_total"] == 3
    assert status["candidate_ledger"]["registered_to_pilot"] == 2
    assert status["integrity"] == {
        "candidate_intake_integrity": "pass",
        "pilot_screen_integrity": "pass",
        "pilot_slot_integrity": "pass",
        "no_selective_enrollment": True,
    }


@pytest.mark.parametrize(
    "prior_stage",
    ["prediction_created", "prediction_frozen", "feedback_received"],
)
def test_post_prediction_intake_is_audited_but_cannot_take_slot(
    tmp_path: Path, prior_stage: str
) -> None:
    store = pilot(tmp_path)
    receipt = store.intake(intake(CANDIDATE_A, prior_stage=prior_stage))
    assert receipt["status"] == "accepted_for_audit"
    assert receipt["candidate"]["intake_sequence_violation"] is True
    with pytest.raises(TrainingError, match="PHASE4_1_SEQUENCE_VIOLATION"):
        store.screen({"candidate_id": CANDIDATE_A, "screened_at": T1})
    audit = store.add_retrospective_audit(
        {
            "candidate_id": CANDIDATE_A,
            "recorded_at": T1,
            "topic_codes": ["career_exam", "family", "children", "finance", "personality"],
            "evidence_codes": ["relocation_confirmed", "no_children_reported"],
        }
    )
    assert audit["audit"]["counts_toward_registered_real_cases"] is False
    status = store.status()
    assert status["candidate_ledger"]["sequence_violations"] == 1
    assert status["phase4_1_validation"]["observed_real_cases"] == 1
    assert status["phase4_1_validation"]["registered_real_cases"] == 0
    assert status["integrity"]["no_selective_enrollment"] is False


def test_synthetic_candidate_never_gets_real_slot(tmp_path: Path) -> None:
    store = pilot(tmp_path)
    store.intake(
        intake(CANDIDATE_A, human=False, synthetic=True)
    )
    screened = store.screen({"candidate_id": CANDIDATE_A, "screened_at": T1})
    assert screened["screen"]["pilot_screen_status"] == "ineligible"
    with pytest.raises(TrainingError, match="PHASE4_1_NOT_ELIGIBLE"):
        store.freeze_prediction(
            {
                "candidate_id": CANDIDATE_A,
                "case_id": CASE_A,
                "prediction_id": PREDICTION_A,
                "frozen_at": T2,
                "prediction_manifest_hash": HASH_A,
                "rule_set_version": "runtime@test",
                "claim_ids": ["synthetic"],
            }
        )


def test_tampered_candidate_hash_fails_closed(tmp_path: Path) -> None:
    store = pilot(tmp_path)
    store.intake(intake(CANDIDATE_A))
    path = store._path("candidate", CANDIDATE_A)
    record = json.loads(path.read_text(encoding="utf-8"))
    record["consent_status"] = "denied"
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(TrainingError, match="PHASE4_1_INTEGRITY_FAILED"):
        store.status()


def test_integrated_http_exposes_authenticated_phase4_1_lifecycle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    collector = TrainingReportCollector(
        TrainingStore(tmp_path / "private", repository_root=repo)
    )
    app = create_app(collector=collector, bearer_token=TOKEN)
    headers = {"authorization": f"Bearer {TOKEN}"}
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        denied = client.post("/v1/training/phase4-1/candidates", json=intake(CANDIDATE_A))
        accepted = client.post(
            "/v1/training/phase4-1/candidates", json=intake(CANDIDATE_A), headers=headers
        )
        screened = client.post(
            "/v1/training/phase4-1/screens",
            json={"candidate_id": CANDIDATE_A, "screened_at": T1},
            headers=headers,
        )
        frozen = client.post(
            "/v1/training/phase4-1/predictions",
            json={
                "candidate_id": CANDIDATE_A,
                "case_id": CASE_A,
                "prediction_id": PREDICTION_A,
                "frozen_at": T2,
                "prediction_manifest_hash": HASH_A,
                "claim_ids": ["career_exam"],
            },
            headers=headers,
        )
        status = client.get("/v1/training/phase4-1/status", headers=headers)

    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert screened.json()["screen"]["pilot_screen_status"] == "eligible"
    assert frozen.json()["prediction"]["rule_set_version"].startswith("mingli-integrated-runtime@")
    assert status.json()["phase4_1_validation"]["registered_real_cases"] == 1


def test_integrated_mcp_exposes_phase4_1_write_and_status_tools(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    collector = TrainingReportCollector(
        TrainingStore(tmp_path / "private", repository_root=repo)
    )
    app = create_app(collector=collector, bearer_token=TOKEN)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
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
                    "clientInfo": {"name": "phase41-tests", "version": "1.0"},
                },
            },
        )
        tools = client.post(
            "/mcp",
            headers=MCP_HEADERS,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ).json()["result"]["tools"]
        headers = {**MCP_HEADERS, "authorization": f"Bearer {TOKEN}"}
        accepted = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "submit_phase4_1_candidate_intake",
                    "arguments": {"candidate": intake(CANDIDATE_A)},
                },
            },
        ).json()

    names = {item["name"] for item in tools}
    assert names >= {
        "submit_phase4_1_candidate_intake",
        "screen_phase4_1_candidate",
        "freeze_phase4_1_prediction",
        "submit_phase4_1_feedback",
        "submit_phase4_1_retrospective_audit",
        "get_phase4_1_status",
    }
    assert accepted["result"]["isError"] is False
    assert accepted["result"]["structuredContent"]["status"] == "accepted"
