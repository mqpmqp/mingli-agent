# Real Case Pilot Report

## Status

```text
NOT_STARTED_NO_AUTHORIZED_CASES
QUALIFIED_REAL_CASES=0
PRODUCT_RELEASE_HOLD_REMAINS
```

No real person data, completed consent record, or project salt was supplied for this work. The repository policy forbids manufacturing, committing, or substituting public-biography data for authorized cases.

## Required pilot evidence

The first controlled pilot should contain 10-20 explicitly consented participants, held outside Git. Each participant must retain:

- consent version, scope, and timestamp;
- source provenance and birth-input confirmation;
- HMAC-pseudonymous `person_case_id`;
- at least 3-5 claims frozen before outcome visibility;
- prediction, rule-set, knowledge, input, and software versions;
- independent outcome collection timestamp and evidence provenance;
- reviewer separation, adjudication, exclusions, withdrawal, and modification audit records.

## End-to-end acceptance path

```text
consent
-> controlled intake
-> pseudonymization
-> scenario registration
-> prediction generation
-> claim freeze
-> independent outcome registration
-> blind review and adjudication
-> scoring
-> dataset freeze
-> benchmark aggregation
-> independent release decision
```

Synthetic tests prove contract behavior only. They do not satisfy this pilot or authorize accuracy claims.
