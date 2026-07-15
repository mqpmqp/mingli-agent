# Full Test Report

## Test partition

Pytest collection assigns every test to exactly one gate:

| Gate | Collected | Timeout | Purpose |
|---|---:|---:|---|
| `test-fast` | 149 | 300 s | Ordinary unit/integration regression |
| `test-benchmark` | 31 | 3600 s | Deterministic matrices, packaging, wheel, and benchmark checks |
| `test-real-case` | 58 | 600 s | Real-case contracts, privacy, freeze, scoring, and ETL dry-run |
| Total | 238 | — | No overlap and no omission |

## Local results

```text
test-fast:
142 passed, 1 skipped, 9 subtests passed, 89 deselected
elapsed: 228.04 s

test-real-case:
58 passed, 174 deselected
elapsed: 59.99 s

test-benchmark first attempt:
TIMEOUT after 1800 s
approximately 26/31 progress markers emitted; no complete pass result

test-benchmark bounded retry:
PENDING with a 3600 s runner limit and 90-minute CI job limit
```

The Windows skip is `SourceRegistryTests.test_symlinks_are_rejected_including_outside_repository`, skipped because Windows symlink privilege is unavailable. It is not silently counted as a pass.

The benchmark timeout is a release blocker. The runner returns its distinct timeout status and now writes a failure JUnit artifact even when pytest is terminated before producing its own XML.

## CI behavior

`.github/workflows/test.yml` contains independent `fast_tests`, `benchmark_tests`, and `real_case_tests` jobs. Each has:

- an explicit GitHub job timeout;
- an explicit runner subprocess timeout;
- an independent JUnit XML artifact uploaded with `if: always()`.

This prevents a long benchmark from hiding the complete fast-test or real-case result.
