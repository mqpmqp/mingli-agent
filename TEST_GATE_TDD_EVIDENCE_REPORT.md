# Test Gate TDD Evidence Report

## Journeys

- A developer can run ordinary regression tests without waiting for long deterministic benchmarks.
- A validation operator can run real-case contract tests independently.
- CI receives a deterministic timeout status and JUnit evidence even when a benchmark is terminated.
- Every collected pytest item belongs to exactly one gate.

## RED / GREEN evidence

| Guarantee | RED evidence | GREEN evidence |
|---|---|---|
| Gate classification and subprocess timeout | `3c5affd`: `mingli.test_gates` missing | `70d773b`: gate-contract tests pass |
| Independent CI jobs with timeouts/artifacts | `d5013c2`: workflow lacked `fast_tests` | `6fc0282`: YAML parses and workflow contract passes |
| Runner execution paths reach coverage threshold | Initial stdlib trace: 59% | Final stdlib trace: 96% |
| Timeout still produces JUnit evidence | `e26034d`: expected XML missing | `cb74ced` plus follow-up coverage: timeout XML contains `errors=1` |

## Collection invariant

Final collection after reproducible-delivery tests were added:

```text
test-fast: 162
test-benchmark: 32
test-real-case: 58
total: 252
```

The sum equals the unfiltered pytest collection, and classification returns one gate per node ID, so the groups are mutually exclusive.

## Long-gate result

The first independent benchmark attempt timed out after 1800 seconds and proved timeout containment. The final 3600-second bounded run completed all 32 benchmark tests in 1401.55 seconds without reducing the matrices. Phase 15 and Phase 16 remain performance hotspots and stay isolated from fast regression.
