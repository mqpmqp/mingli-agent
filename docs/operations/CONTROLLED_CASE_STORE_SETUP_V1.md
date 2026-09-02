# Controlled Case Store Setup V1

This is a preparation template for an authorized operator. It does not create a
store, authorize access, or accept real cases.

## Required Boundary

The controlled store must be:

- outside the source checkout and outside every Git repository;
- outside OneDrive, Dropbox, public shares, and automatically synchronized folders unless explicitly encrypted and authorized;
- inaccessible through chat, Issue, PR, commit, CI artifact, or other public transport;
- restricted to the minimum operator, reviewer, and service identities;
- pseudonymized by `person:<sha256>` case identifiers;
- covered by backup, restore, withdrawal, and destruction procedures;
- logged for access, with reviewer A and reviewer B kept separate;
- unable to overwrite a frozen prediction with later outcome feedback.

## Configuration Record

Complete this record in an authorized off-channel system. Do not commit the
completed record or the actual path to this repository.

```text
controlled_store_path: <absolute path recorded off-channel>
authorization_status: AUTHORIZED | NOT_AUTHORIZED
deidentification_status: VERIFIED | NOT_VERIFIED
reviewer_separation_status: READY | NOT_READY
backup_status: READY | NOT_READY
future_feedback_protocol: READY | NOT_READY
```

The path must be an absolute path at operation time, but it must never be written
into Git, this template, a PR, or a chat transcript. A placeholder such as
`<CONTROLLED_STORE_ROOT>` is the only path form permitted in examples.

## Preflight

The existing CLI enforces the checkout boundary for controlled inputs and
outputs. After the off-channel operator has completed authorization, run the
following with a substituted path only in the local shell:

```powershell
python -m mingli.cli validation case-start --input <CONTROLLED_STORE_ROOT>\start.json --output <CONTROLLED_STORE_ROOT>\case-<id>-frozen.json
python -m mingli.cli validation case-prior --case <CONTROLLED_STORE_ROOT>\case-<id>-frozen.json --evidence <CONTROLLED_STORE_ROOT>\prior-evidence.json --output <CONTROLLED_STORE_ROOT>\case-<id>-prior.json
```

Do not run these commands with real data as part of this candidate freeze.

## Operational Controls

1. Verify authorization and de-identification before intake.
2. Record the minimum birth data and the original question required by the schema.
3. Freeze the initial prediction before future feedback exists.
4. Keep future feedback outside the prediction snapshot and record its arrival time.
5. Assign reviewers independently and preserve both assessments.
6. Test backup, restore, withdrawal, and destruction before import.
7. Stop intake if any readiness field is not `READY` or `AUTHORIZED`.

The Release Hold remains `ACTIVE` throughout this process.
