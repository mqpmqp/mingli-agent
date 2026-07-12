from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .models import Evidence, RULE_STATUSES

PHASE8_SCHEMA_VERSION = "rule-evaluation-evidence-result@0.1"
PHASE8_METHOD_ID = "deterministic-rule-evaluation-evidence@0.1.0"
PHASE8_CALCULATION_VERSION = "0.1.0"
PHASE8_DECISION_ID = "PHASE_8_RULE_EVALUATION_EVIDENCE_R1_APPROVED"
EXECUTABLE_RULE_STATUSES = frozenset({"reviewed", "verified"})
FACT_COLLECTIONS = frozenset({"root", "nodes", "edges", "relations", "growth_stages", "profiles"})
FACT_QUANTIFIERS = frozenset({"any", "none", "all", "count_at_least"})
REALITY_OPERATORS = frozenset({"equals", "not_equals", "in", "contains", "exists", "gte", "lte"})
RULE_MATCH_STATUSES = frozenset({"matched", "not_matched", "blocked", "skipped"})
RESOLUTION_STATUSES = frozenset({"supported", "contradicted", "resolved_by_priority", "resolved_by_reality_override", "unresolved_conflict", "no_evidence"})


def _plain_dataclass(value: object) -> dict[str, object]:
    return json.loads(canonical_json(asdict(value)))


def _record_digest(record_type: str, payload: Mapping[str, object]) -> str:
    body = {key: value for key, value in payload.items() if key not in {"canonical_digest", "canonical_hash"}}
    return digest({"record_type": record_type, "payload": body})


def _require_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _string_tuple(value: object, field_name: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be an array of strings")
    result = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{field_name} must contain non-empty strings only")
    if not allow_empty and not result:
        raise ValueError(f"{field_name} must not be empty")
    return result


def _lookup(value: Mapping[str, object], path: str) -> tuple[bool, object | None]:
    current: object = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _source_ref(record: Mapping[str, object], collection: str, index: int) -> str:
    for key in ("node_id", "edge_id", "relation_id", "fact_id", "profile_id", "period_id", "snapshot_id"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return f"{collection}:{index}"


@dataclass(frozen=True)
class ConditionSpec:
    condition_id: str
    source: Literal["fact_graph", "reality"]
    collection: str | None = None
    where: Mapping[str, object] = field(default_factory=dict)
    quantifier: str = "any"
    threshold: int = 1
    path: str | None = None
    operator: str | None = None
    value: object | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ConditionSpec":
        allowed = {"condition_id", "source", "collection", "where", "quantifier", "threshold", "path", "operator", "value"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"condition contains unknown fields: {', '.join(sorted(unknown))}")
        condition_id = _require_string(value.get("condition_id"), "condition_id")
        source = value.get("source")
        if source not in {"fact_graph", "reality"}:
            raise ValueError("condition.source must be fact_graph or reality")
        if source == "fact_graph":
            collection = value.get("collection")
            if collection not in FACT_COLLECTIONS:
                raise ValueError(f"condition.collection must be one of: {', '.join(sorted(FACT_COLLECTIONS))}")
            where = value.get("where", {})
            if not isinstance(where, Mapping):
                raise ValueError("condition.where must be an object")
            quantifier = value.get("quantifier", "any")
            if quantifier not in FACT_QUANTIFIERS:
                raise ValueError(f"condition.quantifier must be one of: {', '.join(sorted(FACT_QUANTIFIERS))}")
            threshold = value.get("threshold", 1)
            if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
                raise ValueError("condition.threshold must be a positive integer")
            return cls(
                condition_id=condition_id,
                source="fact_graph",
                collection=str(collection),
                where=dict(where),
                quantifier=str(quantifier),
                threshold=threshold,
            )
        path = _require_string(value.get("path"), "condition.path")
        operator = value.get("operator")
        if operator not in REALITY_OPERATORS:
            raise ValueError(f"condition.operator must be one of: {', '.join(sorted(REALITY_OPERATORS))}")
        return cls(
            condition_id=condition_id,
            source="reality",
            path=path,
            operator=str(operator),
            value=value.get("value"),
        )

    def to_dict(self) -> dict[str, object]:
        payload = _plain_dataclass(self)
        return {key: value for key, value in payload.items() if value not in (None, {}, [])}


@dataclass(frozen=True)
class EvaluationRule:
    rule_id: str
    version: str
    domain: str
    claim_id: str
    claim_text: str
    direction: Literal["support", "contradict"]
    weight: float
    priority: int
    status: str
    required_conditions: tuple[ConditionSpec, ...]
    blocking_conditions: tuple[ConditionSpec, ...]
    evidence_detail: str
    plain_language: str
    reality_override_codes: tuple[str, ...]
    source_ids: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "EvaluationRule":
        allowed = {
            "rule_id", "version", "domain", "claim_id", "claim_text", "direction", "weight", "priority",
            "status", "required_conditions", "blocking_conditions", "evidence_detail", "plain_language",
            "reality_override_codes", "source_ids",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"rule contains unknown fields: {', '.join(sorted(unknown))}")
        required_fields = {
            "rule_id", "version", "domain", "claim_id", "claim_text", "direction", "weight", "priority",
            "status", "required_conditions", "evidence_detail", "plain_language", "source_ids",
        }
        missing = required_fields - set(value)
        if missing:
            raise ValueError(f"rule missing fields: {', '.join(sorted(missing))}")
        direction = value.get("direction")
        if direction not in {"support", "contradict"}:
            raise ValueError("rule.direction must be support or contradict")
        weight = value.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= float(weight) <= 10:
            raise ValueError("rule.weight must be between 0 and 10")
        priority = value.get("priority")
        if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 100:
            raise ValueError("rule.priority must be an integer between 1 and 100")
        status = value.get("status")
        if status not in RULE_STATUSES:
            raise ValueError(f"rule.status must be one of: {', '.join(sorted(RULE_STATUSES))}")
        raw_required = value.get("required_conditions")
        if not isinstance(raw_required, list) or not raw_required:
            raise ValueError("rule.required_conditions must be a non-empty array")
        raw_blocking = value.get("blocking_conditions", [])
        if not isinstance(raw_blocking, list):
            raise ValueError("rule.blocking_conditions must be an array")
        required_items: list[ConditionSpec] = []
        for item in raw_required:
            if not isinstance(item, Mapping):
                raise ValueError("required condition must be an object")
            required_items.append(ConditionSpec.from_mapping(item))
        blocking_items: list[ConditionSpec] = []
        for item in raw_blocking:
            if not isinstance(item, Mapping):
                raise ValueError("blocking condition must be an object")
            blocking_items.append(ConditionSpec.from_mapping(item))
        required_conditions = tuple(required_items)
        blocking_conditions = tuple(blocking_items)
        condition_ids = [item.condition_id for item in (*required_conditions, *blocking_conditions)]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("condition_id values must be unique within a rule")
        return cls(
            rule_id=_require_string(value.get("rule_id"), "rule_id"),
            version=_require_string(value.get("version"), "version"),
            domain=_require_string(value.get("domain"), "domain"),
            claim_id=_require_string(value.get("claim_id"), "claim_id"),
            claim_text=_require_string(value.get("claim_text"), "claim_text"),
            direction=str(direction),  # type: ignore[arg-type]
            weight=float(weight),
            priority=priority,
            status=str(status),
            required_conditions=required_conditions,
            blocking_conditions=blocking_conditions,
            evidence_detail=_require_string(value.get("evidence_detail"), "evidence_detail"),
            plain_language=_require_string(value.get("plain_language"), "plain_language"),
            reality_override_codes=_string_tuple(value.get("reality_override_codes", []), "reality_override_codes"),
            source_ids=_string_tuple(value.get("source_ids"), "source_ids", allow_empty=False),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "version": self.version,
            "domain": self.domain,
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "direction": self.direction,
            "weight": self.weight,
            "priority": self.priority,
            "status": self.status,
            "required_conditions": [item.to_dict() for item in self.required_conditions],
            "blocking_conditions": [item.to_dict() for item in self.blocking_conditions],
            "evidence_detail": self.evidence_detail,
            "plain_language": self.plain_language,
            "reality_override_codes": list(self.reality_override_codes),
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class ConditionResult:
    condition_id: str
    matched: bool
    matched_count: int
    source_refs: tuple[str, ...]
    detail: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    claim_id: str
    priority: int
    status: str
    required_results: tuple[Mapping[str, object], ...]
    blocking_results: tuple[Mapping[str, object], ...]
    reason: str
    emitted_evidence_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    claim_id: str
    source_type: Literal["rule", "reality"]
    source_id: str
    detail: str
    direction: Literal["support", "contradict"]
    weight: float
    priority: int
    verified: bool
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)

    def to_model(self) -> Evidence:
        return Evidence(
            source_type=self.source_type,
            detail=self.detail,
            direction=self.direction,
            weight=self.weight,
            source_id=self.source_id,
            verified=self.verified,
        )


@dataclass(frozen=True)
class RealityOverrideRecord:
    override_id: str
    code: str
    message: str
    direction: Literal["contradict"]
    target_claim_ids: tuple[str, ...]
    emitted_evidence_ids: tuple[str, ...]
    verified: bool
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class ConflictRecord:
    conflict_id: str
    claim_id: str
    support_evidence_ids: tuple[str, ...]
    contradict_evidence_ids: tuple[str, ...]
    resolution_status: str
    winning_direction: str | None
    rationale: str
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class ConfidenceInputRecord:
    claim_id: str
    level: Literal["high", "medium", "low"]
    rationale: str
    scope: str
    support_count: int
    contradict_count: int
    verified_reality_count: int
    unresolved_conflict: bool
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class ClaimResolution:
    claim_id: str
    claim_text: str
    final_direction: Literal["support", "contradict", "unresolved", "none"]
    resolution_status: str
    support_score: float
    contradict_score: float
    hard_override_direction: str | None
    evidence_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    confidence: Mapping[str, object]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class RuleEvaluationResult:
    fact_graph_hash: str
    rule_set_hash: str
    intent: str
    rule_matches: tuple[Mapping[str, object], ...]
    evidence_records: tuple[Mapping[str, object], ...]
    reality_overrides: tuple[Mapping[str, object], ...]
    conflicts: tuple[Mapping[str, object], ...]
    claim_resolutions: tuple[Mapping[str, object], ...]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE8_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE8_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE8_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "fact_graph_hash": self.fact_graph_hash,
            "rule_set_hash": self.rule_set_hash,
            "intent": self.intent,
            "rule_matches": list(self.rule_matches),
            "evidence_records": list(self.evidence_records),
            "reality_overrides": list(self.reality_overrides),
            "conflicts": list(self.conflicts),
            "claim_resolutions": list(self.claim_resolutions),
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
class ImportOriginResult:
    mingli_file: str
    expected_root: str | None
    origin_class: Literal["checkout", "isolated_venv", "invalid"]
    valid: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mingli_file": self.mingli_file,
            "expected_root": self.expected_root,
            "origin_class": self.origin_class,
            "valid": self.valid,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Phase8BenchmarkResult:
    assertions_total: int
    rule_assertions: int
    evidence_assertions: int
    conflict_assertions: int
    confidence_assertions: int
    provenance_assertions: int
    deterministic_assertions: int
    passed: int
    failed: int
    unresolved: int
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)
