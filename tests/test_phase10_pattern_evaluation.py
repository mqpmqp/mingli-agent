from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mingli.derived.static_engine import BRANCHES, STEMS
from mingli.contracts.serialization import digest
from mingli.phase8_contracts import EvidenceRecord as Phase8EvidenceRecord
from mingli.phase10 import (
    PHASE10_METHOD_ID,
    PHASE10_SCHEMA_VERSION,
    benchmark_phase10,
    build_pattern_fixture_inputs,
    evaluate_bazi_pattern,
    load_phase10_pattern_profiles,
    pattern_result_to_phase8_evidence,
    validate_phase10_profiles,
)
from mingli.phase10_contracts import Phase10InputError

ROOT = Path(__file__).resolve().parents[1]


def rehash_strength(value: dict[str, object]) -> dict[str, object]:
    body = {key: item for key, item in value.items() if key not in {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}}
    value["canonical_hash"] = digest({"record_type": "DayMasterStrengthResult", "payload": body})
    return value


def rehash_graph(value: dict[str, object]) -> dict[str, object]:
    value["canonical_hash"] = digest({key: item for key, item in value.items() if key != "canonical_hash"})
    return value


def fixture(day_stem: str = STEMS[0], month_branch: str = BRANCHES[2]):
    return build_pattern_fixture_inputs(day_stem, month_branch)


class Phase10EvaluationTests(unittest.TestCase):
    def test_profile_and_large_assertion_matrix_pass(self) -> None:
        self.assertTrue(load_phase10_pattern_profiles()["profiles"])
        self.assertEqual((), validate_phase10_profiles())
        result = benchmark_phase10()
        self.assertGreaterEqual(result.assertions_total, 1200)
        self.assertEqual(result.assertions_total, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)
        self.assertEqual(0, result.schema_failures)
        self.assertEqual(0, result.provenance_failures)
        self.assertEqual(0, result.hash_mismatches)
        self.assertEqual(0, result.threshold_gaps)
        self.assertEqual(0, result.threshold_overlaps)
        self.assertEqual(0, result.conflict_order_failures)

    def test_evaluation_is_deterministic_and_structural_only(self) -> None:
        graph, strength = fixture()
        result = evaluate_bazi_pattern(graph, strength)
        reordered = evaluate_bazi_pattern(
            json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True)),
            json.loads(json.dumps(strength, ensure_ascii=False, sort_keys=True)),
        )
        payload = result.to_dict()
        self.assertEqual(result.canonical_hash, reordered.canonical_hash)
        self.assertEqual(PHASE10_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(PHASE10_METHOD_ID, payload["method_id"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertTrue(payload["candidates"])
        self.assertTrue(payload["evidence_records"])
        self.assertTrue(all(candidate["establishment_conditions"] for candidate in payload["candidates"]))
        self.assertTrue(all("breaking_conditions" in candidate for candidate in payload["candidates"]))
        forbidden = json.dumps(payload, ensure_ascii=False).lower()
        for token in ("yongshen", "xiji", "auspicious", "career prediction", "event window"):
            self.assertNotIn(token, forbidden)

    def test_evidence_converts_to_phase8_records(self) -> None:
        graph, strength = fixture()
        records = pattern_result_to_phase8_evidence(evaluate_bazi_pattern(graph, strength))
        self.assertTrue(records)
        self.assertTrue(all(isinstance(item, Phase8EvidenceRecord) for item in records))
        self.assertTrue(all(item.canonical_digest.startswith("sha256:") for item in records))

    def test_blocked_inputs_are_not_guessed(self) -> None:
        graph, strength = fixture()
        with self.assertRaisesRegex(Phase10InputError, "Fact Graph"):
            evaluate_bazi_pattern({}, strength)
        with self.assertRaisesRegex(Phase10InputError, "Strength Result"):
            evaluate_bazi_pattern(graph, {})
        with self.assertRaisesRegex(Phase10InputError, "prediction_validity"):
            evaluate_bazi_pattern({**graph, "prediction_validity": "evaluated"}, strength)
        with self.assertRaisesRegex(Phase10InputError, "classification"):
            evaluate_bazi_pattern(graph, {**strength, "classification": "unresolved"})
        with self.assertRaisesRegex(Phase10InputError, "unsupported pattern profile"):
            evaluate_bazi_pattern(graph, strength, profile_id="unsupported@0.1")
        with self.assertRaisesRegex(Phase10InputError, "ten-god structure"):
            evaluate_bazi_pattern(rehash_graph({**graph, "nodes": [node for node in graph["nodes"] if node.get("node_type") != "TenGod"]}), strength)
        with self.assertRaisesRegex(Phase10InputError, "canonical_hash mismatch"):
            evaluate_bazi_pattern(graph, {**strength, "support_score": "999"})

    def test_special_candidates_never_become_fully_supported(self) -> None:
        graph, strength = fixture()
        result = evaluate_bazi_pattern(graph, rehash_strength({**strength, "classification": "very_weak"}))
        special = [item for item in result.candidates if item.pattern_type.endswith("_candidate")]
        self.assertTrue(special)
        self.assertTrue(all(item.status in {"conditionally_supported", "unresolved"} for item in special))


class Phase10CliTests(unittest.TestCase):
    def test_cli_surface_outputs_json(self) -> None:
        graph, strength = fixture()
        env = {
            key: value for key, value in os.environ.items()
            if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}
        }
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory() as directory:
            graph_path = Path(directory) / "graph.json"
            strength_path = Path(directory) / "strength.json"
            graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
            strength_path.write_text(json.dumps(strength, ensure_ascii=False), encoding="utf-8")
            commands = (
                ("evaluate", "--graph", str(graph_path), "--strength", str(strength_path)),
                ("validate",),
                ("benchmark",),
                ("profiles",),
                ("schemas",),
                ("provenance", "--expected-root", str(ROOT)),
            )
            for command in commands:
                completed = subprocess.run(
                    [sys.executable, "-m", "mingli.phase10_cli", *command],
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
