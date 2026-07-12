from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .phase8 import (
    benchmark_phase8,
    evaluate_rule_set,
    load_phase8_rules,
    phase8_schema_summary,
    validate_import_origin,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli-phase8", description="Phase 8 deterministic rule evaluation and evidence tools")
    subcommands = parser.add_subparsers(dest="command", required=True)

    evaluate = subcommands.add_parser("evaluate", help="evaluate a Phase 8 rule set against a Phase 7 fact graph")
    evaluate.add_argument("--graph", required=True, type=Path)
    evaluate.add_argument("--rules", required=True, type=Path)
    evaluate.add_argument("--reality", type=Path)
    evaluate.add_argument("--intent", default="unspecified")
    evaluate.add_argument("--signal", action="append", default=[])
    evaluate.add_argument("--missing-information", action="store_true")
    evaluate.add_argument("--image-unconfirmed", action="store_true")
    evaluate.add_argument("--single-symbol", action="store_true")
    evaluate.add_argument("--high-stakes", choices=("medical", "investment"))

    validate = subcommands.add_parser("validate", help="validate a Phase 8 rule set")
    validate.add_argument("--rules", required=True, type=Path)
    subcommands.add_parser("benchmark", help="run the Phase 8 contract benchmark")
    subcommands.add_parser("schemas", help="show Phase 8 contract metadata")
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
        if args.command == "evaluate":
            graph = _read_object(args.graph, "fact graph")
            rules = load_phase8_rules(args.rules)
            reality = _read_object(args.reality, "reality") if args.reality else {}
            result = evaluate_rule_set(
                graph,
                rules,
                intent=args.intent,
                reality=reality,
                chart_signals=tuple(args.signal),
                missing_information=args.missing_information,
                image_unconfirmed=args.image_unconfirmed,
                single_symbol=args.single_symbol,
                high_stakes=args.high_stakes,
            )
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 1 if result.unresolved else 0
        if args.command == "validate":
            rules = load_phase8_rules(args.rules)
            print(json.dumps({"status": "passed", "rules": len(rules)}, ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "benchmark":
            result = benchmark_phase8()
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            for failure in result.failures:
                print(f"error: {failure}", file=sys.stderr)
            return 1 if result.failed or result.unresolved else 0
        if args.command == "provenance":
            result = validate_import_origin(args.expected_root)
            print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
            return 0 if result.valid else 1
        print(json.dumps(phase8_schema_summary(), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
