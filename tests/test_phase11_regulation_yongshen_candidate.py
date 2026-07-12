from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mingli.contracts.serialization import digest
from mingli.derived.static_engine import BRANCHES, STEMS
from mingli.phase8_contracts import EvidenceRecord as Phase8EvidenceRecord
from mingli.phase10 import evaluate_bazi_pattern
from mingli.phase11 import (
    PHASE11_METHOD_ID,
    PHASE11_SCHEMA_VERSION,
    benchmark_phase11,
    build_regulation_fixture_inputs,
    evaluate_bazi_regulation,
    load_phase11_regulation_profiles,
    regulation_result_to_phase8_evidence,
    validate_phase11_profiles,
)
from mingli.phase11_contracts import Phase11InputError
from mingli.phase9_contracts import ELEMENTS

ROOT = Path(__file__).resolve().parents[1]


def rehash_strength(value: dict[str, object]) -> dict[str, object]:
    body = {key: item for key, item in value.items() if key not in {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}}
    value["canonical_hash"] = digest({"record_type": "DayMasterStrengthResult", "payload": body})
    return value


def rehash_pattern(value: dict[str, object]) -> dict[str, object]:
    body = {key: item for key, item in value.items() if key not in {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}}
    value["canonical_hash"] = digest({"record_type": "BaziPatternEvaluationResult", "payload": body})
    return value


def fixture(day_stem: str = STEMS[0], month_branch: str = BRANCHES[2]):
    return build_regulation_fixture_inputs(day_stem, month_branch)


class Phase11EvaluationTests(unittest.TestCase):
    def test_profile_and_large_assertion_matrix_pass(self) -> None:
        self.assertTrue(load_phase11_regulation_profiles()["profiles"])
        self.assertEqual((), validate_phase11_profiles())
        result = benchmark_phase11()
        self.assertGreaterEqual(result.assertions_total, 1600)
        self.assertEqual(result.assertions_total, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)
        self.assertEqual(0, result.schema_failures)
        self.assertEqual(0, result.provenance_failures)
        self.assertEqual(0, result.hash_mismatches)
        self.assertEqual(0, result.threshold_gaps)
        self.assertEqual(0, result.threshold_overlaps)
        self.assertEqual(0, result.conflict_order_failures)
        self.assertEqual(0, result.unsupported_classical_claims)
        self.assertEqual(0, result.xiji_boundary_failures)

    def test_evaluation_is_deterministic_and_candidate_only(self) -> None:
        graph, strength, pattern = fixture()
        result = evaluate_bazi_regulation(graph, strength, pattern)
        reordered = evaluate_bazi_regulation(
            json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True)),
            json.loads(json.dumps(strength, ensure_ascii=False, sort_keys=True)),
            json.loads(json.dumps(pattern, ensure_ascii=False, sort_keys=True)),
        )
        payload = result.to_dict()
        self.assertEqual(result.canonical_hash, reordered.canonical_hash)
        self.assertEqual(PHASE11_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(PHASE11_METHOD_ID, payload["method_id"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertEqual(set(ELEMENTS), {candidate["element"] for candidate in payload["candidates"]})
        self.assertTrue(all(candidate["stem_carriers"] for candidate in payload["candidates"]))
        self.assertTrue(all(set(candidate["score_by_lens"]) == {"strength_balance", "seasonal_climate", "element_passage", "pattern_remedy"} for candidate in payload["candidates"]))
        self.assertTrue(payload["strength_balance_needs"])
        self.assertTrue(payload["seasonal_climate_needs"])
        self.assertIn("classical_daymaster_month_tiaohou_status", payload["seasonal_climate_needs"][0])
        forbidden = {"final_yongshen", "definite_yongshen", "absolute_favorable", "absolute_unfavorable"}
        self.assertTrue(forbidden.isdisjoint(payload))

    def test_evidence_converts_to_phase8_records(self) -> None:
        graph, strength, pattern = fixture()
        records = regulation_result_to_phase8_evidence(evaluate_bazi_regulation(graph, strength, pattern))
        self.assertTrue(records)
        self.assertTrue(all(isinstance(item, Phase8EvidenceRecord) for item in records))
        self.assertTrue(all(item.canonical_digest.startswith("sha256:") for item in records))

    def test_blocked_inputs_are_not_guessed(self) -> None:
        graph, strength, pattern = fixture()
        with self.assertRaisesRegex(Phase11InputError, "Fact Graph"):
            evaluate_bazi_regulation({}, strength, pattern)
        with self.assertRaisesRegex(Phase11InputError, "Strength Result"):
            evaluate_bazi_regulation(graph, {}, pattern)
        with self.assertRaisesRegex(Phase11InputError, "Pattern Result"):
            evaluate_bazi_regulation(graph, strength, {})
        with self.assertRaisesRegex(Phase11InputError, "prediction_validity"):
            evaluate_bazi_regulation(graph, {**strength, "prediction_validity": "evaluated"}, pattern)
        with self.assertRaisesRegex(Phase11InputError, "canonical_hash mismatch"):
            evaluate_bazi_regulation(graph, {**strength, "support_score": "999"}, pattern)
        with self.assertRaisesRegex(Phase11InputError, "hash reference mismatch"):
            evaluate_bazi_regulation(graph, strength, rehash_pattern({**pattern, "strength_result_hash": "sha256:bad"}))
        with self.assertRaisesRegex(Phase11InputError, "final XiJi"):
            evaluate_bazi_regulation(graph, strength, pattern, requested_outputs=("xiji",))

    def test_balanced_and_unresolved_boundaries_are_explicit(self) -> None:
        graph, strength, pattern = fixture()
        balanced = evaluate_bazi_regulation(graph, rehash_strength({**strength, "classification": "balanced"}), pattern)
        self.assertTrue(all("strength_balance" not in candidate.supporting_lenses for candidate in balanced.candidates))
        unresolved_pattern = json.loads(json.dumps(pattern, ensure_ascii=False))
        unresolved_pattern["candidates"][0]["status"] = "unresolved"
        unresolved_pattern["unresolved_candidates"] = [unresolved_pattern["candidates"][0]["candidate_id"]]
        unresolved = evaluate_bazi_regulation(graph, strength, rehash_pattern(unresolved_pattern))
        self.assertTrue(unresolved.unresolved)
        self.assertTrue(unresolved.unresolved_candidates or unresolved.unresolved)


class Phase11CliTests(unittest.TestCase):
    def test_cli_surface_outputs_json(self) -> None:
        graph, strength, pattern = fixture()
        env = {
            key: value for key, value in os.environ.items()
            if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}
        }
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory() as directory:
            graph_path = Path(directory) / "graph.json"
            strength_path = Path(directory) / "strength.json"
            pattern_path = Path(directory) / "pattern.json"
            graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
            strength_path.write_text(json.dumps(strength, ensure_ascii=False), encoding="utf-8")
            pattern_path.write_text(json.dumps(pattern, ensure_ascii=False), encoding="utf-8")
            commands = (
                ("evaluate", "--graph", str(graph_path), "--strength", str(strength_path), "--pattern", str(pattern_path)),
                ("validate",),
                ("benchmark",),
                ("profiles",),
                ("schemas",),
                ("provenance", "--expected-root", str(ROOT)),
            )
            for command in commands:
                completed = subprocess.run(
                    [sys.executable, "-m", "mingli.phase11_cli", *command],
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
