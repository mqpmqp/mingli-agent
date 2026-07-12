# Phase 8 Rule Evaluation / Evidence Layer V1 Report

## Marker

```text
PHASE_8_RULE_EVALUATION_EVIDENCE_LAYER_V1_COMPLETE
```

This report records the Phase 8 implementation contract. GitHub PR, CI, merge and mainline readback fields are finalized after the implementation branch passes remote gates.

## Baseline and Scope

- Baseline main: `5c09b0788fd7126de402a3f524604d0450556e9e`
- Branch: `agent/phase8-rule-evaluation-evidence-layer-v1`
- Phase 7 Fact Graph remains the immutable upstream input.
- `spec/` and `knowledge/` are protected and unchanged.

Phase 8 implements the deterministic chain:

```text
Fact Graph
→ Rule Matching
→ Evidence Records
→ Conflict Resolution
→ Confidence Inputs
```

Renderer integration is explicitly deferred.

## Implemented Contracts

### Rule evaluation

`EvaluationRule` provides stable rule/version/claim identity, support or contradict direction, bounded weight and priority, reviewed or verified execution gates, required and blocking conditions, explicit reality override codes and source provenance.

Only `reviewed` and `verified` rules execute. Draft and deprecated rules are retained as deterministic `skipped` records.

### Condition language

Fact Graph selectors are intentionally bounded:

- collections: root, nodes, edges, relations, growth stages and profiles
- exact `where` matching with dotted paths
- quantifiers: any, none, all and count-at-least

Reality selectors support equals, not-equals, in, contains, exists and numeric gte/lte. No arbitrary expression evaluator, Python evaluation, LLM or network resolver is present.

### Evidence and conflict handling

Each matched rule emits an immutable `EvidenceRecord`. Each claim retains all support and contradict evidence.

Conflict order is fixed:

1. verified Reality Evidence hard override
2. higher rule priority
3. equal-priority opposition remains unresolved

Reality overrides are claim-scoped. A rule must explicitly declare the override code, and the claim must already have matched rule evidence. Unrelated claims are not modified.

### Confidence inputs

Phase 8 emits structured `ConfidenceInputRecord` objects and does not render final prose.

- verified reality hard override: high confidence for the corrected direction
- priority-resolved conflict: medium confidence
- equal-priority unresolved conflict: low confidence
- missing information, unconfirmed image or single-symbol input: low-confidence gate

### Provenance and determinism

Every evaluation result includes the Phase 7 Fact Graph hash, canonical rule-set hash, rule source IDs, active reality override codes, confidence inputs, Phase 8 decision ID and canonical result SHA-256. Rule order and JSON key order do not change the result hash.

### Import-origin quality gate

`validate_import_origin(...)` outputs `mingli.__file__` and requires either an explicitly supplied checkout root or an isolated virtual environment. A global or stale editable install without an expected checkout root fails the gate.

## CLI

```bash
python -m mingli.phase8_cli evaluate --graph fact_graph.json --rules rules.json --reality reality.json --intent career
python -m mingli.phase8_cli validate --rules rules.json
python -m mingli.phase8_cli benchmark
python -m mingli.phase8_cli schemas
python -m mingli.phase8_cli provenance --expected-root .
```

The wheel also exposes `mingli-phase8`.

## Benchmark

The deterministic internal benchmark contains 35 contract assertions:

| Category | Assertions |
|---|---:|
| rule evaluation | 8 |
| evidence records | 5 |
| conflict resolution | 7 |
| confidence inputs | 5 |
| provenance and boundaries | 5 |
| deterministic hashing | 5 |
| total | 35 |

Expected result:

```yaml
assertions_total: 35
passed: 35
failed: 0
unresolved: 0
```

Coverage includes matched, not-matched, blocked and skipped rules; priority conflict resolution; equal-priority unresolved representation; Reality Evidence hard override; confidence degradation; claim scoping; provenance; and deterministic reordering.

## Tests

`tests/test_phase8_rule_evaluation.py` covers:

- direct consumption of a real Phase 7 Fact Graph
- strict rule and condition validation
- blocked and non-executable rule behavior
- claim-scoped reality hard override
- priority and equal-priority conflicts
- deterministic canonical hashes
- JSON and JSONL rule loading
- dedicated Phase 8 CLI
- checkout import-origin validation
- fresh temporary venv wheel install and installed-package benchmark

## Boundaries

Phase 8 does not add:

- 旺衰或身强身弱
- 格局
- 调候
- 用神或喜忌
- 吉凶判断
- 事业、财运、感情或健康预测
- 事件窗口
- 自然语言命理报告
- Renderer integration
- LLM, external API, database, cache or network runtime dependency

Every successful result remains:

```json
{"prediction_validity":"not_evaluated"}
```

## Release State

```yaml
baseline: 5c09b0788fd7126de402a3f524604d0450556e9e
implementation_branch: agent/phase8-rule-evaluation-evidence-layer-v1
implementation_commit: pending
pull_request: pending
pr_ci: pending
merge_commit: pending
main_head: pending
main_ci: pending
spec_modified: false
knowledge_modified: false
prediction_added: false
remaining_blockers: pending remote verification
```
