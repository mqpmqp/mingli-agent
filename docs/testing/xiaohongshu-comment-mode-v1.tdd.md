# Xiaohongshu Comment Mode V1 TDD Evidence

## Problem

Existing Phase 20 and Phase 23 output is intentionally an eight-section runtime contract. Comment Mode needs a separate, explicit, bounded output contract without changing either default path.

## RED

Command:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/test_comment_renderer.py
```

Observed result: collection failed with `ModuleNotFoundError: No module named 'mingli.comment_renderer'`.

## Minimal implementation

- Added versioned request/result schemas.
- Added `render_comment` with confirmed/unconfirmed/high-only fail-closed paths.
- Added `mingli comment-render --input <json>`.
- Used `len(rendered_text)` as the Unicode character count, including the one final disclaimer.
- Bound the canonical hash to both the rendered result and validated request digest.

## GREEN

Command:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q tests/test_comment_renderer.py --basetemp C:\Users\Administrator\.codex\tmp\mingli-comment-mode
```

Observed result: `21 passed`.

| Guarantee | Test coverage |
| --- | --- |
| Strict request/result contracts and fixed Comment Mode settings | schema and invalid-setting tests |
| Unconfirmed image chart emits no claims | unconfirmed fail-closed test |
| Confirmed output selects only ordered high-confidence claims | high-only selection test |
| 80/120 bounds include one final disclaimer | character-budget tests |
| Forbidden promises, contact/payment content, and Yuan structure are rejected | forbidden-content tests |
| Result hashes are deterministic and request-sensitive | determinism test |
| CLI, Phase 20, and Phase 23 isolation | CLI and regression tests |

## Final validation

- `python -m pytest -q tests/test_comment_renderer.py tests/test_phase20_renderer.py tests/test_phase23_runtime.py tests/test_contract_freeze_v2.py tests/test_derived_contracts.py tests/test_real_case_cli.py tests/test_release_hold_attack_v1.py --basetemp <external>`: completed without failures.
- `python -m pytest -q tests/test_comment_renderer.py tests/test_derived_contracts.py --basetemp <external>`: `31 passed in 25.65s` after updating the existing wheel schema-count contract from 43 to 45 and asserting both Comment Mode schemas are packaged.
- `test-fast --timeout-seconds 300 --junitxml <external>/test-fast-final.junit.xml -- -q --basetemp <external>`: exit `0`; `401 passed, 1 skipped, 150 deselected in 213.76s`.
- `python -m pytest -q --junitxml <external>/full-pytest.junit.xml --basetemp <external>`: exit `0`; `551 passed, 1 skipped in 1574.05s`.
- `test-real-case --timeout-seconds 600 --junitxml <external>/test-real-case.junit.xml -- -q --basetemp <external>`: exit `0`; `112 passed, 440 deselected in 26.02s`.
- `python -m ruff check src/mingli/comment_renderer.py src/mingli/cli.py tests/test_comment_renderer.py tests/test_derived_contracts.py`: exit `0`.
- `python -m mingli.contracts.freeze --root <repo>`: exit `0`; 78 frozen contracts checked with no violations.
- `python -m compileall src tests`: exit `0`.
- `python -m build`: exit `0`; the wheel and sdist contain `mingli/comment_renderer.py`, `comment_render_request.schema.json`, and `comment_render_result.schema.json`.

The 900-second `test-benchmark` run timed out through the repository gate and wrote a timeout JUnit result. It has no manual interruption, OOM, or process-kill evidence. This blocks final engineering completion, push, and Draft PR creation until the benchmark gate passes within its required budget.

## Boundaries

No Xiaohongshu API, automated posting, payment integration, real customer data, new prediction algorithm, Release Hold override, or accuracy claim is implemented.
