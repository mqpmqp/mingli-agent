from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Sequence
from .phase22 import PHASE22_DECISION_ID, PHASE22_SCHEMA_VERSION, benchmark_phase22, load_case_registry, run_case_benchmark

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mingli-phase22"); commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run"); run.add_argument("--registry", type=Path)
    commands.add_parser("benchmark"); commands.add_parser("registry"); commands.add_parser("schemas"); args = parser.parse_args(argv)
    try:
        if args.command == "run": result = run_case_benchmark(json.loads(args.registry.read_text(encoding="utf-8")) if args.registry else None).to_dict()
        elif args.command == "benchmark": result = benchmark_phase22()
        elif args.command == "registry": result = load_case_registry()
        else: result = {"decision_id": PHASE22_DECISION_ID, "schema_version": PHASE22_SCHEMA_VERSION, "prediction_validity": "not_evaluated"}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True)); return 1 if result.get("failed") else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())
