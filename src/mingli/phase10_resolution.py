from __future__ import annotations

from typing import Sequence

from .phase10_contracts import PatternCandidateResult, PatternConflictRecord, PatternProfile, record_digest


def candidate_rank(candidate: PatternCandidateResult, profile: PatternProfile) -> tuple[int, int, int]:
    source = candidate.candidate.source_kind
    try:
        source_rank = len(profile.candidate_source_order) - profile.candidate_source_order.index(source)
    except ValueError:
        source_rank = 0
    ordinal_rank = profile.hidden_stem_priority.get(str(candidate.candidate.hidden_stem_ordinal), 0)
    transparent_rank = 1 if candidate.candidate.is_transparent else 0
    return source_rank, ordinal_rank, transparent_rank


def resolve_candidate_conflicts(
    candidates: Sequence[PatternCandidateResult], profile: PatternProfile
) -> tuple[tuple[PatternConflictRecord, ...], tuple[str, ...]]:
    eligible = [
        item for item in candidates
        if item.status in {"supported", "conditionally_supported", "weakened"}
    ]
    if not eligible:
        return (), ()
    best_rank = max(candidate_rank(item, profile) for item in eligible)
    primary = tuple(sorted(item.candidate_id for item in eligible if candidate_rank(item, profile) == best_rank))
    conflicts: list[PatternConflictRecord] = []
    ordered = sorted(eligible, key=lambda item: item.candidate_id)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            left_rank = candidate_rank(left, profile)
            right_rank = candidate_rank(right, profile)
            equal = left_rank == right_rank
            winners = tuple(sorted((left.candidate_id, right.candidate_id))) if equal else (
                left.candidate_id if left_rank > right_rank else right.candidate_id,
            )
            payload = {
                "conflict_id": f"conflict:{left.candidate_id}|{right.candidate_id}",
                "candidate_ids": [left.candidate_id, right.candidate_id],
                "resolution_status": "unresolved" if equal else "resolved",
                "winning_candidate_ids": list(winners),
                "resolution_rule": "equal_rank_conflict_is_unresolved" if equal else "profile_candidate_source_and_transparency_rank",
                "retained_breaking_evidence_ids": sorted(
                    evidence_id
                    for item in (left, right)
                    for evidence_id in item.evidence_ids
                    if ":breaking:" in evidence_id
                ),
            }
            conflicts.append(PatternConflictRecord(canonical_digest=record_digest("PatternConflictRecord", payload), **payload))  # type: ignore[arg-type]
    return tuple(conflicts), primary
