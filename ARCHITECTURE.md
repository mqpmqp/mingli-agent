# MingLi Agent V2.0 Architecture

## Runtime pipeline

`run_mingli_agent` executes one deterministic, versioned pipeline:

```text
Intake Validation
→ Scenario Router
→ Deterministic Chart
→ Fact Graph
→ Strength / Pattern / Regulation / XiJi
→ Luck Interactions / Temporal Trends
→ Domain Rules / Domain Contracts
→ Reality Context / Evidence Fusion
→ Confidence Gate
→ ChengGu Weight
→ Five-Year Bounded Trends
→ Yuan Eight-Section Renderer
→ Final Answer
```

Every material artifact carries a canonical SHA-256 and `prediction_validity=not_evaluated`. P16 is the authoritative source of career, wealth, and relationship baseline states. P18 reality evidence can override only the same `claim_id + scope`; opposing evidence remains in provenance. P21 accepts trends only and rejects concrete event fields.

The P23 confidence gate carries both controlled status and confidence for every domain. P21 does the same for each year and each year-domain. P20 derives the overall status from those upstream domains, rejects caller-supplied overall conclusions, and refuses unresolved output with anything above low confidence.

## Trust boundaries

- `spec/` and `knowledge/` are protected source baselines and are not changed by V2.0 work.
- Unverified ChengGu verses are unavailable rather than synthesized.
- The core renderer rejects verse text even when a caller labels it verified; an optional verse pack is outside V2.0.
- Synthetic cases test contracts only; they never enter real-case metrics.
- A real case requires consent, de-identification, an authorized source, a consent record, external-observation provenance, and a valid observation date.
- No runtime LLM, network API, database, or external chart service is used.

## Compatibility

Phase-specific APIs remain available. The P23 V2 contract intentionally rejects legacy `baseline_domains` and caller-supplied `overall_status`, because either would bypass the P7–P18 chain. P17 career-exam consumers must accept the added `exam_outlook` layer. P20 consumers must provide `domain_confidence` and confidence on every five-year row. Consumers should pass birth data, anchor year, reality facts, and auditable evidence instead.
