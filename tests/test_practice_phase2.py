from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mingli.contracts import get_schema
from mingli.practice_cycle import replay_practice, run_practice
from mingli.practice_phase2 import (
    RealCaseLearningV2Error,
    create_blind_review,
    qualify_prospective_case,
    run_behavioral_regression,
    show_blind_review,
    submit_blind_review,
    summarize_blind_reviews,
    summarize_prospective_cases,
)
from mingli.real_case_learning_v2 import (
    anonymize_person_case,
    build_learning_case,
    record_future_outcome,
)
from mingli.training import TrainingError, TrainingStore
from mingli.training_cli import main


ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-09-13T12:00:00+08:00"
CASE_ID = "person:" + "d" * 64
DISCLAIMER = "仅供文化研究与娱乐参考。"


def store(tmp_path: Path) -> TrainingStore:
    return TrainingStore(tmp_path / "store", repository_root=ROOT, synthetic=True)


def practice_payload(*, run_id: str, rule_version: str, text: str) -> dict[str, object]:
    return {
        "synthetic": True,
        "case_id": CASE_ID,
        "run_id": run_id,
        "as_of": AS_OF,
        "recorded_at": AS_OF if run_id == "phase2-base" else "2026-09-14T12:00:00+08:00",
        "question": "看工作",
        "rule_version": rule_version,
        "known_facts": [
            {"source_id": "employment", "text": "你在职", "available_at": AS_OF}
        ],
        "bases": [
            {
                "basis_id": f"fixture-{run_id}",
                "kind": "synthetic_rule_fixture",
                "available_at": AS_OF,
                "supported_claims": [
                    {
                        "text": text,
                        "window": {"text": "2026年10月", "intent": "future"},
                        "confidence": 0.5,
                        "required_fact_ids": [],
                    }
                ],
            }
        ],
        "claims": [
            {
                "claim_id": "career-interview",
                "text": text,
                "window": {"text": "2026年10月", "intent": "future"},
                "confidence": 0.5,
                "basis_id": f"fixture-{run_id}",
                "known_fact_ids": [],
            }
        ],
    }


def paired_runs(tmp_path: Path) -> TrainingStore:
    result = store(tmp_path)
    run_practice(
        practice_payload(
            run_id="phase2-base",
            rule_version="synthetic-career@1",
            text="你在2026年10月可能有机会收到岗位面谈安排。",
        ),
        result,
    )
    replay_practice(
        {
            "source_run_id": "phase2-base",
            "run_id": "phase2-candidate",
            "rule_version": "synthetic-career@2",
            "recorded_at": "2026-09-14T12:00:00+08:00",
            "bases": practice_payload(
                run_id="phase2-candidate",
                rule_version="synthetic-career@2",
                text="你在2026年10月可能收到一次岗位面谈安排，结果以正式通知为准。",
            )["bases"],
            "claims": practice_payload(
                run_id="phase2-candidate",
                rule_version="synthetic-career@2",
                text="你在2026年10月可能收到一次岗位面谈安排，结果以正式通知为准。",
            )["claims"],
        },
        result,
    )
    return result


def review_create_payload(review_id: str = "review:phase2:001", seed: str = "blind-seed") -> dict[str, object]:
    return {
        "review_id": review_id,
        "comparison_id": "comparison:phase2:001",
        "baseline_run_id": "phase2-base",
        "candidate_run_id": "phase2-candidate",
        "tier": "paid",
        "created_at": "2026-09-15T00:00:00+08:00",
        "randomization_seed": seed,
    }


def review_submission(
    review: dict[str, object],
    internal: dict[str, object],
    *,
    reviewer_id: str,
    submission_id: str,
) -> dict[str, object]:
    candidate_answer_id = internal["assignment"]["candidate_answer_id"]
    labels = {item["answer_id"]: item["label"] for item in review["answers"]}
    candidate = labels[candidate_answer_id]
    baseline = "B" if candidate == "A" else "A"
    return {
        "review_submission_id": submission_id,
        "review_id": review["review_id"],
        "reviewer_id": reviewer_id,
        "submitted_at": "2026-09-16T00:00:00+08:00",
        "overall_preference": candidate,
        "answers_user_question": candidate,
        "specificity_without_overreach": candidate,
        "time_window_clarity": candidate,
        "unsupported_detail_risk": f"{candidate}_lower",
        "template_or_generic_language": f"{candidate}_lower",
        "human_master_style": candidate,
        "requires_manual_rewrite": baseline,
        "note": "合成盲评格式样例，不是独立真人准确率证据。",
    }


def test_review_schemas_are_packaged() -> None:
    for name in ("blind_review_packet.schema.json", "human_blind_review.schema.json"):
        Draft202012Validator.check_schema(get_schema(name))


def test_blind_packet_is_randomized_redacted_and_never_reads_feedback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    training_store = paired_runs(tmp_path)
    original_list = training_store._list

    def guarded_list(kind: str) -> list[dict[str, object]]:
        if kind in {"feedback", "outcome"}:
            raise AssertionError("blind review must not read feedback or outcomes")
        return original_list(kind)

    monkeypatch.setattr(training_store, "_list", guarded_list)
    public = create_blind_review(review_create_payload(), training_store)
    assert public == show_blind_review("review:phase2:001", training_store)
    encoded = json.dumps(public, ensure_ascii=False, sort_keys=True)
    for hidden in (
        "baseline",
        "candidate",
        "rule_version",
        "prediction_hash",
        "blind-seed",
    ):
        assert hidden not in encoded
    assert public["visible_input"] == {
        "question": "看工作",
        "as_of": AS_OF,
        "given_facts": ["你在职"],
        "visible_input_hash": public["visible_input"]["visible_input_hash"],
    }
    assert [item["label"] for item in public["answers"]] == ["A", "B"]
    assert all(item["text"].endswith(DISCLAIMER) for item in public["answers"])
    internal = training_store._read("review_packet", "review:phase2:001")
    assert set(internal["assignment"].values()) == {
        internal["source_snapshots"]["baseline_answer_id"],
        internal["source_snapshots"]["candidate_answer_id"],
    }
    assert internal["randomization"]["seed_hash"].startswith("sha256:")


def test_review_submit_is_append_only_and_summary_distinguishes_single_and_multi_reviewer(
    tmp_path: Path,
) -> None:
    training_store = paired_runs(tmp_path)
    public = create_blind_review(review_create_payload(), training_store)
    internal = training_store._read("review_packet", "review:phase2:001")
    frozen_paths = list((training_store.root / "runs").glob("*.json")) + list(
        (training_store.root / "review_packets").glob("*.json")
    )
    before = {path: path.read_bytes() for path in frozen_paths}

    first = submit_blind_review(
        review_submission(
            public,
            internal,
            reviewer_id="reviewer:synthetic:one",
            submission_id="review-submission:001",
        ),
        training_store,
    )
    assert first["accuracy_eligible"] is False
    assert before == {path: path.read_bytes() for path in frozen_paths}
    single = summarize_blind_reviews(training_store, review_id="review:phase2:001")
    assert single["totals"] == {
        "baseline_wins": 0,
        "candidate_wins": 1,
        "ties": 0,
        "neither": 0,
    }
    assert single["reviewer_agreement"]["status"] == "single_reviewer"
    assert single["reviewer_agreement"]["agreement_rate"] is None
    assert single["manual_rewrite"]["candidate_required"] == 0
    assert single["manual_rewrite"]["baseline_required"] == 1

    submit_blind_review(
        review_submission(
            public,
            internal,
            reviewer_id="reviewer:synthetic:two",
            submission_id="review-submission:002",
        ),
        training_store,
    )
    multiple = summarize_blind_reviews(training_store, review_id="review:phase2:001")
    assert multiple["totals"]["candidate_wins"] == 2
    assert multiple["reviewer_agreement"]["status"] == "multi_reviewer_agreement"
    assert multiple["reviewer_agreement"]["agreement_rate"] == 1.0
    with pytest.raises(TrainingError, match="REVIEWER_ALREADY_SUBMITTED"):
        duplicate = review_submission(
            public,
            internal,
            reviewer_id="reviewer:synthetic:two",
            submission_id="review-submission:003",
        )
        submit_blind_review(duplicate, training_store)


def test_blind_order_can_flip_and_summary_handles_neither(tmp_path: Path) -> None:
    training_store = paired_runs(tmp_path)
    first = create_blind_review(review_create_payload(), training_store)
    second = create_blind_review(
        review_create_payload("review:phase2:002", "flip-2"), training_store
    )
    first_internal = training_store._read("review_packet", "review:phase2:001")
    second_internal = training_store._read("review_packet", "review:phase2:002")
    first_labels = {item["answer_id"]: item["label"] for item in first["answers"]}
    second_labels = {item["answer_id"]: item["label"] for item in second["answers"]}
    assert first_labels[first_internal["assignment"]["candidate_answer_id"]] != second_labels[
        second_internal["assignment"]["candidate_answer_id"]
    ]

    neutral = review_submission(
        first,
        first_internal,
        reviewer_id="reviewer:synthetic:neutral",
        submission_id="review-submission:neutral",
    )
    neutral["overall_preference"] = "neither"
    submit_blind_review(neutral, training_store)
    summary = summarize_blind_reviews(training_store, review_id="review:phase2:001")
    assert summary["totals"]["neither"] == 1


def test_behavior_regression_covers_six_blocked_and_six_allowed_without_accuracy_claim() -> None:
    payload = json.loads(
        (ROOT / "examples/practice_phase2/behavioral_regressions.json").read_text(
            encoding="utf-8"
        )
    )
    report = run_behavioral_regression(payload)
    assert report["total"] == 12
    assert report["passed"] == 12
    assert report["failed"] == 0
    assert set(report["by_error_family"]) == {
        "time_reference_error",
        "given_leakage_or_given_scoring",
        "career_template_reuse",
        "relationship_overclaim",
        "comment_output_vagueness",
        "paid_output_hallucinated_detail",
    }
    for family in report["by_error_family"].values():
        assert family["blocked_cases"] >= 1
        assert family["allowed_cases"] >= 1
    assert report["accuracy_eligible"] is False
    assert report["real_results"] == {
        "eligible_sample_count": 0,
        "accuracy": None,
        "metrics": None,
        "status": "not_evaluated",
    }
    assert len(report["comparisons"]) == 3
    for comparison in report["comparisons"]:
        assert comparison["baseline"]["gate"] == "blocked"
        assert comparison["candidate"]["gate"] == "allowed"
        assert comparison["human_review_status"] == "not_evaluated"
        assert comparison["accuracy_eligible"] is False


def test_behavior_regression_rejects_any_accuracy_eligible_case() -> None:
    payload = json.loads(
        (ROOT / "examples/practice_phase2/behavioral_regressions.json").read_text(
            encoding="utf-8"
        )
    )
    payload["cases"][0]["accuracy_eligible"] = True
    with pytest.raises(TrainingError, match="BEHAVIOR_NOT_ACCURACY_EVIDENCE"):
        run_behavioral_regression(payload)


def real_case() -> dict[str, object]:
    person_case_id = anonymize_person_case(
        "synthetic-phase2-person", project_salt="synthetic-phase2-contract-salt"
    )
    scenario_id = "career:synthetic:phase2"
    intake = {
        "person_case_id": person_case_id,
        "birth_input": {
            "birth_date": "1990-03-15",
            "birth_time": "10:30",
            "location_precision": "city",
            "gender": "female",
            "calendar": "solar",
            "timezone": "Asia/Shanghai",
            "true_solar_time": False,
            "source": "synthetic_contract_fixture",
            "confirmation_status": "confirmed",
        },
        "consent": {
            "consent_status": "granted",
            "consent_scope": ["research", "benchmark", "training"],
            "consent_recorded_at": "2026-01-01T00:00:00Z",
            "consent_record_ref": "consent:synthetic-phase2",
            "withdrawal_supported": True,
            "research_use_allowed": True,
            "benchmark_use_allowed": True,
            "publication_use_allowed": False,
            "raw_data_retention_policy": "controlled_off_git",
        },
        "case_metadata": {
            "collection_channel": "synthetic_contract_test",
            "collector_role": "test-operator",
            "created_at": "2026-01-01T00:00:00Z",
            "source_provenance": "synthetic_contract_fixture",
            "conflict_status": "none",
            "completeness_status": "complete",
        },
        "scenarios": [
            {
                "scenario_id": scenario_id,
                "scenario_type": "career_exam",
                "target_period": "2026",
                "question_scope": "bounded_exam_stage",
                "known_at_prediction_time": True,
                "excluded_future_information": [],
            }
        ],
    }
    prediction = {
        "prediction_id": "prediction:synthetic:phase2",
        "person_case_id": person_case_id,
        "scenario_id": scenario_id,
        "engine_version": "2.0.0",
        "source_commit_sha": "a" * 40,
        "rule_set_version": "synthetic-rules@2.0.0",
        "knowledge_manifest_sha": "sha256:" + "1" * 64,
        "input_manifest_sha": "sha256:" + "2" * 64,
        "generated_at": "2026-02-01T00:00:00Z",
        "prediction_content": "Synthetic contract fixture: bounded career state.",
        "structured_claims": [
            {
                "claim_id": "claim:career:phase2",
                "scope": "career:2026-h2",
                "domain": "career",
                "time_window": "2026-07-01T00:00:00Z/2026-12-31T23:59:59Z",
                "claim_type": "state",
                "predicted_direction": "support",
                "predicted_event_or_state": "bounded_supportive_tendency",
                "confidence": 0.6,
                "specificity_level": "bounded",
                "exclusion_conditions": [],
                "rule_ids": ["rule:synthetic:career:phase2"],
            }
        ],
        "confidence": 0.6,
        "blocked_fields": [],
        "reality_evidence_visibility": False,
        "prediction_validity": "not_evaluated",
    }
    return build_learning_case(
        intake,
        chart_snapshot={
            "schema_version": "synthetic-chart-snapshot@2.0",
            "prediction_validity": "not_evaluated",
        },
        original_question="Synthetic contract question.",
        prediction_time_reality_context={
            "known_at": "2026-02-01T00:00:00Z",
            "facts": {},
        },
        prediction=prediction,
        frozen_at="2026-02-01T00:01:00Z",
        synthetic=True,
    )


def future_evidence(case: dict[str, object], *, evidence_id: str, observed_at: str) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "person_case_id": case["person_case_id"],
        "scenario_id": case["scenario_id"],
        "claim_id": "claim:career:phase2",
        "scope": "career:2026-h2",
        "event_window": "2026-07-01T00:00:00Z/2026-12-31T23:59:59Z",
        "observed_at": observed_at,
        "collected_at": observed_at,
        "source_provenance": "synthetic_contract_fixture",
        "evidence_quality": "high",
        "direction": "support",
        "verified": True,
        "synthetic": True,
    }


def test_prospective_qualification_fails_closed_without_consent_or_freeze() -> None:
    case = real_case()
    no_consent = deepcopy(case)
    no_consent["consent"]["status"] = "revoked"
    result = qualify_prospective_case(no_consent, evaluated_at="2026-03-01T00:00:00Z")
    assert result["qualification_checks"]["consent_granted"] is False
    assert result["accuracy_eligible"] is False
    assert result["status"] == "not_evaluated"

    no_freeze = deepcopy(case)
    del no_freeze["prediction_snapshot"]
    result = qualify_prospective_case(no_freeze, evaluated_at="2026-03-01T00:00:00Z")
    assert result["qualification_checks"]["frozen_prediction_present"] is False
    assert result["accuracy_eligible"] is False


def test_prospective_feedback_chronology_pending_and_append_only() -> None:
    case = real_case()
    pending = qualify_prospective_case(case, evaluated_at="2026-03-01T00:00:00Z")
    assert pending["outcome_counts"]["pending"] == 1
    assert pending["accuracy_eligible"] is False
    assert pending["qualification_basis"]["input"]["as_of"] == "2026-02-01T00:00:00Z"
    assert pending["qualification_basis"]["prediction"]["claim_ids"] == [
        "claim:career:phase2"
    ]
    with pytest.raises(RealCaseLearningV2Error, match="FUTURE_OUTCOME_NOT_FUTURE"):
        record_future_outcome(
            case,
            future_evidence(
                case,
                evidence_id="outcome:too-early",
                observed_at="2026-02-01T00:00:30Z",
            ),
        )

    first = record_future_outcome(
        case,
        future_evidence(
            case,
            evidence_id="outcome:phase2:one",
            observed_at="2026-12-31T00:00:00Z",
        ),
    )
    second = record_future_outcome(
        first,
        future_evidence(
            first,
            evidence_id="outcome:phase2:two",
            observed_at="2026-12-31T01:00:00Z",
        ),
    )
    assert case["future_outcomes"] == []
    assert len(first["future_outcomes"]) == 1
    assert len(second["future_outcomes"]) == 2


def test_replay_still_cannot_read_feedback_and_real_results_remain_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    training_store = paired_runs(tmp_path)
    original_list = training_store._list

    def guarded_list(kind: str) -> list[dict[str, object]]:
        if kind in {"feedback", "outcome"}:
            raise AssertionError("replay must not read feedback or outcomes")
        return original_list(kind)

    monkeypatch.setattr(training_store, "_list", guarded_list)
    replay_practice(
        {
            "source_run_id": "phase2-base",
            "run_id": "phase2-candidate-2",
            "rule_version": "synthetic-career@3",
            "recorded_at": "2026-09-16T12:00:00+08:00",
        },
        training_store,
    )
    summary = summarize_prospective_cases(
        {"evaluated_at": "2026-03-01T00:00:00Z", "cases": [real_case()]}
    )
    assert summary["product_quality"] == {
        "source": "human_blind_review",
        "included_in_real_accuracy": False,
    }
    assert summary["qualification_contract"]["record_source"] == "real_case_learning_v2"
    assert summary["qualification_contract"]["outcome_time_fields"] == {
        "event_window": "frozen claim window",
        "observed_at": "event observed or received time",
        "collected_at": "evidence recorded time",
    }
    assert summary["real_results"]["eligible_sample_count"] == 0
    assert summary["real_results"]["accuracy"] is None
    assert summary["real_results"]["metrics"] is None
    assert summary["real_results"]["status"] == "not_evaluated"
    assert summary["commercial_release_hold"] == "ACTIVE"


def invoke(tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str, input_path: Path) -> tuple[int, dict[str, object]]:
    code = main(
        [
            command,
            "--input",
            str(input_path),
            "--store",
            str(tmp_path / "cli-store"),
            "--repository-root",
            str(ROOT),
            "--synthetic",
            "--json",
        ]
    )
    return code, json.loads(capsys.readouterr().out)


def test_phase2_cli_entry_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    examples = ROOT / "examples/practice_phase2"
    assert invoke(tmp_path, capsys, "practice-run", ROOT / "examples/practice_cycle/run.json")[0] == 0
    assert invoke(tmp_path, capsys, "practice-replay", ROOT / "examples/practice_cycle/replay.json")[0] == 0
    for command, name in (
        ("review-create", "review_create.json"),
        ("review-show", "review_show.json"),
        ("review-submit", "review_submit.json"),
        ("review-summary", "review_summary.json"),
        ("behavior-regression", "behavioral_regressions.json"),
        ("real-case-qualify", "prospective_empty.json"),
    ):
        code, result = invoke(tmp_path, capsys, command, examples / name)
        assert code == 0, result
        assert result["status"] == "ok"
