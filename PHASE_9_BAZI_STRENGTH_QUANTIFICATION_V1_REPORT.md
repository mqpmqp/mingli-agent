# Phase 9 Bazi Strength Quantification V1 Report

This report records the implementation and local verification state for `PHASE_9_BAZI_STRENGTH_QUANTIFICATION_V1`.

## Baseline

- Remote baseline main: `b48657d3d4f305b7dd19bb84740a28e21c105938`
- Branch: `agent/phase9-bazi-strength-quantification-v1`
- Worktree: new clean Phase 9 worktree under `mingli-agent-phase9-bazi-strength-quantification-v1`
- Original P0 worktree: not modified

## Scope

Phase 9 adds a deterministic five-element and day-master strength quantification layer on top of the Phase 7 Fact Graph and Phase 8 Evidence contracts.

Implemented:

- versioned strength profile manifest
- Decimal/string based scoring and ratio outputs
- seasonal/month-order contribution
- visible stem contribution
- hidden stem contribution
- root contribution
- same-type and different-type support/opposition summary
- classification bands: `very_weak`, `weak`, `balanced`, `strong`, `very_strong`, `unresolved`
- structured evidence records convertible to Phase 8 `EvidenceRecord`
- deterministic canonical hashes
- independent `mingli.phase9_cli` entrypoint
- assertion matrix benchmark
- isolated wheel readback coverage

Not implemented by design:

- GeJu
- climate adjustment
- YongShen / XiJi
- auspiciousness or inauspiciousness
- event prediction
- natural-language renderer
- LLM, external chart APIs, database, cache or network runtime dependencies

## Profile

Packaged profile manifest: `phase9-strength-profile-manifest@0.1`

Profiles:

- `strength-quantification-r1@0.1`

The profile explicitly records:

- month-order, visible stem, hidden stem and root weights
- classification thresholds
- same-type and different-type definitions
- toggles excluding structural relations, combination transformation, xunkong, twelve growth, climate adjustment and follower-pattern final judgement from score mutation
- source IDs and independence groups
- explicit exclusions and unresolved conditions

## Assertion Matrix

Current benchmark output:

| Metric | Value |
| --- | ---: |
| assertions_total | 1115 |
| profile_assertions | 10 |
| element_assertions | 315 |
| seasonal_assertions | 48 |
| contribution_assertions | 722 |
| classification_assertions | 10 |
| deterministic_assertions | 6 |
| blocked_assertions | 4 |
| passed | 1115 |
| failed | 0 |
| unresolved | 0 |
| schema_failures | 0 |
| provenance_failures | 0 |
| hash_mismatches | 0 |
| threshold_gaps | 0 |
| threshold_overlaps | 0 |

Coverage includes:

- 10 day masters
- five elements
- same-type and different-type mapping
- 12 month branches
- visible stems
- hidden stems
- root contribution levels
- classification threshold boundaries
- blocked inputs
- JSON key reorder determinism
- subprocess and different-cwd checks through tests
- isolated wheel install/readback through tests

## CLI

Independent entrypoint:

```bash
python -m mingli.phase9_cli calculate --graph fact_graph.json
python -m mingli.phase9_cli validate
python -m mingli.phase9_cli benchmark
python -m mingli.phase9_cli profiles
python -m mingli.phase9_cli schemas
python -m mingli.phase9_cli provenance --expected-root .
```

Installed console script:

```bash
mingli-phase9 benchmark
```

## Safety Boundaries

Phase 9 returns quantified structure facts and evidence only. It does not claim predictive validity.

All successful outputs retain:

```yaml
prediction_validity: not_evaluated
```

Blocked or rejected conditions include:

- missing Fact Graph nodes or edges
- missing four pillars
- missing day master
- incomplete hidden-stem structure
- non-reviewed or unsupported profile
- unsupported school-specific profile request
- input `prediction_validity` not equal to `not_evaluated`
- requested combination transformation, climate adjustment or follower-pattern final judgement

## Protected Paths

- `spec/`: unchanged
- `knowledge/`: unchanged

## Known Limits

- V1 uses one reviewed deterministic profile. Other school formulas require separate profiles.
- Structural relations, xunkong and twelve growth stages are retained as context boundaries but do not mutate strength scores.
- Follower-pattern output is limited to `candidate_not_evaluated` boundary semantics through warnings; no final follower-pattern judgement is made.
- Phase 9 evidence is deterministic evidence input, not a complete interpretation or renderer output.

```yaml
spec_modified: false
knowledge_modified: false
prediction_added: false
original_p0_worktree_modified: false
```
