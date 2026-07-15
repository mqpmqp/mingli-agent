# Full Test Report

## Test partition

Pytest collection assigns every test to exactly one gate:

| Gate | Collected | Timeout | Purpose |
|---|---:|---:|---|
| `test-fast` | 149 | 300 s | Ordinary unit/integration regression |
| `test-benchmark` | 32 | 3600 s | Deterministic matrices, packaging, wheel, and benchmark checks |
| `test-real-case` | 58 | 600 s | Real-case contracts, privacy, freeze, scoring, and ETL dry-run |
| Total | 239 | — | No overlap and no omission |

## Local results

```text
test-fast:
148 passed, 1 skipped, 9 subtests passed
elapsed: 213.82 s

test-real-case:
58 passed, 181 deselected
elapsed: 49.51 s

test-benchmark first attempt:
TIMEOUT after 1800 s
approximately 26/31 progress markers emitted; no complete pass result

test-benchmark bounded retry:
32 passed, 15 subtests passed, 207 deselected
elapsed: 1522.35 s (25:22)
runner limit: 3600 s; CI job limit: 90 minutes
```

The Windows skip is `SourceRegistryTests.test_symlinks_are_rejected_including_outside_repository`, skipped because Windows symlink privilege is unavailable. It is not silently counted as a pass.

The first benchmark timeout proved containment. The bounded retry completed without reducing the assertion matrices. The runner writes a failure JUnit artifact if a future run times out before pytest produces its own XML.

## CI behavior

`.github/workflows/test.yml` contains independent `fast_tests`, `benchmark_tests`, and `real_case_tests` jobs. Each has:

- an explicit GitHub job timeout;
- an explicit runner subprocess timeout;
- an independent JUnit XML artifact uploaded with `if: always()`.

This prevents a long benchmark from hiding the complete fast-test or real-case result.
