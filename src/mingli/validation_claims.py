from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence


COMPARABLE = frozenset({"supported", "partially_supported", "contradicted"})
ALL_STATUSES = COMPARABLE | {"not_comparable", "insufficient_evidence", "excluded_by_contract"}


def validate_comparable_claim(claim: Mapping[str, object], snapshot: Mapping[str, object]) -> None:
    registered = {
        str(item.get("claim_id"))
        for item in snapshot.get("structured_claims", [])
        if isinstance(item, Mapping)
    }
    if claim.get("claim_id") not in registered:
        raise ValueError("claim was not registered in the frozen prediction snapshot")
    for field in ("prediction_id", "person_case_id", "scenario_id", "domain", "time_window", "claim_type", "predicted_direction", "predicted_event_or_state", "confidence", "specificity_level"):
        if claim.get(field) in (None, ""):
            raise ValueError(f"claim.{field} is required")


def _group_metrics(records: Sequence[Mapping[str, object]], key: str) -> dict[str, object]:
    groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for item in records:
        groups[str(item.get(key, "unclassified"))].append(item)
    return {name: _basic_metrics(items) for name, items in sorted(groups.items())}


def _basic_metrics(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    counts = {status: 0 for status in sorted(ALL_STATUSES)}
    for item in records:
        status = str(item.get("comparison_status"))
        if status not in ALL_STATUSES:
            raise ValueError(f"unsupported comparison_status: {status}")
        counts[status] += 1
    comparable = sum(counts[item] for item in COMPARABLE)
    strict = counts["supported"] / comparable if comparable else None
    lenient = (counts["supported"] + 0.5 * counts["partially_supported"]) / comparable if comparable else None
    return {**counts, "comparable_claims": comparable, "strict_score": strict, "lenient_score": lenient}


def calculate_validation_metrics(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    metrics = _basic_metrics(records)
    comparable = [item for item in records if item.get("comparison_status") in COMPARABLE]
    by_person: dict[str, list[float]] = defaultdict(list)
    for item in comparable:
        score = {"supported": 1.0, "partially_supported": 0.5, "contradicted": 0.0}[str(item["comparison_status"])]
        by_person[str(item.get("person_case_id"))].append(score)
    observable = [item for item in records if item.get("comparison_status") != "excluded_by_contract"]
    support_outcomes = {
        "supported": 1.0,
        "partially_supported": 0.5,
        "contradicted": 0.0,
    }
    calibrated = [
        (float(item["confidence"]), support_outcomes[str(item["comparison_status"])])
        for item in comparable
        if isinstance(item.get("confidence"), (int, float)) and not isinstance(item.get("confidence"), bool)
    ]
    brier = sum((confidence - outcome) ** 2 for confidence, outcome in calibrated) / len(calibrated) if calibrated else None
    bins: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for confidence, outcome in calibrated:
        bins[min(9, max(0, int(confidence * 10)))].append((confidence, outcome))
    ece = (
        sum(
            len(values) / len(calibrated)
            * abs(sum(item[0] for item in values) / len(values) - sum(item[1] for item in values) / len(values))
            for values in bins.values()
        )
        if calibrated else None
    )
    agreement_records = [item for item in records if isinstance(item.get("reviewer_agreement"), bool)]
    adjudicated_records = [item for item in records if item.get("adjudicated") is True]
    metrics.update(
        {
            "total_claims": len(records),
            "coverage": len(comparable) / len(observable) if observable else None,
            "abstention_rate": sum(item.get("comparison_status") == "insufficient_evidence" for item in observable) / len(observable) if observable else None,
            "supported_rate": metrics["supported"] / len(comparable) if comparable else None,
            "partially_supported_rate": metrics["partially_supported"] / len(comparable) if comparable else None,
            "contradicted_rate": metrics["contradicted"] / len(comparable) if comparable else None,
            "insufficient_evidence_rate": metrics["insufficient_evidence"] / len(observable) if observable else None,
            "not_comparable_rate": metrics["not_comparable"] / len(observable) if observable else None,
            "reviewer_agreement": sum(item.get("reviewer_agreement") is True for item in agreement_records) / len(agreement_records) if agreement_records else None,
            "adjudication_rate": len(adjudicated_records) / len(records) if records else None,
            "brier_score": brier,
            "ece": ece,
            "calibration_sample_size": len(calibrated),
            "claim_weighted_score": metrics["lenient_score"],
            "person_weighted_score": (
                sum(sum(values) / len(values) for values in by_person.values()) / len(by_person) if by_person else None
            ),
            "domain_metrics": _group_metrics(records, "domain"),
            "scenario_metrics": _group_metrics(records, "scenario_id"),
            "gold_metrics": _basic_metrics([item for item in records if item.get("evidence_tier") == "gold"]),
            "silver_metrics": _basic_metrics([item for item in records if item.get("evidence_tier") == "silver"]),
        }
    )
    return metrics
