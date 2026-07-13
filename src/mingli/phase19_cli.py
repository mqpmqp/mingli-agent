from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Sequence
from .phase19 import PHASE19_DECISION_ID, PHASE19_SCHEMA_VERSION, benchmark_phase19, calculate_chenggu, load_chenggu_table, validate_phase19_table

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mingli-phase19")
    commands = parser.add_subparsers(dest="command", required=True)
    calc = commands.add_parser("calculate"); calc.add_argument("--input", required=True, type=Path)
    commands.add_parser("validate"); commands.add_parser("benchmark"); commands.add_parser("table"); commands.add_parser("schemas")
    args = parser.parse_args(argv)
    try:
        if args.command == "calculate":
            raw = json.loads(args.input.read_text(encoding="utf-8")); print(json.dumps(calculate_chenggu(raw).to_dict(), ensure_ascii=False, sort_keys=True)); return 0
        if args.command == "validate": result = validate_phase19_table()
        elif args.command == "benchmark": result = benchmark_phase19()
        elif args.command == "table": result = load_chenggu_table()
        else: result = {"decision_id": PHASE19_DECISION_ID, "schema_version": PHASE19_SCHEMA_VERSION, "prediction_validity": "not_evaluated"}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True)); return 1 if result.get("failed") or result.get("valid") is False else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())
