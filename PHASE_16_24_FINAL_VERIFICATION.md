# Phase 16-24 Final Verification

## Verified artifact

- Branch: `agent/phase17-24-mingli-agent-v2-release-candidate-v1`
- Baseline: Phase 16 merge commit `dd21ce80da861944817960b30d34cdc027679008`
- Package version: `0.2.0rc1`
- Intended status: `technical_rc_only_product_hold`

## Local commands and results

| Command | Exit | Result |
| --- | ---: | --- |
| `python -m compileall -q src tests` | 0 | Passed |
| `python -m pytest -q` | 0 | 169 passed, 1 skipped, 24 subtests passed |
| `python -m build` | 0 | sdist and wheel built |
| isolated wheel P16-P24 benchmark commands | 0 | 4304/4304 passed, 0 failed, 0 unresolved |
| `git diff --check` | 0 | Passed |

The isolated environment imported `mingli` from its own `site-packages` directory. It did not rely on an existing editable install or the dirty P0 checkout.

## Benchmark breakdown

| Phase | Total | Passed | Failed | Unresolved |
| --- | ---: | ---: | ---: | ---: |
| P16 | 4207 | 4207 | 0 | 0 |
| P17 | 34 | 34 | 0 | 0 |
| P18 | 9 | 9 | 0 | 0 |
| P19 | 12 | 12 | 0 | 0 |
| P20 | 7 | 7 | 0 | 0 |
| P21 | 8 | 8 | 0 | 0 |
| P22 | 8 | 8 | 0 | 0 |
| P23 | 11 | 11 | 0 | 0 |
| P24 | 8 | 8 | 0 | 0 |

P22 reports `real_case_count=0` and `product_accuracy_claim_allowed=false`. P24 reports `release_decision=technical_rc_only_product_hold`.

## Source/wheel equivalence

- P19 digest in both environments: `sha256:fd792f01285b3390068b00fef971cbf103bd4df19534582d2d1a77374efa0c0a`
- P24 canonical hash in both environments: `sha256:ed8191d64b64c53eb8d62219e4dd870417af19473f193e431871f051e360bebb`
- Required package data present: P16 schema; P17 special-scenario rules; P19 weight table; P22 case registry.

## Delivery gates

- PR exact-head CI must pass before merge.
- Main push CI must pass after merge before the annotated RC tag is created.
- Product release remains blocked by content authorization and eligible real-case evidence.
- `prediction_validity=not_evaluated` remains unchanged.

Local verification supports a technical RC only; it does not establish prediction validity or product accuracy.
