from __future__ import annotations

import base64
import gzip
import os
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "src" / "mingli" / "phase7.py"
source = path.read_text(encoding="utf-8")
anchor = (
    "    pillars = _pillars_from_value(derived_chart)\n"
    "    growth_targets = tuple((stem, branch) for _, stem, branch in pillars)\n"
)
replacement = (
    "    pillars = _pillars_from_value(derived_chart)\n"
    "    day_masters = [stem for position, stem, _branch in pillars if position == \"day\"]\n"
    "    if len(day_masters) != 1:\n"
    "        raise ValueError(\"derived pillars must contain exactly one day pillar\")\n"
    "    day_master = day_masters[0]\n"
    "    growth_targets = tuple((stem, branch) for _, stem, branch in pillars)\n"
)
if source.count(anchor) != 1:
    raise RuntimeError("unexpected Phase 7 pillar anchor")
source = source.replace(anchor, replacement)
replacements = {
    "map_hidden_stems(branch, day_master=pillars[2][1])": "map_hidden_stems(branch, day_master=day_master)",
    "map_ten_god(pillars[2][1], stem)": "map_ten_god(day_master, stem)",
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise RuntimeError(f"unexpected Phase 7 occurrence count: {old}")
    source = source.replace(old, new)
if "pillars[2][1]" in source:
    raise RuntimeError("positional day-master access remains")
encoded = base64.b64encode(gzip.compress(source.encode("utf-8"), compresslevel=9)).decode("ascii")
print(f"PHASE7_PATCH_GZIP_B64={encoded}", flush=True)
os._exit(1)
