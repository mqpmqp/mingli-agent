from __future__ import annotations
import unittest
from mingli.phase23 import RUNTIME_STAGES, benchmark_phase23, run_mingli_agent

def fixture():
    return {
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
        "fusion_evidence": [{
            "evidence_id": "verified-wealth",
            "claim_id": "wealth",
            "scope": "runtime:baseline",
            "source_type": "reality",
            "source_id": "user-confirmed",
            "direction": "contradict",
            "weight": 0,
            "priority": 100,
            "verified": True,
        }],
    }

class Phase23Tests(unittest.TestCase):
    def test_benchmark(self):
        result = benchmark_phase23(); self.assertEqual(result["assertions_total"], result["passed"])
    def test_end_to_end(self):
        result = run_mingli_agent(fixture())
        self.assertEqual(RUNTIME_STAGES, tuple(stage.stage for stage in result.stages))
        self.assertEqual(37, result.chenggu["total_qian"])
        self.assertEqual(8, len(result.renderer["sections"]))
        self.assertEqual("challenging", result.effective_domain_statuses["wealth"])
        self.assertEqual(result.evidence_fusion["claims"][0]["confidence"], result.effective_domain_confidence["wealth"])
        self.assertTrue(all(
            result.effective_domain_confidence[domain] == "low"
            for domain, status in result.effective_domain_statuses.items()
            if status == "unresolved"
        ))
        self.assertEqual("resolved_by_reality_override", result.evidence_fusion["claims"][0]["status"])
        self.assertEqual("not_evaluated", result.prediction_validity)

    def test_runtime_uses_real_phase7_to_phase16_artifacts(self):
        result = run_mingli_agent(fixture())
        for name in (
            "fact_graph", "strength", "pattern", "regulation", "xiji",
            "luck_interactions", "temporal_trends", "domain_rules", "domain_contracts",
        ):
            artifact = result.artifacts[name]
            self.assertTrue(str(artifact["canonical_hash"]).startswith("sha256:"), name)
        self.assertEqual(
            result.artifacts["domain_rules"]["canonical_hash"],
            result.artifacts["domain_contracts"]["phase15_result_hash"],
        )

    def test_legacy_caller_baseline_cannot_bypass_domain_rules(self):
        payload = fixture()
        payload["baseline_domains"] = {"career": "supportive", "wealth": "supportive", "relationship": "supportive"}
        with self.assertRaisesRegex(ValueError, "baseline_domains"):
            run_mingli_agent(payload)
    def test_caller_overall_status_cannot_bypass_runtime_chain(self):
        payload = fixture()
        payload["overall_status"] = "supportive"
        with self.assertRaisesRegex(ValueError, "overall_status"):
            run_mingli_agent(payload)
    def test_runtime_is_deterministic(self):
        left, right = run_mingli_agent(fixture()), run_mingli_agent(fixture()); self.assertEqual(left.canonical_hash, right.canonical_hash)

if __name__ == "__main__": unittest.main()
