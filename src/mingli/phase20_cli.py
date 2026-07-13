from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Sequence
from .phase20 import PHASE20_DECISION_ID, PHASE20_SCHEMA_VERSION, benchmark_phase20, render_yuan_eight_sections

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mingli-phase20"); commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render"); render.add_argument("--input", required=True, type=Path)
    commands.add_parser("benchmark"); commands.add_parser("schemas"); args = parser.parse_args(argv)
    try:
        if args.command == "render": result = render_yuan_eight_sections(json.loads(args.input.read_text(encoding="utf-8"))).to_dict()
        elif args.command == "benchmark": result = benchmark_phase20()
        else: result = {"decision_id": PHASE20_DECISION_ID, "schema_version": PHASE20_SCHEMA_VERSION, "prediction_validity": "not_evaluated"}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True)); return 1 if result.get("failed") else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())
