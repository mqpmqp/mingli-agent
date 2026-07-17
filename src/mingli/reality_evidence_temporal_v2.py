"""Shared fail-closed availability checks for direct V2 Reality Evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime


class RealityEvidenceTemporalError(ValueError):
    """Raised when declared evidence time metadata permits future leakage."""


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RealityEvidenceTemporalError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RealityEvidenceTemporalError(
            f"{field} must be an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RealityEvidenceTemporalError(f"{field} must include a timezone")
    return parsed


def _event_window(value: object, *, field: str) -> tuple[datetime, datetime]:
    if not isinstance(value, str) or value.count("/") != 1:
        raise RealityEvidenceTemporalError(
            f"{field} must contain ISO start/end timestamps"
        )
    start_raw, end_raw = value.split("/", 1)
    start = _parse_timestamp(start_raw, field=f"{field}.start")
    end = _parse_timestamp(end_raw, field=f"{field}.end")
    if end < start:
        raise RealityEvidenceTemporalError(f"{field} end precedes start")
    return start, end


def validate_reality_evidence_availability(
    records: Sequence[Mapping[str, object]],
    *,
    evaluation_at: object,
    field: str,
    require_completed_window: bool = False,
) -> None:
    """Validate declared event, observation, collection, and evaluation ordering."""

    if not records and evaluation_at is None:
        return
    if evaluation_at is None:
        raise RealityEvidenceTemporalError(
            f"{field} requires evaluation_at when evidence is supplied"
        )
    evaluation = _parse_timestamp(evaluation_at, field="evaluation_at")
    for record in records:
        evidence_id = record.get("evidence_id")
        prefix = f"{field} {evidence_id!r}"
        start, end = _event_window(
            record.get("event_window"), field=f"{prefix}.event_window"
        )
        observed = _parse_timestamp(
            record.get("observed_at"), field=f"{prefix}.observed_at"
        )
        collected = _parse_timestamp(
            record.get("collected_at"), field=f"{prefix}.collected_at"
        )
        if observed < start:
            raise RealityEvidenceTemporalError(
                f"{prefix} observed_at precedes event_window start"
            )
        if collected < observed:
            raise RealityEvidenceTemporalError(
                f"{prefix} collected_at precedes observed_at"
            )
        if observed > evaluation or collected > evaluation:
            raise RealityEvidenceTemporalError(
                f"{prefix} is available after evaluation_at"
            )
        if require_completed_window and end > evaluation:
            raise RealityEvidenceTemporalError(
                f"{prefix} prior event_window ends after evaluation_at"
            )


__all__ = [
    "RealityEvidenceTemporalError",
    "validate_reality_evidence_availability",
]
