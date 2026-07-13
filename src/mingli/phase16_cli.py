from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .phase16 import (
    benchmark_phase16,
    evaluate_base_domain_contracts,
    load_phase16_base_rules,
    phase16_schema_summary,
    query_base_domain_contracts,
    validate_import_origin,
    validate_phase16_rules,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mingli-phase16",
        description="Phase 16 事业、财运、感情基础领域判断合同工具",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    evaluate = subcommands.add_parser("evaluate")
    evaluate.add_argument("--phase15-result", required=True, type=Path)
    evaluate.add_argument("--profile", default="base-domain-contract-r1@0.1")
    query = subcommands.add_parser("query")
    query.add_argument("--result", required=True, type=Path)
    query.add_argument("--domain", choices=("career", "wealth", "relationship"))
    selector = query.add_mutually_exclusive_group(required=True)
    selector.add_argument("--year", type=int)
    selector.add_argument("--age", type=int)
    selector.add_argument("--target-id")
    subcommands.add_parser("validate")
    subcommands.add_parser("benchmark")
    subcommands.add_parser("rules")
    subcommands.add_parser("schemas")
    provenance = subcommands.add_parser("provenance")
    provenance.add_argument("--expected-root", type=Path)
    return parser


def _read_object(path: Path, label: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "evaluate":
            result = evaluate_base_domain_contracts(
                _read_object(args.phase15_result, "Phase 15 result"),
                profile_id=args.profile,
            )
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        if args.command == "query":
            matches = query_base_domain_contracts(
                _read_object(args.result, "Phase 16 result"),
                domain=args.domain,
                year=args.year,
                age=args.age,
                target_id=args.target_id,
            )
            print(json.dumps({"matches": list(matches)}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        if args.command == "validate":
            issues = validate_phase16_rules()
            print(json.dumps({"status": "passed" if not issues else "failed", "issues": list(issues)}, ensure_ascii=False, sort_keys=True))
            return 1 if issues else 0
        if args.command == "benchmark":
            result = benchmark_phase16()
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            for failure in result.failures:
                print(f"error: {failure}", file=sys.stderr)
            return 1 if any((
                result.failed,
                result.unresolved,
                result.schema_failures,
                result.provenance_failures,
                result.hash_mismatches,
                result.rule_coverage_failures,
                result.contract_partition_failures,
                result.reality_preservation_failures,
                result.query_failures,
                result.prediction_boundary_failures,
            )) else 0
        if args.command == "rules":
            print(json.dumps(load_phase16_base_rules(), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "provenance":
            result = validate_import_origin(args.expected_root)
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            return 0 if result.valid else 1
        print(json.dumps(phase16_schema_summary(), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
