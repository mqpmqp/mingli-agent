from __future__ import annotations

from importlib import resources
import json
from typing import Mapping, Sequence

from .contracts.serialization import canonical_json, digest
from .validation_claims import calculate_validation_metrics


RELEASE_HOLD_ATTACK_PROTOCOL_VERSION = "release-hold-attack@1.0.0"
RC_BASELINE_SHA = "b03af9f1a7ee5199f64cdd627dd47f348c761d6e"
_PROTOCOL_RESOURCE = "release_hold_attack_v1_protocol.json"
_COMPARISON_STATUSES = frozenset(
    {
        "supported",
        "partially_supported",
        "contradicted",
        "not_comparable",
        "insufficient_evidence",
        "excluded_by_contract",
    }
)


class ReleaseHoldAttackV1Error(ValueError):
    """Raised when a reassessment input crosses a real-case safety boundary."""


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ReleaseHoldAttackV1Error(f"{field} must be an object")
    return dict(value)


def _nonempty_strings(value: object, *, field: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReleaseHoldAttackV1Error(f"{field} must be an array")
    result = [str(item) for item in value]
    if any(not item for item in result):
        raise ReleaseHoldAttackV1Error(f"{field} must contain non-empty strings")
    return result


def _protocol_body(protocol: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in protocol.items() if key != "canonical_hash"}


def _validate_protocol(protocol: Mapping[str, object]) -> dict[str, object]:
    value = _mapping(protocol, field="protocol")
    if value.get("protocol_version") != RELEASE_HOLD_ATTACK_PROTOCOL_VERSION:
        raise ReleaseHoldAttackV1Error("unsupported release-hold attack protocol version")
    if value.get("source_commit_sha") != RC_BASELINE_SHA:
        raise ReleaseHoldAttackV1Error("protocol must be pinned to the Release Candidate baseline")
    expected = digest(
        {"record_type": "ReleaseHoldAttackProtocolV1", "payload": _protocol_body(value)}
    )
    if value.get("canonical_hash") != expected:
        raise ReleaseHoldAttackV1Error("protocol canonical hash is invalid")
    review = _mapping(value.get("review"), field="protocol.review")
    if review.get("minimum_independent_human_reviewers") != 2:
        raise ReleaseHoldAttackV1Error("protocol requires two independent human reviewers")
    reassessment = _mapping(
        value.get("hold_reassessment"), field="protocol.hold_reassessment"
    )
    if reassessment.get("automatic_release") is not False:
        raise ReleaseHoldAttackV1Error("protocol cannot permit automatic release")
    return json.loads(canonical_json(value))


def load_release_hold_attack_protocol() -> dict[str, object]:
    raw = resources.files("mingli.derived.data").joinpath(_PROTOCOL_RESOURCE).read_text(
        encoding="utf-8"
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - packaged static guard
        raise ReleaseHoldAttackV1Error("protocol JSON is invalid") from exc
    return _validate_protocol(_mapping(parsed, field="protocol"))


def _validate_record(raw: Mapping[str, object]) -> dict[str, object]:
    record = _mapping(raw, field="record")
    if record.get("data_classification") != "authorized_real_case":
        raise ReleaseHoldAttackV1Error("authorized real-case classification is required")
    if record.get("synthetic") is not False:
        raise ReleaseHoldAttackV1Error("synthetic records cannot enter Hold reassessment")
    if record.get("consent_status") != "granted":
        raise ReleaseHoldAttackV1Error("granted consent is required")
    if record.get("prediction_frozen_before_reality") is not True:
        raise ReleaseHoldAttackV1Error("prediction must be frozen before reality feedback")
    if record.get("double_human_review_complete") is not True:
        raise ReleaseHoldAttackV1Error("double human review is required")
    if not isinstance(record.get("person_case_id"), str) or not str(
        record["person_case_id"]
    ).startswith("person:"):
        raise ReleaseHoldAttackV1Error("person_case_id must be a pseudonymous person id")
    if not isinstance(record.get("scenario_id"), str) or not record["scenario_id"]:
        raise ReleaseHoldAttackV1Error("scenario_id is required")
    if record.get("comparison_status") not in _COMPARISON_STATUSES:
        raise ReleaseHoldAttackV1Error("unsupported comparison_status")
    confidence = record.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= float(confidence) <= 1
    ):
        raise ReleaseHoldAttackV1Error("confidence must be a number from zero through one")
    tier = record.get("evidence_tier")
    if tier not in {"gold", "silver"}:
        raise ReleaseHoldAttackV1Error("evidence_tier must be gold or silver")
    record["rule_ids"] = _nonempty_strings(record.get("rule_ids", []), field="rule_ids")
    record["reality_evidence_ids"] = _nonempty_strings(
        record.get("reality_evidence_ids", []), field="reality_evidence_ids"
    )
    return record


def calculate_release_hold_attack_metrics(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Calculate preregistered diagnostic metrics without authorizing a release."""

    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise ReleaseHoldAttackV1Error("records must be an array")
    validated = [_validate_record(item) for item in records]
    base = calculate_validation_metrics(validated)
    observable = [
        item for item in validated if item["comparison_status"] != "excluded_by_contract"
    ]
    if not observable:
        raise ReleaseHoldAttackV1Error("at least one observable authorized claim is required")
    unique_people = {str(item["person_case_id"]) for item in validated}
    gold_people = {
        str(item["person_case_id"])
        for item in validated
        if item["evidence_tier"] == "gold"
    }
    silver_people = {
        str(item["person_case_id"])
        for item in validated
        if item["evidence_tier"] == "silver"
    }
    if gold_people.intersection(silver_people):
        raise ReleaseHoldAttackV1Error("a person cannot mix gold and silver evidence tiers")
    rule_covered = sum(bool(item["rule_ids"]) for item in observable)
    reality_covered = sum(bool(item["reality_evidence_ids"]) for item in observable)
    unverifiable = sum(
        item["comparison_status"]
        in {"insufficient_evidence", "not_comparable"}
        for item in observable
    )
    double_review_coverage = sum(
        item["double_human_review_complete"] is True for item in observable
    ) / len(observable)
    body: dict[str, object] = {
        **base,
        "unique_person_count": len(unique_people),
        "gold_unique_person_count": len(gold_people),
        "silver_unique_person_count": len(silver_people),
        "scenario_coverage": sorted({str(item["scenario_id"]) for item in validated}),
        "rule_attribution_coverage": rule_covered / len(observable),
        "reality_evidence_coverage": reality_covered / len(observable),
        "unverifiable_rate": unverifiable / len(observable),
        "double_human_review_coverage": double_review_coverage,
        "source_commit_sha": RC_BASELINE_SHA,
        "data_classification": "authorized_real_case",
        "accuracy_claim_allowed": False,
        "release_hold": "ACTIVE",
        "prediction_validity": "not_evaluated",
    }
    body["canonical_hash"] = digest(
        {"record_type": "ReleaseHoldAttackMetricsV1", "payload": body}
    )
    return json.loads(canonical_json(body))


def assess_release_hold_reassessment(
    metrics: Mapping[str, object],
    *,
    protocol: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Report whether an independent review may be requested; never release automatically."""

    active_protocol = _validate_protocol(
        protocol if protocol is not None else load_release_hold_attack_protocol()
    )
    value = _mapping(metrics, field="metrics")
    thresholds = _mapping(
        _mapping(active_protocol["hold_reassessment"], field="protocol.hold_reassessment").get(
            "thresholds"
        ),
        field="protocol.hold_reassessment.thresholds",
    )
    blockers: list[str] = []
    minimums = {
        "unique_person_count": "minimum_unique_persons",
        "gold_unique_person_count": "minimum_gold_persons",
        "comparable_claims": "minimum_comparable_claims",
        "calibration_sample_size": "minimum_calibration_sample_size",
    }
    for metric_name, threshold_name in minimums.items():
        if not isinstance(value.get(metric_name), int) or value[metric_name] < thresholds[threshold_name]:
            blockers.append(metric_name)
    if not isinstance(value.get("silver_unique_person_count"), int) or value[
        "silver_unique_person_count"
    ] > thresholds["maximum_silver_persons"]:
        blockers.append("silver_unique_person_count")
    scenarios = value.get("scenario_coverage")
    if not isinstance(scenarios, Sequence) or isinstance(scenarios, (str, bytes)) or len(scenarios) < thresholds["minimum_scenarios"]:
        blockers.append("scenario_coverage")
    lower_bound_metrics = {
        "rule_attribution_coverage": "minimum_rule_attribution_coverage",
        "reality_evidence_coverage": "minimum_reality_evidence_coverage",
        "double_human_review_coverage": "minimum_double_human_review_coverage",
    }
    for metric_name, threshold_name in lower_bound_metrics.items():
        if not isinstance(value.get(metric_name), (int, float)) or value[metric_name] < thresholds[threshold_name]:
            blockers.append(metric_name)
    upper_bound_metrics = {
        "unverifiable_rate": "maximum_unverifiable_rate",
        "brier_score": "maximum_brier_score",
        "ece": "maximum_expected_calibration_error",
    }
    for metric_name, threshold_name in upper_bound_metrics.items():
        if not isinstance(value.get(metric_name), (int, float)) or value[metric_name] > thresholds[threshold_name]:
            blockers.append(metric_name)
    if value.get("accuracy_claim_allowed") is not False:
        blockers.append("accuracy_claim_boundary")
    if value.get("release_hold") != "ACTIVE":
        blockers.append("release_hold_boundary")
    body = {
        "protocol_hash": active_protocol["canonical_hash"],
        "source_commit_sha": RC_BASELINE_SHA,
        "reassessment_eligible": not blockers,
        "blockers": sorted(set(blockers)),
        "automatic_release": False,
        "requires_independent_authorization": True,
        "release_hold": "ACTIVE",
        "prediction_validity": "not_evaluated",
        "accuracy_claim_allowed": False,
    }
    body["canonical_hash"] = digest(
        {"record_type": "ReleaseHoldAttackReassessmentV1", "payload": body}
    )
    return json.loads(canonical_json(body))


__all__ = [
    "RC_BASELINE_SHA",
    "RELEASE_HOLD_ATTACK_PROTOCOL_VERSION",
    "ReleaseHoldAttackV1Error",
    "assess_release_hold_reassessment",
    "calculate_release_hold_attack_metrics",
    "load_release_hold_attack_protocol",
]
