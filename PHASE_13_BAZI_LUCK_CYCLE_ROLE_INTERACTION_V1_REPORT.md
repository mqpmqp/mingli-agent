# PHASE_13_BAZI_LUCK_CYCLE_ROLE_INTERACTION_V1 Report

## Scope

Phase 13 evaluates deterministic structural interactions between the existing Phase 7 DaYun/LiuNian timeline and the Phase 12 five-element XiJi role map.

Implemented outputs:

- per-DaYun stem and branch-hidden role hits
- per-LiuNian stem and branch-hidden role hits
- support, conflict, neutral and unresolved structural scores
- structural states: `aligned`, `mixed`, `opposed`, `neutral`, `unresolved`
- static stem/branch relations to the four natal pillars
- active DaYun/LiuNian combined windows
- Phase 8-convertible evidence

## Boundaries

- Uses the Phase 7 timeline; does not recalculate or replace luck anchors.
- Requires valid Phase 7 and Phase 12 canonical hashes.
- Requires all nested Phase 12 role-assignment digests to remain valid.
- Stem and branch relations remain structural facts; transformation and effect are not inferred.
- `prediction_validity` remains `not_evaluated`.
- Does not output auspiciousness, good/bad fortune, events, career, wealth, relationship, health, or natural-language conclusions.

## Files

- `src/mingli/phase13.py`
- `src/mingli/phase13_cli.py`
- `src/mingli/phase13_contracts.py`
- `src/mingli/derived/data/phase13_luck_cycle_interaction_profiles_v0.1.json`
- `src/mingli/derived/data/phase13_luck_cycle_interaction_assertions_v0.1.json`
- `tests/test_phase13_bazi_luck_cycle_role_interaction.py`
- `pyproject.toml`
- `.github/workflows/test.yml`

## Deterministic policy

1. Validate Phase 7 graph schema, timeline integrity and canonical hash.
2. Validate Phase 12 XiJi result, graph reference, canonical hash and nested assignment digests.
3. Map the period stem to its Phase 12 element role.
4. Map every branch hidden stem to its element role with ordinal-specific weights.
5. Keep support, conflict, neutral and unresolved channels separate.
6. Classify a structural state using reviewed thresholds only.
7. Record static relations to all four natal pillars.
8. Build DaYun/LiuNian overlap windows only when Phase 7 supplies an active DaYun reference.
9. Preserve missing active-DaYun and upstream unresolved conditions explicitly.
10. Refuse all prediction and domain-output requests.

## Benchmark

Phase 13 benchmark result:

- `assertions_total`: 3604
- `passed`: 3604
- `failed`: 0
- `unresolved`: 0
- `schema_failures`: 0
- `provenance_failures`: 0
- `hash_mismatches`: 0
- `timeline_failures`: 0
- `partition_failures`: 0
- `relation_failures`: 0
- `prediction_boundary_failures`: 0

The matrix covers ten day stems by twelve month branches with thirty deterministic checks per chart, plus explicit Phase 7 hash, Phase 12 hash, nested assignment-digest, and blocked-prediction checks.

## Verification

The final Core Runtime Verification workflow executes successfully:

- `python -m compileall src tests`
- `python -m unittest discover -v`
- `python -m pytest -q`
- existing spec, rule, static benchmark, knowledge, chart, import and rollback gates
- `python -m mingli.phase12_cli validate`
- `python -m mingli.phase12_cli benchmark`
- `python -m mingli.phase13_cli validate`
- `python -m mingli.phase13_cli benchmark`
- `python -m build`
- fresh temporary virtual-environment installation from the generated wheel
- installed-wheel Phase 12 and Phase 13 validation and benchmarks under `python -I`
- source/install canonical-hash equality for Phase 12 and Phase 13
- `git diff --check`
- unchanged `spec/` and `knowledge/` gates

All successful outputs retain `prediction_validity = not_evaluated`; no auspiciousness, good/bad fortune, event, domain, or renderer surface is introduced.
