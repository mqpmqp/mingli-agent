# MingLi Agent V2 Release Candidate Verification

## Candidate

- Package version: `2.0.0`.
- Release class: `technical_release_product_hold`.
- Prediction validity: `not_evaluated`.
- Product release: `PRODUCT_RELEASE_HOLD`.
- Product accuracy claim allowed: false.

## Independent local verification

| Command | Exit | Result |
| --- | ---: | --- |
| `python -m pytest -q` | 0 | 190 passed, 1 skipped, 24 subtests passed in 1425.99s |
| `python -m unittest discover -v` | 0 | Ran 181 tests in 1348.160s; OK (skipped=1) |
| `python -m compileall -q src tests scripts` | 0 | Passed |
| `python -m mingli.cli validate-spec spec` | 0 | Passed |
| `python -m mingli.cli validate-rules spec/rules` | 0 | 36 rule IDs unique; passed |
| `python -m mingli.cli benchmark-static spec/evaluation/golden_cases_v0.2.jsonl` | 0 | Golden 40/40; practical structure 24/24 |
| `python -m mingli.cli knowledge-validate knowledge` | 0 | Passed |
| `python -m mingli.cli knowledge-inventory knowledge` | 0 | batches=1, benchmarks=62, cases=6, concepts=38, evidence=27, rules=19, sources=4 |
| `python -m mingli.cli chart-validate --strict` | 0 | Passed |
| `python -m mingli.cli chart-benchmark --independent-only` | 0 | total=52, independent=52, passed=51, failed=0, unresolved=1, source_agreement=1.0 |
| P12–P24 source CLI matrix | 0 | 22,704/22,704 assertions passed, failed=0, unresolved=0 |
| `python -m build` | 0 | Built 2.0.0 sdist and wheel |
| P12–P24 isolated-wheel CLI matrix | 0 | 22,704/22,704 assertions passed, failed=0, unresolved=0 |
| installed P22 adversarial tests | 0 | Ran 15 tests; OK |
| installed P24 adversarial tests | 0 | Ran 8 tests; OK |
| source/wheel canonical hash comparison | 0 | P12, P13, P14, P15, P16, P19 table, and P24 all match |
| wheel package-data inventory | 0 | 24 files, 23 JSON parsed, `package_data_no_verse=true` |
| isolated-wheel `pip check` | 0 | No broken requirements found |
| isolated-wheel `pip-audit` after toolchain update | 0 | No known vulnerabilities found; local package skipped because it is not on PyPI |
| `git diff --check` | 0 | Passed |
| protected-path checks | 0 | `spec/` unchanged; `knowledge/` unchanged |

The single skip is the repository's existing Windows symlink-privilege check. It is not a changed runtime path. The chart benchmark's single unresolved record is an intentionally recorded external-source conflict; it is not counted as PASS and has `failed=0`.

The first `pip-audit` attempt failed before auditing because its own `pip-api` decoded a Chinese installation path incorrectly. With `PYTHONUTF8=1`, it then identified vulnerable bootstrap `pip 24.0` and `setuptools 79.0.1` in the temporary wheel venv. After upgrading that temporary toolchain to pip 26.1.2 and setuptools 83.0.0, the audit completed with no known vulnerabilities. Project runtime requirements were not weakened or changed.

No repository lint or static type checker is configured in `pyproject.toml` or GitHub Actions; no unconfigured lint/type result is claimed.

## Benchmark breakdown (source and installed wheel)

| Phase | Total | Passed | Failed | Unresolved |
| --- | ---: | ---: | ---: | ---: |
| P12 | 2,883 | 2,883 | 0 | 0 |
| P13 | 3,604 | 3,604 | 0 | 0 |
| P14 | 4,332 | 4,332 | 0 | 0 |
| P15 | 7,575 | 7,575 | 0 | 0 |
| P16 | 4,207 | 4,207 | 0 | 0 |
| P17 | 34 | 34 | 0 | 0 |
| P18 | 9 | 9 | 0 | 0 |
| P19 | 12 | 12 | 0 | 0 |
| P20 | 7 | 7 | 0 | 0 |
| P21 | 10 | 10 | 0 | 0 |
| P22 | 9 | 9 | 0 | 0 |
| P23 | 11 | 11 | 0 | 0 |
| P24 | 11 | 11 | 0 | 0 |

## Canonical hashes

| Artifact | Source and installed wheel |
| --- | --- |
| P12 | `sha256:9137c895ad7a6d54a422281be260828d1f59309d99a5695c96c4e7f788eea448` |
| P13 | `sha256:ef1c28aa5a53ccb557e9471a9e06e3f310310b01e8ce8c599254776bede5c6e2` |
| P14 | `sha256:8cea47d15811a188d447d1a27fd7f3196bf0394f8b796d32abe77d40a076b76c` |
| P15 | `sha256:9b19b6f63c549305ed2411fdaf16c23795dd3d43ae116fb4401e35b26be08d39` |
| P16 | `sha256:d3a9f3dd15f51d24d2fa801a8f04928cd01557645117604c471d691331647683` |
| P19 table | `sha256:fd792f01285b3390068b00fef971cbf103bd4df19534582d2d1a77374efa0c0a` |
| P24 | `sha256:68899d259329c3bce8e4012bcca47c91f59399dbfd6a455e70ab57903d960626` |

## Release gates

- Independent review: `PASS_WITH_NON_BLOCKING_NOTES`.
- Open P1 findings: 0.
- Open P2 findings: 0.
- Technical release candidate: local gates pass; pending exact-head cloud CI and post-merge verification.
- Product release: HOLD.

## Remaining external delivery gates

- Commit and push the reviewed patch to PR #23.
- Confirm exact-head PR CI, mark Ready, and merge.
- Re-run post-merge validation from a new clean main worktree and confirm main CI.
- Create and push annotated `v2.0.0`, then publish the GitHub Release with wheel, sdist, source archives, checksums, and release manifest.
