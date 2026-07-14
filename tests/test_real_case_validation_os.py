from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from mingli.validation_authorization import evaluate_product_release
from mingli.validation_claims import calculate_validation_metrics, validate_comparable_claim
from mingli.validation_dataset import build_dataset_manifest, verify_dataset_manifest
from mingli.validation_freeze import FreezeError, freeze_prediction, verify_prediction_snapshot
from mingli.validation_intake import IntakeError, import_intakes, rollback_import, validate_intake
from mingli.validation_privacy import public_case_manifest, scan_for_pii
from mingli.validation_review import adjudicate_reviews, assess_review_coverage


def intake(person: str = "person:001", *, publication: bool = False) -> dict[str, object]:
    return {
        "person_case_id": person,
        "birth_input": {
            "birth_date": "1990-03-15",
            "birth_time": "10:30",
            "location_precision": "city",
            "gender": "female",
            "calendar": "solar",
            "timezone": "Asia/Shanghai",
            "true_solar_time": False,
            "source": "participant_confirmed",
            "confirmation_status": "confirmed",
        },
        "consent": {
            "consent_status": "granted",
            "consent_scope": ["research", "benchmark"],
            "consent_recorded_at": "2026-01-01T00:00:00Z",
            "consent_record_ref": "consent:irreversible:001",
            "withdrawal_supported": True,
            "research_use_allowed": True,
            "benchmark_use_allowed": True,
            "publication_use_allowed": publication,
            "raw_data_retention_policy": "controlled_off_git",
        },
        "case_metadata": {
            "collection_channel": "authorized_private_intake",
            "collector_role": "case-coordinator",
            "created_at": "2026-01-01T00:00:00Z",
            "source_provenance": "participant_direct",
            "conflict_status": "none",
            "completeness_status": "complete",
        },
        "scenarios": [
            {
                "scenario_id": "career:001",
                "scenario_type": "career_exam",
                "target_period": "2026",
                "question_scope": "exam_stage_trend",
                "known_at_prediction_time": True,
                "excluded_future_information": [],
            }
        ],
    }


def prediction() -> dict[str, object]:
    return {
        "prediction_id": "prediction:001",
        "person_case_id": "person:001",
        "scenario_id": "career:001",
        "engine_version": "2.0.0",
        "source_commit_sha": "393c9ff791d0091176ea8dcba5f50b8ddde6fbd9",
        "rule_set_version": "phase16-24@2.0.0",
        "knowledge_manifest_sha": "sha256:" + "1" * 64,
        "input_manifest_sha": "sha256:" + "2" * 64,
        "generated_at": "2026-01-02T00:00:00Z",
        "prediction_content": "受控结构化预测快照。",
        "structured_claims": [
            {
                "claim_id": "claim:001",
                "domain": "career",
                "time_window": "2026-01-01/2026-12-31",
                "claim_type": "state",
                "predicted_direction": "supportive",
                "predicted_event_or_state": "exam_stage_supportive",
                "confidence": 0.6,
                "specificity_level": "bounded",
                "exclusion_conditions": [],
            }
        ],
        "confidence": 0.6,
        "blocked_fields": [],
        "reality_evidence_visibility": False,
    }


class IntakeAndPrivacyTests(unittest.TestCase):
    def test_missing_person_id_fails_closed(self):
        payload = intake()
        payload.pop("person_case_id")
        with self.assertRaises(IntakeError):
            validate_intake(payload)

    def test_unauthorized_case_is_rejected(self):
        payload = intake()
        payload["consent"]["benchmark_use_allowed"] = False
        with self.assertRaises(IntakeError):
            validate_intake(payload)

    def test_publication_false_never_enters_public_asset(self):
        published = public_case_manifest(intake(publication=False))
        self.assertFalse(published["publication_eligible"])
        self.assertNotIn("birth_input", published)
        self.assertNotIn("consent_record_ref", str(published))

    def test_direct_pii_is_detected(self):
        findings = scan_for_pii({"name": "张三", "phone": "13800138000"})
        self.assertGreaterEqual(len(findings), 2)

    def test_batch_duplicate_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            report = import_intakes(store, [intake()], source_ref="authorized:test")
            self.assertEqual(1, report.imported)
            with self.assertRaises(IntakeError):
                import_intakes(store, [intake()], source_ref="authorized:test")
            rollback = rollback_import(store, report.batch_id)
            self.assertEqual(1, rollback.removed)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            report = import_intakes(store, [intake()], source_ref="authorized:test", dry_run=True)
            self.assertEqual(1, report.validated)
            self.assertFalse(any(store.rglob("*.json")))


class PredictionFreezeTests(unittest.TestCase):
    def test_reality_must_be_invisible_at_generation(self):
        payload = prediction()
        payload["reality_evidence_visibility"] = True
        with self.assertRaises(FreezeError):
            freeze_prediction(payload, frozen_at="2026-01-02T00:01:00Z")

    def test_freeze_is_hash_verifiable_and_immutable(self):
        frozen = freeze_prediction(prediction(), frozen_at="2026-01-02T00:01:00Z")
        self.assertTrue(verify_prediction_snapshot(frozen))
        self.assertEqual("frozen", frozen["freeze_status"])
        tampered = dict(frozen)
        tampered["prediction_content"] = "事后修改"
        self.assertFalse(verify_prediction_snapshot(tampered))

    def test_frozen_id_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            freeze_prediction(prediction(), store=store, frozen_at="2026-01-02T00:01:00Z")
            with self.assertRaises(FreezeError):
                freeze_prediction(prediction(), store=store, frozen_at="2026-01-02T00:02:00Z")

    def test_claim_must_be_registered_in_snapshot(self):
        frozen = freeze_prediction(prediction(), frozen_at="2026-01-02T00:01:00Z")
        claim = dict(frozen["structured_claims"][0])
        claim["prediction_id"] = frozen["prediction_id"]
        claim["person_case_id"] = frozen["person_case_id"]
        claim["scenario_id"] = frozen["scenario_id"]
        validate_comparable_claim(claim, frozen)
        claim["claim_id"] = "claim:invented-after-reality"
        with self.assertRaises(ValueError):
            validate_comparable_claim(claim, frozen)


class ReviewAndMetricsTests(unittest.TestCase):
    def test_not_comparable_is_not_a_hit(self):
        metrics = calculate_validation_metrics(
            [
                {"person_case_id": "person:1", "scenario_id": "career", "domain": "career", "comparison_status": "supported", "confidence": 0.7, "evidence_tier": "gold"},
                {"person_case_id": "person:1", "scenario_id": "career", "domain": "career", "comparison_status": "not_comparable", "confidence": 0.7, "evidence_tier": "gold"},
            ]
        )
        self.assertEqual(1, metrics["comparable_claims"])
        self.assertEqual(1, metrics["not_comparable"])
        self.assertEqual(1.0, metrics["strict_score"])

    def test_reviewer_disagreement_requires_adjudication(self):
        reviews = [
            {"claim_id": "claim:1", "reviewer_id": "reviewer:a", "reviewer_role": "human", "score": "supported"},
            {"claim_id": "claim:1", "reviewer_id": "reviewer:b", "reviewer_role": "human", "score": "contradicted"},
        ]
        coverage = assess_review_coverage(reviews, required_reviewers=2)
        self.assertFalse(coverage["passed"])
        result = adjudicate_reviews(reviews, adjudicator_id="adjudicator:1", final_status="partially_supported", reason="证据仅覆盖部分时间窗")
        self.assertEqual("partially_supported", result["final_status"])
        self.assertTrue(result["disagreement_resolved"])

    def test_llm_cannot_be_sole_final_reviewer(self):
        reviews = [{"claim_id": "claim:1", "reviewer_id": "llm:1", "reviewer_role": "llm_assistant", "score": "supported"}]
        self.assertFalse(assess_review_coverage(reviews, required_reviewers=1)["passed"])


class DatasetAndAuthorizationTests(unittest.TestCase):
    def _manifest(self, *, people: int = 30, gold: int = 10, silver: int = 20, claims: int = 100) -> dict[str, object]:
        cases = []
        for index in range(people):
            cases.append(
                {
                    "person_case_id": f"person:{index}",
                    "evidence_tier": "gold" if index < gold else "silver",
                    "scenario_ids": [f"scenario:{index % 3}"],
                    "qualified": True,
                    "withdrawn": False,
                    "manifest_hash": "sha256:" + f"{index + 1:064x}",
                }
            )
        return build_dataset_manifest(
            dataset_id="real-case-validation-v1",
            dataset_version="1.0.0",
            source_commit_sha="393c9ff791d0091176ea8dcba5f50b8ddde6fbd9",
            protocol_hash="sha256:" + "a" * 64,
            cases=cases,
            prediction_hashes=["sha256:" + "b" * 64],
            reality_evidence_hashes=["sha256:" + "c" * 64],
            review_hashes=["sha256:" + "d" * 64],
            comparable_claims_count=claims,
            review_coverage_passed=True,
            privacy_coverage_passed=True,
            frozen_at="2026-03-01T00:00:00Z",
        )

    def test_10_gold_20_silver_closes_validation_not_accuracy(self):
        manifest = self._manifest()
        self.assertTrue(manifest["validation_closure_passed"])
        self.assertFalse(manifest["product_accuracy_claim_allowed"])
        self.assertTrue(verify_dataset_manifest(manifest))

    def test_30_gold_allows_accuracy_claim(self):
        manifest = self._manifest(gold=30, silver=0)
        self.assertTrue(manifest["validation_closure_passed"])
        self.assertTrue(manifest["product_accuracy_claim_allowed"])

    def test_thirty_scenarios_one_person_never_counts_as_thirty_people(self):
        cases = [
            {
                "person_case_id": "person:one",
                "evidence_tier": "gold",
                "scenario_ids": [f"scenario:{index}"],
                "qualified": True,
                "withdrawn": False,
                "manifest_hash": "sha256:" + f"{index + 1:064x}",
            }
            for index in range(30)
        ]
        manifest = build_dataset_manifest(
            dataset_id="dedupe", dataset_version="1.0.0", source_commit_sha="3" * 40,
            protocol_hash="sha256:" + "a" * 64, cases=cases,
            prediction_hashes=[], reality_evidence_hashes=[], review_hashes=[],
            comparable_claims_count=120, review_coverage_passed=True,
            privacy_coverage_passed=True, frozen_at="2026-03-01T00:00:00Z",
        )
        self.assertEqual(1, manifest["unique_person_count"])
        self.assertFalse(manifest["product_accuracy_claim_allowed"])

    def test_conflicting_tier_is_conservative_and_blocks_closure(self):
        manifest = self._manifest()
        duplicate = dict({
            "person_case_id": "person:0", "evidence_tier": "silver", "scenario_ids": ["scenario:1"],
            "qualified": True, "withdrawn": False, "manifest_hash": "sha256:" + "e" * 64,
        })
        cases = list(manifest["case_entries"]) + [duplicate]
        rebuilt = build_dataset_manifest(
            dataset_id="conflict", dataset_version="1.0.0", source_commit_sha="3" * 40,
            protocol_hash="sha256:" + "a" * 64, cases=cases,
            prediction_hashes=[], reality_evidence_hashes=[], review_hashes=[], comparable_claims_count=120,
            review_coverage_passed=True, privacy_coverage_passed=True, frozen_at="2026-03-01T00:00:00Z",
        )
        self.assertEqual(["person:0"], rebuilt["conflicting_person_tiers"])
        self.assertFalse(rebuilt["validation_closure_passed"])

    def test_withdrawal_reduces_manifest_and_reopens_closure(self):
        manifest = self._manifest()
        cases = [dict(item, withdrawn=item["person_case_id"] == "person:0") for item in manifest["case_entries"]]
        rebuilt = build_dataset_manifest(
            dataset_id="withdrawn", dataset_version="1.0.1", source_commit_sha="3" * 40,
            protocol_hash="sha256:" + "a" * 64, cases=cases,
            prediction_hashes=[], reality_evidence_hashes=[], review_hashes=[], comparable_claims_count=100,
            review_coverage_passed=True, privacy_coverage_passed=True, frozen_at="2026-03-02T00:00:00Z",
        )
        self.assertEqual(29, rebuilt["unique_person_count"])
        self.assertFalse(rebuilt["validation_closure_passed"])

    def test_authorization_state_matrix_is_fail_closed(self):
        manifest = self._manifest()
        base = {
            "authorization_id": "authorization:1",
            "dataset_id": manifest["dataset_id"],
            "dataset_manifest_sha": manifest["aggregate_canonical_hash"],
            "validation_report_sha": "sha256:" + "f" * 64,
            "validation_closure_passed": True,
            "product_accuracy_claim_allowed": False,
            "known_limitations": ["no accuracy claim"],
            "unresolved_conflicts": [],
            "approved_use_scope": ["traditional_culture_reference"],
            "prohibited_claims": ["statistical_accuracy"],
            "authorization_status": "pending",
            "authorized_by_role": "independent-product-reviewer",
            "authorized_at": "2026-03-02T00:00:00Z",
            "review_due_at": "2027-03-02T00:00:00Z",
            "source_commit_sha": "3" * 40,
        }
        gates = {"p1_findings": 0, "p2_findings": 0, "privacy_gate": True, "package_gate": True, "main_ci": True}
        self.assertEqual("PRODUCT_RELEASE_HOLD", evaluate_product_release(manifest, base, gates, now=datetime(2026, 4, 1, tzinfo=timezone.utc))["status"])
        approved = dict(base, authorization_status="approved")
        self.assertEqual("PRODUCT_RELEASE_ALLOWED", evaluate_product_release(manifest, approved, gates, now=datetime(2026, 4, 1, tzinfo=timezone.utc))["status"])
        self.assertEqual("PRODUCT_RELEASE_HOLD", evaluate_product_release(manifest, approved, dict(gates, package_gate=False), now=datetime(2026, 4, 1, tzinfo=timezone.utc))["status"])
        expired = dict(approved, review_due_at="2026-03-03T00:00:00Z")
        self.assertEqual("PRODUCT_RELEASE_HOLD", evaluate_product_release(manifest, expired, gates, now=datetime(2026, 4, 1, tzinfo=timezone.utc))["status"])
        revoked = dict(approved, authorization_status="revoked")
        self.assertEqual("PRODUCT_RELEASE_HOLD", evaluate_product_release(manifest, revoked, gates, now=datetime(2026, 4, 1, tzinfo=timezone.utc))["status"])


if __name__ == "__main__":
    unittest.main()
