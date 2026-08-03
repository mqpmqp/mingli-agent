from __future__ import annotations

import inspect
from copy import deepcopy

import pytest

from mingli.confirmed_pillar_runtime import (
    ConfirmedPillarInputError,
    ConfirmedPillarRuntimeResult,
    run_confirmed_pillar_agent,
)


def request() -> dict[str, object]:
    return {
        "pillars": {
            "year": "戊辰",
            "month": "乙卯",
            "day": "壬午",
            "hour": "丙午",
        },
        "day_master": "壬",
        "gender": "female",
        "source": "image_confirmed",
        "confirmation_status": "confirmed",
        "trace_id": "trace-test-1",
        "idempotency_key": "image-confirmation-test-1",
    }


def test_public_signature_and_static_runtime_result() -> None:
    assert tuple(inspect.signature(run_confirmed_pillar_agent).parameters) == ("raw",)
    assert inspect.signature(run_confirmed_pillar_agent).return_annotation in {
        "ConfirmedPillarRuntimeResult",
        ConfirmedPillarRuntimeResult,
    }

    result = run_confirmed_pillar_agent(request())
    payload = result.to_dict()

    assert payload["chart"]["pillars"] == request()["pillars"]
    assert payload["chart"]["day_master"] == "壬"
    assert payload["chart"]["gender"] == "female"
    assert payload["chart"]["source"] == "image_confirmed"
    assert payload["artifacts"]["strength"]["day_master"] == "壬"
    assert payload["artifacts"]["pattern"]["fact_graph_hash"]
    assert payload["artifacts"]["regulation"]["pattern_result_hash"]
    assert payload["artifacts"]["xiji"]["regulation_result_hash"]
    assert "女命" in payload["final_answer"]
    assert "戊辰 乙卯 壬午 丙午" in payload["final_answer"]
    assert "精确起运年龄" in payload["final_answer"]
    assert payload["unsupported"] == [
        "birth_date",
        "birth_time",
        "birth_location",
        "timezone",
        "true_solar_time",
        "luck_start_age",
        "dayun_timeline",
        "chenggu",
    ]


def test_runtime_is_deterministic_and_does_not_mutate_input() -> None:
    raw = request()
    original = deepcopy(raw)

    first = run_confirmed_pillar_agent(raw).to_dict()
    second = run_confirmed_pillar_agent(raw).to_dict()

    assert first == second
    assert raw == original


def test_text_confirmed_source_is_explicit_and_isolated_from_image_provenance() -> None:
    text = request()
    text["source"] = "text_confirmed"
    text["text_confirmation_id"] = "manual-pillars-42"

    result = run_confirmed_pillar_agent(text).to_dict()

    assert result["chart"]["source"] == "text_confirmed"
    assert result["artifacts"]["fact_graph"]["base_chart_ref"]["source"] == "text_confirmed"

    image = run_confirmed_pillar_agent(request()).to_dict()
    assert image["chart"]["source"] == "image_confirmed"

    text["image_hash"] = "sha256:must-not-cross-provenance"
    with pytest.raises(ConfirmedPillarInputError, match="text_confirmed"):
        run_confirmed_pillar_agent(text)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("gender", None, "gender"),
        ("gender", "unknown", "gender"),
        ("day_master", "乙", "day master"),
        ("confirmation_status", "unconfirmed", "confirmed"),
        ("source", "inferred", "source"),
        ("trace_id", "", "trace_id"),
        ("idempotency_key", "", "idempotency_key"),
    ],
)
def test_runtime_rejects_unconfirmed_or_inconsistent_metadata(
    field: str,
    value: object,
    message: str,
) -> None:
    raw = request()
    raw[field] = value
    with pytest.raises(ConfirmedPillarInputError, match=message):
        run_confirmed_pillar_agent(raw)


@pytest.mark.parametrize("pillar", ["乙孩", "甲X", "甲甲", ""])
def test_runtime_rejects_invalid_pillars(pillar: str) -> None:
    raw = request()
    raw["pillars"] = {**raw["pillars"], "hour": pillar}
    with pytest.raises(ConfirmedPillarInputError, match="pillar"):
        run_confirmed_pillar_agent(raw)
