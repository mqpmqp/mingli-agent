#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
errors = []

index = []
for no, line in enumerate((root / "blind_index.jsonl").read_text(encoding="utf-8").splitlines(), 1):
    if line.strip():
        try:
            index.append(json.loads(line))
        except Exception as exc:
            errors.append(f"blind_index line {no}: {exc}")

reveal = json.loads((root / "private/reveal_key.json").read_text(encoding="utf-8"))
mapping = {x["blind_id"]: x for x in reveal["mapping"]}

if len(index) != 12:
    errors.append(f"expected 12 blind cases, got {len(index)}")
if len(mapping) != 12:
    errors.append(f"expected 12 reveal mappings, got {len(mapping)}")

for item in index:
    bid = item["blind_id"]
    case_dir = root / item["case_path"]
    for name in ("case_brief.md", "answer_A.md", "answer_B.md", "score_sheet.md"):
        if not (case_dir / name).exists():
            errors.append(f"{bid}: missing {name}")
    if bid not in mapping:
        errors.append(f"{bid}: missing reveal mapping")
    else:
        vals = {mapping[bid]["answer_A"], mapping[bid]["answer_B"]}
        if vals != {"baseline", "target"}:
            errors.append(f"{bid}: invalid reveal mapping {vals}")
    for label in ("A", "B"):
        text = (case_dir / f"answer_{label}.md").read_text(encoding="utf-8")
        if "V1.4" in text or "V2" in text or "baseline" in text or "target" in text:
            errors.append(f"{bid}: answer {label} leaks version identity")

print(f"blind_cases={len(index)}")
print(f"reveal_mappings={len(mapping)}")
print(f"errors={len(errors)}")
if errors:
    for e in errors:
        print("ERROR:", e)
    raise SystemExit(1)
print("AB_BLIND_TEST_VALIDATION_PASS")
