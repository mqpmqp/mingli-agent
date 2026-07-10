#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
errors: list[str] = []
ids: dict[tuple[str, str], list[str]] = defaultdict(list)

for path in sorted(root.rglob("*.json")):
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"JSON parse failed: {path.relative_to(root)}: {exc}")

for path in sorted(root.rglob("*.jsonl")):
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception as exc:
            errors.append(f"JSONL parse failed: {path.relative_to(root)}:{line_no}: {exc}")
            continue

        # Use the record's own primary key, not foreign keys such as source_id.
        primary_keys = ("id", "review_id", "candidate_id", "case_id")
        for key in primary_keys:
            value = obj.get(key)
            if isinstance(value, str):
                namespace = path.parent.name
                ids[(namespace, value)].append(f"{path.relative_to(root)}:{line_no}")
                break
        else:
            # source_registry records legitimately use source_id as their primary key.
            value = obj.get("source_id")
            if isinstance(value, str) and path.name == "source_registry.jsonl":
                ids[("sources", value)].append(f"{path.relative_to(root)}:{line_no}")

for (namespace, value), locations in ids.items():
    if len(locations) > 1:
        errors.append(f"Duplicate ID in {namespace}: {value}: {', '.join(locations)}")

required = [
    "system/system_prompt.md",
    "knowledge/sources/source_registry.jsonl",
    "knowledge/ingestion/INGESTION_POLICY.md",
    "evaluation/golden_cases_v0.2.jsonl",
]
for rel in required:
    if not (root / rel).exists():
        errors.append(f"Missing required file: {rel}")

print(f"root={root}")
print(f"errors={len(errors)}")
if errors:
    for error in errors:
        print(f"ERROR: {error}")
    raise SystemExit(1)
print("VALIDATION_PASS")
