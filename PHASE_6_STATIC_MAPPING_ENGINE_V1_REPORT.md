# Phase 6 Static Mapping Engine V1 Report

## Marker

```text
PHASE_6_STATIC_MAPPING_ENGINE_V1_COMPLETE
```

This report is authored on the implementation branch before the implementation PR merge. Fields that are unknowable until GitHub creates the PR merge commit are recorded as pending here and finalized in the release response after post-merge CI.

## PR #9 Closure

- PR: `https://github.com/mqpmqp/mingli-agent/pull/9`
- Original expected head: `ef0b1faada396ef9ab2b19b217e92271120f022a`
- Review fix commit: `5c69636f6cf8be69c818ce8fc961ca68071608da`
- PR CI: run `29150057398`, success
- Merge commit: `3c1c443215bd767f41ab47facff57d8b21896f1d`
- Main post-merge CI: run `29150101856`, success

The PR #9 packaging test was fixed before merge by isolating wheel builds in a copied source tree and clearing inherited Python path variables for venv install probes.

## Implementation Branch

- Branch: `agent/phase6-static-mapping-engine-v1`
- Baseline main/origin-main: `3c1c443215bd767f41ab47facff57d8b21896f1d`
- Worktree: new clean clone under `mingli-agent-phase6-static-mapping-engine-v1`
- Implementation PR: pending at report authoring time
- Implementation merge commit: pending at report authoring time
- Main post-merge HEAD: pending at report authoring time

## Changed Files

- `README.md`
- `pyproject.toml`
- `src/mingli/cli.py`
- `src/mingli/contracts/models.py`
- `src/mingli/derived/__init__.py`
- `src/mingli/derived/static_engine.py`
- `src/mingli/derived/data/__init__.py`
- `src/mingli/derived/data/phase6_capability_manifest_v0.1.json`
- `src/mingli/derived/data/phase6_source_manifest_v0.1.json`
- `tests/test_derived_contracts.py`
- `tests/test_derived_static_engine.py`
- `PHASE_6_STATIC_MAPPING_ENGINE_V1_REPORT.md`

No `spec/` or `knowledge/` files were modified.

## Five Capability Status

All Phase 6 v0.1 static capabilities are implemented and benchmarked:

| Capability | Assertions | Status |
|---|---:|---|
| `visible_stem_ten_gods` | 100 | pass |
| `hidden_stems` | 12 | pass |
| `hidden_stem_ten_gods` | 120 | pass |
| `nayin` | 60 | pass |
| `xunkong` | 60 | pass |

Total independent assertions: 352.

## Source Independence Coverage

Reviewed source groups used by the assertion matrix:

- `classical-yuan-hai-zi-ping`: 292 assertions
- `classical-san-ming-tong-hui`: 120 assertions
- `modern-6tail-lunar`: 352 assertions

Benchmark result:

- pass: 352
- fail: 0
- unresolved: 0
- independence-group violations: 0
- deterministic hash mismatches: 0
- schema failures: 0
- provenance failures: 0

## Mapping Engine Architecture

`mingli.derived.static_engine` adds a deterministic static mapping layer over allowlisted Phase 5 output:

- validates the Phase 5 base result through the existing read-only adapter
- routes only the five approved R1 capabilities
- validates packaged source manifest readiness before mapping
- maps only declared static tables for hidden stems, ten gods, NaYin and XunKong
- preserves field-level provenance through source IDs
- returns immutable `DerivedChartResult` objects
- emits `prediction_validity=not_evaluated`
- rejects unsupported capabilities, unsupported base results, unresolved dependencies and invalid mapping inputs through structured contract errors

No LLM, external API, database, cache, network runtime dependency, interpretation renderer or event prediction was added.

## CLI and API

Python API:

- `derive_static_chart(base_chart, capabilities=None, profile_id="derived-static-r1@0.1", strict=True)`
- `benchmark_static_mappings(path=None)`
- `validate_static_assertions(assertions)`
- `load_static_assertions(path=None)`
- `load_packaged_capability_manifest()`
- `load_packaged_source_manifest()`

CLI:

```bash
python -m mingli.cli phase6 map --input base_chart.json
python -m mingli.cli phase6 validate
python -m mingli.cli phase6 benchmark
python -m mingli.cli phase6 capabilities
python -m mingli.cli phase6 schemas
```

`phase6 map` also accepts stdin when `--input` is omitted. It writes machine-readable JSON to stdout and errors to stderr.

## Canonical JSON and Hash Verification

Tests cover same-process repeatability, JSON key reordering, source manifest ordering, a separate subprocess from a different temporary working directory and wheel-installed execution. All tested paths produce stable canonical JSON/SHA-256 output.

The assertion matrix is deterministically generated from package-owned static mapping tables and source provenance metadata. Each generated assertion stores a canonical digest for its expected mapping result; the benchmark fails if any digest changes.

## Schema and Package Verification

The wheel includes:

- five contract JSON Schemas under `mingli.contracts.schemas`
- packaged Phase 6 capability manifest
- packaged Phase 6 source manifest
- generated Phase 6 static assertion matrix from packaged static source/manifests

An isolated venv installed the wheel with `--no-deps` and read schema/manifest resources, generated and ran the Phase 6 benchmark, and executed one mapping. Result: schema type `object`, decision `PHASE_6_R1_CONSERVATIVE_BOUNDARY_APPROVED`, source manifest `phase6-source-manifest@0.1`, benchmark passed `352`, mapping status `complete`.

## Concurrency Race Fix

The previous wheel packaging test could race when unittest and pytest both invoked `python -m build` in the same source tree, and it could inherit `PYTHONPATH=src` into the isolated venv install probe. The fix:

- copies the source tree into a per-test temporary build root
- excludes `.git`, caches, `build`, `dist` and egg-info
- clears inherited Python path variables from build/install/probe subprocesses
- uses UTF-8 subprocess encoding on Windows

Focused parallel unittest/pytest packaging checks passed after the fix before PR #9 was merged.

## Verification Commands

| Command | Exit | Result |
|---|---:|---|
| `python -m compileall -q src tests` | 0 | pass |
| `python -m unittest discover -v` | 0 | 54 tests OK, 1 skipped |
| `python -m pytest -q` | 0 | 63 passed, 1 skipped, 6 subtests passed |
| `python -m mingli.cli validate-spec spec` | 0 | pass |
| `python -m mingli.cli validate-rules spec/rules` | 0 | 36 rules, IDs unique |
| `python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl` | 0 | 40/40 golden, 24/24 practical |
| `python -m mingli.cli knowledge-validate knowledge` | 0 | pass |
| `python -m mingli.cli knowledge-inventory knowledge` | 0 | batches 1, benchmarks 62, cases 6, concepts 38, evidence 27, rules 19, sources 4 |
| `python -m mingli.cli chart-validate --strict` | 0 | pass |
| `python -m mingli.cli chart-benchmark --independent-only` | 0 | total 52, independent 52, passed 51, failed 0, unresolved 1 |
| `python -m mingli.cli phase6 validate` | 0 | 352 assertions, 0 issues |
| `python -m mingli.cli phase6 benchmark` | 0 | 352 pass, 0 fail, 0 unresolved |
| `python -m mingli.cli phase6 capabilities` | 0 | packaged capability manifest readable |
| `python -m mingli.cli phase6 schemas` | 0 | packaged schema metadata readable |
| `python -m mingli.cli phase6 map --input <utf8-base-json>` | 0 | status `complete` |
| `python -m build` | 0 | sdist and wheel built |
| isolated wheel install/readback | 0 | schema, manifests, benchmark and mapping readable/executable |
| `git diff --check` | 0 | pass |
| `git diff --name-only origin/main...HEAD -- spec knowledge` | 0 | empty |

## Protected Path Diff

`spec/`: unchanged.

`knowledge/`: unchanged.

## Not Implemented

The following remain intentionally excluded from Phase 6 v0.1:

- 大运/流年 timeline
- 起运精确起止时间
- 周岁/虚岁映射
- 十二长生
- 合冲刑害破关系
- 神煞
- 胎元、命宫、身宫、小运
- 旺衰、格局、用神、喜忌
- 吉凶解释、自然语言 renderer、事件窗口或现实结果预测

## Remaining Risks

- Static mapping expected values are represented as packaged assertion data and source provenance metadata; future source disputes must be handled by adding unresolved assertions rather than silently changing expected output.
- Phase 5 `luck.direction` and `start_age_years` remain outside this phase and are not used for Phase 6 v0.1.
- The one existing Phase 5 23:00 external conflict remains unresolved in the Phase 5 chart benchmark and does not count as a Phase 6 pass.

```yaml
spec_modified: false
knowledge_modified: false
phase5_output_modified: false
prediction_added: false
static_mapping_engine_implemented: true
original_p0_worktree_modified: false
```
