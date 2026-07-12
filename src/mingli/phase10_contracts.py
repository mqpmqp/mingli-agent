from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase8_contracts import EvidenceRecord as Phase8EvidenceRecord

PHASE10_SCHEMA_VERSION = "bazi-pattern-evaluation-result@0.1"
PHASE10_METHOD_ID = "bazi-pattern-evaluation@0.1.0"
PHASE10_CALCULATION_VERSION = "0.1.0"
PHASE10_DECISION_ID = "PHASE_10_BAZI_PATTERN_EVALUATION_R1_APPROVED"

PATTERN_STATUSES = frozenset({"supported", "conditionally_supported", "weakened", "contradicted", "rejected", "unresolved"})
ORDINARY_PATTERN_TYPES = (
    "zheng_guan", "qi_sha", "zheng_yin", "pian_yin", "shi_shen",
    "shang_guan", "zheng_cai", "pian_cai",
)
SPECIAL_PATTERN_TYPES = (
    "cong_qiang_candidate", "cong_weak_candidate", "cong_cai_candidate",
    "cong_guan_sha_candidate", "cong_er_candidate", "hua_qi_candidate",
    "special_pattern_unresolved",
)
SUPPORTED_PATTERN_TYPES = ORDINARY_PATTERN_TYPES + ("jian_lu", "yang_ren") + SPECIAL_PATTERN_TYPES


class Phase10InputError(ValueError):
    """Raised when Phase 10 cannot safely evaluate its inputs."""


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
class PatternProfile:
    profile_id: str
    version: str
    reviewed: bool
    convention_summary: str
    candidate_source_order: tuple[str, ...]
    hidden_stem_priority: Mapping[str, int]
    establishment_weights: Mapping[str, str]
    break_weights: Mapping[str, str]
    rescue_weights: Mapping[str, str]
    purity_thresholds: tuple[Mapping[str, object], ...]
    primary_candidate_threshold: str
    conflict_resolution_order: tuple[str, ...]
    ordinary_pattern_rules: Mapping[str, object]
    jianlu_rules: Mapping[str, object]
    yangren_rules: Mapping[str, object]
    special_pattern_candidate_rules: Mapping[str, object]
    source_ids: tuple[str, ...]
    independence_groups: tuple[str, ...]
    explicit_exclusions: tuple[str, ...]
    unresolved_conditions: tuple[str, ...]
    compatibility_version: str
    canonical_hash: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class PatternSourceCandidate:
    candidate_id: str
    pattern_type: str
    month_branch: str
    hidden_stem: str | None
    hidden_stem_ordinal: int | None
    source_kind: str
    is_transparent: bool
    transparent_positions: tuple[str, ...]
    ten_god: str | None
    source_node_ids: tuple[str, ...]
    strength_result_hash: str
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class PatternCondition:
    condition_id: str
    condition_type: Literal["establishment", "breaking", "rescue", "unresolved"]
    description: str
    weight: str
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class PatternConditionResult:
    condition: PatternCondition
    outcome: Literal["met", "not_met", "unresolved"]
    observed_value: object
    source_node_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class EstablishmentEvidence:
    condition_result: PatternConditionResult

    def to_dict(self) -> dict[str, object]:
        return self.condition_result.to_dict()


@dataclass(frozen=True)
class BreakingEvidence:
    condition_result: PatternConditionResult

    def to_dict(self) -> dict[str, object]:
        return self.condition_result.to_dict()


@dataclass(frozen=True)
class RescueEvidence:
    condition_result: PatternConditionResult

    def to_dict(self) -> dict[str, object]:
        return self.condition_result.to_dict()


@dataclass(frozen=True)
class PatternEvidenceRecord:
    evidence_id: str
    candidate_id: str
    pattern_type: str
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
            claim_id=f"bazi-pattern:{self.candidate_id}",
            source_type="rule",
            source_id=self.evidence_id,
            detail=f"Phase 10 deterministic {self.evidence_type} evidence for {self.pattern_type}",
            direction=self.direction,
            weight=float(Decimal(self.contribution)),
            priority=self.priority,
            verified=True,
            canonical_digest=record_digest("Phase8EvidenceRecordFromPhase10", self.to_dict()),
        )


@dataclass(frozen=True)
class PatternConflictRecord:
    conflict_id: str
    candidate_ids: tuple[str, ...]
    resolution_status: Literal["resolved", "unresolved"]
    winning_candidate_ids: tuple[str, ...]
    resolution_rule: str
    retained_breaking_evidence_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class PatternCandidateResult:
    candidate: PatternSourceCandidate
    pattern_type: str
    status: Literal["supported", "conditionally_supported", "weakened", "contradicted", "rejected", "unresolved"]
    purity_score: str
    establishment_score: str
    break_score: str
    rescue_score: str
    establishment_conditions: tuple[Mapping[str, object], ...]
    breaking_conditions: tuple[Mapping[str, object], ...]
    rescue_conditions: tuple[Mapping[str, object], ...]
    unresolved_conditions: tuple[Mapping[str, object], ...]
    evidence_ids: tuple[str, ...]
    canonical_digest: str

    @property
    def candidate_id(self) -> str:
        return self.candidate.candidate_id

    def to_dict(self) -> dict[str, object]:
        payload = _plain_dataclass(self)
        payload["candidate_id"] = self.candidate_id
        return payload


@dataclass(frozen=True)
class BaziPatternEvaluationResult:
    fact_graph_hash: str
    strength_result_hash: str
    profile_id: str
    candidates: tuple[PatternCandidateResult, ...]
    primary_candidates: tuple[str, ...]
    rejected_candidates: tuple[str, ...]
    unresolved_candidates: tuple[str, ...]
    conflicts: tuple[PatternConflictRecord, ...]
    evidence_records: tuple[PatternEvidenceRecord, ...]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE10_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE10_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE10_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "fact_graph_hash": self.fact_graph_hash,
            "strength_result_hash": self.strength_result_hash,
            "profile_id": self.profile_id,
            "candidates": [item.to_dict() for item in self.candidates],
            "primary_candidates": list(self.primary_candidates),
            "rejected_candidates": list(self.rejected_candidates),
            "unresolved_candidates": list(self.unresolved_candidates),
            "conflicts": [item.to_dict() for item in self.conflicts],
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
class Phase10BenchmarkResult:
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
    coverage: Mapping[str, int]
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)
