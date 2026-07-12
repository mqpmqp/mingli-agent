from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .phase9 import (
    benchmark_phase9,
    calculate_day_master_strength,
    load_phase9_strength_profiles,
    phase9_schema_summary,
    validate_import_origin,
    validate_phase9_profiles,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli-phase9", description="Phase 9 deterministic Bazi strength quantification tools")
    subcommands = parser.add_subparsers(dest="command", required=True)

    calculate = subcommands.add_parser("calculate", help="calculate deterministic day-master strength from a Phase 7 fact graph")
    calculate.add_argument("--graph", required=True, type=Path)
    calculate.add_argument("--profile", default="strength-quantification-r1@0.1")

    subcommands.add_parser("validate", help="validate packaged Phase 9 strength profiles")
    subcommands.add_parser("benchmark", help="run the Phase 9 assertion matrix")
    subcommands.add_parser("profiles", help="output Phase 9 profile manifest")
    subcommands.add_parser("schemas", help="output Phase 9 schema metadata")
    provenance = subcommands.add_parser("provenance", help="verify the active mingli import origin")
    provenance.add_argument("--expected-root", type=Path)
    return parser


def _read_object(path: Path, name: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "calculate":
            graph = _read_object(args.graph, "fact graph")
            result = calculate_day_master_strength(graph, profile_id=args.profile)
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1 if result.unresolved else 0
        if args.command == "validate":
            issues = validate_phase9_profiles()
            payload = {"status": "passed" if not issues else "failed", "issues": list(issues)}
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 1 if issues else 0
        if args.command == "benchmark":
            result = benchmark_phase9()
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            for failure in result.failures:
                print(f"error: {failure}", file=sys.stderr)
            return 1 if (
                result.failed
                or result.unresolved
                or result.schema_failures
                or result.provenance_failures
                or result.hash_mismatches
                or result.threshold_gaps
                or result.threshold_overlaps
            ) else 0
        if args.command == "profiles":
            print(json.dumps(load_phase9_strength_profiles(), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "provenance":
            result = validate_import_origin(args.expected_root)
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            return 0 if result.valid else 1
        print(json.dumps(phase9_schema_summary(), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

