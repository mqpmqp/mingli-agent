# Phase 16-24 Benchmark Report

This report records the measured local verification evidence for the V2.0 release-candidate branch.

## Independent gate

P24 uses fixed expected-output checks and does not invoke P16-P23 benchmark helpers. It checks domain partitions, special-scenario hard gates, reality override precedence, the 1990-03-15 ChengGu sample, the fixed eight sections and disclaimer, five-year event rejection, synthetic/real case separation, and the complete P23 stage chain.

## Product evidence status

- Eligible real cases: 0.
- Product accuracy claim: forbidden.
- Verified complete ChengGu verse set: unavailable.
- Prediction validity: `not_evaluated`.

## Measured local results

- Full source suite: `169 passed, 1 skipped, 24 subtests passed`; exit code 0.
- Isolated wheel P16-P24: `4304/4304` assertions passed; `failed=0`; `unresolved=0`; exit code 0.
- Per-phase wheel totals: P16 4207, P17 34, P18 9, P19 12, P20 7, P21 8, P22 8, P23 11, P24 8.
- P22 eligible real cases: 0; product accuracy claims remain forbidden.
- P24 decision: `technical_rc_only_product_hold`.
- P19 source/wheel digest: `sha256:fd792f01285b3390068b00fef971cbf103bd4df19534582d2d1a77374efa0c0a`.
- P24 source/wheel canonical hash: `sha256:ed8191d64b64c53eb8d62219e4dd870417af19473f193e431871f051e360bebb`.
- The isolated import originated from the temporary wheel virtual environment, not a checkout or editable install.
- The wheel contains the P16 schema and the P17, P19, and P22 JSON resources.

## Required final evidence

The delivery report must include exact commands, exit codes, test totals, P16-P24 benchmark totals, wheel installation origin, resource presence, canonical hash comparison, PR CI, and post-merge main CI. Local success does not substitute for either GitHub gate.
