from __future__ import annotations
import unittest
from mingli.phase22 import run_case_benchmark
from mingli.phase24 import assess_release_candidate, benchmark_phase24


def qualified_case(index: int, tier: str) -> dict[str, object]:
    scenario_id = ("career", "wealth", "relationship")[index % 3]
    case = {
        "case_id": f"{tier}:{index}",
        "person_case_id": f"person:{index}",
        "scenario_id": scenario_id,
        "case_class": "real",
        "evidence_tier": tier,
        "consent_status": "granted",
        "deidentified": True,
        "source_ref": "authorized:phase24-fixture",
        "consent_record_id": f"consent:{index}",
        "provenance_class": "external_observation",
        "observed_at": "2026-02-01T00:00:00+00:00",
        "double_review_complete": True,
        "review_disagreement": False,
        "predicted_claims": {f"{scenario_id}:{index}:{claim}": "supportive" for claim in range(4)},
        "observed_claims": {f"{scenario_id}:{index}:{claim}": "supportive" for claim in range(4)},
    }
    if tier == "gold":
        case.update({"prospective_prediction": True, "prediction_freeze_hash": f"sha256:{index:064x}", "prediction_frozen_at": "2026-01-01T00:00:00+00:00"})
    else:
        case["retrospective_external_support"] = True
    return case

class Phase24Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = assess_release_candidate()
    def test_local_rc_and_product_hold(self):
        self.assertTrue(self.result.local_technical_rc_ready); self.assertFalse(self.result.product_release_ready); self.assertEqual("technical_rc_only_product_hold", self.result.release_decision); self.assertEqual("PRODUCT_RELEASE_HOLD", self.result.product_release_status)
    def test_all_phase_gates_pass(self):
        self.assertEqual(list(range(16, 24)), [gate.phase for gate in self.result.phase_gates]); self.assertTrue(all(gate.status == "passed" for gate in self.result.phase_gates))
    def test_handoff_is_explicit(self):
        self.assertEqual(2, len(self.result.codex_handoff)); self.assertEqual({"P22_VALIDATION_CLOSURE", "PRODUCT_RELEASE_AUTHORIZATION"}, {item["blocker_id"] for item in self.result.blockers})
    def test_validation_closure_conditionally_removes_only_p22_blocker(self):
        cases = [qualified_case(index, "gold") for index in range(10)]
        cases.extend(qualified_case(index + 10, "silver") for index in range(20))
        report = run_case_benchmark({"registry_id": "phase24-closure", "minimum_cases_for_product_claim": 30, "pii_leak_count": 0, "cases": cases})
        result = assess_release_candidate(report)
        self.assertTrue(result.validation_closure_passed)
        self.assertFalse(result.product_accuracy_claim_allowed)
        self.assertEqual({"PRODUCT_RELEASE_AUTHORIZATION"}, {item["blocker_id"] for item in result.blockers})
        self.assertFalse(result.product_release_ready)
        self.assertEqual("technical_rc_only_product_hold", result.release_decision)
        self.assertEqual("PRODUCT_RELEASE_HOLD", result.product_release_status)
    def test_failed_validation_closure_keeps_p22_blocker(self):
        result = assess_release_candidate(run_case_benchmark({"registry_id": "phase24-empty", "pii_leak_count": 0, "cases": []}))
        self.assertFalse(result.validation_closure_passed)
        self.assertFalse(result.product_accuracy_claim_allowed)
        self.assertIn("P22_VALIDATION_CLOSURE", {item["blocker_id"] for item in result.blockers})
    def test_accuracy_claim_does_not_authorize_product_release(self):
        cases = [qualified_case(index, "gold") for index in range(30)]
        report = run_case_benchmark({"registry_id": "phase24-accuracy", "minimum_cases_for_product_claim": 30, "pii_leak_count": 0, "cases": cases})
        result = assess_release_candidate(report)
        self.assertTrue(result.validation_closure_passed)
        self.assertTrue(result.product_accuracy_claim_allowed)
        self.assertFalse(result.product_release_ready)
        self.assertEqual({"PRODUCT_RELEASE_AUTHORIZATION"}, {item["blocker_id"] for item in result.blockers})
    def test_release_gate_is_not_circular(self):
        self.assertFalse(self.result.provenance["benchmark_helpers_invoked"])
        self.assertEqual("independent_contract_checks@0.2",self.result.provenance["gate_source"])
    def test_benchmark_contract(self):
        result = benchmark_phase24(self.result); self.assertEqual(result["assertions_total"], result["passed"])

if __name__ == "__main__": unittest.main()
