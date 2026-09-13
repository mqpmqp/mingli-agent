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
NOW = "2026-09-13T12:00:00+08:00"
PAST = "2026-08-01T00:00:00+08:00/2026-08-31T23:59:59+08:00"
FUTURE = "2026-10-01T00:00:00+08:00/2026-10-31T23:59:59+08:00"


@pytest.fixture
def store(tmp_path: Path) -> TrainingStore:
    return TrainingStore(tmp_path / "store", repository_root=ROOT, synthetic=True)


def start_payload() -> dict[str, object]:
    return {
        "batch_id": "phase4-pilot-001",
        "pilot_start_at": NOW,
        "target_real_cases": 10,
        "grace_period_days": 7,
        "synthetic": True,
        "real_intake_enabled": False,
    }


def screen_payload(
    index: int = 1,
    *,
    consent_granted: bool = True,
    l2: int = 1,
    current: int = 0,
    l3: int = 1,
) -> dict[str, object]:
    total = l2 + current + l3
    return {
        "batch_id": "phase4-pilot-001",
        "screen_id": f"screen-{index:02d}",
        "candidate_case_id": f"synthetic-pilot-{index:02d}",
        "person_case_id": "person:" + f"{index:064x}",
        "source_timestamp": f"2026-09-13T12:{index:02d}:00+08:00",
        "screened_at": f"2026-09-13T13:{index:02d}:00+08:00",
        "synthetic": True,
        "engineering_dry_run": True,
        "consent": {
            "granted": consent_granted,
            "scope": ["deidentified_training_evaluation"] if consent_granted else [],
            "recorded_at": NOW,
            "withdrawal_supported": True,
        },
        "deidentified": True,
        "minimum_input_gate_passed": True,
        "chart_gate_passed": True,
        "freeze_ready": True,
        "claim_counts": {"L2": l2, "current_state": current, "L3": l3, "total": total},
        "case_role": "pilot_evaluation",
        "engine_version": "synthetic@1",
        "source_commit_sha": "0" * 40,
        "rule_set_version": "synthetic@1",
        "input_manifest_sha": "sha256:" + "1" * 64,
        "visible_input_hash": "sha256:" + "2" * 64,
        "prediction_snapshot_hash": "sha256:" + "3" * 64,
    }


def candidate_payload(index: int = 1, *, consent_granted: bool = True) -> dict[str, object]:
    return {
        "batch_id": "phase4-pilot-001",
        "received_at": f"2026-09-13T12:{index:02d}:00+08:00",
        "source_timestamp": f"2026-09-13T12:{index:02d}:00+08:00",
        "source_type": "synthetic_fixture",
        "deidentified_source_fingerprint": "sha256:" + f"{index:064x}",
        "intake_nonce": "sha256:" + f"{index + 100:064x}",
        "proposed_case_id": f"synthetic-pilot-{index:02d}",
        "human": False,
        "synthetic": True,
        "consent_status": "unknown",
        "privacy_status": "pass",
        "input_gate_status": "pass",
    }


def intake_for_screen(
    store: TrainingStore,
    index: int = 1,
    *,
    consent_granted: bool = True,
) -> dict[str, object]:
    return dispatch_phase4(
        "pilot-candidate-intake",
        candidate_payload(index, consent_granted=consent_granted),
        store=store,
    )


def screen_with_intake(
    store: TrainingStore,
    index: int = 1,
    *,
    consent_granted: bool = True,
    l2: int = 1,
    current: int = 0,
    l3: int = 1,
) -> dict[str, object]:
    candidate = intake_for_screen(store, index, consent_granted=consent_granted)
    payload = screen_payload(index, consent_granted=consent_granted, l2=l2, current=current, l3=l3)
    payload["candidate_id"] = candidate["candidate_id"]
    return dispatch_phase4("pilot-screen", payload, store=store)


def phase3_case(track: str, case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "synthetic": True,
        "evidence_level": "L0",
        "simulated_validation_track": "prospective" if track == "L3" else "retrospective_blind",
        "registered_at": NOW,
        "question": "离线 Pilot 工程验收",
        "outcome_hidden_from_prediction": track == "L2",
        "sources": [
            {"source_id": "basis", "role": "independent", "text": "离线规则依据", "available_at": NOW}
        ],
        "given_facts": [{"fact_id": "given", "text": "你正在求职", "available_at": NOW}],
        "pilot_batch_id": "phase4-pilot-001",
        "case_role": "pilot_evaluation",
        "consent": {
            "status": "synthetic_not_applicable",
            "analysis": False,
            "storage": False,
            "followup": False,
            "withdrawal_available": True,
        },
        "hidden_answer_fields": ["interview_notice_received"] if track == "L2" else [],
        "future_outcome_fields": ["interview_notice_received"] if track == "L3" else [],
    }


def phase3_claim(track: str, claim_id: str = "interview") -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "predicted_event_or_state": "你收到一次岗位面谈通知",
        "claim_type": "future_event" if track == "L3" else "prior_event",
        "domain": "career",
        "validation_track": "prospective" if track == "L3" else "retrospective_blind",
        "predicted_direction": "support",
        "confidence": 0.5,
        "specificity_level": "bounded",
        "given_dependency_ids": [],
        "exclusion_conditions": [],
        "event_window": FUTURE if track == "L3" else PAST,
        "result_variable": "interview_notice_received",
        "atomic": True,
        "outcome_criterion": "以窗口内一份岗位面谈通知记录核验",
        "basis_source_ids": ["basis"],
    }


def phase3_prediction(track: str, prediction_id: str, case_id: str) -> dict[str, object]:
    case = phase3_case(track, case_id)
    return {
        "case_id": case_id,
        "frozen_at": NOW,
        "prediction": {
            "prediction_id": prediction_id,
            "person_case_id": case_id,
            "scenario_id": "career",
            "engine_version": "synthetic@1",
            "source_commit_sha": "0" * 40,
            "rule_set_version": "synthetic@1",
            "knowledge_manifest_sha": "sha256:" + "0" * 64,
            "input_manifest_sha": digest(visible_input(case)),
            "generated_at": NOW,
            "prediction_content": "你收到一次岗位面谈通知",
            "structured_claims": [phase3_claim(track)],
            "confidence": 0.5,
            "blocked_fields": [],
            "reality_evidence_visibility": False,
        },
    }


def freeze_phase3(store: TrainingStore, track: str = "L3", *, suffix: str = "one") -> dict[str, object]:
    case_id = f"phase4-{track.lower()}-{suffix}"
    dispatch_phase3("case-create", phase3_case(track, case_id), store=store)
    return dispatch_phase3(
        "freeze-prediction",
        phase3_prediction(track, f"prediction-{suffix}", case_id),
        store=store,
    )


def test_empty_pilot_start_and_summary_keep_real_metrics_zero(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["pilot_target"] == 10
    assert summary["registered_real_cases"] == summary["eligible_real_cases"] == 0
    assert summary["screen_failed_real_cases"] == 0
    assert summary["synthetic_real_mix"] is False
    assert summary["no_selective_enrollment"] == "not_evaluated"
    assert summary["accuracy"] is None and summary["status"] == "not_evaluated"
    assert summary["commercial_release_hold"] == "ACTIVE"
    assert all(slot["case_id"] is None for slot in summary["real_slots"])


def test_synthetic_eligible_screen_uses_simulation_slot_only(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    record = screen_with_intake(store)
    assert record["screen_status"] == "synthetic_simulation_eligible"
    assert record["assigned_real_slot"] is None
    assert record["simulated_slot"] == 1
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["registered_real_cases"] == 0
    assert summary["engineering_simulation"]["eligible_screens"] == 1
    assert summary["engineering_simulation"]["simulated_slots_used"] == 1


@pytest.mark.parametrize(
    "counts,reason",
    [
        ((4, 0, 0), "L2_CLAIM_LIMIT"),
        ((0, 3, 0), "CURRENT_STATE_CLAIM_LIMIT"),
        ((0, 0, 4), "L3_CLAIM_LIMIT"),
        ((3, 2, 4), "TOTAL_CLAIM_LIMIT"),
    ],
)
def test_claim_limits_fail_screen_without_consuming_slot(
    store: TrainingStore, counts: tuple[int, int, int], reason: str
) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    record = screen_with_intake(store, l2=counts[0], current=counts[1], l3=counts[2])
    assert record["screen_status"] == "synthetic_screen_fail"
    assert reason in record["failure_reasons"]
    assert record["simulated_slot"] is None


def test_unconsented_case_is_screen_fail_and_next_eligible_gets_first_slot(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    failed = screen_with_intake(store, consent_granted=False)
    enrolled = screen_with_intake(store, 2)
    assert failed["screen_status"] == "synthetic_screen_fail"
    assert "CONSENT_REQUIRED" in failed["failure_reasons"]
    assert enrolled["simulated_slot"] == 1


def test_screen_fail_can_only_be_corrected_by_append_only_superseding_record(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    failed = screen_with_intake(store, consent_granted=False)
    corrected = screen_payload(consent_granted=True)
    corrected["screen_id"] = "screen-01-consented"
    corrected["screened_at"] = "2026-09-13T14:01:00+08:00"
    corrected["supersedes_screen_id"] = failed["screen_id"]
    corrected["candidate_id"] = failed["candidate_id"]
    record = dispatch_phase4("pilot-screen", corrected, store=store)
    assert record["screen_status"] == "synthetic_simulation_eligible"
    assert record["simulated_slot"] == 1
    listed = dispatch_phase4("pilot-list", {"batch_id": "phase4-pilot-001"}, store=store)
    assert len(listed["engineering_simulations"]) == 2


def test_first_ten_simulated_eligible_are_contiguous_and_eleventh_is_full(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    records = [screen_with_intake(store, index) for index in range(1, 12)]
    assert [item["simulated_slot"] for item in records[:10]] == list(range(1, 11))
    assert records[10]["screen_status"] == "synthetic_pilot_full"
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["engineering_simulation"]["no_selective_enrollment"] is True
    assert summary["registered_real_cases"] == 0


def test_out_of_order_eligible_screening_breaks_continuous_enrollment_invariant(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    later = screen_payload(2)
    earlier = screen_payload(1)
    earlier["candidate_id"] = intake_for_screen(store, 1)["candidate_id"]
    later["candidate_id"] = intake_for_screen(store, 2)["candidate_id"]
    dispatch_phase4("pilot-screen", later, store=store)
    dispatch_phase4("pilot-screen", earlier, store=store)
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}, store=store)
    assert summary["engineering_simulation"]["no_selective_enrollment"] is False
    assert summary["engineering_simulation"]["selection_integrity_broken"] is True
    assert summary["registered_real_cases"] == 0


def test_duplicate_candidate_cannot_replace_a_slot(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    first = screen_with_intake(store)
    duplicate = screen_payload(2)
    duplicate["candidate_case_id"] = "synthetic-pilot-01"
    duplicate["person_case_id"] = "person:" + f"{1:064x}"
    duplicate["candidate_id"] = first["candidate_id"]
    duplicate["source_timestamp"] = "2026-09-13T12:01:00+08:00"
    with pytest.raises(TrainingError, match="DUPLICATE_PILOT_CANDIDATE"):
        dispatch_phase4("pilot-screen", duplicate, store=store)


def test_synthetic_mode_rejects_a_false_real_flag(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    candidate = intake_for_screen(store)
    payload = screen_payload()
    payload["candidate_id"] = candidate["candidate_id"]
    payload["synthetic"] = False
    payload["engineering_dry_run"] = False
    with pytest.raises(TrainingError, match="STORE_MODE_MISMATCH"):
        dispatch_phase4("pilot-screen", payload, store=store)


def test_withdrawal_keeps_simulated_slot_reserved_and_is_append_only(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    screen_with_intake(store)
    payload = {
        "batch_id": "phase4-pilot-001",
        "withdrawal_id": "withdrawal-one",
        "person_case_id": "person:" + f"{1:064x}",
        "withdrawn_at": "2026-09-14T12:00:00+08:00",
        "source_withdrawal_ref": "sha256:" + "4" * 64,
        "synthetic": True,
    }
    record = dispatch_phase4("pilot-withdraw", payload, store=store)
    assert record["simulated_slot"] == 1 and record["slot_released"] is False
    with pytest.raises(TrainingError, match="DUPLICATE_WITHDRAWAL"):
        dispatch_phase4("pilot-withdraw", payload, store=store)
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": payload["withdrawn_at"]}, store=store)
    assert summary["engineering_simulation"]["withdrawn"] == 1
    assert summary["registered_real_cases"] == 0


def test_future_maturity_waits_for_explicit_grace_period(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    freeze_phase3(store)
    record = dispatch_phase4(
        "pilot-mature",
        {
            "batch_id": "phase4-pilot-001",
            "maturity_id": "maturity-pending",
            "prediction_id": "prediction-one",
            "claim_id": "interview",
            "as_of": "2026-11-05T12:00:00+08:00",
            "resolution": "pending",
            "synthetic": True,
        },
        store=store,
    )
    assert record["maturity_status"] == "pending"
    assert record["maturity_at"] == "2026-11-07T23:59:59+08:00"
    summary = dispatch_phase4(
        "pilot-summary",
        {"batch_id": "phase4-pilot-001", "as_of": "2026-11-05T12:00:00+08:00"},
        store=store,
    )
    assert summary["engineering_simulation"]["L3"]["pending"] == 1
    assert summary["engineering_simulation"]["L3"]["missing"] == 0


def test_mature_without_feedback_can_be_lost_but_never_auto_miss(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    freeze_phase3(store)
    base = {
        "batch_id": "phase4-pilot-001",
        "prediction_id": "prediction-one",
        "claim_id": "interview",
        "as_of": "2026-11-08T12:00:00+08:00",
        "synthetic": True,
    }
    with pytest.raises(TrainingError, match="AUTO_MISS_FORBIDDEN"):
        dispatch_phase4(
            "pilot-mature",
            {**base, "maturity_id": "maturity-miss", "resolution": "miss"},
            store=store,
        )
    record = dispatch_phase4(
        "pilot-mature",
        {**base, "maturity_id": "maturity-lost", "resolution": "lost_to_followup"},
        store=store,
    )
    assert record["maturity_status"] == "lost_to_followup"
    summary = dispatch_phase4("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": base["as_of"]}, store=store)
    assert summary["engineering_simulation"]["L3"]["lost_to_followup"] == 1
    assert summary["engineering_simulation"]["L3"]["miss"] == 0
    assert summary["engineering_simulation"]["L3"]["missing"] == 0


def test_mature_with_outcome_is_separate_from_quality_feedback(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    freeze_phase3(store)
    dispatch_phase3(
        "outcome-append",
        {
            "prediction_id": "prediction-one",
            "evidence_id": "future-evidence",
            "claim_id": "interview",
            "event_window": FUTURE,
            "observed_at": "2026-10-20T12:00:00+08:00",
            "collected_at": "2026-11-08T10:00:00+08:00",
            "source_provenance": "synthetic_fixture",
            "evidence_quality": "synthetic",
            "fact": "离线样例记录包含一份面谈通知",
            "synthetic": True,
        },
        store=store,
    )
    maturity = dispatch_phase4(
        "pilot-mature",
        {
            "batch_id": "phase4-pilot-001",
            "maturity_id": "maturity-feedback",
            "prediction_id": "prediction-one",
            "claim_id": "interview",
            "as_of": "2026-11-08T12:00:00+08:00",
            "resolution": "with_feedback",
            "synthetic": True,
        },
        store=store,
    )
    quality = dispatch_phase4(
        "pilot-quality-append",
        {
            "batch_id": "phase4-pilot-001",
            "quality_feedback_id": "quality-one",
            "prediction_id": "prediction-one",
            "collected_at": "2026-11-08T12:30:00+08:00",
            "labels": ["GOOD_STYLE", "TOO_VERBOSE"],
            "raw_feedback_excerpt": "表达自然，但略长。",
            "synthetic": True,
        },
        store=store,
    )
    assert maturity["maturity_status"] == "matured_with_feedback"
    assert "verdict" not in quality and "result_candidate" not in quality
    summary = dispatch_phase4(
        "pilot-summary",
        {"batch_id": "phase4-pilot-001", "as_of": "2026-11-08T13:00:00+08:00"},
        store=store,
    )
    assert summary["engineering_simulation"]["quality_feedback"]["GOOD_STYLE"] == 1
    assert summary["engineering_simulation"]["quality_feedback"]["TOO_VERBOSE"] == 1


def test_quality_feedback_is_append_only_and_cannot_smuggle_a_verdict(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    freeze_phase3(store, "L2")
    payload = {
        "batch_id": "phase4-pilot-001",
        "quality_feedback_id": "quality-one",
        "prediction_id": "prediction-one",
        "collected_at": "2026-09-14T12:00:00+08:00",
        "labels": ["GOOD_STYLE"],
        "raw_feedback_excerpt": "风格可用。",
        "synthetic": True,
    }
    dispatch_phase4("pilot-quality-append", payload, store=store)
    with pytest.raises(TrainingError, match="DUPLICATE_RECORD"):
        dispatch_phase4("pilot-quality-append", payload, store=store)
    with pytest.raises(TrainingError, match="INPUT_FIELD_NOT_ALLOWED"):
        dispatch_phase4(
            "pilot-quality-append",
            {**payload, "quality_feedback_id": "quality-two", "verdict": "hit"},
            store=store,
        )


def test_style_can_be_good_while_prediction_result_is_miss(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    freeze_phase3(store, "L2")
    dispatch_phase3(
        "outcome-append",
        {
            "prediction_id": "prediction-one",
            "evidence_id": "miss-evidence",
            "claim_id": "interview",
            "event_window": PAST,
            "observed_at": "2026-08-20T12:00:00+08:00",
            "collected_at": "2026-09-14T12:00:00+08:00",
            "source_provenance": "synthetic_fixture",
            "evidence_quality": "synthetic",
            "fact": "离线事实记录明确没有收到面谈通知",
            "synthetic": True,
        },
        store=store,
    )
    dispatch_phase3(
        "claim-adjudicate",
        {
            "prediction_id": "prediction-one",
            "adjudication_id": "miss-decision",
            "claim_id": "interview",
            "outcome_evidence_ids": ["miss-evidence"],
            "status": "miss",
            "reason": "离线事实与冻结事件方向相反",
            "adjudicated_at": "2026-09-15T12:00:00+08:00",
            "verdict": "miss",
            "timing_verdict": "in_window",
            "direction_verdict": "contradict",
            "adjudicator": "synthetic-reviewer-one",
            "adjudication_status": "single_reviewer",
        },
        store=store,
    )
    dispatch_phase4(
        "pilot-quality-append",
        {
            "batch_id": "phase4-pilot-001",
            "quality_feedback_id": "good-style-miss",
            "prediction_id": "prediction-one",
            "collected_at": "2026-09-15T12:30:00+08:00",
            "labels": ["GOOD_STYLE"],
            "raw_feedback_excerpt": "表达很自然，但事实不符。",
            "synthetic": True,
        },
        store=store,
    )
    summary = dispatch_phase4(
        "pilot-summary",
        {"batch_id": "phase4-pilot-001", "as_of": "2026-11-08T12:00:00+08:00"},
        store=store,
    )
    assert summary["engineering_simulation"]["L2"]["miss"] == 1
    assert summary["engineering_simulation"]["quality_feedback"]["GOOD_STYLE"] == 1


def test_feels_accurate_feedback_cannot_become_outcome_evidence(store: TrainingStore) -> None:
    freeze_phase3(store, "L2")
    with pytest.raises(TrainingError, match="QUALITY_FEEDBACK_NOT_OUTCOME"):
        dispatch_phase3(
            "outcome-append",
            {
                "prediction_id": "prediction-one",
                "evidence_id": "style-only",
                "claim_id": "interview",
                "event_window": PAST,
                "observed_at": "2026-08-20T12:00:00+08:00",
                "collected_at": "2026-09-14T12:00:00+08:00",
                "source_provenance": "synthetic_fixture",
                "evidence_quality": "synthetic",
                "fact": "用户感觉很准，也很满意",
                "synthetic": True,
            },
            store=store,
        )


def test_revision_wrapper_preserves_v1_and_requires_reason(store: TrainingStore) -> None:
    dispatch_phase4("pilot-start", start_payload(), store=store)
    original = freeze_phase3(store, "L2")
    case_id = original["case_id"]
    revised = phase3_prediction("L2", "prediction-two", case_id)
    revised["revision_of"] = "prediction-one"
    revised["frozen_at"] = "2026-09-14T12:00:00+08:00"
    revised["prediction"]["generated_at"] = "2026-09-14T12:00:00+08:00"
    with pytest.raises(TrainingError, match="REVISION_REASON_REQUIRED"):
        dispatch_phase4(
            "pilot-revision-freeze",
            {
                "batch_id": "phase4-pilot-001",
                "revision_receipt_id": "revision-receipt-bad",
                "freeze_payload": revised,
                "revision_reason": "",
                "feedback_visibility_at_generation": "hidden",
                "synthetic": True,
            },
            store=store,
        )
    receipt = dispatch_phase4(
        "pilot-revision-freeze",
        {
            "batch_id": "phase4-pilot-001",
            "revision_receipt_id": "revision-receipt-one",
            "freeze_payload": revised,
            "revision_reason": "离线规则版本比较",
            "feedback_visibility_at_generation": "hidden",
            "synthetic": True,
        },
        store=store,
    )
    shown = dispatch_phase3("case-show", {"case_id": case_id}, store=store)
    assert len(shown["predictions"]) == 2
    assert original in shown["predictions"]
    assert receipt["parent_prediction_hash"] == original["canonical_hash"]
    assert receipt["revision_prediction_hash"] != receipt["parent_prediction_hash"]


def test_phase3_enforces_pilot_claim_ceiling(store: TrainingStore) -> None:
    case_id = "phase4-l2-claim-limit"
    dispatch_phase3("case-create", phase3_case("L2", case_id), store=store)
    payload = phase3_prediction("L2", "prediction-limit", case_id)
    payload["prediction"]["structured_claims"] = [
        phase3_claim("L2", f"claim-{index}") for index in range(4)
    ]
    with pytest.raises(TrainingError, match="CLAIM_LIMIT_EXCEEDED"):
        dispatch_phase3("freeze-prediction", payload, store=store)


@pytest.mark.parametrize(
    "track,claim_type,count",
    [("L2", "current_state", 3), ("L3", "future_event", 4)],
)
def test_phase3_enforces_each_pool_ceiling(
    store: TrainingStore, track: str, claim_type: str, count: int
) -> None:
    case_id = f"phase4-{track.lower()}-{claim_type}-limit"
    dispatch_phase3("case-create", phase3_case(track, case_id), store=store)
    payload = phase3_prediction(track, "prediction-limit", case_id)
    claims = []
    for index in range(count):
        item = phase3_claim(track, f"claim-{index}")
        item["claim_type"] = claim_type
        claims.append(item)
    payload["prediction"]["structured_claims"] = claims
    with pytest.raises(TrainingError, match="CLAIM_LIMIT_EXCEEDED"):
        dispatch_phase3("freeze-prediction", payload, store=store)


def test_phase4_cli_entry_loop(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_path = tmp_path / "input.json"
    store_path = tmp_path / "cli-store"
    candidate = candidate_payload()
    steps = [
        ("pilot-start", start_payload()),
        ("pilot-candidate-intake", candidate),
        ("pilot-list", {"batch_id": "phase4-pilot-001"}),
        ("pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": NOW}),
    ]
    screen_added = False
    for command, payload in steps:
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        assert main(
            [
                command,
                "--input",
                str(input_path),
                "--store",
                str(store_path),
                "--repository-root",
                str(ROOT),
                "--synthetic",
                "--json",
            ]
        ) == 0
        output = json.loads(capsys.readouterr().out)
        assert output["status"] == "ok"
        if command == "pilot-candidate-intake":
            screen = screen_payload()
            screen["candidate_id"] = output["data"]["candidate_id"]
            input_path.write_text(json.dumps(screen), encoding="utf-8")
            assert main([
                "pilot-screen", "--input", str(input_path), "--store", str(store_path),
                "--repository-root", str(ROOT), "--synthetic", "--json",
            ]) == 0
            assert json.loads(capsys.readouterr().out)["status"] == "ok"
            screen_added = True
    assert screen_added is True


def test_existing_phase3_pilot_template_remains_unchanged(store: TrainingStore) -> None:
    pilot = dispatch_phase3("pilot-show", {}, store=store)
    assert pilot["target_real_cases"] == 10
    assert pilot["registered_cases"] == 0
    assert pilot["eligible_sample_count"] == 0
    assert pilot["real_intake_enabled"] is False
