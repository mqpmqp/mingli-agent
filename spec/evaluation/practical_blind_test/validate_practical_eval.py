#!/usr/bin/env python3
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); errors=[]; cases=[]
for no,line in enumerate((root/'practical_cases.jsonl').read_text(encoding='utf-8').splitlines(),1):
    if not line.strip(): continue
    try: cases.append(json.loads(line))
    except Exception as e: errors.append(f'invalid JSON at line {no}: {e}')
ids=set(); required=['id','category','prompt','facts','must_include','must_not','target_confidence','target_outline']
for c in cases:
    cid=c.get('id')
    if cid in ids: errors.append(f'duplicate case id: {cid}')
    ids.add(cid)
    for f in required:
        if f not in c: errors.append(f'{cid}: missing field {f}')
    if not c.get('must_include'): errors.append(f'{cid}: must_include empty')
    if not c.get('must_not'): errors.append(f'{cid}: must_not empty')
if len(cases)<20: errors.append(f'expected at least 20 cases, got {len(cases)}')
style=json.loads((root/'style_guard.json').read_text(encoding='utf-8'))
if 'forbidden_phrases' not in style or 'required_patterns' not in style: errors.append('style_guard missing required sections')
required_categories={'image_chart','career_exam','relationship_reunion','startup','wealth','career','fengshui','health','investment','style'}
missing=sorted(required_categories-{c['category'] for c in cases})
if missing: errors.append(f'missing categories: {missing}')
print(f'cases={len(cases)}'); print(f'categories={len({c["category"] for c in cases})}'); print(f'errors={len(errors)}')
if errors:
    [print('ERROR:',e) for e in errors]; raise SystemExit(1)
print('PRACTICAL_EVAL_VALIDATION_PASS')
