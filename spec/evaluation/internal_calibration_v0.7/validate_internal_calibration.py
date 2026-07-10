#!/usr/bin/env python3
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
errors=[]
res=json.loads((root/"internal_aggregate_results.json").read_text(encoding="utf-8"))
gaps=json.loads((root/"gap_analysis.json").read_text(encoding="utf-8"))
method=json.loads((root/"calibration_method.json").read_text(encoding="utf-8"))
if not res.get("gate",{}).get("overall_pass"): errors.append("gate failed")
if len(gaps)<6: errors.append("too few gap findings")
if method.get("status")!="internal_non_independent_calibration": errors.append("status not explicit")
if not (root/"RENDERER_PATCH_V0.7.md").exists(): errors.append("missing renderer patch")
if res.get("normalization")!="role scores normalized to common dimension maxima": errors.append("normalization missing")
print(f"gap_findings={len(gaps)}")
print(f"gate_pass={res.get('gate',{}).get('overall_pass')}")
print(f"errors={len(errors)}")
if errors:
  [print("ERROR:",e) for e in errors]; raise SystemExit(1)
print("INTERNAL_CALIBRATION_VALIDATION_PASS")
