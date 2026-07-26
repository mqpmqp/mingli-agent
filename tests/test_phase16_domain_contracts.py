from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema.validators import Draft202012Validator

import mingli.phase15 as phase15_module
from mingli.derived.static_engine import BRANCHES, STEMS
from mingli.phase15 import build_phase15_fixture, evaluate_bazi_tengod_domains
from mingli.phase16 import (
    PHASE16_METHOD_ID,
    PHASE16_SCHEMA_VERSION,
    Phase16InputError,
    benchmark_phase16,
    build_phase16_fixture,
    evaluate_base_domain_contracts,
    load_phase16_base_rules,
    load_phase16_result_schema,
    query_base_domain_contracts,
    validate_phase16_rules,
)
from mingli.phase16_contracts import BASE_DOMAINS, JUDGEMENT_LABELS

ROOT = Path(__file__).resolve().parents[1]


class Phase16EvaluationTests(unittest.TestCase):
    def test_phase15_fixture_cache_reuses_build_without_shared_mutable_state(self) -> None:
        cached_builder = getattr(phase15_module, "_build_phase15_fixture_cached", None)
        self.assertIsNotNone(cached_builder)
        cached_builder.cache_clear()
        first = build_phase15_fixture(STEMS[0], BRANCHES[2])
        first[0]["__test_mutation__"] = True
        second = build_phase15_fixture(STEMS[0], BRANCHES[2])
        self.assertNotIn("__test_mutation__", second[0])
        self.assertEqual(first[1:], second[1:])
        self.assertEqual(1, cached_builder.cache_info().misses)
        self.assertEqual(1, cached_builder.cache_info().hits)

    def test_formal_result_schema_accepts_runtime_output(self) -> None:
        schema = load_phase16_result_schema()
        self.assertEqual("object", schema["type"])
        Draft202012Validator(schema).validate(
            evaluate_base_domain_contracts(build_phase16_fixture(STEMS[0], BRANCHES[2])).to_dict()
        )

    def test_rule_manifest_and_large_assertion_matrix_pass(self) -> None:
        self.assertEqual(set(BASE_DOMAINS), set(load_phase16_base_rules()["domains"]))
        self.assertEqual((), validate_phase16_rules())
        result = benchmark_phase16()
        self.assertGreaterEqual(result.assertions_total, 3600)
        self.assertEqual(result.assertions_total, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)

    def test_contract_is_deterministic_complete_and_bounded(self) -> None:
        source = build_phase16_fixture(STEMS[0], BRANCHES[2])
        result = evaluate_base_domain_contracts(source)
        reordered = evaluate_base_domain_contracts(json.loads(json.dumps(source, ensure_ascii=False, sort_keys=True)))
        payload = result.to_dict()
        self.assertEqual(result.canonical_hash, reordered.canonical_hash)
        self.assertEqual(PHASE16_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(PHASE16_METHOD_ID, payload["method_id"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertEqual("base_rules_only", payload["domain_contract_validity"])
        target_ids = {item["target_id"] for item in source["domain_judgements"]}
        self.assertEqual(len(target_ids) * len(BASE_DOMAINS), len(result.domain_contracts))
        self.assertEqual(set(BASE_DOMAINS), set(result.domain_index))
        self.assertTrue(all(item.judgement_label in JUDGEMENT_LABELS for item in result.domain_contracts))
        self.assertTrue(all("base_domain_rule_only" in item.claim_boundary_codes for item in result.domain_contracts))
        forbidden = {"promotion_prediction", "profit_prediction", "marriage_prediction", "natural_language_renderer"}
        self.assertTrue(forbidden.isdisjoint(payload))

    def test_every_contract_has_complete_required_facets(self) -> None:
        result = evaluate_base_domain_contracts(build_phase16_fixture(STEMS[1], BRANCHES[5]))
        required = load_phase16_base_rules()["required_facets"]
        for contract in result.domain_contracts:
            facets = {
                item.facet_code
                for item in result.facet_assessments
                if item.target_id == contract.target_id and item.domain == contract.domain
            }
            self.assertEqual(set(required[contract.domain]), facets)
        self.assertTrue(all(item.evidence_status in {"matched", "unresolved"} for item in result.facet_assessments))
        self.assertTrue(all(item.confidence == "low" for item in result.facet_assessments if item.evidence_status == "unresolved"))

    def test_domain_contract_exposes_auditable_confidence_and_plain_language(self) -> None:
        result = evaluate_base_domain_contracts(build_phase16_fixture(STEMS[0], BRANCHES[2]))
        expected_facets = {
            "career": {"system_fit", "enterprise_employment", "professional_technical", "management", "entrepreneurship", "freelance", "stability", "growth_space", "pressure_sources", "position_direction"},
            "wealth": {"earned_income", "variable_income", "income_stability", "risk_preference", "retention", "cashflow", "investment_boundary", "debt_risk", "income_model"},
            "relationship": {"attraction", "communication", "boundaries", "dependency", "conflict", "stability", "marriage_tendency", "reality_obstacles"},
        }
        self.assertEqual(expected_facets, {key: set(value) for key, value in load_phase16_base_rules()["required_facets"].items()})
        for contract in result.domain_contracts:
            self.assertIn(contract.confidence_score, {30, 60, 85})
            self.assertEqual(bool(contract.reality_override_direction), contract.reality_override)
            self.assertEqual(contract.claim_boundary_codes, contract.boundary_flags)
            self.assertTrue(contract.plain_language_explanation.endswith("该结果不表示具体事件会发生。"))
            self.assertTrue(set(contract.supporting_evidence_ids).isdisjoint(contract.limiting_evidence_ids))
            self.assertEqual(
                {f"facet:{item.facet_code}" for item in result.facet_assessments if item.target_id == contract.target_id and item.domain == contract.domain and item.evidence_status == "unresolved"},
                set(contract.missing_inputs),
            )

    def test_phase15_reality_override_and_conflict_are_preserved(self) -> None:
        graph, interaction, trend = build_phase15_fixture(STEMS[0], BRANCHES[2])
        baseline = evaluate_bazi_tengod_domains(graph, interaction, trend)
        target = next(item.target_id for item in baseline.domain_judgements if item.domain == "career")
        support = {
            "target_id": target,
            "domain": "career",
            "direction": "support",
            "detail": "verified career reality",
            "weight": 10,
            "verified": True,
            "source_id": "phase16-test-support",
        }
        supported_source = evaluate_bazi_tengod_domains(graph, interaction, trend, reality_evidence=(support,)).to_dict()
        supported = evaluate_base_domain_contracts(supported_source)
        item = next(value for value in supported.domain_contracts if value.target_id == target and value.domain == "career")
        self.assertEqual("support", item.reality_override_direction)
        self.assertEqual("support_tendency", item.judgement_label)
        self.assertEqual("high", item.confidence)
        conflicted_source = evaluate_bazi_tengod_domains(graph, interaction, trend, reality_evidence=(
            support,
            {**support, "direction": "contradict", "source_id": "phase16-test-conflict", "evidence_id": "phase16-conflict"},
        )).to_dict()
        conflicted = evaluate_base_domain_contracts(conflicted_source)
        conflict_item = next(value for value in conflicted.domain_contracts if value.target_id == target and value.domain == "career")
        self.assertEqual("unresolved", conflict_item.judgement_label)
        self.assertEqual("low", conflict_item.confidence)
        self.assertIsNone(conflict_item.reality_override_direction)

    def test_queries_and_invalid_inputs(self) -> None:
        source = build_phase16_fixture(STEMS[0], BRANCHES[2])
        result = evaluate_base_domain_contracts(source)
        year_item = next(item for item in result.domain_contracts if item.label_year is not None)
        age_item = next(item for item in result.domain_contracts if item.start_age is not None)
        self.assertTrue(query_base_domain_contracts(result, year=year_item.label_year, domain=year_item.domain))
        self.assertTrue(query_base_domain_contracts(result, age=age_item.start_age, domain=age_item.domain))
        self.assertEqual(set(BASE_DOMAINS), {item["domain"] for item in query_base_domain_contracts(result, target_id=year_item.target_id)})
        with self.assertRaisesRegex(Phase16InputError, "required"):
            evaluate_base_domain_contracts({})
        with self.assertRaisesRegex(Phase16InputError, "canonical_hash mismatch"):
            evaluate_base_domain_contracts({**source, "canonical_hash": "sha256:bad"})
        with self.assertRaisesRegex(Phase16InputError, "canonical_digest mismatch"):
            broken = json.loads(json.dumps(source))
            broken["domain_judgements"][0]["active_theme_codes"] = ["tampered"]
            evaluate_base_domain_contracts(broken)
        with self.assertRaisesRegex(Phase16InputError, "exactly one"):
            query_base_domain_contracts(result)
        with self.assertRaisesRegex(Phase16InputError, "unsupported domain"):
            query_base_domain_contracts(result, target_id=year_item.target_id, domain="health")
        with self.assertRaisesRegex(Phase16InputError, "cannot return"):
            evaluate_base_domain_contracts(source, requested_outputs=("profit_prediction",))


class Phase16CliTests(unittest.TestCase):
    def test_cli_surface_outputs_json(self) -> None:
        source = build_phase16_fixture(STEMS[0], BRANCHES[2])
        result = evaluate_base_domain_contracts(source)
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}
        }
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "phase15.json"
            result_path = Path(directory) / "phase16.json"
            source_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            result_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False), encoding="utf-8")
            year_item = next(item for item in result.domain_contracts if item.label_year is not None)
            commands = (
                ("evaluate", "--phase15-result", str(source_path)),
                ("query", "--result", str(result_path), "--year", str(year_item.label_year), "--domain", year_item.domain),
                ("validate",),
                ("rules",),
                ("schemas",),
                ("provenance", "--expected-root", str(ROOT)),
            )
            for command in commands:
                completed = subprocess.run(
                    [sys.executable, "-m", "mingli.phase16_cli", *command],
                    cwd=ROOT,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertTrue(json.loads(completed.stdout))


if __name__ == "__main__":
    unittest.main()
