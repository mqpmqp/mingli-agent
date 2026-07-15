# Draft PR: Harden Astro ETL Intake and Reproducible Validation Gates

## Status

Draft only. Do not merge or clear the product release hold.

## Summary

- fail closed unless research and benchmark consent are explicit;
- reject retrospective events as pre-registered claims;
- use salted HMAC-SHA256 pseudonymous IDs;
- label longitude correction as local mean solar time, not true solar time;
- keep source data, salt, validation stores, and imported cases outside Git;
- separate fast, benchmark, and real-case contract gates in local commands and CI;
- produce deterministic wheel, sdist, and toolkit candidate artifacts with manifests.

## Local verification

```text
fast:       161 passed, 1 skipped, 90 deselected (171.18 s)
benchmark:   32 passed, 220 deselected (1401.55 s)
real-case:   58 passed, 194 deselected (47.44 s)
Ruff delta:     0 (395 baseline, 395 branch)
Pyright delta:  0 (354 baseline, 354 branch)
pip-audit:      no known vulnerabilities in the isolated environment
privacy scan:   passed
```

The skip is the documented Windows symlink-privilege case. No test timeout or skip is counted as a pass.

## Required reports

- `ASTRO_ETL_HARDENING_REPORT.md`
- `REAL_CASE_PILOT_REPORT.md`
- `FULL_TEST_REPORT.md`
- `DEPENDENCY_AUDIT_REPORT.md`
- `PRODUCT_RELEASE_HOLD_DECISION.md`
- `REPRODUCIBLE_DELIVERY_REPORT.md`
- `TEST_GATE_TDD_EVIDENCE_REPORT.md`

## Reviewer checklist

- [ ] Confirm no raw case data, consent records, stable source IDs, salt, or secrets entered Git history.
- [ ] Confirm known outcomes cannot become pre-registered claims.
- [ ] Confirm Rodden rating does not grant Gold/Silver evidence status.
- [ ] Confirm local mean solar time is not described as true solar time.
- [ ] Confirm test-gate partition is exhaustive and mutually exclusive.
- [ ] Confirm timeout exits nonzero and still creates JUnit evidence.
- [ ] Rebuild wheel, sdist, and toolkit from the recorded source commit and compare hashes.
- [ ] Obtain an independent privacy and time-leakage review.

## Remaining blockers

- No authorized 10-20-person real-case pilot exists.
- No consent-to-release chain has run end to end on real data.
- No remote branch, Draft PR, or remote CI evidence exists.
- No independent reviewer has approved privacy, time-leakage, or case-tier handling.

```text
ASTRO_ETL_HARDENING_COMPLETE
PRODUCT_RELEASE_HOLD_REMAINS
```
