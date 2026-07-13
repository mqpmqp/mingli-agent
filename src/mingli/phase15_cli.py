from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .phase15 import (
    benchmark_phase15,
    evaluate_bazi_tengod_domains,
    load_phase15_domain_profiles,
    phase15_schema_summary,
    query_domain_judgements,
    validate_import_origin,
    validate_phase15_profiles,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mingli-phase15",
        description="Phase 15 deterministic Bazi TenGod dynamic domain judgement candidate tools",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    evaluate = subcommands.add_parser("evaluate")
    evaluate.add_argument("--graph", required=True, type=Path)
    evaluate.add_argument("--interaction", required=True, type=Path)
    evaluate.add_argument("--trend", required=True, type=Path)
    evaluate.add_argument("--reality", type=Path)
    evaluate.add_argument("--profile", default="tengod-domain-judgement-r1@0.1")

    query = subcommands.add_parser("query")
    query.add_argument("--result", required=True, type=Path)
    query.add_argument("--domain", choices=("career", "wealth", "relationship", "education", "exam", "startup", "migration"))
    selector = query.add_mutually_exclusive_group(required=True)
    selector.add_argument("--year", type=int)
    selector.add_argument("--age", type=int)
    selector.add_argument("--target-id")

    subcommands.add_parser("validate")
    subcommands.add_parser("benchmark")
    subcommands.add_parser("profiles")
    subcommands.add_parser("schemas")
    provenance = subcommands.add_parser("provenance")
    provenance.add_argument("--expected-root", type=Path)
    return parser


def _read_object(path: Path, label: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _read_reality(path: Path | None) -> tuple[dict[str, object], ...]:
    if path is None:
        return ()
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("reality evidence must be a JSON array of objects")
    return tuple(value)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "evaluate":
            result = evaluate_bazi_tengod_domains(
                _read_object(args.graph, "fact graph"),
                _read_object(args.interaction, "interaction result"),
                _read_object(args.trend, "temporal trend result"),
                reality_evidence=_read_reality(args.reality),
                profile_id=args.profile,
            )
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        if args.command == "query":
            result = _read_object(args.result, "domain judgement result")
            matches = query_domain_judgements(
                result,
                domain=args.domain,
                year=args.year,
                age=args.age,
                target_id=args.target_id,
            )
            print(json.dumps({"matches": list(matches)}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        if args.command == "validate":
            issues = validate_phase15_profiles()
            print(json.dumps({"status": "passed" if not issues else "failed", "issues": list(issues)}, ensure_ascii=False, sort_keys=True))
            return 1 if issues else 0
        if args.command == "benchmark":
            result = benchmark_phase15()
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            for failure in result.failures:
                print(f"error: {failure}", file=sys.stderr)
            return 1 if any((
                result.failed,
                result.unresolved,
                result.schema_failures,
                result.provenance_failures,
                result.hash_mismatches,
                result.ten_god_mapping_failures,
                result.domain_partition_failures,
                result.query_failures,
                result.reality_override_failures,
                result.claim_boundary_failures,
                result.prediction_boundary_failures,
            )) else 0
        if args.command == "profiles":
            print(json.dumps(load_phase15_domain_profiles(), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "provenance":
            result = validate_import_origin(args.expected_root)
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            return 0 if result.valid else 1
        print(json.dumps(phase15_schema_summary(), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
