# Protected retrospective audit write API

## Scope

`POST /admin/retrospective` writes one validated `RealCaseIntake` into the
operator-managed validation store. It is an audit/feedback intake record only;
it is not an MCP tool and never reports prediction accuracy or product revenue.

The product-runtime training path uses the same operator pattern:
`MINGLI_TRAINING_STORE=D:\\MingLiTrainingStore` (or an equivalent absolute path
on the host). With explicit training consent, `/admin/training/analyze` captures
the case and frozen analysis automatically; `/admin/training/feedback` appends
later feedback and checks its case/run association.

## Authorization

The route fails closed unless both environment variables are configured:

- `MINGLI_RETROSPECTIVE_AUDIT_TOKEN`: an operator-provisioned secret.
- `MINGLI_VALIDATION_STORE`: an absolute path to the Git-external validation store.

Send the token as `Authorization: Bearer <token>`. The service compares it with
constant-time comparison and does not log the header or request body. Missing or
invalid authorization returns `401`; a missing store configuration returns
`503`.

## Request contract

```json
{
  "source_ref": "authorized:operator-reference",
  "intake": {
    "person_case_id": "person:<pseudonymous-id>",
    "birth_input": {},
    "consent": {},
    "case_metadata": {},
    "scenarios": []
  }
}
```

`intake` is validated by the existing `validation_intake.validate_intake` path
and must contain confirmed, redacted/pseudonymous data, granted research and
benchmark consent, withdrawal support, provenance, and at least one scenario
registered before prediction. Direct PII is rejected. The complete field
template is `validation/templates/real_case_intake.template.json`; populated
real records must stay outside Git.

## Operator blockers

- Provision `MINGLI_RETROSPECTIVE_AUDIT_TOKEN` through the deployment secret
  mechanism; never commit or print it.
- Provision `MINGLI_VALIDATION_STORE` outside Git with restricted ownership.
- Provision `MINGLI_TRAINING_STORE` outside Git with restricted ownership; the
  configured path must not be the repository or a repository child.
- Obtain and independently review the second redacted intake before sending it.
- This change does not deploy, configure DNS/Caddy, expose the route publicly,
  or create a product-release authorization.
