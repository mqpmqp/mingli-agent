from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path

from mingli.test_gates import build_pytest_command, classify_test, run_gate


ROOT = Path(__file__).resolve().parents[1]


class TestGateClassificationTests(unittest.TestCase):
    def test_real_case_files_take_precedence_over_benchmark_name(self):
        nodeid = "tests/test_phase22_case_benchmark.py::Phase22Tests::test_benchmark"
        self.assertEqual("real_case", classify_test(nodeid))

    def test_benchmark_and_assertion_matrix_tests_are_isolated(self):
        self.assertEqual(
            "benchmark",
            classify_test(
                "tests/test_bazi_engine.py::IndependentBenchmarkTests::test_strict_contract_and_independent_results"
            ),
        )
        self.assertEqual(
            "benchmark",
            classify_test(
                "tests/test_phase10_pattern_evaluation.py::Phase10EvaluationTests::test_profile_and_large_assertion_matrix_pass"
            ),
        )

    def test_regular_unit_tests_are_fast(self):
        self.assertEqual(
            "fast",
            classify_test(
                "tests/test_runtime.py::SchemaLoaderTests::test_rejects_non_object_schema"
            ),
        )


class TestGateRunnerTests(unittest.TestCase):
    def test_command_contains_one_gate_marker_and_optional_junit_path(self):
        command = build_pytest_command(
            "fast",
            junit_xml="D:/artifacts/test-fast.xml",
            extra_args=("-q",),
        )
        self.assertEqual("-m", command[3])
        self.assertEqual("fast", command[4])
        self.assertIn("--junitxml=D:/artifacts/test-fast.xml", command)
        self.assertEqual("-q", command[-1])

    @patch("mingli.test_gates.subprocess.run")
    def test_timeout_returns_distinct_exit_code(self, run):
        run.side_effect = subprocess.TimeoutExpired(["python", "-m", "pytest"], 30)
        self.assertEqual(124, run_gate("benchmark", timeout_seconds=30))

    def test_unknown_gate_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown test gate"):
            build_pytest_command("everything")


class TestGateWorkflowTests(unittest.TestCase):
    def test_ci_has_independent_timed_jobs_and_junit_artifacts(self):
        workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(
            encoding="utf-8"
        )
        for job, command in (
            ("fast_tests", "test-fast"),
            ("benchmark_tests", "test-benchmark"),
            ("real_case_tests", "test-real-case"),
        ):
            self.assertIn(f"  {job}:", workflow)
            self.assertIn(command, workflow)
        self.assertGreaterEqual(workflow.count("timeout-minutes:"), 3)
        self.assertGreaterEqual(workflow.count("actions/upload-artifact@v4"), 3)


if __name__ == "__main__":
    unittest.main()
