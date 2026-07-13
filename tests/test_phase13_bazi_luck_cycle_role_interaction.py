from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mingli.derived.static_engine import BRANCHES, STEMS
from mingli.phase8_contracts import EvidenceRecord as Phase8EvidenceRecord
from mingli.phase12_contracts import record_digest as phase12_record_digest
from mingli.phase13 import (
    PHASE13_METHOD_ID,
    PHASE13_SCHEMA_VERSION,
    Phase13InputError,
    benchmark_phase13,
    build_phase13_fixture,
    evaluate_luck_cycle_role_interactions,
    interaction_result_to_phase8_evidence,
    load_phase13_interaction_profiles,
    validate_phase13_profiles,
)
from mingli.phase13_contracts import STRUCTURAL_STATES

ROOT = Path(__file__).resolve().parents[1]
METADATA_FIELDS = {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}


def fixture(day_stem: str = STEMS[0], month_branch: str = BRANCHES[2]):
    return build_phase13_fixture(day_stem, month_branch)


class Phase13EvaluationTests(unittest.TestCase):
    def test_profile_and_large_assertion_matrix_pass(self) -> None:
        self.assertTrue(load_phase13_interaction_profiles()["profiles"])
        self.assertEqual((), validate_phase13_profiles())
        result = benchmark_phase13()
        self.assertGreaterEqual(result.assertions_total, 3600)
        self.assertEqual(result.assertions_total, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)
        self.assertEqual(0, result.schema_failures)
        self.assertEqual(0, result.provenance_failures)
        self.assertEqual(0, result.hash_mismatches)
        self.assertEqual(0, result.timeline_failures)
        self.assertEqual(0, result.partition_failures)
        self.assertEqual(0, result.relation_failures)
        self.assertEqual(0, result.prediction_boundary_failures)

    def test_evaluation_is_deterministic_and_structural_only(self) -> None:
        graph, xiji = fixture()
        result = evaluate_luck_cycle_role_interactions(graph, xiji)
        reordered = evaluate_luck_cycle_role_interactions(
            json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True)),
            json.loads(json.dumps(xiji, ensure_ascii=False, sort_keys=True)),
        )
        payload = result.to_dict()
        self.assertEqual(result.canonical_hash, reordered.canonical_hash)
        self.assertEqual(PHASE13_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(PHASE13_METHOD_ID, payload["method_id"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertEqual(10, len(payload["dayun_interactions"]))
        self.assertEqual(10, len(payload["liunian_interactions"]))
        self.assertTrue(all(item["structural_state"] in STRUCTURAL_STATES for item in payload["dayun_interactions"] + payload["liunian_interactions"]))
        self.assertTrue(all(len(item["natal_relations"]) == 8 for item in payload["dayun_interactions"] + payload["liunian_interactions"]))
        self.assertTrue({"auspiciousness", "event_prediction", "fortune_judgement"}.isdisjoint(payload))

    def test_combined_windows_reference_existing_periods(self) -> None:
        result = evaluate_luck_cycle_role_interactions(*fixture())
        dayun_ids = {item.period_id for item in result.dayun_interactions}
        liunian_ids = {item.period_id for item in result.liunian_interactions}
        self.assertTrue(all(item.dayun_period_id in dayun_ids for item in result.combined_windows))
        self.assertTrue(all(item.liunian_period_id in liunian_ids for item in result.combined_windows))
        self.assertEqual(
            len(result.dayun_interactions) + len(result.liunian_interactions) + len(result.combined_windows),
            sum(result.state_counts.values()),
        )

    def test_evidence_converts_to_phase8_records(self) -> None:
        records = interaction_result_to_phase8_evidence(evaluate_luck_cycle_role_interactions(*fixture()))
        self.assertTrue(records)
        self.assertTrue(all(isinstance(item, Phase8EvidenceRecord) for item in records))
        self.assertTrue(all(item.canonical_digest.startswith("sha256:") for item in records))

    def test_blocked_inputs_and_predictions_are_not_guessed(self) -> None:
        graph, xiji = fixture()
        with self.assertRaisesRegex(Phase13InputError, "Fact Graph is required"):
            evaluate_luck_cycle_role_interactions({}, xiji)
        with self.assertRaisesRegex(Phase13InputError, "XiJi Result is required"):
            evaluate_luck_cycle_role_interactions(graph, {})
        with self.assertRaisesRegex(Phase13InputError, "canonical_hash mismatch"):
            evaluate_luck_cycle_role_interactions({**graph, "canonical_hash": "sha256:bad"}, xiji)
        tampered = json.loads(json.dumps(xiji, ensure_ascii=False))
        tampered["element_assignments"][0]["role"] = "unresolved"
        tampered_body = {key: value for key, value in tampered.items() if key not in METADATA_FIELDS}
        tampered["canonical_hash"] = phase12_record_digest("BaziXiJiEvaluationResult", tampered_body)
        with self.assertRaisesRegex(Phase13InputError, "assignment canonical_digest mismatch"):
            evaluate_luck_cycle_role_interactions(graph, tampered)
        with self.assertRaisesRegex(Phase13InputError, "cannot return"):
            evaluate_luck_cycle_role_interactions(graph, xiji, requested_outputs=("event_prediction",))


class Phase13CliTests(unittest.TestCase):
    def test_cli_surface_outputs_json(self) -> None:
        graph, xiji = fixture()
        env = {key: value for key, value in os.environ.items() if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}}
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory() as directory:
            graph_path = Path(directory) / "graph.json"
            xiji_path = Path(directory) / "xiji.json"
            graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
            xiji_path.write_text(json.dumps(xiji, ensure_ascii=False), encoding="utf-8")
            commands = (
                ("evaluate", "--graph", str(graph_path), "--xiji", str(xiji_path)),
                ("validate",),
                ("profiles",),
                ("schemas",),
                ("provenance", "--expected-root", str(ROOT)),
            )
            for command in commands:
                completed = subprocess.run(
                    [sys.executable, "-m", "mingli.phase13_cli", *command],
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
