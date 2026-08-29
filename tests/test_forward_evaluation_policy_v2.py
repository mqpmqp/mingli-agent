from __future__ import annotations

import pytest

from mingli.forward_evaluation import (
    EVALUATION_RESULTS,
    EvaluationError,
    ForwardTestRecord,
    settle_forward_test,
)


def record(**overrides: object) -> ForwardTestRecord:
    value: dict[str, object] = {
        "test_id": "forward:test:1",
        "prediction_id": "prediction:test:1",
        "rule_ids": ("domain:career:reality-first",),
        "frozen_at": "2026-08-29T00:00:00+00:00",
        "due_at": "2026-10-01T00:00:00+00:00",
        "input_valid": True,
        "prediction_valid": True,
    }
    value.update(overrides)
    return ForwardTestRecord(**value)  # type: ignore[arg-type]


def test_evaluation_taxonomy_is_exact_and_versioned() -> None:
    assert EVALUATION_RESULTS == (
        "exact_hit",
        "partial_hit",
        "miss",
        "timing_error",
        "category_error",
        "unmet_condition",
        "bad_input",
        "no_feedback",
        "invalid_prediction",
    )


def test_forward_test_cannot_settle_before_due_at() -> None:
    with pytest.raises(EvaluationError, match="FORWARD_TEST_NOT_MATURE"):
        settle_forward_test(
            record(),
            as_of="2026-09-30T23:59:59+00:00",
            result="exact_hit",
            feedback_source="independent_observation",
        )


@pytest.mark.parametrize("source", ("author_self_claim", "payment_screenshot"))
def test_self_claim_and_payment_are_never_evidence(source: str) -> None:
    with pytest.raises(EvaluationError, match="INELIGIBLE_EVIDENCE_SOURCE"):
        settle_forward_test(
            record(),
            as_of="2026-10-02T00:00:00+00:00",
            result="exact_hit",
            feedback_source=source,
        )


def test_mature_forward_test_returns_a_deterministic_receipt() -> None:
    left = settle_forward_test(
        record(),
        as_of="2026-10-02T00:00:00+00:00",
        result="partial_hit",
        feedback_source="independent_observation",
        counterevidence=("timing_window_too_wide",),
    )
    right = settle_forward_test(
        record(),
        as_of="2026-10-02T00:00:00+00:00",
        result="partial_hit",
        feedback_source="independent_observation",
        counterevidence=("timing_window_too_wide",),
    )

    assert left.to_dict() == right.to_dict()
    assert left.result == "partial_hit"
    assert left.maturity_status == "matured"
    assert left.canonical_hash.startswith("sha256:")


def test_no_feedback_and_invalid_contracts_are_classified_without_accuracy_claims() -> None:
    no_feedback = settle_forward_test(
        record(),
        as_of="2026-10-02T00:00:00+00:00",
        result=None,
        feedback_source=None,
    )
    bad_input = settle_forward_test(
        record(input_valid=False),
        as_of="2026-10-02T00:00:00+00:00",
        result="exact_hit",
        feedback_source="independent_observation",
    )
    invalid_prediction = settle_forward_test(
        record(prediction_valid=False),
        as_of="2026-10-02T00:00:00+00:00",
        result="exact_hit",
        feedback_source="independent_observation",
    )

    assert no_feedback.result == "no_feedback"
    assert bad_input.result == "bad_input"
    assert invalid_prediction.result == "invalid_prediction"
    assert not no_feedback.counts_toward_accuracy
    assert not bad_input.counts_toward_accuracy
    assert not invalid_prediction.counts_toward_accuracy

