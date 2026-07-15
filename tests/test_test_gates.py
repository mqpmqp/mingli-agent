from __future__ import annotations

import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from mingli.test_gates import (
    _entrypoint,
    benchmark_main,
    build_pytest_command,
    classify_test,
    fast_main,
    main,
    real_case_main,
    run_gate,
)


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

    @patch("mingli.test_gates.subprocess.run")
    def test_timeout_writes_failure_junit_artifact(self, run):
        run.side_effect = subprocess.TimeoutExpired(["python", "-m", "pytest"], 30)
        with tempfile.TemporaryDirectory() as directory:
            junit = Path(directory) / "benchmark.xml"
            self.assertEqual(
                124,
                run_gate(
                    "benchmark",
                    timeout_seconds=30,
                    junit_xml=str(junit),
                ),
            )
            report = junit.read_text(encoding="utf-8")
        self.assertIn('errors="1"', report)
        self.assertIn("timed out after 30 seconds", report)

    @patch("mingli.test_gates.subprocess.run")
    def test_success_returns_pytest_exit_code_and_creates_junit_directory(self, run):
        run.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as directory:
            junit = Path(directory) / "nested" / "fast.xml"
            self.assertEqual(
                0,
                run_gate(
                    "fast",
                    timeout_seconds=12,
                    junit_xml=str(junit),
                    extra_args=("-q",),
                ),
            )
            self.assertTrue(junit.parent.is_dir())
        command = run.call_args.args[0]
        self.assertIn("--junitxml=", " ".join(command))
        self.assertEqual(12, run.call_args.kwargs["timeout"])

    def test_non_positive_timeout_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "must be positive"):
            run_gate("fast", timeout_seconds=-1)

    @patch("mingli.test_gates.run_gate", return_value=0)
    def test_entrypoint_and_module_main_forward_options(self, run):
        self.assertEqual(
            0,
            _entrypoint(
                "fast",
                ["--timeout-seconds", "12", "--junitxml", "fast.xml", "--", "-q"],
            ),
        )
        self.assertEqual(
            0,
            main(
                [
                    "--timeout-seconds",
                    "34",
                    "--junitxml",
                    "real.xml",
                    "real_case",
                    "--",
                    "-x",
                ]
            ),
        )
        first, second = run.call_args_list
        self.assertEqual(("fast",), first.args)
        self.assertEqual(("-q",), first.kwargs["extra_args"])
        self.assertEqual(("real_case",), second.args)
        self.assertEqual(("-x",), second.kwargs["extra_args"])

    @patch("mingli.test_gates._entrypoint", return_value=0)
    def test_console_entrypoints_select_exact_gate(self, entrypoint):
        self.assertEqual(0, fast_main())
        self.assertEqual(0, benchmark_main())
        self.assertEqual(0, real_case_main())
        self.assertEqual(
            [("fast",), ("benchmark",), ("real_case",)],
            [call.args for call in entrypoint.call_args_list],
        )

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
