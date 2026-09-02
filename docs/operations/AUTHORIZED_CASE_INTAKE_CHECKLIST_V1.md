# Authorized Case Intake Checklist V1

This checklist is a gate for future, authorized, de-identified real-case intake.
It is not an intake form and must not contain real case data.

## Before Intake

- [ ] Written authorization exists in the controlled off-channel system.
- [ ] The controlled store is outside the checkout and every Git repository.
- [ ] The store is not in an automatically synchronized or public directory unless explicitly encrypted and authorized.
- [ ] Access is least-privilege and access logging is enabled.
- [ ] Backup, restore, withdrawal, and destruction procedures are tested.
- [ ] Reviewer A and reviewer B are independently assigned and separated.
- [ ] Future feedback protocol and due date are recorded off-channel.

## Intake Record

- [ ] Direct identity data is separated from the Case OS data partition.
- [ ] A pseudonymous `person:<sha256>` identifier is generated.
- [ ] Birth data is minimized, confirmed, and scope-limited.
- [ ] Consent and withdrawal support are recorded.
- [ ] The original question and scenario scope are registered before prediction.
- [ ] Reality context available at prediction time is recorded separately.
- [ ] Candidate SHA is exactly `a41f6d6da78124f0eb76918ebfbb1f8a843b2798` or a later explicitly frozen candidate.
- [ ] Input fingerprint is generated and retained.
- [ ] Initial output is stored immutably.
- [ ] Prediction timestamp and freeze timestamp are recorded.

## After Prediction Freeze

- [ ] Future feedback is recorded only after the prediction freeze timestamp.
- [ ] Outcome observations cannot overwrite the prediction snapshot.
- [ ] Prior-event validation is kept temporally separate from future outcomes.
- [ ] A withdrawal request creates a tombstone and does not erase audit evidence.
- [ ] Reviewer assessments retain timestamps, role separation, and disagreement records.
- [ ] Miss, partial, and unverifiable outcomes remain in the archive.
- [ ] No case data is placed in Git, PRs, Issues, chat, or CI artifacts.

## Stop Conditions

Stop and do not import when authorization, de-identification, reviewer separation,
backup, or future-feedback readiness is incomplete. Stop if any real identity,
absolute external path, credential, or case payload would enter this repository.

Release Hold remains `ACTIVE`; this checklist does not grant release, merge, tag,
or commercial-validation authorization.
