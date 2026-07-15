from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from mingli.cli import main as mingli_main
from mingli.contracts import get_schema
from mingli.product_readiness import assess_v2_readiness
from mingli.product_runtime import run_product_runtime
from mingli.training import TrainingError, TrainingStore
from mingli.validation_privacy import irreversible_person_case_id


CREATED_AT = "2026-07-15T12:00:00+00:00"


def runtime_input(*, training_consent: bool = False) -> dict[str, object]:
    return {
        "case_id": "person:" + "a" * 64,
        "created_at": CREATED_AT,
        "consent": {
            "analysis_allowed": True,
            "training_use_allowed": training_consent,
            "consent_version": "training-consent@1",
        },
        "topic": "career",
        "chart_input": {
            "gender": "male",
            "calendar": "solar",
            "birth_date": "1990-03-15",
            "birth_time": "10:30",
            "timezone": "Asia/Shanghai",
            "birth_location": {"longitude": 121.47, "latitude": 31.23},
            "true_solar_time": False,
        },
        "anchor_year": 2026,
        "reality": {"cash_runway_months": 2},
        "fusion_evidence": [
            {
                "evidence_id": f"verified-{domain}",
                "claim_id": domain,
                "scope": "runtime:baseline",
                "source_type": "reality",
                "source_id": "user-confirmed",
                "direction": direction,
                "weight": 0,
                "priority": 100,
                "verified": True,
            }
            for domain, direction in (
                ("career", "support"),
                ("wealth", "contradict"),
                ("relationship", "support"),
            )
        ],
    }


class ProductRuntimeTests(unittest.TestCase):
    def test_complete_input_returns_product_envelope(self) -> None:
        Draft202012Validator(get_schema("product_runtime_input.schema.json")).validate(runtime_input())
        result = run_product_runtime(runtime_input())
        Draft202012Validator(get_schema("product_runtime_envelope.schema.json")).validate(result)
        self.assertEqual("completed", result["status"])
        for field in (
            "run_id", "schema_version", "engine_version", "rule_manifest_hash",
            "renderer_version", "created_at", "confidence", "confidence_reason",
            "limitations", "reality_evidence_used", "sections", "trace",
        ):
            self.assertIn(field, result)
        self.assertEqual(8, len(result["sections"]))
        self.assertEqual("challenging", result["domain_results"]["wealth"])
        self.assertEqual("resolved_by_reality_override", result["reality_evidence_used"][0]["resolution"])
        self.assertEqual("validated", result["trace"]["knowledge_os"]["status"])
        self.assertTrue(result["trace"]["knowledge_os"]["manifest_hash"].startswith("sha256:"))
        self.assertEqual([], result["errors"])

    def test_missing_birth_input_returns_structured_blocked_error(self) -> None:
        payload = runtime_input()
        payload.pop("chart_input")
        result = run_product_runtime(payload)
        self.assertEqual("blocked", result["status"])
        self.assertEqual("MISSING_CHART_INPUT", result["errors"][0]["code"])
        self.assertEqual("$.chart_input", result["errors"][0]["field_path"])

    def test_calculation_failure_is_blocked_without_fabricated_sections(self) -> None:
        with patch("mingli.product_runtime.run_mingli_agent", side_effect=RuntimeError("tool unavailable")):
            result = run_product_runtime(runtime_input())
        self.assertEqual("blocked", result["status"])
        self.assertEqual("CALCULATION_UNAVAILABLE", result["errors"][0]["code"])
        self.assertEqual([], result["sections"])

    def test_low_confidence_is_explicitly_degraded(self) -> None:
        payload = runtime_input()
        payload["fusion_evidence"] = []
        result = run_product_runtime(payload)
        self.assertIn(result["status"], {"completed", "degraded"})
        if result["confidence"] == "low":
            self.assertEqual("degraded", result["status"])
            self.assertIn("low", result["confidence_reason"])

    def test_runtime_is_fully_deterministic_for_same_contract_input(self) -> None:
        left = run_product_runtime(runtime_input())
        right = run_product_runtime(json.loads(json.dumps(runtime_input())))
        self.assertEqual(left, right)

    def test_raw_identity_is_rejected_and_never_echoed(self) -> None:
        payload = runtime_input()
        payload["name"] = "Synthetic Person"
        result = run_product_runtime(payload)
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertEqual("blocked", result["status"])
        self.assertEqual("PII_DETECTED", result["errors"][0]["code"])
        self.assertNotIn("Synthetic Person", encoded)


class TrainingStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = Path(__file__).resolve().parents[1]
        self.store = TrainingStore(self.root / "training", repository_root=self.repo)
        self.case_id = irreversible_person_case_id("synthetic-subject", project_salt="synthetic-test-key-0001")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def case_record(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "consent_scope": ["analysis", "training"],
            "consent_version": "training-consent@1",
            "intake_snapshot_ref": "sha256:" + "1" * 64,
            "chart_snapshot_ref": "sha256:" + "2" * 64,
            "runtime_output_ref": "pending",
            "analysis_version": "2.0.0",
            "created_at": CREATED_AT,
            "topic": "career",
            "confidence": "pending",
            "feedback_status": "pending",
            "outcome_status": "pending",
            "review_status": "pending",
            "provenance": {"source": "synthetic-test"},
            "lifecycle": "active",
        }

    def test_training_schemas_are_packaged_and_validate_minimum_objects(self) -> None:
        names = (
            "product_runtime_input.schema.json", "product_runtime_envelope.schema.json",
            "training_case.schema.json", "analysis_run.schema.json", "user_feedback.schema.json",
            "outcome_observation.schema.json", "rule_review_candidate.schema.json",
            "training_iteration.schema.json",
        )
        for name in names:
            Draft202012Validator.check_schema(get_schema(name))

    def test_real_store_inside_repository_is_rejected_but_synthetic_is_explicit(self) -> None:
        with self.assertRaisesRegex(TrainingError, "TRAINING_STORE_INSIDE_REPOSITORY"):
            TrainingStore(self.repo / ".training-real", repository_root=self.repo)
        store = TrainingStore(self.repo / ".training-synthetic", repository_root=self.repo, synthetic=True)
        self.assertTrue(store.synthetic)

    def test_no_training_consent_means_no_storage_write(self) -> None:
        result = run_product_runtime(runtime_input(training_consent=False), store=self.store)
        self.assertFalse(result["training_write"]["stored"])
        self.assertEqual("TRAINING_CONSENT_NOT_GRANTED", result["training_write"]["reason"])
        self.assertEqual([], list((self.root / "training").glob("runs/*.json")))

    def test_authorized_run_feedback_outcome_and_manual_candidate(self) -> None:
        self.store.create_case(self.case_record())
        payload = runtime_input(training_consent=True)
        payload["case_id"] = self.case_id
        result = run_product_runtime(payload, store=self.store)
        self.assertTrue(result["training_write"]["stored"])
        run_id = str(result["run_id"])
        feedback = self.store.add_feedback({
            "feedback_id": "feedback-1",
            "case_id": self.case_id,
            "run_id": run_id,
            "overall_rating": 4,
            "useful_sections": ["事业"],
            "inaccurate_sections": [],
            "missing_context": ["capital_constraint"],
            "user_correction": None,
            "clarity_rating": 4,
            "actionability_rating": 3,
            "free_text": "synthetic feedback",
            "feedback_kind": "subjective",
            "submitted_at": CREATED_AT,
        })
        self.assertFalse(feedback["counts_toward_accuracy"])
        outcome = self.store.add_outcome({
            "outcome_id": "outcome-1",
            "case_id": self.case_id,
            "run_id": run_id,
            "event_type": "job_change",
            "event_time": "2026-09-01T00:00:00+00:00",
            "observed_at": "2026-09-02T00:00:00+00:00",
            "source_type": "user_report",
            "source_reliability": "unverified",
            "relation_to_prior_claim": "later_outcome",
            "notes": "synthetic observation",
            "preregistered_claim_id": None,
        })
        self.assertFalse(outcome["commercial_validation_eligible"])
        candidate = self.store.create_rule_candidate({
            "candidate_id": "candidate-1",
            "source_case_ids": [self.case_id],
            "suspected_failure_mode": "missing-context",
            "current_rule_ids": [],
            "proposed_change": "review context dependency",
            "supporting_evidence": ["feedback:feedback-1"],
            "counter_evidence": [],
            "confidence": "low",
            "review_state": "pending_human_review",
            "reviewer_note": None,
            "created_at": CREATED_AT,
        })
        self.assertEqual("pending_human_review", candidate["review_state"])
        self.assertFalse(candidate["applied_to_rules"])
        report = self.store.review()
        self.assertEqual(1, report["feedback_count"])
        self.assertEqual(0, report["benchmark_accuracy_observations"])
        iteration = self.store.create_review_iteration(created_at=CREATED_AT)
        self.assertEqual("pending_human_review", iteration["review_state"])
        self.assertEqual(["feedback-1"], iteration["feedback_ids"])
        self.assertEqual(1, len(iteration["candidate_ids"]))
        generated = self.store.candidates()
        self.assertEqual(2, len(generated))
        self.assertTrue(all(item["applied_to_rules"] is False for item in generated))

    def test_withdrawal_removes_derived_records_and_keeps_non_pii_audit(self) -> None:
        self.store.create_case(self.case_record())
        payload = runtime_input(training_consent=True)
        payload["case_id"] = self.case_id
        run_product_runtime(payload, store=self.store)
        self.store.withdraw(self.case_id, withdrawn_at=CREATED_AT)
        with self.assertRaisesRegex(TrainingError, "CASE_WITHDRAWN"):
            self.store.show_case(self.case_id)
        self.assertEqual([], list((self.root / "training" / "runs").glob("*.json")))
        audit = (self.root / "training" / "audit.jsonl").read_text(encoding="utf-8")
        self.assertIn("CONSENT_WITHDRAWN", audit)
        self.assertNotIn(self.case_id, audit)
        self.assertNotIn("synthetic-subject", audit)

    def test_duplicate_and_pii_records_have_stable_errors(self) -> None:
        self.store.create_case(self.case_record())
        with self.assertRaisesRegex(TrainingError, "DUPLICATE_RECORD"):
            self.store.create_case(self.case_record())
        bad = self.case_record()
        bad["case_id"] = "person:" + "b" * 64
        bad["phone"] = "13800138000"
        with self.assertRaisesRegex(TrainingError, "PII_DETECTED"):
            self.store.create_case(bad)


class ProductReadinessTests(unittest.TestCase):
    def test_product_ready_and_commercial_pending_are_independent(self) -> None:
        gates = {
            name: True for name in (
                "runtime", "knowledge", "rules", "evidence", "renderer", "etl",
                "training", "privacy", "fast_tests", "build", "static_checks",
            )
        }
        result = assess_v2_readiness(gates, commercial_evidence={})
        self.assertEqual("PRODUCT_CAPABILITY_READY", result["product_status"])
        self.assertEqual("COMMERCIAL_VALIDATION_PENDING", result["commercial_status"])
        self.assertTrue(result["allowed_modes"]["development"])
        self.assertFalse(result["allowed_modes"]["production-commercial"])
        self.assertEqual("PRODUCT_RELEASE_HOLD", result["legacy_product_release_status"])

    def test_training_feedback_and_unauthorized_cases_never_satisfy_commercial_gate(self) -> None:
        gates = {name: True for name in (
            "runtime", "knowledge", "rules", "evidence", "renderer", "etl",
            "training", "privacy", "fast_tests", "build", "static_checks",
        )}
        evidence = {
            "authorized_real_cases": 0,
            "unauthorized_cases": 999,
            "training_feedback_count": 999,
            "claims_prefrozen": False,
        }
        result = assess_v2_readiness(gates, evidence)
        self.assertEqual("COMMERCIAL_VALIDATION_PENDING", result["commercial_status"])
        self.assertEqual(0, result["commercial_evidence_counted"]["authorized_real_cases"])
        self.assertEqual(0, result["commercial_evidence_counted"]["accuracy_observations"])


class TrainingCliTests(unittest.TestCase):
    def test_top_level_training_cli_returns_structured_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = io.StringIO()
            with redirect_stdout(output):
                code = mingli_main(["training", "review", "--store", str(Path(temp) / "training"), "--json"])
            payload = json.loads(output.getvalue())
        self.assertEqual(0, code)
        self.assertEqual("ok", payload["status"])
        self.assertEqual(0, payload["data"]["feedback_count"])

    def test_cli_errors_are_json_with_stable_exit_code(self) -> None:
        output = io.StringIO()
        repo = Path(__file__).resolve().parents[1]
        with redirect_stdout(output):
            code = mingli_main(["training", "review", "--store", str(repo / "real-store"), "--json"])
        payload = json.loads(output.getvalue())
        self.assertEqual(2, code)
        self.assertEqual("TRAINING_STORE_INSIDE_REPOSITORY", payload["error"]["code"])


if __name__ == "__main__":
    unittest.main()
