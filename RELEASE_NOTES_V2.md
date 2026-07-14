# MingLi Agent v2.0.0 Release Notes

## Release class

`v2.0.0` is a deterministic technical release. Product status remains `PRODUCT_RELEASE_HOLD`, `prediction_validity` remains `not_evaluated`, and `product_accuracy_claim_allowed` remains false for the repository's empty private-validation registry.

## Included

- Phase 16 career, wealth, and relationship domain contracts.
- Phase 17 five-layer career-exam and four-layer reunion contracts with scoped reality gates.
- Phase 18 provenance-preserving evidence fusion and verified-reality hard overrides.
- Phase 19 deterministic ChengGu weights without verse text or modern paraphrase.
- Phase 20 fixed Yuan eight-section output with explicit confidence and one final disclaimer.
- Phase 21 bounded anchor-year ±2 trends without concrete event claims.
- Phase 22 validation-closure and Gold-only accuracy gates based on qualified unique people.
- Phase 23 deterministic end-to-end runtime and Phase 24 independent technical/product gate separation.

## Final closure hardening

- Caller-supplied `baseline_domains` and `overall_status` are rejected.
- The core renderer rejects verse text and requires `verse_available=false`.
- Unresolved domain or yearly states cannot be rendered above low confidence.
- Missing review, adjudication, de-identification, or a nonzero PII leak count fails closed.
- Silver cases may help close validation, but never authorize a product accuracy claim.
- Validation closure and product accuracy never imply product release authorization.

## Compatibility notes

- Phase 17 career-exam output adds `exam_outlook`; without independent support it is `unresolved` with low confidence.
- Phase 20 requires `domain_confidence`, and every `five_years` record requires `confidence`.
- Phase 21 adds `confidence` and `domain_confidence` to every yearly result.
- Phase 23 adds `effective_domain_confidence` and rejects `overall_status` input.

## Explicit non-claims

This release does not validate predictive accuracy, does not authorize an accuracy claim, does not include real-case PII, and does not package ChengGu verse text. It uses no external LLM, database, network runtime, or external chart API.
