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
from mingli.phase12 import (
    PHASE12_METHOD_ID,
    PHASE12_SCHEMA_VERSION,
    Phase12InputError,
    benchmark_phase12,
    build_xiji_fixture,
    evaluate_bazi_xiji_roles,
    load_phase12_xiji_profiles,
    validate_phase12_profiles,
    xiji_result_to_phase8_evidence,
)
from mingli.phase12_contracts import XIJI_ROLES
from mingli.phase9_contracts import ELEMENTS

ROOT = Path(__file__).resolve().parents[1]


def fixture(day_stem: str = STEMS[0], month_branch: str = BRANCHES[2]):
    return build_xiji_fixture(day_stem, month_branch)


class Phase12EvaluationTests(unittest.TestCase):
    def test_profile_and_large_assertion_matrix_pass(self) -> None:
        self.assertTrue(load_phase12_xiji_profiles()["profiles"])
        self.assertEqual((), validate_phase12_profiles())
        result = benchmark_phase12()
        self.assertGreaterEqual(result.assertions_total, 2800)
        self.assertEqual(result.assertions_total, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)
        self.assertEqual(0, result.schema_failures)
        self.assertEqual(0, result.provenance_failures)
        self.assertEqual(0, result.hash_mismatches)
        self.assertEqual(0, result.role_partition_failures)
        self.assertEqual(0, result.role_collision_failures)
        self.assertEqual(0, result.carrier_failures)
        self.assertEqual(0, result.prediction_boundary_failures)

    def test_evaluation_is_deterministic_and_partitioned(self) -> None:
        regulation = fixture()
        result = evaluate_bazi_xiji_roles(regulation)
        reordered = evaluate_bazi_xiji_roles(json.loads(json.dumps(regulation, ensure_ascii=False, sort_keys=True)))
        payload = result.to_dict()
        self.assertEqual(result.canonical_hash, reordered.canonical_hash)
        self.assertEqual(PHASE12_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(PHASE12_METHOD_ID, payload["method_id"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertEqual(set(ELEMENTS), {item["element"] for item in payload["element_assignments"]})
        self.assertTrue(all(item["role"] in XIJI_ROLES for item in payload["element_assignments"]))
        buckets = [
            set(payload["yongshen_elements"]), set(payload["xishen_elements"]), set(payload["jishen_elements"]),
            set(payload["choushen_elements"]), set(payload["xianshen_elements"]), set(payload["unresolved_elements"]),
        ]
        self.assertEqual(set(ELEMENTS), set().union(*buckets))
        self.assertEqual(5, sum(len(value) for value in buckets))
        self.assertLessEqual(len(payload["yongshen_elements"]), 1)

    def test_stem_carriers_preserve_identity(self) -> None:
        result = evaluate_bazi_xiji_roles(fixture())
        self.assertEqual(set(STEMS), {item.stem for item in result.stem_carriers})
        self.assertTrue(all(item.inheritance_rule == "inherits_element_role" for item in result.stem_carriers))
        self.assertTrue(all(item.yin_yang_differentiation_status == "not_evaluated" for item in result.stem_carriers))

    def test_evidence_converts_to_phase8_records(self) -> None:
        records = xiji_result_to_phase8_evidence(evaluate_bazi_xiji_roles(fixture()))
        self.assertTrue(records)
        self.assertTrue(all(isinstance(item, Phase8EvidenceRecord) for item in records))
        self.assertTrue(all(item.canonical_digest.startswith("sha256:") for item in records))

    def test_blocked_inputs_and_predictions_are_not_guessed(self) -> None:
        regulation = fixture()
        with self.assertRaisesRegex(Phase12InputError, "required"):
            evaluate_bazi_xiji_roles({})
        with self.assertRaisesRegex(Phase12InputError, "canonical_hash mismatch"):
            evaluate_bazi_xiji_roles({**regulation, "canonical_hash": "sha256:bad"})
        tampered = json.loads(json.dumps(regulation, ensure_ascii=False))
        tampered["candidates"][0]["combined_score"] = "99.9999"
        with self.assertRaisesRegex(Phase12InputError, "candidate canonical_digest mismatch"):
            evaluate_bazi_xiji_roles(tampered)
        with self.assertRaisesRegex(Phase12InputError, "cannot return"):
            evaluate_bazi_xiji_roles(regulation, requested_outputs=("event_prediction",))


class Phase12CliTests(unittest.TestCase):
    def test_cli_surface_outputs_json(self) -> None:
        regulation = fixture()
        env = {key: value for key, value in os.environ.items() if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}}
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory() as directory:
            regulation_path = Path(directory) / "regulation.json"
            regulation_path.write_text(json.dumps(regulation, ensure_ascii=False), encoding="utf-8")
            commands = (
                ("evaluate", "--regulation", str(regulation_path)), ("validate",), ("benchmark",),
                ("profiles",), ("schemas",), ("provenance", "--expected-root", str(ROOT)),
            )
            for command in commands:
                completed = subprocess.run(
                    [sys.executable, "-m", "mingli.phase12_cli", *command], cwd=ROOT, env=env,
                    check=True, capture_output=True, text=True, encoding="utf-8",
                )
                self.assertTrue(json.loads(completed.stdout))


if __name__ == "__main__":
    unittest.main()
