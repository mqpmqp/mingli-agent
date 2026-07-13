from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Sequence
from .phase17 import benchmark_phase17, evaluate_special_scenario, load_phase17_rules, phase17_schema_summary, validate_phase17_rules

def _object(path: Path) -> dict[str, object]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ValueError(f"{path} must contain an object")
    return value

def main(argv: Sequence[str] | None=None) -> int:
    parser=argparse.ArgumentParser(prog="mingli-phase17",description="Phase 17 考公考编与复合特殊场景规则")
    sub=parser.add_subparsers(dest="command",required=True)
    evaluate=sub.add_parser("evaluate"); evaluate.add_argument("--phase16-result",type=Path,required=True); evaluate.add_argument("--scenario",choices=("career_exam","relationship_reunion"),required=True); evaluate.add_argument("--target-id",required=True); evaluate.add_argument("--reality",type=Path)
    for name in ("validate","benchmark","rules","schemas"): sub.add_parser(name)
    args=parser.parse_args(argv)
    try:
        if args.command=="evaluate": print(json.dumps(evaluate_special_scenario(_object(args.phase16_result),scenario=args.scenario,target_id=args.target_id,reality_context=_object(args.reality) if args.reality else {}).to_dict(),ensure_ascii=False,sort_keys=True)); return 0
        if args.command=="validate":
            issues=validate_phase17_rules(); print(json.dumps({"status":"passed" if not issues else "failed","issues":list(issues)},ensure_ascii=False,sort_keys=True)); return 1 if issues else 0
        if args.command=="benchmark":
            result=benchmark_phase17(); print(json.dumps(result,ensure_ascii=False,sort_keys=True)); return 1 if result["failed"] else 0
        if args.command=="rules": print(json.dumps(load_phase17_rules(),ensure_ascii=False,sort_keys=True)); return 0
        print(json.dumps(phase17_schema_summary(),ensure_ascii=False,sort_keys=True)); return 0
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc: print(f"error: {exc}",file=sys.stderr); return 1

if __name__=="__main__": raise SystemExit(main())
