# PHASE_12_BAZI_XIJI_ROLE_CLASSIFICATION_V1 Report

## Scope

Phase 12 adds deterministic five-element XiJi role classification on top of the Phase 11 regulation candidate result.

Implemented roles:

- `yongshen`
- `xishen`
- `jishen`
- `choushen`
- `xianshen`
- `unresolved`

Implemented boundaries:

- Consumes and verifies the complete Phase 11 canonical result.
- Requires nested Phase 11 candidate digests to remain valid.
- Selects at most one YongShen element; semantic top-score ties remain unresolved.
- Derives XiShen, JiShen, ChouShen and XianShen through reviewed score, contradiction, excess-risk and five-element relationship rules.
- Keeps five-element role assignments separate from ten stem carriers.
- Stem carriers inherit the element role while Yin/Yang differentiation remains `not_evaluated`.
- Emits Phase 8-convertible evidence.
- Keeps `prediction_validity = not_evaluated`.
- Does not evaluate luck cycles, annual favorable elements, events, career, wealth, relationship, health, or natural-language conclusions.

## Files

- `src/mingli/phase12.py`
- `src/mingli/phase12_cli.py`
- `src/mingli/phase12_contracts.py`
- `src/mingli/derived/data/phase12_xiji_role_profiles_v0.1.json`
- `src/mingli/derived/data/phase12_xiji_role_assertions_v0.1.json`
- `tests/test_phase12_bazi_xiji_role_classification.py`
- `pyproject.toml`
- `.github/workflows/test.yml`

## Deterministic policy

1. Validate Phase 11 schema, prediction boundary, canonical hash and candidate digests.
2. Retain upstream unresolved facts.
3. Select a unique eligible top regulation candidate as YongShen.
4. Refuse identifier-based semantic tie-breaking.
5. Derive direct JiShen from contradiction and excess-risk thresholds.
6. Derive XiShen through generation of YongShen or control of JiShen.
7. Derive ChouShen through harm to Yong/Xi or support of Ji.
8. Assign all remaining elements as XianShen.
9. Partition all five elements into exactly one role.
10. Preserve all ten stem identities without claiming Yin/Yang equivalence.

## Benchmark

Phase 12 benchmark result:

- `assertions_total`: 2883
- `passed`: 2883
- `failed`: 0
- `unresolved`: 0
- `schema_failures`: 0
- `provenance_failures`: 0
- `hash_mismatches`: 0
- `role_partition_failures`: 0
- `role_collision_failures`: 0
- `carrier_failures`: 0
- `prediction_boundary_failures`: 0

The matrix covers ten day stems by twelve month branches with twenty-four deterministic checks per chart, plus explicit outer-hash, nested-candidate-digest, and blocked-prediction checks.

## Verification

The Core Runtime Verification workflow executes:

- `python -m compileall src tests`
- `python -m unittest discover -v`
- `python -m pytest -q`
- all existing spec, rule, static benchmark, knowledge, chart, import and rollback gates
- `python -m mingli.phase12_cli validate`
- `python -m mingli.phase12_cli benchmark`
- `python -m build`
- fresh temporary virtual-environment installation from the generated wheel
- installed-wheel Phase 12 validation and benchmark with `python -I`
- source/install canonical-hash equality check
- `git diff --check`
- unchanged `spec/` and `knowledge/` gates

All successful Phase 12 results retain `prediction_validity = not_evaluated`; no luck-cycle, annual, event, domain, or renderer prediction surface is introduced.
