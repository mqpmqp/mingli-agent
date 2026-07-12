from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path

from mingli.bazi import DeterministicBaziEngine
from mingli.phase7 import build_bazi_fact_graph
from mingli.phase8 import (
    PHASE8_DECISION_ID,
    PHASE8_SCHEMA_VERSION,
    benchmark_phase8,
    evaluate_rule_set,
    load_phase8_rules,
    parse_rule_set,
    phase8_schema_summary,
    validate_import_origin,
    validate_phase8_rules,
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


def base_input() -> dict[str, object]:
    return {
        "birth_date": "2000-01-07",
        "birth_time": "12:00",
        "timezone": "Asia/Shanghai",
        "gender": "male",
        "calendar": "solar",
        "longitude": 121.4737,
        "latitude": 31.2304,
        "true_solar_time": False,
    }


def fact_condition(condition_id: str = "pillars", *, node_type: str = "Pillar", quantifier: str = "any", threshold: int = 1) -> dict[str, object]:
    return {
        "condition_id": condition_id,
        "source": "fact_graph",
        "collection": "nodes",
        "where": {"node_type": node_type},
        "quantifier": quantifier,
        "threshold": threshold,
    }


def rule(
    rule_id: str,
    *,
    claim_id: str = "claim",
    claim_text: str = "A structural contract claim.",
    direction: str = "support",
    priority: int = 50,
    status: str = "reviewed",
    required_conditions: list[dict[str, object]] | None = None,
    blocking_conditions: list[dict[str, object]] | None = None,
    override_codes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "version": "0.1",
        "domain": "contract",
        "claim_id": claim_id,
        "claim_text": claim_text,
        "direction": direction,
        "weight": 6,
        "priority": priority,
        "status": status,
        "required_conditions": required_conditions or [fact_condition()],
        "blocking_conditions": blocking_conditions or [],
        "evidence_detail": f"Evidence emitted by {rule_id}.",
        "plain_language": "Contract-only evidence; no prediction is generated.",
        "reality_override_codes": override_codes or [],
        "source_ids": [f"source:{rule_id}"],
    }


def phase7_graph() -> dict[str, object]:
    base = DeterministicBaziEngine().calculate(base_input())
    return build_bazi_fact_graph(base, dayun_count=4, liunian_start_year=2006, liunian_end_year=2009).to_dict()


class Phase8BenchmarkTests(unittest.TestCase):
    def test_phase8_benchmark_contract(self) -> None:
        result = benchmark_phase8()
        self.assertEqual(35, result.assertions_total)
        self.assertEqual(35, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)
        self.assertEqual((), result.failures)
        self.assertEqual(PHASE8_DECISION_ID, phase8_schema_summary()["decision_id"])


class Phase8EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = phase7_graph()

    def test_consumes_phase7_graph_and_is_deterministic(self) -> None:
        rules = parse_rule_set(
            [
                rule(
                    "four-pillars",
                    required_conditions=[fact_condition(quantifier="count_at_least", threshold=4)],
                )
            ]
        )
        first = evaluate_rule_set(self.graph, rules)
        reordered_graph = json.loads(json.dumps(self.graph, ensure_ascii=False, sort_keys=True))
        second = evaluate_rule_set(reordered_graph, tuple(reversed(rules)))
        payload = first.to_dict()

        self.assertEqual("matched", payload["rule_matches"][0]["status"])
        self.assertEqual("support", payload["claim_resolutions"][0]["final_direction"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertEqual(PHASE8_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(first.canonical_hash, second.canonical_hash)
        self.assertEqual(first.rule_set_hash, second.rule_set_hash)

    def test_verified_reality_is_a_claim_scoped_hard_override(self) -> None:
        rules = parse_rule_set(
            [
                rule(
                    "promotion-rule",
                    claim_id="promotion",
                    claim_text="The current career condition should be described as promotion.",
                    priority=80,
                    status="verified",
                    override_codes=["unemployed"],
                ),
                rule(
                    "unrelated-rule",
                    claim_id="unrelated",
                    claim_text="An unrelated structural claim.",
                    priority=70,
                ),
            ]
        )
        result = evaluate_rule_set(
            self.graph,
            rules,
            intent="career",
            reality={"career_status": "unemployed"},
        ).to_dict()
        resolutions = {item["claim_id"]: item for item in result["claim_resolutions"]}

        self.assertEqual("contradict", resolutions["promotion"]["final_direction"])
        self.assertEqual("resolved_by_reality_override", resolutions["promotion"]["resolution_status"])
        self.assertEqual(0, resolutions["promotion"]["support_score"])
        self.assertEqual("high", resolutions["promotion"]["confidence"]["level"])
        self.assertEqual("support", resolutions["unrelated"]["final_direction"])
        reality_evidence = [item for item in result["evidence_records"] if item["source_type"] == "reality"]
        self.assertEqual(["promotion"], [item["claim_id"] for item in reality_evidence])

    def test_priority_resolution_and_equal_priority_conflict(self) -> None:
        high = rule("high", claim_id="shared", priority=90, direction="support")
        low = rule("low", claim_id="shared", priority=40, direction="contradict")
        resolved = evaluate_rule_set(self.graph, parse_rule_set([low, high])).to_dict()["claim_resolutions"][0]
        self.assertEqual("resolved_by_priority", resolved["resolution_status"])
        self.assertEqual("support", resolved["final_direction"])
        self.assertEqual("medium", resolved["confidence"]["level"])

        low["priority"] = 90
        unresolved = evaluate_rule_set(self.graph, parse_rule_set([low, high])).to_dict()
        claim = unresolved["claim_resolutions"][0]
        self.assertEqual("unresolved_conflict", claim["resolution_status"])
        self.assertEqual("unresolved", claim["final_direction"])
        self.assertEqual("low", claim["confidence"]["level"])
        self.assertEqual(1, len(unresolved["unresolved"]))

    def test_blocking_conditions_and_non_executable_statuses_emit_no_evidence(self) -> None:
        blocking = {
            "condition_id": "blocked_by_status",
            "source": "reality",
            "path": "career_status",
            "operator": "equals",
            "value": "unemployed",
        }
        rules = parse_rule_set(
            [
                rule("blocked", blocking_conditions=[blocking]),
                rule("draft", claim_id="draft", status="draft"),
                rule("missing", claim_id="missing", required_conditions=[fact_condition(node_type="Missing")]),
            ]
        )
        payload = evaluate_rule_set(self.graph, rules, reality={"career_status": "unemployed"}).to_dict()
        statuses = {item["rule_id"]: item["status"] for item in payload["rule_matches"]}

        self.assertEqual({"blocked": "blocked", "draft": "skipped", "missing": "not_matched"}, statuses)
        self.assertEqual([], payload["evidence_records"])
        self.assertEqual([], payload["claim_resolutions"])

    def test_rule_validation_is_strict(self) -> None:
        duplicate = [rule("same"), rule("same", claim_id="other")]
        self.assertIn("duplicate rule_id: same", validate_phase8_rules(duplicate))
        with self.assertRaisesRegex(ValueError, "rule.weight"):
            parse_rule_set([{**rule("bad-weight"), "weight": 11}])
        with self.assertRaisesRegex(ValueError, "condition.collection"):
            parse_rule_set(
                [
                    rule(
                        "bad-collection",
                        required_conditions=[
                            {
                                "condition_id": "bad",
                                "source": "fact_graph",
                                "collection": "unknown",
                                "where": {},
                            }
                        ],
                    )
                ]
            )
        with self.assertRaisesRegex(ValueError, "prediction_validity"):
            evaluate_rule_set({**self.graph, "prediction_validity": "evaluated"}, parse_rule_set([rule("boundary")]))


class Phase8IoAndCliTests(unittest.TestCase):
    def test_jsonl_loader_and_import_origin_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.jsonl"
            path.write_text(json.dumps(rule("loaded"), ensure_ascii=False) + "\n", encoding="utf-8")
            loaded = load_phase8_rules(path)
        self.assertEqual(["loaded"], [item.rule_id for item in loaded])

        origin = validate_import_origin(ROOT)
        self.assertTrue(origin.valid)
        self.assertEqual("checkout", origin.origin_class)
        self.assertTrue(Path(origin.mingli_file).resolve().is_relative_to(ROOT.resolve()))

    def test_phase8_cli_evaluate_validate_benchmark_schemas_and_provenance(self) -> None:
        graph = phase7_graph()
        rules = {"rule_set_id": "test", "version": "0.1", "rules": [rule("cli-rule")]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph_path = root / "graph.json"
            rules_path = root / "rules.json"
            reality_path = root / "reality.json"
            graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
            rules_path.write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
            reality_path.write_text(json.dumps({"career_status": "employed"}), encoding="utf-8")
            commands = (
                ("evaluate", "--graph", str(graph_path), "--rules", str(rules_path), "--reality", str(reality_path), "--intent", "career"),
                ("validate", "--rules", str(rules_path)),
                ("benchmark",),
                ("schemas",),
                ("provenance", "--expected-root", str(ROOT)),
            )
            for command in commands:
                with self.subTest(command=command):
                    completed = subprocess.run(
                        [sys.executable, "-m", "mingli.phase8_cli", *command],
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


class Phase8WheelTests(unittest.TestCase):
    def test_fresh_venv_import_origin_and_installed_phase8_benchmark(self) -> None:
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
                "import mingli; "
                "from mingli.phase8 import benchmark_phase8, phase8_schema_summary, validate_import_origin; "
                "origin=validate_import_origin(); result=benchmark_phase8(); "
                "print('|'.join([mingli.__file__, origin.origin_class, str(origin.valid), str(result.passed), phase8_schema_summary()['decision_id']]))"
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
            self.assertEqual("isolated_venv", fields[1])
            self.assertEqual("True", fields[2])
            self.assertEqual("35", fields[3])
            self.assertEqual(PHASE8_DECISION_ID, fields[4])
            self.assertTrue(Path(fields[0]).resolve().is_relative_to(environment.resolve()))


if __name__ == "__main__":
    unittest.main()
