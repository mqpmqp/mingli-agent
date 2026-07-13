# PHASE_14_BAZI_TEMPORAL_TREND_EVIDENCE_V1 Report

## Scope

Phase 14 converts the Phase 13 DaYun/LiuNian structural interaction result into deterministic temporal tendency evidence.

Implemented outputs:

- per-DaYun temporal trend records
- per-LiuNian temporal trend records
- per-combined-window temporal trend records
- normalized support, conflict and neutral ratios
- bounded net balance and intensity values
- tendency labels: `support_tendency`, `conflict_tendency`, `mixed_tendency`, `neutral_tendency`, `unresolved`
- explicit `high`, `medium`, and `low` confidence gates
- verified reality evidence hard override without deleting structural evidence
- conflicting verified reality evidence retained as unresolved
- trend-transition records
- deterministic year and chronological-age indexes and queries
- Phase 8-convertible evidence

## Boundaries

- Consumes the existing Phase 7 timeline and Phase 13 interaction result.
- Does not recalculate the luck anchor, DaYun sequence, or LiuNian boundaries.
- Requires valid Phase 7 and Phase 13 canonical hashes.
- Requires all nested Phase 13 period, window, and evidence digests to remain valid.
- High confidence is allowed only for the scope of consistent verified reality evidence.
- Unverified reality evidence cannot create high confidence.
- Reality hard override changes the final tendency label but does not erase structural support or conflict evidence.
- `prediction_validity` remains `not_evaluated`.
- Does not output auspiciousness, good/bad fortune, events, career, wealth, relationship, health, or natural-language conclusions.

## Files

- `src/mingli/phase14.py`
- `src/mingli/phase14_cli.py`
- `src/mingli/phase14_contracts.py`
- `src/mingli/derived/data/phase14_temporal_trend_profiles_v0.1.json`
- `src/mingli/derived/data/phase14_temporal_trend_assertions_v0.1.json`
- `tests/test_phase14_bazi_temporal_trend_evidence.py`
- `pyproject.toml`
- `.github/workflows/test.yml`

## Deterministic policy

1. Validate Phase 7 schema, timeline and canonical hash.
2. Validate Phase 13 schema, graph reference, top-level hash, and nested digests.
3. Preserve support, conflict, neutral and unresolved channels independently.
4. Normalize scores without binary floating-point public output.
5. Derive bounded net balance and intensity.
6. Apply reviewed tendency thresholds.
7. Cap structural-only confidence at medium.
8. Apply a hard override only for consistent verified reality evidence.
9. Preserve contradictory verified reality evidence as unresolved.
10. Build ordered transitions and deterministic year/age indexes.
11. Refuse all prediction, domain-conclusion and renderer requests.

## Benchmark

Phase 14 benchmark result:

- `assertions_total`: 4332
- `passed`: 4332
- `failed`: 0
- `unresolved`: 0
- `schema_failures`: 0
- `provenance_failures`: 0
- `hash_mismatches`: 0
- `partition_failures`: 0
- `query_failures`: 0
- `transition_failures`: 0
- `reality_override_failures`: 0
- `prediction_boundary_failures`: 0

The matrix covers ten day stems by twelve month branches with thirty-six deterministic checks per chart, plus verified-reality override, conflicting-reality, unverified-reality, year query, age query, top-level hash, nested-digest and blocked-prediction checks.

## Verification

The successful Core Runtime Verification workflow executes:

- `python -m compileall src tests`
- `python -m unittest discover -v`
- `python -m pytest -q`
- all existing spec, rule, static benchmark, knowledge, chart, pilot import and rollback gates
- Phase 12, Phase 13 and Phase 14 profile validation and complete benchmarks
- `python -m build`
- fresh temporary virtual-environment installation from the generated wheel
- installed-wheel Phase 12, Phase 13 and Phase 14 validation and benchmarks under `python -I`
- source/install canonical-hash equality for Phase 12, Phase 13 and Phase 14
- `git diff --check`
- unchanged `spec/` and `knowledge/` gates

All successful outputs retain `prediction_validity = not_evaluated`; no auspiciousness, good/bad fortune, event, domain, or renderer surface is introduced.
