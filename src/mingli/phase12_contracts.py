from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase8_contracts import EvidenceRecord as Phase8EvidenceRecord

PHASE12_SCHEMA_VERSION = "bazi-xiji-role-classification-result@0.1"
PHASE12_METHOD_ID = "bazi-xiji-role-classification@0.1.0"
PHASE12_CALCULATION_VERSION = "0.1.0"
PHASE12_DECISION_ID = "PHASE_12_BAZI_XIJI_ROLE_CLASSIFICATION_R1_APPROVED"
XIJI_ROLES = ("yongshen", "xishen", "jishen", "choushen", "xianshen", "unresolved")


class Phase12InputError(ValueError):
    """Raised when Phase 12 cannot safely classify XiJi roles."""


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
class ElementRoleAssignment:
    assignment_id: str
    element: str
    role: str
    status: Literal["resolved", "conditional", "unresolved"]
    phase11_candidate_id: str
    phase11_status: str
    combined_score: str
    contradiction_score: str
    excess_risk: str
    relation_to_yongshen: str
    rationale_codes: tuple[str, ...]
    source_result_hashes: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class StemCarrierRole:
    carrier_id: str
    stem: str
    element: str
    inherited_role: str
    assignment_status: str
    inheritance_rule: Literal["inherits_element_role"]
    yin_yang_differentiation_status: Literal["not_evaluated"]
    source_assignment_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class RoleEvidenceRecord:
    evidence_id: str
    element: str
    role: str
    evidence_type: str
    direction: Literal["support", "contradict"]
    contribution: str
    priority: int
    source_candidate_ids: tuple[str, ...]
    source_result_hashes: tuple[str, ...]
    profile_id: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)

    def to_phase8_evidence(self) -> Phase8EvidenceRecord:
        return Phase8EvidenceRecord(
            evidence_id=self.evidence_id,
            claim_id=f"bazi-xiji-role:{self.element}:{self.role}",
            source_type="rule",
            source_id=self.evidence_id,
            detail=f"Phase 12 deterministic role evidence for {self.element}:{self.role}",
            direction=self.direction,
            weight=float(Decimal(self.contribution)),
            priority=self.priority,
            verified=True,
            canonical_digest=record_digest("Phase8EvidenceRecordFromPhase12", self.to_dict()),
        )


@dataclass(frozen=True)
class BaziXiJiEvaluationResult:
    regulation_result_hash: str
    fact_graph_hash: str
    strength_result_hash: str
    pattern_result_hash: str
    profile_id: str
    classification_status: Literal["resolved", "conditional", "unresolved"]
    element_assignments: tuple[ElementRoleAssignment, ...]
    stem_carriers: tuple[StemCarrierRole, ...]
    yongshen_elements: tuple[str, ...]
    xishen_elements: tuple[str, ...]
    jishen_elements: tuple[str, ...]
    choushen_elements: tuple[str, ...]
    xianshen_elements: tuple[str, ...]
    unresolved_elements: tuple[str, ...]
    evidence_records: tuple[RoleEvidenceRecord, ...]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE12_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE12_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE12_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "regulation_result_hash": self.regulation_result_hash,
            "fact_graph_hash": self.fact_graph_hash,
            "strength_result_hash": self.strength_result_hash,
            "pattern_result_hash": self.pattern_result_hash,
            "profile_id": self.profile_id,
            "classification_status": self.classification_status,
            "element_assignments": [item.to_dict() for item in self.element_assignments],
            "stem_carriers": [item.to_dict() for item in self.stem_carriers],
            "yongshen_elements": list(self.yongshen_elements),
            "xishen_elements": list(self.xishen_elements),
            "jishen_elements": list(self.jishen_elements),
            "choushen_elements": list(self.choushen_elements),
            "xianshen_elements": list(self.xianshen_elements),
            "unresolved_elements": list(self.unresolved_elements),
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
class Phase12BenchmarkResult:
    assertions_total: int
    passed: int
    failed: int
    unresolved: int
    schema_failures: int
    provenance_failures: int
    hash_mismatches: int
    role_partition_failures: int
    role_collision_failures: int
    carrier_failures: int
    prediction_boundary_failures: int
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain(self)
