from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Sequence
from .phase21 import PHASE21_DECISION_ID, PHASE21_SCHEMA_VERSION, benchmark_phase21, generate_five_year_outlook

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mingli-phase21"); commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate"); generate.add_argument("--input", required=True, type=Path)
    commands.add_parser("benchmark"); commands.add_parser("schemas"); args = parser.parse_args(argv)
    try:
        if args.command == "generate": result = generate_five_year_outlook(json.loads(args.input.read_text(encoding="utf-8"))).to_dict()
        elif args.command == "benchmark": result = benchmark_phase21()
        else: result = {"decision_id": PHASE21_DECISION_ID, "schema_version": PHASE21_SCHEMA_VERSION, "prediction_validity": "not_evaluated"}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True)); return 1 if result.get("failed") else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())
