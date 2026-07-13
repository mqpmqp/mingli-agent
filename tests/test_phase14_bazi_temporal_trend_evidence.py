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
from mingli.phase14 import (
    PHASE14_METHOD_ID,
    PHASE14_SCHEMA_VERSION,
    Phase14InputError,
    benchmark_phase14,
    build_phase14_fixture,
    evaluate_bazi_temporal_trends,
    load_phase14_trend_profiles,
    query_temporal_trends,
    temporal_trend_result_to_phase8_evidence,
    validate_phase14_profiles,
)
from mingli.phase14_contracts import TARGET_TYPES, TRANSITION_TYPES, TREND_LABELS

ROOT = Path(__file__).resolve().parents[1]


def fixture(day_stem: str = STEMS[0], month_branch: str = BRANCHES[2]):
    return build_phase14_fixture(day_stem, month_branch)


class Phase14EvaluationTests(unittest.TestCase):
    def test_profile_and_large_assertion_matrix_pass(self) -> None:
        self.assertTrue(load_phase14_trend_profiles()["profiles"])
        self.assertEqual((), validate_phase14_profiles())
        result = benchmark_phase14()
        self.assertGreaterEqual(result.assertions_total, 4300)
        self.assertEqual(result.assertions_total, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)
        self.assertEqual(0, result.schema_failures)
        self.assertEqual(0, result.provenance_failures)
        self.assertEqual(0, result.hash_mismatches)
        self.assertEqual(0, result.partition_failures)
        self.assertEqual(0, result.query_failures)
        self.assertEqual(0, result.transition_failures)
        self.assertEqual(0, result.reality_override_failures)
        self.assertEqual(0, result.prediction_boundary_failures)

    def test_evaluation_is_deterministic_and_non_predictive(self) -> None:
        graph, interaction = fixture()
        result = evaluate_bazi_temporal_trends(graph, interaction)
        reordered = evaluate_bazi_temporal_trends(
            json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True)),
            json.loads(json.dumps(interaction, ensure_ascii=False, sort_keys=True)),
        )
        payload = result.to_dict()
        self.assertEqual(result.canonical_hash, reordered.canonical_hash)
        self.assertEqual(PHASE14_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(PHASE14_METHOD_ID, payload["method_id"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        trends = payload["dayun_trends"] + payload["liunian_trends"] + payload["combined_trends"]
        self.assertTrue(trends)
        self.assertTrue(all(item["target_type"] in TARGET_TYPES for item in trends))
        self.assertTrue(all(item["trend_label"] in TREND_LABELS for item in trends))
        self.assertTrue(all(item["confidence"] in {"high", "medium", "low"} for item in trends))
        self.assertTrue(all(item["confidence"] != "high" for item in trends))
        self.assertTrue({"auspiciousness", "event_prediction", "fortune_judgement"}.isdisjoint(payload))

    def test_reality_hard_override_and_conflict_retention(self) -> None:
        graph, interaction = fixture()
        baseline = evaluate_bazi_temporal_trends(graph, interaction)
        target = baseline.liunian_trends[0].target_id
        support = {
            "target_id": target,
            "direction": "support",
            "detail": "verified real-world condition",
            "weight": 10,
            "verified": True,
            "source_id": "test-reality-support",
        }
        overridden = evaluate_bazi_temporal_trends(graph, interaction, reality_evidence=(support,))
        item = next(record for record in overridden.liunian_trends if record.target_id == target)
        self.assertEqual("support_tendency", item.trend_label)
        self.assertEqual("high", item.confidence)
        self.assertEqual("support", item.reality_override_direction)
        conflicted = evaluate_bazi_temporal_trends(graph, interaction, reality_evidence=(
            support,
            {
                "target_id": target,
                "direction": "contradict",
                "detail": "verified contradictory condition",
                "weight": 10,
                "verified": True,
                "source_id": "test-reality-conflict",
            },
        ))
        conflict_item = next(record for record in conflicted.liunian_trends if record.target_id == target)
        self.assertEqual("unresolved", conflict_item.trend_label)
        self.assertEqual("low", conflict_item.confidence)
        self.assertGreaterEqual(len(conflict_item.reality_evidence_ids), 2)

    def test_year_age_queries_and_transitions(self) -> None:
        result = evaluate_bazi_temporal_trends(*fixture())
        year = result.liunian_trends[0].label_year
        age = result.liunian_trends[0].start_age
        self.assertIsNotNone(year)
        self.assertIsNotNone(age)
        self.assertTrue(query_temporal_trends(result, year=year))
        self.assertTrue(query_temporal_trends(result, age=age))
        self.assertTrue(all(item.transition_type in TRANSITION_TYPES for item in result.transitions))
        with self.assertRaisesRegex(Phase14InputError, "exactly one"):
            query_temporal_trends(result)
        with self.assertRaisesRegex(Phase14InputError, "exactly one"):
            query_temporal_trends(result, year=year, age=age)

    def test_evidence_converts_to_phase8_records(self) -> None:
        records = temporal_trend_result_to_phase8_evidence(evaluate_bazi_temporal_trends(*fixture()))
        self.assertTrue(records)
        self.assertTrue(all(isinstance(item, Phase8EvidenceRecord) for item in records))
        self.assertTrue(all(item.canonical_digest.startswith("sha256:") for item in records))

    def test_blocked_inputs_and_predictions_are_not_guessed(self) -> None:
        graph, interaction = fixture()
        with self.assertRaisesRegex(Phase14InputError, "Fact Graph is required"):
            evaluate_bazi_temporal_trends({}, interaction)
        with self.assertRaisesRegex(Phase14InputError, "Interaction Result is required"):
            evaluate_bazi_temporal_trends(graph, {})
        with self.assertRaisesRegex(Phase14InputError, "canonical_hash mismatch"):
            evaluate_bazi_temporal_trends({**graph, "canonical_hash": "sha256:bad"}, interaction)
        with self.assertRaisesRegex(Phase14InputError, "unknown"):
            evaluate_bazi_temporal_trends(graph, interaction, reality_evidence=({
                "target_id": "unknown-target",
                "direction": "support",
                "detail": "invalid target",
                "weight": 1,
                "verified": True,
                "source_id": "invalid",
            },))
        with self.assertRaisesRegex(Phase14InputError, "cannot return"):
            evaluate_bazi_temporal_trends(graph, interaction, requested_outputs=("event_prediction",))


class Phase14CliTests(unittest.TestCase):
    def test_cli_surface_outputs_json(self) -> None:
        graph, interaction = fixture()
        result = evaluate_bazi_temporal_trends(graph, interaction)
        env = {key: value for key, value in os.environ.items() if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}}
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory() as directory:
            graph_path = Path(directory) / "graph.json"
            interaction_path = Path(directory) / "interaction.json"
            result_path = Path(directory) / "result.json"
            graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
            interaction_path.write_text(json.dumps(interaction, ensure_ascii=False), encoding="utf-8")
            result_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False), encoding="utf-8")
            year = result.liunian_trends[0].label_year
            commands = (
                ("evaluate", "--graph", str(graph_path), "--interaction", str(interaction_path)),
                ("query", "--result", str(result_path), "--year", str(year)),
                ("validate",),
                ("profiles",),
                ("schemas",),
                ("provenance", "--expected-root", str(ROOT)),
            )
            for command in commands:
                completed = subprocess.run(
                    [sys.executable, "-m", "mingli.phase14_cli", *command],
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
