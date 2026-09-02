from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from mingli.contracts import get_schema
from mingli.training import TrainingError
from mingli.training_v2 import OUTCOME_SCHEMA_V2, TrainingStoreV2


def _outcome_v2() -> dict[str, object]:
    return {
        "outcome_id": "outcome-1",
        "case_id": "person:" + "a" * 64,
        "run_id": "run-1",
        "event_type": "job_change",
        "event_time": "2026-09-01T00:00:00Z",
        "observed_at": "2026-09-02T00:00:00Z",
        "source_type": "independent_record",
        "source_reliability": "independently_verified",
        "relation_to_prior_claim": "preregistered_claim_outcome",
        "notes": None,
        "preregistered_claim_id": "claim-1",
        "commercial_validation_eligible": False,
        "eligibility_reason": "REAL_CASE_V2_ADJUDICATION_REQUIRED",
        "valid": True,
    }


def test_v2_accepts_a_controlled_outcome() -> None:
    Draft202012Validator(get_schema(OUTCOME_SCHEMA_V2)).validate(_outcome_v2())


@pytest.mark.parametrize(
    "change",
    [
        {"commercial_validation_eligible": True},
        {"eligibility_reason": None},
        {"eligibility_reason": "caller-asserted"},
    ],
)
def test_v2_rejects_unsafe_outcome_variants(change: dict[str, object]) -> None:
    payload = _outcome_v2()
    payload.update(change)
    with pytest.raises(ValidationError):
        Draft202012Validator(get_schema(OUTCOME_SCHEMA_V2)).validate(payload)


def test_v1_contract_remains_compatible_with_legacy_outcomes() -> None:
    payload = deepcopy(_outcome_v2())
    payload.pop("eligibility_reason")
    payload["commercial_validation_eligible"] = True
    Draft202012Validator(get_schema("outcome_observation.schema.json")).validate(payload)


def test_v2_is_a_distinct_versioned_contract() -> None:
    assert OUTCOME_SCHEMA_V2 != "outcome_observation.schema.json"
    schema = get_schema(OUTCOME_SCHEMA_V2)
    assert schema["additionalProperties"] is False


def test_v2_training_consumer_validates_against_v2_schema() -> None:
    store = TrainingStoreV2.__new__(TrainingStoreV2)
    validated = store._validate("outcome", _outcome_v2())
    assert validated["eligibility_reason"] == "REAL_CASE_V2_ADJUDICATION_REQUIRED"
    unsafe = _outcome_v2()
    unsafe["commercial_validation_eligible"] = True
    with pytest.raises(TrainingError):
        store._validate("outcome", unsafe)
