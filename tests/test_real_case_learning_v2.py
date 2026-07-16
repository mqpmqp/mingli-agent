from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mingli.contracts import get_schema
from mingli.real_case_learning_v2 import (
    RealCaseLearningV2Error,
    adjudicate_outcome,
    anonymize_person_case,
    build_learning_case,
    build_operator_review_queue,
    build_temporal_partitions,
    record_future_outcome,
    record_prior_event_validation,
    summarize_learning_cases,
    verify_learning_record,
    withdraw_case,
)
from mingli.test_gates import classify_test


SYNTHETIC_SALT = "synthetic-contract-fixture-salt-v2"
SOURCE_SHA = "a" * 40


def intake_record(
    *,
    raw_identifier: str = "synthetic-person-a",
    scenario_id: str = "career:synthetic:001",
) -> dict[str, object]:
    return {
        "person_case_id": anonymize_person_case(raw_identifier, project_salt=SYNTHETIC_SALT),
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
            "consent_recorded_at": "2025-01-01T00:00:00Z",
            "consent_record_ref": "consent:synthetic-contract-only",
            "withdrawal_supported": True,
            "research_use_allowed": True,
            "benchmark_use_allowed": True,
            "publication_use_allowed": False,
            "raw_data_retention_policy": "controlled_off_git",
        },
        "case_metadata": {
            "collection_channel": "synthetic_contract_test",
            "collector_role": "test-operator",
            "created_at": "2025-01-01T00:00:00Z",
            "source_provenance": "synthetic_contract_fixture",
            "conflict_status": "none",
            "completeness_status": "complete",
        },
        "scenarios": [
            {
                "scenario_id": scenario_id,
                "scenario_type": "career_exam",
                "target_period": "2025-2026",
                "question_scope": "bounded_exam_stage",
                "known_at_prediction_time": True,
                "excluded_future_information": [],
            }
        ],
    }


def prediction_record(
    *,
    person_case_id: str,
    scenario_id: str,
    prediction_id: str = "prediction:synthetic:001",
    generated_at: str = "2025-02-01T00:00:00Z",
) -> dict[str, object]:
    return {
        "prediction_id": prediction_id,
        "person_case_id": person_case_id,
        "scenario_id": scenario_id,
        "engine_version": "2.0.0",
        "source_commit_sha": SOURCE_SHA,
        "rule_set_version": "synthetic-rules@2.0.0",
        "knowledge_manifest_sha": "sha256:" + "1" * 64,
        "input_manifest_sha": "sha256:" + "2" * 64,
        "generated_at": generated_at,
        "prediction_content": "Synthetic contract fixture: bounded supportive tendency.",
        "structured_claims": [
            {
                "claim_id": "claim:career:001",
                "scope": "career:2025-h2",
                "domain": "career",
                "time_window": "2025-07-01T00:00:00Z/2025-12-31T23:59:59Z",
                "claim_type": "state",
                "predicted_direction": "support",
                "predicted_event_or_state": "bounded_supportive_tendency",
                "confidence": 0.6,
                "specificity_level": "bounded",
                "exclusion_conditions": [],
                "rule_ids": ["rule:synthetic:career:001"],
            },
            {
                "claim_id": "claim:career:prior:001",
                "scope": "career:prior:2025-01",
                "domain": "career",
                "time_window": "2025-01-01T00:00:00Z/2025-01-31T23:59:59Z",
                "claim_type": "state",
                "predicted_direction": "support",
                "predicted_event_or_state": "bounded_prior_state",
                "confidence": 0.6,
                "specificity_level": "bounded",
                "exclusion_conditions": [],
                "rule_ids": ["rule:synthetic:career:prior:001"],
            },
        ],
        "confidence": 0.6,
        "blocked_fields": [],
        "reality_evidence_visibility": False,
        "prediction_validity": "not_evaluated",
    }


def evidence_record(
    case: dict[str, Any],
    *,
    evidence_id: str,
    observed_at: str,
    collected_at: str,
    direction: str,
    claim_id: str = "claim:career:001",
    scope: str = "career:2025-h2",
    event_window: str = "2025-07-01T00:00:00Z/2025-12-31T23:59:59Z",
    source_provenance: str = "synthetic_contract_fixture",
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "person_case_id": case["person_case_id"],
        "scenario_id": case["scenario_id"],
        "claim_id": claim_id,
        "scope": scope,
        "event_window": event_window,
        "observed_at": observed_at,
        "collected_at": collected_at,
        "source_provenance": source_provenance,
        "evidence_quality": "high",
        "direction": direction,
        "verified": True,
        "synthetic": True,
    }


def learning_case(
    *,
    raw_identifier: str = "synthetic-person-a",
    scenario_id: str = "career:synthetic:001",
    prediction_id: str = "prediction:synthetic:001",
    generated_at: str = "2025-02-01T00:00:00Z",
    frozen_at: str = "2025-02-01T00:01:00Z",
    near_duplicate_fingerprint: str | None = None,
) -> dict[str, Any]:
    intake = intake_record(raw_identifier=raw_identifier, scenario_id=scenario_id)
    prediction = prediction_record(
        person_case_id=str(intake["person_case_id"]),
        scenario_id=scenario_id,
        prediction_id=prediction_id,
        generated_at=generated_at,
    )
    return build_learning_case(
        intake,
        chart_snapshot={
            "schema_version": "synthetic-chart-snapshot@2.0",
            "chart_fingerprint": "sha256:" + "3" * 64,
            "calculation_status": "complete",
            "prediction_validity": "not_evaluated",
        },
        original_question="Synthetic contract question about a bounded exam window.",
        prediction_time_reality_context={
            "known_at": generated_at,
            "facts": {"exam_stage": "preparation", "preparation_months": 6},
            "excluded_future_information": ["future_exam_result"],
        },
        prediction=prediction,
        frozen_at=frozen_at,
        synthetic=True,
        near_duplicate_fingerprint=near_duplicate_fingerprint,
    )


def observed_case(
    *,
    raw_identifier: str,
    scenario_id: str,
    prediction_id: str,
    generated_at: str,
    frozen_at: str,
    observed_at: str,
    collected_at: str,
    near_duplicate_fingerprint: str | None = None,
) -> dict[str, Any]:
    case = learning_case(
        raw_identifier=raw_identifier,
        scenario_id=scenario_id,
        prediction_id=prediction_id,
        generated_at=generated_at,
        frozen_at=frozen_at,
        near_duplicate_fingerprint=near_duplicate_fingerprint,
    )
    return record_future_outcome(
        case,
        evidence_record(
            case,
            evidence_id=f"outcome:{prediction_id}",
            observed_at=observed_at,
            collected_at=collected_at,
            direction="contradict",
        ),
    )


def test_v2_schemas_are_packaged_and_real_case_gate_classifies_test() -> None:
    for name in (
        "real_case_learning_v2_case.schema.json",
        "real_case_learning_v2_partition.schema.json",
        "real_case_learning_v2_withdrawal.schema.json",
    ):
        Draft202012Validator.check_schema(get_schema(name))
    assert classify_test("tests/test_real_case_learning_v2.py::test_contract") == "real_case"


def test_intake_anonymization_context_and_prediction_are_frozen_deterministically() -> None:
    first = learning_case()
    second = learning_case()

    Draft202012Validator(get_schema("real_case_learning_v2_case.schema.json")).validate(first)
    assert first == second
    assert verify_learning_record(first)
    assert first["lifecycle_status"] == "prediction_frozen"
    assert first["storage_boundary"] == "controlled_off_git"
    assert first["synthetic"] is True
    assert first["accuracy_eligible"] is False
    assert first["product_claim_eligible"] is False
    assert first["prediction_validity"] == "not_evaluated"
    assert first["commercial_release_hold"] == "ACTIVE"
    assert first["prediction_snapshot"]["freeze_status"] == "frozen"
    assert first["chart_snapshot"]["canonical_hash"].startswith("sha256:")
    assert first["original_question_snapshot"]["canonical_hash"].startswith("sha256:")
    assert first["prediction_time_reality_snapshot"]["canonical_hash"].startswith("sha256:")
    assert "synthetic-person-a" not in json.dumps(first, sort_keys=True)


def test_fail_closed_on_pii_unsupported_boundaries_and_prediction_reality_visibility() -> None:
    intake = intake_record()
    prediction = prediction_record(
        person_case_id=str(intake["person_case_id"]),
        scenario_id="career:synthetic:001",
    )
    prediction["reality_evidence_visibility"] = True
    with pytest.raises(RealCaseLearningV2Error, match="REALITY_VISIBLE_AT_PREDICTION"):
        build_learning_case(
            intake,
            chart_snapshot={"schema_version": "synthetic-chart-snapshot@2.0", "prediction_validity": "not_evaluated"},
            original_question="Synthetic contract question.",
            prediction_time_reality_context={"known_at": "2025-02-01T00:00:00Z", "facts": {}},
            prediction=prediction,
            frozen_at="2025-02-01T00:01:00Z",
            synthetic=True,
        )

    bad_chart = {"schema_version": "unknown@99", "prediction_validity": "not_evaluated", "name": "Forbidden Name"}
    with pytest.raises(RealCaseLearningV2Error, match="PII_DETECTED|UNSUPPORTED_CHART_SNAPSHOT"):
        build_learning_case(
            intake,
            chart_snapshot=bad_chart,
            original_question="Synthetic contract question.",
            prediction_time_reality_context={"known_at": "2025-02-01T00:00:00Z", "facts": {}},
            prediction=prediction_record(person_case_id=str(intake["person_case_id"]), scenario_id="career:synthetic:001"),
            frozen_at="2025-02-01T00:01:00Z",
            synthetic=True,
        )


def test_prior_event_and_future_outcome_enforce_prediction_time_boundary() -> None:
    case = learning_case()
    prior = evidence_record(
        case,
        evidence_id="prior:synthetic:001",
        observed_at="2025-01-15T00:00:00Z",
        collected_at="2025-01-16T00:00:00Z",
        direction="support",
        claim_id="claim:career:prior:001",
        scope="career:prior:2025-01",
        event_window="2025-01-01T00:00:00Z/2025-01-31T23:59:59Z",
    )
    with_prior = record_prior_event_validation(case, prior)
    assert with_prior["lifecycle_status"] == "prior_event_validated"
    assert len(with_prior["prior_event_validations"]) == 1

    leaked_prior = {**prior, "evidence_id": "prior:leaked", "observed_at": "2025-03-01T00:00:00Z"}
    with pytest.raises(RealCaseLearningV2Error, match="PRIOR_EVENT_AFTER_PREDICTION"):
        record_prior_event_validation(case, leaked_prior)

    mismatched_prior_window = {
        **prior,
        "evidence_id": "prior:mismatched-window",
        "event_window": "2024-01-01T00:00:00Z/2024-01-31T23:59:59Z",
    }
    with pytest.raises(RealCaseLearningV2Error, match="EVENT_WINDOW_MISMATCH"):
        record_prior_event_validation(case, mismatched_prior_window)

    future_window_as_prior = evidence_record(
        case,
        evidence_id="prior:future-window",
        observed_at="2025-01-15T00:00:00Z",
        collected_at="2025-01-16T00:00:00Z",
        direction="support",
    )
    with pytest.raises(RealCaseLearningV2Error, match="PRIOR_EVENT_WINDOW_NOT_PRIOR"):
        record_prior_event_validation(case, future_window_as_prior)

    premature_future = {**prior, "evidence_id": "outcome:premature"}
    with pytest.raises(RealCaseLearningV2Error, match="FUTURE_OUTCOME_NOT_FUTURE"):
        record_future_outcome(case, premature_future)

    pre_freeze_window_as_future = {
        **prior,
        "evidence_id": "outcome:pre-freeze-window",
        "observed_at": "2025-03-01T00:00:00Z",
        "collected_at": "2025-03-02T00:00:00Z",
    }
    with pytest.raises(RealCaseLearningV2Error, match="FUTURE_OUTCOME_WINDOW_NOT_FUTURE"):
        record_future_outcome(case, pre_freeze_window_as_future)


def test_future_reality_hard_override_is_claim_and_scope_specific() -> None:
    case = learning_case()
    wrong_scope = evidence_record(
        case,
        evidence_id="outcome:wrong-scope",
        observed_at="2025-12-31T00:00:00Z",
        collected_at="2026-01-02T00:00:00Z",
        direction="contradict",
        scope="career:2026-h1",
    )
    with pytest.raises(RealCaseLearningV2Error, match="CLAIM_SCOPE_MISMATCH"):
        record_future_outcome(case, wrong_scope)

    outcome = evidence_record(
        case,
        evidence_id="outcome:synthetic:001",
        observed_at="2025-12-31T00:00:00Z",
        collected_at="2026-01-02T00:00:00Z",
        direction="contradict",
    )
    observed = record_future_outcome(case, outcome)
    resolution = observed["future_outcomes"][0]["reality_resolution"]
    assert resolution["claim_id"] == "claim:career:001"
    assert resolution["scope"] == "career:2025-h2"
    assert resolution["status"] == "resolved_by_reality_override"
    assert resolution["hard_override_direction"] == "contradict"
    assert observed["prediction_validity"] == "not_evaluated"


def test_miss_creates_negative_archive_revision_and_review_only_demotion() -> None:
    case = observed_case(
        raw_identifier="synthetic-person-a",
        scenario_id="career:synthetic:001",
        prediction_id="prediction:synthetic:001",
        generated_at="2025-02-01T00:00:00Z",
        frozen_at="2025-02-01T00:01:00Z",
        observed_at="2025-12-31T00:00:00Z",
        collected_at="2026-01-02T00:00:00Z",
    )
    adjudicated = adjudicate_outcome(
        case,
        adjudication_id="adjudication:synthetic:001",
        claim_id="claim:career:001",
        scope="career:2025-h2",
        outcome_evidence_ids=["outcome:prediction:synthetic:001"],
        status="miss",
        error_taxonomy=["wrong_direction", "missing_context"],
        rule_attributions=[
            {"rule_id": "rule:synthetic:career:001", "attribution": "candidate_contributor"}
        ],
        revision={
            "revision_id": "revision:synthetic:001",
            "proposal": "Narrow the synthetic trigger and require the missing context.",
        },
        benchmark_comparison={
            "baseline_version": "synthetic-rules@2.0.0",
            "candidate_version": "synthetic-rules@2.0.1-draft",
            "baseline_status": "miss",
            "candidate_status": "partial",
            "partition": "test",
            "leakage_clean": True,
        },
        recommendation="demote",
        adjudicated_at="2026-01-03T00:00:00Z",
    )

    assert adjudicated["lifecycle_status"] == "pending_operator_review"
    assert adjudicated["adjudications"][0]["status"] == "miss"
    assert adjudicated["negative_case_archive"][0]["adjudication_id"] == "adjudication:synthetic:001"
    assert adjudicated["revisions"][0]["applied"] is False
    assert adjudicated["rule_recommendations"][0]["recommendation"] == "demote"
    assert adjudicated["rule_recommendations"][0]["review_state"] == "pending_operator_review"
    assert adjudicated["rule_recommendations"][0]["applied_to_rules"] is False
    assert adjudicated["accuracy_eligible"] is False
    assert verify_learning_record(adjudicated)

    queue = build_operator_review_queue([adjudicated])
    assert queue["automatic_actions_applied"] == 0
    assert queue["entries"][0]["recommendation"] == "demote"
    assert queue["entries"][0]["review_state"] == "pending_operator_review"
    assert queue["prediction_validity"] == "not_evaluated"


@pytest.mark.parametrize("status", ["hit", "partial", "miss", "unverifiable"])
def test_all_outcome_classes_are_supported_but_never_auto_promote(status: str) -> None:
    case = observed_case(
        raw_identifier=f"synthetic-{status}",
        scenario_id=f"career:synthetic:{status}",
        prediction_id=f"prediction:synthetic:{status}",
        generated_at="2025-02-01T00:00:00Z",
        frozen_at="2025-02-01T00:01:00Z",
        observed_at="2025-12-31T00:00:00Z",
        collected_at="2026-01-02T00:00:00Z",
    )
    result = adjudicate_outcome(
        case,
        adjudication_id=f"adjudication:synthetic:{status}",
        claim_id="claim:career:001",
        scope="career:2025-h2",
        outcome_evidence_ids=[f"outcome:prediction:synthetic:{status}"],
        status=status,
        error_taxonomy=[] if status == "hit" else ["insufficient_evidence" if status == "unverifiable" else "wrong_timing"],
        rule_attributions=[{"rule_id": "rule:synthetic:career:001", "attribution": "review_required"}],
        revision={"revision_id": f"revision:{status}", "proposal": "Synthetic contract revision."},
        benchmark_comparison={
            "baseline_version": "synthetic-rules@2.0.0",
            "candidate_version": "synthetic-rules@2.0.1-draft",
            "baseline_status": status,
            "candidate_status": status,
            "partition": "test",
            "leakage_clean": True,
        },
        recommendation="promote" if status == "hit" else "investigate",
        adjudicated_at="2026-01-03T00:00:00Z",
    )
    assert result["adjudications"][0]["status"] == status
    assert result["rule_recommendations"][0]["applied_to_rules"] is False
    assert result["product_claim_eligible"] is False


def test_temporal_partition_uses_event_and_observation_time_not_ingestion_order() -> None:
    train = observed_case(
        raw_identifier="synthetic-train",
        scenario_id="career:synthetic:train",
        prediction_id="prediction:synthetic:train",
        generated_at="2025-02-01T00:00:00Z",
        frozen_at="2025-02-01T00:01:00Z",
        observed_at="2025-12-30T00:00:00Z",
        collected_at="2025-12-31T00:00:00Z",
    )
    test = observed_case(
        raw_identifier="synthetic-test",
        scenario_id="career:synthetic:test",
        prediction_id="prediction:synthetic:test",
        generated_at="2025-03-01T00:00:00Z",
        frozen_at="2025-03-01T00:01:00Z",
        observed_at="2026-01-02T00:00:00Z",
        collected_at="2026-01-03T00:00:00Z",
    )
    train["ingested_at"] = "2026-12-31T00:00:00Z"
    test["ingested_at"] = "2025-01-01T00:00:00Z"

    manifest = build_temporal_partitions([test, train], cutoff_at="2026-01-01T00:00:00Z")
    Draft202012Validator(get_schema("real_case_learning_v2_partition.schema.json")).validate(manifest)
    assert manifest["train_case_ids"] == [train["case_id"]]
    assert manifest["test_case_ids"] == [test["case_id"]]
    assert manifest["assignment_basis"] == "event_and_observation_time"
    assert manifest["ingestion_order_used"] is False
    assert manifest["leakage_detected"] is False
    assert manifest["prediction_validity"] == "not_evaluated"
    assert verify_learning_record(manifest)


def test_person_prediction_window_fingerprint_and_near_duplicates_cannot_cross_partitions() -> None:
    shared_near = "sha256:" + "9" * 64
    early = observed_case(
        raw_identifier="synthetic-duplicate-person",
        scenario_id="career:synthetic:early",
        prediction_id="prediction:synthetic:early",
        generated_at="2025-02-01T00:00:00Z",
        frozen_at="2025-02-01T00:01:00Z",
        observed_at="2025-12-30T00:00:00Z",
        collected_at="2025-12-31T00:00:00Z",
        near_duplicate_fingerprint=shared_near,
    )
    late = observed_case(
        raw_identifier="synthetic-duplicate-person",
        scenario_id="career:synthetic:late",
        prediction_id="prediction:synthetic:late",
        generated_at="2025-03-01T00:00:00Z",
        frozen_at="2025-03-01T00:01:00Z",
        observed_at="2026-01-02T00:00:00Z",
        collected_at="2026-01-03T00:00:00Z",
        near_duplicate_fingerprint=shared_near,
    )

    first = build_temporal_partitions([early, late], cutoff_at="2026-01-01T00:00:00Z")
    second = build_temporal_partitions([late, early], cutoff_at="2026-01-01T00:00:00Z")
    assert first == second
    assert first["train_case_ids"] == []
    assert first["test_case_ids"] == sorted([early["case_id"], late["case_id"]])
    assert first["leakage_detected"] is False
    assert first["forced_test_case_ids"] == [early["case_id"]]
    assert {
        "person_case_id",
        "prediction_id",
        "event_window",
        "derived_fingerprint",
        "near_duplicate_fingerprint",
    }.issubset(first["deduplication_keys"])


def test_observation_after_cutoff_stays_test_even_when_event_window_ends_before_cutoff() -> None:
    case = observed_case(
        raw_identifier="synthetic-late-observation",
        scenario_id="career:synthetic:late-observation",
        prediction_id="prediction:synthetic:late-observation",
        generated_at="2025-02-01T00:00:00Z",
        frozen_at="2025-02-01T00:01:00Z",
        observed_at="2025-12-31T00:00:00Z",
        collected_at="2026-01-02T00:00:00Z",
    )
    manifest = build_temporal_partitions([case], cutoff_at="2026-01-01T00:00:00Z")
    assert manifest["train_case_ids"] == []
    assert manifest["test_case_ids"] == [case["case_id"]]


def test_withdrawal_returns_only_tombstone_and_invalidates_all_dependencies() -> None:
    case = learning_case()
    case = record_prior_event_validation(
        case,
        evidence_record(
            case,
            evidence_id="prior:synthetic:withdrawal",
            observed_at="2025-01-15T00:00:00Z",
            collected_at="2025-01-16T00:00:00Z",
            direction="support",
        ),
    )
    case = record_future_outcome(
        case,
        evidence_record(
            case,
            evidence_id="outcome:synthetic:withdrawal",
            observed_at="2025-12-31T00:00:00Z",
            collected_at="2026-01-02T00:00:00Z",
            direction="contradict",
        ),
    )
    tombstone = withdraw_case(case, withdrawn_at="2026-02-01T00:00:00Z")

    Draft202012Validator(get_schema("real_case_learning_v2_withdrawal.schema.json")).validate(tombstone)
    assert tombstone["lifecycle_status"] == "withdrawn"
    assert tombstone["dependencies_valid"] is False
    assert tombstone["dependent_records_retained"] is False
    assert len(tombstone["invalidated_dependency_hashes"]) >= 6
    assert "prediction_snapshot" not in tombstone
    assert "original_question_snapshot" not in tombstone
    assert case["person_case_id"] not in json.dumps(tombstone, sort_keys=True)
    assert verify_learning_record(tombstone)

    manifest = build_temporal_partitions([tombstone], cutoff_at="2026-01-01T00:00:00Z")
    assert manifest["withdrawn_case_refs"] == [tombstone["case_ref_hash"]]
    assert manifest["train_case_ids"] == []
    assert manifest["test_case_ids"] == []


def test_synthetic_contract_records_never_become_accuracy_or_product_claim_evidence() -> None:
    case = observed_case(
        raw_identifier="synthetic-summary",
        scenario_id="career:synthetic:summary",
        prediction_id="prediction:synthetic:summary",
        generated_at="2025-02-01T00:00:00Z",
        frozen_at="2025-02-01T00:01:00Z",
        observed_at="2025-12-31T00:00:00Z",
        collected_at="2026-01-02T00:00:00Z",
    )
    summary = summarize_learning_cases([case])
    assert summary["synthetic_contract_cases"] == 1
    assert summary["accuracy_eligible_cases"] == 0
    assert summary["accuracy_metrics"] is None
    assert summary["product_accuracy_claim_allowed"] is False
    assert summary["prediction_validity"] == "not_evaluated"
    assert summary["commercial_release_hold"] == "ACTIVE"
    assert "synthetic_cases_are_contract_tests_only" in summary["limitations"]


def test_tampering_breaks_canonical_verification() -> None:
    case = learning_case()
    tampered = deepcopy(case)
    tampered["original_question_snapshot"]["text"] = "Changed after freeze."
    assert verify_learning_record(case)
    assert not verify_learning_record(tampered)


def test_invalid_adjudication_and_leaky_benchmark_comparison_fail_closed() -> None:
    case = observed_case(
        raw_identifier="synthetic-invalid",
        scenario_id="career:synthetic:invalid",
        prediction_id="prediction:synthetic:invalid",
        generated_at="2025-02-01T00:00:00Z",
        frozen_at="2025-02-01T00:01:00Z",
        observed_at="2025-12-31T00:00:00Z",
        collected_at="2026-01-02T00:00:00Z",
    )
    kwargs = {
        "adjudication_id": "adjudication:synthetic:invalid",
        "claim_id": "claim:career:001",
        "scope": "career:2025-h2",
        "outcome_evidence_ids": ["outcome:prediction:synthetic:invalid"],
        "status": "miss",
        "error_taxonomy": ["wrong_direction"],
        "rule_attributions": [{"rule_id": "rule:synthetic:career:001", "attribution": "candidate_contributor"}],
        "revision": {"revision_id": "revision:invalid", "proposal": "Synthetic contract revision."},
        "benchmark_comparison": {
            "baseline_version": "synthetic-rules@2.0.0",
            "candidate_version": "synthetic-rules@2.0.1-draft",
            "baseline_status": "miss",
            "candidate_status": "hit",
            "partition": "train",
            "leakage_clean": False,
        },
        "recommendation": "demote",
        "adjudicated_at": datetime(2026, 1, 3, tzinfo=timezone.utc).isoformat(),
    }
    with pytest.raises(RealCaseLearningV2Error, match="LEAKAGE_RISK"):
        adjudicate_outcome(case, **kwargs)

    kwargs["benchmark_comparison"] = {**kwargs["benchmark_comparison"], "partition": "test", "leakage_clean": True}
    kwargs["status"] = "fabricated-success"
    with pytest.raises(RealCaseLearningV2Error, match="UNSUPPORTED_ADJUDICATION_STATUS"):
        adjudicate_outcome(case, **kwargs)
