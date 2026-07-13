from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Sequence
from .phase18 import PHASE18_DECISION_ID,PHASE18_SCHEMA_VERSION,benchmark_phase18,normalize_reality_context,orchestrate_evidence_fusion
def _read(path):
    value=json.loads(Path(path).read_text(encoding="utf-8")); return value
def main(argv:Sequence[str]|None=None)->int:
    p=argparse.ArgumentParser(prog="mingli-phase18"); s=p.add_subparsers(dest="command",required=True)
    n=s.add_parser("normalize"); n.add_argument("--reality",required=True,type=Path)
    f=s.add_parser("fuse"); f.add_argument("--reality",required=True,type=Path); f.add_argument("--evidence",required=True,type=Path)
    s.add_parser("benchmark"); s.add_parser("schemas"); a=p.parse_args(argv)
    try:
        if a.command=="normalize": print(json.dumps(normalize_reality_context(_read(a.reality)).to_dict(),ensure_ascii=False,sort_keys=True)); return 0
        if a.command=="fuse":
            evidence=_read(a.evidence)
            if not isinstance(evidence,list): raise ValueError("evidence must be an array")
            print(json.dumps(orchestrate_evidence_fusion(_read(a.reality),evidence).to_dict(),ensure_ascii=False,sort_keys=True)); return 0
        if a.command=="benchmark":
            result=benchmark_phase18(); print(json.dumps(result,ensure_ascii=False,sort_keys=True)); return 1 if result["failed"] else 0
        print(json.dumps({"decision_id":PHASE18_DECISION_ID,"schema_version":PHASE18_SCHEMA_VERSION,"prediction_validity":"not_evaluated"},sort_keys=True)); return 0
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc: print(f"error: {exc}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
