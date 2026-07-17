"""Synthetic contract tests for Bazi Expert Rules V2.

The generated Phase 7 charts in this module are synthetic fixtures.  They prove
only deterministic orchestration contracts and are never evidence of predictive
accuracy.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json

import pytest
from jsonschema import Draft202012Validator

from mingli.bazi_expert_v2 import (
    BAZI_EXPERT_V2_INPUT_SCHEMA_VERSION,
    BAZI_EXPERT_V2_METHOD_ID,
    BAZI_EXPERT_V2_SCHEMA_VERSION,
    BaziExpertV2InputError,
    load_bazi_expert_v2_schema,
    orchestrate_bazi_expert_v2,
)
from mingli.contracts.serialization import digest
from mingli.phase13 import build_phase13_fixture
from mingli.phase20 import DISCLAIMER, FORBIDDEN_PROMISES


@pytest.fixture(scope="module")
def synthetic_graph() -> dict[str, object]:
    graph, _ = build_phase13_fixture("甲", "寅")
    return graph


def _request(graph: dict[str, object], **updates: object) -> dict[str, object]:
    timeline = graph["timeline"]
    assert isinstance(timeline, dict)
    liunian = timeline["liunian_periods"]
    assert isinstance(liunian, list)
    first_year = liunian[0]
    assert isinstance(first_year, dict)
    request: dict[str, object] = {
        "schema_version": BAZI_EXPERT_V2_INPUT_SCHEMA_VERSION,
        "fact_graph": deepcopy(graph),
        "target_id": first_year["period_id"],
        "reality_context": {},
        "fixture_provenance": {
            "synthetic": True,
            "purpose": "contract_test_only",
            "accuracy_eligible": False,
        },
    }
    request.update(updates)
    return request


def _evidence_availability(
    *,
    event_window: str = "2028-01-01T00:00:00Z/2028-12-31T23:59:59Z",
    observed_at: str = "2029-01-01T00:00:00Z",
    collected_at: str = "2029-01-02T00:00:00Z",
) -> dict[str, str]:
    return {
        "event_window": event_window,
        "observed_at": observed_at,
        "collected_at": collected_at,
    }


@pytest.fixture(scope="module")
def complete_payload(synthetic_graph: dict[str, object]) -> dict[str, object]:
    timeline = synthetic_graph["timeline"]
    assert isinstance(timeline, dict)
    liunian = timeline["liunian_periods"]
    assert isinstance(liunian, list)
    first_year = liunian[0]
    assert isinstance(first_year, dict)
    request = _request(
        synthetic_graph,
        evaluation_at="2025-02-01T00:00:00Z",
        reality_context={
            "major_eligible": False,
            "preparation_months": 1,
            "other_party_status": "married",
            "no_contact_months": 24,
        },
        compatibility_peer_fact_graph=deepcopy(synthetic_graph),
        prior_event_evidence=[
            {
                "evidence_id": "prior-event-evidence:employment",
                "claim_id": "prior-event:employment-history",
                "scope": "before-anchor:employment",
                "source_id": "synthetic-contract-observation",
                "direction": "support",
                "verified": True,
                "detail_code": "synthetic_contract_fixture_only",
                **_evidence_availability(
                    event_window="2025-01-01T00:00:00Z/2025-01-31T23:59:59Z",
                    observed_at="2025-01-31T23:59:59Z",
                    collected_at="2025-02-01T00:00:00Z",
                ),
            }
        ],
        renderer_context={
            "profile": {
                "calendar": "solar",
                "birth_date": "2000-01-01",
                "birth_time": "12:00",
            },
            "chenggu": {"display_weight": "未计算", "verse_available": False},
            "start_year": first_year["label_year"],
            "advice_codes": ["verify_reality", "build_plan"],
        },
    )
    return orchestrate_bazi_expert_v2(request).to_dict()


def test_versioned_result_validates_and_preserves_non_accuracy_boundaries(
    complete_payload: dict[str, object],
) -> None:
    assert complete_payload["schema_version"] == BAZI_EXPERT_V2_SCHEMA_VERSION
    assert complete_payload["method_id"] == BAZI_EXPERT_V2_METHOD_ID
    assert complete_payload["prediction_validity"] == "not_evaluated"
    assert complete_payload["release_hold"] == "ACTIVE"
    assert complete_payload["accuracy_claim_allowed"] is False
    assert complete_payload["canonical_hash"].startswith("sha256:")
    assert complete_payload["fixture_provenance"] == {
        "accuracy_eligible": False,
        "purpose": "contract_test_only",
        "synthetic": True,
    }
    schema = load_bazi_expert_v2_schema()
    assert schema["$id"].endswith("bazi_expert_v2_result.schema.json")
    assert not list(Draft202012Validator(schema).iter_errors(complete_payload))


def test_canonical_hash_binds_all_public_boundary_metadata(
    complete_payload: dict[str, object],
) -> None:
    body = {
        key: value
        for key, value in complete_payload.items()
        if key != "canonical_hash"
    }
    assert complete_payload["canonical_hash"] == digest(
        {"record_type": "BaziExpertV2Result", "payload": body}
    )


def test_facets_distinguish_implemented_conditional_and_unsupported(
    complete_payload: dict[str, object],
) -> None:
    facets = complete_payload["facets"]
    assert isinstance(facets, dict)
    summary = complete_payload["facet_summary"]
    assert isinstance(summary, dict)
    assert set(summary) == {"implemented", "conditional", "unsupported"}
    assert set().union(*(set(values) for values in summary.values())) == set(facets)
    assert {facet["status"] for facet in facets.values()} == {
        "implemented",
        "conditional",
        "unsupported",
    }
    for facet_id in ("five_element_strength", "same_kind_different_kind"):
        assert facets[facet_id]["status"] == "implemented"
    for facet_id in (
        "pattern",
        "yongshen_climate_regulation",
        "ten_god_combinations",
        "career",
        "wealth",
        "relationship",
        "study",
        "civil_service_exam",
        "relationship_reunion",
        "dual_person_compatibility",
        "prior_event_validation",
        "yuan_renderer_adapter",
    ):
        assert facets[facet_id]["status"] == "conditional"
    for facet_id in ("monthly_scope", "marriage", "family"):
        assert facets[facet_id]["status"] == "unsupported"
        assert facets[facet_id]["confidence"] == "not_applicable"


def test_composed_structural_temporal_and_domain_views_are_source_backed(
    complete_payload: dict[str, object],
) -> None:
    facets = complete_payload["facets"]
    assert isinstance(facets, dict)
    strength = facets["five_element_strength"]["data"]
    proportions = facets["same_kind_different_kind"]["data"]
    assert set(strength["element_scores"]) == {"wood", "fire", "earth", "metal", "water"}
    assert Decimal(proportions["same_kind_ratio"]) + Decimal(
        proportions["different_kind_ratio"]
    ) == Decimal("1.0000")
    assert facets["pattern"]["data"]["candidate_only"] is True
    assert facets["yongshen_climate_regulation"]["data"]["seasonal_climate_needs"]
    assert facets["ten_god_combinations"]["data"]["dynamic_hits"]
    relation_families = facets["punishment_clash_combine_harm"]["data"][
        "relation_families"
    ]
    assert set(relation_families) == {"punishment", "clash", "combine", "harm"}
    assert facets["decadal_luck"]["data"]["interactions"]
    assert facets["annual_scope"]["data"]["trends"]
    assert facets["monthly_scope"]["availability"] == "unsupported_by_frozen_phases"
    for facet_id in ("career", "wealth", "relationship", "study"):
        assert facets[facet_id]["data"]["target_id"] == complete_payload["selected_target_id"]
    assert facets["marriage"]["data"]["concrete_event_prediction"] == "unsupported"
    assert facets["family"]["data"]["rule_coverage"] == "unsupported"
    source_results = complete_payload["source_results"]
    assert set(source_results) >= {f"phase{number}" for number in range(9, 19)}
    assert all(
        value["canonical_hash"].startswith("sha256:")
        for value in source_results.values()
    )


def test_annual_scope_rejects_non_liunian_target(
    synthetic_graph: dict[str, object],
) -> None:
    timeline = synthetic_graph["timeline"]
    assert isinstance(timeline, dict)
    dayun = timeline["dayun_periods"]
    assert isinstance(dayun, list)
    first_decade = dayun[0]
    assert isinstance(first_decade, dict)

    with pytest.raises(BaziExpertV2InputError, match="liunian"):
        orchestrate_bazi_expert_v2(
            _request(synthetic_graph, target_id=first_decade["period_id"])
        )


def test_exam_reunion_compatibility_and_prior_events_remain_bounded(
    complete_payload: dict[str, object],
) -> None:
    facets = complete_payload["facets"]
    exam = facets["civil_service_exam"]["data"]
    assert set(exam) >= {
        "system_fit",
        "exam_conditions",
        "role_direction",
        "preparation_strategy",
    }
    assert set(exam["exam_conditions"]) == {"eligibility", "exam_outlook"}
    reunion = facets["relationship_reunion"]["data"]
    assert set(reunion) >= {"attraction", "contact", "reunion", "stability"}
    compatibility = facets["dual_person_compatibility"]["data"]
    assert compatibility["comparison_only"] is True
    assert compatibility["compatibility_conclusion"] == "unsupported"
    assert "score" not in compatibility
    prior = facets["prior_event_validation"]["data"]
    assert prior["claims"][0]["claim_id"] == "prior-event:employment-history"
    assert prior["claims"][0]["status"] == "resolved_by_reality_override"
    assert complete_payload["prediction_validity"] == "not_evaluated"


def test_reality_evidence_hard_override_is_claim_and_scope_specific(
    synthetic_graph: dict[str, object],
) -> None:
    request = _request(synthetic_graph)
    target_id = request["target_id"]
    request["evaluation_at"] = "2029-01-02T00:00:00Z"
    request["domain_reality_evidence"] = [
        {
            "evidence_id": "reality:career:blocked",
            "target_id": target_id,
            "domain": "career",
            "direction": "contradict",
            "detail": "verified synthetic contract condition",
            "weight": 10,
            "verified": True,
            "source_id": "synthetic-contract-reality",
            **_evidence_availability(),
        }
    ]
    payload = orchestrate_bazi_expert_v2(request).to_dict()
    facets = payload["facets"]
    assert facets["career"]["data"]["reality_override"] is True
    assert facets["career"]["data"]["reality_override_direction"] == "contradict"
    assert facets["wealth"]["data"]["reality_override"] is False
    fusion = payload["evidence_fusion"]
    career_claim = next(
        item
        for item in fusion["claims"]
        if item["claim_id"] == f"bazi-domain-judgement:{target_id}:career"
        and item["scope"] == f"{target_id}:career"
    )
    assert career_claim["status"] == "resolved_by_reality_override"
    assert career_claim["hard_override_direction"] == "contradict"
    calibrated = next(
        item
        for item in payload["calibrated_claims"]
        if item["claim_id"] == career_claim["claim_id"]
        and item["scope"] == career_claim["scope"]
    )
    assert calibrated["confidence"] in {"medium", "high"}


def test_conflicting_verified_reality_is_unresolved_and_low_confidence(
    synthetic_graph: dict[str, object],
) -> None:
    request = _request(synthetic_graph)
    target_id = request["target_id"]
    request["evaluation_at"] = "2029-01-02T00:00:00Z"
    common = {
        "target_id": target_id,
        "domain": "relationship",
        "detail": "synthetic contradictory contract evidence",
        "weight": 10,
        "verified": True,
        **_evidence_availability(),
    }
    request["domain_reality_evidence"] = [
        {
            **common,
            "evidence_id": "reality:relationship:support",
            "direction": "support",
            "source_id": "synthetic-support",
        },
        {
            **common,
            "evidence_id": "reality:relationship:contradict",
            "direction": "contradict",
            "source_id": "synthetic-contradict",
        },
    ]
    payload = orchestrate_bazi_expert_v2(request).to_dict()
    relationship = payload["facets"]["relationship"]
    assert relationship["data"]["judgement_label"] == "unresolved"
    assert relationship["confidence"] == "low"
    fused = next(
        item
        for item in payload["evidence_fusion"]["claims"]
        if item["claim_id"]
        == f"bazi-domain-judgement:{target_id}:relationship"
        and item["scope"] == f"{target_id}:relationship"
    )
    assert fused["status"] == "unresolved_conflict"
    assert fused["confidence"] == "low"
    assert fused["hard_override_direction"] is None


@pytest.mark.parametrize(
    ("field", "record"),
    [
        (
            "temporal_reality_evidence",
            {
                "evidence_id": "reality:temporal:future",
                "direction": "support",
                "detail": "synthetic future availability mutation",
                "weight": 1,
                "verified": True,
                "source_id": "synthetic-contract-source",
            },
        ),
        (
            "domain_reality_evidence",
            {
                "evidence_id": "reality:domain:future",
                "domain": "career",
                "direction": "support",
                "detail": "synthetic future availability mutation",
                "weight": 1,
                "verified": True,
                "source_id": "synthetic-contract-source",
            },
        ),
        (
            "prior_event_evidence",
            {
                "evidence_id": "reality:prior:future",
                "claim_id": "prior-event:employment-history",
                "scope": "before-anchor:employment",
                "source_id": "synthetic-contract-source",
                "direction": "support",
                "verified": True,
                "detail_code": "synthetic_future_availability_mutation",
            },
        ),
    ],
)
def test_direct_reality_evidence_rejects_information_available_after_evaluation(
    synthetic_graph: dict[str, object], field: str, record: dict[str, object]
) -> None:
    request = _request(
        synthetic_graph,
        evaluation_at="2028-12-31T23:59:59Z",
    )
    record = deepcopy(record)
    if field != "prior_event_evidence":
        record["target_id"] = request["target_id"]
    record.update(_evidence_availability())
    request[field] = [record]

    with pytest.raises(BaziExpertV2InputError, match="available after evaluation_at"):
        orchestrate_bazi_expert_v2(request)


def test_direct_reality_evidence_requires_an_explicit_evaluation_cutoff(
    synthetic_graph: dict[str, object],
) -> None:
    request = _request(synthetic_graph)
    request["domain_reality_evidence"] = [
        {
            "evidence_id": "reality:domain:no-cutoff",
            "target_id": request["target_id"],
            "domain": "career",
            "direction": "support",
            "detail": "synthetic missing cutoff mutation",
            "weight": 1,
            "verified": True,
            "source_id": "synthetic-contract-source",
            **_evidence_availability(),
        }
    ]

    with pytest.raises(BaziExpertV2InputError, match="evaluation_at"):
        orchestrate_bazi_expert_v2(request)


def test_yuan_adapter_uses_phase20_without_inventing_text(
    complete_payload: dict[str, object],
) -> None:
    yuan = complete_payload["yuan"]
    assert yuan["prediction_validity"] == "not_evaluated"
    assert len(yuan["sections"]) == 8
    assert yuan["rendered_text"].count(DISCLAIMER) == 1
    assert yuan["rendered_text"].endswith(DISCLAIMER)
    assert not any(token in yuan["rendered_text"] for token in FORBIDDEN_PROMISES)
    assert complete_payload["source_results"]["phase20"]["canonical_hash"] == yuan[
        "canonical_hash"
    ]


def test_hash_is_deterministic_across_json_key_order(
    synthetic_graph: dict[str, object],
) -> None:
    request = _request(synthetic_graph)
    first = orchestrate_bazi_expert_v2(request)
    reordered = json.loads(json.dumps(request, ensure_ascii=False, sort_keys=True))
    second = orchestrate_bazi_expert_v2(reordered)
    assert first.canonical_hash == second.canonical_hash
    assert first.to_dict() == second.to_dict()


def test_fail_closed_for_unknown_versions_tampering_and_private_fields(
    synthetic_graph: dict[str, object],
) -> None:
    with pytest.raises(BaziExpertV2InputError, match="schema_version"):
        orchestrate_bazi_expert_v2(
            {**_request(synthetic_graph), "schema_version": "bazi-expert-input@1.0"}
        )
    with pytest.raises(BaziExpertV2InputError, match="unsupported request fields"):
        orchestrate_bazi_expert_v2(
            {**_request(synthetic_graph), "person_name": "synthetic name must not pass"}
        )
    tampered = _request(synthetic_graph)
    fact_graph = tampered["fact_graph"]
    assert isinstance(fact_graph, dict)
    fact_graph["canonical_hash"] = "sha256:" + "0" * 64
    with pytest.raises(BaziExpertV2InputError, match="fact graph|canonical_hash"):
        orchestrate_bazi_expert_v2(tampered)


@pytest.mark.parametrize(
    ("field", "record"),
    [
        (
            "domain_reality_evidence",
            {
                "evidence_id": "reality:domain:extra-scope",
                "domain": "career",
                "direction": "support",
                "detail": "synthetic contract evidence",
                "weight": 1,
                "verified": True,
                "source_id": "synthetic-contract-source",
                "claim_id": "wrong:claim",
                "scope": "wrong:scope",
            },
        ),
        (
            "temporal_reality_evidence",
            {
                "evidence_id": "reality:temporal:extra-scope",
                "direction": "support",
                "detail": "synthetic contract evidence",
                "weight": 1,
                "verified": True,
                "source_id": "synthetic-contract-source",
                "claim_id": "wrong:claim",
                "scope": "wrong:scope",
            },
        ),
    ],
)
def test_nested_reality_evidence_rejects_ignored_claim_scope_fields(
    synthetic_graph: dict[str, object], field: str, record: dict[str, object]
) -> None:
    request = _request(synthetic_graph)
    record["target_id"] = request["target_id"]
    request[field] = [record]
    with pytest.raises(BaziExpertV2InputError, match="unsupported fields"):
        orchestrate_bazi_expert_v2(request)
