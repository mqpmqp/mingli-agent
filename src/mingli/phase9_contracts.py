from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase8_contracts import EvidenceRecord as Phase8EvidenceRecord

PHASE9_SCHEMA_VERSION = "bazi-strength-quantification-result@0.1"
PHASE9_METHOD_ID = "bazi-strength-quantification@0.1.0"
PHASE9_CALCULATION_VERSION = "0.1.0"
PHASE9_DECISION_ID = "PHASE_9_BAZI_STRENGTH_QUANTIFICATION_R1_APPROVED"

CLASSIFICATIONS = frozenset({"very_weak", "weak", "balanced", "strong", "very_strong", "unresolved"})
ELEMENTS = ("wood", "fire", "earth", "metal", "water")
SUPPORT_DIRECTIONS = frozenset({"support", "oppose", "neutral"})


class Phase9InputError(ValueError):
    """Raised when Phase 9 cannot safely evaluate an input fact graph."""


def _decimal_string(value: Decimal | str | int) -> str:
    return format(Decimal(str(value)), "f")


def _plain_dataclass(value: object) -> dict[str, object]:
    def convert(item: object) -> object:
        if isinstance(item, Decimal):
            return _decimal_string(item)
        if isinstance(item, Mapping):
            return {str(key): convert(child) for key, child in item.items()}
        if isinstance(item, tuple | list):
            return [convert(child) for child in item]
        return item

    return json.loads(canonical_json(convert(asdict(value))))


def _record_digest(record_type: str, payload: Mapping[str, object]) -> str:
    body = {key: value for key, value in payload.items() if key not in {"canonical_digest", "canonical_hash"}}
    return digest({"record_type": record_type, "payload": body})


@dataclass(frozen=True)
class StrengthProfile:
    profile_id: str
    version: str
    convention_summary: str
    reviewed: bool
    weights: Mapping[str, object]
    classification_thresholds: tuple[Mapping[str, object], ...]
    source_ids: tuple[str, ...]
    independence_groups: tuple[str, ...]
    explicit_exclusions: tuple[str, ...]
    unresolved_conditions: tuple[str, ...]
    compatibility_version: str
    quantity: Mapping[str, object]
    toggles: Mapping[str, object]
    same_type_relations: tuple[str, ...]
    different_type_relations: tuple[str, ...]
    canonical_hash: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)

@dataclass(frozen=True)
class ElementContribution:
    contribution_id: str
    contribution_type: str
    element: str
    relationship_to_day_master: Literal["peer", "resource", "output", "wealth", "authority"]
    direction: Literal["support", "oppose"]
    score: str
    source_node_ids: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class RootContribution:
    contribution_id: str
    branch_position: str
    branch: str
    hidden_stem: str
    hidden_stem_ordinal: int
    root_level: Literal["principal", "middle", "residual"]
    element: str
    score: str
    source_node_ids: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class SeasonalContribution:
    contribution_id: str
    month_branch: str
    hidden_stem: str
    hidden_stem_ordinal: int
    element: str
    relationship_to_day_master: Literal["peer", "resource", "output", "wealth", "authority"]
    direction: Literal["support", "oppose"]
    score: str
    source_node_ids: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class StemContribution:
    contribution_id: str
    position: str
    stem: str
    element: str
    relationship_to_day_master: Literal["peer", "resource", "output", "wealth", "authority"]
    direction: Literal["support", "oppose"]
    score: str
    source_node_ids: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class BranchContribution:
    contribution_id: str
    position: str
    branch: str
    hidden_stem: str
    hidden_stem_ordinal: int
    element: str
    relationship_to_day_master: Literal["peer", "resource", "output", "wealth", "authority"]
    direction: Literal["support", "oppose"]
    score: str
    source_node_ids: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class SupportOppositionSummary:
    support_score: str
    opposition_score: str
    support_ratio: str
    opposition_ratio: str
    net_score: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class StrengthEvidenceRecord:
    evidence_id: str
    claim_id: str
    source_type: str
    source_node_ids: tuple[str, ...]
    direction: Literal["support", "contradict"]
    contribution: str
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)

    def to_phase8_evidence(self) -> Phase8EvidenceRecord:
        return Phase8EvidenceRecord(
            evidence_id=self.evidence_id,
            claim_id=self.claim_id,
            source_type="rule",
            source_id=self.evidence_id,
            detail=f"Phase 9 deterministic strength evidence from {self.source_type}",
            direction=self.direction,
            weight=float(Decimal(self.contribution)),
            priority=50,
            verified=True,
            canonical_digest=_record_digest("Phase8EvidenceRecordFromPhase9", self.to_dict()),
        )


@dataclass(frozen=True)
class DayMasterStrengthResult:
    day_master: str
    day_master_element: str
    profile_id: str
    element_scores: Mapping[str, str]
    support_score: str
    opposition_score: str
    support_ratio: str
    opposition_ratio: str
    net_score: str
    classification: Literal["very_weak", "weak", "balanced", "strong", "very_strong", "unresolved"]
    classification_band: Mapping[str, object]
    seasonal_state: Mapping[str, object]
    roots: tuple[Mapping[str, object], ...]
    visible_stems: tuple[Mapping[str, object], ...]
    hidden_stems: tuple[Mapping[str, object], ...]
    contribution_records: tuple[Mapping[str, object], ...]
    supporting_evidence: tuple[Mapping[str, object], ...]
    contradicting_evidence: tuple[Mapping[str, object], ...]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE9_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE9_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE9_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "day_master": self.day_master,
            "day_master_element": self.day_master_element,
            "profile_id": self.profile_id,
            "element_scores": dict(self.element_scores),
            "support_score": self.support_score,
            "opposition_score": self.opposition_score,
            "support_ratio": self.support_ratio,
            "opposition_ratio": self.opposition_ratio,
            "net_score": self.net_score,
            "classification": self.classification,
            "classification_band": dict(self.classification_band),
            "seasonal_state": dict(self.seasonal_state),
            "roots": list(self.roots),
            "visible_stems": list(self.visible_stems),
            "hidden_stems": list(self.hidden_stems),
            "contribution_records": list(self.contribution_records),
            "supporting_evidence": list(self.supporting_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
            "warnings": list(self.warnings),
            "unresolved": list(self.unresolved),
            "canonical_hash": self.canonical_hash,
            "schema_version": self.schema_version,
            "method_id": self.method_id,
            "calculation_version": self.calculation_version,
            "prediction_validity": self.prediction_validity,
        }


@dataclass(frozen=True)
class Phase9BenchmarkResult:
    assertions_total: int
    profile_assertions: int
    element_assertions: int
    seasonal_assertions: int
    contribution_assertions: int
    classification_assertions: int
    deterministic_assertions: int
    blocked_assertions: int
    passed: int
    failed: int
    unresolved: int
    schema_failures: int
    provenance_failures: int
    hash_mismatches: int
    threshold_gaps: int
    threshold_overlaps: int
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)
