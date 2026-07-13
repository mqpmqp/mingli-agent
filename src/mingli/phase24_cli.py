from __future__ import annotations
import argparse, json, sys
from typing import Sequence
from .phase24 import PHASE24_DECISION_ID, PHASE24_SCHEMA_VERSION, assess_release_candidate, benchmark_phase24

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mingli-phase24"); commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("assess"); commands.add_parser("benchmark"); commands.add_parser("schemas"); args = parser.parse_args(argv)
    try:
        if args.command == "assess": result = assess_release_candidate().to_dict()
        elif args.command == "benchmark": result = benchmark_phase24()
        else: result = {"decision_id": PHASE24_DECISION_ID, "schema_version": PHASE24_SCHEMA_VERSION, "prediction_validity": "not_evaluated"}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True)); return 1 if result.get("failed") else 0
    except (ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())
