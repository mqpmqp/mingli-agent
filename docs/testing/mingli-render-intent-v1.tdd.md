# MingLi RenderIntent v1 implementation record

## Scope

This change adds a rendering-only intent layer and explicit text-confirmed pillar provenance. It does not modify `spec/`, chart calculation, rule packs, thresholds, sources, training data, or Phase 23's existing full-reading renderer.

## Contracts

| Contract | Expected behavior | Evidence |
| --- | --- | --- |
| `full_reading` | Preserve the existing Phase 23 final answer. | `test_full_reading_preserves_existing_yuan_answer` |
| `focused_question` | Render only a supported requested topic from existing Runtime artifacts. | `test_focused_and_follow_up_use_only_the_requested_topic` |
| `follow_up` | Render a supported continuation from existing artifacts, or return the formal supported-scope limitation. | `test_focused_and_follow_up_use_only_the_requested_topic` and `test_unsupported_topic_fails_closed_without_generic_conclusion` |
| `comment` | Produce a short, supported comment from the same artifacts. | `test_selection_rules_are_explicit_and_state_aware` |
| `text_confirmed` | Require text-specific confirmation provenance and reject image-specific fields. | `test_text_confirmed_source_is_explicit_and_isolated_from_image_provenance` |
| `image_confirmed` | Preserve image provenance and reject text confirmation fields. | `test_text_confirmed_source_is_explicit_and_isolated_from_image_provenance` |
| Confirmed-pillar follow-up | Do not synthesize a new reading; return the formal supported-scope result. | `test_confirmed_pillar_follow_up_is_an_official_limited_runtime` |

## TDD and verification record

The RED commit is `9eea412`; implementation and user-facing scenario-label fixes are `65bd3cb` and `678d872`.

Executed on commit `7967d12865db0cb21e09fc3b362134fe20245dbc`:

| Gate | Result |
| --- | --- |
| Focused implementation tests | `20 passed` |
| Fast gate | `401 passed, 1 skipped, 150 deselected, 1 warning, 16 subtests passed` |
| Real-case gate | `112 passed, 440 deselected, 1 warning` |
| Benchmark gate | `38 passed, 514 deselected, 1 warning, 15 subtests passed` |
| Contract freeze | Passed; 78 protected inputs checked, no violations |
| Ruff | Passed |
| `compileall` | Passed |
| Wheel build and isolated import | Passed |
| `git diff --check` | Passed |

The fast gate was re-run after the final code change. The documentation change in this commit is explanatory only.
