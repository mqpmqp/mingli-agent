from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest

PHASE16_SCHEMA_VERSION = "bazi-base-domain-contract-result@0.1"
PHASE16_METHOD_ID = "bazi-base-domain-contract@0.1.0"
PHASE16_CALCULATION_VERSION = "0.1.0"
PHASE16_DECISION_ID = "PHASE_16_DOMAIN_CONTRACT_BASE_RULES_R1_APPROVED"
BASE_DOMAINS = ("career", "wealth", "relationship")
JUDGEMENT_LABELS = ("support_tendency", "conflict_tendency", "mixed_tendency", "neutral_tendency", "unresolved")


class Phase16InputError(ValueError):
    """Raised when Phase 16 cannot safely build a bounded base-domain contract."""


def _plain(value: object) -> dict[str, object]:
    return json.loads(canonical_json(asdict(value)))


def record_digest(record_type: str, payload: Mapping[str, object]) -> str:
    body = {key: value for key, value in payload.items() if key not in {"canonical_digest", "canonical_hash"}}
    return digest({"record_type": record_type, "payload": body})


@dataclass(frozen=True)
class BaseDomainRuleMatch:
    match_id: str
    rule_id: str
    target_id: str
    domain: str
    facet_code: str
    matched_theme_codes: tuple[str, ...]
    judgement_label: str
    confidence: Literal["high", "medium", "low"]
    priority: int
    claim_code: str
    source_judgement_id: str
    source_judgement_digest: str
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class DomainFacetAssessment:
    assessment_id: str
    target_id: str
    domain: str
    facet_code: str
    judgement_label: str
    confidence: Literal["high", "medium", "low"]
    claim_codes: tuple[str, ...]
    rule_match_ids: tuple[str, ...]
    source_judgement_id: str
    evidence_status: Literal["matched", "unresolved"]
    plain_language_explanation: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class BaseDomainContract:
    contract_id: str
    target_id: str
    target_type: str
    domain: str
    sequence_index: int | None
    label_year: int | None
    start_age: int | None
    end_age: int | None
    start_instant_utc: str
    end_instant_utc: str
    judgement_label: str
    confidence: Literal["high", "medium", "low"]
    confidence_score: int
    supporting_evidence_ids: tuple[str, ...]
    limiting_evidence_ids: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    reality_override: bool
    boundary_flags: tuple[str, ...]
    plain_language_explanation: str
    facet_assessment_ids: tuple[str, ...]
    matched_rule_ids: tuple[str, ...]
    active_theme_codes: tuple[str, ...]
    top_ten_gods: tuple[str, ...]
    reality_override_direction: Literal["support", "contradict"] | None
    reality_evidence_ids: tuple[str, ...]
    confidence_rationale_codes: tuple[str, ...]
    claim_boundary_codes: tuple[str, ...]
    source_judgement_id: str
    source_judgement_digest: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class BaziBaseDomainContractResult:
    phase15_result_hash: str
    profile_id: str
    rule_set_hash: str
    rule_matches: tuple[BaseDomainRuleMatch, ...]
    facet_assessments: tuple[DomainFacetAssessment, ...]
    domain_contracts: tuple[BaseDomainContract, ...]
    year_index: Mapping[str, tuple[str, ...]]
    age_index: Mapping[str, tuple[str, ...]]
    domain_index: Mapping[str, tuple[str, ...]]
    judgement_counts: Mapping[str, int]
    confidence_counts: Mapping[str, int]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE16_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE16_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE16_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)
    domain_contract_validity: Literal["base_rules_only"] = field(default="base_rules_only", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "phase15_result_hash": self.phase15_result_hash,
            "profile_id": self.profile_id,
            "rule_set_hash": self.rule_set_hash,
            "rule_matches": [item.to_dict() for item in self.rule_matches],
            "facet_assessments": [item.to_dict() for item in self.facet_assessments],
            "domain_contracts": [item.to_dict() for item in self.domain_contracts],
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
            "domain_contract_validity": self.domain_contract_validity,
        }


@dataclass(frozen=True)
class Phase16BenchmarkResult:
    assertions_total: int
    passed: int
    failed: int
    unresolved: int
    schema_failures: int
    provenance_failures: int
    hash_mismatches: int
    rule_coverage_failures: int
    contract_partition_failures: int
    reality_preservation_failures: int
    query_failures: int
    prediction_boundary_failures: int
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain(self)
