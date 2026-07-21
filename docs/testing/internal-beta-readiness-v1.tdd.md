# Internal Beta Readiness V1 TDD Evidence

## Scope

The work reuses Case OS V2 and Phase 16. It adds controlled read-only case audit operations and hardens the existing evaluator cache; the default evaluator bound is eight entries so a benchmark does not retain the entire unique-input matrix. No real case data, accuracy metric, Release Hold override, external service, or new dependency is introduced.

## RED

Command actually run before production edits:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/test_fixture_cache_contract.py tests/test_real_case_cli.py
```

Observed result: collection failed with `ImportError: cannot import name 'clear_phase16_evaluation_cache' from 'mingli.phase16'`. The new cache-isolation contract referenced a missing target API, so this was an intended missing-behavior RED.

## GREEN

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/test_fixture_cache_contract.py tests/test_real_case_cli.py tests/test_real_case_learning_v2.py tests/test_real_case_validation_os.py tests/test_release_hold_attack_v1.py
```

Observed result: `109 passed in 23.16s`.

| Guarantee | Test |
| --- | --- |
| Phase 16 cache returns isolated results, is bounded, excludes failed evaluations, and remains deterministic under concurrent access | `tests/test_fixture_cache_contract.py` |
| Frozen output/version inspection, case classification statistics, anonymized review-pack export, and permanent Hold status are available through the external-store CLI | `test_case_os_cli_exposes_read_only_internal_beta_audit_operations` |
| Consent, anonymization, prediction freeze, append-only feedback/revisions, withdrawal, and Hold rejection remain covered by Case OS V2 regression tests | `tests/test_real_case_learning_v2.py`, `tests/test_real_case_validation_os.py`, `tests/test_release_hold_attack_v1.py` |

## Boundaries

The review pack remains off-Git and is for human review only. `case-summary` reports classifications, never accuracy. Verification level is derived from frozen evidence and manual review; no command automatically creates a `verified` result, permits training, or clears the commercial release hold.
