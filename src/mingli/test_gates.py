from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Sequence
from xml.etree import ElementTree


TEST_GATES = ("fast", "benchmark", "real_case")
REAL_CASE_TEST_FILES = frozenset(
    {
        "test_phase22_case_benchmark.py",
        "test_phase24_release_candidate.py",
        "test_real_case_validation_os.py",
        "test_validation_astro_etl.py",
    }
)
_BENCHMARK_TOKENS = ("benchmark", "assertion_matrix", "golden", "wheel_contains")
_DEFAULT_TIMEOUTS = {"fast": 300, "benchmark": 3600, "real_case": 600}


def classify_test(nodeid: str) -> str:
    """Assign every collected test to exactly one release-gate group."""

    normalized = nodeid.replace("\\", "/")
    filename = normalized.split("::", 1)[0].rsplit("/", 1)[-1]
    if filename in REAL_CASE_TEST_FILES:
        return "real_case"
    lowered = normalized.lower()
    if any(token in lowered for token in _BENCHMARK_TOKENS):
        return "benchmark"
    return "fast"


def build_pytest_command(
    gate: str,
    *,
    junit_xml: str | None = None,
    extra_args: Sequence[str] = (),
) -> list[str]:
    if gate not in TEST_GATES:
        raise ValueError(f"unknown test gate: {gate}")
    command = [sys.executable, "-m", "pytest", "-m", gate]
    if junit_xml:
        command.append(f"--junitxml={junit_xml}")
    command.extend(extra_args)
    return command


def _write_timeout_junit(path: str, gate: str, timeout: int) -> None:
    message = f"{gate} test gate timed out after {timeout} seconds"
    root = ElementTree.Element("testsuites", {"name": "pytest tests"})
    suite = ElementTree.SubElement(
        root,
        "testsuite",
        {
            "name": f"{gate} timeout",
            "errors": "1",
            "failures": "0",
            "skipped": "0",
            "tests": "1",
            "time": str(timeout),
        },
    )
    case = ElementTree.SubElement(
        suite,
        "testcase",
        {"classname": "mingli.test_gates", "name": f"test_{gate}_timeout"},
    )
    error = ElementTree.SubElement(
        case,
        "error",
        {"type": "timeout", "message": message},
    )
    error.text = message
    ElementTree.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def run_gate(
    gate: str,
    *,
    timeout_seconds: int | None = None,
    junit_xml: str | None = None,
    extra_args: Sequence[str] = (),
) -> int:
    if gate not in TEST_GATES:
        raise ValueError(f"unknown test gate: {gate}")
    timeout = timeout_seconds or _DEFAULT_TIMEOUTS[gate]
    if timeout <= 0:
        raise ValueError("timeout_seconds must be positive")
    if junit_xml:
        Path(junit_xml).parent.mkdir(parents=True, exist_ok=True)
    command = build_pytest_command(gate, junit_xml=junit_xml, extra_args=extra_args)
    try:
        return subprocess.run(command, check=False, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        if junit_xml:
            _write_timeout_junit(junit_xml, gate, timeout)
        print(f"error: {gate} test gate timed out after {timeout} seconds", file=sys.stderr)
        return 124


def _parser(gate: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"test-{gate.replace('_', '-')}")
    parser.add_argument("--timeout-seconds", type=int, default=_DEFAULT_TIMEOUTS[gate])
    parser.add_argument("--junitxml")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    return parser


def _entrypoint(gate: str, argv: Sequence[str] | None = None) -> int:
    args = _parser(gate).parse_args(argv)
    extra_args = tuple(args.pytest_args)
    if extra_args[:1] == ("--",):
        extra_args = extra_args[1:]
    return run_gate(
        gate,
        timeout_seconds=args.timeout_seconds,
        junit_xml=args.junitxml,
        extra_args=extra_args,
    )


def fast_main() -> int:
    return _entrypoint("fast")


def benchmark_main() -> int:
    return _entrypoint("benchmark")


def real_case_main() -> int:
    return _entrypoint("real_case")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mingli.test_gates")
    parser.add_argument("gate", choices=TEST_GATES)
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--junitxml")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    extra_args = tuple(args.pytest_args)
    if extra_args[:1] == ("--",):
        extra_args = extra_args[1:]
    return run_gate(
        args.gate,
        timeout_seconds=args.timeout_seconds,
        junit_xml=args.junitxml,
        extra_args=extra_args,
    )


if __name__ == "__main__":
    raise SystemExit(main())
