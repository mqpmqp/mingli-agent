# Phase 16-24 Independent Final Audit

## Scope and baseline

Phase 16 was reviewed and merged independently by PR #21 at merge commit `dd21ce80da861944817960b30d34cdc027679008`. This branch starts from that merged `origin/main` and contains Phase 17-24 only. The audit did not modify `spec/` or `knowledge/`, and it did not use the original dirty P0 worktree.

## Independent findings and fixes

- P17 was more than a skeleton, but several real-world eligibility, legal, safety, contact, and root-cause gates were incomplete. Those gates are now explicit and tested.
- P18 evidence fusion now participates in the final status and exposes deterministic missing-source and contradiction penalties. Verified reality evidence remains a scoped hard override; conflicts remain visible.
- P19 calculates deterministic weights only. The repository deliberately does not contain fabricated complete ChengGu verses.
- P20 enforces exactly eight sections and one exact final disclaimer: `仅供文化研究与娱乐参考。`
- P21 rejects concrete-event claims and requires evidence identity, type, source, and verification provenance for each annual record.
- P22 now distinguishes synthetic fixtures from consented external observations. No repository case currently qualifies as a real eligible case, so accuracy claims are forbidden.
- P23 now executes the actual P7-P23 deterministic chain. P16 results are authoritative, P18 fusion affects final statuses, and legacy injected baseline domains are rejected.
- P24 previously risked circular self-verification. It now uses fixed independent expected outputs and does not invoke P16-P23 benchmark helper functions.

## Phase verdicts

| Phase | Technical verdict | Product/evidence boundary |
| --- | --- | --- |
| P16 | PASS, merged and independently gated | Deterministic domain contracts only |
| P17 | PASS | Reality gates do not prove outcomes |
| P18 | PASS | Fusion preserves conflicts and scope |
| P19 | PASS for weights | Full verses blocked on source and authorization |
| P20 | PASS | Fixed renderer does not validate predictions |
| P21 | PASS | Bounded trends; concrete events rejected |
| P22 | PASS for harness | 0 eligible real cases; no accuracy claim |
| P23 | PASS | Complete deterministic runtime chain |
| P24 | PASS for technical RC gate | `technical_rc_only_product_hold` |

## Non-code blockers

1. A complete ChengGu verse corpus needs traceable sources, rights review, and content approval.
2. Product validation needs at least 30 consented, de-identified, externally observed real cases that pass the provenance contract.
3. No scientific, prospective, or external certification of predictive validity exists. `prediction_validity` remains `not_evaluated`.

## Audit conclusion

The code is eligible for a technical release-candidate merge after exact-head PR CI passes. It is not eligible for product release or an accuracy claim.
