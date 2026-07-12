# Phase 10 Bazi Pattern Evaluation V1

## Scope

Phase 10 adds deterministic structural Bazi pattern candidate evaluation on top of the Phase 7 Fact Graph and Phase 9 strength result. It does not add climate adjustment, useful-god selection, favorable/unfavorable judgement, luck-cycle prediction, natural-language rendering, LLM behavior, or network dependencies.

## Contracts and flow

The implementation provides immutable contracts for profiles, sources, conditions, establishment/breaking/rescue evidence, conflicts, candidate results, evaluation results, and benchmark results.

The evaluation flow is:

1. Validate reviewed profile, input shape, prediction boundary, canonical hashes, four pillars, day master, month branch, month hidden stems, and cross-input node references.
2. Generate explicitly typed ordinary, Jian Lu, Yang Ren, follower-boundary, transformation-boundary, or unresolved candidates.
3. Evaluate establishment, breaking, rescue, and unresolved conditions independently with profile-controlled Decimal weights.
4. Preserve breaking evidence when rescue evidence exists.
5. Resolve candidates using profile source rank, hidden-stem rank, and transparency rank. Equal ranks remain explicit unresolved conflicts.
6. Emit deterministic Phase 10 evidence that can be converted into Phase 8 `EvidenceRecord` values.

## Conservative boundaries

- `very_weak` and `very_strong` are prerequisites only; they never produce a final follower-pattern determination.
- Special candidate status never exceeds `conditionally_supported`.
- Five-stem combination evidence produces `hua_qi_candidate` with unresolved conditions; it never produces a final transformation determination.
- Every result retains `prediction_validity = not_evaluated`.

## Determinism and benchmark

The packaged assertion manifest defines a 10 day-stem × 12 month-branch matrix plus targeted special-pattern, transformation, and conflict assertions. The benchmark covers all supported pattern types and verifies canonical hashes, schema boundaries, provenance, condition separation, stable key reordering, special-pattern ceilings, and equal-priority conflict retention.

Expected Phase 10 benchmark acceptance:

- `assertions_total >= 1200`
- `passed == assertions_total`
- `failed == unresolved == 0`
- all schema, provenance, hash, threshold, and conflict-order failure counters are zero

Verified result: `1224/1224` passed with every failure counter at zero.

The complete repository suite also passed with `84` unittest tests (`1` skipped) and `93` pytest tests (`1` skipped, `24` subtests). An isolated wheel installation rebuilt a Phase 7 graph, calculated Phase 9 strength, evaluated Phase 10, and reproduced the source hashes for all three results. The installed Phase 10 benchmark also passed `1224/1224`.

## Compatibility

No files under `spec/` or `knowledge/` are modified. Phase 5–9 public output semantics are unchanged. Phase 10 is exposed through `python -m mingli.phase10_cli` and the optional `mingli-phase10` console script.
