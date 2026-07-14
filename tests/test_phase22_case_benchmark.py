from __future__ import annotations
import unittest
from mingli.phase22 import Phase22InputError, benchmark_phase22, run_case_benchmark

class Phase22Tests(unittest.TestCase):
    def test_benchmark(self):
        result = benchmark_phase22(); self.assertEqual(result["assertions_total"], result["passed"]); self.assertEqual(0, result["real_case_count"])
    def test_empty_registry_has_no_accuracy(self):
        result = run_case_benchmark(); self.assertIsNone(result.exact_match_rate); self.assertFalse(result.product_accuracy_claim_allowed)
    def test_synthetic_never_counts(self):
        result = run_case_benchmark({"minimum_cases_for_product_claim": 30, "cases": [{"case_id": "s", "case_class": "synthetic", "predicted_claims": {"x": "mixed"}, "observed_claims": {"x": "mixed"}}]})
        self.assertEqual(0, result.eligible_real_cases); self.assertIsNone(result.exact_match_rate)
    def test_real_label_requires_external_authorization_provenance(self):
        result = run_case_benchmark({"minimum_cases_for_product_claim": 30, "cases": [{"case_id": "r", "case_class": "real", "consent_status": "granted", "deidentified": True, "source_ref": "fixture", "predicted_claims": {}, "observed_claims": {}}]})
        self.assertEqual(0,result.eligible_real_cases); self.assertIn("real_case_source_not_authorized",result.case_scores[0].warnings)
    def test_silver_cases_never_enable_product_accuracy_claim(self):
        cases = []
        for index in range(30):
            cases.append({
                "case_id": f"silver-contract-fixture:{index}",
                "case_class": "real",
                "evidence_tier": "silver",
                "consent_status": "granted",
                "deidentified": True,
                "source_ref": "authorized:contract-fixture",
                "consent_record_id": f"consent-contract-fixture:{index}",
                "provenance_class": "external_observation",
                "observed_at": "2026-01-02T00:00:00+00:00",
                "double_review_complete": True,
                "retrospective_external_support": True,
                "predicted_claims": {"career:fixture": "supportive"},
                "observed_claims": {"career:fixture": "supportive"},
            })
        result = run_case_benchmark({"registry_id": "silver-contract-fixture", "minimum_cases_for_product_claim": 30, "cases": cases})
        self.assertEqual(30, result.eligible_silver_cases)
        self.assertEqual(0, result.eligible_gold_cases)
        self.assertFalse(result.product_accuracy_claim_allowed)
        self.assertIn("minimum_gold_case_threshold_not_met_for_product_accuracy_claim", result.warnings)
    def test_threshold_cannot_be_lowered_for_a_product_claim(self):
        with self.assertRaises(Phase22InputError): run_case_benchmark({"minimum_cases_for_product_claim": 1,"cases":[]})
    def test_duplicate_case_rejected(self):
        case = {"case_id": "x", "case_class": "synthetic", "predicted_claims": {}, "observed_claims": {}}
        with self.assertRaises(Phase22InputError): run_case_benchmark({"cases": [case, case]})

if __name__ == "__main__": unittest.main()
