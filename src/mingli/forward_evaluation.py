from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .contracts.serialization import digest


EVALUATION_RESULTS = (
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
ELIGIBLE_EVIDENCE_SOURCES = frozenset(
    {
        "independent_observation",
        "official_result",
        "documented_reality",
        "user_feedback_with_verifiable_artifact",
    }
)
INELIGIBLE_EVIDENCE_SOURCES = frozenset(
    {"author_self_claim", "payment_screenshot"}
)
_ACCURACY_RESULTS = frozenset(
    {"exact_hit", "partial_hit", "miss", "timing_error", "category_error"}
)


class EvaluationError(ValueError):
    """Raised when a forward test cannot be settled without leakage."""


def _instant(value: str, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EvaluationError(f"{field_name} must be a timezone-aware ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvaluationError(f"{field_name} must be a valid ISO-8601 string") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvaluationError(f"{field_name} must include a timezone")
    return parsed


@dataclass(frozen=True, slots=True)
class ForwardTestRecord:
    test_id: str
    prediction_id: str
    rule_ids: tuple[str, ...]
    frozen_at: str
    due_at: str
    input_valid: bool
    prediction_valid: bool
    status: str = "pending_forward_test"

    def __post_init__(self) -> None:
        if not isinstance(self.test_id, str) or not self.test_id:
            raise EvaluationError("test_id is required")
        if not isinstance(self.prediction_id, str) or not self.prediction_id:
            raise EvaluationError("prediction_id is required")
        if not self.rule_ids or any(
            not isinstance(rule_id, str) or not rule_id for rule_id in self.rule_ids
        ):
            raise EvaluationError("rule_ids must contain at least one rule id")
        frozen = _instant(self.frozen_at, "frozen_at")
        due = _instant(self.due_at, "due_at")
        if due <= frozen:
            raise EvaluationError("due_at must be later than frozen_at")
        if not isinstance(self.input_valid, bool) or not isinstance(
            self.prediction_valid, bool
        ):
            raise EvaluationError("validity flags must be boolean")
        if self.status != "pending_forward_test":
            raise EvaluationError("forward test status must be pending_forward_test")

    @property
    def canonical_hash(self) -> str:
        return digest({"record_type": "ForwardTestRecord", "payload": self.to_dict()})

    def to_dict(self) -> dict[str, object]:
        return {
            "test_id": self.test_id,
            "prediction_id": self.prediction_id,
            "rule_ids": list(self.rule_ids),
            "frozen_at": self.frozen_at,
            "due_at": self.due_at,
            "input_valid": self.input_valid,
            "prediction_valid": self.prediction_valid,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class EvaluationReceipt:
    test_id: str
    prediction_id: str
    rule_ids: tuple[str, ...]
    settled_at: str
    due_at: str
    maturity_status: str
    result: str
    feedback_source: str | None
    counterevidence: tuple[str, ...]
    counts_toward_accuracy: bool
    canonical_hash: str
    schema_version: str = "forward-evaluation-receipt@1.0"

    def to_dict(self) -> dict[str, object]:
        return {
            "test_id": self.test_id,
            "prediction_id": self.prediction_id,
            "rule_ids": list(self.rule_ids),
            "settled_at": self.settled_at,
            "due_at": self.due_at,
            "maturity_status": self.maturity_status,
            "result": self.result,
            "feedback_source": self.feedback_source,
            "counterevidence": list(self.counterevidence),
            "counts_toward_accuracy": self.counts_toward_accuracy,
            "canonical_hash": self.canonical_hash,
            "schema_version": self.schema_version,
        }


def settle_forward_test(
    record: ForwardTestRecord,
    *,
    as_of: str,
    result: str | None,
    feedback_source: str | None,
    counterevidence: tuple[str, ...] = (),
) -> EvaluationReceipt:
    as_of_instant = _instant(as_of, "as_of")
    if as_of_instant < _instant(record.due_at, "due_at"):
        raise EvaluationError("FORWARD_TEST_NOT_MATURE")
    if feedback_source in INELIGIBLE_EVIDENCE_SOURCES:
        raise EvaluationError("INELIGIBLE_EVIDENCE_SOURCE")
    if result is not None and result not in EVALUATION_RESULTS:
        raise EvaluationError(f"unknown evaluation result: {result}")
    if result is not None and feedback_source is None:
        raise EvaluationError("feedback_source is required for an observed result")
    if feedback_source is not None and feedback_source not in ELIGIBLE_EVIDENCE_SOURCES:
        raise EvaluationError(f"unsupported feedback source: {feedback_source}")
    if any(not isinstance(item, str) or not item for item in counterevidence):
        raise EvaluationError("counterevidence must contain non-empty strings")

    if not record.input_valid:
        final_result = "bad_input"
    elif not record.prediction_valid:
        final_result = "invalid_prediction"
    elif result is None:
        final_result = "no_feedback"
    else:
        final_result = result

    body = {
        "test_id": record.test_id,
        "prediction_id": record.prediction_id,
        "rule_ids": list(record.rule_ids),
        "settled_at": as_of,
        "due_at": record.due_at,
        "maturity_status": "matured",
        "result": final_result,
        "feedback_source": feedback_source,
        "counterevidence": list(counterevidence),
        "counts_toward_accuracy": final_result in _ACCURACY_RESULTS,
        "schema_version": "forward-evaluation-receipt@1.0",
    }
    return EvaluationReceipt(
        test_id=record.test_id,
        prediction_id=record.prediction_id,
        rule_ids=record.rule_ids,
        settled_at=as_of,
        due_at=record.due_at,
        maturity_status="matured",
        result=final_result,
        feedback_source=feedback_source,
        counterevidence=counterevidence,
        counts_toward_accuracy=final_result in _ACCURACY_RESULTS,
        canonical_hash=digest(
            {"record_type": "EvaluationReceipt", "payload": body}
        ),
    )
