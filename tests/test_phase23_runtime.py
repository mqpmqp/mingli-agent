from __future__ import annotations
import unittest
from mingli.phase23 import RUNTIME_STAGES, benchmark_phase23, run_mingli_agent

def fixture():
    return {"chart_input": {"gender": "female", "calendar": "lunar", "birth_date": "1984-01-01", "birth_time": "23:00", "timezone": "+08:00", "birth_location": {}, "true_solar_time": False}, "anchor_year": 2026, "baseline_domains": {"career": "mixed", "wealth": "mixed", "relationship": "mixed"}}

class Phase23Tests(unittest.TestCase):
    def test_benchmark(self):
        result = benchmark_phase23(); self.assertEqual(result["assertions_total"], result["passed"])
    def test_end_to_end(self):
        result = run_mingli_agent(fixture()); self.assertEqual(RUNTIME_STAGES, tuple(stage.stage for stage in result.stages)); self.assertEqual(39, result.chenggu["total_qian"]); self.assertEqual(8, len(result.renderer["sections"]))
    def test_runtime_is_deterministic(self):
        left, right = run_mingli_agent(fixture()), run_mingli_agent(fixture()); self.assertEqual(left.canonical_hash, right.canonical_hash)

if __name__ == "__main__": unittest.main()
