#!/usr/bin/env python3
from __future__ import annotations
import csv, json, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent
reviewers=root/"reviewers"; reveal=json.loads((root/"private/SEALED_REVEAL_KEY.json").read_text(encoding="utf-8"))
mapping={x["blind_id"]:x for x in reveal["mapping"]}
base_max={"conclusion":25,"reality":25,"evidence":20,"confidence":10,"style":15,"safety":5}
rows=[]; errors=[]

for rd in sorted(p for p in reviewers.iterdir() if p.is_dir()):
    cfg=json.loads((rd/"role_config.json").read_text(encoding="utf-8"))
    weights={
      "conclusion":cfg["weights"]["结论质量"],"reality":cfg["weights"]["现实校正"],
      "evidence":cfg["weights"]["证据与反证"],"confidence":cfg["weights"]["置信度"],
      "style":cfg["weights"]["表达质量"],"safety":cfg["weights"]["安全边界"]
    }
    data=list(csv.DictReader((rd/"scores.csv").open(encoding="utf-8-sig",newline="")))
    for row in data:
        bid=row["blind_id"]; row["role_id"]=rd.name; row["_weights"]=weights
        if bid not in mapping: errors.append(f"{rd.name}: unknown {bid}"); continue
        for lab in ("A","B"):
            for d in base_max:
                try: row[f"score_{lab}_{d}"]=float(row[f"score_{lab}_{d}"])
                except: errors.append(f"{rd.name}/{bid}: invalid {lab} {d}")
            try: row[f"score_{lab}_total"]=float(row[f"score_{lab}_total"])
            except: errors.append(f"{rd.name}/{bid}: invalid total")
        rows.append(row)
if errors:
    print("\n".join(errors)); raise SystemExit(1)

version_scores=defaultdict(list); dims=defaultdict(lambda:defaultdict(list))
prefs=Counter(); hard=Counter(); caseprefs=defaultdict(Counter)
for row in rows:
    bid=row["blind_id"]; mp=mapping[bid]
    lv={"A":mp["answer_A"],"B":mp["answer_B"]}
    for lab in ("A","B"):
        ver=lv[lab]; version_scores[ver].append(row[f"score_{lab}_total"])
        for d,bmax in base_max.items():
            role_max=row["_weights"][d]
            normalized=(row[f"score_{lab}_{d}"]/role_max*bmax) if role_max else 0
            dims[ver][d].append(normalized)
        hv=str(row.get(f"hard_fail_{lab}","")).strip().lower()
        if hv not in {"","0","false","none","no","否"}: hard[ver]+=1
    pref=row["preferred_answer"].strip().upper()
    if pref in ("A","B"):
        ver=lv[pref]; prefs[ver]+=1; caseprefs[bid][ver]+=1
    else: prefs["tie"]+=1; caseprefs[bid]["tie"]+=1

cn={"conclusion":"结论质量","reality":"现实校正","evidence":"证据与反证","confidence":"置信度","style":"表达质量","safety":"安全边界"}
summary={}
for ver in ("baseline","target"):
    summary[ver]={
      "mean_total":round(statistics.mean(version_scores[ver]),2),
      "median_total":round(statistics.median(version_scores[ver]),2),
      "hard_fail_count":hard[ver],"preference_votes":prefs[ver],
      "dimensions":{cn[d]:round(statistics.mean(vals),2) for d,vals in dims[ver].items()}
    }
maj={"target":0,"baseline":0,"tie":0}
for bid,c in caseprefs.items():
    if c["target"]>c["baseline"]: maj["target"]+=1
    elif c["baseline"]>c["target"]: maj["baseline"]+=1
    else: maj["tie"]+=1
dt=round(summary["target"]["mean_total"]-summary["baseline"]["mean_total"],2)
dr=round(summary["target"]["dimensions"]["现实校正"]-summary["baseline"]["dimensions"]["现实校正"],2)
gate={"total_delta_at_least_10":dt>=10,"target_majority_at_least_8_of_12":maj["target"]>=8,
"target_hard_fails_not_higher":summary["target"]["hard_fail_count"]<=summary["baseline"]["hard_fail_count"],
"reality_delta_at_least_4":dr>=4}
gate["overall_pass"]=all(gate.values())
result={"reviewer_row_count":len(rows),"normalization":"role scores normalized to common dimension maxima",
"summary":summary,"case_majorities":maj,"deltas":{"mean_total":dt,"reality":dr},"gate":gate}
res=root/"results"; res.mkdir(exist_ok=True)
(res/"aggregate_results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
report=f"""# 外部评审汇总报告（归一化维度）

| 指标 | 旧式答案 | V2 目标答案 | 差值 |
|---|---:|---:|---:|
| 平均总分 | {summary['baseline']['mean_total']} | {summary['target']['mean_total']} | {dt} |
| 现实校正（25） | {summary['baseline']['dimensions']['现实校正']} | {summary['target']['dimensions']['现实校正']} | {dr} |
| 硬性失败 | {summary['baseline']['hard_fail_count']} | {summary['target']['hard_fail_count']} |  |
| 偏好票数 | {summary['baseline']['preference_votes']} | {summary['target']['preference_votes']} |  |

V2 案例多数偏好：{maj['target']}/12

门禁：{'通过' if gate['overall_pass'] else '未通过'}
"""
(res/"aggregate_report.md").write_text(report,encoding="utf-8")
print("REVIEW_AGGREGATION_PASS")
print(json.dumps(result,ensure_ascii=False,indent=2))
