# Real Case Validation Candidate Freeze V1

This record freezes the existing engineering candidate for a later, authorized,
off-channel real-case validation intake. It is not a release record, a commercial
validation result, or an authorization to merge or publish.

## Candidate Identity

- Repository: `mqpmqp/mingli-agent`
- Branch: `codex/release-hold-attack-v1`
- PR: [#36](https://github.com/mqpmqp/mingli-agent/pull/36), OPEN, Draft
- Base SHA: `b03af9f1a7ee5199f64cdd627dd47f348c761d6e`
- Frozen candidate SHA: `a41f6d6da78124f0eb76918ebfbb1f8a843b2798`
- Freeze timestamp: `2026-07-18T08:53:50Z`
- Release Hold: `ACTIVE`
- CI run: [29636958835](https://github.com/mqpmqp/mingli-agent/actions/runs/29636958835)
  - `fast_tests`: SUCCESS
  - `real_case_tests`: SUCCESS
  - `benchmark_tests`: SUCCESS

The freeze metadata is committed after the parent candidate. The parent SHA is
the frozen subject; the metadata commit is deliberately a separate, non-candidate
commit and must not be confused with the frozen candidate SHA.

## Scope

Relative to `origin/main`, the candidate contains:

- 16 commits
- 17 changed files
- 1,745 additions and 6 deletions
- Case OS V2 controlled checkout-root and off-checkout storage boundaries
- V2 outcome contract versioning and package-surface verification
- validation CLI intake, freeze, transition, adjudication, review, and Hold reassessment guards
- controlled Real Case Learning OS V2 and Release Hold protocol tests

Explicitly excluded:

- real cases, real identity data, consent records, salts, or external-store contents
- production release or publication
- Release Hold removal
- post-outcome feedback at freeze time
- commercial validity or accuracy claims
- merge authorization, tags, or GitHub Releases

## Frozen Components

The exact Git blob bytes of the relevant components are recorded in
`src/mingli/derived/data/real_case_candidate_freeze_v1.json`:

- Python package version: `2.0.0`
- Runtime entry points and build metadata: `pyproject.toml`
- Runtime, Case OS, training, validation, contract, and Hold code listed in the manifest
- All schema files under `src/mingli/contracts/schemas/`
- Frozen contract manifest
- `release_hold_attack_v1_protocol.json`
- Relevant tests and `.github/workflows/test.yml`

No real-case store, cache, build output, wheel, `.git` content, or CI artifact is
part of the manifest.

## Validation Evidence

Verified before this freeze:

- `test-fast --timeout-seconds 300 --junitxml artifacts/test-fast.xml -- -q`: 371 passed, 1 skipped, 150 deselected
- `test-real-case --timeout-seconds 600 --junitxml artifacts/test-real-case.xml -- -q`: 112 passed, 410 deselected
- `test-benchmark --timeout-seconds 3600 --junitxml artifacts/test-benchmark.xml -- -q`: 38 passed, 484 deselected
- `python -m compileall -q src/mingli`: passed
- `git diff --check`: passed
- contract freeze, package schema count, isolated wheel, and privacy/package-boundary checks: reported from the successful CI run above; not locally re-run in this freeze task

No real-case data was imported. Synthetic fixtures remain contract-only and are
not evidence of prediction accuracy.

## Mutation Policy

After this freeze:

- prediction rules, schemas, algorithms, renderers, and scoring rules must not be changed in place because of future feedback;
- any repair must create a new candidate version;
- the original prediction snapshot is immutable;
- outcome observation must be later than prediction freeze;
- reviewer assessments retain timestamps and identity separation;
- misses, partials, and unverifiable outcomes are retained and cannot be deleted or rewritten.

## Release Boundary

- Release Hold: `ACTIVE`
- Candidate freeze is not a release.
- Candidate freeze is not commercial validation.
- Candidate freeze is not merge authorization.
- Candidate freeze is not tag or Release authorization.

## External Intake Readiness

Use `docs/operations/CONTROLLED_CASE_STORE_SETUP_V1.md` and
`docs/operations/AUTHORIZED_CASE_INTAKE_CHECKLIST_V1.md` before any future
authorized intake. The store path is intentionally not supplied or created by
this change. All readiness fields must be independently established before
import; no assertion is made here that an external store is authorized or exists.
