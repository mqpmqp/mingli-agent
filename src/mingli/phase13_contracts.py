from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase8_contracts import EvidenceRecord as Phase8EvidenceRecord

PHASE13_SCHEMA_VERSION = "bazi-luck-cycle-role-interaction-result@0.1"
PHASE13_METHOD_ID = "bazi-luck-cycle-role-interaction@0.1.0"
PHASE13_CALCULATION_VERSION = "0.1.0"
PHASE13_DECISION_ID = "PHASE_13_BAZI_LUCK_CYCLE_ROLE_INTERACTION_R1_APPROVED"
STRUCTURAL_STATES = ("aligned", "mixed", "opposed", "neutral", "unresolved")


class Phase13InputError(ValueError):
    """Raised when Phase 13 cannot safely evaluate timeline-role interactions."""


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
class CycleRoleHit:
    hit_id: str
    period_id: str
    source_type: Literal["stem", "branch_hidden"]
    source_symbol: str
    ordinal: int
    element: str
    role: str
    direction: Literal["support", "conflict", "neutral", "unresolved"]
    base_weight: str
    role_multiplier: str
    weighted_score: str
    source_assignment_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class NatalRelationRecord:
    relation_id: str
    period_id: str
    source_symbol_type: Literal["stem", "branch"]
    source_symbol: str
    natal_position: str
    natal_symbol: str
    relation_types: tuple[str, ...]
    relation_statuses: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class PeriodRoleInteraction:
    interaction_id: str
    period_id: str
    period_type: Literal["dayun", "liunian"]
    sequence_index: int | None
    label_year: int | None
    dayun_period_id: str | None
    ganzhi: str
    stem: str
    branch: str
    start_instant_utc: str
    end_instant_utc: str
    role_hits: tuple[CycleRoleHit, ...]
    support_score: str
    conflict_score: str
    neutral_score: str
    unresolved_count: int
    structural_state: Literal["aligned", "mixed", "opposed", "neutral", "unresolved"]
    natal_relations: tuple[NatalRelationRecord, ...]
    source_result_hashes: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class CombinedCycleWindow:
    window_id: str
    dayun_period_id: str
    liunian_period_id: str
    start_instant_utc: str
    end_instant_utc: str
    dayun_ganzhi: str
    liunian_ganzhi: str
    support_score: str
    conflict_score: str
    neutral_score: str
    unresolved_count: int
    stem_relation_types: tuple[str, ...]
    branch_relation_types: tuple[str, ...]
    structural_state: Literal["aligned", "mixed", "opposed", "neutral", "unresolved"]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class CycleInteractionEvidenceRecord:
    evidence_id: str
    period_id: str
    element: str
    role: str
    evidence_type: str
    direction: Literal["support", "contradict"]
    contribution: str
    priority: int
    source_result_hashes: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)

    def to_phase8_evidence(self) -> Phase8EvidenceRecord:
        return Phase8EvidenceRecord(
            evidence_id=self.evidence_id,
            claim_id=f"bazi-cycle-role:{self.period_id}:{self.element}:{self.role}",
            source_type="rule",
            source_id=self.evidence_id,
            detail=f"Phase 13 deterministic timeline-role evidence for {self.period_id}",
            direction=self.direction,
            weight=float(Decimal(self.contribution)),
            priority=self.priority,
            verified=True,
            canonical_digest=record_digest("Phase8EvidenceRecordFromPhase13", self.to_dict()),
        )


@dataclass(frozen=True)
class BaziLuckCycleRoleInteractionResult:
    fact_graph_hash: str
    xiji_result_hash: str
    profile_id: str
    dayun_interactions: tuple[PeriodRoleInteraction, ...]
    liunian_interactions: tuple[PeriodRoleInteraction, ...]
    combined_windows: tuple[CombinedCycleWindow, ...]
    state_counts: Mapping[str, int]
    evidence_records: tuple[CycleInteractionEvidenceRecord, ...]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE13_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE13_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE13_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "fact_graph_hash": self.fact_graph_hash,
            "xiji_result_hash": self.xiji_result_hash,
            "profile_id": self.profile_id,
            "dayun_interactions": [item.to_dict() for item in self.dayun_interactions],
            "liunian_interactions": [item.to_dict() for item in self.liunian_interactions],
            "combined_windows": [item.to_dict() for item in self.combined_windows],
            "state_counts": dict(self.state_counts),
            "evidence_records": [item.to_dict() for item in self.evidence_records],
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
class Phase13BenchmarkResult:
    assertions_total: int
    passed: int
    failed: int
    unresolved: int
    schema_failures: int
    provenance_failures: int
    hash_mismatches: int
    timeline_failures: int
    partition_failures: int
    relation_failures: int
    prediction_boundary_failures: int
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain(self)
