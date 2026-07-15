# Astro ETL Hardening Report

## Decision

```text
ASTRO_ETL_HARDENING_COMPLETE
PRODUCT_RELEASE_HOLD_REMAINS
```

## Closed risks

- Public visibility is not accepted as consent. Research and benchmark consent must be explicit.
- Retrospective outcomes cannot be transformed into pre-registered scenarios.
- Direct identity fields and source IDs are omitted; stable IDs use HMAC-SHA256 with a salt controlled outside Git.
- Longitude-only correction is named `local_mean_solar_time`; `true_solar_time` remains `false`.
- Rodden rating is not promoted into Gold/Silver validation evidence tier.
- Source JSON, project salt, validation store, and imported cases must remain outside the Git checkout.
- Import reuses privacy scanning, intake validation, canonical hashing, duplicate rejection, atomic batches, and rollback manifests.

## Evidence

- ETL tests: 6 passed.
- ETL module line coverage: 87% using stdlib `trace`.
- Changed Python files: Ruff passes.
- Pyright delta: baseline 354 errors; current 354 errors; no new type errors.
- Local wheel build and wrapper compilation passed.
- Frozen toolkit SHA-256: `681F9467F0568ED64F8C5A5FFEBD2F3D4B033B9A941B4A6A313F0F09C8703233`.
- Final local gate collection: 252 tests with 161 fast passes, 32 benchmark passes, 58 real-case contract passes, and one documented Windows privilege skip.
- Reproducible wheel, sdist, and RC2 candidate hashes were confirmed across independent temporary worktrees.

## Non-claims

This report does not assert real-case accuracy, Gold/Silver eligibility, validation closure, or product release authorization.
