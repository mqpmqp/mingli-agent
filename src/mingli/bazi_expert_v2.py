"""Versioned, deterministic orchestration over the frozen Bazi expert phases.

This module does not add divination rules.  It validates and composes Phase
9--18 outputs, exposes explicit capability boundaries, calibrates confidence,
and optionally adapts eligible results to the Phase 20 Yuan renderer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from importlib.resources import files
import json
from typing import Literal

from .contracts.serialization import canonical_json, digest
from .phase10_contracts import Phase10InputError
from .phase10_engine import evaluate_bazi_pattern
from .phase11_contracts import Phase11InputError
from .phase11_engine import evaluate_bazi_regulation
from .phase12 import evaluate_bazi_xiji_roles
from .phase12_contracts import Phase12InputError
from .phase13 import evaluate_luck_cycle_role_interactions
from .phase13_contracts import Phase13InputError
from .phase14 import evaluate_bazi_temporal_trends
from .phase14_contracts import Phase14InputError
from .phase15 import evaluate_bazi_tengod_domains
from .phase15_contracts import Phase15InputError
from .phase16 import evaluate_base_domain_contracts
from .phase16_contracts import Phase16InputError
from .phase17 import evaluate_special_scenario
from .phase17_contracts import Phase17InputError
from .phase18 import (
    Phase18InputError,
    normalize_reality_context,
    orchestrate_evidence_fusion,
)
from .phase20 import Phase20InputError, render_yuan_eight_sections
from .phase9_contracts import Phase9InputError
from .phase9_engine import calculate_day_master_strength

BAZI_EXPERT_V2_INPUT_SCHEMA_VERSION = "bazi-expert-orchestration-input@2.0"
BAZI_EXPERT_V2_SCHEMA_VERSION = "bazi-expert-orchestration-result@2.0"
BAZI_EXPERT_V2_METHOD_ID = "bazi-expert-orchestration@2.0.0"
BAZI_EXPERT_V2_CALCULATION_VERSION = "2.0.0"
BAZI_EXPERT_V2_DECISION_ID = "BAZI_EXPERT_RULES_V2_ADDITIVE_ORCHESTRATION_APPROVED"

FacetStatus = Literal["implemented", "conditional", "unsupported"]
Confidence = Literal["high", "medium", "low", "not_applicable"]

_INPUT_FIELDS = frozenset(
    {
        "schema_version",
        "fact_graph",
        "target_id",
        "reality_context",
        "temporal_reality_evidence",
        "domain_reality_evidence",
        "prior_event_evidence",
        "compatibility_peer_fact_graph",
        "renderer_context",
        "fixture_provenance",
    }
)
_FACET_ORDER = (
    "five_element_strength",
    "same_kind_different_kind",
    "pattern",
    "yongshen_climate_regulation",
    "ten_god_combinations",
    "punishment_clash_combine_harm",
    "decadal_luck",
    "annual_scope",
    "monthly_scope",
    "career",
    "wealth",
    "relationship",
    "marriage",
    "study",
    "family",
    "civil_service_exam",
    "relationship_reunion",
    "dual_person_compatibility",
    "prior_event_validation",
    "reality_evidence_override",
    "confidence_calibration",
    "yuan_renderer_adapter",
)
_PHASE_ERRORS = (
    Phase9InputError,
    Phase10InputError,
    Phase11InputError,
    Phase12InputError,
    Phase13InputError,
    Phase14InputError,
    Phase15InputError,
    Phase16InputError,
    Phase17InputError,
    Phase18InputError,
    Phase20InputError,
)
_LABEL_TO_RENDER_STATUS = {
    "support_tendency": "supportive",
    "conflict_tendency": "challenging",
    "mixed_tendency": "mixed",
    "neutral_tendency": "mixed",
    "unresolved": "unresolved",
}


class BaziExpertV2InputError(ValueError):
    """Raised when V2 orchestration cannot proceed without guessing."""


def _plain(value: object) -> dict[str, object]:
    return json.loads(canonical_json(asdict(value)))


def _record_digest(record_type: str, payload: Mapping[str, object]) -> str:
    return digest({"record_type": record_type, "payload": payload})


@dataclass(frozen=True)
class CapabilityFacet:
    facet_id: str
    status: FacetStatus
    availability: str
    confidence: Confidence
    source_phases: tuple[str, ...]
    boundary_codes: tuple[str, ...]
    data: Mapping[str, object]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain(self)


@dataclass(frozen=True)
class BaziExpertV2Result:
    request_hash: str
    selected_target_id: str
    source_results: Mapping[str, Mapping[str, object]]
    facets: Mapping[str, CapabilityFacet]
    facet_summary: Mapping[str, tuple[str, ...]]
    evidence_fusion: Mapping[str, object]
    calibrated_claims: tuple[Mapping[str, object], ...]
    yuan: Mapping[str, object] | None
    fixture_provenance: Mapping[str, object] | None
    confidence: Literal["high", "medium", "low"]
    confidence_reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    unsupported: tuple[str, ...]
    canonical_hash: str
    schema_version: str = field(default=BAZI_EXPERT_V2_SCHEMA_VERSION, init=False)
    method_id: str = field(default=BAZI_EXPERT_V2_METHOD_ID, init=False)
    calculation_version: str = field(
        default=BAZI_EXPERT_V2_CALCULATION_VERSION, init=False
    )
    prediction_validity: Literal["not_evaluated"] = field(
        default="not_evaluated", init=False
    )
    release_hold: Literal["ACTIVE"] = field(default="ACTIVE", init=False)
    accuracy_claim_allowed: Literal[False] = field(default=False, init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "request_hash": self.request_hash,
            "selected_target_id": self.selected_target_id,
            "source_results": {
                key: dict(value) for key, value in self.source_results.items()
            },
            "facets": {key: value.to_dict() for key, value in self.facets.items()},
            "facet_summary": {
                key: list(value) for key, value in self.facet_summary.items()
            },
            "evidence_fusion": dict(self.evidence_fusion),
            "calibrated_claims": [dict(item) for item in self.calibrated_claims],
            "yuan": dict(self.yuan) if self.yuan is not None else None,
            "fixture_provenance": (
                dict(self.fixture_provenance)
                if self.fixture_provenance is not None
                else None
            ),
            "confidence": self.confidence,
            "confidence_reason_codes": list(self.confidence_reason_codes),
            "warnings": list(self.warnings),
            "unsupported": list(self.unsupported),
            "canonical_hash": self.canonical_hash,
            "schema_version": self.schema_version,
            "method_id": self.method_id,
            "calculation_version": self.calculation_version,
            "prediction_validity": self.prediction_validity,
            "release_hold": self.release_hold,
            "accuracy_claim_allowed": self.accuracy_claim_allowed,
        }


def load_bazi_expert_v2_schema() -> dict[str, object]:
    resource = files("mingli.contracts.schemas").joinpath(
        "bazi_expert_v2_result.schema.json"
    )
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("Bazi Expert V2 result schema must be an object")
    return value


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise BaziExpertV2InputError(f"{name} must be an object")
    return dict(value)


def _records(
    value: object,
    name: str,
    *,
    required_fields: frozenset[str] = frozenset(),
) -> tuple[dict[str, object], ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise BaziExpertV2InputError(f"{name} must be an array")
    records: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise BaziExpertV2InputError(f"{name} entries must be objects")
        record = dict(item)
        missing = required_fields - set(record)
        if missing:
            raise BaziExpertV2InputError(
                f"{name} entry is missing fields: {sorted(missing)}"
            )
        records.append(record)
    return tuple(sorted(records, key=canonical_json))


def _fixture_provenance(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    payload = _mapping(value, "fixture_provenance")
    allowed = {"synthetic", "purpose", "accuracy_eligible"}
    if set(payload) != allowed:
        raise BaziExpertV2InputError(
            "fixture_provenance must declare synthetic, purpose, and accuracy_eligible"
        )
    if payload["synthetic"] is not True or payload["accuracy_eligible"] is not False:
        raise BaziExpertV2InputError(
            "synthetic fixtures must remain accuracy_eligible=false"
        )
    if payload["purpose"] != "contract_test_only":
        raise BaziExpertV2InputError(
            "synthetic fixture purpose must be contract_test_only"
        )
    return payload


def _source_ref(payload: Mapping[str, object]) -> dict[str, object]:
    required = ("schema_version", "method_id", "calculation_version", "canonical_hash")
    if any(not isinstance(payload.get(key), str) for key in required):
        raise BaziExpertV2InputError("composed phase result is missing version metadata")
    if payload.get("prediction_validity") != "not_evaluated":
        raise BaziExpertV2InputError(
            "composed phase prediction_validity must remain not_evaluated"
        )
    return {key: payload[key] for key in required}


def _scenario_bundle_ref(
    exam: Mapping[str, object], reunion: Mapping[str, object]
) -> dict[str, object]:
    hashes = sorted((str(exam["canonical_hash"]), str(reunion["canonical_hash"])))
    body = {"component_hashes": hashes, "prediction_validity": "not_evaluated"}
    return {
        "schema_version": "special-scenario-assessment-bundle@2.0",
        "method_id": "phase17-special-scenario-bundle@2.0.0",
        "calculation_version": "2.0.0",
        "canonical_hash": _record_digest("Phase17ScenarioBundle", body),
        "component_hashes": hashes,
    }


def _facet(
    facet_id: str,
    status: FacetStatus,
    availability: str,
    confidence: Confidence,
    source_phases: Sequence[str],
    boundary_codes: Sequence[str],
    data: Mapping[str, object],
) -> CapabilityFacet:
    body: dict[str, object] = {
        "facet_id": facet_id,
        "status": status,
        "availability": availability,
        "confidence": confidence,
        "source_phases": list(source_phases),
        "boundary_codes": list(boundary_codes),
        "data": dict(data),
    }
    return CapabilityFacet(
        facet_id=facet_id,
        status=status,
        availability=availability,
        confidence=confidence,
        source_phases=tuple(source_phases),
        boundary_codes=tuple(boundary_codes),
        data=dict(data),
        canonical_digest=_record_digest("BaziExpertV2CapabilityFacet", body),
    )


def _structural_confidence(value: object, *, reality_override: bool = False) -> str:
    confidence = str(value)
    if confidence not in {"high", "medium", "low"}:
        return "low"
    if confidence == "high" and not reality_override:
        return "medium"
    return confidence


def _aggregate_confidence(values: Sequence[str]) -> Literal["high", "medium", "low"]:
    rank = {"low": 0, "medium": 1, "high": 2}
    eligible = [value for value in values if value in rank]
    if not eligible:
        return "low"
    return min(eligible, key=rank.__getitem__)  # type: ignore[return-value]


def _run_natal_core(fact_graph: Mapping[str, object]) -> dict[str, dict[str, object]]:
    strength = calculate_day_master_strength(fact_graph).to_dict()
    pattern = evaluate_bazi_pattern(fact_graph, strength).to_dict()
    regulation = evaluate_bazi_regulation(fact_graph, strength, pattern).to_dict()
    xiji = evaluate_bazi_xiji_roles(regulation).to_dict()
    return {
        "phase9": strength,
        "phase10": pattern,
        "phase11": regulation,
        "phase12": xiji,
    }


def _find_by_target(
    records: object, target_id: str, *, domain: str | None = None
) -> dict[str, object]:
    if not isinstance(records, list):
        raise BaziExpertV2InputError("composed target collection must be an array")
    for item in records:
        if not isinstance(item, Mapping) or item.get("target_id") != target_id:
            continue
        if domain is None or item.get("domain") == domain:
            return dict(item)
    suffix = f" and domain {domain}" if domain is not None else ""
    raise BaziExpertV2InputError(f"unknown target_id {target_id}{suffix}")


def _relation_summary(
    fact_graph: Mapping[str, object], interaction: Mapping[str, object]
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    raw_natal = fact_graph.get("relations", [])
    if isinstance(raw_natal, list):
        for item in raw_natal:
            if not isinstance(item, Mapping):
                continue
            relation_types = item.get("relation_types")
            if not isinstance(relation_types, list):
                relation_type = item.get("relation_type")
                relation_types = [relation_type] if isinstance(relation_type, str) else []
            for relation_type in relation_types:
                records.append(
                    {
                        "source_phase": "phase7",
                        "target_id": "natal",
                        "relation_type": str(relation_type),
                        "source_digest": item.get("canonical_digest"),
                    }
                )
    for collection in ("dayun_interactions", "liunian_interactions"):
        raw = interaction.get(collection, [])
        if not isinstance(raw, list):
            continue
        for period in raw:
            if not isinstance(period, Mapping):
                continue
            relations = period.get("natal_relations", [])
            if not isinstance(relations, list):
                continue
            for relation in relations:
                if not isinstance(relation, Mapping):
                    continue
                relation_types = relation.get("relation_types", [])
                if not isinstance(relation_types, list):
                    continue
                for relation_type in relation_types:
                    records.append(
                        {
                            "source_phase": "phase13",
                            "target_id": period.get("period_id"),
                            "relation_type": str(relation_type),
                            "source_digest": relation.get("canonical_digest"),
                        }
                    )
    raw_windows = interaction.get("combined_windows", [])
    if isinstance(raw_windows, list):
        for window in raw_windows:
            if not isinstance(window, Mapping):
                continue
            for key in ("stem_relation_types", "branch_relation_types"):
                relation_types = window.get(key, [])
                if not isinstance(relation_types, list):
                    continue
                for relation_type in relation_types:
                    records.append(
                        {
                            "source_phase": "phase13",
                            "target_id": window.get("window_id"),
                            "relation_type": str(relation_type),
                            "source_digest": window.get("canonical_digest"),
                        }
                    )
    records.sort(key=canonical_json)
    families: dict[str, list[dict[str, object]]] = {
        "punishment": [],
        "clash": [],
        "combine": [],
        "harm": [],
    }
    unclassified: list[dict[str, object]] = []
    for item in records:
        code = str(item["relation_type"]).lower()
        matched = False
        if "xing" in code or "punish" in code:
            families["punishment"].append(item)
            matched = True
        if "chong" in code or "clash" in code:
            families["clash"].append(item)
            matched = True
        if any(token in code for token in ("combine", "liuhe", "sanhe", "sanhui")):
            families["combine"].append(item)
            matched = True
        if "liuhai" in code or "harm" in code:
            families["harm"].append(item)
            matched = True
        if not matched:
            unclassified.append(item)
    return {
        "relation_families": families,
        "all_records": records,
        "unclassified_records": unclassified,
        "transformation_judgement": "unsupported",
    }


def _derived_evidence(
    evidence_id: str,
    claim_id: str,
    scope: str,
    source_type: str,
    source_id: str,
    direction: str,
    *,
    priority: int = 70,
    verified: bool = False,
    detail_code: str,
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "claim_id": claim_id,
        "scope": scope,
        "source_type": source_type,
        "source_id": source_id,
        "direction": direction,
        "weight": 1,
        "priority": priority,
        "verified": verified,
        "detail_code": detail_code,
    }


def _label_evidence(
    prefix: str,
    claim_id: str,
    scope: str,
    label: str,
    source_type: str,
    source_id: str,
    *,
    verified: bool = False,
) -> list[dict[str, object]]:
    if label in {"support_tendency", "support"}:
        directions = ("support",)
    elif label in {"conflict_tendency", "conflict"}:
        directions = ("contradict",)
    elif label in {"mixed_tendency", "conditional", "unresolved"}:
        directions = ("support", "contradict")
    else:
        directions = ()
    return [
        _derived_evidence(
            f"{prefix}:{direction}",
            claim_id,
            scope,
            source_type,
            source_id,
            direction,
            verified=verified,
            priority=100 if verified else 70,
            detail_code=f"composed_{label}",
        )
        for direction in directions
    ]


def _domain_fusion_evidence(
    judgements: Mapping[str, Mapping[str, object]],
    reality: Sequence[Mapping[str, object]],
    source_hash: str,
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for domain, judgement in sorted(judgements.items()):
        target_id = str(judgement["target_id"])
        claim_id = f"bazi-domain-judgement:{target_id}:{domain}"
        scope = f"{target_id}:{domain}"
        evidence.extend(
            _label_evidence(
                f"expert-v2:domain:{target_id}:{domain}",
                claim_id,
                scope,
                str(judgement["judgement_label"]),
                "rule",
                source_hash,
            )
        )
    for item in reality:
        target_id = str(item["target_id"])
        domain = str(item["domain"])
        evidence.append(
            {
                "evidence_id": f"expert-v2:domain-reality:{item['evidence_id']}",
                "claim_id": f"bazi-domain-judgement:{target_id}:{domain}",
                "scope": f"{target_id}:{domain}",
                "source_type": "reality",
                "source_id": str(item["source_id"]),
                "direction": str(item["direction"]),
                "weight": item.get("weight", 0),
                "priority": 100,
                "verified": item.get("verified") is True,
                "detail_code": "phase15_domain_reality_evidence",
            }
        )
    return evidence


def _temporal_fusion_evidence(
    trend: Mapping[str, object],
    reality: Sequence[Mapping[str, object]],
    source_hash: str,
) -> list[dict[str, object]]:
    target_id = str(trend["target_id"])
    claim_id = f"bazi-temporal-trend:{target_id}"
    scope = target_id
    evidence = _label_evidence(
        f"expert-v2:temporal:{target_id}",
        claim_id,
        scope,
        str(trend["trend_label"]),
        "timing",
        source_hash,
    )
    for item in reality:
        item_target = str(item["target_id"])
        evidence.append(
            {
                "evidence_id": f"expert-v2:temporal-reality:{item['evidence_id']}",
                "claim_id": f"bazi-temporal-trend:{item_target}",
                "scope": item_target,
                "source_type": "reality",
                "source_id": str(item["source_id"]),
                "direction": str(item["direction"]),
                "weight": item.get("weight", 0),
                "priority": 100,
                "verified": item.get("verified") is True,
                "detail_code": "phase14_temporal_reality_evidence",
            }
        )
    return evidence


def _scenario_fusion_evidence(
    scenario: Mapping[str, object],
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    raw_layers = scenario.get("layers", [])
    if not isinstance(raw_layers, list):
        return evidence
    for layer in raw_layers:
        if not isinstance(layer, Mapping):
            continue
        target_id = str(scenario["target_id"])
        layer_id = str(layer["layer"])
        override = layer.get("reality_override") is True
        evidence.extend(
            _label_evidence(
                f"expert-v2:scenario:{scenario['scenario']}:{target_id}:{layer_id}",
                f"bazi-scenario:{scenario['scenario']}:{layer_id}",
                f"{target_id}:{layer_id}",
                str(layer["label"]),
                "reality" if override else "rule",
                str(scenario["reality_context_hash"])
                if override
                else str(scenario["canonical_hash"]),
                verified=override,
            )
        )
    return evidence


def _prior_event_fusion_evidence(
    records: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    allowed = {
        "evidence_id",
        "claim_id",
        "scope",
        "source_id",
        "direction",
        "verified",
        "detail_code",
    }
    for item in records:
        extra = set(item) - allowed
        if extra:
            raise BaziExpertV2InputError(
                f"prior_event_evidence contains unsupported fields: {sorted(extra)}"
            )
        if not str(item["claim_id"]).startswith("prior-event:"):
            raise BaziExpertV2InputError(
                "prior_event_evidence claim_id must start with prior-event:"
            )
        if item["direction"] not in {"support", "contradict"}:
            raise BaziExpertV2InputError(
                "prior_event_evidence direction must be support or contradict"
            )
        evidence.append(
            {
                "evidence_id": f"expert-v2:prior:{item['evidence_id']}",
                "claim_id": str(item["claim_id"]),
                "scope": str(item["scope"]),
                "source_type": "reality",
                "source_id": str(item["source_id"]),
                "direction": str(item["direction"]),
                "weight": 0,
                "priority": 100,
                "verified": item["verified"] is True,
                "detail_code": str(item["detail_code"]),
            }
        )
    return evidence


def _calibrated_claims(
    fusion: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    claims = fusion.get("claims", [])
    if not isinstance(claims, list):
        raise BaziExpertV2InputError("Phase 18 claims must be an array")
    calibrated: list[dict[str, object]] = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        status = str(claim.get("status"))
        if status in {"unresolved_conflict", "no_evidence"}:
            confidence = "low"
            reasons = ["unresolved_or_missing_evidence"]
        elif status == "resolved_by_reality_override":
            confidence = str(claim.get("confidence", "low"))
            reasons = ["verified_claim_scope_reality_override"]
        else:
            confidence = _structural_confidence(claim.get("confidence"))
            reasons = ["structural_only_confidence_ceiling"]
        calibrated.append(
            {
                "claim_id": str(claim.get("claim_id")),
                "scope": str(claim.get("scope")),
                "status": status,
                "confidence": confidence,
                "confidence_score": int(claim.get("confidence_score", 0)),
                "reality_override": status == "resolved_by_reality_override",
                "reason_codes": reasons,
            }
        )
    return tuple(sorted(calibrated, key=canonical_json))


def _adapt_layer(layer: Mapping[str, object]) -> dict[str, object]:
    value = dict(layer)
    source_confidence = str(value.get("confidence", "low"))
    value["source_confidence"] = source_confidence
    value["confidence"] = _structural_confidence(
        source_confidence, reality_override=value.get("reality_override") is True
    )
    return value


def _scenario_views(
    exam: Mapping[str, object], reunion: Mapping[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    exam_layers = {
        str(item["layer"]): _adapt_layer(item)
        for item in exam["layers"]  # type: ignore[index]
        if isinstance(item, Mapping)
    }
    reunion_layers = {
        str(item["layer"]): _adapt_layer(item)
        for item in reunion["layers"]  # type: ignore[index]
        if isinstance(item, Mapping)
    }
    exam_view = {
        "system_fit": exam_layers["system_fit"],
        "exam_conditions": {
            "eligibility": exam_layers["admission_outlook"],
            "exam_outlook": exam_layers["exam_outlook"],
        },
        "role_direction": exam_layers["position_direction"],
        "preparation_strategy": exam_layers["preparation_strategy"],
        "guaranteed_admission": "unsupported",
    }
    reunion_view = {
        "attraction": reunion_layers["attraction"],
        "contact": reunion_layers["recontact"],
        "reunion": reunion_layers["reunion"],
        "stability": reunion_layers["stability"],
        "guaranteed_reunion": "unsupported",
    }
    return exam_view, reunion_view


def _compatibility_view(
    left: Mapping[str, Mapping[str, object]],
    peer_graph: Mapping[str, object] | None,
) -> tuple[dict[str, object], str, dict[str, object] | None]:
    if peer_graph is None:
        return (
            {
                "comparison_only": True,
                "compatibility_conclusion": "unsupported",
                "reason": "compatibility_peer_fact_graph_not_provided",
            },
            "missing_prerequisite",
            None,
        )
    peer = _run_natal_core(peer_graph)
    left_strength = left["phase9"]
    right_strength = peer["phase9"]
    left_xiji = left["phase12"]
    right_xiji = peer["phase12"]
    left_yongshen = set(str(value) for value in left_xiji["yongshen_elements"])
    right_yongshen = set(str(value) for value in right_xiji["yongshen_elements"])
    view = {
        "comparison_only": True,
        "left": {
            "day_master_element": left_strength["day_master_element"],
            "strength_classification": left_strength["classification"],
            "same_kind_ratio": left_strength["support_ratio"],
            "yongshen_elements": sorted(left_yongshen),
        },
        "right": {
            "day_master_element": right_strength["day_master_element"],
            "strength_classification": right_strength["classification"],
            "same_kind_ratio": right_strength["support_ratio"],
            "yongshen_elements": sorted(right_yongshen),
        },
        "shared_yongshen_elements": sorted(left_yongshen & right_yongshen),
        "compatibility_conclusion": "unsupported",
        "boundary_codes": [
            "no_compatibility_score",
            "no_relationship_outcome_prediction",
        ],
    }
    peer_refs = {
        key: _source_ref(value) for key, value in sorted(peer.items())
    }
    return view, "available", peer_refs


def _renderer_payload(
    renderer_context: Mapping[str, object],
    contracts: Mapping[str, Mapping[str, object]],
    trend_result: Mapping[str, object],
) -> tuple[dict[str, object] | None, str]:
    allowed = {"profile", "chenggu", "start_year", "advice_codes"}
    extra = set(renderer_context) - allowed
    if extra:
        raise BaziExpertV2InputError(
            f"renderer_context contains unsupported fields: {sorted(extra)}"
        )
    profile = _mapping(renderer_context.get("profile"), "renderer_context.profile")
    if set(profile) != {"calendar", "birth_date", "birth_time"}:
        raise BaziExpertV2InputError(
            "renderer_context.profile requires only calendar, birth_date, and birth_time"
        )
    chenggu = _mapping(renderer_context.get("chenggu"), "renderer_context.chenggu")
    if set(chenggu) != {"display_weight", "verse_available"}:
        raise BaziExpertV2InputError(
            "renderer_context.chenggu requires only display_weight and verse_available"
        )
    start_year = renderer_context.get("start_year")
    if isinstance(start_year, bool) or not isinstance(start_year, int):
        raise BaziExpertV2InputError("renderer_context.start_year must be an integer")
    advice_codes = renderer_context.get("advice_codes", [])
    if not isinstance(advice_codes, Sequence) or isinstance(advice_codes, (str, bytes)):
        raise BaziExpertV2InputError("renderer_context.advice_codes must be an array")
    raw_trends = trend_result.get("liunian_trends", [])
    if not isinstance(raw_trends, list):
        raise BaziExpertV2InputError("Phase 14 liunian_trends must be an array")
    by_year = {
        int(item["label_year"]): item
        for item in raw_trends
        if isinstance(item, Mapping) and isinstance(item.get("label_year"), int)
    }
    years = list(range(start_year, start_year + 5))
    if any(year not in by_year for year in years):
        return None, "missing_consecutive_annual_scope"
    domains = {
        domain: _LABEL_TO_RENDER_STATUS[str(contracts[domain]["judgement_label"])]
        for domain in ("career", "wealth", "relationship")
    }
    domain_confidence = {
        domain: _structural_confidence(
            contracts[domain]["confidence"],
            reality_override=contracts[domain].get("reality_override") is True,
        )
        for domain in ("career", "wealth", "relationship")
    }
    five_years = []
    for year in years:
        trend = by_year[year]
        five_years.append(
            {
                "year": year,
                "status": _LABEL_TO_RENDER_STATUS[str(trend["trend_label"])],
                "confidence": _structural_confidence(
                    trend["confidence"],
                    reality_override=trend.get("reality_override_direction") is not None,
                ),
            }
        )
    return {
        "profile": profile,
        "chenggu": chenggu,
        "domains": domains,
        "domain_confidence": domain_confidence,
        "five_years": five_years,
        "advice_codes": sorted(str(value) for value in advice_codes),
    }, "available"


def _domain_facet_data(contract: Mapping[str, object]) -> dict[str, object]:
    return {
        "target_id": contract["target_id"],
        "target_type": contract["target_type"],
        "judgement_label": contract["judgement_label"],
        "confidence": contract["confidence"],
        "active_theme_codes": contract["active_theme_codes"],
        "top_ten_gods": contract["top_ten_gods"],
        "reality_override": contract["reality_override"],
        "reality_override_direction": contract["reality_override_direction"],
        "claim_boundary_codes": contract["claim_boundary_codes"],
        "plain_language_explanation": contract["plain_language_explanation"],
        "source_contract_id": contract["contract_id"],
        "source_digest": contract["canonical_digest"],
    }


def _overall_confidence(
    facets: Mapping[str, CapabilityFacet], calibrated: Sequence[Mapping[str, object]]
) -> tuple[Literal["high", "medium", "low"], tuple[str, ...]]:
    available = [
        facet.confidence
        for facet in facets.values()
        if facet.status != "unsupported" and facet.availability == "available"
    ]
    confidence = _aggregate_confidence([str(value) for value in available])
    reasons = ["structural_only_confidence_ceiling"]
    if any(item.get("status") == "unresolved_conflict" for item in calibrated):
        confidence = "low"
        reasons.append("unresolved_evidence_conflict")
    if any(item.get("reality_override") is True for item in calibrated):
        reasons.append("claim_scope_reality_override_present")
    return confidence, tuple(reasons)


def orchestrate_bazi_expert_v2(
    raw: Mapping[str, object],
) -> BaziExpertV2Result:
    """Compose frozen Phase 9--18 capabilities and optional Phase 20 output."""

    if not isinstance(raw, Mapping):
        raise BaziExpertV2InputError("request must be an object")
    request = dict(raw)
    extra = set(request) - _INPUT_FIELDS
    if extra:
        raise BaziExpertV2InputError(
            f"unsupported request fields: {sorted(extra)}"
        )
    if request.get("schema_version") != BAZI_EXPERT_V2_INPUT_SCHEMA_VERSION:
        raise BaziExpertV2InputError("unsupported Bazi Expert V2 schema_version")
    fact_graph = _mapping(request.get("fact_graph"), "fact_graph")
    target_id = request.get("target_id")
    if not isinstance(target_id, str) or not target_id:
        raise BaziExpertV2InputError("target_id must be a non-empty string")
    raw_reality = _mapping(request.get("reality_context", {}), "reality_context")
    temporal_reality = _records(
        request.get("temporal_reality_evidence", []),
        "temporal_reality_evidence",
        required_fields=frozenset(
            {
                "evidence_id",
                "target_id",
                "direction",
                "detail",
                "weight",
                "verified",
                "source_id",
            }
        ),
    )
    domain_reality = _records(
        request.get("domain_reality_evidence", []),
        "domain_reality_evidence",
        required_fields=frozenset(
            {
                "evidence_id",
                "target_id",
                "domain",
                "direction",
                "detail",
                "weight",
                "verified",
                "source_id",
            }
        ),
    )
    prior_events = _records(
        request.get("prior_event_evidence", []),
        "prior_event_evidence",
        required_fields=frozenset(
            {
                "evidence_id",
                "claim_id",
                "scope",
                "source_id",
                "direction",
                "verified",
                "detail_code",
            }
        ),
    )
    fixture = _fixture_provenance(request.get("fixture_provenance"))
    peer_raw = request.get("compatibility_peer_fact_graph")
    peer_graph = (
        _mapping(peer_raw, "compatibility_peer_fact_graph")
        if peer_raw is not None
        else None
    )
    try:
        reality_context = normalize_reality_context(raw_reality)
        natal = _run_natal_core(fact_graph)
        interaction = evaluate_luck_cycle_role_interactions(
            fact_graph, natal["phase12"]
        ).to_dict()
        trend = evaluate_bazi_temporal_trends(
            fact_graph,
            interaction,
            reality_evidence=temporal_reality,
        ).to_dict()
        domains = evaluate_bazi_tengod_domains(
            fact_graph,
            interaction,
            trend,
            reality_evidence=domain_reality,
        ).to_dict()
        base_domains = evaluate_base_domain_contracts(domains).to_dict()
        exam = evaluate_special_scenario(
            base_domains,
            scenario="career_exam",
            target_id=target_id,
            reality_context=reality_context.facts,
        ).to_dict()
        reunion = evaluate_special_scenario(
            base_domains,
            scenario="relationship_reunion",
            target_id=target_id,
            reality_context=reality_context.facts,
        ).to_dict()
        compatibility, compatibility_availability, peer_refs = _compatibility_view(
            natal, peer_graph
        )
    except _PHASE_ERRORS as exc:
        raise BaziExpertV2InputError(
            f"fact graph canonical_hash orchestration failed: {exc}"
        ) from exc

    selected_contracts = {
        domain: _find_by_target(
            base_domains["domain_contracts"], target_id, domain=domain
        )
        for domain in ("career", "wealth", "relationship")
    }
    study_judgement = _find_by_target(
        domains["domain_judgements"], target_id, domain="education"
    )
    selected_trend = _find_by_target(
        [
            *trend["dayun_trends"],  # type: ignore[index]
            *trend["liunian_trends"],  # type: ignore[index]
            *trend["combined_trends"],  # type: ignore[index]
        ],
        target_id,
    )
    scenario_exam_view, scenario_reunion_view = _scenario_views(exam, reunion)

    fusion_items: list[dict[str, object]] = []
    selected_judgements = {
        domain: _find_by_target(
            domains["domain_judgements"], target_id, domain=domain
        )
        for domain in ("career", "wealth", "relationship", "education")
    }
    fusion_items.extend(
        _domain_fusion_evidence(
            selected_judgements,
            domain_reality,
            str(domains["canonical_hash"]),
        )
    )
    fusion_items.extend(
        _temporal_fusion_evidence(
            selected_trend, temporal_reality, str(trend["canonical_hash"])
        )
    )
    fusion_items.extend(_scenario_fusion_evidence(exam))
    fusion_items.extend(_scenario_fusion_evidence(reunion))
    fusion_items.extend(_prior_event_fusion_evidence(prior_events))
    try:
        fusion = orchestrate_evidence_fusion(
            reality_context, tuple(sorted(fusion_items, key=canonical_json))
        ).to_dict()
    except Phase18InputError as exc:
        raise BaziExpertV2InputError(f"evidence fusion failed closed: {exc}") from exc
    calibrated = _calibrated_claims(fusion)

    source_results: dict[str, dict[str, object]] = {
        key: _source_ref(value) for key, value in natal.items()
    }
    for key, value in (
        ("phase13", interaction),
        ("phase14", trend),
        ("phase15", domains),
        ("phase16", base_domains),
        ("phase18", fusion),
    ):
        source_results[key] = _source_ref(value)
    source_results["phase17"] = _scenario_bundle_ref(exam, reunion)

    strength = natal["phase9"]
    pattern = natal["phase10"]
    regulation = natal["phase11"]
    xiji = natal["phase12"]
    selected_hits = [
        dict(item)
        for item in domains["dynamic_hits"]  # type: ignore[index]
        if isinstance(item, Mapping) and item.get("target_id") == target_id
    ]
    selected_conflicts = [
        dict(item)
        for item in domains["cross_domain_conflicts"]  # type: ignore[index]
        if isinstance(item, Mapping) and item.get("target_id") == target_id
    ]
    relation_summary = _relation_summary(fact_graph, interaction)
    prior_claim_ids = {str(item["claim_id"]) for item in prior_events}
    prior_claims = [
        dict(item)
        for item in fusion["claims"]  # type: ignore[index]
        if isinstance(item, Mapping) and item.get("claim_id") in prior_claim_ids
    ]
    override_claims = [
        dict(item)
        for item in fusion["claims"]  # type: ignore[index]
        if isinstance(item, Mapping)
        and item.get("status")
        in {"resolved_by_reality_override", "unresolved_conflict"}
    ]

    facets: dict[str, CapabilityFacet] = {}
    facets["five_element_strength"] = _facet(
        "five_element_strength",
        "implemented",
        "available",
        "low" if strength["classification"] == "unresolved" else "medium",
        ("phase9",),
        ("structural_quantification_not_accuracy",),
        {
            "day_master": strength["day_master"],
            "day_master_element": strength["day_master_element"],
            "element_scores": strength["element_scores"],
            "classification": strength["classification"],
            "source_result_hash": strength["canonical_hash"],
        },
    )
    facets["same_kind_different_kind"] = _facet(
        "same_kind_different_kind",
        "implemented",
        "available",
        "low" if strength["classification"] == "unresolved" else "medium",
        ("phase9",),
        ("same_kind_maps_to_phase9_support", "different_kind_maps_to_phase9_opposition"),
        {
            "same_kind_score": strength["support_score"],
            "different_kind_score": strength["opposition_score"],
            "same_kind_ratio": strength["support_ratio"],
            "different_kind_ratio": strength["opposition_ratio"],
            "net_score": strength["net_score"],
        },
    )
    facets["pattern"] = _facet(
        "pattern",
        "conditional",
        "available",
        "low" if pattern["unresolved"] else "medium",
        ("phase10",),
        ("candidate_only", "no_concrete_event_inference"),
        {
            "candidate_only": True,
            "primary_candidates": pattern["primary_candidates"],
            "candidates": pattern["candidates"],
            "conflicts": pattern["conflicts"],
            "unresolved": pattern["unresolved"],
        },
    )
    facets["yongshen_climate_regulation"] = _facet(
        "yongshen_climate_regulation",
        "conditional",
        "available",
        "low" if regulation["unresolved"] else "medium",
        ("phase11", "phase12"),
        (
            "candidate_only",
            "classical_daymaster_month_tiaohou_not_evaluated",
            "xiji_roles_structural_only",
        ),
        {
            "primary_candidates": regulation["primary_candidates"],
            "secondary_candidates": regulation["secondary_candidates"],
            "candidates": regulation["candidates"],
            "seasonal_climate_needs": regulation["seasonal_climate_needs"],
            "yongshen_elements": xiji["yongshen_elements"],
            "xishen_elements": xiji["xishen_elements"],
            "classification_status": xiji["classification_status"],
        },
    )
    facets["ten_god_combinations"] = _facet(
        "ten_god_combinations",
        "conditional",
        "available",
        _structural_confidence(study_judgement["confidence"]),  # type: ignore[arg-type]
        ("phase15",),
        ("candidate_only", "ten_god_theme_does_not_imply_event"),
        {
            "target_id": target_id,
            "natal_context": domains["natal_context"],
            "dynamic_hits": selected_hits,
            "cross_domain_conflicts": selected_conflicts,
        },
    )
    facets["punishment_clash_combine_harm"] = _facet(
        "punishment_clash_combine_harm",
        "implemented",
        "available",
        "medium",
        ("phase7", "phase13"),
        ("relation_summary_only", "no_transformation_or_event_inference"),
        relation_summary,
    )
    facets["decadal_luck"] = _facet(
        "decadal_luck",
        "implemented",
        "available",
        _aggregate_confidence(
            [
                _structural_confidence(item.get("confidence"))
                for item in trend["dayun_trends"]  # type: ignore[index]
                if isinstance(item, Mapping)
            ]
        ),
        ("phase13", "phase14"),
        ("structural_tendency_only", "no_concrete_event_prediction"),
        {
            "interactions": interaction["dayun_interactions"],
            "trends": trend["dayun_trends"],
        },
    )
    facets["annual_scope"] = _facet(
        "annual_scope",
        "implemented",
        "available",
        _structural_confidence(
            selected_trend["confidence"],
            reality_override=selected_trend.get("reality_override_direction") is not None,
        ),  # type: ignore[arg-type]
        ("phase13", "phase14"),
        ("structural_tendency_only", "no_concrete_event_prediction"),
        {
            "selected_target": selected_trend,
            "interactions": interaction["liunian_interactions"],
            "trends": trend["liunian_trends"],
        },
    )
    facets["monthly_scope"] = _facet(
        "monthly_scope",
        "unsupported",
        "unsupported_by_frozen_phases",
        "not_applicable",
        ("phase13", "phase14"),
        ("no_liuyue_contract_in_frozen_phases", "fail_closed"),
        {"scope": "monthly", "rule_coverage": "unsupported"},
    )
    for domain in ("career", "wealth", "relationship"):
        contract = selected_contracts[domain]
        facets[domain] = _facet(
            domain,
            "conditional",
            "available",
            _structural_confidence(
                contract["confidence"],
                reality_override=contract.get("reality_override") is True,
            ),  # type: ignore[arg-type]
            ("phase15", "phase16", "phase18"),
            ("candidate_only", "scope_specific_reality_override"),
            _domain_facet_data(contract),
        )
    facets["marriage"] = _facet(
        "marriage",
        "unsupported",
        "unsupported_by_frozen_phases",
        "not_applicable",
        ("phase16", "phase17"),
        ("no_marriage_event_contract", "relationship_tendency_is_not_marriage"),
        {
            "relationship_source_available": True,
            "concrete_event_prediction": "unsupported",
        },
    )
    facets["study"] = _facet(
        "study",
        "conditional",
        "available",
        _structural_confidence(
            study_judgement["confidence"],
            reality_override=study_judgement.get("reality_override_direction")
            is not None,
        ),  # type: ignore[arg-type]
        ("phase15", "phase18"),
        ("education_domain_candidate_only", "no_exam_outcome_guarantee"),
        {
            "target_id": target_id,
            "target_type": study_judgement["target_type"],
            "judgement_label": study_judgement["judgement_label"],
            "confidence": study_judgement["confidence"],
            "active_theme_codes": study_judgement["active_theme_codes"],
            "top_ten_gods": study_judgement["top_ten_gods"],
            "reality_override_direction": study_judgement[
                "reality_override_direction"
            ],
            "source_digest": study_judgement["canonical_digest"],
        },
    )
    facets["family"] = _facet(
        "family",
        "unsupported",
        "unsupported_by_frozen_phases",
        "not_applicable",
        ("phase15", "phase16"),
        ("no_family_domain_contract", "fail_closed"),
        {"rule_coverage": "unsupported"},
    )
    exam_confidences = [
        str(item["confidence"])
        for item in (
            scenario_exam_view["system_fit"],
            scenario_exam_view["exam_conditions"]["eligibility"],  # type: ignore[index]
            scenario_exam_view["exam_conditions"]["exam_outlook"],  # type: ignore[index]
            scenario_exam_view["role_direction"],
            scenario_exam_view["preparation_strategy"],
        )
        if isinstance(item, Mapping)
    ]
    facets["civil_service_exam"] = _facet(
        "civil_service_exam",
        "conditional",
        "available",
        _aggregate_confidence(exam_confidences),
        ("phase16", "phase17", "phase18"),
        ("no_guaranteed_admission", "reality_override_is_layer_scoped"),
        scenario_exam_view,
    )
    reunion_confidences = [
        str(scenario_reunion_view[key]["confidence"])  # type: ignore[index]
        for key in ("attraction", "contact", "reunion", "stability")
    ]
    facets["relationship_reunion"] = _facet(
        "relationship_reunion",
        "conditional",
        "available",
        _aggregate_confidence(reunion_confidences),
        ("phase16", "phase17", "phase18"),
        ("no_guaranteed_reunion", "reality_override_is_layer_scoped"),
        scenario_reunion_view,
    )
    compatibility_data = dict(compatibility)
    if peer_refs is not None:
        compatibility_data["peer_source_results"] = peer_refs
    facets["dual_person_compatibility"] = _facet(
        "dual_person_compatibility",
        "conditional",
        compatibility_availability,
        "low",
        ("phase9", "phase10", "phase11", "phase12"),
        ("comparison_only", "no_compatibility_score", "no_outcome_prediction"),
        compatibility_data,
    )
    facets["prior_event_validation"] = _facet(
        "prior_event_validation",
        "conditional",
        "available" if prior_events else "not_requested",
        _aggregate_confidence(
            [
                str(item["confidence"])
                for item in calibrated
                if item["claim_id"] in prior_claim_ids
            ]
        ),
        ("phase18",),
        (
            "verified_reality_only",
            "contract_validation_not_predictive_accuracy",
        ),
        {"claims": prior_claims, "accuracy_evidence": False},
    )
    facets["reality_evidence_override"] = _facet(
        "reality_evidence_override",
        "implemented",
        "available",
        _aggregate_confidence(
            [
                str(item["confidence"])
                for item in calibrated
                if item["status"]
                in {"resolved_by_reality_override", "unresolved_conflict"}
            ]
        ),
        ("phase14", "phase15", "phase17", "phase18"),
        ("claim_and_scope_specific", "conflicting_verified_reality_is_unresolved"),
        {"claims": override_claims},
    )
    facets["confidence_calibration"] = _facet(
        "confidence_calibration",
        "implemented",
        "available",
        _aggregate_confidence([str(item["confidence"]) for item in calibrated]),
        ("phase18",),
        ("structural_high_confidence_prohibited", "unresolved_is_low"),
        {"claims": list(calibrated)},
    )

    yuan: dict[str, object] | None = None
    renderer_availability = "not_requested"
    renderer_data: dict[str, object] = {"rendered": False}
    renderer_context_raw = request.get("renderer_context")
    if renderer_context_raw is not None:
        renderer_context = _mapping(renderer_context_raw, "renderer_context")
        try:
            adapted, renderer_availability = _renderer_payload(
                renderer_context, selected_contracts, trend
            )
            if adapted is not None:
                yuan = render_yuan_eight_sections(adapted).to_dict()
                source_results["phase20"] = _source_ref(yuan)
                renderer_data = {
                    "rendered": True,
                    "source_hash": yuan["canonical_hash"],
                    "section_count": len(yuan["sections"]),  # type: ignore[arg-type]
                }
        except Phase20InputError as exc:
            raise BaziExpertV2InputError(
                f"Yuan renderer adapter failed closed: {exc}"
            ) from exc
    facets["yuan_renderer_adapter"] = _facet(
        "yuan_renderer_adapter",
        "conditional",
        renderer_availability,
        "low"
        if yuan is None
        else _aggregate_confidence(
            [facets[key].confidence for key in ("career", "wealth", "relationship")]
        ),
        ("phase14", "phase16", "phase20"),
        ("controlled_language_only", "single_disclaimer", "no_absolute_promises"),
        renderer_data,
    )

    if tuple(facets) != _FACET_ORDER:
        raise AssertionError("Bazi Expert V2 facet order invariant violated")
    facet_summary = {
        status: tuple(
            facet_id
            for facet_id in _FACET_ORDER
            if facets[facet_id].status == status
        )
        for status in ("implemented", "conditional", "unsupported")
    }
    confidence, confidence_reasons = _overall_confidence(facets, calibrated)
    normalized_request = {
        "schema_version": BAZI_EXPERT_V2_INPUT_SCHEMA_VERSION,
        "fact_graph": fact_graph,
        "target_id": target_id,
        "reality_context": reality_context.to_dict(),
        "temporal_reality_evidence": list(temporal_reality),
        "domain_reality_evidence": list(domain_reality),
        "prior_event_evidence": list(prior_events),
        "compatibility_peer_fact_graph": peer_graph,
        "renderer_context": request.get("renderer_context"),
        "fixture_provenance": fixture,
    }
    request_hash = _record_digest("BaziExpertV2Request", normalized_request)
    warnings = (
        "existing_phase_outputs_composed_without_rule_duplication",
        "candidate_and_conditional_wording_preserved",
        "unsupported_facets_fail_closed",
        "synthetic_fixtures_are_contract_tests_only",
        "prediction_validity_not_evaluated",
        "product_release_hold_active",
    )
    unsupported = tuple(facet_summary["unsupported"])
    body: dict[str, object] = {
        "request_hash": request_hash,
        "selected_target_id": target_id,
        "source_results": source_results,
        "facets": {key: value.to_dict() for key, value in facets.items()},
        "facet_summary": {key: list(value) for key, value in facet_summary.items()},
        "evidence_fusion": fusion,
        "calibrated_claims": list(calibrated),
        "yuan": yuan,
        "fixture_provenance": fixture,
        "confidence": confidence,
        "confidence_reason_codes": list(confidence_reasons),
        "warnings": list(warnings),
        "unsupported": list(unsupported),
        "release_hold": "ACTIVE",
        "accuracy_claim_allowed": False,
    }
    return BaziExpertV2Result(
        request_hash=request_hash,
        selected_target_id=target_id,
        source_results=source_results,
        facets=facets,
        facet_summary=facet_summary,
        evidence_fusion=fusion,
        calibrated_claims=calibrated,
        yuan=yuan,
        fixture_provenance=fixture,
        confidence=confidence,
        confidence_reason_codes=confidence_reasons,
        warnings=warnings,
        unsupported=unsupported,
        canonical_hash=_record_digest("BaziExpertV2Result", body),
    )
