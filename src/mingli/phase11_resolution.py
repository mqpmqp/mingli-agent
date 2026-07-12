from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from .phase11_contracts import CandidateConflictRecord, YongShenCandidate, record_digest
from .phase11_profiles import DEFAULT_PHASE11_PROFILE_ID

STATUS_PRIORITY = {
    "supported": 6,
    "conditionally_supported": 5,
    "secondary": 4,
    "conflicted": 3,
    "unresolved": 2,
    "contradicted": 1,
    "unavailable": 0,
}


def candidate_rank(candidate: YongShenCandidate) -> tuple[int, Decimal, int]:
    consensus = len(candidate.supporting_lenses)
    return STATUS_PRIORITY.get(candidate.status, 0), Decimal(candidate.combined_score), consensus


def build_candidate_conflicts(
    candidates: Sequence[YongShenCandidate],
    evidence_ids_by_candidate: Mapping[str, Sequence[str]],
    *,
    profile_id: str = DEFAULT_PHASE11_PROFILE_ID,
) -> tuple[CandidateConflictRecord, ...]:
    conflicts: list[CandidateConflictRecord] = []
    for candidate in sorted(candidates, key=lambda item: item.candidate_id):
        if not candidate.supporting_lenses or not candidate.contradicting_lenses:
            continue
        payload = {
            "conflict_id": f"candidate-conflict:{candidate.candidate_id}:cross-lens",
            "candidate_ids": [candidate.candidate_id],
            "lenses": sorted(set(candidate.supporting_lenses) | set(candidate.contradicting_lenses)),
            "conflict_type": "cross_lens_candidate_contradiction",
            "resolution_status": "unresolved" if candidate.status == "unresolved" else "resolved",
            "winning_candidate_ids": [] if candidate.status in {"unresolved", "contradicted"} else [candidate.candidate_id],
            "resolution_rule": "profile_lens_priority_with_counterevidence_retained",
            "retained_evidence_ids": sorted(evidence_ids_by_candidate.get(candidate.candidate_id, ())),
        }
        conflicts.append(CandidateConflictRecord(canonical_digest=record_digest("CandidateConflictRecord", payload), **payload))  # type: ignore[arg-type]
    eligible = [
        item for item in candidates
        if item.status in {"supported", "conditionally_supported", "secondary", "conflicted"}
    ]
    if len(eligible) >= 2:
        ranks = {item.candidate_id: candidate_rank(item) for item in eligible}
        best = max(ranks.values())
        best_ids = sorted(candidate_id for candidate_id, rank in ranks.items() if rank == best)
        if len(best_ids) > 1:
            payload = {
                "conflict_id": "candidate-conflict:equal-rank-top-candidates",
                "candidate_ids": best_ids,
                "lenses": sorted({lens for item in eligible if item.candidate_id in best_ids for lens in item.supporting_lenses}),
                "conflict_type": "equal_rank_candidate_conflict",
                "resolution_status": "unresolved",
                "winning_candidate_ids": [],
                "resolution_rule": "equal_rank_conflict_is_unresolved",
                "retained_evidence_ids": sorted({evidence_id for candidate_id in best_ids for evidence_id in evidence_ids_by_candidate.get(candidate_id, ())}),
            }
            conflicts.append(CandidateConflictRecord(canonical_digest=record_digest("CandidateConflictRecord", payload), **payload))  # type: ignore[arg-type]
    return tuple(sorted(conflicts, key=lambda item: item.conflict_id))


def primary_candidate_ids(candidates: Sequence[YongShenCandidate]) -> tuple[str, ...]:
    supported = [item for item in candidates if item.status == "supported"]
    if supported:
        best = max(candidate_rank(item) for item in supported)
        return tuple(sorted(item.candidate_id for item in supported if candidate_rank(item) == best))
    conditional = [item for item in candidates if item.status == "conditionally_supported"]
    if conditional:
        best = max(candidate_rank(item) for item in conditional)
        return tuple(sorted(item.candidate_id for item in conditional if candidate_rank(item) == best))
    return ()
