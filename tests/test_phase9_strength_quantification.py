from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv

from mingli.bazi import DeterministicBaziEngine
from mingli.derived.static_engine import BRANCHES, STEMS
from mingli.phase7 import build_bazi_fact_graph
from mingli.phase8_contracts import EvidenceRecord as Phase8EvidenceRecord
from mingli.phase9 import (
    PHASE9_DECISION_ID,
    benchmark_phase9,
    build_strength_fixture_fact_graph,
    calculate_day_master_strength,
    load_phase9_strength_profiles,
    phase9_schema_summary,
    strength_result_to_phase8_evidence,
    validate_import_origin,
    validate_phase9_profiles,
)
from mingli.phase9_contracts import PHASE9_METHOD_ID, PHASE9_SCHEMA_VERSION, Phase9InputError

ROOT = Path(__file__).resolve().parents[1]


def subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def fixture_graph(day_stem: str | None = None, month_branch: str | None = None) -> dict[str, object]:
    return build_strength_fixture_fact_graph(
        year=(STEMS[0], BRANCHES[0]),
        month=(STEMS[2], month_branch or BRANCHES[2]),
        day=(day_stem or STEMS[0], BRANCHES[4]),
        hour=(STEMS[6], BRANCHES[8]),
    )


class Phase9ProfileAndBenchmarkTests(unittest.TestCase):
    def test_profiles_validate_and_benchmark_matrix_passes(self) -> None:
        manifest = load_phase9_strength_profiles()
        self.assertEqual("PHASE_9_BAZI_STRENGTH_QUANTIFICATION_R1_APPROVED", manifest["decision_id"])
        self.assertEqual((), validate_phase9_profiles())

        result = benchmark_phase9()
        payload = result.to_dict()
        self.assertGreaterEqual(payload["assertions_total"], 300)
        self.assertEqual(payload["assertions_total"], payload["passed"])
        self.assertEqual(0, payload["failed"])
        self.assertEqual(0, payload["unresolved"])
        self.assertEqual(0, payload["schema_failures"])
        self.assertEqual(0, payload["provenance_failures"])
        self.assertEqual(0, payload["hash_mismatches"])
        self.assertEqual(0, payload["threshold_gaps"])
        self.assertEqual(0, payload["threshold_overlaps"])


class Phase9CalculationTests(unittest.TestCase):
    def test_calculates_strength_from_phase7_fact_graph_without_prediction_claims(self) -> None:
        base = DeterministicBaziEngine().calculate(
            {
                "birth_date": "2000-01-07",
                "birth_time": "12:00",
                "timezone": "+08:00",
                "gender": "male",
                "calendar": "solar",
                "longitude": 121.4737,
                "latitude": 31.2304,
                "true_solar_time": False,
            }
        )
        graph = build_bazi_fact_graph(base, dayun_count=4, liunian_start_year=2006, liunian_end_year=2009).to_dict()
        result = calculate_day_master_strength(graph)
        payload = result.to_dict()

        self.assertEqual(PHASE9_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(PHASE9_METHOD_ID, payload["method_id"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertIn(payload["classification"], {"very_weak", "weak", "balanced", "strong", "very_strong"})
        self.assertTrue(payload["canonical_hash"].startswith("sha256:"))
        self.assertEqual({"wood", "fire", "earth", "metal", "water"}, set(payload["element_scores"]))
        self.assertTrue(payload["supporting_evidence"] or payload["contradicting_evidence"])
        self.assertTrue(any("not_evaluated" in str(payload["prediction_validity"]) for _ in [None]))
        forbidden = json.dumps(payload, ensure_ascii=False).lower()
        for token in ("yongshen", "xiji", "geju", "auspicious", "event window", "renderer"):
            self.assertNotIn(token, forbidden)

    def test_evidence_converts_to_phase8_records(self) -> None:
        result = calculate_day_master_strength(fixture_graph())
        records = strength_result_to_phase8_evidence(result)
        self.assertTrue(records)
        self.assertTrue(all(isinstance(item, Phase8EvidenceRecord) for item in records))
        self.assertTrue(all(item.canonical_digest.startswith("sha256:") for item in records))
        self.assertEqual({"day-master-strength"}, {item.claim_id for item in records})

    def test_deterministic_under_key_reorder_and_matrix_covers_elements(self) -> None:
        hashes: set[str] = set()
        classes: set[str] = set()
        for day_stem in STEMS:
            for month_branch in BRANCHES:
                graph = fixture_graph(day_stem, month_branch)
                result = calculate_day_master_strength(graph)
                reordered = calculate_day_master_strength(json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True)))
                self.assertEqual(result.canonical_hash, reordered.canonical_hash)
                hashes.add(result.canonical_hash)
                classes.add(result.classification)
        self.assertGreater(len(hashes), 20)
        self.assertLessEqual(classes, {"very_weak", "weak", "balanced", "strong", "very_strong"})

    def test_blocked_inputs_are_rejected_not_guessed(self) -> None:
        graph = fixture_graph()
        with self.assertRaisesRegex(Phase9InputError, "prediction_validity"):
            calculate_day_master_strength({**graph, "prediction_validity": "evaluated"})
        with self.assertRaisesRegex(Phase9InputError, "missing four pillars"):
            calculate_day_master_strength({**graph, "nodes": [node for node in graph["nodes"] if node.get("node_type") != "Pillar"]})  # type: ignore[index]
        with self.assertRaisesRegex(Phase9InputError, "hidden-stem"):
            calculate_day_master_strength({**graph, "edges": []})
        with self.assertRaisesRegex(Phase9InputError, "unsupported strength profile"):
            calculate_day_master_strength(graph, profile_id="unsupported-school@0.1")


class Phase9CliAndProvenanceTests(unittest.TestCase):
    def test_cli_calculate_validate_benchmark_profiles_schemas_and_provenance(self) -> None:
        graph = fixture_graph()
        with tempfile.TemporaryDirectory() as directory:
            graph_path = Path(directory) / "graph.json"
            graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
            commands = (
                ("calculate", "--graph", str(graph_path)),
                ("validate",),
                ("benchmark",),
                ("profiles",),
                ("schemas",),
                ("provenance", "--expected-root", str(ROOT)),
            )
            for command in commands:
                with self.subTest(command=command):
                    completed = subprocess.run(
                        [sys.executable, "-m", "mingli.phase9_cli", *command],
                        cwd=ROOT,
                        env=subprocess_env(),
                        check=True,
                        capture_output=True,
                        encoding="utf-8",
                        text=True,
                    )
                    payload = json.loads(completed.stdout)
                    self.assertTrue(payload)
                    if command[0] == "provenance":
                        self.assertTrue(payload["valid"])
                    if command[0] == "benchmark":
                        self.assertEqual(payload["assertions_total"], payload["passed"])

    def test_import_origin_and_subprocess_cwd_are_stable(self) -> None:
        origin = validate_import_origin(ROOT)
        self.assertTrue(origin.valid)
        self.assertTrue(Path(origin.mingli_file).resolve().is_relative_to(ROOT.resolve()))
        code = (
            "from mingli.phase9 import benchmark_phase9, phase9_schema_summary; "
            "r=benchmark_phase9(); print('|'.join([phase9_schema_summary()['decision_id'], str(r.passed), str(r.failed)]))"
        )
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, "-c", code],
                cwd=directory,
                env=subprocess_env(),
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
        decision_id, passed, failed = completed.stdout.strip().split("|")
        self.assertEqual(PHASE9_DECISION_ID, decision_id)
        self.assertGreaterEqual(int(passed), 300)
        self.assertEqual("0", failed)


class Phase9WheelTests(unittest.TestCase):
    def test_fresh_venv_import_origin_installed_benchmark_and_calculate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean_env = {
                key: value
                for key, value in os.environ.items()
                if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}
            }
            clean_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
            clean_env["PYTHONIOENCODING"] = "utf-8"
            clean_env["PYTHONUTF8"] = "1"
            temp_path = Path(temp).resolve()
            build_root = temp_path / "source"
            shutil.copytree(
                ROOT,
                build_root,
                ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "build", "dist", "*.egg-info"),
            )
            output = temp_path / "dist"
            subprocess.run(
                [sys.executable, "-m", "build", "--wheel", "--outdir", str(output)],
                cwd=build_root,
                env=clean_env,
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
            wheel = next(output.glob("*.whl"))
            environment = temp_path / "installed"
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            subprocess.run(
                [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
                env=clean_env,
            )
            code = (
                "from mingli.phase9 import benchmark_phase9, build_strength_fixture_fact_graph, calculate_day_master_strength, phase9_schema_summary, validate_import_origin; "
                "from mingli.derived.static_engine import STEMS, BRANCHES; "
                "origin=validate_import_origin(); r=benchmark_phase9(); "
                "g=build_strength_fixture_fact_graph(year=(STEMS[0],BRANCHES[0]), month=(STEMS[2],BRANCHES[2]), day=(STEMS[0],BRANCHES[4]), hour=(STEMS[6],BRANCHES[8])); "
                "s=calculate_day_master_strength(g); "
                "print('|'.join([origin.origin_class, str(origin.valid), phase9_schema_summary()['decision_id'], str(r.passed), str(r.failed), s.prediction_validity, s.canonical_hash]))"
            )
            probe = subprocess.run(
                [str(python), "-I", "-c", code],
                cwd=temp_path,
                env=clean_env,
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
            fields = probe.stdout.strip().split("|")
            self.assertEqual("isolated_venv", fields[0])
            self.assertEqual("True", fields[1])
            self.assertEqual(PHASE9_DECISION_ID, fields[2])
            self.assertGreaterEqual(int(fields[3]), 300)
            self.assertEqual("0", fields[4])
            self.assertEqual("not_evaluated", fields[5])
            self.assertTrue(fields[6].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

