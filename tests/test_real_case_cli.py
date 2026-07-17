from __future__ import annotations

import io
import json
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
