from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from mingli.real_case_learning_v2 import anonymize_person_case
from mingli.validation_cli import main as validation_main


def _case_start_input() -> dict[str, object]:
    person_case_id = anonymize_person_case(
        "synthetic-contract-subject",
        project_salt="synthetic-contract-salt-0001",
    )
    return {
        "intake": {
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
                    "scenario_id": "career:synthetic:cli",
                    "scenario_type": "career_exam",
                    "target_period": "2025-2026",
                    "question_scope": "bounded_exam_stage",
                    "known_at_prediction_time": True,
                    "excluded_future_information": [],
                }
            ],
        },
        "chart_snapshot": {
            "schema_version": "synthetic-chart-snapshot@2.0",
            "chart_fingerprint": "sha256:" + "3" * 64,
            "calculation_status": "complete",
            "prediction_validity": "not_evaluated",
        },
        "original_question": "Synthetic bounded career question.",
        "prediction_time_reality_context": {
            "known_at": "2025-02-01T00:00:00Z",
            "facts": {"exam_stage": "preparation", "preparation_months": 6},
            "excluded_future_information": ["future_exam_result"],
        },
        "prediction": {
            "prediction_id": "prediction:synthetic:cli",
            "person_case_id": person_case_id,
            "scenario_id": "career:synthetic:cli",
            "engine_version": "2.0.0",
            "source_commit_sha": "a" * 40,
            "rule_set_version": "synthetic-rules@2.0.0",
            "knowledge_manifest_sha": "sha256:" + "1" * 64,
            "input_manifest_sha": "sha256:" + "2" * 64,
            "generated_at": "2025-02-01T00:00:00Z",
            "prediction_content": "Synthetic bounded supportive tendency.",
            "structured_claims": [
                {
                    "claim_id": "claim:career:cli",
                    "scope": "career:2025-h2",
                    "domain": "career",
                    "time_window": "2025-07-01T00:00:00Z/2025-12-31T23:59:59Z",
                    "claim_type": "state",
                    "predicted_direction": "support",
                    "predicted_event_or_state": "bounded_supportive_tendency",
                    "confidence": 0.6,
                    "specificity_level": "bounded",
                    "exclusion_conditions": [],
                    "rule_ids": ["rule:synthetic:career:cli"],
                },
                {
                    "claim_id": "claim:career:prior:cli",
                    "scope": "career:prior:2025-01",
                    "domain": "career",
                    "time_window": "2025-01-01T00:00:00Z/2025-01-31T23:59:59Z",
                    "claim_type": "state",
                    "predicted_direction": "support",
                    "predicted_event_or_state": "bounded_prior_state",
                    "confidence": 0.6,
                    "specificity_level": "bounded",
                    "exclusion_conditions": [],
                    "rule_ids": ["rule:synthetic:career:prior:cli"],
                }
            ],
            "confidence": 0.6,
            "blocked_fields": [],
            "reality_evidence_visibility": False,
            "prediction_validity": "not_evaluated",
        },
        "frozen_at": "2025-02-01T00:01:00Z",
        "synthetic": True,
    }


def test_case_start_cli_writes_only_an_external_frozen_contract_fixture() -> None:
    with TemporaryDirectory(dir=Path.cwd().parent) as directory:
        input_path = Path(directory) / "start.json"
        output_path = Path(directory) / "case.json"
        input_path.write_text(json.dumps(_case_start_input()), encoding="utf-8")
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = validation_main(
                ["case-start", "--input", str(input_path), "--output", str(output_path)]
            )

        assert code == 0
        assert stderr.getvalue() == ""
        case = json.loads(output_path.read_text(encoding="utf-8"))
        assert case["lifecycle_status"] == "prediction_frozen"
        assert case["synthetic"] is True
        assert case["accuracy_eligible"] is False
        assert case["commercial_release_hold"] == "ACTIVE"


def test_case_start_rejects_a_checkout_output_without_writing() -> None:
    with TemporaryDirectory(dir=Path.cwd().parent) as directory:
        input_path = Path(directory) / "start.json"
        output_path = Path.cwd() / "case-start-output.json"
        input_path.write_text(json.dumps(_case_start_input()), encoding="utf-8")
        if output_path.exists():
            output_path.unlink()
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            code = validation_main(
                ["case-start", "--input", str(input_path), "--output", str(output_path)]
            )

        assert code == 1
        assert not output_path.exists()
        assert "outside the Git checkout" in stderr.getvalue()


def test_case_start_rejects_a_checkout_output_when_called_from_controlled_storage() -> None:
    repo_root = Path.cwd()
    output_path = repo_root / "case-start-cwd-escape.json"
    if output_path.exists():
        output_path.unlink()
    with (
        TemporaryDirectory(dir=repo_root.parent) as controlled_directory,
        TemporaryDirectory(dir=repo_root.parent) as input_directory,
    ):
        controlled = Path(controlled_directory)
        input_path = Path(input_directory) / "start.json"
        input_path.write_text(json.dumps(_case_start_input()), encoding="utf-8")
        stderr = io.StringIO()
        original_cwd = Path.cwd()
        try:
            os.chdir(controlled)
            with redirect_stderr(stderr):
                code = validation_main(
                    ["case-start", "--input", str(input_path), "--output", str(output_path)]
                )
        finally:
            os.chdir(original_cwd)
            if output_path.exists():
                output_path.unlink()

        assert code == 1
        assert "outside the Git checkout" in stderr.getvalue()


def test_case_start_fails_closed_when_synthetic_provenance_is_relabelled_real() -> None:
    payload = _case_start_input()
    payload["synthetic"] = False
    with TemporaryDirectory(dir=Path.cwd().parent) as directory:
        input_path = Path(directory) / "start.json"
        output_path = Path(directory) / "case.json"
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            code = validation_main(
                ["case-start", "--input", str(input_path), "--output", str(output_path)]
            )

        assert code == 1
        assert not output_path.exists()
        assert "synthetic" in stderr.getvalue()


def test_case_start_rejects_an_unsealed_payload_shape_without_writing() -> None:
    with TemporaryDirectory(dir=Path.cwd().parent) as directory:
        input_path = Path(directory) / "start.json"
        output_path = Path(directory) / "case.json"
        input_path.write_text(json.dumps({"synthetic": True}), encoding="utf-8")
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            code = validation_main(
                ["case-start", "--input", str(input_path), "--output", str(output_path)]
            )

        assert code == 1
        assert not output_path.exists()
        assert "exactly the required V2 case fields" in stderr.getvalue()


def test_case_start_operator_can_privacy_scan_an_external_contract_fixture() -> None:
    with TemporaryDirectory(dir=Path.cwd().parent) as directory:
        fixture_path = Path(directory) / "synthetic-contract.json"
        fixture_path.write_text(json.dumps({"synthetic": True}), encoding="utf-8")
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            code = validation_main(["privacy-scan", str(fixture_path)])

        assert code == 0
        assert json.loads(stdout.getvalue()) == {"findings": [], "passed": True}


def test_case_os_cli_exposes_read_only_internal_beta_audit_operations() -> None:
    payload = _case_start_input()
    payload["intake"]["case_metadata"]["case_classification"] = "test_fixture"  # type: ignore[index]
    with TemporaryDirectory(dir=Path.cwd().parent) as directory:
        controlled = Path(directory)
        input_path = controlled / "start.json"
        case_path = controlled / "case.json"
        cases_path = controlled / "cases.json"
        review_pack_path = controlled / "review-pack.json"
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        assert validation_main(["case-start", "--input", str(input_path), "--output", str(case_path)]) == 0
        case = json.loads(case_path.read_text(encoding="utf-8"))
        cases_path.write_text(json.dumps([case]), encoding="utf-8")

        inspect_stdout = io.StringIO()
        with redirect_stdout(inspect_stdout):
            assert validation_main(["case-inspect", "--case", str(case_path)]) == 0
        inspection = json.loads(inspect_stdout.getvalue())
        assert inspection["original_output"] == payload["prediction"]["prediction_content"]
        assert inspection["output_hash"] == case["prediction_snapshot"]["canonical_hash"]
        assert inspection["case_classification"] == "test_fixture"
        assert inspection["commercial_release_hold"] == "ACTIVE"

        summary_stdout = io.StringIO()
        with redirect_stdout(summary_stdout):
            assert validation_main(["case-summary", "--cases", str(cases_path)]) == 0
        summary = json.loads(summary_stdout.getvalue())
        assert summary["case_classification_counts"] == {"test_fixture": 1}
        assert summary["accuracy_eligible_cases"] == 0

        assert validation_main(
            ["case-export-review-pack", "--cases", str(cases_path), "--output", str(review_pack_path)]
        ) == 0
        review_pack = json.loads(review_pack_path.read_text(encoding="utf-8"))
        assert review_pack["case_count"] == 1
        assert "person_case_id" not in review_pack["cases"][0]
        assert "consent_record_ref" not in json.dumps(review_pack)

        hold_stdout = io.StringIO()
        with redirect_stdout(hold_stdout):
            assert validation_main(["case-hold-status"]) == 0
        assert json.loads(hold_stdout.getvalue()) == {
            "commercial_release_hold": "ACTIVE",
            "commercial_validation_eligibility": False,
            "prediction_validity": "not_evaluated",
            "product_accuracy_claim": "prohibited",
        }


def test_case_os_cli_keeps_external_snapshots_append_only_after_start() -> None:
    payload = _case_start_input()
    with TemporaryDirectory(dir=Path.cwd().parent) as directory:
        controlled = Path(directory)
        start_input = controlled / "start.json"
        frozen_case_path = controlled / "frozen-case.json"
        prior_evidence_path = controlled / "prior-evidence.json"
        prior_case_path = controlled / "prior-case.json"
        evidence_path = controlled / "future-evidence.json"
        observed_case_path = controlled / "observed-case.json"
        cases_path = controlled / "cases.json"
        partition_path = controlled / "partition.json"
        adjudication_request_path = controlled / "adjudication-request.json"
        adjudicated_case_path = controlled / "adjudicated-case.json"
        queue_path = controlled / "queue.json"
        withdrawal_path = controlled / "withdrawal.json"
        start_input.write_text(json.dumps(payload), encoding="utf-8")
        person_case_id = str(payload["intake"]["person_case_id"])
        prior_evidence_path.write_text(
            json.dumps(
                {
                    "evidence_id": "evidence:synthetic:prior:cli",
                    "person_case_id": person_case_id,
                    "scenario_id": "career:synthetic:cli",
                    "claim_id": "claim:career:prior:cli",
                    "scope": "career:prior:2025-01",
                    "event_window": "2025-01-01T00:00:00Z/2025-01-31T23:59:59Z",
                    "observed_at": "2025-01-30T00:00:00Z",
                    "collected_at": "2025-01-31T00:00:00Z",
                    "source_provenance": "synthetic_contract_fixture",
                    "evidence_quality": "high",
                    "direction": "support",
                    "verified": True,
                    "synthetic": True,
                }
            ),
            encoding="utf-8",
        )
        evidence_path.write_text(
            json.dumps(
                {
                    "evidence_id": "evidence:synthetic:future:cli",
                    "person_case_id": person_case_id,
                    "scenario_id": "career:synthetic:cli",
                    "claim_id": "claim:career:cli",
                    "scope": "career:2025-h2",
                    "event_window": "2025-07-01T00:00:00Z/2025-12-31T23:59:59Z",
                    "observed_at": "2025-12-31T00:00:00Z",
                    "collected_at": "2026-01-02T00:00:00Z",
                    "source_provenance": "synthetic_contract_fixture",
                    "evidence_quality": "high",
                    "direction": "contradict",
                    "verified": True,
                    "synthetic": True,
                }
            ),
            encoding="utf-8",
        )

        assert validation_main(
            ["case-start", "--input", str(start_input), "--output", str(frozen_case_path)]
        ) == 0
        frozen_case = json.loads(frozen_case_path.read_text(encoding="utf-8"))

        assert validation_main(
            [
                "case-prior",
                "--case",
                str(frozen_case_path),
                "--evidence",
                str(prior_evidence_path),
                "--output",
                str(prior_case_path),
            ]
        ) == 0
        prior_case = json.loads(prior_case_path.read_text(encoding="utf-8"))
        assert prior_case["lifecycle_status"] == "prior_event_validated"

        assert validation_main(
            [
                "case-future",
                "--case",
                str(prior_case_path),
                "--evidence",
                str(evidence_path),
                "--output",
                str(observed_case_path),
            ]
        ) == 0
        observed_case = json.loads(observed_case_path.read_text(encoding="utf-8"))
        assert frozen_case["lifecycle_status"] == "prediction_frozen"
        assert frozen_case["prior_event_validations"] == []
        assert observed_case["lifecycle_status"] == "future_outcome_observed"
        assert len(observed_case["prior_event_validations"]) == 1
        assert observed_case["future_outcomes"][0]["reality_resolution"]["status"] == "resolved_by_reality_override"

        cases_path.write_text(json.dumps([observed_case]), encoding="utf-8")
        assert validation_main(
            [
                "case-partition",
                "--cases",
                str(cases_path),
                "--cutoff-at",
                "2026-01-01T00:00:00Z",
                "--output",
                str(partition_path),
            ]
        ) == 0
        partition = json.loads(partition_path.read_text(encoding="utf-8"))
        assert observed_case["case_id"] in partition["test_case_ids"]

        adjudication_request_path.write_text(
            json.dumps(
                {
                    "adjudication_id": "adjudication:synthetic:cli",
                    "claim_id": "claim:career:cli",
                    "scope": "career:2025-h2",
                    "outcome_evidence_ids": ["evidence:synthetic:future:cli"],
                    "status": "miss",
                    "error_taxonomy": ["wrong_direction"],
                    "rule_attributions": [
                        {
                            "rule_id": "rule:synthetic:career:cli",
                            "attribution": "candidate_contributor",
                        }
                    ],
                    "revision": {
                        "revision_id": "revision:synthetic:cli",
                        "proposal": "Synthetic contract revision for operator review.",
                    },
                    "benchmark_comparison": {
                        "baseline_version": "synthetic-rules@2.0.0",
                        "candidate_version": "synthetic-rules@2.0.1-draft",
                        "baseline_status": "miss",
                        "candidate_status": "partial",
                        "partition": "test",
                        "leakage_clean": True,
                        "partition_manifest": partition,
                    },
                    "recommendation": "demote",
                    "adjudicated_at": "2026-01-03T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        assert validation_main(
            [
                "case-adjudicate",
                "--case",
                str(observed_case_path),
                "--request",
                str(adjudication_request_path),
                "--output",
                str(adjudicated_case_path),
            ]
        ) == 0
        adjudicated_case = json.loads(adjudicated_case_path.read_text(encoding="utf-8"))
        assert adjudicated_case["lifecycle_status"] == "pending_operator_review"
        assert adjudicated_case["negative_case_archive"]

        cases_path.write_text(json.dumps([adjudicated_case]), encoding="utf-8")
        assert validation_main(
            ["case-review-queue", "--cases", str(cases_path), "--output", str(queue_path)]
        ) == 0
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        assert queue["automatic_actions_applied"] == 0
        assert queue["entries"][0]["recommendation"] == "demote"

        assert validation_main(
            [
                "case-withdraw",
                "--case",
                str(adjudicated_case_path),
                "--withdrawn-at",
                "2026-01-03T00:00:00Z",
                "--output",
                str(withdrawal_path),
            ]
        ) == 0
        withdrawal = json.loads(withdrawal_path.read_text(encoding="utf-8"))
        assert withdrawal["lifecycle_status"] == "withdrawn"
        assert withdrawal["commercial_release_hold"] == "ACTIVE"
