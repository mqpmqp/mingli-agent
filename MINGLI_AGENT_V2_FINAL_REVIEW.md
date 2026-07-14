# MingLi Agent V2 Final Independent Review

## Verdict

`PASS_WITH_NON_BLOCKING_NOTES`

The independent review found six release-blocking P1/P2 contract gaps and one P3 clarity gap. All P1/P2 findings were fixed with regression tests. Open P1 findings: 0. Open P2 findings: 0. The remaining notes are product-evidence limitations, not hidden code completion claims.

## Baseline and method

- Reviewed PR source head: `5333acb6f598cd7ddce5e4f215145463f81a490e`.
- Baseline at review start: `origin/main` = `2a299d501d1192c5c65d9c2373eed1bb3de6617d`.
- Review worktree: independent clean worktree on `codex/v2-final-closure-review`.
- GitHub PR #23 was Open, Draft, Mergeable, with successful exact-head CI at preflight.
- GitHub review threads at preflight: 0 conversation comments, 0 reviews, 0 review threads.
- Review approach: contract trace from P16 facts through P24 release assessment, adversarial input tests, source/wheel equivalence, package inventory, and protected-path checks.

## Findings and closure

| Severity | Phase | Finding | Resolution | Status |
| --- | --- | --- | --- | --- |
| P2 | P17 | Career-exam contract merged exam tendency into other layers and exposed only four layers. | Added independent `exam_outlook`; it remains unresolved/low without independent evidence. | closed |
| P1 | P20 | Caller could inject an overall conclusion or arbitrary verse text into the core renderer. | Renderer now derives the overall state and rejects `overall_status`, verse text, and `verse_available!=false`. | closed |
| P2 | P21 | Five-year records had statuses but no explicit domain/year confidence gate. | Added deterministic domain and overall confidence; missing/conflicting evidence is low. | closed |
| P1 | P22 | Excluded unreviewed or non-deidentified records could be hidden by a passing coverage flag; a PII leak did not independently block the accuracy gate. | Review/privacy coverage now sees candidate Gold/Silver failures; accuracy authorization requires both coverages. | closed |
| P1 | P23 | Caller-supplied `overall_status` bypassed the deterministic chain, and the confidence stage stored only statuses. | Reject caller total; propagate effective status and confidence together into P20 and the runtime result. | closed |
| P1 | Package | Distribution metadata was upgraded to 2.0.0 while `mingli.__version__` remained 0.1.0. | Synchronized the runtime version with package metadata and added an executable equality test. | closed |
| P3 | P19 | Gender independence of the weight table was implicit. | Added the versioned `gender_basis=not_used_for_weight_calculation` convention and equality test. | closed |

## Phase verdicts

| Phase | Verdict | Independent conclusion |
| --- | --- | --- |
| P16 | PASS | Complete bounded career/wealth/relationship contracts; no concrete event promise. |
| P17 | PASS | Five career-exam layers and four reunion layers; reality overrides remain layer-scoped. |
| P18 | PASS | Verified reality is a scoped hard override; conflict and missing provenance lower confidence. |
| P19 | PASS | Deterministic integer weights; gender is irrelevant; no verse package. |
| P20 | PASS | Exactly eight sections, one final disclaimer, confidence-gated degraded output, no upstream bypass. |
| P21 | PASS | Anchor ±2 trend only; each domain/year has confidence; concrete events rejected. |
| P22 | PASS (harness) | Unique-person, Gold/Silver, review, privacy, conflict, and claim gates are executable; real data count remains zero. |
| P23 | PASS | Actual P7–P23 artifacts are chained deterministically; caller conclusions are rejected. |
| P24 | PASS (technical gate) | Closure, accuracy, and product authorization remain independent; empty data remains HOLD. |

## Adversarial coverage

The executable tests cover: 10 Gold + 20 Silver closure without accuracy; 30 unique Gold with accuracy; 30 Gold rows for one person; missing and duplicate person IDs; conflicting tiers; 30 Silver; empty registry; closure/accuracy true while product authorization remains false; malformed records/claims; privacy failure; review/adjudication failure; scenario coverage failure; and the same Phase 22/24 scenarios against the isolated installed wheel.

## Protected boundaries

- `spec/` modified: false.
- `knowledge/` modified: false.
- Original P0 worktree modified: false.
- External LLM, network runtime, database, or external chart API added: false.
- Verse text, modern paraphrase, real-case PII, consent records, or accuracy claims added: false.
- `prediction_validity`: `not_evaluated`.

## Non-blocking product notes

- Repository eligible Gold cases: 0; eligible Silver cases: 0.
- Product validation closure is not complete.
- Product accuracy claims are not allowed.
- Product release authorization remains open; V2.0 is a technical release under `PRODUCT_RELEASE_HOLD`.
