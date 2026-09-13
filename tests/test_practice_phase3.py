from __future__ import annotations

import json
from pathlib import Path

import pytest

from mingli.contracts import digest
from mingli.practice_phase3 import POOLS, dispatch_phase3, validate_scorable_claim, visible_input
from mingli.training import TrainingError, TrainingStore
from mingli.training_cli import main


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-13T12:00:00+08:00"
MATURE = "2026-11-02T12:00:00+08:00"
PAST = "2026-08-01T00:00:00+08:00/2026-08-31T23:59:59+08:00"
FUTURE = "2026-10-01T00:00:00+08:00/2026-10-31T23:59:59+08:00"


def case(pool="L2", case_id="phase3-fixture"):
    return {
        "case_id": case_id, "synthetic": True, "evidence_level": "L0", "simulated_validation_track": POOLS[pool],
        "registered_at": NOW, "question": "离线岗位面谈通知验收",
        "outcome_hidden_from_prediction": pool == "L2",
        "sources": [{"source_id": "basis", "role": "independent", "text": "离线规则依据", "available_at": NOW}],
        "given_facts": [{"fact_id": "given", "text": "你正在求职", "available_at": NOW}],
        "pilot_batch_id": "pilot-10-v1", "case_role": "pilot_evaluation",
        "consent": {"status": "synthetic_not_applicable", "analysis": False, "storage": False, "followup": False, "withdrawal_available": True},
        "hidden_answer_fields": ["interview_notice_received"] if pool != "L3" else [],
        "future_outcome_fields": ["interview_notice_received"] if pool == "L3" else [],
    }


def claim(window=PAST, pool=None):
    pool = pool or ("L3" if window == FUTURE else "L2")
    return {"claim_id": "interview", "predicted_event_or_state": "你收到一次岗位面谈通知", "claim_type": "future_event" if pool == "L3" else "prior_event",
            "domain": "career", "validation_track": POOLS[pool], "predicted_direction": "support", "confidence": 0.5,
            "specificity_level": "bounded", "given_dependency_ids": [], "exclusion_conditions": [],
            "event_window": window, "result_variable": "interview_notice_received", "atomic": True,
            "outcome_criterion": "以窗口内一份岗位面谈通知记录核验", "basis_source_ids": ["basis"]}


def prediction(pool="L2", prediction_id="prediction-one", case_id="phase3-fixture"):
    return {"case_id": case_id, "frozen_at": NOW, "prediction": {
        "prediction_id": prediction_id, "person_case_id": case_id, "scenario_id": "career",
        "engine_version": "synthetic@1", "source_commit_sha": "0" * 40,
        "rule_set_version": "synthetic@1", "knowledge_manifest_sha": "sha256:" + "0" * 64,
        "input_manifest_sha": digest(visible_input(case(pool, case_id))), "generated_at": NOW,
        "prediction_content": "你收到一次岗位面谈通知", "structured_claims": [claim(FUTURE if pool == "L3" else PAST, pool)],
        "confidence": 0.5, "blocked_fields": [], "reality_evidence_visibility": False,
    }}


def observation(prediction_id="prediction-one", evidence_id="notice-record"):
    return {"prediction_id": prediction_id, "evidence_id": evidence_id, "claim_id": "interview",
            "observed_at": "2026-08-20T12:00:00+08:00", "collected_at": "2026-09-14T12:00:00+08:00",
            "event_window": PAST, "source_provenance": "synthetic_fixture", "evidence_quality": "synthetic",
            "fact": "离线样例记录包含一份面谈通知", "synthetic": True}


def decision(status="hit", **changes):
    return {"prediction_id": "prediction-one", "adjudication_id": "decision-one", "claim_id": "interview",
            "outcome_evidence_ids": ["notice-record"], "status": status, "reason": "离线核对通知记录与冻结窗口",
            "adjudicated_at": "2026-09-15T12:00:00+08:00", "verdict": status,
            "timing_verdict": "pending" if status == "pending" else "in_window",
            "direction_verdict": "pending" if status == "pending" else "contradict" if status == "miss" else "support",
            "adjudicator": "synthetic-reviewer-one", "adjudication_status": "single_reviewer", **changes}


@pytest.fixture
def store(tmp_path):
    return TrainingStore(tmp_path / "store", repository_root=ROOT, synthetic=True)


def run(store, command, payload):
    return dispatch_phase3(command, payload, store=store)


def frozen(store, pool="L2"):
    run(store, "case-create", case(pool))
    return run(store, "freeze-prediction", prediction(pool))


@pytest.mark.parametrize("status", ["hit", "miss"])
def test_l2_closed_loop_is_synthetic_and_not_real_accuracy(store, status):
    snapshot = frozen(store)
    assert snapshot["claim_contracts"][0]["scorable"] is True
    outcome = run(store, "outcome-append", observation())
    assert "status" not in outcome["evidence_snapshot"]
    result = run(store, "claim-adjudicate", decision(status))
    assert result["status"] == status
    assert result["accuracy_eligible"] is False
    summary = run(store, "validation-summary", {"as_of": MATURE})
    assert summary["pools"]["L2"]["synthetic_claim_counts"][status] == 1
    assert summary["eligible_sample_count"] == 0
    assert summary["accuracy"] is None and summary["metrics"] is None


def test_l3_pending_cannot_be_adjudicated_early(store):
    frozen(store, "L3")
    summary = run(store, "validation-summary", {"as_of": NOW})
    assert summary["pools"]["L3"]["synthetic_claim_counts"]["pending"] == 1
    assert summary["pools"]["L3"]["synthetic_claim_counts"]["miss"] == 0
    with pytest.raises(TrainingError, match="OUTCOME_PENDING"):
        run(store, "claim-adjudicate", decision())


@pytest.mark.parametrize("changes,reason", [
    ({"predicted_event_or_state": "你有机会，压力大，慢慢稳定"}, "vague"),
    ({"given_dependency_ids": ["given"]}, "given_not_scored"),
    ({"basis_source_ids": ["given"]}, "given_not_scored"),
    ({"predicted_event_or_state": "你正在求职"}, "given_not_scored"),
    ({"predicted_event_or_state": "仅供文化研究与娱乐参考。"}, "disclaimer"),
    ({"predicted_event_or_state": "建议你提前准备面谈"}, "advice"),
    ({"predicted_event_or_state": "注意面谈取消风险"}, "risk"),
    ({"predicted_event_or_state": "你收到面谈通知并且通过面谈"}, "compound"),
    ({"atomic": False}, "compound"),
    ({"event_window": "未来"}, "unbounded_time"),
])
def test_unscorable_contract(changes, reason):
    result = validate_scorable_claim({**claim(), **changes}, case(), generated_at=NOW, frozen_at=NOW)
    assert result["scorable"] is False
    assert reason in result["reasons"]


@pytest.mark.parametrize("pool", ["L0", "L1"])
def test_low_evidence_never_scores(store, pool):
    snapshot = frozen(store, pool)
    assert snapshot["claim_contracts"][0]["scorable"] is False
    with pytest.raises(TrainingError, match="CLAIM_UNSCORABLE"):
        run(store, "claim-adjudicate", decision())


def test_expired_prospective_window_fails_closed(store):
    run(store, "case-create", case("L3"))
    payload = prediction("L3")
    payload["prediction"]["structured_claims"][0]["event_window"] = PAST
    with pytest.raises(TrainingError, match="PROSPECTIVE_WINDOW_NOT_FUTURE"):
        run(store, "freeze-prediction", payload)


def test_append_only_and_revision_preserve_original(store):
    before = frozen(store)
    with pytest.raises(TrainingError, match="DUPLICATE_RECORD"):
        run(store, "freeze-prediction", prediction())
    run(store, "outcome-append", observation())
    with pytest.raises(TrainingError, match="DUPLICATE_RECORD"):
        run(store, "outcome-append", observation())
    run(store, "claim-adjudicate", decision())
    with pytest.raises(TrainingError, match="DUPLICATE_RECORD"):
        run(store, "claim-adjudicate", decision())
    revision = prediction(prediction_id="prediction-revised")
    revision["revision_of"] = "prediction-one"
    run(store, "freeze-prediction", revision)
    shown = run(store, "case-show", {"case_id": "phase3-fixture"})
    assert shown["predictions"][0] == before or shown["predictions"][1] == before
    assert len(shown["predictions"]) == 2


def test_partial_requires_reason_and_case_correct_rejected(store):
    frozen(store)
    run(store, "outcome-append", observation())
    with pytest.raises(TrainingError, match="SCHEMA_INCOMPATIBLE"):
        run(store, "claim-adjudicate", decision("partial", reason=""))
    with pytest.raises(TrainingError, match="INPUT_FIELD_NOT_ALLOWED"):
        run(store, "claim-adjudicate", decision(case_correct=True))


def test_fact_cannot_contain_claim_verdict(store):
    frozen(store)
    with pytest.raises(TrainingError, match="INPUT_FIELD_NOT_ALLOWED"):
        run(store, "outcome-append", {**observation(), "status": "hit"})


def test_empty_pilot_remains_empty_after_synthetic_loop(store):
    frozen(store)
    run(store, "outcome-append", observation())
    run(store, "claim-adjudicate", decision())
    pilot = run(store, "pilot-show", {})
    assert pilot["target_real_cases"] == 10 and len(pilot["slots"]) == 10
    assert pilot["registered_cases"] == pilot["eligible_sample_count"] == 0
    assert pilot["accuracy"] is pilot["metrics"] is None
    assert pilot["status"] == "not_evaluated" and pilot["commercial_release_hold"] == "ACTIVE"
    assert all(slot["case_id"] is None for slot in pilot["slots"])
    assert pilot == json.loads((ROOT / "examples/practice_phase3/pilot_empty.json").read_text(encoding="utf-8"))


def test_l2_requires_blinding_and_synthetic_flag(store):
    with pytest.raises(TrainingError, match="RETROSPECTIVE_BLIND_REQUIRED"):
        run(store, "case-create", {**case(), "outcome_hidden_from_prediction": False})
    with pytest.raises(TrainingError, match="SYNTHETIC_ONLY"):
        run(store, "case-create", {**case(), "synthetic": False})


@pytest.mark.parametrize("pool", ["L2", "L3"])
def test_cli_entrypoint_complete_chain(tmp_path, capsys, pool):
    path = tmp_path / "input.json"
    steps = [("case-create", case(pool)), ("case-show", {"case_id": "phase3-fixture"}),
             ("freeze-prediction", prediction(pool))]
    if pool == "L2":
        steps += [("outcome-append", observation()), ("claim-adjudicate", decision())]
    steps += [("validation-summary", {"as_of": NOW if pool == "L3" else MATURE}), ("pilot-show", {})]
    for command, payload in steps:
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert main([command, "--input", str(path), "--store", str(tmp_path / "store"),
                     "--repository-root", str(ROOT), "--synthetic", "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_l3_mature_claim_and_as_of_receipt_boundary(store):
    frozen(store, "L3")
    evidence = {**observation(), "event_window": FUTURE, "observed_at": "2026-10-20T12:00:00+08:00",
                "collected_at": "2026-11-01T12:00:00+08:00"}
    run(store, "outcome-append", evidence)
    run(store, "claim-adjudicate", decision(adjudicated_at=MATURE))
    before = run(store, "validation-summary", {"as_of": NOW})
    after = run(store, "validation-summary", {"as_of": MATURE})
    assert before["pools"]["L3"]["synthetic_claim_counts"]["pending"] == 1
    assert after["pools"]["L3"]["synthetic_claim_counts"]["hit"] == 1
    assert after["accuracy"] is None


def test_adjudication_revision_is_append_only(store):
    frozen(store)
    run(store, "outcome-append", observation())
    original = run(store, "claim-adjudicate", decision())
    with pytest.raises(TrainingError, match="ADJUDICATION_REVISION_REQUIRED"):
        run(store, "claim-adjudicate", decision("partial", adjudication_id="new-decision", adjudicated_at=MATURE))
    amended = decision("partial", adjudication_id="new-decision", adjudicated_at=MATURE, supersedes="decision-one")
    run(store, "claim-adjudicate", amended)
    shown = run(store, "case-show", {"case_id": "phase3-fixture"})
    assert original in shown["claim_adjudications"]
    counts = run(store, "validation-summary", {"as_of": MATURE})["pools"]["L2"]["synthetic_claim_counts"]
    assert counts["partial"] == 1 and counts["hit"] == 0


@pytest.mark.parametrize("text", ["你收到面谈通知、通过面谈", "你收到通知。你通过面谈。", "你会得到改善"])
def test_undeclared_compound_and_generic_text_are_unscorable(text):
    contract = validate_scorable_claim({**claim(), "predicted_event_or_state": text}, case(), generated_at=NOW, frozen_at=NOW)
    assert contract["scorable"] is False


def test_adjudication_rejects_evidence_collected_later(store):
    frozen(store)
    run(store, "outcome-append", observation())
    with pytest.raises(TrainingError, match="INVALID_ADJUDICATION_TIME"):
        run(store, "claim-adjudicate", decision(adjudicated_at="2026-09-13T13:00:00+08:00"))


def test_integrity_fail_closed_on_modified_prediction(store):
    frozen(store)
    path = store._path("validation_prediction", "prediction-one")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["prediction_snapshot"]["prediction_content"] = "替换原预测"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TrainingError, match="RECORD_INTEGRITY_ERROR"):
        run(store, "case-show", {"case_id": "phase3-fixture"})


def test_cli_rejects_real_mode_before_reading_input(tmp_path, capsys):
    exit_code = main(["case-create", "--input", str(tmp_path / "does-not-exist.json"), "--store", str(tmp_path / "store")])
    assert exit_code == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "SYNTHETIC_ONLY"


@pytest.mark.parametrize("field,value,error", [
    ("generated_at", "2026-09-12T12:00:00+08:00", "INVALID_TIME_ORDER"),
    ("reality_evidence_visibility", True, "FEEDBACK_VISIBLE"),
])
def test_prediction_temporal_and_feedback_gate(store, field, value, error):
    run(store, "case-create", case())
    payload = prediction()
    payload["prediction"][field] = value
    with pytest.raises(TrainingError, match=error):
        run(store, "freeze-prediction", payload)


def test_four_pools_are_reported_separately(store):
    for pool in ("L0", "L1", "L2", "L3"):
        case_id = "synthetic-pool-" + pool
        run(store, "case-create", case(pool, case_id))
        run(store, "freeze-prediction", prediction(pool, "prediction-" + pool, case_id))
    summary = run(store, "validation-summary", {"as_of": NOW})
    assert summary["pooled_accuracy_allowed"] is False
    assert summary["pools"]["L0"]["synthetic_claim_counts"]["unscorable"] == 1
    assert summary["pools"]["L1"]["synthetic_claim_counts"]["unscorable"] == 1
    assert summary["pools"]["L2"]["synthetic_claim_counts"]["missing"] == 1
    assert summary["pools"]["L3"]["synthetic_claim_counts"]["pending"] == 1
    assert all(pool["accuracy"] is None for pool in summary["pools"].values())


def test_default_blind_case_does_not_expose_target_answer():
    visible = json.dumps(visible_input(case()), ensure_ascii=False)
    assert "收到面谈通知" not in visible


@pytest.mark.parametrize("known", ["你已经收到面谈通知", "你已获得面试邀请", "你曾经收到正式面试通知"])
def test_near_synonymous_given_is_not_independent(known):
    contaminated = case()
    contaminated["given_facts"][0]["text"] = known
    result = validate_scorable_claim(claim(), contaminated, generated_at=NOW, frozen_at=NOW)
    assert result["scorable"] is False
    assert "given_not_scored" in result["reasons"]


def test_claim_contract_contains_event_semantics_and_derived_scorable(store):
    record = frozen(store)
    contract = record["claim_contracts"][0]
    required = {"claim_id", "domain", "claim_type", "validation_track", "predicted_event_or_state",
                "predicted_direction", "event_window", "confidence", "specificity_level",
                "given_dependency_ids", "exclusion_conditions", "basis_source_ids", "scorable"}
    assert required <= set(contract)
    assert contract["claim_type"] == "prior_event"


def test_case_contract_has_separated_slots_and_visible_hash(store):
    record = run(store, "case-create", case())
    assert {"pilot_batch_id", "case_role", "consent", "given_facts", "hidden_answer_fields",
            "future_outcome_fields", "visible_input_hash"} <= set(record)
    before = record["visible_input_hash"]
    assert before == digest(visible_input(case()))
    metadata_change = {**case(), "pilot_batch_id": "other-batch", "hidden_answer_fields": ["another_empty_slot"]}
    assert digest(visible_input(metadata_change)) == before
    run(store, "freeze-prediction", prediction())
    run(store, "outcome-append", observation())
    run(store, "claim-adjudicate", decision())
    assert run(store, "case-show", {"case_id": record["case_id"]})["case"]["visible_input_hash"] == before


def test_adjudication_contract_includes_reviewer_and_semantic_verdict(store):
    frozen(store)
    run(store, "outcome-append", observation())
    result = run(store, "claim-adjudicate", decision())
    assert {"verdict", "timing_verdict", "direction_verdict", "adjudicator", "adjudication_status"} <= set(result)
    assert result["adjudication_status"] == "single_reviewer"


def test_validation_summary_contains_required_real_metrics_and_separate_pools(store):
    frozen(store)
    report = run(store, "validation-summary", {"as_of": NOW})
    assert report["l0_synthetic_count"] == report["cases"]["l0_synthetic"] == 1
    for name in ("l1_historical_count", "l2_retrospective_count", "l3_prospective_count", "prospective_pending_count"):
        assert report[name] == 0
    assert report["public_accuracy_claim_allowed"] is False
    assert {"total", "l0_synthetic", "l1_historical", "l2_retrospective", "l3_prospective", "pending", "development", "pilot_evaluation"} <= set(report["cases"])
    assert all(report["claims"][name] == 0 for name in ("scorable", "hit", "partial", "miss", "unverifiable"))
    for key in ("retrospective_validation", "prospective_validation"):
        assert {"total_cases", "eligible_cases", "scorable_claims", "by_domain", "by_claim_type", "hit", "partial", "miss", "unverifiable"} <= set(report[key])
    assert report["retrospective_validation"]["confidence_calibration_status"] == "insufficient_sample"
    assert {"pending", "lost", "refused", "missing"} <= set(report["prospective_validation"])
    assert "overall_accuracy" not in report


@pytest.mark.parametrize("field", ["domain", "validation_track", "predicted_direction", "confidence", "specificity_level", "given_dependency_ids", "exclusion_conditions"])
def test_required_claim_semantics_cannot_be_omitted(field):
    payload = claim()
    del payload[field]
    with pytest.raises(TrainingError, match="SCHEMA_INCOMPATIBLE"):
        validate_scorable_claim(payload, case(), generated_at=NOW, frozen_at=NOW)


@pytest.mark.parametrize("field,value", [
    ("hidden_answer_fields", [{"field_id": "interview_notice_received", "answer": "hit"}]),
    ("future_outcome_fields", ["你收到面谈通知"]),
    ("consent", {"status": "granted", "analysis": True, "storage": True, "followup": True, "withdrawal_available": True}),
])
def test_intake_rejects_answer_contents_and_real_consent(store, field, value):
    with pytest.raises(TrainingError):
        run(store, "case-create", {**case(), field: value})


def test_prediction_rejects_hash_that_includes_hidden_or_feedback_data(store):
    record = run(store, "case-create", case())
    payload = prediction()
    payload["prediction"]["input_manifest_sha"] = digest({**visible_input(case()), "feedback": "命中"})
    with pytest.raises(TrainingError, match="VISIBLE_INPUT_HASH_MISMATCH"):
        run(store, "freeze-prediction", payload)
    assert record["visible_input_hash"] == digest(visible_input(case()))


def test_given_answer_cannot_be_disguised_as_independent_source():
    contaminated = case()
    contaminated["sources"][0]["text"] = "你已经收到面谈通知"
    contract = validate_scorable_claim(claim(), contaminated, generated_at=NOW, frozen_at=NOW)
    assert contract["scorable"] is False
    assert "given_not_scored" in contract["reasons"]


@pytest.mark.parametrize("changes,error", [
    ({"verdict": "miss"}, "VERDICT_STATUS_MISMATCH"),
    ({"adjudication_status": "reviewed_consensus"}, "INDEPENDENT_REVIEW_NOT_IMPLEMENTED"),
    ({"timing_verdict": "out_of_window"}, "HIT_VERDICT_CONFLICT"),
])
def test_adjudication_cannot_forge_semantics_or_review_status(store, changes, error):
    frozen(store)
    run(store, "outcome-append", observation())
    with pytest.raises(TrainingError, match=error):
        run(store, "claim-adjudicate", decision(**changes))


@pytest.mark.parametrize("track", ["L2", "L3"])
def test_synthetic_retrospective_and_prospective_remain_actual_l0(store, track):
    record = frozen(store, track)
    actual_case = run(store, "case-show", {"case_id": "phase3-fixture"})["case"]
    assert record["evidence_level"] == actual_case["evidence_level"] == "L0"
    assert actual_case["simulated_validation_track"] == POOLS[track]
    summary = run(store, "validation-summary", {"as_of": NOW})
    assert summary["l0_synthetic_count"] == summary["cases"]["l0_synthetic"] == 1
    assert summary["l2_retrospective_count"] == summary["l3_prospective_count"] == 0
    assert summary["synthetic_engineering"]["by_simulated_track"][POOLS[track]]["simulated_cases"] == 1
    with pytest.raises(TrainingError, match="SYNTHETIC_EVIDENCE_LEVEL_REQUIRED"):
        run(store, "case-create", {**case(track, "illegal-case"), "evidence_level": track})
