from __future__ import annotations

import json
from pathlib import Path

import pytest

from mingli.contracts.serialization import digest
from mingli.practice_phase3 import dispatch_phase3, visible_input
from mingli.practice_phase4 import dispatch_phase4
from mingli.training import TrainingError, TrainingStore
from mingli.training_cli import main


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-13T14:00:00+08:00"
PAST = "2026-08-01T00:00:00+08:00/2026-08-31T23:59:59+08:00"


@pytest.fixture
def store(tmp_path: Path) -> TrainingStore:
    return TrainingStore(tmp_path / "store", repository_root=ROOT, synthetic=True)


def start(store: TrainingStore) -> None:
    dispatch_phase4(
        "pilot-start",
        {
            "batch_id": "phase4-pilot-001",
            "pilot_start_at": "2026-09-13T12:00:00+08:00",
            "target_real_cases": 10,
            "grace_period_days": 7,
            "synthetic": True,
            "real_intake_enabled": False,
        },
        store=store,
    )


def intake_payload(index: int = 1, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "batch_id": "phase4-pilot-001",
        "received_at": f"2026-09-13T13:{index:02d}:00+08:00",
        "source_timestamp": f"2026-09-13T13:{index:02d}:00+08:00",
        "source_type": "synthetic_fixture",
        "deidentified_source_fingerprint": "sha256:" + f"{index:064x}",
        "intake_nonce": "sha256:" + f"{index + 100:064x}",
        "proposed_case_id": f"synthetic-phase4-1-case-{index:02d}",
        "human": False,
        "synthetic": True,
        "consent_status": "unknown",
        "privacy_status": "pending",
        "input_gate_status": "pending",
    }
    payload.update(overrides)
    return payload


def screen_payload(candidate_id: str, index: int = 1, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "batch_id": "phase4-pilot-001",
        "screen_id": f"screen-{index:02d}",
        "candidate_id": candidate_id,
        "candidate_case_id": f"synthetic-phase4-1-case-{index:02d}",
        "person_case_id": "person:" + f"{index:064x}",
        "source_timestamp": f"2026-09-13T13:{index:02d}:00+08:00",
        "screened_at": f"2026-09-13T14:{index:02d}:00+08:00",
        "synthetic": True,
        "engineering_dry_run": True,
        "consent": {
            "granted": True,
            "scope": ["deidentified_training_evaluation"],
            "recorded_at": f"2026-09-13T13:{index + 10:02d}:00+08:00",
            "withdrawal_supported": True,
        },
        "deidentified": True,
        "minimum_input_gate_passed": True,
        "chart_gate_passed": True,
        "freeze_ready": True,
        "claim_counts": {"L2": 1, "current_state": 0, "L3": 0, "total": 1},
        "case_role": "pilot_evaluation",
        "engine_version": "fixture-engine",
        "source_commit_sha": "fixture-sha",
        "rule_set_version": "fixture-rules",
        "input_manifest_sha": "sha256:" + "1" * 64,
        "visible_input_hash": "sha256:" + "2" * 64,
        "prediction_snapshot_hash": "sha256:" + "3" * 64,
    }
    payload.update(overrides)
    return payload


def intake(store: TrainingStore, index: int = 1, **overrides: object) -> dict[str, object]:
    return dispatch_phase4("pilot-candidate-intake", intake_payload(index, **overrides), store=store)


def screen(store: TrainingStore, candidate: dict[str, object], index: int = 1, **overrides: object) -> dict[str, object]:
    return dispatch_phase4(
        "pilot-screen",
        screen_payload(str(candidate["candidate_id"]), index, **overrides),
        store=store,
    )


def phase3_case(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "synthetic": True,
        "evidence_level": "L0",
        "simulated_validation_track": "retrospective_blind",
        "registered_at": "2026-09-13T12:00:00+08:00",
        "question": "离线 Candidate 时序验收",
        "outcome_hidden_from_prediction": True,
        "sources": [{"source_id": "basis", "role": "independent", "text": "离线规则依据", "available_at": "2026-09-13T12:00:00+08:00"}],
        "given_facts": [],
        "pilot_batch_id": "phase4-pilot-001",
        "case_role": "pilot_evaluation",
        "consent": {"status": "synthetic_not_applicable", "analysis": False, "storage": False, "followup": False, "withdrawal_available": True},
        "hidden_answer_fields": ["interview_notice_received"],
        "future_outcome_fields": [],
    }


def phase3_prediction(prediction_id: str, case_id: str) -> dict[str, object]:
    case = phase3_case(case_id)
    return {
        "case_id": case_id,
        "frozen_at": "2026-09-13T12:15:00+08:00",
        "prediction": {
            "prediction_id": prediction_id,
            "person_case_id": case_id,
            "scenario_id": "career",
            "engine_version": "synthetic@1",
            "source_commit_sha": "0" * 40,
            "rule_set_version": "synthetic@1",
            "knowledge_manifest_sha": "sha256:" + "0" * 64,
            "input_manifest_sha": digest(visible_input(case)),
            "generated_at": "2026-09-13T12:15:00+08:00",
            "prediction_content": "你收到一次岗位面谈通知",
            "structured_claims": [{
                "claim_id": "interview", "predicted_event_or_state": "你收到一次岗位面谈通知",
                "claim_type": "prior_event", "domain": "career", "validation_track": "retrospective_blind",
                "predicted_direction": "support", "confidence": 0.5, "specificity_level": "bounded",
                "given_dependency_ids": [], "exclusion_conditions": [], "event_window": PAST,
                "result_variable": "interview_notice_received", "atomic": True,
                "outcome_criterion": "以窗口内一份岗位面谈通知记录核验", "basis_source_ids": ["basis"],
            }],
            "confidence": 0.5,
            "blocked_fields": [],
            "reality_evidence_visibility": False,
        },
    }


def test_empty_candidate_ledger_is_not_evaluated(store: TrainingStore) -> None:
    start(store)
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["candidate_intake"]["candidate_total"] == 0
    assert summary["candidate_intake_integrity"] == "not_evaluated"
    assert summary["no_selective_enrollment"] == "not_evaluated"
    assert summary["registered_real_cases"] == summary["eligible_real_cases"] == 0
    assert summary["accuracy"] is None and summary["status"] == "not_evaluated"
    assert summary["commercial_release_hold"] == "ACTIVE"


def test_candidate_screen_case_slot_binding_normal_path(store: TrainingStore) -> None:
    start(store)
    candidate = intake(store)
    enrolled = screen(store, candidate)
    shown = dispatch_phase4(
        "pilot-candidate-show",
        {"batch_id": "phase4-pilot-001", "candidate_id": candidate["candidate_id"]},
        store=store,
    )
    assert enrolled["candidate_id"] == candidate["candidate_id"]
    assert shown["pilot_screen_status"] == "eligible"
    assert shown["registered_case_id"] == "synthetic-phase4-1-case-01"
    assert shown["simulated_slot"] == 1 and shown["pilot_slot"] is None


def test_candidate_screen_case_prediction_freeze_sequence_remains_integral(store: TrainingStore) -> None:
    start(store)
    candidate = intake(store)
    screen(store, candidate)
    case_id = "synthetic-phase4-1-case-01"
    case = phase3_case(case_id)
    case["registered_at"] = "2026-09-13T14:02:00+08:00"
    dispatch_phase3("case-create", case, store=store)
    prediction = phase3_prediction("prediction-after-screen", case_id)
    prediction["frozen_at"] = "2026-09-13T14:03:00+08:00"
    prediction["prediction"]["generated_at"] = "2026-09-13T14:03:00+08:00"
    prediction["prediction"]["input_manifest_sha"] = digest(visible_input(case))
    dispatch_phase3("freeze-prediction", prediction, store=store)
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["candidate_intake_integrity"] == "pass"
    assert summary["pilot_screen_integrity"] == "pass"
    assert summary["pilot_slot_integrity"] == "pass"
    assert summary["no_selective_enrollment"] is True


@pytest.mark.parametrize(
    "intake_overrides,screen_overrides,reason",
    [
        ({"consent_status": "denied"}, {"consent": {"granted": False, "scope": [], "recorded_at": "2026-09-13T13:11:00+08:00", "withdrawal_supported": True}}, "CONSENT_REQUIRED"),
        ({"input_gate_status": "fail"}, {"minimum_input_gate_passed": False}, "INPUT_GATE_FAILED"),
    ],
)
def test_failed_candidate_remains_in_ledger_without_slot(
    store: TrainingStore,
    intake_overrides: dict[str, object],
    screen_overrides: dict[str, object],
    reason: str,
) -> None:
    start(store)
    candidate = intake(store, **intake_overrides)
    failed = screen(store, candidate, **screen_overrides)
    assert failed["simulated_slot"] is None
    assert reason in failed["failure_reasons"]
    ledger = dispatch_phase4("pilot-candidate-list", {"batch_id": "phase4-pilot-001"}, store=store)
    assert ledger["candidate_total"] == 1
    assert ledger["registered_to_pilot"] == 0


def test_synthetic_candidate_never_gets_real_slot_or_real_count(store: TrainingStore) -> None:
    start(store)
    enrolled = screen(store, intake(store))
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert enrolled["assigned_real_slot"] is None and enrolled["simulated_slot"] == 1
    assert summary["candidate_intake"]["candidate_human_total"] == 0
    assert summary["registered_real_cases"] == summary["eligible_real_cases"] == 0


def test_continuous_candidates_allow_a_failed_middle_candidate(store: TrainingStore) -> None:
    start(store)
    first, second, third = (intake(store, index) for index in range(1, 4))
    assert screen(store, first, 1)["simulated_slot"] == 1
    assert screen(store, second, 2, minimum_input_gate_passed=False)["simulated_slot"] is None
    assert screen(store, third, 3)["simulated_slot"] == 2
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["engineering_simulation"]["no_selective_enrollment"] is True


def test_prediction_before_candidate_intake_is_recorded_as_blocked_violation(store: TrainingStore) -> None:
    start(store)
    case_id = "synthetic-phase4-1-case-01"
    dispatch_phase3("case-create", phase3_case(case_id), store=store)
    dispatch_phase3("freeze-prediction", phase3_prediction("prediction-before-intake", case_id), store=store)
    candidate = intake(store)
    assert candidate["intake_status"] == "blocked_sequence_violation"
    assert candidate["intake_sequence_violation"] is True
    assert "prediction" in candidate["prior_state_detected"]
    with pytest.raises(TrainingError, match="CANDIDATE_INTAKE_SEQUENCE_VIOLATION"):
        screen(store, candidate)


def test_feedback_before_candidate_intake_is_recorded_as_violation(store: TrainingStore) -> None:
    start(store)
    case_id = "synthetic-phase4-1-case-01"
    dispatch_phase3("case-create", phase3_case(case_id), store=store)
    dispatch_phase3("freeze-prediction", phase3_prediction("prediction-before-feedback", case_id), store=store)
    dispatch_phase3(
        "outcome-append",
        {
            "prediction_id": "prediction-before-feedback",
            "evidence_id": "feedback-before-intake",
            "claim_id": "interview",
            "event_window": "2026-08-01T00:00:00+08:00/2026-08-31T23:59:59+08:00",
            "observed_at": "2026-08-20T12:00:00+08:00",
            "collected_at": "2026-09-13T12:30:00+08:00",
            "source_provenance": "synthetic_fixture",
            "evidence_quality": "synthetic",
            "fact": "离线事实记录包含一份面谈通知",
            "synthetic": True,
        },
        store=store,
    )
    candidate = intake(store)
    assert candidate["intake_status"] == "blocked_sequence_violation"
    assert "feedback" in candidate["prior_state_detected"]


def test_prediction_between_intake_and_screen_is_screen_fail_and_integrity_broken(store: TrainingStore) -> None:
    start(store)
    candidate = intake(store)
    case_id = "synthetic-phase4-1-case-01"
    case = phase3_case(case_id)
    case["registered_at"] = "2026-09-13T13:30:00+08:00"
    dispatch_phase3("case-create", case, store=store)
    prediction = phase3_prediction("prediction-before-screen", case_id)
    prediction["frozen_at"] = "2026-09-13T13:40:00+08:00"
    prediction["prediction"]["generated_at"] = "2026-09-13T13:40:00+08:00"
    prediction["prediction"]["input_manifest_sha"] = digest(visible_input(case))
    dispatch_phase3("freeze-prediction", prediction, store=store)
    failed = screen(store, candidate)
    assert failed["screen_status"] == "synthetic_screen_fail"
    assert "INTAKE_SEQUENCE_VIOLATION" in failed["failure_reasons"]
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["candidate_intake_integrity"] == "broken"
    assert summary["pilot_screen_integrity"] == "broken"
    assert summary["no_selective_enrollment"] is False


def test_candidate_cannot_bind_two_cases(store: TrainingStore) -> None:
    start(store)
    candidate = intake(store)
    screen(store, candidate)
    with pytest.raises(TrainingError, match="CANDIDATE_CASE_BINDING_MISMATCH"):
        screen(store, candidate, 2, candidate_case_id="synthetic-phase4-1-case-02")


def test_case_without_candidate_cannot_screen_or_get_slot(store: TrainingStore) -> None:
    start(store)
    with pytest.raises(TrainingError, match="CANDIDATE_INTAKE_REQUIRED"):
        dispatch_phase4("pilot-screen", screen_payload("candidate:" + "9" * 64), store=store)


def test_candidate_arrival_order_inversion_breaks_intake_integrity(store: TrainingStore) -> None:
    start(store)
    intake(store, 2, received_at="2026-09-13T13:03:00+08:00")
    intake(store, 1, received_at="2026-09-13T13:04:00+08:00")
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["candidate_intake_integrity"] == "broken"
    assert summary["no_selective_enrollment"] is False


def test_skipping_candidate_screen_order_breaks_screen_integrity(store: TrainingStore) -> None:
    start(store)
    first, second, third = (intake(store, index) for index in range(1, 4))
    screen(store, first, 1)
    screen(store, third, 3)
    screen(store, second, 2, minimum_input_gate_passed=False, screened_at="2026-09-13T14:04:00+08:00")
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["pilot_screen_integrity"] == "broken"
    assert summary["no_selective_enrollment"] is False


def test_deleted_receipt_cannot_be_renumbered_with_a_new_nonce(store: TrainingStore) -> None:
    start(store)
    candidate = intake(store)
    store._path("pilot_candidate_intake", str(candidate["candidate_id"])).unlink()
    replacement = intake_payload(intake_nonce="sha256:" + "f" * 64)
    with pytest.raises(TrainingError, match="CANDIDATE_IDENTITY_REUSE"):
        dispatch_phase4("pilot-candidate-intake", replacement, store=store)


def test_candidate_cli_entry_chain(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_path = tmp_path / "cli-store"
    input_path = tmp_path / "input.json"
    commands = [
        ("pilot-start", {
            "batch_id": "phase4-pilot-001", "pilot_start_at": "2026-09-13T12:00:00+08:00",
            "target_real_cases": 10, "grace_period_days": 7, "synthetic": True,
            "real_intake_enabled": False,
        }),
        ("pilot-candidate-intake", intake_payload()),
        ("pilot-candidate-list", {"batch_id": "phase4-pilot-001"}),
    ]
    outputs = []
    for command, payload in commands:
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        assert main([command, "--input", str(input_path), "--store", str(store_path),
                     "--repository-root", str(ROOT), "--synthetic", "--json"]) == 0
        outputs.append(json.loads(capsys.readouterr().out))
    assert all(item["status"] == "ok" for item in outputs)
    assert outputs[-1]["data"]["candidate_total"] == 1
