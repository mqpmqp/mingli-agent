from __future__ import annotations
import unittest
from mingli.phase21 import Phase21InputError, benchmark_phase21, generate_five_year_outlook, renderer_years

class Phase21Tests(unittest.TestCase):
    def test_benchmark(self):
        result = benchmark_phase21(); self.assertEqual(result["assertions_total"], result["passed"])
    def test_exact_window_and_renderer_adapter(self):
        result = generate_five_year_outlook({"anchor_year": 2026, "baseline_domains": {"career": "mixed", "wealth": "mixed", "relationship": "mixed"}})
        self.assertEqual([2024, 2025, 2026, 2027, 2028], [x.year for x in result.years]); self.assertEqual(5, len(renderer_years(result)))
    def test_conflicting_verified_reality_unresolved(self):
        raw = {"anchor_year": 2026, "baseline_domains": {"career": "supportive", "wealth": "mixed", "relationship": "mixed"}, "annual_evidence": [{"evidence_id": "a", "year": 2026, "domain": "career", "signal": 2, "verified_reality": "support","source_type":"reality","source_id":"a","verified":True}, {"evidence_id": "b", "year": 2026, "domain": "career", "signal": -2, "verified_reality": "contradict","source_type":"reality","source_id":"b","verified":True}]}
        result = generate_five_year_outlook(raw); self.assertEqual("unresolved", result.years[2].domain_statuses["career"])
    def test_concrete_event_rejected(self):
        raw = {"anchor_year": 2026, "baseline_domains": {}, "annual_evidence": [{"year": 2026, "domain": "career", "signal": 1, "event": "录用"}]}
        with self.assertRaises(Phase21InputError): generate_five_year_outlook(raw)
    def test_reality_override_requires_verified_provenance(self):
        raw={"anchor_year":2026,"baseline_domains":{},"annual_evidence":[{"evidence_id":"x","year":2026,"domain":"career","signal":0,"verified_reality":"support","source_type":"reality","source_id":"user"}]}
        with self.assertRaises(Phase21InputError): generate_five_year_outlook(raw)

if __name__ == "__main__": unittest.main()
