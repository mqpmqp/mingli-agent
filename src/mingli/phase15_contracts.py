from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase8_contracts import EvidenceRecord as Phase8EvidenceRecord

PHASE15_SCHEMA_VERSION = "bazi-tengod-domain-judgement-result@0.1"
PHASE15_METHOD_ID = "bazi-tengod-domain-judgement@0.1.0"
PHASE15_CALCULATION_VERSION = "0.1.0"
PHASE15_DECISION_ID = "PHASE_15_BAZI_TENGOD_DOMAIN_JUDGEMENT_R1_APPROVED"
DOMAINS = ("career", "wealth", "relationship", "education", "exam", "startup", "migration")
DOMAIN_LABELS = ("support_tendency", "conflict_tendency", "mixed_tendency", "neutral_tendency", "unresolved")
TARGET_TYPES = ("dayun", "liunian", "combined_window")
CONFLICT_STATUSES = ("no_conflict", "cross_domain_conflict", "unresolved")


class Phase15InputError(ValueError):
    """Raised when Phase 15 cannot safely derive TenGod domain judgement candidates."""


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
class NatalTenGodContext:
    day_master: str
    visible_scores: Mapping[str, str]
    hidden_scores: Mapping[str, str]
    total_scores: Mapping[str, str]
    domain_activation_scores: Mapping[str, str]
    source_node_ids: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class DynamicTenGodHit:
    hit_id: str
    target_id: str
    target_type: Literal["dayun", "liunian", "combined_window"]
    component_period_id: str
    component_type: Literal["dayun", "liunian"]
    source_type: Literal["stem", "branch_hidden"]
    source_symbol: str
    ordinal: int
    ten_god_code: str
    ten_god_label: str
    ten_god_family: str
    polarity_relation: Literal["same_polarity", "opposite_polarity"]
    element: str
    xiji_role: str
    role_direction: Literal["support", "conflict", "neutral", "unresolved"]
    raw_score: str
    component_weight: str
    effective_score: str
    source_hit_digest: str
    source_result_hashes: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class DomainContribution:
    contribution_id: str
    target_id: str
    domain: str
    ten_god_code: str
    theme_codes: tuple[str, ...]
    direction: Literal["support", "conflict", "neutral", "unresolved"]
    theme_weight: str
    effective_score: str
    contribution_score: str
    source_hit_id: str
    source_result_hashes: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class DomainRealityEvidenceRecord:
    evidence_id: str
    target_id: str
    domain: str
    direction: Literal["support", "contradict"]
    detail: str
    weight: str
    verified: bool
    source_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class DomainJudgementCandidate:
    judgement_id: str
    target_id: str
    target_type: Literal["dayun", "liunian", "combined_window"]
    domain: str
    sequence_index: int | None
    label_year: int | None
    start_age: int | None
    end_age: int | None
    start_instant_utc: str
    end_instant_utc: str
    temporal_trend_label: str
    temporal_trend_confidence: str
    activation_score: str
    natal_context_score: str
    support_score: str
    conflict_score: str
    neutral_score: str
    unresolved_count: int
    support_ratio: str
    conflict_ratio: str
    neutral_ratio: str
    net_balance: str
    judgement_label: Literal["support_tendency", "conflict_tendency", "mixed_tendency", "neutral_tendency", "unresolved"]
    confidence: Literal["high", "medium", "low"]
    top_ten_gods: tuple[str, ...]
    active_theme_codes: tuple[str, ...]
    confidence_rationale_codes: tuple[str, ...]
    reality_override_direction: Literal["support", "contradict"] | None
    reality_evidence_ids: tuple[str, ...]
    claim_boundary_codes: tuple[str, ...]
    source_contribution_ids: tuple[str, ...]
    source_result_hashes: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class CrossDomainConflictRecord:
    conflict_id: str
    target_id: str
    support_domains: tuple[str, ...]
    conflict_domains: tuple[str, ...]
    mixed_domains: tuple[str, ...]
    unresolved_domains: tuple[str, ...]
    status: Literal["no_conflict", "cross_domain_conflict", "unresolved"]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class DomainJudgementEvidenceRecord:
    evidence_id: str
    target_id: str
    domain: str
    evidence_type: str
    source_type: Literal["timing", "rule", "reality"]
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
            claim_id=f"bazi-domain-judgement:{self.target_id}:{self.domain}",
            source_type=self.source_type,
            source_id=self.source_id,
            detail=f"Phase 15 deterministic TenGod domain evidence for {self.target_id}:{self.domain}",
            direction=self.direction,
            weight=float(Decimal(self.contribution)),
            priority=self.priority,
            verified=self.verified,
            canonical_digest=record_digest("Phase8EvidenceRecordFromPhase15", self.to_dict()),
        )


@dataclass(frozen=True)
class BaziTenGodDomainJudgementResult:
    fact_graph_hash: str
    interaction_result_hash: str
    temporal_trend_result_hash: str
    profile_id: str
    natal_context: NatalTenGodContext
    dynamic_hits: tuple[DynamicTenGodHit, ...]
    domain_contributions: tuple[DomainContribution, ...]
    domain_judgements: tuple[DomainJudgementCandidate, ...]
    cross_domain_conflicts: tuple[CrossDomainConflictRecord, ...]
    reality_evidence: tuple[DomainRealityEvidenceRecord, ...]
    evidence_records: tuple[DomainJudgementEvidenceRecord, ...]
    year_index: Mapping[str, tuple[str, ...]]
    age_index: Mapping[str, tuple[str, ...]]
    domain_index: Mapping[str, tuple[str, ...]]
    judgement_counts: Mapping[str, int]
    confidence_counts: Mapping[str, int]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE15_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE15_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE15_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)
    domain_judgement_validity: Literal["candidate_only"] = field(default="candidate_only", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "fact_graph_hash": self.fact_graph_hash,
            "interaction_result_hash": self.interaction_result_hash,
            "temporal_trend_result_hash": self.temporal_trend_result_hash,
            "profile_id": self.profile_id,
            "natal_context": self.natal_context.to_dict(),
            "dynamic_hits": [item.to_dict() for item in self.dynamic_hits],
            "domain_contributions": [item.to_dict() for item in self.domain_contributions],
            "domain_judgements": [item.to_dict() for item in self.domain_judgements],
            "cross_domain_conflicts": [item.to_dict() for item in self.cross_domain_conflicts],
            "reality_evidence": [item.to_dict() for item in self.reality_evidence],
            "evidence_records": [item.to_dict() for item in self.evidence_records],
            "year_index": {key: list(value) for key, value in self.year_index.items()},
            "age_index": {key: list(value) for key, value in self.age_index.items()},
            "domain_index": {key: list(value) for key, value in self.domain_index.items()},
            "judgement_counts": dict(self.judgement_counts),
            "confidence_counts": dict(self.confidence_counts),
            "provenance_index": dict(self.provenance_index),
            "warnings": list(self.warnings),
            "unresolved": list(self.unresolved),
            "canonical_hash": self.canonical_hash,
            "schema_version": self.schema_version,
            "method_id": self.method_id,
            "calculation_version": self.calculation_version,
            "prediction_validity": self.prediction_validity,
            "domain_judgement_validity": self.domain_judgement_validity,
        }


@dataclass(frozen=True)
class Phase15BenchmarkResult:
    assertions_total: int
    passed: int
    failed: int
    unresolved: int
    schema_failures: int
    provenance_failures: int
    hash_mismatches: int
    ten_god_mapping_failures: int
    domain_partition_failures: int
    query_failures: int
    reality_override_failures: int
    claim_boundary_failures: int
    prediction_boundary_failures: int
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain(self)
