# MINGLI Core Capability Surge V2 adversarial convergence TDD evidence

## Scope

This cycle closes four findings from the algorithm/time-boundary adversarial review:

1. Initial prediction snapshots accepted unknown future-reality metadata.
2. Hash-valid temporal partition manifests did not prove semantic assignment or reproducible corpus provenance.
3. Reality Evidence accepted open or nested contradictory boundary metadata.
4. The Bazi V2 result digest did not bind all public boundary metadata.

All fixtures remain explicitly synthetic contract fixtures. They are not accuracy evidence and cannot support product claims.

## RED evidence

- Checkpoint: `fe98fea`.
- Command: `$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_learning_v2.py tests/test_bazi_expert_v2.py -q`.
- Result: collection failed because `verify_temporal_partition_manifest` did not exist.
- Interpretation: this was the intended missing semantic-verification capability, not an environment, dependency, or syntax failure.

## GREEN evidence

- Checkpoint: `a854415`.
- Focused command: `$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_learning_v2.py tests/test_bazi_expert_v2.py -q`.
- Focused result: `41 passed`.
- Contract regression command: `$env:PYTHONPATH='src'; python -m pytest tests/test_contract_freeze_v2.py tests/test_derived_contracts.py -q --basetemp <writable-external-temp>`.
- Contract regression result: `16 passed`.
- Focused branch coverage: `real_case_learning_v2.py` 82%, `bazi_expert_v2.py` 84%, combined 83%.
- Ruff, compileall, and `git diff --check`: PASS.
- Frozen-contract verifier: `ok=true`, `checked_count=78`, `violations=[]`.

## Guarantees

| Guarantee | Test evidence |
| --- | --- |
| Initial prediction and nested structured-claim objects use exact V2 field sets; unknown future-reality metadata fails closed at runtime and schema validation. | `test_prediction_snapshot_contract_rejects_unknown_future_reality_fields`, `test_prediction_snapshot_schema_is_closed_to_unknown_metadata` |
| Reality Evidence accepts only exact scalar claim/scope/window/direction boundary fields. | `test_reality_evidence_contract_rejects_open_or_nested_boundary_metadata` |
| Temporal manifests bind base assignments, forced assignments, case/withdrawal dependency hashes, and a reproducible corpus hash. | `test_partition_manifest_records_reproducible_base_and_forced_assignments` |
| A hash-valid manifest still fails for train/test overlap, inconsistent forced assignment, or corpus/dependency tampering. | `test_hash_valid_partition_manifest_rejects_semantic_and_provenance_tampering` |
| The Bazi V2 digest binds `schema_version`, `method_id`, `calculation_version`, `prediction_validity`, `release_hold`, and `accuracy_claim_allowed`. | `test_canonical_hash_binds_all_public_boundary_metadata` |

## Boundaries

- No real cases were accessed or created.
- No release, tag, package upload, or Release Hold change occurred.
- `prediction_validity=not_evaluated`, Release Hold `ACTIVE`, and accuracy/product claims remain disabled.

## Theme 1 Santa convergence round 2

- Dual-review result before the fix: FAIL / FAIL.
- RED checkpoint: `a569bda`.
- RED command: `$env:PYTHONPATH='src'; python -m pytest tests/test_real_case_learning_v2.py -q`.
- RED result: `7 failed, 27 passed`; the failures reproduced hash-valid legacy-frozen snapshot injection, missing additive V2 schemas, semantic partition reassignment, and stale case/manifest acceptance.
- GREEN checkpoint: `7487e86`.
- Same Real Case target after the fix: `34 passed`.
- Four V2 focused suites: `70 passed`.
- Contract/packaging regression: `16 passed`.
- Focused Real Case branch coverage: 80%.
- Frozen-contract verifier: `ok=true`, `checked_count=78`, `violations=[]`.

The fix deliberately leaves the frozen legacy prediction/evidence freezers unchanged. The additive V2 layer now rejects their open payloads when they enter a V2 case, supplies closed V2 prediction/evidence schemas, validates nested evidence entries and dependency binding, recomputes partition assignment from per-case temporal inputs, and binds recommendation eligibility to the current case hash and temporal input record.

## Theme 1 Santa convergence round 3

- Fresh dual-review result before the fix: FAIL / FAIL.
- RED checkpoint: `012f5c1`.
- RED focused result: `5 failed`; counterexamples covered missing Ziwei parents, prior observation before window, hash-valid prediction validity mutation, hash-valid evidence direction divergence, and injected prior temporal divergence.
- GREEN checkpoint: `7f4afd7`.
- Same counterexample target: `5 passed`.
- Four V2 focused suites: `75 passed`.
- Modified Real Case/Ziwei branch coverage: 81% each, 81% combined.
- Ruff, compileall, diff check, and frozen-contract verifier: PASS.

New guarantees: year/month overlays require an explicit decade parent and month overlays require an explicit year parent; prior observation cannot precede its frozen window; injected V2 predictions preserve `not_evaluated` and invisible-reality boundaries; verified frozen evidence direction equals the recorded Reality hard-override direction.

## Observation-time semantic correction

- Rejected RED checkpoint: `30b0c2f` proposed treating `observed_at` as the event occurrence instant and therefore rejecting observations after `event_window.end`.
- Full regression disproved that interpretation: the established temporal-partition contract intentionally permits an outcome to be observed or collected after its event window, then uses event end, observation time, and collection availability together to assign train/test.
- Correct invariant: the frozen `event_window` bounds the claimed event period; `observed_at` is when the outcome becomes observable. It must not precede the window start, but it may follow the window end. `collected_at` must not precede observation.
- Correction evidence: the four V2 focused suites returned to `75 passed`; the invalid upper-bound tests and uncommitted implementation were removed without rewriting history.

## Theme 1 unique-parent convergence

- Fresh dual-review result before the fix: FAIL / PASS.
- RED checkpoint: `87d58a6`; overlapping decade parents and duplicate year parents were accepted for the same child chain.
- GREEN checkpoint: `d6bc69c`.
- Parent containment target: `3 passed`.
- Four V2 focused suites: `76 passed`.
- Ziwei V2 branch coverage: 81%.
- Rule: each child year must be contained by exactly one supplied decade, and each month must be contained by exactly one supplied year; ambiguous parents fail closed.

## Theme 1 dedup-contract convergence

- Fresh dual-review result before the fix: FAIL / FAIL.
- RED checkpoint: `7a396ff`; manifest declared a standalone `event_window` dedup key that the identity graph did not and should not apply across unrelated people.
- GREEN checkpoint: `0057490`.
- Correct dedup identity keys: `person_case_id`, `prediction_id`, `derived_fingerprint`, `near_duplicate_fingerprint`. The derived fingerprint already binds person, prediction, chart/question hashes, and claim windows.
- Different people sharing a common event period remain independently partitionable; near-duplicate or identity-linked components still use test-priority union.
- Four V2 focused suites: `76 passed`; Real Case branch coverage 81%; contract/packaging regression `16 passed`; frozen contracts 78/78.

## Theme 1 evidence-availability and manifest-summary convergence

- Fresh dual-review result before the fix: FAIL / FAIL.
- RED checkpoint: `7de0ebd`.
- RED target: Bazi temporal/domain/prior evidence availability, Ziwei direct evidence availability, the unified capability boundary, and a hash-valid resealed partition-summary forgery.
- RED result: the focused counterexample run produced `7 failed, 3 passed`; a tightened Bazi target independently produced `3 failed`. Failures were caused by the missing `evaluation_at` contract, the missing Ziwei argument, the unified input rejecting the cutoff field, and `verify_temporal_partition_manifest` accepting the forged summary.
- GREEN checkpoint: `cfde91e`.
- Four V2 focused suites: `86 passed`.
- Explicit branch-coverage gate: `--cov-branch --cov-fail-under=80` passed at 82.20% total. Module results were Bazi 84%, capability runtime 83%, Real Case 81%, shared Reality Evidence temporal validator 82%, and Ziwei 82%.
- Ruff and `git diff --check`: PASS.

New guarantees: every direct Bazi/Ziwei Reality Evidence record declares a closed event window plus observation and collection availability; an explicit `evaluation_at` cutoff is mandatory whenever direct evidence is supplied; observation may follow event-window end but cannot precede its start; collection cannot precede observation; evidence unavailable at the cutoff fails closed. The standalone temporal partition verifier now parses declared event windows and recomputes their maximum end instead of trusting a hash-valid summary field.

## Theme 2 semantic-coverage convergence

- Fresh rule-content/false-pass dual review: FAIL / FAIL.
- RED checkpoint: `09d70ba`.
- RED result: `3 failed`; coordinated rewrites of `trigger`, `canonical_trigger`, synthetic fixture tokens, and hashes could report a rule covered, and a resealed one-rule subset could report the versioned ruleset complete.
- GREEN checkpoint: `930f8ab`.
- Ziwei focused result: `27 passed`.
- Explicit Ziwei branch coverage: 81.54% with `--cov-branch --cov-fail-under=80`.
- Ruff and `git diff --check`: PASS.

New guarantees: a rule carrying the fixed V2 content version must match the built-in semantic rule hash for its rule ID, and a runtime rule pack must contain the exact complete versioned rule-ID set. Behavioral coverage therefore fails for coordinated trigger/fixture/hash rewrites and for resealed subsets; conflict suppression/demotion remains tested directly at the shared resolver boundary.

## Theme 2 independent-manifest convergence

- Fresh dual-review result before the fix: FAIL / PASS.
- RED checkpoint: `1f23a74`; a source-level semantic rewrite could still rederive the expected hashes from the same active `_RULE_TEMPLATES` under the unchanged content version.
- RED target: `test_source_template_rewrite_cannot_rederive_the_frozen_semantic_contract` failed because the coordinated rewrite reported `covered=true`.
- GREEN checkpoint: `14fd9b1`.
- Ziwei focused result: `28 passed`.
- Explicit Ziwei plus manifest branch coverage: 81% with `--cov-branch --cov-fail-under=80`.
- Ruff and `git diff --check`: PASS.

The fixed content version now resolves against literal rule IDs and semantic hashes in an independent frozen manifest. Executable rule templates cannot regenerate or replace that trust anchor at import time; a source-template rewrite therefore fails both behavioral coverage and runtime validation unless the content version and independently reviewed manifest are intentionally advanced together.

## Theme 3 privacy, withdrawal, and operator-boundary convergence

- Fresh leakage/privacy/Reality Override dual review before the fix: FAIL / FAIL.
- RED checkpoint: `91a5909`.
- RED target: hash-valid consent denial, PII injection, accuracy/synthetic relabelling, operator recommendation application, forged withdrawal tombstones, missing dependency invalidation, and simultaneous active/withdrawn partition input.
- RED result: `11 failed`; every counterexample reached an unsafe downstream path or left the original case active.
- GREEN checkpoint: `b9071d4`.
- Real Case focused result: `50 passed`.
- Four V2 focused suites: `101 passed`.
- Explicit Real Case branch coverage: 81% with `--cov-branch --cov-fail-under=80`.
- Ruff and `git diff --check`: PASS.

New guarantees: every downstream V2 case use revalidates the closed case schema, canonical intake, explicit consent projection, PII-safe payload projection, synthetic provenance, frozen snapshot dependencies, case identity/fingerprint, and operator-only review records. Withdrawal tombstones are schema- and time-validated; when the matching case is present, person/synthetic/dependency bindings must match exactly and the active case is removed from every partition and dependency map. The standalone manifest verifier also rejects any hash-valid manifest that lists the same case as both active and withdrawn.

## Theme 3 trust-proof and conflicting-Reality convergence

- Fresh dual review after the first privacy fix: FAIL / FAIL.
- RED checkpoint: `bf435cb`; counterexamples covered PII hidden behind a forged `*_sha` field in an open frozen snapshot, opposite verified future evidence for one claim/scope, and a schema-valid standalone tombstone with arbitrary references.
- RED result: `3 failed`.
- GREEN checkpoint: `48e42c0`.
- Real Case focused result: `53 passed`.
- Explicit Real Case branch coverage: 81% with `--cov-branch --cov-fail-under=80`.
- Ruff and `git diff --check`: PASS.

Only values that actually satisfy the canonical digest, source-SHA, or pseudonymous-person formats are excluded from downstream PII pattern scanning; a field name alone cannot hide PII. Opposite verified future outcomes for the same claim and scope now fail closed pending operator reconciliation. A standalone withdrawal tombstone is accepted only when its canonical hash appears in an explicit trusted withdrawal registry; tombstones supplied with their original case may instead prove trust through exact person, synthetic, time, and invalidated-dependency bindings.
