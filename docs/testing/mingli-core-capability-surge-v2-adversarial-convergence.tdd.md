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
