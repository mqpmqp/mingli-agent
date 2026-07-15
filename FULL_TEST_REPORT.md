# Full Test Report

## Test partition

Pytest collection assigns every test to exactly one gate:

| Gate | Collected | Timeout | Purpose |
|---|---:|---:|---|
| `test-fast` | 162 | 300 s | Ordinary unit/integration regression |
| `test-benchmark` | 32 | 3600 s | Deterministic matrices, packaging, wheel, and benchmark checks |
| `test-real-case` | 58 | 600 s | Real-case contracts, privacy, freeze, scoring, and ETL dry-run |
| Total | 252 | - | No overlap and no omission |

## Final local results

```text
test-fast:
161 passed, 1 skipped, 90 deselected
elapsed: 171.18 s

test-real-case:
58 passed, 194 deselected
elapsed: 47.44 s

test-benchmark:
32 passed, 220 deselected
elapsed: 1401.55 s (23:21)
runner limit: 3600 s; CI job limit: 90 minutes
```

The Windows skip is `SourceRegistryTests.test_symlinks_are_rejected_including_outside_repository`, skipped because Windows symlink privilege is unavailable. It is not silently counted as a pass.

An earlier benchmark attempt timed out after 1800 seconds. That attempt produced no pass claim and led to explicit timeout JUnit evidence. The final bounded run completed every benchmark item without reducing the assertion matrices.

## CI behavior

`.github/workflows/test.yml` contains independent `fast_tests`, `benchmark_tests`, and `real_case_tests` jobs. Each has:

- an explicit GitHub job timeout;
- an explicit runner subprocess timeout;
- an independent JUnit XML artifact uploaded with `if: always()`.

This prevents a long benchmark from hiding the complete fast-test or real-case result.
