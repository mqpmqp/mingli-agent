# Product Release Gate

## P19 RC2 decision

```yaml
p19_verse_blocker: removed_by_design
p19_algorithm_status: usable
p19_verse_pack_status: future_optional_pack
verse_available: false
```

RC2 核心包保留 P19 称骨算法、骨重表、年/月/日/时权重、`display_weight` 和 `canonical_hash`。完整歌诀原文、歌诀 package-data 与现代白话解释不属于 RC2 范围。未来 optional verse pack 必须作为独立版本和独立审核项目，不能改变核心算法结果。

## Validation closure gate

全部条件同时满足时，`validation_closure_passed=true`：

```yaml
qualified_validation_cases: ">= 30"
gold_cases: ">= 10"
silver_cases: "<= 20"
bronze_counted: 0
comparable_claims: ">= 100"
scenario_coverage: ">= 3"
consent_rate: 1.0
pii_leak_count: 0
freeze_hash_coverage_gold: 1.0
double_review_coverage: 1.0
adjudication_required_when_disagreement: true
```

`qualified_validation_cases` 按唯一人员案例计数，不按同一人的多个场景重复计数。Gold 与 Silver 可进入 validation closure；Bronze 和合成案例不得计数。

## Product accuracy claim gate

该门禁与 validation closure 独立：

```yaml
eligible_gold_cases: ">= 30"
prospective_only: true
silver_counted: 0
bronze_counted: 0
product_accuracy_claim_allowed: true
```

只有全部条件通过后才能把 `product_accuracy_claim_allowed` 设为 `true`。Silver 的回顾性结果只能作为辅助指标，不能用于产品准确率声明。

## Required metrics

报告必须同时给出样本数、分子、分母和不可计算原因，不得只报告 simple accuracy：

- `coverage`
- `abstention_rate`
- `brier_score`
- `ece`
- `scenario_metrics`
- `domain_metrics`
- Gold/Silver 分层结果
- `pii_leak_count`
