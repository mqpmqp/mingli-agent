from __future__ import annotations
import unittest
from mingli.phase22 import Phase22InputError, benchmark_phase22, run_case_benchmark


def qualified_case(index: int, tier: str, *, person_case_id: str | None = None) -> dict[str, object]:
    scenario_id = ("career", "wealth", "relationship")[index % 3]
    case = {
        "case_id": f"{tier}:{index}",
        "person_case_id": person_case_id or f"person:{index}",
        "scenario_id": scenario_id,
        "case_class": "real",
        "evidence_tier": tier,
        "consent_status": "granted",
        "deidentified": True,
        "source_ref": "authorized:contract-fixture",
        "consent_record_id": f"consent:{index}",
        "provenance_class": "external_observation",
        "observed_at": "2026-02-01T00:00:00+00:00",
        "double_review_complete": True,
        "review_disagreement": False,
        "predicted_claims": {f"{scenario_id}:{index}:{claim}": "supportive" for claim in range(4)},
        "observed_claims": {f"{scenario_id}:{index}:{claim}": "supportive" for claim in range(4)},
    }
    if tier == "gold":
        case.update({
            "prospective_prediction": True,
            "prediction_freeze_hash": f"sha256:{index:064x}",
            "prediction_frozen_at": "2026-01-01T00:00:00+00:00",
        })
    elif tier == "silver":
        case["retrospective_external_support"] = True
    return case


class Phase22Tests(unittest.TestCase):
    def test_benchmark(self):
        result = benchmark_phase22(); self.assertEqual(result["assertions_total"], result["passed"]); self.assertEqual(0, result["real_case_count"])
    def test_empty_registry_has_no_accuracy(self):
        result = run_case_benchmark(); self.assertIsNone(result.exact_match_rate); self.assertFalse(result.product_accuracy_claim_allowed)
    def test_synthetic_never_counts(self):
        result = run_case_benchmark({"minimum_cases_for_product_claim": 30, "cases": [{"case_id": "s", "case_class": "synthetic", "predicted_claims": {"x": "mixed"}, "observed_claims": {"x": "mixed"}}]})
        self.assertEqual(0, result.eligible_real_cases); self.assertIsNone(result.exact_match_rate)
    def test_real_label_requires_external_authorization_provenance(self):
        result = run_case_benchmark({"minimum_cases_for_product_claim": 30, "cases": [{"case_id": "r", "person_case_id": "person:r", "scenario_id": "career", "case_class": "real", "consent_status": "granted", "deidentified": True, "source_ref": "fixture", "predicted_claims": {}, "observed_claims": {}}]})
        self.assertEqual(0,result.eligible_real_cases); self.assertIn("real_case_source_not_authorized",result.case_scores[0].warnings)
    def test_silver_cases_never_enable_product_accuracy_claim(self):
        cases = [qualified_case(index, "silver") for index in range(30)]
        result = run_case_benchmark({"registry_id": "silver-contract-fixture", "minimum_cases_for_product_claim": 30, "pii_leak_count": 0, "cases": cases})
        self.assertEqual(30, result.eligible_silver_cases)
        self.assertEqual(0, result.eligible_gold_cases)
        self.assertFalse(result.product_accuracy_claim_allowed)
        self.assertIn("minimum_gold_case_threshold_not_met_for_product_accuracy_claim", result.warnings)
    def test_ten_gold_twenty_silver_close_validation_without_accuracy_claim(self):
        cases = [qualified_case(index, "gold") for index in range(10)]
        cases.extend(qualified_case(index + 10, "silver") for index in range(20))
        result = run_case_benchmark({"registry_id": "closure-contract", "minimum_cases_for_product_claim": 30, "pii_leak_count": 0, "cases": cases})
        self.assertTrue(result.validation_closure_passed)
        self.assertEqual((), result.validation_closure_failures)
        self.assertEqual(30, result.qualified_unique_person_cases)
        self.assertEqual(10, result.qualified_gold_unique_person_cases)
        self.assertEqual(20, result.qualified_silver_unique_person_cases)
        self.assertEqual(120, result.comparable_claims_count)
        self.assertTrue(result.scenario_coverage_passed)
        self.assertTrue(result.review_coverage_passed)
        self.assertTrue(result.privacy_coverage_passed)
        self.assertFalse(result.product_accuracy_claim_allowed)
    def test_thirty_unique_gold_people_enable_accuracy_claim(self):
        cases = [qualified_case(index, "gold") for index in range(30)]
        result = run_case_benchmark({"registry_id": "accuracy-contract", "minimum_cases_for_product_claim": 30, "pii_leak_count": 0, "cases": cases})
        self.assertTrue(result.validation_closure_passed)
        self.assertEqual(30, result.qualified_gold_unique_person_cases)
        self.assertTrue(result.product_accuracy_claim_allowed)
    def test_thirty_gold_scenarios_for_one_person_count_once(self):
        cases = [qualified_case(index, "gold", person_case_id="person:one") for index in range(30)]
        result = run_case_benchmark({"registry_id": "one-person-contract", "minimum_cases_for_product_claim": 30, "pii_leak_count": 0, "cases": cases})
        self.assertEqual(1, result.qualified_unique_person_cases)
        self.assertEqual(1, result.qualified_gold_unique_person_cases)
        self.assertFalse(result.validation_closure_passed)
        self.assertFalse(result.product_accuracy_claim_allowed)
    def test_missing_person_id_is_excluded_and_duplicate_person_is_deduplicated(self):
        missing = qualified_case(0, "gold")
        missing.pop("person_case_id")
        duplicate = [qualified_case(1, "gold", person_case_id="person:shared"), qualified_case(2, "gold", person_case_id="person:shared")]
        result = run_case_benchmark({"registry_id": "person-id-contract", "minimum_cases_for_product_claim": 30, "pii_leak_count": 0, "cases": [missing, *duplicate]})
        self.assertEqual(1, result.qualified_unique_person_cases)
        self.assertEqual(1, result.qualified_gold_unique_person_cases)
        self.assertIn("real_case_missing_person_case_id", result.case_scores[0].warnings)
    def test_person_with_conflicting_tiers_is_conservatively_silver(self):
        gold = qualified_case(0, "gold", person_case_id="person:conflict")
        silver = qualified_case(1, "silver", person_case_id="person:conflict")
        result = run_case_benchmark({"registry_id": "tier-conflict-contract", "minimum_cases_for_product_claim": 30, "pii_leak_count": 0, "cases": [gold, silver]})
        self.assertEqual(0, result.qualified_gold_unique_person_cases)
        self.assertEqual(1, result.qualified_silver_unique_person_cases)
        self.assertIn("conflicting_person_tiers", result.validation_closure_failures)
    def test_threshold_cannot_be_lowered_for_a_product_claim(self):
        with self.assertRaises(Phase22InputError): run_case_benchmark({"minimum_cases_for_product_claim": 1,"cases":[]})
    def test_duplicate_case_rejected(self):
        case = {"case_id": "x", "case_class": "synthetic", "predicted_claims": {}, "observed_claims": {}}
        with self.assertRaises(Phase22InputError): run_case_benchmark({"cases": [case, case]})

if __name__ == "__main__": unittest.main()
