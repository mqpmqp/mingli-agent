# PHASE_15_BAZI_TENGOD_DOMAIN_JUDGEMENT_V1 Report

## Scope

Phase 15 adds a deterministic dynamic TenGod theme and bounded domain-judgement candidate layer on top of the Phase 7 Fact Graph, Phase 13 timing-role interactions, and Phase 14 temporal trend evidence.

Implemented domains:

- `career`
- `wealth`
- `relationship`
- `education`
- `exam`
- `startup`
- `migration`

Implemented outputs:

- natal visible and hidden TenGod context scores
- exact dynamic TenGod identity for every DaYun/LiuNian timing hit
- same/opposite-polarity preservation
- per-domain theme activation contributions
- per-domain support, conflict, neutral, and unresolved channels
- bounded domain judgement labels
- top active TenGod codes and theme codes
- scoped verified-reality hard override
- cross-domain conflict records
- year, chronological-age, target, and domain query indexes
- Phase 8-convertible evidence

## Boundaries

- Consumes existing Phase 7, Phase 13, and Phase 14 results.
- Does not recalculate the chart, luck anchor, DaYun sequence, or LiuNian boundaries.
- Requires valid top-level hashes and nested Phase 13/14 digests.
- Domain outputs are `candidate_only`.
- Structural-only confidence is capped at `medium`.
- `high` confidence is permitted only for the exact target/domain covered by consistent verified reality evidence.
- Conflicting verified reality evidence remains `unresolved`.
- TenGod theme activation does not assert concrete events.
- `prediction_validity` remains `not_evaluated`.
- Does not output promotion, dismissal, profit, loss, marriage, reunion, exam admission, health events, auspiciousness, or natural-language destiny conclusions.

## Files

- `src/mingli/phase15.py`
- `src/mingli/phase15_cli.py`
- `src/mingli/phase15_contracts.py`
- `src/mingli/derived/data/phase15_tengod_domain_profiles_v0.1.json`
- `src/mingli/derived/data/phase15_tengod_domain_assertions_v0.1.json`
- `tests/test_phase15_bazi_tengod_domain_judgement.py`
- `pyproject.toml`
- `.github/workflows/test.yml`

## Deterministic policy

1. Validate Phase 7 graph schema and canonical hash.
2. Validate Phase 13 schema, graph reference, top-level hash, and nested timing-hit digests.
3. Validate Phase 14 schema, Phase 13 reference, top-level hash, and nested trend/evidence digests.
4. Derive natal visible and hidden TenGod context from reviewed static mappings.
5. Preserve exact TenGod code, label, family, polarity relation, source symbol, XiJi role, and timing direction.
6. Apply profile-driven domain weights and bounded theme codes.
7. Keep support, conflict, neutral, and unresolved channels separate.
8. Combine TenGod domain activation with Phase 14 temporal context without deleting either source.
9. Cap structural-only confidence at medium.
10. Apply hard override only to the exact domain and target covered by consistent verified reality evidence.
11. Preserve conflicting verified reality as unresolved.
12. Record cross-domain conflicts rather than flattening them into a single conclusion.
13. Refuse concrete event and renderer requests.

## Benchmark

Phase 15 benchmark result:

- `assertions_total`: 7575
- `passed`: 7575
- `failed`: 0
- `unresolved`: 0
- `schema_failures`: 0
- `provenance_failures`: 0
- `hash_mismatches`: 0
- `ten_god_mapping_failures`: 0
- `domain_partition_failures`: 0
- `query_failures`: 0
- `reality_override_failures`: 0
- `claim_boundary_failures`: 0
- `prediction_boundary_failures`: 0

The matrix covers ten day stems by twelve month branches with sixty-three deterministic checks per chart, plus verified-reality override, conflicting-reality, unverified-reality, year/domain query, age/domain query, target query, Phase 7/13/14 top-level hashes, nested Phase 13/14 digests, and blocked concrete-event requests.

## Verification

The successful Core Runtime Verification workflow executes:

- `python -m compileall src tests`
- `python -m unittest discover -v`
- `python -m pytest -q`
- all existing spec, rule, static benchmark, knowledge, chart, pilot import, and rollback gates
- Phase 12, Phase 13, Phase 14, and Phase 15 profile validation and complete benchmarks
- `python -m build`
- fresh temporary virtual-environment installation from the generated wheel
- installed-wheel Phase 12 through Phase 15 validation and benchmarks under `python -I`
- source/install canonical-hash equality for Phase 12 through Phase 15
- `git diff --check`
- unchanged `spec/` and `knowledge/` gates

All successful outputs retain `prediction_validity = not_evaluated` and `domain_judgement_validity = candidate_only`; no concrete event, auspiciousness, or natural-language destiny renderer surface is introduced.
