from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase8_contracts import EvidenceRecord as Phase8EvidenceRecord

PHASE11_SCHEMA_VERSION = "bazi-regulation-yongshen-candidate-result@0.1"
PHASE11_METHOD_ID = "bazi-regulation-yongshen-candidate@0.1.0"
PHASE11_CALCULATION_VERSION = "0.1.0"
PHASE11_DECISION_ID = "PHASE_11_BAZI_REGULATION_YONGSHEN_CANDIDATE_R1_APPROVED"

REGULATION_LENSES = ("strength_balance", "seasonal_climate", "element_passage", "pattern_remedy")
CANDIDATE_STATUSES = frozenset(
    {"supported", "conditionally_supported", "secondary", "conflicted", "contradicted", "unavailable", "unresolved"}
)
AVAILABILITY_STATUSES = frozenset(
    {"absent", "hidden_only", "visible_unrooted", "visible_rooted", "rooted_hidden", "multiple_visible", "multiple_rooted"}
)


class Phase11InputError(ValueError):
    """Raised when Phase 11 cannot safely evaluate its inputs."""


def _convert(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(key): _convert(child) for key, child in value.items()}
    if isinstance(value, tuple | list):
        return [_convert(child) for child in value]
    return value


def _plain_dataclass(value: object) -> dict[str, object]:
    return json.loads(canonical_json(_convert(asdict(value))))


def record_digest(record_type: str, payload: Mapping[str, object]) -> str:
    body = {key: value for key, value in payload.items() if key not in {"canonical_digest", "canonical_hash"}}
    return digest({"record_type": record_type, "payload": body})


@dataclass(frozen=True)
class RegulationLensProfile:
    profile_id: str
    version: str
    lens: str
    reviewed: bool
    convention_summary: str
    applicable_inputs: tuple[str, ...]
    weights: Mapping[str, str]
    thresholds: Mapping[str, object]
    conflict_policy: tuple[str, ...]
    confidence_ceiling: str
    source_ids: tuple[str, ...]
    independence_groups: tuple[str, ...]
    explicit_exclusions: tuple[str, ...]
    unresolved_conditions: tuple[str, ...]
    compatibility_version: str
    canonical_hash: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class RegulationProfile:
    profile_id: str
    version: str
    reviewed: bool
    convention_summary: str
    lens_profiles: tuple[RegulationLensProfile, ...]
    score_precision: str
    ratio_precision: str
    rounding_mode: str
    candidate_thresholds: tuple[Mapping[str, object], ...]
    conflict_thresholds: Mapping[str, str]
    confidence_thresholds: Mapping[str, str]
    per_lens_weights: Mapping[str, str]
    availability_weights: Mapping[str, str]
    overcorrection_penalties: Mapping[str, str]
    fusion_policy: tuple[str, ...]
    source_ids: tuple[str, ...]
    independence_groups: tuple[str, ...]
    explicit_exclusions: tuple[str, ...]
    unresolved_conditions: tuple[str, ...]
    compatibility_version: str
    canonical_hash: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class RegulationNeed:
    need_id: str
    lens: str
    need_type: str
    target_elements: tuple[str, ...]
    severity: str
    description: str
    confidence_ceiling: str
    source_node_ids: tuple[str, ...]
    source_result_hashes: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class StrengthBalanceNeed(RegulationNeed):
    strength_classification: str
    day_master_element: str
    support_relationships: tuple[str, ...]


@dataclass(frozen=True)
class SeasonalClimateNeed(RegulationNeed):
    month_branch: str
    season: str
    cold_tendency: str
    heat_tendency: str
    dryness_tendency: str
    dampness_tendency: str
    contraindicated_overcorrections: tuple[str, ...]
    structural_seasonal_climate_status: Literal["evaluated"]
    classical_daymaster_month_tiaohou_status: Literal["not_evaluated", "unresolved"]
    explicit_exclusions: tuple[str, ...]


@dataclass(frozen=True)
class ElementPassageNeed(RegulationNeed):
    conflict_elements: tuple[str, str]
    blocked_chain: str
    mediator_element: str
    chain_before: tuple[str, ...]
    chain_after: tuple[str, ...]
    supporting_facts: tuple[str, ...]
    contradicting_facts: tuple[str, ...]
    availability: str


@dataclass(frozen=True)
class PatternRemedyNeed(RegulationNeed):
    pattern_candidate_id: str
    pattern_type: str
    pattern_status: str
    purity_score: str
    breaking_evidence_ids: tuple[str, ...]
    rescue_evidence_ids: tuple[str, ...]
    rescue_role: str


@dataclass(frozen=True)
class CandidateContribution:
    contribution_id: str
    candidate_id: str
    element: str
    stem_carrier: str | None
    lens: str
    direction: Literal["support", "contradict", "unresolved"]
    contribution_type: str
    score: str
    priority: int
    need_id: str
    source_node_ids: tuple[str, ...]
    source_result_hashes: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class CandidateAvailability:
    candidate_id: str
    element: str
    status: Literal[
        "absent", "hidden_only", "visible_unrooted", "visible_rooted", "rooted_hidden", "multiple_visible", "multiple_rooted"
    ]
    candidate_need: str
    candidate_presence: str
    candidate_accessibility: str
    candidate_excess_risk: str
    visible_positions: tuple[str, ...]
    hidden_positions: tuple[str, ...]
    root_positions: tuple[str, ...]
    source_node_ids: tuple[str, ...]
    source_result_hashes: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class YongShenCandidate:
    candidate_id: str
    element: str
    stem_carriers: tuple[str, ...]
    supporting_lenses: tuple[str, ...]
    contradicting_lenses: tuple[str, ...]
    score_by_lens: Mapping[str, str]
    combined_score: str
    balance_score: str
    climate_score: str
    passage_score: str
    remedy_score: str
    availability_score: str
    contradiction_score: str
    consensus_bonus: str
    unresolved_penalty: str
    availability: CandidateAvailability
    visible_positions: tuple[str, ...]
    hidden_positions: tuple[str, ...]
    root_positions: tuple[str, ...]
    strength_context: Mapping[str, object]
    pattern_context: Mapping[str, object]
    status: Literal[
        "supported", "conditionally_supported", "secondary", "conflicted", "contradicted", "unavailable", "unresolved"
    ]
    confidence_input: Mapping[str, object]
    source_node_ids: tuple[str, ...]
    source_result_hashes: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class CandidateConflictRecord:
    conflict_id: str
    candidate_ids: tuple[str, ...]
    lenses: tuple[str, ...]
    conflict_type: str
    resolution_status: Literal["resolved", "unresolved"]
    winning_candidate_ids: tuple[str, ...]
    resolution_rule: str
    retained_evidence_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class CandidateResolution:
    candidate_id: str
    status: str
    resolution_rule: str
    score_rank: int
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class RegulationEvidenceRecord:
    evidence_id: str
    candidate_id: str
    element: str
    stem_carrier: str | None
    lens: str
    evidence_type: str
    direction: Literal["support", "contradict"]
    contribution: str
    priority: int
    source_node_ids: tuple[str, ...]
    source_result_hashes: tuple[str, ...]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)

    def to_phase8_evidence(self) -> Phase8EvidenceRecord:
        return Phase8EvidenceRecord(
            evidence_id=self.evidence_id,
            claim_id=f"bazi-regulation:{self.candidate_id}",
            source_type="rule",
            source_id=self.evidence_id,
            detail=f"Phase 11 deterministic {self.evidence_type} evidence for {self.element}",
            direction=self.direction,
            weight=float(Decimal(self.contribution)),
            priority=self.priority,
            verified=True,
            canonical_digest=record_digest("Phase8EvidenceRecordFromPhase11", self.to_dict()),
        )


@dataclass(frozen=True)
class BaziRegulationEvaluationResult:
    fact_graph_hash: str
    strength_result_hash: str
    pattern_result_hash: str
    profile_id: str
    regulation_needs: tuple[Mapping[str, object], ...]
    strength_balance_needs: tuple[StrengthBalanceNeed, ...]
    seasonal_climate_needs: tuple[SeasonalClimateNeed, ...]
    element_passage_needs: tuple[ElementPassageNeed, ...]
    pattern_remedy_needs: tuple[PatternRemedyNeed, ...]
    candidates: tuple[YongShenCandidate, ...]
    primary_candidates: tuple[str, ...]
    secondary_candidates: tuple[str, ...]
    conflicted_candidates: tuple[str, ...]
    contradicted_candidates: tuple[str, ...]
    unresolved_candidates: tuple[str, ...]
    candidate_conflicts: tuple[CandidateConflictRecord, ...]
    evidence_records: tuple[RegulationEvidenceRecord, ...]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE11_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE11_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE11_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "fact_graph_hash": self.fact_graph_hash,
            "strength_result_hash": self.strength_result_hash,
            "pattern_result_hash": self.pattern_result_hash,
            "profile_id": self.profile_id,
            "regulation_needs": list(self.regulation_needs),
            "strength_balance_needs": [item.to_dict() for item in self.strength_balance_needs],
            "seasonal_climate_needs": [item.to_dict() for item in self.seasonal_climate_needs],
            "element_passage_needs": [item.to_dict() for item in self.element_passage_needs],
            "pattern_remedy_needs": [item.to_dict() for item in self.pattern_remedy_needs],
            "candidates": [item.to_dict() for item in self.candidates],
            "primary_candidates": list(self.primary_candidates),
            "secondary_candidates": list(self.secondary_candidates),
            "conflicted_candidates": list(self.conflicted_candidates),
            "contradicted_candidates": list(self.contradicted_candidates),
            "unresolved_candidates": list(self.unresolved_candidates),
            "candidate_conflicts": [item.to_dict() for item in self.candidate_conflicts],
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
class Phase11BenchmarkResult:
    assertions_total: int
    passed: int
    failed: int
    unresolved: int
    schema_failures: int
    provenance_failures: int
    hash_mismatches: int
    threshold_gaps: int
    threshold_overlaps: int
    conflict_order_failures: int
    unsupported_classical_claims: int
    xiji_boundary_failures: int
    coverage: Mapping[str, int]
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)
