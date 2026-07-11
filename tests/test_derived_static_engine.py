from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mingli.bazi import DeterministicBaziEngine
from mingli.contracts import DerivedContractError, digest
from mingli.derived import (
    benchmark_static_mappings,
    derive_static_chart,
    load_packaged_source_manifest,
    load_static_assertions,
    validate_static_assertions,
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


class Phase6AssertionMatrixTests(unittest.TestCase):
    def test_assertion_matrix_is_complete_and_benchmark_passes(self) -> None:
        assertions = load_static_assertions()

        self.assertEqual((), validate_static_assertions(assertions))
        result = benchmark_static_mappings()

        self.assertEqual(352, result.total)
        self.assertEqual(352, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)
        self.assertEqual(0, result.independence_group_violations)
        self.assertEqual(0, result.deterministic_hash_mismatches)
        self.assertEqual(0, result.schema_failures)
        self.assertEqual(0, result.provenance_failures)
        self.assertEqual(
            {
                "hidden_stem_ten_gods": 120,
                "hidden_stems": 12,
                "nayin": 60,
                "visible_stem_ten_gods": 100,
                "xunkong": 60,
            },
            dict(result.capability_counts),
        )

    def test_assertion_matrix_rejects_duplicate_empty_and_same_group_sources(self) -> None:
        assertions = [dict(load_static_assertions()[0])]
        assertions.append(dict(assertions[0]))
        assertions[0]["expected_mapping_result"] = {}
        assertions[1]["assertion_id"] = "duplicate-source"
        assertions[1]["expected_provenance"] = {
            "source_ids": [
                "yuan-hai-zi-ping-wikisource-20260711",
                "yuan-hai-zi-ping-wikisource-20260711",
            ]
        }

        issues = validate_static_assertions(assertions)

        self.assertTrue(any("expected_mapping_result is empty" in issue for issue in issues))
        self.assertTrue(any("independent reviewed groups" in issue for issue in issues))
        self.assertTrue(any("requires at least 272 assertions" in issue for issue in issues))


class Phase6StaticEngineTests(unittest.TestCase):
    def test_real_phase5_output_maps_all_static_capabilities(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        result = derive_static_chart(base)
        payload = result.to_dict()

        self.assertEqual("complete", payload["status"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertEqual(4, len(payload["pillars"]))
        year = payload["pillars"][0]
        self.assertEqual({"position": "year", "stem": "己", "branch": "卯"}, {key: year[key] for key in ("position", "stem", "branch")})
        self.assertEqual("wealth_opposite_polarity", year["stem_ten_god"]["code"])
        self.assertEqual("正财", year["stem_ten_god"]["label"])
        self.assertEqual("乙", year["hidden_stems"][0]["stem"])
        self.assertEqual("peer_opposite_polarity", year["hidden_stems"][0]["ten_god"]["code"])
        self.assertEqual("city_wall_earth", year["nayin"]["code"])
        self.assertEqual({"xun_start": "甲戌", "void_branches": ["申", "酉"]}, {key: year["xunkong"][key] for key in ("xun_start", "void_branches")})

    def test_capability_routing_can_request_single_capability(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        result = derive_static_chart(base, capabilities=("nayin",)).to_dict()

        for pillar in result["pillars"]:
            self.assertIsNone(pillar["stem_ten_god"])
            self.assertEqual([], pillar["hidden_stems"])
            self.assertIsNotNone(pillar["nayin"])
            self.assertIsNone(pillar["xunkong"])

    def test_negative_contract_paths_are_structured(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        with self.assertRaisesRegex(DerivedContractError, "DERIVED_BASE_RESULT_INVALID"):
            derive_static_chart("not an object")  # type: ignore[arg-type]
        with self.assertRaisesRegex(DerivedContractError, "DERIVED_CAPABILITY_NOT_ENABLED"):
            derive_static_chart(base, capabilities=("shensha",))
        with self.assertRaisesRegex(DerivedContractError, "DERIVED_DEPENDENCY_UNRESOLVED"):
            derive_static_chart(base, source_manifest={"sources": []})
        invalid = dict(base, pillars={**base["pillars"], "year": "甲甲"})
        with self.assertRaisesRegex(DerivedContractError, "DERIVED_FIELD_NOT_AVAILABLE"):
            derive_static_chart(invalid)

    def test_strict_rejects_unresolved_base_and_explicit_partial_is_stable(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        ambiguous = dict(
            base,
            ambiguities=[
                {
                    "dependency": "base.pillars.hour",
                    "field_paths": ["pillars.hour"],
                    "source_ids": ["external-conflict"],
                    "message": "23:00 day-boundary conflict",
                }
            ],
        )

        with self.assertRaisesRegex(DerivedContractError, "DERIVED_DEPENDENCY_UNRESOLVED"):
            derive_static_chart(ambiguous)

        partial = derive_static_chart(ambiguous, strict=False).to_dict()
        self.assertEqual("partial", partial["status"])
        self.assertEqual([], partial["pillars"])
        self.assertEqual("base.pillars.hour", partial["ambiguities"][0]["dependency"])
        self.assertEqual("not_evaluated", partial["prediction_validity"])

    def test_determinism_across_key_order_source_order_process_and_cwd(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        first = digest(derive_static_chart(base).to_dict())
        reordered_base = json.loads(json.dumps(base, ensure_ascii=False, sort_keys=True))
        reversed_manifest = load_packaged_source_manifest()
        reversed_manifest["sources"] = list(reversed(reversed_manifest["sources"]))

        self.assertEqual(first, digest(derive_static_chart(base).to_dict()))
        self.assertEqual(first, digest(derive_static_chart(reordered_base).to_dict()))
        self.assertEqual(first, digest(derive_static_chart(base, source_manifest=reversed_manifest).to_dict()))

        code = (
            "import json; "
            "from mingli.contracts import digest; "
            "from mingli.derived import derive_static_chart; "
            f"base=json.loads({json.dumps(base, ensure_ascii=False)!r}); "
            "print(digest(derive_static_chart(base).to_dict()))"
        )
        with tempfile.TemporaryDirectory() as directory:
            probe = subprocess.run(
                [sys.executable, "-c", code],
                cwd=directory,
                env=subprocess_env(),
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
        self.assertEqual(first, probe.stdout.strip())


class Phase6CliTests(unittest.TestCase):
    def test_phase6_cli_map_validate_benchmark_and_metadata(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        env = subprocess_env()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "base.json"
            path.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
            mapped = subprocess.run(
                [sys.executable, "-m", "mingli.cli", "phase6", "map", "--input", str(path)],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
            payload = json.loads(mapped.stdout)
            self.assertEqual("complete", payload["status"])
            self.assertEqual("not_evaluated", payload["prediction_validity"])

        for command in (
            ("phase6", "validate"),
            ("phase6", "benchmark"),
            ("phase6", "capabilities"),
            ("phase6", "schemas"),
        ):
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

    def test_phase6_cli_reports_malformed_json_to_stderr(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "mingli.cli", "phase6", "map"],
            cwd=ROOT,
            env=subprocess_env(),
            input="{not-json",
            capture_output=True,
            encoding="utf-8",
            text=True,
        )

        self.assertNotEqual(0, completed.returncode)
        self.assertEqual("", completed.stdout)
        self.assertIn("错误", completed.stderr)


if __name__ == "__main__":
    unittest.main()
