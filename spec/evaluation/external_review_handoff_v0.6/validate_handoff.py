#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
errors = []

index_path = root.parent / "ab_blind_test_v0.5/blind_index.jsonl"
index = [
    json.loads(line)
    for line in index_path.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
expected_ids = {x["blind_id"] for x in index}

reveal_path = root / "private/SEALED_REVEAL_KEY.json"
sha_path = root / "private/SEALED_REVEAL_KEY.sha256"
actual_sha = hashlib.sha256(reveal_path.read_bytes()).hexdigest()
expected_sha = sha_path.read_text(encoding="utf-8").split()[0]
if actual_sha != expected_sha:
    errors.append("sealed reveal checksum mismatch")

reviewer_dirs = [p for p in (root / "reviewers").iterdir() if p.is_dir()]
if len(reviewer_dirs) != 3:
    errors.append(f"expected 3 reviewer roles, got {len(reviewer_dirs)}")

for rdir in reviewer_dirs:
    for required in ("REVIEWER_GUIDE.md", "scores.csv", "role_config.json"):
        if not (rdir / required).exists():
            errors.append(f"{rdir.name}: missing {required}")
    rows = list(csv.DictReader((rdir / "scores.csv").open(encoding="utf-8-sig")))
    ids = {r["blind_id"] for r in rows}
    if ids != expected_ids:
        errors.append(f"{rdir.name}: score IDs do not match blind index")

blind_cases = [p for p in (root / "blind_cases").iterdir() if p.is_dir()]
if len(blind_cases) != 12:
    errors.append(f"expected 12 blind case directories, got {len(blind_cases)}")
for case_dir in blind_cases:
    for required in ("case_brief.md", "answer_A.md", "answer_B.md", "score_sheet.md"):
        if not (case_dir / required).exists():
            errors.append(f"{case_dir.name}: missing {required}")

print(f"reviewer_roles={len(reviewer_dirs)}")
print(f"blind_cases={len(blind_cases)}")
print(f"errors={len(errors)}")
if errors:
    for error in errors:
        print("ERROR:", error)
    raise SystemExit(1)
print("EXTERNAL_REVIEW_HANDOFF_VALIDATION_PASS")
