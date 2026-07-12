from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .phase10 import (
    benchmark_phase10,
    evaluate_bazi_pattern,
    load_phase10_pattern_profiles,
    phase10_schema_summary,
    validate_import_origin,
    validate_phase10_profiles,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli-phase10", description="Phase 10 deterministic Bazi pattern evaluation tools")
    subcommands = parser.add_subparsers(dest="command", required=True)
    evaluate = subcommands.add_parser("evaluate")
    evaluate.add_argument("--graph", required=True, type=Path)
    evaluate.add_argument("--strength", required=True, type=Path)
    evaluate.add_argument("--profile", default="bazi-pattern-evaluation-r1@0.1")
    subcommands.add_parser("validate")
    subcommands.add_parser("benchmark")
    subcommands.add_parser("profiles")
    subcommands.add_parser("schemas")
    provenance = subcommands.add_parser("provenance")
    provenance.add_argument("--expected-root", type=Path)
    return parser


def _read(path: Path, name: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "evaluate":
            result = evaluate_bazi_pattern(_read(args.graph, "fact graph"), _read(args.strength, "strength result"), profile_id=args.profile)
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        if args.command == "validate":
            issues = validate_phase10_profiles()
            print(json.dumps({"status": "passed" if not issues else "failed", "issues": list(issues)}, ensure_ascii=False, sort_keys=True))
            return 1 if issues else 0
        if args.command == "benchmark":
            result = benchmark_phase10()
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            for failure in result.failures:
                print(f"error: {failure}", file=sys.stderr)
            return 1 if any((result.failed, result.unresolved, result.schema_failures, result.provenance_failures, result.hash_mismatches, result.threshold_gaps, result.threshold_overlaps, result.conflict_order_failures)) else 0
        if args.command == "profiles":
            print(json.dumps(load_phase10_pattern_profiles(), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "provenance":
            result = validate_import_origin(args.expected_root)
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            return 0 if result.valid else 1
        print(json.dumps(phase10_schema_summary(), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
