from __future__ import annotations
import unittest
from mingli.phase20 import DISCLAIMER, Phase20InputError, benchmark_phase20, render_yuan_eight_sections

def fixture():
    return {"profile": {"calendar": "lunar", "birth_date": "1984-01-01", "birth_time": "23:00"}, "chenggu": {"display_weight": "3两9钱", "verse_available": False}, "domains": {"career": "mixed", "wealth": "unresolved", "relationship": "challenging"}, "domain_confidence": {"career": "medium", "wealth": "low", "relationship": "medium"}, "five_years": [{"year": y, "status": "mixed", "confidence": "low"} for y in range(2026, 2031)]}

class Phase20Tests(unittest.TestCase):
    def test_benchmark(self):
        result = benchmark_phase20(); self.assertEqual(result["assertions_total"], result["passed"])
    def test_eight_sections_and_disclaimer(self):
        result = render_yuan_eight_sections(fixture()); self.assertEqual(8, len(result.sections)); self.assertEqual(1, result.rendered_text.count(DISCLAIMER)); self.assertTrue(result.rendered_text.endswith(DISCLAIMER))
        self.assertIn("置信度：低", result.sections[6].content)
    def test_five_year_contract(self):
        raw = fixture(); raw["five_years"] = raw["five_years"][:4]
        with self.assertRaises(Phase20InputError): render_yuan_eight_sections(raw)
    def test_no_unverified_verse_or_guarantee(self):
        raw = fixture(); raw["chenggu"] = {"verse_available": True, "verified_verse": "未经核心包审核的歌诀"}
        with self.assertRaises(Phase20InputError): render_yuan_eight_sections(raw)
    def test_caller_cannot_inject_overall_conclusion(self):
        raw = fixture(); raw["overall_status"] = "supportive"
        with self.assertRaisesRegex(Phase20InputError, "overall_status"):
            render_yuan_eight_sections(raw)
    def test_confidence_contract_is_required(self):
        raw = fixture(); raw.pop("domain_confidence")
        with self.assertRaisesRegex(Phase20InputError, "domain_confidence"):
            render_yuan_eight_sections(raw)
        raw = fixture(); raw["five_years"][0].pop("confidence")
        with self.assertRaisesRegex(Phase20InputError, "confidence"):
            render_yuan_eight_sections(raw)
    def test_unresolved_output_cannot_claim_high_confidence(self):
        raw = fixture(); raw["domain_confidence"]["wealth"] = "high"
        with self.assertRaisesRegex(Phase20InputError, "unresolved"):
            render_yuan_eight_sections(raw)
        raw = fixture(); raw["five_years"][0] = {"year": 2026, "status": "unresolved", "confidence": "high"}
        with self.assertRaisesRegex(Phase20InputError, "unresolved"):
            render_yuan_eight_sections(raw)

if __name__ == "__main__": unittest.main()
