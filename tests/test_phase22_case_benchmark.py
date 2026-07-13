from __future__ import annotations
import unittest
from mingli.phase22 import Phase22InputError, benchmark_phase22, run_case_benchmark

class Phase22Tests(unittest.TestCase):
    def test_benchmark(self):
        result = benchmark_phase22(); self.assertEqual(result["assertions_total"], result["passed"]); self.assertEqual(0, result["real_case_count"])
    def test_empty_registry_has_no_accuracy(self):
        result = run_case_benchmark(); self.assertIsNone(result.exact_match_rate); self.assertFalse(result.product_accuracy_claim_allowed)
    def test_synthetic_never_counts(self):
        result = run_case_benchmark({"minimum_cases_for_product_claim": 1, "cases": [{"case_id": "s", "case_class": "synthetic", "predicted_claims": {"x": "mixed"}, "observed_claims": {"x": "mixed"}}]})
        self.assertEqual(0, result.eligible_real_cases); self.assertIsNone(result.exact_match_rate)
    def test_duplicate_case_rejected(self):
        case = {"case_id": "x", "case_class": "synthetic", "predicted_claims": {}, "observed_claims": {}}
        with self.assertRaises(Phase22InputError): run_case_benchmark({"cases": [case, case]})

if __name__ == "__main__": unittest.main()
