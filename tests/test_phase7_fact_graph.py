from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from decimal import Decimal
from pathlib import Path

from mingli.bazi import DeterministicBaziEngine
from mingli.contracts import digest
from mingli.derived import derive_static_chart
from mingli.phase7 import (
    build_bazi_fact_graph,
    build_luck_timeline,
    calculate_growth_stages,
    detect_structural_relations,
    load_phase7_profiles,
    phase7_schema_summary,
    benchmark_phase7,
    validate_phase7_profiles,
)


ROOT = Path(__file__).resolve().parents[1]


def subprocess_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}
    }
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def base_input(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "birth_date": "2000-01-07",
        "birth_time": "12:00",
        "timezone": "Asia/Shanghai",
        "gender": "male",
        "calendar": "solar",
        "longitude": 121.4737,
        "latitude": 31.2304,
        "true_solar_time": False,
    }
    value.update(overrides)
    return value


class Phase7BenchmarkTests(unittest.TestCase):
    def test_profiles_and_assertion_matrix_are_complete(self) -> None:
        self.assertEqual((), validate_phase7_profiles())
        manifest = load_phase7_profiles()
        self.assertEqual("PHASE_7_FACT_GRAPH_R1_DETERMINISTIC_BOUNDARY_APPROVED", manifest["decision_id"])

        result = benchmark_phase7()

        self.assertEqual(736, result.assertions_total)
        self.assertEqual(736, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)
        self.assertEqual(0, result.schema_failures)
        self.assertEqual(0, result.provenance_failures)
        self.assertEqual(0, result.hash_mismatches)
        self.assertEqual(0, result.interval_gaps)
        self.assertEqual(0, result.interval_overlaps)
        self.assertEqual(120, result.growth_assertions)
        self.assertEqual(136, result.timeline_assertions)
        self.assertEqual(100, result.stem_relation_assertions)
        self.assertEqual(364, result.branch_relation_assertions)


class Phase7FactGraphTests(unittest.TestCase):
    def test_timeline_uses_exact_anchor_and_contiguous_intervals(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        timeline = build_luck_timeline(base, dayun_count=6, liunian_start_year=2006, liunian_end_year=2011)

        self.assertEqual(0, timeline.interval_gaps)
        self.assertEqual(0, timeline.interval_overlaps)
        self.assertEqual("integer microseconds from UTC instants; no binary float public result", timeline.luck_anchor.calculation_precision)
        self.assertIsInstance(timeline.luck_anchor.duration.source_microseconds, int)
        self.assertEqual(
            Decimal(str(base["luck"]["start_age_years"])).quantize(Decimal("0.000001")),
            Decimal(timeline.luck_anchor.duration.display_start_age_years),
        )
        for left, right in zip(timeline.dayun_periods, timeline.dayun_periods[1:]):
            self.assertEqual(left.end_instant_utc, right.start_instant_utc)
        self.assertTrue(all(period.dayun_period_id for period in timeline.liunian_periods))

    def test_growth_and_relations_are_structural_only(self) -> None:
        growth = calculate_growth_stages()
        self.assertEqual(120, len(growth))
        self.assertTrue({fact.stage_code for fact in growth})

        base = DeterministicBaziEngine().calculate(base_input())
        derived = derive_static_chart(base).to_dict()
        relations = detect_structural_relations(derived)

        self.assertTrue(relations)
        for relation in relations:
            self.assertIn("transformation_not_evaluated", relation.status)
            self.assertIn("strength_not_evaluated", relation.status)
            self.assertIn("auspiciousness_not_evaluated", relation.status)

    def test_fact_graph_is_stable_and_references_existing_nodes(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        graph = build_bazi_fact_graph(base, dayun_count=4, liunian_start_year=2006, liunian_end_year=2009)
        payload = graph.to_dict()

        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertEqual("bazi-deterministic-fact-graph@0.1.0", payload["method_id"])
        node_ids = {node["node_id"] for node in payload["nodes"]}
        node_types = {node["node_type"] for node in payload["nodes"]}
        self.assertTrue(
            {
                "Pillar",
                "Stem",
                "Branch",
                "HiddenStem",
                "TenGod",
                "NaYin",
                "XunKong",
                "LuckAnchor",
                "DaYunPeriod",
                "LiuNianPeriod",
                "AgeSnapshot",
                "GrowthStage",
                "Relation",
            }.issubset(node_types)
        )
        for edge in payload["edges"]:
            self.assertIn(edge["source"], node_ids)
            self.assertIn(edge["target"], node_ids)

        reordered = json.loads(json.dumps(base, ensure_ascii=False, sort_keys=True))
        self.assertEqual(graph.canonical_hash, build_bazi_fact_graph(reordered, dayun_count=4, liunian_start_year=2006, liunian_end_year=2009).canonical_hash)

        code = (
            "import json; "
            "from mingli.phase7 import build_bazi_fact_graph; "
            f"base=json.loads({json.dumps(base, ensure_ascii=False)!r}); "
            "print(build_bazi_fact_graph(base, dayun_count=4, liunian_start_year=2006, liunian_end_year=2009).canonical_hash)"
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
        self.assertEqual(graph.canonical_hash, completed.stdout.strip())
        self.assertEqual(digest(payload), digest(graph.to_dict()))


class Phase7CliTests(unittest.TestCase):
    def test_phase7_cli_build_timeline_relations_and_metadata(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        derived = derive_static_chart(base).to_dict()
        env = subprocess_env()
        with tempfile.TemporaryDirectory() as directory:
            base_path = Path(directory) / "base.json"
            derived_path = Path(directory) / "derived.json"
            base_path.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
            derived_path.write_text(json.dumps(derived, ensure_ascii=False), encoding="utf-8")
            commands = (
                ("phase7", "build", "--input", str(base_path), "--dayun-count", "4", "--liunian-start-year", "2006", "--liunian-end-year", "2009"),
                ("phase7", "timeline", "--input", str(base_path), "--dayun-count", "4", "--liunian-start-year", "2006", "--liunian-end-year", "2009"),
                ("phase7", "relations", "--input", str(derived_path)),
                ("phase7", "validate"),
                ("phase7", "benchmark"),
                ("phase7", "profiles"),
                ("phase7", "schemas"),
            )
            for command in commands:
                with self.subTest(command=command):
                    completed = subprocess.run(
                        [sys.executable, "-m", "mingli.cli", *command],
                        cwd=ROOT,
                        env=env,
                        check=True,
                        capture_output=True,
                        encoding="utf-8",
                        text=True,
                    )
                    self.assertTrue(json.loads(completed.stdout))

    def test_phase7_cli_reports_malformed_json_to_stderr(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "mingli.cli", "phase7", "build"],
            cwd=ROOT,
            env=subprocess_env(),
            input="{not-json",
            capture_output=True,
            encoding="utf-8",
            text=True,
        )

        self.assertNotEqual(0, completed.returncode)
        self.assertEqual("", completed.stdout)
        self.assertTrue(completed.stderr.strip())


class Phase7WheelTests(unittest.TestCase):
    def test_wheel_contains_phase7_resources_and_builds_fact_graph(self) -> None:
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
                "from mingli.bazi import DeterministicBaziEngine; "
                "from mingli.phase7 import benchmark_phase7, build_bazi_fact_graph, load_phase7_profiles, phase7_schema_summary; "
                "base=DeterministicBaziEngine().calculate({'birth_date':'2000-01-07','birth_time':'12:00','timezone':'+08:00','gender':'male','calendar':'solar','longitude':121.4737,'latitude':31.2304,'true_solar_time':False}); "
                "graph=build_bazi_fact_graph(base, dayun_count=4, liunian_start_year=2006, liunian_end_year=2009); "
                "print('|'.join([load_phase7_profiles()['decision_id'], phase7_schema_summary()['schemas']['BaziFactGraphResult'], str(benchmark_phase7().passed), graph.prediction_validity]))"
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
            self.assertEqual(
                "PHASE_7_FACT_GRAPH_R1_DETERMINISTIC_BOUNDARY_APPROVED|bazi-fact-graph-result@0.1|736|not_evaluated",
                probe.stdout.strip(),
            )


if __name__ == "__main__":
    unittest.main()
