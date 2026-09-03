from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Mapping

from .advanced_runtime import (
    AdvancedContextRequest,
    build_advanced_runtime_report,
)
from .case_record import LiuYaoCaseRecord
from .interpretation import InterpretationRequest, REALITY_STATUSES, SIX_RELATIONS
from .selection_profile import (
    SELECTION_ENGINEERING_POLICY_ID,
    SELECTION_ENGINEERING_POLICY_SHA256,
    SELECTION_GATE_PRIORITY,
    SELECTION_PRIORITY_BANDS,
    SELECTION_PRIORITY_TABLE_SHA256,
    SELECTION_SOURCE_PROFILE_ID,
    SELECTION_SOURCE_PROFILE_SHA256,
    SELECTION_SOURCE_RULES,
    SELECTION_TOPIC_ALIASES,
    SELECTION_TOPIC_DIMENSIONS,
    SELECTION_TOPIC_POLICY_ID,
    SELECTION_TOPIC_POLICY_SHA256,
    find_topic_dimension,
    selection_engineering_policy_payload,
    selection_source_profile_payload,
    selection_topic_policy_payload,
)
from .tables import PREDICTION_VALIDITY, digest
from .validation import (
    LiuYaoError,
    _non_empty,
    _reject_unknown,
    _require_mapping,
    _string_tuple,
)
from .validity_matrix import (
    VALIDITY_ENGINEERING_POLICY_SHA256,
    VALIDITY_PRIORITY_TABLE_SHA256,
    VALIDITY_RULE_PROFILE_SHA256,
    HiddenValidity,
    NodeValidity,
    ValidityMatrixReport,
    ValidityRequest,
    build_validity_matrix,
)

SELECTION_RUNTIME_METHOD_ID = "liuyao-event-contract-selection-runtime@0.1.0"
SELECTION_RUNTIME_STATUS = "review_only"
SELECTION_RUNTIME_PRODUCTION_ALLOWED = False

_REALITY_ALIASES = {
    "unknown": "unknown",
    "未知": "unknown",
    "supportive": "supportive",
    "支持": "supportive",
    "blocking": "blocking",
    "阻断": "blocking",
    "mixed": "mixed",
    "混合": "mixed",
}
_EXAM_SCOPES = frozenset(
    {
        "not_applicable",
        "unknown",
        "written_or_cultural",
        "martial",
        "modern_civil_service_unspecified",
    }
)
_RELATIONSHIP_SCOPES = frozenset(
    {
        "not_applicable",
        "unknown",
        "male_subject_female_spouse",
        "female_subject_male_spouse",
        "outside_traditional_scope",
    }
)
_PREGNANCY_METHODS = frozenset(
    {"not_applicable", "unresolved", "children_relation", "fetal_marker"}
)
_GATE_ORDERS = {item.band_id: item.order for item in SELECTION_PRIORITY_BANDS}


def _bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise LiuYaoError("INVALID_INPUT", f"{name} 必须是布尔值")
    return value


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _non_empty(value, name)  # type: ignore[arg-type]


def _position(value: object, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 6:
        raise LiuYaoError("INVALID_INPUT", f"{name} 必须是 1 到 6 的整数")
    return value


@dataclass(frozen=True, slots=True)
class SelectionRequest:
    topic: str
    focus_dimension: str
    case_record_sha256: str
    event_contract_sha256: str
    advanced_context: AdvancedContextRequest
    contract_focus_confirmed: bool = False
    contract_source_refs: tuple[str, ...] = ()
    reality_status: str = "unknown"
    reality_facts: tuple[str, ...] = ()
    reality_evidence_confirmed: bool = False
    reality_evidence_refs: tuple[str, ...] = ()
    subject_mapping_confirmed: bool = False
    subject_position: int | None = None
    subject_mapping_refs: tuple[str, ...] = ()
    exam_scope: str = "not_applicable"
    exam_scope_confirmed: bool = False
    exam_scope_refs: tuple[str, ...] = ()
    relationship_pairing_scope: str = "not_applicable"
    relationship_pairing_confirmed: bool = False
    relationship_pairing_refs: tuple[str, ...] = ()
    pregnancy_method: str = "not_applicable"
    pregnancy_method_confirmed: bool = False
    pregnancy_method_refs: tuple[str, ...] = ()
    relation_choice: str | None = None
    relation_choice_confirmed: bool = False
    relation_choice_refs: tuple[str, ...] = ()
    relation_choice_reason: str | None = None
    primary_position: int | None = None
    primary_position_confirmed: bool = False
    primary_position_refs: tuple[str, ...] = ()
    review_notes: tuple[str, ...] = ()
    source_profile_id: str = SELECTION_SOURCE_PROFILE_ID
    topic_policy_id: str = SELECTION_TOPIC_POLICY_ID
    engineering_policy_id: str = SELECTION_ENGINEERING_POLICY_ID

    def __post_init__(self) -> None:
        topic_text = _non_empty(self.topic, "topic")
        topic = SELECTION_TOPIC_ALIASES.get(topic_text)
        if topic is None:
            raise LiuYaoError("INVALID_INPUT", f"第三切片不支持 topic：{topic_text}")
        object.__setattr__(self, "topic", topic)
        focus = _non_empty(self.focus_dimension, "focus_dimension")
        if find_topic_dimension(topic, focus) is None:
            raise LiuYaoError("INVALID_INPUT", f"focus_dimension 不属于 {topic}：{focus}")
        object.__setattr__(self, "focus_dimension", focus)

        if not isinstance(self.case_record_sha256, str) or not self.case_record_sha256.strip():
            raise LiuYaoError("CASE_RECORD_HASH_REQUIRED", "case_record_sha256 必须存在")
        case_record_hash = self.case_record_sha256.strip()
        if re.fullmatch(r"[0-9a-f]{64}", case_record_hash) is None:
            raise LiuYaoError("CASE_RECORD_HASH_REQUIRED", "case_record_sha256 必须是 64 位小写 SHA-256")
        object.__setattr__(self, "case_record_sha256", case_record_hash)

        if not isinstance(self.event_contract_sha256, str) or not self.event_contract_sha256.strip():
            raise LiuYaoError("CONTRACT_HASH_REQUIRED", "event_contract_sha256 必须存在")
        contract_hash = self.event_contract_sha256.strip()
        if re.fullmatch(r"[0-9a-f]{64}", contract_hash) is None:
            raise LiuYaoError("CONTRACT_HASH_REQUIRED", "event_contract_sha256 必须是 64 位小写 SHA-256")
        object.__setattr__(self, "event_contract_sha256", contract_hash)
        if not isinstance(self.advanced_context, AdvancedContextRequest):
            raise LiuYaoError("INVALID_INPUT", "advanced_context 必须是 AdvancedContextRequest")

        contract_confirmed = _bool(self.contract_focus_confirmed, "contract_focus_confirmed")
        contract_refs = _string_tuple(self.contract_source_refs, "contract_source_refs")
        object.__setattr__(self, "contract_source_refs", contract_refs)
        if contract_confirmed and not contract_refs:
            raise LiuYaoError("CONTRACT_SOURCE_REQUIRED", "确认事件焦点时必须提供 contract_source_refs")
        if contract_refs and not contract_confirmed:
            raise LiuYaoError("CONTRACT_CONFIRMATION_REQUIRED", "提供 contract_source_refs 时必须确认事件焦点")

        reality_text = _non_empty(self.reality_status, "reality_status")
        reality_status = _REALITY_ALIASES.get(reality_text)
        if reality_status is None or reality_status not in REALITY_STATUSES:
            raise LiuYaoError("INVALID_INPUT", "reality_status 必须是 unknown、supportive、blocking 或 mixed")
        object.__setattr__(self, "reality_status", reality_status)
        reality_facts = _string_tuple(self.reality_facts, "reality_facts")
        reality_refs = _string_tuple(self.reality_evidence_refs, "reality_evidence_refs")
        reality_confirmed = _bool(self.reality_evidence_confirmed, "reality_evidence_confirmed")
        object.__setattr__(self, "reality_facts", reality_facts)
        object.__setattr__(self, "reality_evidence_refs", reality_refs)
        if reality_status == "unknown" and (reality_facts or reality_refs or reality_confirmed):
            raise LiuYaoError("REALITY_STATUS_REQUIRED", "unknown 现实状态不能携带事实或证据确认")
        if reality_status != "unknown":
            if not reality_facts:
                raise LiuYaoError("INVALID_INPUT", "非 unknown 的 reality_status 必须附带 reality_facts")
            if not reality_confirmed:
                raise LiuYaoError("REALITY_CONFIRMATION_REQUIRED", "非 unknown 的现实状态必须确认")
            if not reality_refs:
                raise LiuYaoError("REALITY_EVIDENCE_REQUIRED", "非 unknown 的现实状态必须绑定 evidence refs")

        subject_position = _position(self.subject_position, "subject_position")
        subject_confirmed = _bool(self.subject_mapping_confirmed, "subject_mapping_confirmed")
        subject_refs = _string_tuple(self.subject_mapping_refs, "subject_mapping_refs")
        object.__setattr__(self, "subject_position", subject_position)
        object.__setattr__(self, "subject_mapping_refs", subject_refs)
        if subject_confirmed and (subject_position is None or not subject_refs):
            raise LiuYaoError("SUBJECT_POSITION_REQUIRED", "确认代摇主体时必须提供位置和来源引用")
        if not subject_confirmed and (subject_position is not None or subject_refs):
            raise LiuYaoError("SUBJECT_CONFIRMATION_REQUIRED", "提供主体位置或引用时必须确认主体映射")

        self._validate_scoped_context()

        relation_choice = _optional_text(self.relation_choice, "relation_choice")
        if relation_choice is not None and relation_choice not in SIX_RELATIONS:
            raise LiuYaoError("INVALID_INPUT", "relation_choice 必须是五类六亲之一")
        relation_confirmed = _bool(self.relation_choice_confirmed, "relation_choice_confirmed")
        relation_refs = _string_tuple(self.relation_choice_refs, "relation_choice_refs")
        relation_reason = _optional_text(self.relation_choice_reason, "relation_choice_reason")
        object.__setattr__(self, "relation_choice", relation_choice)
        object.__setattr__(self, "relation_choice_refs", relation_refs)
        object.__setattr__(self, "relation_choice_reason", relation_reason)
        if relation_reason is not None and relation_choice is None:
            raise LiuYaoError("INVALID_INPUT", "relation_choice_reason 不能脱离 relation_choice 单独提供")
        if relation_confirmed and (relation_choice is None or not relation_refs):
            raise LiuYaoError("RELATION_CONFIRMATION_REQUIRED", "确认六亲选择时必须提供 relation_choice 和引用")
        if not relation_confirmed and relation_refs:
            raise LiuYaoError("RELATION_CONFIRMATION_REQUIRED", "提供 relation_choice_refs 时必须确认六亲选择")
        if topic == "pregnancy" and (
            relation_choice is not None or relation_confirmed or relation_refs or relation_reason
        ):
            raise LiuYaoError("INVALID_INPUT", "求孕主题必须通过 pregnancy_method 选择方法，不能用 relation_choice 绕过")

        primary_position = _position(self.primary_position, "primary_position")
        primary_confirmed = _bool(self.primary_position_confirmed, "primary_position_confirmed")
        primary_refs = _string_tuple(self.primary_position_refs, "primary_position_refs")
        object.__setattr__(self, "primary_position", primary_position)
        object.__setattr__(self, "primary_position_refs", primary_refs)
        if primary_confirmed and (primary_position is None or not primary_refs):
            raise LiuYaoError("POSITION_CONFIRMATION_REQUIRED", "确认主爻位时必须提供位置和引用")
        if not primary_confirmed and (primary_position is not None or primary_refs):
            raise LiuYaoError("POSITION_CONFIRMATION_REQUIRED", "提供主爻位或引用时必须确认")

        object.__setattr__(self, "review_notes", _string_tuple(self.review_notes, "review_notes"))
        if self.source_profile_id != SELECTION_SOURCE_PROFILE_ID:
            raise LiuYaoError("UNSUPPORTED_RULE_PROFILE", "不支持的取用来源 profile")
        if self.topic_policy_id != SELECTION_TOPIC_POLICY_ID:
            raise LiuYaoError("UNSUPPORTED_RULE_PROFILE", "不支持的专项主题 policy")
        if self.engineering_policy_id != SELECTION_ENGINEERING_POLICY_ID:
            raise LiuYaoError("UNSUPPORTED_RULE_PROFILE", "不支持的取用工程 policy")

    def _validate_scoped_context(self) -> None:
        exam_scope = _non_empty(self.exam_scope, "exam_scope")
        if exam_scope not in _EXAM_SCOPES:
            raise LiuYaoError("INVALID_INPUT", f"不支持的 exam_scope：{exam_scope}")
        exam_confirmed = _bool(self.exam_scope_confirmed, "exam_scope_confirmed")
        exam_refs = _string_tuple(self.exam_scope_refs, "exam_scope_refs")
        object.__setattr__(self, "exam_scope", exam_scope)
        object.__setattr__(self, "exam_scope_refs", exam_refs)
        if exam_confirmed and (exam_scope in {"not_applicable", "unknown"} or not exam_refs):
            raise LiuYaoError("EXAM_SCOPE_REQUIRED", "确认考试范围时必须提供具体范围和引用")
        if not exam_confirmed and exam_refs:
            raise LiuYaoError("EXAM_SCOPE_CONFIRMATION_REQUIRED", "提供考试范围引用时必须确认")

        pairing = _non_empty(self.relationship_pairing_scope, "relationship_pairing_scope")
        if pairing not in _RELATIONSHIP_SCOPES:
            raise LiuYaoError("INVALID_INPUT", f"不支持的 relationship_pairing_scope：{pairing}")
        pairing_confirmed = _bool(self.relationship_pairing_confirmed, "relationship_pairing_confirmed")
        pairing_refs = _string_tuple(self.relationship_pairing_refs, "relationship_pairing_refs")
        object.__setattr__(self, "relationship_pairing_scope", pairing)
        object.__setattr__(self, "relationship_pairing_refs", pairing_refs)
        if pairing_confirmed and (pairing in {"not_applicable", "unknown"} or not pairing_refs):
            raise LiuYaoError("RELATION_CONTEXT_REQUIRED", "确认关系角色时必须提供具体范围和引用")
        if not pairing_confirmed and pairing_refs:
            raise LiuYaoError("RELATION_CONTEXT_CONFIRMATION_REQUIRED", "提供关系角色引用时必须确认")

        pregnancy_method = _non_empty(self.pregnancy_method, "pregnancy_method")
        if pregnancy_method not in _PREGNANCY_METHODS:
            raise LiuYaoError("INVALID_INPUT", f"不支持的 pregnancy_method：{pregnancy_method}")
        pregnancy_confirmed = _bool(self.pregnancy_method_confirmed, "pregnancy_method_confirmed")
        pregnancy_refs = _string_tuple(self.pregnancy_method_refs, "pregnancy_method_refs")
        object.__setattr__(self, "pregnancy_method", pregnancy_method)
        object.__setattr__(self, "pregnancy_method_refs", pregnancy_refs)
        if pregnancy_confirmed and (pregnancy_method in {"not_applicable", "unresolved"} or not pregnancy_refs):
            raise LiuYaoError("PREGNANCY_METHOD_REQUIRED", "确认求孕方法时必须提供具体方法和引用")
        if not pregnancy_confirmed and pregnancy_refs:
            raise LiuYaoError("PREGNANCY_METHOD_CONFIRMATION_REQUIRED", "提供求孕方法引用时必须确认")

        if self.topic != "exam" and (
            exam_scope != "not_applicable" or exam_confirmed or exam_refs
        ):
            raise LiuYaoError("INVALID_INPUT", "exam_scope 只允许考试主题使用")
        if self.topic != "relationship_reconciliation" and (
            pairing != "not_applicable" or pairing_confirmed or pairing_refs
        ):
            raise LiuYaoError("INVALID_INPUT", "relationship_pairing_scope 只允许感情主题使用")
        if self.topic != "pregnancy" and (
            pregnancy_method != "not_applicable" or pregnancy_confirmed or pregnancy_refs
        ):
            raise LiuYaoError("INVALID_INPUT", "pregnancy_method 只允许求孕主题使用")

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "topic": self.topic,
            "focus_dimension": self.focus_dimension,
            "case_record_sha256": self.case_record_sha256,
            "event_contract_sha256": self.event_contract_sha256,
            "contract_focus_confirmed": self.contract_focus_confirmed,
            "contract_source_refs": list(self.contract_source_refs),
            "advanced_context": self.advanced_context.to_dict(),
            "reality_status": self.reality_status,
            "reality_facts": list(self.reality_facts),
            "reality_evidence_confirmed": self.reality_evidence_confirmed,
            "reality_evidence_refs": list(self.reality_evidence_refs),
            "subject_mapping_confirmed": self.subject_mapping_confirmed,
            "subject_position": self.subject_position,
            "subject_mapping_refs": list(self.subject_mapping_refs),
            "exam_scope": self.exam_scope,
            "exam_scope_confirmed": self.exam_scope_confirmed,
            "exam_scope_refs": list(self.exam_scope_refs),
            "relationship_pairing_scope": self.relationship_pairing_scope,
            "relationship_pairing_confirmed": self.relationship_pairing_confirmed,
            "relationship_pairing_refs": list(self.relationship_pairing_refs),
            "pregnancy_method": self.pregnancy_method,
            "pregnancy_method_confirmed": self.pregnancy_method_confirmed,
            "pregnancy_method_refs": list(self.pregnancy_method_refs),
            "relation_choice": self.relation_choice,
            "relation_choice_confirmed": self.relation_choice_confirmed,
            "relation_choice_refs": list(self.relation_choice_refs),
            "relation_choice_reason": self.relation_choice_reason,
            "primary_position": self.primary_position,
            "primary_position_confirmed": self.primary_position_confirmed,
            "primary_position_refs": list(self.primary_position_refs),
            "review_notes": list(self.review_notes),
            "source_profile_id": self.source_profile_id,
            "topic_policy_id": self.topic_policy_id,
            "engineering_policy_id": self.engineering_policy_id,
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SelectionRequest":
        allowed = {
            "topic", "focus_dimension", "case_record_sha256", "event_contract_sha256",
            "contract_focus_confirmed",
            "contract_source_refs", "advanced_context", "reality_status", "reality_facts",
            "reality_evidence_confirmed", "reality_evidence_refs", "subject_mapping_confirmed",
            "subject_position", "subject_mapping_refs", "exam_scope", "exam_scope_confirmed",
            "exam_scope_refs", "relationship_pairing_scope", "relationship_pairing_confirmed",
            "relationship_pairing_refs", "pregnancy_method", "pregnancy_method_confirmed",
            "pregnancy_method_refs", "relation_choice", "relation_choice_confirmed",
            "relation_choice_refs", "relation_choice_reason", "primary_position",
            "primary_position_confirmed", "primary_position_refs", "review_notes",
            "source_profile_id", "topic_policy_id", "engineering_policy_id", "canonical_sha256",
        }
        _reject_unknown(value, allowed, "selection_request")
        missing = {"topic", "focus_dimension", "advanced_context"} - set(value)
        if missing:
            raise LiuYaoError("INVALID_INPUT", f"selection_request 缺少字段：{', '.join(sorted(missing))}")
        if "case_record_sha256" not in value:
            raise LiuYaoError("CASE_RECORD_HASH_REQUIRED", "selection_request 缺少 case_record_sha256")
        if "event_contract_sha256" not in value:
            raise LiuYaoError("CONTRACT_HASH_REQUIRED", "selection_request 缺少 event_contract_sha256")
        tuple_fields = {
            "contract_source_refs",
            "reality_facts",
            "reality_evidence_refs",
            "subject_mapping_refs",
            "exam_scope_refs",
            "relationship_pairing_refs",
            "pregnancy_method_refs",
            "relation_choice_refs",
            "primary_position_refs",
            "review_notes",
        }
        null_tuple_fields = sorted(
            field for field in tuple_fields if field in value and value[field] is None
        )
        if null_tuple_fields:
            raise LiuYaoError(
                "INVALID_INPUT",
                "selection_request 数组字段不能为 null："
                + ", ".join(null_tuple_fields),
            )
        request = cls(
            topic=value["topic"],
            focus_dimension=value["focus_dimension"],
            case_record_sha256=value["case_record_sha256"],
            event_contract_sha256=value["event_contract_sha256"],
            advanced_context=AdvancedContextRequest.from_mapping(
                _require_mapping(value["advanced_context"], "advanced_context")
            ),
            contract_focus_confirmed=value.get("contract_focus_confirmed", False),
            contract_source_refs=_string_tuple(value.get("contract_source_refs", ()), "contract_source_refs"),
            reality_status=value.get("reality_status", "unknown"),
            reality_facts=_string_tuple(value.get("reality_facts", ()), "reality_facts"),
            reality_evidence_confirmed=value.get("reality_evidence_confirmed", False),
            reality_evidence_refs=_string_tuple(value.get("reality_evidence_refs", ()), "reality_evidence_refs"),
            subject_mapping_confirmed=value.get("subject_mapping_confirmed", False),
            subject_position=value.get("subject_position"),
            subject_mapping_refs=_string_tuple(value.get("subject_mapping_refs", ()), "subject_mapping_refs"),
            exam_scope=value.get("exam_scope", "not_applicable"),
            exam_scope_confirmed=value.get("exam_scope_confirmed", False),
            exam_scope_refs=_string_tuple(value.get("exam_scope_refs", ()), "exam_scope_refs"),
            relationship_pairing_scope=value.get("relationship_pairing_scope", "not_applicable"),
            relationship_pairing_confirmed=value.get("relationship_pairing_confirmed", False),
            relationship_pairing_refs=_string_tuple(value.get("relationship_pairing_refs", ()), "relationship_pairing_refs"),
            pregnancy_method=value.get("pregnancy_method", "not_applicable"),
            pregnancy_method_confirmed=value.get("pregnancy_method_confirmed", False),
            pregnancy_method_refs=_string_tuple(value.get("pregnancy_method_refs", ()), "pregnancy_method_refs"),
            relation_choice=value.get("relation_choice"),
            relation_choice_confirmed=value.get("relation_choice_confirmed", False),
            relation_choice_refs=_string_tuple(value.get("relation_choice_refs", ()), "relation_choice_refs"),
            relation_choice_reason=value.get("relation_choice_reason"),
            primary_position=value.get("primary_position"),
            primary_position_confirmed=value.get("primary_position_confirmed", False),
            primary_position_refs=_string_tuple(value.get("primary_position_refs", ()), "primary_position_refs"),
            review_notes=_string_tuple(value.get("review_notes", ()), "review_notes"),
            source_profile_id=value.get("source_profile_id", SELECTION_SOURCE_PROFILE_ID),
            topic_policy_id=value.get("topic_policy_id", SELECTION_TOPIC_POLICY_ID),
            engineering_policy_id=value.get("engineering_policy_id", SELECTION_ENGINEERING_POLICY_ID),
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != request.canonical_sha256:
            raise LiuYaoError("RECORD_TAMPERED", "selection_request canonical_sha256 与重算结果不一致")
        return request


@dataclass(frozen=True, slots=True)
class GateReceipt:
    gate_id: str
    order: int
    status: str
    reason_code: str
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "order": self.order,
            "status": self.status,
            "reason_code": self.reason_code,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class SubjectMappingReceipt:
    casting_mode: str
    status: str
    subject_position: int | None
    basis: str
    source_rule_ids: tuple[str, ...]
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "casting_mode": self.casting_mode,
            "status": self.status,
            "subject_position": self.subject_position,
            "basis": self.basis,
            "source_rule_ids": list(self.source_rule_ids),
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class RelationRole:
    role_id: str
    relation: str
    contribution_allowed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "role_id": self.role_id,
            "relation": self.relation,
            "contribution_allowed": self.contribution_allowed,
        }


@dataclass(frozen=True, slots=True)
class RelationDecision:
    status: str
    active_roles: tuple[RelationRole, ...]
    source_relation_candidates: tuple[str, ...]
    method_options: tuple[str, ...]
    selected_method: str | None
    source_rule_ids: tuple[str, ...]
    conflict_codes: tuple[str, ...]
    manual_unvalidated: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "active_roles": [item.to_dict() for item in self.active_roles],
            "source_relation_candidates": list(self.source_relation_candidates),
            "method_options": list(self.method_options),
            "selected_method": self.selected_method,
            "source_rule_ids": list(self.source_rule_ids),
            "conflict_codes": list(self.conflict_codes),
            "manual_unvalidated": self.manual_unvalidated,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class CandidatePathReceipt:
    path_id: str
    validity_status: str
    enumeration_status: str
    direction: str
    candidate_graph_reaches_focus: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "path_id": self.path_id,
            "validity_status": self.validity_status,
            "enumeration_status": self.enumeration_status,
            "direction": self.direction,
            "candidate_graph_reaches_focus": self.candidate_graph_reaches_focus,
        }


@dataclass(frozen=True, slots=True)
class ValidityMatrixReceipt:
    receipt_id: str
    role_id: str
    relation: str
    evaluation_mode: str
    request: ValidityRequest
    validity_request_sha256: str
    validity_matrix_sha256: str
    validity_trace_sha256: str
    focus_selection_status: str
    selected_position: int | None
    focus_status: str
    focus_dependencies: tuple[str, ...]
    conflict_codes: tuple[str, ...]
    candidate_node_ids: tuple[str, ...]
    path_evaluation_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "role_id": self.role_id,
            "relation": self.relation,
            "evaluation_mode": self.evaluation_mode,
            "request": self.request.to_dict(),
            "validity_request_sha256": self.validity_request_sha256,
            "validity_matrix_sha256": self.validity_matrix_sha256,
            "validity_trace_sha256": self.validity_trace_sha256,
            "focus_selection_status": self.focus_selection_status,
            "selected_position": self.selected_position,
            "focus_status": self.focus_status,
            "focus_dependencies": list(self.focus_dependencies),
            "conflict_codes": list(self.conflict_codes),
            "candidate_node_ids": list(self.candidate_node_ids),
            "path_evaluation_status": self.path_evaluation_status,
        }


@dataclass(frozen=True, slots=True)
class SelectionCandidate:
    candidate_id: str
    matrix_receipt_id: str
    role_id: str
    source_kind: str
    relation: str
    position: int
    node_id: str
    moving: bool
    is_shi: bool
    is_ying: bool
    structural_eligibility: str
    current_force: str
    manifestation_state: str
    role_polarity: str
    node_state: str
    open_obligations: tuple[str, ...]
    relief_candidates: tuple[str, ...]
    focus_status: str
    path_evaluation_status: str
    path_receipts: tuple[CandidatePathReceipt, ...]
    conflict_codes: tuple[str, ...]
    visibility_state: str | None
    activation_state: str | None
    flying_node_id: str | None
    release_candidates: tuple[str, ...]
    source_preference_hits: tuple[str, ...]
    contributes: bool
    decision_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "matrix_receipt_id": self.matrix_receipt_id,
            "role_id": self.role_id,
            "source_kind": self.source_kind,
            "relation": self.relation,
            "position": self.position,
            "node_id": self.node_id,
            "moving": self.moving,
            "is_shi": self.is_shi,
            "is_ying": self.is_ying,
            "structural_eligibility": self.structural_eligibility,
            "current_force": self.current_force,
            "manifestation_state": self.manifestation_state,
            "role_polarity": self.role_polarity,
            "node_state": self.node_state,
            "open_obligations": list(self.open_obligations),
            "relief_candidates": list(self.relief_candidates),
            "focus_status": self.focus_status,
            "path_evaluation_status": self.path_evaluation_status,
            "path_receipts": [item.to_dict() for item in self.path_receipts],
            "conflict_codes": list(self.conflict_codes),
            "visibility_state": self.visibility_state,
            "activation_state": self.activation_state,
            "flying_node_id": self.flying_node_id,
            "release_candidates": list(self.release_candidates),
            "source_preference_hits": list(self.source_preference_hits),
            "source_preferences_applied_to_ranking": False,
            "contributes": self.contributes,
            "decision_codes": list(self.decision_codes),
        }


@dataclass(frozen=True, slots=True)
class SelectionRuntimeReport:
    case_id: str
    case_record_sha256: str
    cast_sha256: str
    chart_sha256: str
    event_contract_sha256: str
    request: SelectionRequest
    advanced_runtime_sha256: str | None
    selection_status: str
    subject_mapping: SubjectMappingReceipt
    relation_decision: RelationDecision
    gate_receipts: tuple[GateReceipt, ...]
    matrix_receipts: tuple[ValidityMatrixReceipt, ...]
    candidates: tuple[SelectionCandidate, ...]
    provisional_candidate_id: str | None
    dependencies: tuple[str, ...]
    trace_sha256: str
    headline: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        source_profile = selection_source_profile_payload()
        source_profile["profile_sha256"] = SELECTION_SOURCE_PROFILE_SHA256
        topic_policy = selection_topic_policy_payload()
        topic_policy["policy_sha256"] = SELECTION_TOPIC_POLICY_SHA256
        engineering_policy = selection_engineering_policy_payload()
        engineering_policy["policy_sha256"] = SELECTION_ENGINEERING_POLICY_SHA256
        matrix_payload = [item.to_dict() for item in self.matrix_receipts]
        candidate_payload = [item.to_dict() for item in self.candidates]
        payload: dict[str, object] = {
            "method_id": SELECTION_RUNTIME_METHOD_ID,
            "selection_runtime_status": SELECTION_RUNTIME_STATUS,
            "production_allowed": SELECTION_RUNTIME_PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "source_profile": source_profile,
            "topic_policy": topic_policy,
            "engineering_policy": engineering_policy,
            "selection_priority_table_sha256": SELECTION_PRIORITY_TABLE_SHA256,
            "gate_priority_receipt": list(SELECTION_GATE_PRIORITY),
            "upstream_validity_hashes": {
                "rule_profile_sha256": VALIDITY_RULE_PROFILE_SHA256,
                "engineering_policy_sha256": VALIDITY_ENGINEERING_POLICY_SHA256,
                "priority_table_sha256": VALIDITY_PRIORITY_TABLE_SHA256,
            },
            "case_id": self.case_id,
            "case_record_sha256": self.case_record_sha256,
            "cast_sha256": self.cast_sha256,
            "chart_sha256": self.chart_sha256,
            "event_contract_sha256": self.event_contract_sha256,
            "request": self.request.to_dict(),
            "selection_request_sha256": self.request.canonical_sha256,
            "advanced_runtime_sha256": self.advanced_runtime_sha256,
            "topic_pack_dimensions": [
                item.to_dict()
                for item in SELECTION_TOPIC_DIMENSIONS
                if item.topic == self.request.topic
            ],
            "selection_status": self.selection_status,
            "subject_mapping": self.subject_mapping.to_dict(),
            "relation_decision": self.relation_decision.to_dict(),
            "gate_receipts": [item.to_dict() for item in self.gate_receipts],
            "matrix_receipts": matrix_payload,
            "matrix_receipts_sha256": digest(matrix_payload),
            "candidates": candidate_payload,
            "candidate_inventory_sha256": digest(candidate_payload),
            "provisional_candidate_id": self.provisional_candidate_id,
            "dependencies": list(self.dependencies),
            "trace_sha256": self.trace_sha256,
            "headline": self.headline,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def _gate(gate_id: str, status: str, reason_code: str, detail: str) -> GateReceipt:
    return GateReceipt(gate_id, _GATE_ORDERS[gate_id], status, reason_code, detail)


def _complete_gates(receipts: list[GateReceipt]) -> tuple[GateReceipt, ...]:
    present = {item.gate_id for item in receipts}
    for gate_id in SELECTION_GATE_PRIORITY:
        if gate_id not in present:
            receipts.append(_gate(gate_id, "not_reached", "EARLIER_GATE_STOPPED", "此前门禁已停止运行。"))
    return tuple(sorted(receipts, key=lambda item: -item.order))


def _empty_subject(record: LiuYaoCaseRecord) -> SubjectMappingReceipt:
    return SubjectMappingReceipt(
        record.cast.casting_mode,
        "not_evaluated",
        None,
        "not_evaluated",
        (),
        (),
    )


def _source_rule_refs(rule_id: str) -> tuple[str, ...]:
    rule = next(item for item in SELECTION_SOURCE_RULES if item.rule_id == rule_id)
    return tuple(item.source_ref for item in rule.evidence)


def _empty_relation(status: str = "not_evaluated", detail: str = "尚未进入来源关系门禁。") -> RelationDecision:
    return RelationDecision(status, (), (), (), None, (), (), False, detail)


def _make_report(
    record: LiuYaoCaseRecord,
    request: SelectionRequest,
    *,
    advanced_runtime_sha256: str | None,
    selection_status: str,
    subject_mapping: SubjectMappingReceipt,
    relation_decision: RelationDecision,
    gate_receipts: list[GateReceipt],
    matrix_receipts: tuple[ValidityMatrixReceipt, ...] = (),
    candidates: tuple[SelectionCandidate, ...] = (),
    provisional_candidate_id: str | None = None,
    dependencies: tuple[str, ...] = (),
    headline: str,
) -> SelectionRuntimeReport:
    completed_gates = _complete_gates(gate_receipts)
    trace_payload = {
        "gates": [item.to_dict() for item in completed_gates],
        "subject_mapping": subject_mapping.to_dict(),
        "relation_decision": relation_decision.to_dict(),
        "matrix_receipts": [item.to_dict() for item in matrix_receipts],
        "candidates": [item.to_dict() for item in candidates],
        "provisional_candidate_id": provisional_candidate_id,
        "dependencies": list(dependencies),
    }
    warnings = (
        "两本活动资料属于同一作者文本谱系，活动来源族数量为 1。",
        "所有来源规则均为 source_only、human_reviewed=false；工程摘要不是签名，也不证明来源或预测有效。",
        "source preference 只作命中收据，永不参与候选决胜。",
        "provisional candidate 只供人工复核，不表示最终用神或事件结果。",
    )
    limits = (
        "本切片不推断应期、概率、成败、吉凶或确定日期。",
        "多可见候选不伪造 primary_position，因此在人工确认前不展开候选专属路径。",
        "伏神只进入审计清单，不能成为自动贡献候选。",
        "现代考公、来源范围外关系和胎爻法均没有被静默补成传统规则。",
        "现实、历法、主体、关系与方法引用只由调用方声明；当前运行时不核验引用内容真实性。",
    )
    return SelectionRuntimeReport(
        case_id=record.cast.case_id,
        case_record_sha256=record.canonical_sha256,
        cast_sha256=record.cast.canonical_sha256,
        chart_sha256=record.chart.canonical_sha256,
        event_contract_sha256=digest(record.cast.event_contract.to_dict()),
        request=request,
        advanced_runtime_sha256=advanced_runtime_sha256,
        selection_status=selection_status,
        subject_mapping=subject_mapping,
        relation_decision=relation_decision,
        gate_receipts=completed_gates,
        matrix_receipts=matrix_receipts,
        candidates=candidates,
        provisional_candidate_id=provisional_candidate_id,
        dependencies=tuple(dict.fromkeys(dependencies)),
        trace_sha256=digest(trace_payload),
        headline=headline,
        warnings=warnings,
        limits=limits,
    )


def _source_relation_decision(
    request: SelectionRequest,
    *,
    casting_mode: str,
) -> RelationDecision:
    if request.topic == "exam":
        if not request.exam_scope_confirmed or request.exam_scope == "unknown":
            return _empty_relation("exam_scope_required", "考试范围未确认，来源不能映射六亲。")
        if request.exam_scope == "modern_civil_service_unspecified":
            return RelationDecision(
                "modern_exam_scope_unresolved", (), ("官鬼", "父母"), (), None,
                ("EXAM-DUAL-RELATION",), ("MODERN_EXAM_SCOPE_UNRESOLVED",), False,
                "资料没有把现代考公直接等同于文试或武试。",
            )
        source_relations = ("官鬼", "父母") if request.exam_scope == "written_or_cultural" else ("官鬼",)
        if request.relation_choice is not None and not request.relation_choice_confirmed:
            return RelationDecision(
                "relation_confirmation_required", (), source_relations, (), None,
                ("EXAM-DUAL-RELATION",), ("RELATION_CHOICE_UNCONFIRMED",), False,
                "已提供六亲选择但尚未确认。",
            )
        if request.relation_choice_confirmed:
            assert request.relation_choice is not None
            if request.relation_choice not in source_relations:
                raise LiuYaoError("USE_RELATION_OUTSIDE_SOURCE_PROFILE", "考试六亲选择不在已登记来源候选中")
            role = "exam_officer" if request.relation_choice == "官鬼" else "exam_document"
            return RelationDecision(
                "caller_narrowed_source_relations",
                (RelationRole(role, request.relation_choice, True),),
                source_relations, (), None, ("EXAM-DUAL-RELATION",), (), False,
                "调用方按事件合同从来源候选关系中显式收窄；仍不是最终用神。",
            )
        if len(source_relations) == 2:
            return RelationDecision(
                "source_dual_relation",
                (
                    RelationRole("exam_officer", "官鬼", False),
                    RelationRole("exam_document", "父母", False),
                ),
                source_relations, (), None, ("EXAM-DUAL-RELATION",),
                ("RELATION_CONFIRMATION_REQUIRED",), False,
                "文试来源为官父两用；两组候选均保留但不自动压成一个。",
            )
        return RelationDecision(
            "source_single_relation", (RelationRole("exam_officer", "官鬼", True),),
            source_relations, (), None, ("EXAM-DUAL-RELATION",), (), False,
            "经确认的武试范围只登记官鬼候选。",
        )

    if request.topic == "relationship_reconciliation":
        if not request.relationship_pairing_confirmed or request.relationship_pairing_scope == "unknown":
            return _empty_relation("relation_context_required", "被测主体与关系对象的来源角色范围未确认。")
        mapping = {
            "male_subject_female_spouse": "妻财",
            "female_subject_male_spouse": "官鬼",
        }
        mapped = mapping.get(request.relationship_pairing_scope)
        # The registered relationship rule describes a person asking about
        # their own traditional spouse role.  Confirming a proxy subject line
        # does not extend that source scope to a third-person relationship.
        if casting_mode == "proxy":
            mapped = None
        if mapped is not None:
            if request.relation_choice is not None and not request.relation_choice_confirmed:
                return RelationDecision(
                    "relation_confirmation_required", (), (mapped,), (), None,
                    ("RELATIONSHIP-TRADITIONAL-PAIRING",), ("RELATION_CHOICE_UNCONFIRMED",), False,
                    "已提供六亲选择但尚未确认。",
                )
            if request.relation_choice is not None and request.relation_choice != mapped:
                raise LiuYaoError("RELATION_CHOICE_MISMATCH", "人工六亲选择与已确认传统关系角色不一致")
            return RelationDecision(
                "source_scope_mapped",
                (RelationRole("relationship_counterparty", mapped, True),),
                (mapped,), (), None, ("RELATIONSHIP-TRADITIONAL-PAIRING",), (), False,
                "只在经确认的传统异性婚姻角色范围内映射。",
            )
        if not request.relation_choice_confirmed:
            return RelationDecision(
                "manual_relation_required", (), (), (), None,
                ("RELATIONSHIP-TRADITIONAL-PAIRING",), ("RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED",), True,
                "该关系在来源范围外；需要显式人工映射，但不能形成自动贡献。",
            )
        if not request.relation_choice_reason:
            raise LiuYaoError("RELATION_REASON_REQUIRED", "来源范围外人工映射必须提供理由")
        assert request.relation_choice is not None
        return RelationDecision(
            "manual_unvalidated_mapping",
            (RelationRole("relationship_manual", request.relation_choice, False),),
            (), (), None, ("RELATIONSHIP-TRADITIONAL-PAIRING",),
            ("RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED",), True,
            "候选仅供审计；来源没有验证该关系范围的六亲映射。",
        )

    if not request.pregnancy_method_confirmed or request.pregnancy_method == "unresolved":
        return RelationDecision(
            "source_method_conflict", (), ("子孙",), ("children_relation", "fetal_marker"), None,
            ("PREGNANCY-METHOD-CONFLICT",), ("PREGNANCY_SOURCE_METHOD_CONFLICT",), False,
            "子孙法与胎爻法并存；作者偏好不解除方法冲突。",
        )
    if request.pregnancy_method == "fetal_marker":
        return RelationDecision(
            "unsupported_method", (), ("子孙",), ("children_relation", "fetal_marker"), "fetal_marker",
            ("PREGNANCY-METHOD-CONFLICT",), ("FETAL_MARKER_NOT_IMPLEMENTED",), False,
            "当前结构模型没有胎爻 selector，不能静默退回子孙法。",
        )
    return RelationDecision(
        "caller_selected_source_method",
        (RelationRole("pregnancy_children", "子孙", True),),
        ("子孙",), ("children_relation", "fetal_marker"), "children_relation",
        ("PREGNANCY-METHOD-CONFLICT",), ("FETAL_MARKER_NOT_IMPLEMENTED",), False,
        "调用方显式选择子孙法；仍保留另一来源方法未实现的收据。",
    )


def _matrix_receipt(
    role: RelationRole,
    request: ValidityRequest,
    matrix: ValidityMatrixReport,
) -> ValidityMatrixReceipt:
    selection_status = matrix.focus_selection.status
    if selection_status == "confirmed":
        evaluation_mode = "caller_confirmed_position"
        path_status = "evaluated"
    elif selection_status == "unique_candidate":
        evaluation_mode = "automatic_unique_candidate"
        path_status = "evaluated"
    elif selection_status == "ambiguous":
        evaluation_mode = "ambiguous_inventory"
        path_status = "not_run_use_line_unconfirmed"
    else:
        evaluation_mode = "hidden_or_empty_inventory"
        path_status = "not_run_no_visible_candidate"
    candidate_ids = tuple(
        [f"original:{position}" for position in matrix.focus_selection.candidate_positions]
        + [item.hidden_node.node_id for item in matrix.hidden_candidates if item.relation == role.relation]
    )
    return ValidityMatrixReceipt(
        receipt_id=f"matrix:{role.role_id}",
        role_id=role.role_id,
        relation=role.relation,
        evaluation_mode=evaluation_mode,
        request=request,
        validity_request_sha256=request.canonical_sha256,
        validity_matrix_sha256=matrix.canonical_sha256,
        validity_trace_sha256=matrix.trace_sha256,
        focus_selection_status=selection_status,
        selected_position=matrix.focus_selection.selected_position,
        focus_status=matrix.focus_status,
        focus_dependencies=matrix.focus_dependencies,
        conflict_codes=tuple(item.code for item in matrix.conflicts),
        candidate_node_ids=candidate_ids,
        path_evaluation_status=path_status,
    )


def _matrix_trace_sha256(matrix: ValidityMatrixReport) -> str:
    hits = [hit for node in matrix.nodes for hit in node.rule_hits]
    hits.extend(
        hit
        for hidden in matrix.hidden_candidates
        for hit in hidden.hidden_node.rule_hits
    )
    hits.extend(hit for hidden in matrix.hidden_candidates for hit in hidden.rule_hits)
    hits.extend(hit for edge in matrix.edges for hit in edge.rule_hits)
    return digest([item.to_dict() for item in sorted(hits, key=lambda item: item.trace_id)])


def _available_focus_is_consistent(
    matrix: ValidityMatrixReport,
    selected_node: NodeValidity | None,
) -> bool:
    if (
        selected_node is None
        or selected_node.state != "available_candidate"
        or selected_node.open_obligations
        or matrix.focus_dependencies
    ):
        return False
    if any(
        conflict.code in {"OPPOSING_DIRECT_PATHS", "PATH_ENUMERATION_LIMIT"}
        for conflict in matrix.conflicts
    ):
        return False
    if any(
        path.target_node_id == selected_node.node_id
        and path.enumeration_status == "retained"
        and path.validity_status == "deferred"
        for path in matrix.paths
    ):
        return False
    opposing_directions = {
        path.direction
        for path in matrix.paths
        if path.target_node_id == selected_node.node_id
        and path.enumeration_status == "retained"
        and path.validity_status == "active_candidate"
        and path.candidate_graph_reaches_focus
        and len(path.edge_ids) == 1
        and path.direction in {"supportive", "restrictive"}
    }
    return opposing_directions != {"supportive", "restrictive"}


def _validate_matrix_binding(
    record: LiuYaoCaseRecord,
    request: ValidityRequest,
    role: RelationRole,
    advanced_runtime_sha256: str,
    matrix: ValidityMatrixReport,
) -> dict[str, NodeValidity]:
    if not isinstance(matrix, ValidityMatrixReport):
        raise LiuYaoError("VALIDITY_MATRIX_BINDING_MISMATCH", "上游有效性矩阵类型不匹配")
    if (
        matrix.case_id != record.cast.case_id
        or matrix.case_record_sha256 != record.canonical_sha256
        or matrix.chart_sha256 != record.chart.canonical_sha256
    ):
        raise LiuYaoError("VALIDITY_MATRIX_BINDING_MISMATCH", "上游有效性矩阵与当前案例不一致")
    if matrix.request != request or matrix.request.canonical_sha256 != request.canonical_sha256:
        raise LiuYaoError("VALIDITY_MATRIX_BINDING_MISMATCH", "上游有效性矩阵请求与本轮请求不一致")
    if matrix.advanced_runtime_sha256 != advanced_runtime_sha256:
        raise LiuYaoError("VALIDITY_MATRIX_BINDING_MISMATCH", "上游有效性矩阵历法运行时摘要不一致")
    if matrix.trace_sha256 != _matrix_trace_sha256(matrix):
        raise LiuYaoError("VALIDITY_MATRIX_BINDING_MISMATCH", "上游有效性矩阵规则轨迹摘要不一致")
    if matrix.focus_selection.relation != role.relation:
        raise LiuYaoError("VALIDITY_MATRIX_BINDING_MISMATCH", "上游有效性矩阵焦点六亲与候选角色不一致")

    expected_positions = tuple(
        line.position
        for line in record.chart.lines
        if line.six_relation == role.relation
    )
    if matrix.focus_selection.candidate_positions != expected_positions:
        raise LiuYaoError(
            "VALIDITY_MATRIX_BINDING_MISMATCH",
            "上游有效性矩阵的可见候选全集与当前命盘不一致",
        )
    confirmed_position = request.interpretation.primary_position
    if confirmed_position is not None:
        expected_focus = ("confirmed", confirmed_position)
    elif len(expected_positions) == 1:
        expected_focus = ("unique_candidate", expected_positions[0])
    elif not expected_positions:
        expected_focus = ("not_found", None)
    else:
        expected_focus = ("ambiguous", None)
    actual_focus = (
        matrix.focus_selection.status,
        matrix.focus_selection.selected_position,
    )
    if actual_focus != expected_focus:
        raise LiuYaoError(
            "VALIDITY_MATRIX_BINDING_MISMATCH",
            "上游有效性矩阵的焦点选择语义与当前请求不一致",
        )

    node_by_id = {item.node_id: item for item in matrix.nodes}
    if len(node_by_id) != len(matrix.nodes):
        raise LiuYaoError("VALIDITY_MATRIX_BINDING_MISMATCH", "上游有效性矩阵包含重复节点 ID")
    expected_node_ids = {
        *(f"original:{line.position}" for line in record.chart.lines),
        *(
            f"changed:{line.position}"
            for line in record.chart.lines
            if line.moving
        ),
    }
    if set(node_by_id) != expected_node_ids:
        raise LiuYaoError(
            "VALIDITY_MATRIX_BINDING_MISMATCH",
            "上游有效性矩阵的节点全集与当前命盘不一致",
        )
    selected_position = matrix.focus_selection.selected_position
    for line in record.chart.lines:
        original = node_by_id[f"original:{line.position}"]
        expected_selected = line.position == selected_position
        if (
            original.node_kind != "original"
            or original.position != line.position
            or original.branch != line.najia_branch
            or original.element != line.element
            or original.motion_kind != ("moving" if line.moving else "static")
            or original.selected_use is not expected_selected
            or original.role_polarity
            != ("selected_use" if expected_selected else "unassigned")
        ):
            raise LiuYaoError(
                "VALIDITY_MATRIX_BINDING_MISMATCH",
                "上游原爻节点身份或选中状态与当前命盘不一致",
            )
        if line.moving:
            changed = node_by_id[f"changed:{line.position}"]
            if (
                changed.node_kind != "changed"
                or changed.position != line.position
                or changed.branch != line.changed_najia_branch
                or changed.element != line.changed_element
                or changed.motion_kind != "changed"
                or changed.selected_use
                or changed.role_polarity != "unassigned"
            ):
                raise LiuYaoError(
                    "VALIDITY_MATRIX_BINDING_MISMATCH",
                    "上游变爻节点身份或选中状态与当前命盘不一致",
                )
    if selected_position is None and matrix.focus_status != "needs_confirmation":
        raise LiuYaoError(
            "VALIDITY_MATRIX_BINDING_MISMATCH",
            "未选中焦点时上游矩阵不得声明候选可用",
        )
    if matrix.focus_status == "available_candidate":
        selected_node = (
            None
            if selected_position is None
            else node_by_id[f"original:{selected_position}"]
        )
        if not _available_focus_is_consistent(matrix, selected_node):
            raise LiuYaoError(
                "VALIDITY_MATRIX_BINDING_MISMATCH",
                "上游矩阵的可用焦点与节点、路径、冲突或开放依赖不一致",
            )
    for hidden in matrix.hidden_candidates:
        if hidden.relation != role.relation:
            continue
        node = hidden.hidden_node
        if (
            isinstance(node.position, bool)
            or not isinstance(node.position, int)
            or not 1 <= node.position <= 6
            or node.node_kind != "hidden"
            or node.node_id != f"hidden:{role.relation}:{node.position}"
            or hidden.flying_node_id != f"original:{node.position}"
        ):
            raise LiuYaoError("VALIDITY_MATRIX_BINDING_MISMATCH", "上游伏神候选节点绑定不一致")
    return node_by_id


def _candidate_conflicts(matrix: ValidityMatrixReport, node_id: str) -> tuple[str, ...]:
    selected_node_id = (
        f"original:{matrix.focus_selection.selected_position}"
        if matrix.focus_selection.selected_position is not None
        else None
    )
    return tuple(
        dict.fromkeys(
            conflict.code
            for conflict in matrix.conflicts
            if node_id in conflict.subjects
            or (
                conflict.code in {"OPPOSING_DIRECT_PATHS", "PATH_ENUMERATION_LIMIT"}
                and node_id == selected_node_id
            )
        )
    )


def _visible_candidate(
    record: LiuYaoCaseRecord,
    role: RelationRole,
    receipt: ValidityMatrixReceipt,
    matrix: ValidityMatrixReport,
    node: NodeValidity,
) -> SelectionCandidate:
    line = record.chart.lines[node.position - 1]
    selected = matrix.focus_selection.selected_position == node.position
    contributes = (
        role.contribution_allowed
        and selected
        and node.selected_use
        and matrix.focus_selection.status in {"unique_candidate", "confirmed"}
        and matrix.focus_status == "available_candidate"
        and _available_focus_is_consistent(matrix, node)
    )
    if contributes:
        decision_codes = ("PROVISIONAL_REVIEW_CANDIDATE_ONLY",)
    elif matrix.focus_selection.status == "ambiguous":
        decision_codes = ("USE_LINE_CONFIRMATION_REQUIRED", "PATHS_NOT_EVALUATED")
    elif not role.contribution_allowed:
        decision_codes = ("RELATION_RESOLUTION_OPEN",)
    elif selected:
        decision_codes = (f"FOCUS_{matrix.focus_status.upper()}",)
    else:
        decision_codes = ("NOT_SELECTED_BY_FOCUS_RECEIPT",)
    paths = tuple(
        CandidatePathReceipt(
            item.path_id,
            item.validity_status,
            item.enumeration_status,
            item.direction,
            item.candidate_graph_reaches_focus,
        )
        for item in matrix.paths
        if item.target_node_id == node.node_id
    )
    return SelectionCandidate(
        candidate_id=f"{role.role_id}:visible:{node.position}",
        matrix_receipt_id=receipt.receipt_id,
        role_id=role.role_id,
        source_kind="visible_original",
        relation=role.relation,
        position=node.position,
        node_id=node.node_id,
        moving=line.moving,
        is_shi=node.position == record.chart.original.shi_line,
        is_ying=node.position == record.chart.original.ying_line,
        structural_eligibility=node.structural_eligibility,
        current_force=node.current_force,
        manifestation_state=node.manifestation_state,
        role_polarity=node.role_polarity,
        node_state=node.state,
        open_obligations=node.open_obligations,
        relief_candidates=node.relief_candidates,
        focus_status=matrix.focus_status,
        path_evaluation_status=receipt.path_evaluation_status,
        path_receipts=paths,
        conflict_codes=_candidate_conflicts(matrix, node.node_id),
        visibility_state=None,
        activation_state=None,
        flying_node_id=None,
        release_candidates=(),
        source_preference_hits=(),
        contributes=contributes,
        decision_codes=decision_codes,
    )


def _hidden_candidate(
    record: LiuYaoCaseRecord,
    role: RelationRole,
    receipt: ValidityMatrixReceipt,
    matrix: ValidityMatrixReport,
    hidden: HiddenValidity,
) -> SelectionCandidate:
    node = hidden.hidden_node
    return SelectionCandidate(
        candidate_id=f"{role.role_id}:hidden:{node.position}",
        matrix_receipt_id=receipt.receipt_id,
        role_id=role.role_id,
        source_kind="hidden",
        relation=role.relation,
        position=node.position,
        node_id=node.node_id,
        moving=False,
        is_shi=node.position == record.chart.original.shi_line,
        is_ying=node.position == record.chart.original.ying_line,
        structural_eligibility=node.structural_eligibility,
        current_force=node.current_force,
        manifestation_state=node.manifestation_state,
        role_polarity=node.role_polarity,
        node_state=node.state,
        open_obligations=tuple(dict.fromkeys(node.open_obligations + hidden.open_obligations)),
        relief_candidates=node.relief_candidates,
        focus_status=matrix.focus_status,
        path_evaluation_status="not_run_hidden_never_primary",
        path_receipts=(),
        conflict_codes=_candidate_conflicts(matrix, node.node_id),
        visibility_state=hidden.visibility_state,
        activation_state=hidden.activation_state,
        flying_node_id=hidden.flying_node_id,
        release_candidates=hidden.release_candidates,
        source_preference_hits=(),
        contributes=False,
        decision_codes=("HIDDEN_NEVER_AUTO_CONTRIBUTES",),
    )


def _add_source_preferences(
    record: LiuYaoCaseRecord,
    candidates: list[SelectionCandidate],
) -> list[SelectionCandidate]:
    result = list(candidates)
    for role_id in dict.fromkeys(item.role_id for item in result):
        indexes = [
            index
            for index, item in enumerate(result)
            if item.role_id == role_id and item.source_kind == "visible_original"
        ]
        if len(indexes) < 2:
            continue
        comparable_by_motion = {
            moving: tuple(index for index in indexes if result[index].moving is moving)
            for moving in (False, True)
        }
        nearer_shi_indexes: set[int] = set()
        for comparable_indexes in comparable_by_motion.values():
            if len(comparable_indexes) < 2:
                continue
            min_distance = min(
                abs(result[index].position - record.chart.original.shi_line)
                for index in comparable_indexes
            )
            nearer_shi_indexes.update(
                index
                for index in comparable_indexes
                if abs(result[index].position - record.chart.original.shi_line)
                == min_distance
            )
        for index in indexes:
            item = result[index]
            hits: list[str] = []
            if item.moving:
                hits.append("prefer_moving_over_static")
            if "VOID_EFFECT_OPEN" not in item.open_obligations:
                hits.append("prefer_not_void")
            if "MONTH_BREAK_OPEN" not in item.open_obligations:
                hits.append("prefer_not_month_broken")
            if index in nearer_shi_indexes:
                hits.append("prefer_nearer_shi")
            result[index] = replace(item, source_preference_hits=tuple(hits))
    return result


def build_selection_runtime_report(
    record: LiuYaoCaseRecord,
    request: SelectionRequest,
) -> SelectionRuntimeReport:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    if not isinstance(request, SelectionRequest):
        raise LiuYaoError("INVALID_INPUT", "request 必须是 SelectionRequest")
    if request.case_record_sha256 != record.canonical_sha256:
        raise LiuYaoError("CASE_RECORD_BINDING_MISMATCH", "案例摘要与 selection request 不一致")
    expected_contract_hash = digest(record.cast.event_contract.to_dict())
    if request.event_contract_sha256 != expected_contract_hash:
        raise LiuYaoError("CONTRACT_BINDING_MISMATCH", "事件合同摘要与冻结案例不一致")
    if record.chart.input_sha256 != record.cast.canonical_sha256:
        raise LiuYaoError("RECORD_TAMPERED", "chart.input_sha256 与冻结 cast 不一致")
    if record.cast.casting_mode == "self" and request.subject_mapping_confirmed:
        raise LiuYaoError("SUBJECT_MAPPING_NOT_APPLICABLE", "本人摇卦不接受调用方覆盖主体位置")

    gates = [
        _gate(
            "contract_integrity_gate",
            "passed",
            "INPUT_HASHES_BOUND",
            "案例与事件合同摘要均和 selection request 一致。",
        )
    ]
    subject = _empty_subject(record)
    relation = _empty_relation()

    cast_facts = set(record.cast.reality_facts)
    if cast_facts and (
        request.reality_status == "unknown" or not cast_facts.issubset(set(request.reality_facts))
    ):
        raise LiuYaoError("REALITY_CONTEXT_MISMATCH", "selection request 不能忽略冻结 cast 中的 reality_facts")
    if request.reality_status == "blocking":
        gates.append(_gate("reality_gate", "blocked", "REALITY_HARD_BLOCK_CONFIRMED", "已确认现实阻断并绑定证据。"))
        return _make_report(
            record, request, advanced_runtime_sha256=None, selection_status="reality_blocked",
            subject_mapping=subject, relation_decision=relation, gate_receipts=gates,
            dependencies=("REALITY_HARD_BLOCK_CONFIRMED",), headline="现实阻断优先，未生成结构候选。",
        )
    gates.append(_gate("reality_gate", "passed", "NO_REALITY_HARD_BLOCK", "未收到经确认的现实硬阻断。"))

    dimension = find_topic_dimension(request.topic, request.focus_dimension)
    assert dimension is not None
    if dimension.scope in {"outside_single_cast", "professional_only", "reality_required"}:
        status = {
            "outside_single_cast": "focus_outside_single_cast",
            "professional_only": "professional_only",
            "reality_required": "reality_context_required",
        }[dimension.scope]
        code = {
            "outside_single_cast": "FOCUS_OUTSIDE_SINGLE_CAST",
            "professional_only": "PROFESSIONAL_ONLY",
            "reality_required": "REALITY_CONTEXT_REQUIRED",
        }[dimension.scope]
        gates.append(_gate("topic_safety_gate", "blocked", code, dimension.plain))
        return _make_report(
            record, request, advanced_runtime_sha256=None, selection_status=status,
            subject_mapping=subject, relation_decision=relation, gate_receipts=gates,
            dependencies=(code,), headline=dimension.plain,
        )
    if dimension.scope == "structural_with_reality_gate" and request.reality_status == "unknown":
        gates.append(_gate("topic_safety_gate", "blocked", "REALITY_CONTEXT_REQUIRED", dimension.plain))
        return _make_report(
            record, request, advanced_runtime_sha256=None, selection_status="reality_context_required",
            subject_mapping=subject, relation_decision=relation, gate_receipts=gates,
            dependencies=("REALITY_CONTEXT_REQUIRED",), headline=dimension.plain,
        )
    gates.append(_gate("topic_safety_gate", "passed", "STRUCTURAL_FOCUS_ALLOWED", dimension.plain))

    if not request.contract_focus_confirmed:
        gates.append(_gate("contract_focus_gate", "blocked", "CONTRACT_FOCUS_UNCONFIRMED", "topic 与 focus 尚未由事件合同确认。"))
        return _make_report(
            record, request, advanced_runtime_sha256=None, selection_status="contract_unconfirmed",
            subject_mapping=subject, relation_decision=relation, gate_receipts=gates,
            dependencies=("CONTRACT_FOCUS_UNCONFIRMED",), headline="事件焦点未确认，未生成候选。",
        )
    gates.append(_gate("contract_focus_gate", "passed", "CONTRACT_FOCUS_CONFIRMED", "事件焦点已由调用方确认并绑定引用。"))

    if not request.advanced_context.calendar_context_confirmed:
        gates.append(_gate("calendar_provenance_gate", "blocked", "CALENDAR_PROVENANCE_UNCONFIRMED", "月日轴来源未确认。"))
        return _make_report(
            record, request, advanced_runtime_sha256=None, selection_status="calendar_unconfirmed",
            subject_mapping=subject, relation_decision=relation, gate_receipts=gates,
            dependencies=("CALENDAR_PROVENANCE_UNCONFIRMED",), headline="月日来源未确认，未生成候选矩阵。",
        )
    advanced = build_advanced_runtime_report(record, request.advanced_context)
    if advanced.context_status == "confirmed_partial":
        gates.append(_gate("calendar_provenance_gate", "blocked", "CALENDAR_CONTEXT_PARTIAL", "月建或日柱缺失。"))
        return _make_report(
            record, request, advanced_runtime_sha256=advanced.canonical_sha256,
            selection_status="calendar_partial", subject_mapping=subject,
            relation_decision=relation, gate_receipts=gates,
            dependencies=("CALENDAR_CONTEXT_PARTIAL",), headline="月日轴不完整，未生成候选矩阵。",
        )
    gates.append(_gate("calendar_provenance_gate", "passed", "CALENDAR_CONFIRMED_COMPLETE", "月建、日柱和来源声明齐备。"))

    if record.cast.casting_mode == "self":
        subject = SubjectMappingReceipt(
            "self",
            "bound_to_shi",
            record.chart.original.shi_line,
            "source_rule_and_chart_original_shi_line",
            ("SELF-TO-SHI",),
            _source_rule_refs("SELF-TO-SHI"),
        )
    elif not request.subject_mapping_confirmed:
        gates.append(_gate("subject_mapping_gate", "blocked", "SUBJECT_MAPPING_REQUIRED", "代摇主体位置尚未确认。"))
        return _make_report(
            record, request, advanced_runtime_sha256=advanced.canonical_sha256,
            selection_status="subject_mapping_required", subject_mapping=subject,
            relation_decision=relation, gate_receipts=gates,
            dependencies=("SUBJECT_MAPPING_REQUIRED",), headline="代摇主体未确认，未生成候选矩阵。",
        )
    else:
        subject = SubjectMappingReceipt(
            "proxy", "caller_confirmed", request.subject_position,
            "explicit_proxy_subject_mapping", (), request.subject_mapping_refs,
        )
    gates.append(_gate("subject_mapping_gate", "passed", "SUBJECT_MAPPING_BOUND", "主体映射已记录。"))

    relation = _source_relation_decision(
        request,
        casting_mode=record.cast.casting_mode,
    )
    blocked_relation_statuses = {
        "exam_scope_required": "exam_scope_required",
        "modern_exam_scope_unresolved": "exam_scope_unresolved",
        "relation_context_required": "relation_context_required",
        "manual_relation_required": "manual_relation_required",
        "source_method_conflict": "source_method_conflict",
        "unsupported_method": "unsupported_method",
        "relation_confirmation_required": "relation_confirmation_required",
    }
    if relation.status in blocked_relation_statuses:
        code = relation.conflict_codes[0] if relation.conflict_codes else relation.status.upper()
        gates.append(_gate("source_scope_method_gate", "blocked", code, relation.detail))
        return _make_report(
            record, request, advanced_runtime_sha256=advanced.canonical_sha256,
            selection_status=blocked_relation_statuses[relation.status],
            subject_mapping=subject, relation_decision=relation, gate_receipts=gates,
            dependencies=relation.conflict_codes or (code,), headline=relation.detail,
        )
    if relation.status == "manual_unvalidated_mapping":
        gates.append(
            _gate(
                "source_scope_method_gate",
                "review_required",
                "RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED",
                relation.detail,
            )
        )
    else:
        gates.append(_gate("source_scope_method_gate", "passed", "SOURCE_SCOPE_RESOLVED", relation.detail))
    if relation.status == "source_dual_relation":
        gates.append(_gate("relation_resolution_gate", "review_required", "RELATION_CONFIRMATION_REQUIRED", relation.detail))
    elif relation.status == "manual_unvalidated_mapping":
        gates.append(
            _gate(
                "relation_resolution_gate",
                "review_required",
                "RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED",
                relation.detail,
            )
        )
    else:
        gates.append(_gate("relation_resolution_gate", "passed", "RELATION_RESOLVED", relation.detail))

    if request.primary_position_confirmed:
        assert request.primary_position is not None
        actual_relation = record.chart.lines[request.primary_position - 1].six_relation
        if actual_relation not in {item.relation for item in relation.active_roles}:
            raise LiuYaoError("USE_GOD_MISMATCH", "确认爻位的六亲不属于当前关系候选")
        gates.append(_gate("use_position_gate", "passed", "CALLER_POSITION_CONFIRMED", "爻位由调用方确认并绑定引用。"))
    else:
        gates.append(_gate("use_position_gate", "passed", "NO_POSITION_OVERRIDE", "由矩阵保留唯一候选或多候选待确认语义。"))

    matrix_receipts: list[ValidityMatrixReceipt] = []
    candidates: list[SelectionCandidate] = []
    for role in relation.active_roles:
        primary = None
        if request.primary_position_confirmed:
            assert request.primary_position is not None
            if record.chart.lines[request.primary_position - 1].six_relation == role.relation:
                primary = request.primary_position
        interpretation = InterpretationRequest(
            topic=request.topic,
            focus_dimension=request.focus_dimension,
            use_relation=role.relation,
            primary_position=primary,
            calendar_context_confirmed=True,
            reality_status=request.reality_status,
            reality_facts=request.reality_facts,
            notes=(f"selection_role={role.role_id}",),
        )
        validity_request = ValidityRequest(
            interpretation=interpretation,
            advanced_context=request.advanced_context,
            reality_evidence_refs=request.reality_evidence_refs,
            reality_evidence_confirmed=request.reality_evidence_confirmed,
        )
        matrix = build_validity_matrix(record, validity_request)
        node_by_id = _validate_matrix_binding(
            record,
            validity_request,
            role,
            advanced.canonical_sha256,
            matrix,
        )
        receipt = _matrix_receipt(role, validity_request, matrix)
        matrix_receipts.append(receipt)
        for position in matrix.focus_selection.candidate_positions:
            candidates.append(
                _visible_candidate(record, role, receipt, matrix, node_by_id[f"original:{position}"])
            )
        for hidden in matrix.hidden_candidates:
            if hidden.relation == role.relation:
                candidates.append(_hidden_candidate(record, role, receipt, matrix, hidden))

    candidates = _add_source_preferences(record, candidates)
    gates.append(_gate("validity_matrix_gate", "passed", "VALIDITY_MATRICES_BOUND", "每个活动关系均绑定一份第二切片矩阵。"))
    provisional = tuple(item.candidate_id for item in candidates if item.contributes)
    multiple_ready_candidates = len(provisional) > 1
    if multiple_ready_candidates:
        candidates = [
            replace(
                item,
                contributes=False,
                decision_codes=tuple(
                    dict.fromkeys(item.decision_codes + ("MULTIPLE_REVIEW_CANDIDATES",))
                ),
            )
            if item.contributes
            else item
            for item in candidates
        ]
        provisional = ()
    visible = tuple(item for item in candidates if item.source_kind == "visible_original")
    hidden = tuple(item for item in candidates if item.source_kind == "hidden")
    matrix_statuses = {item.focus_status for item in matrix_receipts}

    if relation.status == "source_dual_relation":
        status = "relation_confirmation_required"
        provisional_id = None
        dependencies = ("RELATION_CONFIRMATION_REQUIRED",)
        headline = "官父两组来源候选均已登记，尚未收窄为单一关系。"
    elif relation.status == "manual_unvalidated_mapping":
        status = "manual_unvalidated_mapping"
        provisional_id = None
        dependencies = relation.conflict_codes
        headline = "来源范围外人工映射仅保留候选审计，不形成自动贡献。"
    elif any(item.focus_selection_status == "ambiguous" for item in matrix_receipts):
        status = "tie_needs_confirmation"
        provisional_id = None
        dependencies = ("USE_LINE_CONFIRMATION_REQUIRED",)
        headline = "同六亲有多个可见候选；发动与来源偏好均不用于决胜。"
    elif not visible and hidden:
        status = "hidden_candidate_needs_confirmation"
        provisional_id = None
        dependencies = ("HIDDEN_NEVER_AUTO_CONTRIBUTES",)
        headline = "只发现伏神候选；伏神不自动出伏或取用。"
    elif not candidates:
        status = "no_candidate"
        provisional_id = None
        dependencies = ("NO_STRUCTURAL_CANDIDATE",)
        headline = "当前结构中没有登记到对应候选。"
    elif multiple_ready_candidates:
        status = "multiple_review_candidates"
        provisional_id = None
        dependencies = ("MULTIPLE_REVIEW_CANDIDATES",)
        headline = "多个候选同时通过基础门禁，系统不自动决胜。"
    elif len(provisional) == 1:
        status = "single_review_candidate"
        provisional_id = provisional[0]
        dependencies = ()
        headline = "生成一个待人工复核的临时候选；不构成最终用神或事件结论。"
    elif "unresolved" in matrix_statuses:
        status = "validity_unresolved"
        provisional_id = None
        dependencies = tuple(
            dict.fromkeys(code for item in matrix_receipts for code in item.focus_dependencies)
        ) or ("VALIDITY_UNRESOLVED",)
        headline = "焦点有效性或作用方向仍未决，不形成临时候选。"
    elif "conditional" in matrix_statuses:
        status = "validity_conditional"
        provisional_id = None
        dependencies = tuple(
            dict.fromkeys(code for item in matrix_receipts for code in item.focus_dependencies)
        ) or ("VALIDITY_CONDITIONAL",)
        headline = "焦点仍有开放条件义务，不形成临时候选。"
    else:
        status = "candidate_review_required"
        provisional_id = None
        dependencies = tuple(
            dict.fromkeys(code for item in matrix_receipts for code in item.focus_dependencies)
        ) or ("CANDIDATE_REVIEW_REQUIRED",)
        headline = "候选收据已生成，但尚不满足单一临时候选条件。"

    gates.append(
        _gate(
            "candidate_review_gate",
            "passed" if provisional_id is not None else "review_required",
            "PROVISIONAL_REVIEW_CANDIDATE" if provisional_id is not None else dependencies[0],
            headline,
        )
    )
    return _make_report(
        record,
        request,
        advanced_runtime_sha256=advanced.canonical_sha256,
        selection_status=status,
        subject_mapping=subject,
        relation_decision=relation,
        gate_receipts=gates,
        matrix_receipts=tuple(matrix_receipts),
        candidates=tuple(candidates),
        provisional_candidate_id=provisional_id,
        dependencies=dependencies,
        headline=headline,
    )


__all__ = [
    "SELECTION_RUNTIME_METHOD_ID",
    "SELECTION_RUNTIME_PRODUCTION_ALLOWED",
    "SELECTION_RUNTIME_STATUS",
    "CandidatePathReceipt",
    "GateReceipt",
    "RelationDecision",
    "RelationRole",
    "SelectionCandidate",
    "SelectionRequest",
    "SelectionRuntimeReport",
    "SubjectMappingReceipt",
    "ValidityMatrixReceipt",
    "build_selection_runtime_report",
]
