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

## Verification target

- Phase 14 benchmark: at least 4,300 deterministic assertions.
- Full unittest and pytest regression.
- Phase 14 CLI evaluate, query, validate, benchmark, profiles, schemas and provenance.
- Isolated wheel installation under `python -I`.
- Source/install canonical-hash equality for Phase 12, Phase 13 and Phase 14.
- No changes to `spec/` or `knowledge/`.
