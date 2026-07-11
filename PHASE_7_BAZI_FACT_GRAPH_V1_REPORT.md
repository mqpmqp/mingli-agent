# Phase 7 Bazi Deterministic Fact Graph V1 Report

## Marker

```text
PHASE_7_BAZI_FACT_GRAPH_V1_COMPLETE
```

This file records the implementation and local verification state for the Phase 7 pull request. GitHub PR number, merge commit, main push CI and post-merge readback are release-time values and are reported in the final delivery response after the PR is merged.

## Baseline

- Baseline main/origin-main: `2cfc080e54f041642539e83046fb2b066f36b981`
- Branch: `agent/phase7-bazi-fact-graph-v1`
- Worktree: new clean worktree under `mingli-agent-phase7-bazi-fact-graph-v1`
- Original P0 worktree: not modified

## Phase 6 Release Readback Fix

`PHASE_6_STATIC_MAPPING_ENGINE_V1_REPORT.md` was updated with the already-completed Phase 6 PR #10 release values:

- Implementation PR: `https://github.com/mqpmqp/mingli-agent/pull/10`
- Implementation commit: `affbd329957badc585305ac762962eda97ec6164`
- Implementation merge commit: `2cfc080e54f041642539e83046fb2b066f36b981`
- Main post-merge CI: run `29151166536`, success

No Phase 6 implementation semantics were changed.

## Implemented Phase 7 Scope

Phase 7 adds a deterministic fact layer in `mingli.phase7`:

- exact luck anchor from birth instant and adjacent `jie`
- DaYun sequence and half-open timeline periods
- LiuNian sequence using explicit LiChun boundaries
- chronological and explicit nominal age snapshots
- profile-gated twelve growth stages
- structural stem and branch relations
- unified immutable Bazi fact graph with deterministic node/edge ordering
- canonical JSON / SHA-256 compatible payloads
- packaged Phase 7 profile and source manifests
- `phase7` CLI commands

The implementation consumes Phase 5 base chart output and Phase 6 derived structure output. It does not modify Phase 5 or Phase 6 public output semantics.

## Profiles

Packaged profile manifest: `phase7-profile-manifest@0.1`

Profiles:

- `luck-direction-profile@0.1`
- `luck-anchor-profile@0.1`
- `dayun-sequence-profile@0.1`
- `liunian-boundary-profile@0.1`
- `age-profile@0.1`
- `twelve-growth-profile@0.1`
- `stem-relation-profile@0.1`
- `branch-relation-profile@0.1`

Each profile records a stable ID, version, convention summary, source IDs, independence groups, reviewed state, applicable inputs, explicit exclusions, unresolved conditions and compatibility version.

## Assertion Matrix

`python -m mingli.cli phase7 benchmark` result:

| Metric | Count |
|---|---:|
| assertions_total | 736 |
| timeline_assertions | 136 |
| growth_assertions | 120 |
| stem_relation_assertions | 100 |
| branch_relation_assertions | 364 |
| graph_assertions | 16 |
| passed | 736 |
| failed | 0 |
| unresolved | 0 |
| schema_failures | 0 |
| provenance_failures | 0 |
| hash_mismatches | 0 |
| interval_gaps | 0 |
| interval_overlaps | 0 |

Coverage includes:

- 10 x 12 twelve-growth matrix
- 10 x 10 stem relation pair matrix
- 12 x 12 branch relation pair matrix
- all 220 three-branch combinations
- 60 JiaZi DaYun forward first-step assertions
- 60 JiaZi DaYun reverse first-step assertions
- forward and reverse luck-direction fixtures
- exact luck-anchor display-age compatibility with Phase 5
- DaYun interval continuity
- LiuNian to DaYun references
- graph node/edge type coverage
- canonical hash stability under JSON key reorder and subprocess/different cwd

## CLI and API

CLI:

```bash
python -m mingli.cli phase7 build --input base_chart.json
python -m mingli.cli phase7 timeline --input base_chart.json
python -m mingli.cli phase7 relations --input derived_chart.json
python -m mingli.cli phase7 validate
python -m mingli.cli phase7 benchmark
python -m mingli.cli phase7 profiles
python -m mingli.cli phase7 schemas
```

Public API:

- `build_bazi_fact_graph(...)`
- `build_luck_timeline(...)`
- `detect_structural_relations(...)`
- `calculate_growth_stages(...)`
- `benchmark_phase7(...)`

## Verification Commands

| Command | Exit | Result |
|---|---:|---|
| `python -c "import mingli; print(mingli.__file__)"` | 0 | local `src/mingli/__init__.py` readback |
| `python -m compileall -q src tests` | 0 | pass |
| `python -m unittest discover -v` | 0 | 61 tests OK, 1 skipped |
| `python -m pytest -q` | 0 | 70 passed, 1 skipped, 13 subtests passed |
| `python -m mingli.cli validate-spec spec` | 0 | pass |
| `python -m mingli.cli validate-rules spec/rules` | 0 | 36 rules, IDs unique |
| `python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl` | 0 | 40/40 golden, 24/24 practical |
| `python -m mingli.cli knowledge-validate knowledge` | 0 | pass |
| `python -m mingli.cli knowledge-inventory knowledge` | 0 | batches 1, benchmarks 62, cases 6, concepts 38, evidence 27, rules 19, sources 4 |
| `python -m mingli.cli chart-validate --strict` | 0 | pass |
| `python -m mingli.cli chart-benchmark --independent-only` | 0 | total 52, independent 52, passed 51, failed 0, unresolved 1 |
| `python -m mingli.cli phase6 validate` | 0 | 352 assertions, 0 issues |
| `python -m mingli.cli phase6 benchmark` | 0 | 352 pass, 0 fail, 0 unresolved |
| `python -m mingli.cli phase7 validate` | 0 | pass |
| `python -m mingli.cli phase7 benchmark` | 0 | 736 pass, 0 fail, 0 unresolved |
| `python -m build` | 0 | sdist and wheel built |
| `git diff --check` | 0 | pass |
| `git diff --name-only HEAD -- spec knowledge` | 0 | empty |

Additional test coverage includes:

- JSON key reorder determinism
- separate subprocess determinism
- different cwd determinism
- packaged profile/source manifest readback
- isolated wheel install and fact graph build
- interval continuity verification
- import source readback
- malformed CLI JSON error path

## Protected Paths

- `spec/`: unchanged
- `knowledge/`: unchanged

## Safety and Claim Boundaries

Phase 7 outputs only deterministic structure facts. It does not output:

- wang/shuai
- geju
- yongshen
- xiji
- auspiciousness or inauspiciousness
- relationship/career/wealth/health interpretation
- event windows
- natural-language reading renderer
- LLM, external API, database, cache or web-service integration

All successful outputs continue to set `prediction_validity=not_evaluated`.

## Known Limits

- The exact luck anchor uses a declared deterministic conversion profile: adjacent `jie` duration divided by three for display years, with exact start instant converted by a 365.2425-day tropical year. Other schools require separate profiles.
- Relation facts only detect structural membership. They never claim transformation, strength, completion quality or auspiciousness.
- Twelve growth outputs are stage facts only; they are not wang/shuai or strength judgements.
- The existing Phase 5 23:00 external-source conflict remains unresolved in the Phase 5 chart benchmark and is not promoted to a Phase 7 pass.

```yaml
spec_modified: false
knowledge_modified: false
phase5_output_modified: false
phase6_output_modified: false
prediction_added: false
original_p0_worktree_modified: false
```
