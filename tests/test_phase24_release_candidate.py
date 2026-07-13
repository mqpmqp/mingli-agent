from __future__ import annotations
import unittest
from mingli.phase24 import assess_release_candidate, benchmark_phase24

class Phase24Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = assess_release_candidate()
    def test_local_rc_and_product_hold(self):
        self.assertTrue(self.result.local_technical_rc_ready); self.assertFalse(self.result.product_release_ready); self.assertEqual("technical_rc_only_product_hold", self.result.release_decision)
    def test_all_phase_gates_pass(self):
        self.assertEqual(list(range(16, 24)), [gate.phase for gate in self.result.phase_gates]); self.assertTrue(all(gate.status == "passed" for gate in self.result.phase_gates))
    def test_handoff_is_explicit(self):
        self.assertEqual(4, len(self.result.codex_handoff)); self.assertIn("CLOUD_CI", {item["blocker_id"] for item in self.result.blockers})
    def test_benchmark_contract(self):
        result = benchmark_phase24(self.result); self.assertEqual(result["assertions_total"], result["passed"])

if __name__ == "__main__": unittest.main()
