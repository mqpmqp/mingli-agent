from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Sequence

from .contracts.serialization import digest


def assess_review_coverage(reviews: Sequence[Mapping[str, object]], *, required_reviewers: int) -> dict[str, object]:
    human_ids = {
        str(item.get("reviewer_id"))
        for item in reviews
        if item.get("reviewer_role") == "human" and item.get("reviewer_id")
    }
    scores = {str(item.get("score")) for item in reviews if item.get("score")}
    disagreement = len(scores) > 1
    adjudicated = any(item.get("reviewer_role") == "adjudicator" and item.get("final_status") for item in reviews)
    failures: list[str] = []
    if len(human_ids) < required_reviewers:
        failures.append("insufficient_human_reviewer_coverage")
    if disagreement and not adjudicated:
        failures.append("reviewer_disagreement_requires_adjudication")
    return {
        "passed": not failures,
        "human_reviewer_count": len(human_ids),
        "disagreement": disagreement,
        "adjudicated": adjudicated,
        "failures": failures,
    }


def adjudicate_reviews(
    reviews: Sequence[Mapping[str, object]],
    *,
    adjudicator_id: str,
    final_status: str,
    reason: str,
) -> dict[str, object]:
    if not adjudicator_id.startswith("adjudicator:") or not reason.strip():
        raise ValueError("independent adjudicator id and reason are required")
    claim_ids = {str(item.get("claim_id")) for item in reviews}
    if len(claim_ids) != 1:
        raise ValueError("all reviews must refer to one claim")
    if final_status not in {"supported", "partially_supported", "contradicted", "not_comparable", "insufficient_evidence", "excluded_by_contract"}:
        raise ValueError("unsupported final_status")
    body = {
        "claim_id": next(iter(claim_ids)),
        "adjudicator_id": adjudicator_id,
        "final_status": final_status,
        "reason": reason,
        "review_hashes": [digest(item) for item in reviews],
        "adjudicated_at": datetime.now(timezone.utc).isoformat(),
        "disagreement_resolved": len({str(item.get('score')) for item in reviews}) > 1,
    }
    return {**body, "canonical_hash": digest({"record_type": "Adjudication", "payload": body})}
