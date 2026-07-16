# Dependency Audit Report

## Scope

Audits were separated into the pre-existing project environment and a clean quality-gate environment outside the Git checkout.

## Pre-existing environment

The original `.venv-validation` audit reported seven findings in build/development tooling:

- `pip 24.0`: six reported advisories.
- `setuptools 79.0.1`: one reported advisory.

These packages are not declared runtime dependencies in `[project.dependencies]`, but an RC build environment must not retain them.

## Isolated quality environment

Environment: isolated virtual environment `astro-etl-quality` outside the Git checkout.

- Python: 3.11
- pip: 26.1.2
- setuptools: 83.0.0
- wheel: 0.47.0
- Ruff: 0.15.21
- Pyright: 1.1.411
- pip-audit: 2.10.1

`python -m pip_audit --local` result:

```text
No known vulnerabilities found
```

The editable local package is skipped because `mingli-agent 2.0.0` is not published on PyPI. Its resolved third-party runtime dependencies were installed in the environment and included in the audit.

## Static-quality delta

| Tool | Baseline `384e142` | Current branch | New findings |
|---|---:|---:|---:|
| Ruff | 395 | 395 | 0 |
| Pyright | 354 | 354 | 0 |

The historical findings remain release-quality debt but are not widened by this branch. No automatic bulk fixes were applied.
