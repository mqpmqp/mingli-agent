# Product Release Hold Decision

## Current decision

```text
ASTRO_ETL_HARDENING_COMPLETE
PRODUCT_RELEASE_HOLD_REMAINS
prediction_validity=not_evaluated
```

## Passed

- ETL safety contract and synthetic dry-run tests.
- Fast regression gate completed locally.
- Real-case contract gate completed locally with synthetic/private-store boundary tests only.
- No Ruff or Pyright regression relative to baseline commit `384e142`.
- Isolated updated build/quality environment has no known audited dependency vulnerabilities.
- Test gates are separated in local commands and CI jobs with timeouts and JUnit artifacts.
- Independent benchmark gate completed: 32 tests and 15 subtests passed in 1522.35 seconds.

## Still blocking release

- No authorized real-case pilot exists; the full consent-to-release evidence chain is unproven on real data.
- No remote branch, Draft PR, remote CI evidence, or independent privacy/time-leakage review exists yet.
- The repository retains historical Ruff/Pyright debt; this branch introduces no delta but does not erase that debt.
- A release artifact must be rebuilt from the final reviewed commit and tied to its source hash.

Only an independent authorization referencing a frozen, reproducible, qualified real-case dataset may clear the hold.
