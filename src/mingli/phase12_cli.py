from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .phase12 import (
    benchmark_phase12,
    evaluate_bazi_xiji_roles,
    load_phase12_xiji_profiles,
    phase12_schema_summary,
    validate_import_origin,
    validate_phase12_profiles,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli-phase12", description="Phase 12 deterministic Bazi XiJi role classification tools")
    subcommands = parser.add_subparsers(dest="command", required=True)
    evaluate = subcommands.add_parser("evaluate")
    evaluate.add_argument("--regulation", required=True, type=Path)
    evaluate.add_argument("--profile", default="xiji-role-classification-r1@0.1")
    subcommands.add_parser("validate")
    subcommands.add_parser("benchmark")
    subcommands.add_parser("profiles")
    subcommands.add_parser("schemas")
    provenance = subcommands.add_parser("provenance")
    provenance.add_argument("--expected-root", type=Path)
    return parser


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("regulation result must be a JSON object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "evaluate":
            result = evaluate_bazi_xiji_roles(_read(args.regulation), profile_id=args.profile)
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        if args.command == "validate":
            issues = validate_phase12_profiles()
            print(json.dumps({"status": "passed" if not issues else "failed", "issues": list(issues)}, ensure_ascii=False, sort_keys=True))
            return 1 if issues else 0
        if args.command == "benchmark":
            result = benchmark_phase12()
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            for failure in result.failures:
                print(f"error: {failure}", file=sys.stderr)
            return 1 if any((
                result.failed,
                result.unresolved,
                result.schema_failures,
                result.provenance_failures,
                result.hash_mismatches,
                result.role_partition_failures,
                result.role_collision_failures,
                result.carrier_failures,
                result.prediction_boundary_failures,
            )) else 0
        if args.command == "profiles":
            print(json.dumps(load_phase12_xiji_profiles(), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "provenance":
            result = validate_import_origin(args.expected_root)
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            return 0 if result.valid else 1
        print(json.dumps(phase12_schema_summary(), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
