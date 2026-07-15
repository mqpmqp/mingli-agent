# Test Gate TDD Evidence Report

## Journeys

- A developer can run ordinary regression tests without waiting for long deterministic benchmarks.
- A validation operator can run real-case contract tests independently.
- CI receives a deterministic timeout status and JUnit evidence even when a benchmark is terminated.
- Every collected pytest item belongs to exactly one gate.

## RED / GREEN evidence

| Guarantee | RED evidence | GREEN evidence |
|---|---|---|
| Gate classification and subprocess timeout | `3c5affd`: `mingli.test_gates` missing | `70d773b`: 6 gate-contract tests pass |
| Independent CI jobs with timeouts/artifacts | `d5013c2`: workflow lacked `fast_tests` | `6fc0282`: YAML parses and workflow contract passes |
| Runner execution paths reach coverage threshold | Initial stdlib trace: 59% | Final stdlib trace: 96% |
| Timeout still produces JUnit evidence | `e26034d`: expected XML missing | `cb74ced` plus follow-up coverage: 13 gate-runner tests pass; timeout XML contains `errors=1` |

## Collection invariant

Final collection after the runner tests were completed:

```text
test-fast: 149
test-benchmark: 32
test-real-case: 58
total: 239
```

The sum must equal the unfiltered pytest collection, and classification returns one string value per node ID, so the groups are mutually exclusive.

## Long-gate result

The first independent benchmark run timed out after 1800 seconds and proved timeout containment. A bounded retry with a 3600-second limit completed all 32 benchmark tests and 15 subtests in 1522.35 seconds without reducing the matrices. Phase 15 and Phase 16 assertion matrices remain performance hotspots and should stay isolated from fast regression.
