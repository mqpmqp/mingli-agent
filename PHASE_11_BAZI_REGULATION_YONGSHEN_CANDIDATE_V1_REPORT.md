# PHASE_11_BAZI_REGULATION_YONGSHEN_CANDIDATE_V1 Report

## Scope

Phase 11 adds deterministic regulation-need extraction and YongShen candidate ranking on top of Phase 7 Fact Graph, Phase 9 Strength Result, and Phase 10 Pattern Evaluation.

Implemented lenses:

- `strength_balance`
- `seasonal_climate`
- `element_passage`
- `pattern_remedy`

Implemented boundaries:

- Outputs regulation candidates only.
- Keeps five-element candidates separate from stem carriers.
- Preserves per-lens evidence before fusion.
- Converts Phase 11 evidence into Phase 8 `EvidenceRecord`.
- Keeps `prediction_validity = not_evaluated`.
- Does not output final favorable/unfavorable categories, luck-cycle judgement, event prediction, natural-language rendering, LLM calls, external APIs, databases, or caches.

## Files

- `src/mingli/phase11.py`
- `src/mingli/phase11_cli.py`
- `src/mingli/phase11_contracts.py`
- `src/mingli/phase11_engine.py`
- `src/mingli/phase11_profiles.py`
- `src/mingli/phase11_resolution.py`
- `src/mingli/derived/data/phase11_regulation_profiles_v0.1.json`
- `src/mingli/derived/data/phase11_regulation_assertions_v0.1.json`
- `tests/test_phase11_regulation_yongshen_candidate.py`
- `pyproject.toml`

## Benchmark

Phase 11 benchmark result:

- `assertions_total`: 1697
- `passed`: 1697
- `failed`: 0
- `unresolved`: 0
- `schema_failures`: 0
- `provenance_failures`: 0
- `hash_mismatches`: 0
- `threshold_gaps`: 0
- `threshold_overlaps`: 0
- `conflict_order_failures`: 0
- `unsupported_classical_claims`: 0
- `xiji_boundary_failures`: 0

Coverage includes five elements, ten stem carriers, 10 day masters by 12 month branches, strength classifications, ordinary patterns, Jian Lu, Yang Ren, climate cold/heat/dry/damp, passage chains, absent/hidden-only/visible-rooted/visible-unrooted/multiple-rooted availability states, conflicts, and unresolved boundary behavior.

## Verification

Executed successfully:

- `python -c "import mingli; print(mingli.__file__)"` with `PYTHONPATH=src`, confirming import from this checkout.
- `python -m compileall -q src tests`
- `python -m unittest discover -v`
- `python -m pytest -q`
- `python -m mingli.cli validate-spec spec`
- `python -m mingli.cli validate-rules spec/rules`
- `python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl`
- `python -m mingli.cli knowledge-validate knowledge`
- `python -m mingli.cli knowledge-inventory knowledge`
- `python -m mingli.cli chart-validate --strict`
- `python -m mingli.cli chart-benchmark --independent-only`
- `python -m mingli.cli phase6 validate`
- `python -m mingli.cli phase6 benchmark`
- `python -m mingli.cli phase7 validate`
- `python -m mingli.cli phase7 benchmark`
- `python -m mingli.phase8_cli provenance --expected-root .`
- `python -m mingli.phase8_cli benchmark`
- `python -m mingli.phase9_cli provenance --expected-root .`
- `python -m mingli.phase9_cli validate`
- `python -m mingli.phase9_cli benchmark`
- `python -m mingli.phase10_cli provenance --expected-root .`
- `python -m mingli.phase10_cli validate`
- `python -m mingli.phase10_cli benchmark`
- `python -m mingli.phase11_cli provenance --expected-root .`
- `python -m mingli.phase11_cli validate`
- `python -m mingli.phase11_cli benchmark`
- `python -m build`
- `git diff --check`
- `git diff --name-only 7914a5ded40a9b78ea8d40db74fef360fb43a339...HEAD -- spec knowledge`
- Fresh temporary venv wheel install with `python -I`

Wheel readback matched source canonical hashes:

- Phase 7: `sha256:c941d0444bf3de5bccfb0ff1383fe3d0ce019f2d3e6a89a9c1e03b759cf343ea`
- Phase 9: `sha256:0d135033c4e34b448d8518e10bc00294cfe4288f2da7cf6616f86ad554a5198b`
- Phase 10: `sha256:a4bc9617f5cf0811554598ada18694df0a7f15cb3a23103d4fef0a4c81834a7f`
- Phase 11: `sha256:8bc235392f8961d967dde5f475c4b83c07fa7c2584b278d07779f25d2a95ac69`

## Notes

- Bare `python -c "import mingli; print(mingli.__file__)"` in this machine resolves to the original P0 checkout because the ambient Python path is already contaminated. All source verification in this phase explicitly pinned `PYTHONPATH=src`; the wheel readback used `python -I` and imported from temporary `site-packages`.
- No `spec/` files were modified.
- No `knowledge/` files were modified.
