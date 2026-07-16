# Ziwei Temporal and Combination Rules V2 — TDD Evidence

## Source and boundary

No `*.plan.md` was supplied. The journeys and acceptance criteria were derived from Workstream B. Work was limited to the owned additive v2 module, schemas, uniquely named tests and these reports. Frozen v1 contracts were inspected and left unchanged.

All test charts, overlays and Reality Evidence records are explicitly synthetic contract fixtures. They prove deterministic contract behavior only; they are not real-case evidence and do not establish prediction accuracy.

## User journeys

1. As a caller with a complete compatible Ziwei chart, I can deterministically evaluate structural combinations and receive versioned, hash-stable, privacy-bounded findings.
2. As a caller supplying decade, year and month overlays, I receive bounded month-precision observation windows and never an exact event prediction.
3. As a reviewer, I can inspect career, wealth, relationship, study, family and migration findings across four transformations, star combinations, geometry, life/body and brightness/state rules.
4. As an evidence operator, verified Reality Evidence overrides only the same claim and scope.
5. As a contract owner, unsupported or incompatible inputs fail closed, conflicts demote confidence, and no result changes `prediction_validity=not_evaluated` or an ACTIVE Release Hold.
6. As a coverage reviewer, I can see behavioral proof for canonical trigger, exclusion, priority/conflict and unsupported paths, while mutations cannot falsely count as covered.

## RED checkpoint

Command:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/test_ziwei_temporal_v2.py
```

Observed result: pytest collection failed with `ModuleNotFoundError: No module named 'mingli.ziwei_temporal_v2'`. This was a valid missing-behavior RED: the test module parsed and imported the requested additive API, which did not yet exist.

- RED SHA: `3e19aa9f796c05c31fc670576f1fff9c301c4a44`
- RED commit: `test(ziwei): define temporal combination v2 behavior`

## Behavioral specification and GREEN evidence

| # | Guarantee | Behavioral test | Type | Result |
|---|---|---|---|---|
| 1 | Stable versions, canonical hash, deterministic ordering and no private birth/session values | `test_synthetic_contract_evaluation_is_versioned_deterministic_and_private` | contract/integration | PASS |
| 2 | All requested combination families and six topics are reached through real evaluator calls | `test_all_combination_families_and_six_topics_are_behaviorally_reached` | behavioral | PASS |
| 3 | Decade/year/month windows are finite and month-precision | `test_decade_year_month_overlays_produce_only_bounded_event_windows` | boundary | PASS |
| 4 | Lower priority is suppressed; equal opposite priority is unresolved; both demote confidence | `test_priority_suppression_and_equal_priority_conflict_demote_confidence` | conflict | PASS |
| 5 | Verified Reality Evidence overrides only the exact claim/scope | `test_reality_evidence_hard_override_is_claim_and_scope_specific` | evidence integration | PASS |
| 6 | Degraded, unsupported, incompatible and hash-tampered charts fail closed | `test_unsupported_or_incompatible_charts_fail_closed` | negative/contract | PASS |
| 7 | Unsupported/unbounded overlays and event prediction requests fail closed | `test_unsupported_and_unbounded_overlay_requests_fail_closed` | negative/boundary | PASS |
| 8 | Rule/result schemas, hashes and non-accuracy boundaries remain explicit | `test_rule_pack_and_behavioral_coverage_are_hashed_and_non_accuracy_claims` | schema/contract | PASS |
| 9 | Trigger, exclusion, priority, conflict-policy and unsupported mutations cannot false-pass coverage | `test_false_pass_mutations_cannot_count_a_rule_as_behaviorally_covered` | mutation | PASS (5 variants) |
| 10 | Runtime rejects an invalid pack even when the coverage report safely records failure | `test_invalid_rule_pack_is_rejected_by_runtime_even_if_coverage_reports_failure` | negative/runtime | PASS |

Focused GREEN command and result:

```text
$env:PYTHONPATH='src'; python -m pytest -q tests/test_ziwei_temporal_v2.py
17 passed
```

The GREEN commit subject is `feat(ziwei): add temporal combination rules v2`; its exact SHA is recorded in the final handoff after the commit exists.

## Coverage

Command:

```powershell
$env:PYTHONPATH='src'; python -m coverage erase
$env:PYTHONPATH='src'; python -m coverage run --branch --source=mingli.ziwei_temporal_v2 -m pytest -q tests/test_ziwei_temporal_v2.py
$env:PYTHONPATH='src'; python -m coverage report -m --fail-under=80
```

Observed result: 17 tests passed; `src/mingli/ziwei_temporal_v2.py` reached 81% branch-aware focused coverage and passed the 80% threshold. There are no skipped or disabled tests in the focused file.

## Final verification gates

| Gate | Command | Observed result |
|---|---|---|
| Ruff | `$env:PYTHONPATH='src'; python -m ruff check src/mingli/ziwei_temporal_v2.py tests/test_ziwei_temporal_v2.py` | PASS, all checks passed |
| Compile | `$env:PYTHONPATH='src'; python -m compileall -q src/mingli/ziwei_temporal_v2.py tests/test_ziwei_temporal_v2.py` | PASS |
| Frozen contracts | `$env:PYTHONPATH='src'; python -m mingli.contracts.freeze --root .` | PASS, 78 checked, 0 violations |
| Whitespace | `git diff --check` | PASS |

These gates are rerun after the final documentation edit before the GREEN commit. Exact final outcomes are reported in the handoff and are not inferred from coverage or prediction behavior.

## Known gaps and interpretation

- The rule records are draft traditional paraphrases and a deterministic engineering surface, not validated predictive models.
- Synthetic fixture coverage is intentionally labeled `synthetic_contract_only`; it cannot be cited as real-case or accuracy evidence.
- Event prediction, exact dates, unsupported overlays and incompatible chart versions remain closed.
- Release Hold remains `ACTIVE`; no test or coverage result can change it.
