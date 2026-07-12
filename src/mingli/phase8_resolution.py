from __future__ import annotations

from typing import Literal, Mapping, Sequence

from .confidence import evaluate_confidence
from .evidence import fuse_evidence
from .reality import apply_reality_overrides
from .phase8_contracts import (
    ClaimResolution,
    ConfidenceInputRecord,
    ConflictRecord,
    EvaluationRule,
    EvidenceRecord,
    RealityOverrideRecord,
    _record_digest,
)


def _reality_override_records(
    intent: str,
    reality: Mapping[str, object],
    chart_signals: Sequence[str],
    rules: Sequence[EvaluationRule],
    active_claim_ids: frozenset[str],
) -> tuple[tuple[RealityOverrideRecord, ...], tuple[EvidenceRecord, ...]]:
    records: list[RealityOverrideRecord] = []
    evidence: list[EvidenceRecord] = []
    for override in sorted(apply_reality_overrides(intent, reality, chart_signals), key=lambda item: item.code):
        target_claims = tuple(sorted({
            rule.claim_id
            for rule in rules
            if rule.claim_id in active_claim_ids and override.code in rule.reality_override_codes
        }))
        emitted_ids: list[str] = []
        for claim_id in target_claims:
            evidence_id = f"reality-evidence:{override.code}:{claim_id}:contradict"
            payload = {
                "evidence_id": evidence_id,
                "claim_id": claim_id,
                "source_type": "reality",
                "source_id": override.code,
                "detail": override.message,
                "direction": "contradict",
                "weight": 10.0,
                "priority": 100,
                "verified": True,
            }
            evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    claim_id=claim_id,
                    source_type="reality",
                    source_id=override.code,
                    detail=override.message,
                    direction="contradict",
                    weight=10.0,
                    priority=100,
                    verified=True,
                    canonical_digest=_record_digest("EvidenceRecord", payload),
                )
            )
            emitted_ids.append(evidence_id)
        override_id = f"reality-override:{override.code}"
        payload = {
            "override_id": override_id,
            "code": override.code,
            "message": override.message,
            "direction": "contradict",
            "target_claim_ids": list(target_claims),
            "emitted_evidence_ids": emitted_ids,
            "verified": True,
        }
        records.append(
            RealityOverrideRecord(
                override_id,
                override.code,
                override.message,
                "contradict",
                target_claims,
                tuple(emitted_ids),
                True,
                _record_digest("RealityOverrideRecord", payload),
            )
        )
    return tuple(records), tuple(evidence)


def _resolve_claim(
    claim_id: str,
    claim_text: str,
    records: Sequence[EvidenceRecord],
    *,
    missing_information: bool,
    image_unconfirmed: bool,
    single_symbol: bool,
    high_stakes: str | None,
) -> tuple[ClaimResolution, ConflictRecord | None, ConfidenceInputRecord]:
    ordered = tuple(sorted(records, key=lambda item: (-item.priority, item.evidence_id)))
    support = tuple(item for item in ordered if item.direction == "support")
    contradict = tuple(item for item in ordered if item.direction == "contradict")
    fusion = fuse_evidence(item.to_model() for item in ordered)
    conflict: ConflictRecord | None = None
    if support and contradict:
        if fusion.hard_override_direction:
            resolution_status = "resolved_by_reality_override"
            winner = fusion.hard_override_direction
            rationale = "verified reality evidence hard-overrides ordinary rule evidence"
        else:
            support_priority = max(item.priority for item in support)
            contradict_priority = max(item.priority for item in contradict)
            if support_priority != contradict_priority:
                resolution_status = "resolved_by_priority"
                winner = "support" if support_priority > contradict_priority else "contradict"
                rationale = "higher-priority evidence wins while the conflict remains recorded"
            else:
                resolution_status = "unresolved_conflict"
                winner = None
                rationale = "opposing evidence has equal top priority and no verified reality override"
        conflict_id = f"conflict:{claim_id}"
        conflict_payload = {
            "conflict_id": conflict_id,
            "claim_id": claim_id,
            "support_evidence_ids": [item.evidence_id for item in support],
            "contradict_evidence_ids": [item.evidence_id for item in contradict],
            "resolution_status": resolution_status,
            "winning_direction": winner,
            "rationale": rationale,
        }
        conflict = ConflictRecord(
            conflict_id,
            claim_id,
            tuple(item.evidence_id for item in support),
            tuple(item.evidence_id for item in contradict),
            resolution_status,
            winner,
            rationale,
            _record_digest("ConflictRecord", conflict_payload),
        )
    elif support:
        resolution_status = "supported"
        winner = "support"
    elif contradict:
        resolution_status = "contradicted"
        winner = "contradict"
    else:
        resolution_status = "no_evidence"
        winner = None

    unresolved_conflict = resolution_status == "unresolved_conflict"
    if fusion.hard_override_direction:
        confidence_level = "high"
        confidence_rationale = "verified reality evidence is a hard override"
        confidence_scope = "现实处置" if high_stakes in {"medical", "investment"} else "命理辅助判断"
    elif unresolved_conflict:
        confidence_level = "low"
        confidence_rationale = "equal-priority opposing evidence remains unresolved"
        confidence_scope = "命理辅助判断"
    elif conflict is not None:
        confidence_level = "medium"
        confidence_rationale = "conflicting evidence was deterministically resolved by priority"
        confidence_scope = "命理辅助判断"
    else:
        decision = evaluate_confidence(
            (item.to_model() for item in ordered),
            missing_information=missing_information,
            image_unconfirmed=image_unconfirmed,
            single_symbol=single_symbol,
            high_stakes=high_stakes,
        )
        confidence_level = decision.level
        confidence_rationale = decision.rationale
        confidence_scope = decision.scope
    confidence_payload = {
        "claim_id": claim_id,
        "level": confidence_level,
        "rationale": confidence_rationale,
        "scope": confidence_scope,
        "support_count": len(support),
        "contradict_count": len(contradict),
        "verified_reality_count": sum(item.source_type == "reality" and item.verified for item in ordered),
        "unresolved_conflict": unresolved_conflict,
    }
    confidence = ConfidenceInputRecord(
        claim_id,
        confidence_level,  # type: ignore[arg-type]
        confidence_rationale,
        confidence_scope,
        len(support),
        len(contradict),
        int(confidence_payload["verified_reality_count"]),
        unresolved_conflict,
        _record_digest("ConfidenceInputRecord", confidence_payload),
    )
    final_direction: Literal["support", "contradict", "unresolved", "none"]
    if winner in {"support", "contradict"}:
        final_direction = winner  # type: ignore[assignment]
    elif unresolved_conflict:
        final_direction = "unresolved"
    else:
        final_direction = "none"
    conflict_ids = (conflict.conflict_id,) if conflict else ()
    resolution_payload = {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "final_direction": final_direction,
        "resolution_status": resolution_status,
        "support_score": fusion.support_score,
        "contradict_score": fusion.contradict_score,
        "hard_override_direction": fusion.hard_override_direction,
        "evidence_ids": [item.evidence_id for item in ordered],
        "conflict_ids": list(conflict_ids),
        "confidence": confidence.to_dict(),
    }
    resolution = ClaimResolution(
        claim_id,
        claim_text,
        final_direction,
        resolution_status,
        fusion.support_score,
        fusion.contradict_score,
        fusion.hard_override_direction,
        tuple(item.evidence_id for item in ordered),
        conflict_ids,
        confidence.to_dict(),
        _record_digest("ClaimResolution", resolution_payload),
    )
    return resolution, conflict, confidence
