from __future__ import annotations
import unittest
from mingli.phase18 import Phase18InputError,benchmark_phase18,normalize_reality_context,orchestrate_evidence_fusion
class Phase18Tests(unittest.TestCase):
    def test_benchmark(self):
        r=benchmark_phase18(); self.assertEqual(r["assertions_total"],r["passed"]); self.assertEqual(0,r["failed"])
    def test_aliases_and_conflicts(self):
        c=normalize_reality_context({"no_contact_duration_months":12,"major_not_eligible":True}); self.assertEqual(12,c.facts["no_contact_months"]); self.assertFalse(c.facts["major_eligible"])
        with self.assertRaises(Phase18InputError): normalize_reality_context({"unknown":1})
    def test_scope_specific_override(self):
        items=[{"evidence_id":"c","claim_id":"x","scope":"a","source_type":"chart","source_id":"p16","direction":"support","weight":10,"priority":90},{"evidence_id":"r","claim_id":"x","scope":"a","source_type":"reality","source_id":"user","direction":"contradict","weight":0,"priority":100,"verified":True},{"evidence_id":"other","claim_id":"x","scope":"b","source_type":"chart","source_id":"p16","direction":"support","weight":2,"priority":50}]
        result=orchestrate_evidence_fusion({},items); by_scope={x.scope:x for x in result.claims}; self.assertEqual("contradict",by_scope["a"].hard_override_direction); self.assertIsNone(by_scope["b"].hard_override_direction); self.assertIn("c",by_scope["a"].conflicting_evidence_ids)
        self.assertGreaterEqual(by_scope["a"].confidence_score,50); self.assertGreater(by_scope["a"].contradiction_penalty,0); self.assertEqual(0,by_scope["a"].missing_source_penalty)
        self.assertEqual("low",by_scope["b"].confidence); self.assertEqual(30,by_scope["b"].missing_source_penalty)
if __name__=="__main__": unittest.main()
