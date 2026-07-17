from __future__ import annotations

from copy import deepcopy

import pytest

from mingli.release_hold_attack_v1 import (
    RC_BASELINE_SHA,
    RELEASE_HOLD_ATTACK_PROTOCOL_VERSION,
    ReleaseHoldAttackV1Error,
    assess_release_hold_reassessment,
    calculate_release_hold_attack_metrics,
    load_release_hold_attack_protocol,
)


def _record(
    *,
    person: str,
    status: str,
    confidence: float,
    rule_ids: list[str],
    reality_evidence_ids: list[str],
) -> dict[str, object]:
    return {
        "data_classification": "authorized_real_case",
        "synthetic": False,
        "consent_status": "granted",
        "prediction_frozen_before_reality": True,
        "double_human_review_complete": True,
        "person_case_id": f"person:{person}",
        "scenario_id": "career_exam",
        "domain": "career",
        "comparison_status": status,
        "confidence": confidence,
        "reviewer_agreement": True,
        "adjudicated": False,
        "evidence_tier": "gold",
        "rule_ids": rule_ids,
        "reality_evidence_ids": reality_evidence_ids,
    }


def test_protocol_is_hash_valid_and_pinned_to_the_rc_baseline() -> None:
    protocol = load_release_hold_attack_protocol()

    assert protocol["protocol_version"] == RELEASE_HOLD_ATTACK_PROTOCOL_VERSION
    assert protocol["source_commit_sha"] == RC_BASELINE_SHA
    assert protocol["canonical_hash"].startswith("sha256:")
    assert protocol["review"]["minimum_independent_human_reviewers"] == 2
    assert protocol["hold_reassessment"]["automatic_release"] is False


def test_metrics_expose_coverage_and_calibration_without_authorizing_accuracy_claims() -> None:
    metrics = calculate_release_hold_attack_metrics(
        [
            _record(
                person="a" * 64,
                status="supported",
                confidence=0.8,
                rule_ids=["rule:career"],
                reality_evidence_ids=["evidence:career"],
            ),
            _record(
                person="b" * 64,
                status="insufficient_evidence",
                confidence=0.4,
                rule_ids=[],
                reality_evidence_ids=[],
            ),
        ]
    )

    assert metrics["rule_attribution_coverage"] == 0.5
    assert metrics["reality_evidence_coverage"] == 0.5
    assert metrics["unverifiable_rate"] == 0.5
    assert metrics["brier_score"] == 0.04
    assert metrics["accuracy_claim_allowed"] is False
    assert metrics["release_hold"] == "ACTIVE"


def test_synthetic_or_unreviewed_rows_fail_closed() -> None:
    record = _record(
        person="c" * 64,
        status="supported",
        confidence=0.7,
        rule_ids=["rule:career"],
        reality_evidence_ids=["evidence:career"],
    )
    synthetic = deepcopy(record)
    synthetic["synthetic"] = True
    with pytest.raises(ReleaseHoldAttackV1Error, match="synthetic"):
        calculate_release_hold_attack_metrics([synthetic])

    unreviewed = deepcopy(record)
    unreviewed["double_human_review_complete"] = False
    with pytest.raises(ReleaseHoldAttackV1Error, match="review"):
        calculate_release_hold_attack_metrics([unreviewed])


def test_thresholds_only_allow_independent_reassessment_never_automatic_release() -> None:
    protocol = load_release_hold_attack_protocol()
    metrics = {
        "unique_person_count": 30,
        "gold_unique_person_count": 30,
        "silver_unique_person_count": 0,
        "comparable_claims": 120,
        "scenario_coverage": ["career_exam", "relationship_reconciliation", "wealth_work_change"],
        "rule_attribution_coverage": 1.0,
        "reality_evidence_coverage": 1.0,
        "unverifiable_rate": 0.0,
        "brier_score": 0.0,
        "ece": 0.0,
        "calibration_sample_size": 120,
        "double_human_review_coverage": 1.0,
        "accuracy_claim_allowed": False,
        "release_hold": "ACTIVE",
    }

    result = assess_release_hold_reassessment(metrics, protocol=protocol)

    assert result["reassessment_eligible"] is True
    assert result["automatic_release"] is False
    assert result["release_hold"] == "ACTIVE"
    assert result["prediction_validity"] == "not_evaluated"
    assert result["accuracy_claim_allowed"] is False
