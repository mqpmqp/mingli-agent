from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest

PHASE17_SCHEMA_VERSION = "special-scenario-assessment-result@0.1"
PHASE17_METHOD_ID = "special-scenario-rules@0.1.0"
PHASE17_CALCULATION_VERSION = "0.1.0"
PHASE17_DECISION_ID = "PHASE_17_SPECIAL_SCENARIO_RULES_R1_APPROVED"
SCENARIOS = ("career_exam", "relationship_reunion")
SCENARIO_LAYERS = {
    "career_exam": ("system_fit", "admission_outlook", "position_direction", "preparation_strategy"),
    "relationship_reunion": ("attraction", "recontact", "reunion", "stability"),
}
LAYER_LABELS = ("support", "conflict", "conditional", "unresolved", "not_applicable")


class Phase17InputError(ValueError):
    """Raised when a special-scenario assessment cannot be evaluated safely."""


def _plain(value: object) -> dict[str, object]:
    return json.loads(canonical_json(asdict(value)))


def record_digest(record_type: str, payload: Mapping[str, object]) -> str:
    body = {key: value for key, value in payload.items() if key not in {"canonical_digest", "canonical_hash"}}
    return digest({"record_type": record_type, "payload": body})


@dataclass(frozen=True)
class ScenarioRuleHit:
    hit_id: str
    rule_id: str
    layer: str
    direction: Literal["support", "conflict"]
    outcome_code: str
    priority: int
    hard_override: bool
    source_field: str
    source_value: object
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class ScenarioLayerAssessment:
    assessment_id: str
    layer: str
    label: str
    confidence: Literal["high", "medium", "low"]
    outcome_codes: tuple[str, ...]
    rule_hit_ids: tuple[str, ...]
    structural_source_contract_id: str | None
    reality_override: bool
    claim_boundary_codes: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class SpecialScenarioAssessmentResult:
    phase16_result_hash: str
    scenario: Literal["career_exam", "relationship_reunion"]
    target_id: str
    source_domain: Literal["career", "relationship"]
    reality_context_hash: str
    profile_id: str
    rule_set_hash: str
    rule_hits: tuple[ScenarioRuleHit, ...]
    layers: tuple[ScenarioLayerAssessment, ...]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE17_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE17_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE17_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)
    scenario_validity: Literal["bounded_special_rules"] = field(default="bounded_special_rules", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "phase16_result_hash": self.phase16_result_hash,
            "scenario": self.scenario,
            "target_id": self.target_id,
            "source_domain": self.source_domain,
            "reality_context_hash": self.reality_context_hash,
            "profile_id": self.profile_id,
            "rule_set_hash": self.rule_set_hash,
            "rule_hits": [item.to_dict() for item in self.rule_hits],
            "layers": [item.to_dict() for item in self.layers],
            "provenance_index": dict(self.provenance_index),
            "warnings": list(self.warnings),
            "unresolved": list(self.unresolved),
            "canonical_hash": self.canonical_hash,
            "schema_version": self.schema_version,
            "method_id": self.method_id,
            "calculation_version": self.calculation_version,
            "prediction_validity": self.prediction_validity,
            "scenario_validity": self.scenario_validity,
        }
