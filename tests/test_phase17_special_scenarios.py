from __future__ import annotations
import unittest
from mingli.phase17 import benchmark_phase17, build_phase17_fixture, evaluate_special_scenario, validate_phase17_rules
from mingli.phase17_contracts import Phase17InputError, SCENARIO_LAYERS

class Phase17Tests(unittest.TestCase):
    def setUp(self): self.source,self.target=build_phase17_fixture()
    def test_validation_and_benchmark(self):
        self.assertEqual((),validate_phase17_rules()); result=benchmark_phase17(); self.assertEqual(result["assertions_total"],result["passed"]); self.assertEqual(0,result["failed"])
    def test_exam_layers_and_hard_boundary(self):
        result=evaluate_special_scenario(self.source,scenario="career_exam",target_id=self.target,reality_context={"major_eligible":False,"preparation_months":1})
        self.assertEqual(SCENARIO_LAYERS["career_exam"],tuple(item.layer for item in result.layers))
        self.assertFalse(next(x for x in result.layers if x.layer=="system_fit").reality_override)
        self.assertEqual("conflict",next(x for x in result.layers if x.layer=="admission_outlook").label)
    def test_reunion_layers_and_scope(self):
        result=evaluate_special_scenario(self.source,scenario="relationship_reunion",target_id=self.target,reality_context={"other_party_status":"married","no_contact_months":24})
        self.assertEqual(SCENARIO_LAYERS["relationship_reunion"],tuple(item.layer for item in result.layers))
        self.assertFalse(next(x for x in result.layers if x.layer=="attraction").reality_override)
        self.assertTrue(all(next(x for x in result.layers if x.layer==layer).label=="conflict" for layer in ("recontact","reunion","stability")))
    def test_published_eligibility_and_safety_facts_are_hard_gates(self):
        exam=evaluate_special_scenario(self.source,scenario="career_exam",target_id=self.target,reality_context={"age_eligible":False,"job_requirements_met":False})
        self.assertTrue(next(x for x in exam.layers if x.layer=="admission_outlook").reality_override)
        reunion=evaluate_special_scenario(self.source,scenario="relationship_reunion",target_id=self.target,reality_context={"legal_contact_restriction":True,"root_cause_resolved":True})
        self.assertTrue(next(x for x in reunion.layers if x.layer=="recontact").reality_override)
        self.assertEqual("conflict",next(x for x in reunion.layers if x.layer=="stability").label)
    def test_invalid_and_blocked(self):
        with self.assertRaises(Phase17InputError): evaluate_special_scenario(self.source,scenario="health",target_id=self.target)
        with self.assertRaises(Phase17InputError): evaluate_special_scenario(self.source,scenario="career_exam",target_id="missing")
        with self.assertRaises(Phase17InputError): evaluate_special_scenario(self.source,scenario="career_exam",target_id=self.target,requested_outputs=("guaranteed_admission",))

if __name__=="__main__": unittest.main()
