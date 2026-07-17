from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import resources
import json
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .bazi_expert_v2 import BaziExpertV2InputError, orchestrate_bazi_expert_v2
from .contracts.serialization import canonical_json, digest
from .phase20 import DISCLAIMER, FORBIDDEN_PROMISES
from .real_case_learning_v2 import RealCaseLearningV2Error, summarize_learning_cases
from .ziwei_temporal_v2 import (
    ZiweiTemporalV2Error,
    build_ziwei_temporal_v2_coverage,
    evaluate_ziwei_temporal_v2,
)

CAPABILITY_SURGE_V2_INPUT_SCHEMA_VERSION = "mingli-core-capability-surge-input@2.0"
CAPABILITY_SURGE_V2_SCHEMA_VERSION = "mingli-core-capability-surge-result@2.0"
CAPABILITY_SURGE_V2_METHOD_ID = "mingli-core-capability-surge@2.0.0"
PREDICTION_VALIDITY = "not_evaluated"
RELEASE_HOLD = "ACTIVE"

_ALLOWED_INPUT_FIELDS = frozenset(
    {
        "schema_version",
        "bazi_request",
        "ziwei_chart",
        "ziwei_overlays",
        "ziwei_reality_evidence",
        "learning_cases",
        "evaluation_at",
    }
)


class CapabilitySurgeV2Error(ValueError):
    """Fail-closed boundary error for the additive V2 integration layer."""


@dataclass(frozen=True)
class CapabilitySurgeV2Result:
    components: Mapping[str, object]
    component_hashes: Mapping[str, str]
    renderer: Mapping[str, object]
    capability_matrix: Mapping[str, object]
    unsupported: tuple[Mapping[str, object], ...]
    warnings: tuple[str, ...]
    canonical_hash: str
    schema_version: str = CAPABILITY_SURGE_V2_SCHEMA_VERSION
    method_id: str = CAPABILITY_SURGE_V2_METHOD_ID
    prediction_validity: str = PREDICTION_VALIDITY
    release_hold: str = RELEASE_HOLD
    accuracy_claim_allowed: bool = False

    def to_dict(self) -> dict[str, object]:
        return json.loads(canonical_json(asdict(self)))


def load_capability_surge_v2_schema() -> dict[str, object]:
    value = resources.files("mingli.contracts.schemas").joinpath(
        "capability_surge_v2_result.schema.json"
    )
    return json.loads(value.read_text(encoding="utf-8"))


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise CapabilitySurgeV2Error(f"{field} must be an object")
    return dict(value)


def _records(value: object, field: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CapabilitySurgeV2Error(f"{field} must be an array")
    records: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise CapabilitySurgeV2Error(f"{field} entries must be objects")
        records.append(dict(item))
    return tuple(records)


def _strings(value: object, field: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CapabilitySurgeV2Error(f"{field} must be an array")
    if any(not isinstance(item, str) or not item for item in value):
        raise CapabilitySurgeV2Error(f"{field} must contain non-empty strings")
    return list(value)


def _unsupported_rows(bazi: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    summary = _mapping(bazi.get("facet_summary"), "bazi.facet_summary")
    raw = _strings(summary.get("unsupported"), "bazi.facet_summary.unsupported")
    rows: list[dict[str, object]] = [
        {
            "capability": f"bazi.{facet}",
            "status": "unsupported",
            "reason": "unsupported_by_frozen_contracts",
            "behavior": "fail_closed",
        }
        for facet in raw
    ]
    rows.append(
        {
            "capability": "real_case_learning.accuracy_claim",
            "status": "unsupported",
            "reason": "no_independently_qualified_real_case_dataset",
            "behavior": "release_hold_active",
        }
    )
    return tuple(rows)


def _renderer(bazi: Mapping[str, object]) -> dict[str, object]:
    yuan = bazi.get("yuan")
    if not isinstance(yuan, Mapping):
        raise CapabilitySurgeV2Error(
            "Bazi Expert V2 Yuan renderer output is required for unified runtime"
        )
    rendered = yuan.get("rendered_text")
    if (
        not isinstance(rendered, str)
        or rendered.count(DISCLAIMER) != 1
        or not rendered.endswith(DISCLAIMER)
    ):
        raise CapabilitySurgeV2Error("Yuan renderer single-disclaimer contract failed")
    if any(token in rendered for token in FORBIDDEN_PROMISES):
        raise CapabilitySurgeV2Error("Yuan renderer contains a forbidden promise")
    return {"source": "bazi_expert_v2.phase20", **dict(yuan)}


def _capability_matrix(
    bazi: Mapping[str, object],
    ziwei_coverage: Mapping[str, object],
    learning: Mapping[str, object],
) -> dict[str, object]:
    summary = _mapping(bazi.get("facet_summary"), "bazi.facet_summary")
    return {
        "bazi": {
            key: _strings(summary.get(key, ()), f"bazi.facet_summary.{key}")
            for key in ("implemented", "conditional", "unsupported")
        },
        "ziwei": {
            "rule_count": ziwei_coverage.get("rule_count"),
            "covered_count": ziwei_coverage.get("covered_count"),
            "behavioral_coverage_complete": ziwei_coverage.get("complete") is True,
            "accuracy_assessment": ziwei_coverage.get("accuracy_assessment"),
        },
        "real_case_learning": {
            "total_cases": learning.get("total_cases"),
            "synthetic_contract_cases": learning.get("synthetic_contract_cases"),
            "accuracy_metrics": learning.get("accuracy_metrics"),
            "automatic_rule_actions": 0,
            "product_accuracy_claim_allowed": learning.get(
                "product_accuracy_claim_allowed"
            ),
        },
    }


def run_capability_surge_v2(
    raw: Mapping[str, object],
) -> CapabilitySurgeV2Result:
    if not isinstance(raw, Mapping):
        raise CapabilitySurgeV2Error("input must be an object")
    request = dict(raw)
    extra = sorted(set(request).difference(_ALLOWED_INPUT_FIELDS))
    if extra:
        raise CapabilitySurgeV2Error(f"unsupported input fields: {extra}")
    if request.get("schema_version") != CAPABILITY_SURGE_V2_INPUT_SCHEMA_VERSION:
        raise CapabilitySurgeV2Error("unsupported capability surge schema_version")

    bazi_request = _mapping(request.get("bazi_request"), "bazi_request")
    ziwei_chart = _mapping(request.get("ziwei_chart"), "ziwei_chart")
    overlays = _records(request.get("ziwei_overlays", ()), "ziwei_overlays")
    ziwei_evidence = _records(
        request.get("ziwei_reality_evidence", ()),
        "ziwei_reality_evidence",
    )
    learning_cases = _records(request.get("learning_cases", ()), "learning_cases")
    evaluation_at = request.get("evaluation_at")
    bazi_evidence_fields = (
        "temporal_reality_evidence",
        "domain_reality_evidence",
        "prior_event_evidence",
    )
    has_direct_evidence = bool(ziwei_evidence) or any(
        bool(bazi_request.get(field)) for field in bazi_evidence_fields
    )
    if has_direct_evidence and (
        not isinstance(evaluation_at, str) or not evaluation_at
    ):
        raise CapabilitySurgeV2Error(
            "evaluation_at is required when direct Reality Evidence is supplied"
        )
    if evaluation_at is not None:
        if not isinstance(evaluation_at, str) or not evaluation_at:
            raise CapabilitySurgeV2Error("evaluation_at must be a non-empty string")
        nested_evaluation_at = bazi_request.get("evaluation_at")
        if nested_evaluation_at is not None and nested_evaluation_at != evaluation_at:
            raise CapabilitySurgeV2Error(
                "bazi_request evaluation_at must match the unified evaluation_at"
            )
        bazi_request["evaluation_at"] = evaluation_at

    try:
        bazi = orchestrate_bazi_expert_v2(bazi_request).to_dict()
    except BaziExpertV2InputError as exc:
        raise CapabilitySurgeV2Error(f"Bazi Expert V2 failed closed: {exc}") from exc
    try:
        ziwei = evaluate_ziwei_temporal_v2(
            ziwei_chart,
            overlays=overlays,
            reality_evidence=ziwei_evidence,
            evaluation_at=evaluation_at,
        )
        ziwei_coverage = build_ziwei_temporal_v2_coverage()
    except ZiweiTemporalV2Error as exc:
        raise CapabilitySurgeV2Error(f"Ziwei Temporal V2 failed closed: {exc}") from exc
    try:
        learning = summarize_learning_cases(learning_cases)
    except RealCaseLearningV2Error as exc:
        raise CapabilitySurgeV2Error(f"Real Case Learning V2 failed closed: {exc}") from exc

    for name, value in (
        ("bazi", bazi),
        ("ziwei", ziwei),
        ("real_case_learning", learning),
    ):
        if value.get("prediction_validity") != PREDICTION_VALIDITY:
            raise CapabilitySurgeV2Error(
                f"{name} prediction_validity contract was weakened"
            )
        hold = value.get("release_hold", value.get("commercial_release_hold"))
        if hold != RELEASE_HOLD:
            raise CapabilitySurgeV2Error(f"{name} Release Hold must remain ACTIVE")

    renderer = _renderer(bazi)
    components = {
        "bazi": bazi,
        "ziwei": ziwei,
        "real_case_learning": learning,
    }
    component_hashes = {
        name: str(value["canonical_hash"]) for name, value in components.items()
    }
    matrix = _capability_matrix(bazi, ziwei_coverage, learning)
    unsupported = _unsupported_rows(bazi)
    warnings = (
        "component_contracts_are_versioned_and_additive",
        "Reality_Evidence_override_remains_claim_and_scope_specific",
        "synthetic_fixtures_do_not_establish_accuracy",
        "unsupported_capabilities_fail_closed",
        "release_hold_remains_active",
    )
    body: dict[str, object] = {
        "schema_version": CAPABILITY_SURGE_V2_SCHEMA_VERSION,
        "method_id": CAPABILITY_SURGE_V2_METHOD_ID,
        "components": components,
        "component_hashes": component_hashes,
        "renderer": renderer,
        "capability_matrix": matrix,
        "unsupported": list(unsupported),
        "warnings": list(warnings),
        "prediction_validity": PREDICTION_VALIDITY,
        "release_hold": RELEASE_HOLD,
        "accuracy_claim_allowed": False,
    }
    canonical_hash = digest(
        {"record_type": "MingLiCoreCapabilitySurgeV2Result", "payload": body}
    )
    body["canonical_hash"] = canonical_hash
    try:
        Draft202012Validator(load_capability_surge_v2_schema()).validate(body)
    except ValidationError as exc:
        raise CapabilitySurgeV2Error(
            f"capability surge result schema failed: {exc.message}"
        ) from exc
    return CapabilitySurgeV2Result(
        components=components,
        component_hashes=component_hashes,
        renderer=renderer,
        capability_matrix=matrix,
        unsupported=unsupported,
        warnings=warnings,
        canonical_hash=canonical_hash,
    )


__all__ = [
    "CAPABILITY_SURGE_V2_INPUT_SCHEMA_VERSION",
    "CAPABILITY_SURGE_V2_METHOD_ID",
    "CAPABILITY_SURGE_V2_SCHEMA_VERSION",
    "CapabilitySurgeV2Error",
    "CapabilitySurgeV2Result",
    "load_capability_surge_v2_schema",
    "run_capability_surge_v2",
]
