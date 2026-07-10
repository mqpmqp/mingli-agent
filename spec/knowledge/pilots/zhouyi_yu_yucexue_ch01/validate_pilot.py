#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
errors = []

def load_jsonl(name):
    rows = []
    path = root / name
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception as exc:
            errors.append(f"{name}:{no}: invalid JSON: {exc}")
    return rows

concepts = load_jsonl("concept_cards.jsonl")
rules = load_jsonl("candidate_rules.jsonl")
excluded = load_jsonl("non_promotable_claims.jsonl")

if len(concepts) != 30:
    errors.append(f"expected 30 concept cards, got {len(concepts)}")
if not (10 <= len(rules) <= 15):
    errors.append(f"expected 10-15 candidate rules, got {len(rules)}")
if len(excluded) < 5:
    errors.append("expected at least 5 non-promotable claims")

seen = set()
for row in concepts:
    cid = row.get("concept_id")
    if cid in seen:
        errors.append(f"duplicate concept_id: {cid}")
    seen.add(cid)
    for p in row.get("pdf_pages", []):
        if not (16 <= p <= 32):
            errors.append(f"{cid}: PDF page out of chapter: {p}")
    for p in row.get("printed_pages", []):
        if not (1 <= p <= 17):
            errors.append(f"{cid}: printed page out of chapter: {p}")

seen = set()
for row in rules:
    cid = row.get("candidate_id")
    if cid in seen:
        errors.append(f"duplicate candidate_id: {cid}")
    seen.add(cid)
    if row.get("production_allowed") is not False:
        errors.append(f"{cid}: production_allowed must be false")
    if row.get("evidence_level") != "source_only":
        errors.append(f"{cid}: evidence_level must be source_only")
    if row.get("review_status") not in {"draft", "reviewed"}:
        errors.append(f"{cid}: invalid review_status")

for token in ("必然发财", "一定发财", "必离婚", "必有灾"):
    for row in concepts + rules:
        if token in json.dumps(row, ensure_ascii=False):
            errors.append(f"forbidden absolute claim found: {token}")

print(f"concept_cards={len(concepts)}")
print(f"candidate_rules={len(rules)}")
print(f"non_promotable_claims={len(excluded)}")
print(f"errors={len(errors)}")
if errors:
    for error in errors:
        print("ERROR:", error)
    raise SystemExit(1)
print("PILOT_VALIDATION_PASS")
