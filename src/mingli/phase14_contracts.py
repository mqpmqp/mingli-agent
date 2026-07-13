from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase8_contracts import EvidenceRecord as Phase8EvidenceRecord

PHASE14_SCHEMA_VERSION = "bazi-temporal-trend-evidence-result@0.1"
PHASE14_METHOD_ID = "bazi-temporal-trend-evidence@0.1.0"
PHASE14_CALCULATION_VERSION = "0.1.0"
PHASE14_DECISION_ID = "PHASE_14_BAZI_TEMPORAL_TREND_EVIDENCE_R1_APPROVED"
TREND_LABELS = (
    "support_tendency",
    "conflict_tendency",
    "mixed_tendency",
    "neutral_tendency",
    "unresolved",
)
TARGET_TYPES = ("dayun", "liunian", "combined_window")
TRANSITION_TYPES = (
    "strengthening_support",
    "strengthening_conflict",
    "entering_mixed",
    "leaving_mixed",
    "becoming_unresolved",
    "resolving",
    "stable",
)


class Phase14InputError(ValueError):
    """Raised when Phase 14 cannot safely derive temporal trend evidence."""


def _convert(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(key): _convert(child) for key, child in value.items()}
    if isinstance(value, tuple | list):
        return [_convert(child) for child in value]
    return value


def _plain(value: object) -> dict[str, object]:
    return json.loads(canonical_json(_convert(asdict(value))))


def record_digest(record_type: str, payload: Mapping[str, object]) -> str:
    body = {key: value for key, value in payload.items() if key not in {"canonical_digest", "canonical_hash"}}
    return digest({"record_type": record_type, "payload": body})


@dataclass(frozen=True)
class TemporalRealityEvidenceRecord:
    evidence_id: str
    target_id: str
    direction: Literal["support", "contradict"]
    detail: str
    weight: str
    verified: bool
    source_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class TemporalTrendRecord:
    trend_id: str
    target_id: str
    target_type: Literal["dayun", "liunian", "combined_window"]
    sequence_index: int | None
    label_year: int | None
    start_instant_utc: str
    end_instant_utc: str
    start_age: int | None
    end_age: int | None
    structural_state: str
    base_support_score: str
    base_conflict_score: str
    base_neutral_score: str
    support_ratio: str
    conflict_ratio: str
    neutral_ratio: str
    net_balance: str
    intensity: str
    trend_label: Literal[
        "support_tendency",
        "conflict_tendency",
        "mixed_tendency",
        "neutral_tendency",
        "unresolved",
    ]
    confidence: Literal["high", "medium", "low"]
    confidence_rationale_codes: tuple[str, ...]
    reality_override_direction: Literal["support", "contradict"] | None
    reality_evidence_ids: tuple[str, ...]
    source_record_digest: str
    source_result_hashes: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class TrendTransitionRecord:
    transition_id: str
    target_type: Literal["dayun", "liunian", "combined_window"]
    from_target_id: str
    to_target_id: str
    from_label: str
    to_label: str
    net_delta: str
    intensity_delta: str
    transition_type: Literal[
        "strengthening_support",
        "strengthening_conflict",
        "entering_mixed",
        "leaving_mixed",
        "becoming_unresolved",
        "resolving",
        "stable",
    ]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class TemporalTrendEvidenceRecord:
    evidence_id: str
    target_id: str
    evidence_type: str
    source_type: Literal["timing", "reality", "rule"]
    direction: Literal["support", "contradict"]
    contribution: str
    priority: int
    verified: bool
    source_id: str
    source_result_hashes: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)

    def to_phase8_evidence(self) -> Phase8EvidenceRecord:
        return Phase8EvidenceRecord(
            evidence_id=self.evidence_id,
            claim_id=f"bazi-temporal-trend:{self.target_id}",
            source_type=self.source_type,
            source_id=self.source_id,
            detail=f"Phase 14 deterministic temporal trend evidence for {self.target_id}",
            direction=self.direction,
            weight=float(Decimal(self.contribution)),
            priority=self.priority,
            verified=self.verified,
            canonical_digest=record_digest("Phase8EvidenceRecordFromPhase14", self.to_dict()),
        )


@dataclass(frozen=True)
class BaziTemporalTrendEvidenceResult:
    fact_graph_hash: str
    interaction_result_hash: str
    profile_id: str
    dayun_trends: tuple[TemporalTrendRecord, ...]
    liunian_trends: tuple[TemporalTrendRecord, ...]
    combined_trends: tuple[TemporalTrendRecord, ...]
    transitions: tuple[TrendTransitionRecord, ...]
    reality_evidence: tuple[TemporalRealityEvidenceRecord, ...]
    evidence_records: tuple[TemporalTrendEvidenceRecord, ...]
    year_index: Mapping[str, tuple[str, ...]]
    age_index: Mapping[str, tuple[str, ...]]
    trend_counts: Mapping[str, int]
    confidence_counts: Mapping[str, int]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE14_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE14_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE14_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "fact_graph_hash": self.fact_graph_hash,
            "interaction_result_hash": self.interaction_result_hash,
            "profile_id": self.profile_id,
            "dayun_trends": [item.to_dict() for item in self.dayun_trends],
            "liunian_trends": [item.to_dict() for item in self.liunian_trends],
            "combined_trends": [item.to_dict() for item in self.combined_trends],
            "transitions": [item.to_dict() for item in self.transitions],
            "reality_evidence": [item.to_dict() for item in self.reality_evidence],
            "evidence_records": [item.to_dict() for item in self.evidence_records],
            "year_index": {key: list(value) for key, value in self.year_index.items()},
            "age_index": {key: list(value) for key, value in self.age_index.items()},
            "trend_counts": dict(self.trend_counts),
            "confidence_counts": dict(self.confidence_counts),
            "provenance_index": dict(self.provenance_index),
            "warnings": list(self.warnings),
            "unresolved": list(self.unresolved),
            "canonical_hash": self.canonical_hash,
            "schema_version": self.schema_version,
            "method_id": self.method_id,
            "calculation_version": self.calculation_version,
            "prediction_validity": self.prediction_validity,
        }


@dataclass(frozen=True)
class Phase14BenchmarkResult:
    assertions_total: int
    passed: int
    failed: int
    unresolved: int
    schema_failures: int
    provenance_failures: int
    hash_mismatches: int
    partition_failures: int
    query_failures: int
    transition_failures: int
    reality_override_failures: int
    prediction_boundary_failures: int
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain(self)
