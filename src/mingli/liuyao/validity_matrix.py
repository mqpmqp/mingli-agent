from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping

from .advanced_facts import classify_branch_relation, classify_element_relation, growth_stage
from .advanced_runtime import (
    AdvancedContextRequest,
    AdvancedRuntimeReport,
    build_advanced_runtime_report,
)
from .case_record import LiuYaoCaseRecord
from .interpretation import InterpretationRequest
from .tables import PREDICTION_VALIDITY, digest
from .validation import LiuYaoError, _reject_unknown, _require_mapping, _string_tuple

VALIDITY_MATRIX_METHOD_ID = "liuyao-validity-conflict-matrix@0.1.0"
VALIDITY_MATRIX_STATUS = "review_only"
VALIDITY_MATRIX_PRODUCTION_ALLOWED = False

VALIDITY_RULE_PROFILE_ID = "liuyao-shaoweihua-source-only-validity@0.1.0"
VALIDITY_RULE_PROFILE_STATUS = "draft"
VALIDITY_RULE_EVIDENCE_LEVEL = "source_only"
VALIDITY_RULE_HUMAN_REVIEWED = False
VALIDITY_SOURCE_FAMILY_ID = "shaoweihua-liuyao-lineage"
VALIDITY_ENGINEERING_POLICY_ID = "liuyao-validity-engineering-policy@0.1.0"
VALIDITY_ENGINEERING_POLICY_STATUS = "review_only"

_SOURCE_FAMILY_ALIASES = {
    VALIDITY_SOURCE_FAMILY_ID: "F_SHAO_PARALLEL_TEXT",
    "zhangzhichun-commentary": "F_ZHANG_COMMENTARY",
}

_MAX_PATH_HOPS = 2
_MAX_PATHS = 256

_SOURCE_FILES = {
    "src_039": {
        "title": "周易预测宝典",
        "sha256": "afa2cd2ad5acc09f3d7b4f4bb65f98d71f2199125ddef6ada84a0d114a626f79",
        "source_family_id": VALIDITY_SOURCE_FAMILY_ID,
    },
    "src_037": {
        "title": "周易与预测学",
        "sha256": "c00449b2a1d58da4da091a0078e580ad7657f015b3bed770131d11db158b4fb8",
        "source_family_id": VALIDITY_SOURCE_FAMILY_ID,
    },
    "src_040": {
        "title": "未知之门",
        "sha256": "3e7a8c70fb0d4554f5b17d25bf50069c3366fd0e7aaecb79c097a8ee32dedb01",
        "source_family_id": "zhangzhichun-commentary",
    },
}
_SOURCE_REFS = {
    "void": (
        "src_039:print94-95/pdf94-95,print165-166/pdf165-166",
        "src_037:print181-182/pdf196-197",
    ),
    "void_moving_conflict": (
        "src_039:print165-166/pdf165-166,print202/pdf202",
        "src_037:print181-182/pdf196-197,print219/pdf234",
    ),
    "void_clash": (
        "src_039:print200/pdf200",
        "src_037:print217/pdf232",
    ),
    "void_fill": (
        "src_039:print200/pdf200,print202/pdf202,print220/pdf220",
        "src_037:print217/pdf232,print219/pdf234,print237/pdf252",
    ),
    "month_break": (
        "src_039:print198-199/pdf198-199",
        "src_037:print215-216/pdf230-231",
    ),
    "day_clash": (
        "src_039:print200/pdf200",
        "src_037:print217/pdf232",
    ),
    "tomb": (
        "src_039:print219-221/pdf219-221,print338-339/pdf338-339",
        "src_037:print236-238/pdf251-253,print359-360/pdf374-375",
    ),
    "absolute": (
        "src_039:print335/pdf335,print338/pdf338",
        "src_037:print356/pdf371,print359/pdf374",
    ),
    "storage_release": (
        "src_039:print219/pdf219,print221/pdf221,print296/pdf296,print339/pdf339",
        "src_037:print236/pdf251,print238/pdf253,print358/pdf373,print360/pdf375",
    ),
    "flying_hidden": (
        "src_039:print169-172/pdf169-172",
        "src_037:print185-188/pdf200-203",
    ),
    "hidden_control_conflict": (
        "src_039:print170/pdf170,print172/pdf172",
        "src_037:print186/pdf201,print188/pdf203",
    ),
    "changed_scope": (
        "src_039:print193-194/pdf193-194",
        "src_037:print210-211/pdf225-226",
    ),
}
_RULE_SOURCE_EVIDENCE = {
    "void": (
        ("src_039:print94/pdf94", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_039:print95/pdf95", "author_case", "case_specific", ()),
        ("src_039:print165/pdf165", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_039:print166/pdf166", "author_case", "case_specific", ()),
        ("src_037:print181/pdf196", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_037:print182/pdf197", "author_case", "case_specific", ()),
    ),
    "void_moving_conflict": (
        ("src_039:print165/pdf165", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_039:print166/pdf166", "author_case", "case_specific", ()),
        ("src_039:print202/pdf202", "attributed_quote", "scope_unresolved_not_global_override", ()),
        ("src_037:print181/pdf196", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_037:print182/pdf197", "author_case", "case_specific", ()),
        ("src_037:print219/pdf234", "attributed_quote", "scope_unresolved_not_global_override", ()),
    ),
    "void_clash": (
        ("src_039:print200/pdf200", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_037:print217/pdf232", "author_rule", "general_structure_scope_unresolved", ()),
    ),
    "void_fill": (
        ("src_039:print200/pdf200", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_039:print202/pdf202", "attributed_quote", "editorial_text_unresolved", ()),
        ("src_039:print220/pdf220", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_037:print217/pdf232", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_037:print219/pdf234", "attributed_quote", "editorial_text_unresolved", ()),
        ("src_037:print237/pdf252", "author_rule", "general_structure_scope_unresolved", ()),
    ),
    "month_break": (
        ("src_039:print198/pdf198", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_039:print199/pdf199", "author_case", "case_specific", ()),
        ("src_037:print215/pdf230", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_037:print216/pdf231", "author_case", "case_specific", ()),
    ),
    "day_clash": (
        ("src_039:print200/pdf200", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_037:print217/pdf232", "author_rule", "general_structure_scope_unresolved", ()),
    ),
    "tomb": (
        ("src_039:print219-221/pdf219-221", "author_rule", "general_structure_scope_unresolved", ("墓", "库", "入库")),
        ("src_039:print338/pdf338", "author_rule", "general_structure_scope_unresolved", ("墓", "库")),
        ("src_039:print339/pdf339", "author_case", "case_specific", ("库之破",)),
        ("src_037:print236-238/pdf251-253", "author_rule", "general_structure_scope_unresolved", ("墓", "库", "入库")),
        ("src_037:print359/pdf374", "author_rule", "general_structure_scope_unresolved", ("墓", "库")),
        ("src_037:print360/pdf375", "author_case", "case_specific", ("库之破",)),
    ),
    "absolute": (
        ("src_039:print335/pdf335", "author_rule", "general_structure_scope_unresolved", ("绝",)),
        ("src_039:print338/pdf338", "author_rule", "general_structure_scope_unresolved", ("绝",)),
        ("src_037:print356/pdf371", "author_rule", "general_structure_scope_unresolved", ("绝",)),
        ("src_037:print359/pdf374", "author_rule", "general_structure_scope_unresolved", ("绝",)),
    ),
    "storage_release": (
        ("src_039:print219/pdf219", "author_rule", "general_structure_scope_unresolved", ("冲库",)),
        ("src_039:print221/pdf221", "author_rule", "general_structure_scope_unresolved", ("冲库",)),
        ("src_039:print296/pdf296", "author_rule", "general_structure_scope_unresolved", ("冲开库",)),
        ("src_039:print339/pdf339", "author_case", "case_specific", ("库之破",)),
        ("src_037:print236/pdf251", "author_rule", "general_structure_scope_unresolved", ("冲库",)),
        ("src_037:print238/pdf253", "author_rule", "general_structure_scope_unresolved", ("冲库",)),
        ("src_037:print358/pdf373", "author_rule", "general_structure_scope_unresolved", ("冲开库",)),
        ("src_037:print360/pdf375", "author_case", "case_specific", ("库之破",)),
    ),
    "flying_hidden": (
        ("src_039:print169-172/pdf169-172", "author_rule", "general_structure_scope_unresolved", ()),
        ("src_037:print185-188/pdf200-203", "author_rule", "general_structure_scope_unresolved", ()),
    ),
    "hidden_control_conflict": (
        ("src_039:print170/pdf170", "author_rule", "scope_unresolved_no_deterministic_outcome", ()),
        ("src_039:print172/pdf172", "author_rule", "scope_unresolved_no_deterministic_outcome", ()),
        ("src_037:print186/pdf201", "author_rule", "scope_unresolved_no_deterministic_outcome", ()),
        ("src_037:print188/pdf203", "author_rule", "scope_unresolved_no_deterministic_outcome", ()),
    ),
    "changed_scope": (
        ("src_039:print193-194/pdf193-194", "author_rule", "original_changed_same_position", ()),
        ("src_037:print210-211/pdf225-226", "author_rule", "original_changed_same_position", ()),
    ),
}
_SCOPE_AUDIT_REFS = MappingProxyType({
    "source_family_id": "zhangzhichun-commentary",
    "source_refs": (
        "src_040:print210/pdf227,print239/pdf256",
        "src_040:print211/pdf228,print213/pdf230",
        "src_040:print223/pdf240",
        "src_040:print300-302/pdf317-319",
    ),
    "activates_rules": False,
    "purpose": "scope_conflict_and_role_polarity_audit_only",
})
_SCOPE_AUDIT_RULES = (
    (
        "ZHANG-LIFELONG-SELF-VOID-SCOPE",
        "src_040:print239/pdf256",
        "author_rule",
        "lifelong",
        "self_line",
    ),
    (
        "ZHANG-ROLE-POLARITY-CASES",
        "src_040:print211,213/pdf228,230",
        "author_case",
        "case_specific",
        "sought_use_or_illness_avoid",
    ),
    (
        "ZHANG-NO-FIXED-PRIORITY",
        "src_040:print223/pdf240",
        "author_methodology",
        "timing_method_boundary",
        "unassigned",
    ),
)
_SOURCE_TEXT_ANOMALIES = (
    (
        "VOID_FILL_WORDING_219_202",
        ("src_039:print202/pdf202", "src_037:print219/pdf234"),
        "旬空、填空之日不为空",
        "冲空、填空之日不为空",
        "unresolved_editorial_text",
    ),
    (
        "HIDDEN_TOMB_ABSOLUTE_GRAMMAR_172",
        ("src_039:print172/pdf172",),
        "伏神库绝于日、月飞神者",
        None,
        "scope_and_grammar_unresolved",
    ),
)


@dataclass(frozen=True, slots=True)
class PriorityBand:
    band_id: str
    order: int
    purpose: str

    def to_dict(self) -> dict[str, object]:
        return {"band_id": self.band_id, "order": self.order, "purpose": self.purpose}


VALIDITY_PRIORITY_BANDS = (
    PriorityBand("contract_integrity_gate", 800, "冻结合同、类型与哈希完整性前置门禁。"),
    PriorityBand("reality_gate", 700, "有证据引用的现实硬阻断只覆盖行动状态。"),
    PriorityBand("calendar_provenance_gate", 600, "月日轴及其来源声明门禁。"),
    PriorityBand("use_selection_gate", 500, "用神必须为显式确认或唯一可见候选。"),
    PriorityBand("node_validity", 400, "空、破、墓、绝及合冲条件义务。"),
    PriorityBand("hidden_self_gate", 350, "伏神自身资格先于飞神释放候选。"),
    PriorityBand("same_position_change", 300, "变爻只回头作用本位原爻。"),
    PriorityBand("direct_moving_to_use", 200, "动爻到所选用神的直接候选边。"),
    PriorityBand("indirect_moving_path", 100, "多动爻间接路径只作聚焦候选。"),
    PriorityBand("path_validity", 50, "汇总保留路径的有效性与未决冲突。"),
)
_PRIORITY = {item.band_id: item.order for item in VALIDITY_PRIORITY_BANDS}
VALIDITY_GATE_PRIORITY = (
    "reality_gate",
    "calendar_provenance_gate",
    "use_selection_gate",
    "node_validity",
    "path_validity",
)
VALIDITY_PRECONDITION_GATES = ("contract_integrity_gate",)
VALIDITY_PRIORITY_TABLE_SHA256 = digest(
    {
        "priority_bands": [item.to_dict() for item in VALIDITY_PRIORITY_BANDS],
        "precondition_gates": VALIDITY_PRECONDITION_GATES,
        "gate_priority": VALIDITY_GATE_PRIORITY,
    }
)
_VALIDITY_RULE_CONTRACT_DATA = {
    "single_condition_policy": "open_obligation_never_hard_prune",
    "void_moving_policy": "author_internal_conflict_unresolved",
    "month_break_relief": (
        "out_of_month_candidate",
        "fill_by_day_candidate",
        "combine_candidate",
    ),
    "storage_release_normalized_relation": "storage_release_by_clash",
    "storage_release_source_terms": ("冲库", "冲开库", "库之破"),
    "absolute_policy": "growth_recovery_candidate_unresolved",
    "hidden_policy": "hidden_self_before_flying_release",
    "changed_line_scope": "same_position_original_only",
    "same_priority_conflict": "unresolved_no_scoring_no_load_order_override",
}
VALIDITY_RULE_CONTRACT = MappingProxyType(_VALIDITY_RULE_CONTRACT_DATA)

_VALIDITY_ENGINEERING_POLICY_DATA = {
    "node_axes": (
        "structural_eligibility",
        "current_force",
        "manifestation_state",
        "role_polarity",
    ),
    "changed_line_enforcement": "exclude_cross_position_edges_with_receipt",
    "maximum_path_hops": _MAX_PATH_HOPS,
    "maximum_paths": _MAX_PATHS,
    "path_enumeration_exclusion_reasons": (
        "changed_cross_position_excluded",
        "cycle",
        "length_limit",
        "not_focus_relevant",
        "enumeration_limit",
    ),
    "reality_evidence_gate": "explicit_confirmation_and_bound_refs_required",
    "path_status_axes": ("validity_status", "enumeration_status"),
}
VALIDITY_ENGINEERING_POLICY = MappingProxyType(_VALIDITY_ENGINEERING_POLICY_DATA)


def _rule_profile_payload() -> dict[str, object]:
    return {
        "profile_id": VALIDITY_RULE_PROFILE_ID,
        "profile_status": VALIDITY_RULE_PROFILE_STATUS,
        "evidence_level": VALIDITY_RULE_EVIDENCE_LEVEL,
        "human_reviewed": VALIDITY_RULE_HUMAN_REVIEWED,
        "source_family_id": VALIDITY_SOURCE_FAMILY_ID,
        "source_family_aliases": dict(_SOURCE_FAMILY_ALIASES),
        "active_rule_source_family_count": 1,
        "referenced_text_family_count": 2,
        "empirical_validation_source_family_count": 0,
        "source_files": {
            source_id: dict(metadata)
            for source_id, metadata in _SOURCE_FILES.items()
        },
        "source_refs": {key: list(value) for key, value in _SOURCE_REFS.items()},
        "rule_source_evidence": {
            key: [
                {
                    "source_ref": source_ref,
                    "source_family": VALIDITY_SOURCE_FAMILY_ID,
                    "source_level": source_level,
                    "topic_scope": topic_scope,
                    "source_terms": list(source_terms),
                }
                for source_ref, source_level, topic_scope, source_terms in evidence
            ]
            for key, evidence in _RULE_SOURCE_EVIDENCE.items()
        },
        "supplementary_scope_audit": {
            "source_family_id": _SCOPE_AUDIT_REFS["source_family_id"],
            "source_refs": list(_SCOPE_AUDIT_REFS["source_refs"]),
            "activates_rules": False,
            "purpose": _SCOPE_AUDIT_REFS["purpose"],
            "rules": [
                {
                    "audit_id": audit_id,
                    "source_ref": source_ref,
                    "source_level": source_level,
                    "topic_scope": topic_scope,
                    "node_role": node_role,
                    "activates_rules": False,
                }
                for (
                    audit_id,
                    source_ref,
                    source_level,
                    topic_scope,
                    node_role,
                ) in _SCOPE_AUDIT_RULES
            ],
        },
        "source_text_anomalies": [
            {
                "anomaly_id": anomaly_id,
                "source_refs": list(source_refs),
                "reason_code": "SOURCE_TEXT_ANOMALY",
                "source_text": source_text,
                "candidate_reading": candidate_reading,
                "resolution": resolution,
                "activates_rules": False,
            }
            for (
                anomaly_id,
                source_refs,
                source_text,
                candidate_reading,
                resolution,
            ) in _SOURCE_TEXT_ANOMALIES
        ],
        "rule_contract": {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in VALIDITY_RULE_CONTRACT.items()
        },
    }


def _engineering_policy_payload() -> dict[str, object]:
    return {
        "policy_id": VALIDITY_ENGINEERING_POLICY_ID,
        "policy_status": VALIDITY_ENGINEERING_POLICY_STATUS,
        "priority_bands": [item.to_dict() for item in VALIDITY_PRIORITY_BANDS],
        "priority_table_sha256": VALIDITY_PRIORITY_TABLE_SHA256,
        "precondition_gates": list(VALIDITY_PRECONDITION_GATES),
        "gate_priority": list(VALIDITY_GATE_PRIORITY),
        "policy_contract": {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in VALIDITY_ENGINEERING_POLICY.items()
        },
    }


VALIDITY_RULE_PROFILE_SHA256 = digest(_rule_profile_payload())
VALIDITY_ENGINEERING_POLICY_SHA256 = digest(_engineering_policy_payload())

_SELECTED_STATES = frozenset({"confirmed", "unique_candidate"})
_RELEASE_OBLIGATIONS = frozenset(
    {
        "VOID_EFFECT_OPEN",
        "MONTH_BREAK_OPEN",
        "MONTH_TOMB_EFFECT_OPEN",
        "DAY_TOMB_EFFECT_OPEN",
        "MONTH_ABSOLUTE_EFFECT_OPEN",
        "DAY_ABSOLUTE_EFFECT_OPEN",
    }
)
_UNKNOWN_OBLIGATIONS = frozenset(
    {
        "CALENDAR_PROVENANCE_UNCONFIRMED",
        "CALENDAR_MONTH_MISSING",
        "CALENDAR_DAY_MISSING",
    }
)
_DIRECTION_OPEN_OBLIGATIONS = frozenset(
    {
        "DAY_CLASH_EFFECT_OPEN",
        "MONTH_COMBINE_EFFECT_OPEN",
        "DAY_COMBINE_EFFECT_OPEN",
        "MONTH_TOMB_EFFECT_OPEN",
        "DAY_TOMB_EFFECT_OPEN",
        "MONTH_ABSOLUTE_EFFECT_OPEN",
        "DAY_ABSOLUTE_EFFECT_OPEN",
        "RULE_EFFECT_CONFLICT",
    }
)
@dataclass(frozen=True, slots=True)
class ValidityRequest:
    interpretation: InterpretationRequest
    advanced_context: AdvancedContextRequest
    reality_evidence_refs: tuple[str, ...] = ()
    reality_evidence_confirmed: bool = False
    rule_profile_id: str = VALIDITY_RULE_PROFILE_ID

    def __post_init__(self) -> None:
        if not isinstance(self.interpretation, InterpretationRequest):
            raise LiuYaoError("INVALID_INPUT", "interpretation 必须是 InterpretationRequest")
        if not isinstance(self.advanced_context, AdvancedContextRequest):
            raise LiuYaoError("INVALID_INPUT", "advanced_context 必须是 AdvancedContextRequest")
        if self.interpretation.calendar_context_confirmed != self.advanced_context.calendar_context_confirmed:
            raise LiuYaoError(
                "CALENDAR_CONFIRMATION_MISMATCH",
                "解释请求和高级上下文的 calendar_context_confirmed 必须一致",
            )
        refs = _string_tuple(self.reality_evidence_refs, "reality_evidence_refs")
        object.__setattr__(self, "reality_evidence_refs", refs)
        if not isinstance(self.reality_evidence_confirmed, bool):
            raise LiuYaoError("INVALID_INPUT", "reality_evidence_confirmed 必须是布尔值")
        if self.interpretation.reality_status == "unknown" and (
            refs or self.reality_evidence_confirmed
        ):
            raise LiuYaoError(
                "REALITY_STATUS_REQUIRED",
                "确认现实证据时 reality_status 不能是 unknown",
            )
        if self.interpretation.reality_status != "unknown":
            if not self.reality_evidence_confirmed:
                raise LiuYaoError(
                    "REALITY_CONFIRMATION_REQUIRED",
                    "非 unknown 的现实状态必须显式确认 evidence refs",
                )
            if not refs:
                raise LiuYaoError(
                    "REALITY_EVIDENCE_REQUIRED",
                    "非 unknown 的现实状态必须在 ValidityRequest 提供 evidence refs",
                )
        if self.rule_profile_id != VALIDITY_RULE_PROFILE_ID:
            raise LiuYaoError("UNSUPPORTED_RULE_PROFILE", "不支持的有效性规则 profile")

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "interpretation": self.interpretation.to_dict(),
            "advanced_context": self.advanced_context.to_dict(),
            "reality_evidence_refs": list(self.reality_evidence_refs),
            "reality_evidence_confirmed": self.reality_evidence_confirmed,
            "rule_profile_id": self.rule_profile_id,
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ValidityRequest":
        allowed = {
            "interpretation",
            "advanced_context",
            "reality_evidence_refs",
            "reality_evidence_confirmed",
            "rule_profile_id",
            "canonical_sha256",
        }
        _reject_unknown(value, allowed, "validity_request")
        missing = {"interpretation", "advanced_context"} - set(value)
        if missing:
            raise LiuYaoError(
                "INVALID_INPUT",
                f"validity_request 缺少字段：{', '.join(sorted(missing))}",
            )
        request = cls(
            interpretation=InterpretationRequest.from_mapping(
                _require_mapping(value["interpretation"], "interpretation")
            ),
            advanced_context=AdvancedContextRequest.from_mapping(
                _require_mapping(value["advanced_context"], "advanced_context")
            ),
            reality_evidence_refs=_string_tuple(
                value.get("reality_evidence_refs", ()), "reality_evidence_refs"
            ),
            reality_evidence_confirmed=value.get("reality_evidence_confirmed", False),
            rule_profile_id=value.get("rule_profile_id", VALIDITY_RULE_PROFILE_ID),
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != request.canonical_sha256:
            raise LiuYaoError("RECORD_TAMPERED", "validity_request canonical_sha256 与重算结果不一致")
        return request


@dataclass(frozen=True, slots=True)
class RuleSourceEvidence:
    source_ref: str
    source_family: str
    source_level: str
    topic_scope: str
    source_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_ref": self.source_ref,
            "source_family": self.source_family,
            "source_level": self.source_level,
            "topic_scope": self.topic_scope,
            "source_terms": list(self.source_terms),
        }


@dataclass(frozen=True, slots=True)
class RuleHit:
    trace_id: str
    rule_id: str
    priority_band: str
    priority: int
    subject_id: str
    effect: str
    reason_code: str
    policy_id: str
    priority_policy_id: str
    source_family: str
    source_level: str
    source_refs: tuple[str, ...]
    source_evidence: tuple[RuleSourceEvidence, ...]
    topic_scope: str
    node_role: str
    opened_obligations: tuple[str, ...]
    discharged_obligations: tuple[str, ...]
    remaining_obligations: tuple[str, ...]
    outcome: str
    normalized_relation: str | None
    source_terms: tuple[str, ...]
    conflict_group: str | None
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "rule_id": self.rule_id,
            "priority_band": self.priority_band,
            "priority": self.priority,
            "subject_id": self.subject_id,
            "effect": self.effect,
            "reason_code": self.reason_code,
            "policy_id": self.policy_id,
            "priority_policy_id": self.priority_policy_id,
            "source_family": self.source_family,
            "source_level": self.source_level,
            "source_refs": list(self.source_refs),
            "source_evidence": [item.to_dict() for item in self.source_evidence],
            "topic_scope": self.topic_scope,
            "node_role": self.node_role,
            "opened_obligations": list(self.opened_obligations),
            "discharged_obligations": list(self.discharged_obligations),
            "remaining_obligations": list(self.remaining_obligations),
            "outcome": self.outcome,
            "normalized_relation": self.normalized_relation,
            "source_terms": list(self.source_terms),
            "conflict_group": self.conflict_group,
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class FocusSelection:
    relation: str
    status: str
    selected_position: int | None
    candidate_positions: tuple[int, ...]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "relation": self.relation,
            "status": self.status,
            "selected_position": self.selected_position,
            "candidate_positions": list(self.candidate_positions),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class NodeValidity:
    node_id: str
    node_kind: str
    position: int
    branch: str
    element: str
    motion_kind: str
    selected_use: bool
    structural_eligibility: str
    current_force: str
    manifestation_state: str
    role_polarity: str
    state: str
    open_obligations: tuple[str, ...]
    relief_candidates: tuple[str, ...]
    month_relation: str | None
    day_relation: str | None
    month_growth_stage: str | None
    day_growth_stage: str | None
    rule_hits: tuple[RuleHit, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "position": self.position,
            "branch": self.branch,
            "element": self.element,
            "motion_kind": self.motion_kind,
            "selected_use": self.selected_use,
            "structural_eligibility": self.structural_eligibility,
            "current_force": self.current_force,
            "manifestation_state": self.manifestation_state,
            "role_polarity": self.role_polarity,
            "state": self.state,
            "open_obligations": list(self.open_obligations),
            "relief_candidates": list(self.relief_candidates),
            "month_relation": self.month_relation,
            "day_relation": self.day_relation,
            "month_growth_stage": self.month_growth_stage,
            "day_growth_stage": self.day_growth_stage,
            "rule_hits": [item.to_dict() for item in self.rule_hits],
        }


@dataclass(frozen=True, slots=True)
class HiddenValidity:
    hidden_node: NodeValidity
    relation: str
    flying_node_id: str
    flying_state: str
    flying_to_hidden: str
    hidden_to_flying: str
    visibility_state: str
    activation_state: str
    open_obligations: tuple[str, ...]
    release_candidates: tuple[str, ...]
    rule_hits: tuple[RuleHit, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "hidden_node": self.hidden_node.to_dict(),
            "relation": self.relation,
            "flying_node_id": self.flying_node_id,
            "flying_state": self.flying_state,
            "flying_to_hidden": self.flying_to_hidden,
            "hidden_to_flying": self.hidden_to_flying,
            "visibility_state": self.visibility_state,
            "activation_state": self.activation_state,
            "open_obligations": list(self.open_obligations),
            "release_candidates": list(self.release_candidates),
            "rule_hits": [item.to_dict() for item in self.rule_hits],
        }


@dataclass(frozen=True, slots=True)
class InteractionEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_kind: str
    relation: str
    direction: str
    priority_band: str
    source_state: str
    target_state: str
    status: str
    prune_reason: str | None
    rule_hits: tuple[RuleHit, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_kind": self.edge_kind,
            "relation": self.relation,
            "direction": self.direction,
            "priority_band": self.priority_band,
            "source_state": self.source_state,
            "target_state": self.target_state,
            "status": self.status,
            "prune_reason": self.prune_reason,
            "rule_hits": [item.to_dict() for item in self.rule_hits],
        }


@dataclass(frozen=True, slots=True)
class InfluencePath:
    path_id: str
    source_node_id: str
    target_node_id: str
    edge_ids: tuple[str, ...]
    validity_status: str
    enumeration_status: str
    direction: str
    candidate_graph_reaches_focus: bool
    enumeration_reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "path_id": self.path_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_ids": list(self.edge_ids),
            "validity_status": self.validity_status,
            "enumeration_status": self.enumeration_status,
            "direction": self.direction,
            "candidate_graph_reaches_focus": self.candidate_graph_reaches_focus,
            "enumeration_reason": self.enumeration_reason,
        }


@dataclass(frozen=True, slots=True)
class ValidityConflict:
    conflict_id: str
    code: str
    subjects: tuple[str, ...]
    severity: str
    resolution: str
    rule_ids: tuple[str, ...]
    technical: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "conflict_id": self.conflict_id,
            "code": self.code,
            "subjects": list(self.subjects),
            "severity": self.severity,
            "resolution": self.resolution,
            "rule_ids": list(self.rule_ids),
            "technical": self.technical,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class ValidityMatrixReport:
    case_id: str
    case_record_sha256: str
    chart_sha256: str
    request: ValidityRequest
    advanced_runtime_sha256: str
    focus_selection: FocusSelection
    focus_status: str
    inventory_status: str
    nodes: tuple[NodeValidity, ...]
    hidden_candidates: tuple[HiddenValidity, ...]
    edges: tuple[InteractionEdge, ...]
    paths: tuple[InfluencePath, ...]
    conflicts: tuple[ValidityConflict, ...]
    focus_dependencies: tuple[str, ...]
    inventory_dependencies: tuple[str, ...]
    reality_override: str
    trace_sha256: str
    headline: str
    warnings: tuple[str, ...]
    limits: tuple[str, ...]

    @property
    def canonical_sha256(self) -> str:
        return digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        rule_profile = _rule_profile_payload()
        rule_profile["profile_sha256"] = VALIDITY_RULE_PROFILE_SHA256
        engineering_policy = _engineering_policy_payload()
        engineering_policy["policy_sha256"] = VALIDITY_ENGINEERING_POLICY_SHA256
        payload: dict[str, object] = {
            "method_id": VALIDITY_MATRIX_METHOD_ID,
            "validity_matrix_status": VALIDITY_MATRIX_STATUS,
            "production_allowed": VALIDITY_MATRIX_PRODUCTION_ALLOWED,
            "prediction_validity": PREDICTION_VALIDITY,
            "rule_profile": rule_profile,
            "engineering_policy": engineering_policy,
            "case_id": self.case_id,
            "case_record_sha256": self.case_record_sha256,
            "chart_sha256": self.chart_sha256,
            "request": self.request.to_dict(),
            "interpretation_request_sha256": self.request.interpretation.canonical_sha256,
            "advanced_runtime_sha256": self.advanced_runtime_sha256,
            "priority_table_sha256": VALIDITY_PRIORITY_TABLE_SHA256,
            "engineering_policy_sha256": VALIDITY_ENGINEERING_POLICY_SHA256,
            "gate_priority_receipt": list(VALIDITY_GATE_PRIORITY),
            "focus_selection": self.focus_selection.to_dict(),
            "focus_status": self.focus_status,
            "inventory_status": self.inventory_status,
            "nodes": [item.to_dict() for item in self.nodes],
            "hidden_candidates": [item.to_dict() for item in self.hidden_candidates],
            "edges": [item.to_dict() for item in self.edges],
            "paths": [item.to_dict() for item in self.paths],
            "conflicts": [item.to_dict() for item in self.conflicts],
            "focus_dependencies": list(self.focus_dependencies),
            "inventory_dependencies": list(self.inventory_dependencies),
            "reality_override": self.reality_override,
            "trace_sha256": self.trace_sha256,
            "headline": self.headline,
            "warnings": list(self.warnings),
            "limits": list(self.limits),
        }
        if include_hash:
            payload["canonical_sha256"] = digest(payload)
        return payload


def _hit(
    *,
    subject_id: str,
    rule_id: str,
    priority_band: str,
    effect: str,
    reason_code: str,
    source_key: str | None,
    technical: str,
    plain: str,
    conflict_group: str | None = None,
    topic_scope: str = "general_structure_scope_unresolved",
    node_role: str | None = None,
    opened_obligations: tuple[str, ...] | None = None,
    discharged_obligations: tuple[str, ...] = (),
    remaining_obligations: tuple[str, ...] | None = None,
    outcome: str | None = None,
    normalized_relation: str | None = None,
    source_terms: tuple[str, ...] = (),
) -> RuleHit:
    inferred_opened = (
        (reason_code,)
        if effect == "open"
        or reason_code.endswith("_OPEN")
        or reason_code == "RULE_EFFECT_CONFLICT"
        else ()
    )
    opened = inferred_opened if opened_obligations is None else opened_obligations
    remaining = opened if remaining_obligations is None else remaining_obligations
    if outcome is None:
        if reason_code.endswith("_CANDIDATE"):
            resolved_outcome = "candidate_only"
        elif effect == "exclude":
            resolved_outcome = "engineering_profile_exclusion"
        elif effect == "retain":
            resolved_outcome = "retained_candidate"
        elif effect == "open":
            resolved_outcome = "obligation_open"
        else:
            resolved_outcome = "deferred_or_unresolved"
    else:
        resolved_outcome = outcome
    if node_role is None:
        if subject_id.startswith("hidden:"):
            resolved_role = "hidden_candidate"
        elif ":" in subject_id and any(
            marker in subject_id for marker in (":self", ":to-use", ":to-moving", ":cross-")
        ):
            resolved_role = "interaction_edge"
        else:
            resolved_role = "unassigned"
    else:
        resolved_role = node_role
    is_source_rule = source_key is not None
    if source_key is None:
        source_evidence: tuple[RuleSourceEvidence, ...] = ()
        resolved_source_level = "engineering_policy"
        resolved_source_refs: tuple[str, ...] = ()
    else:
        source_evidence = tuple(
            RuleSourceEvidence(
                source_ref=source_ref,
                source_family=VALIDITY_SOURCE_FAMILY_ID,
                source_level=source_level,
                topic_scope=evidence_scope,
                source_terms=evidence_terms,
            )
            for source_ref, source_level, evidence_scope, evidence_terms in (
                _RULE_SOURCE_EVIDENCE[source_key]
            )
        )
        evidence_levels = {item.source_level for item in source_evidence}
        resolved_source_level = (
            next(iter(evidence_levels))
            if len(evidence_levels) == 1
            else "per_reference"
        )
        resolved_source_refs = tuple(item.source_ref for item in source_evidence)
    return RuleHit(
        trace_id=f"{subject_id}:{rule_id}",
        rule_id=rule_id,
        priority_band=priority_band,
        priority=_PRIORITY[priority_band],
        subject_id=subject_id,
        effect=effect,
        reason_code=reason_code,
        policy_id=(VALIDITY_RULE_PROFILE_ID if is_source_rule else VALIDITY_ENGINEERING_POLICY_ID),
        priority_policy_id=VALIDITY_ENGINEERING_POLICY_ID,
        source_family=(VALIDITY_SOURCE_FAMILY_ID if is_source_rule else "engineering_policy"),
        source_level=resolved_source_level,
        source_refs=resolved_source_refs,
        source_evidence=source_evidence,
        topic_scope=topic_scope,
        node_role=resolved_role,
        opened_obligations=opened,
        discharged_obligations=discharged_obligations,
        remaining_obligations=remaining,
        outcome=resolved_outcome,
        normalized_relation=normalized_relation,
        source_terms=source_terms,
        conflict_group=conflict_group,
        technical=technical,
        plain=plain,
    )


def _focus_selection(record: LiuYaoCaseRecord, request: InterpretationRequest) -> FocusSelection:
    candidates = tuple(
        line.position for line in record.chart.lines if line.six_relation == request.use_relation
    )
    if request.primary_position is not None:
        line = record.chart.lines[request.primary_position - 1]
        if line.six_relation != request.use_relation:
            raise LiuYaoError(
                "USE_GOD_MISMATCH",
                f"第 {request.primary_position} 爻六亲为{line.six_relation}，与 use_relation={request.use_relation} 不一致",
            )
        return FocusSelection(
            relation=request.use_relation,
            status="confirmed",
            selected_position=request.primary_position,
            candidate_positions=candidates,
            reason="调用方已明确确认主用神爻位。",
        )
    if len(candidates) == 1:
        return FocusSelection(
            relation=request.use_relation,
            status="unique_candidate",
            selected_position=candidates[0],
            candidate_positions=candidates,
            reason="该六亲在本卦中只有一个可见候选。",
        )
    if not candidates:
        return FocusSelection(
            relation=request.use_relation,
            status="not_found",
            selected_position=None,
            candidate_positions=(),
            reason="本卦没有可见用神；伏神仍只登记为候选，不自动取用。",
        )
    return FocusSelection(
        relation=request.use_relation,
        status="ambiguous",
        selected_position=None,
        candidate_positions=candidates,
        reason="同一六亲存在多个候选，必须显式确认 primary_position。",
    )


def _node_state(obligations: list[str]) -> str:
    if set(obligations) & _UNKNOWN_OBLIGATIONS:
        return "unknown_context"
    if "RULE_EFFECT_CONFLICT" in obligations:
        return "unresolved"
    if set(obligations) & _DIRECTION_OPEN_OBLIGATIONS:
        return "unresolved"
    if obligations:
        return "conditional"
    return "available_candidate"


def _node_axes(
    *, obligations: list[str], state: str, selected_use: bool
) -> tuple[str, str, str, str]:
    structural_eligibility = "retained_candidate"
    current_force = {
        "unknown_context": "unknown_context",
        "unresolved": "unresolved",
        "conditional": "constrained",
        "available_candidate": "available_candidate",
    }[state]
    if state == "unknown_context":
        manifestation_state = "unknown_context"
    elif "RULE_EFFECT_CONFLICT" in obligations:
        manifestation_state = "unresolved"
    elif set(obligations) & _RELEASE_OBLIGATIONS:
        manifestation_state = "deferred"
    elif obligations:
        manifestation_state = "conditional"
    else:
        manifestation_state = "candidate"
    role_polarity = "selected_use" if selected_use else "unassigned"
    return (
        structural_eligibility,
        current_force,
        manifestation_state,
        role_polarity,
    )


def _evaluate_node(
    *,
    node_id: str,
    node_kind: str,
    position: int,
    branch: str,
    element: str,
    motion_kind: str,
    selected_use: bool,
    is_void: bool | None,
    advanced: AdvancedRuntimeReport,
    month_branch: str | None,
    day_branch: str | None,
) -> NodeValidity:
    obligations: list[str] = []
    relief: list[str] = []
    hits: list[RuleHit] = []
    confirmed = advanced.context_status.startswith("confirmed_")
    effective_is_void = is_void if confirmed else None
    month_relation: str | None = None
    day_relation: str | None = None
    month_growth: str | None = None
    day_growth: str | None = None

    if not confirmed:
        obligations.append("CALENDAR_PROVENANCE_UNCONFIRMED")
        hits.append(
            _hit(
                subject_id=node_id,
                rule_id="LYV-CALENDAR-PROVENANCE-001",
                priority_band="calendar_provenance_gate",
                effect="open",
                reason_code="CALENDAR_PROVENANCE_UNCONFIRMED",
                source_key=None,
                technical="月日上下文未通过第一批来源声明门禁。",
                plain="月日没有通过来源门禁，不能判断空破墓绝的作用资格。",
            )
        )
    else:
        if month_branch is None:
            obligations.append("CALENDAR_MONTH_MISSING")
            hits.append(
                _hit(
                    subject_id=node_id,
                    rule_id="LYV-CALENDAR-MONTH-MISSING-001",
                    priority_band="calendar_provenance_gate",
                    effect="open",
                    reason_code="CALENDAR_MONTH_MISSING",
                    source_key=None,
                    technical="来源门禁已确认，但月建字段缺失。",
                    plain="缺月建时，依赖月支的空破墓绝条件不能闭合。",
                )
            )
        else:
            month_relation = classify_branch_relation(month_branch, branch)
            month_growth = growth_stage(element, month_branch)
            if month_relation == "clash":
                obligations.append("MONTH_BREAK_OPEN")
                relief.extend(
                    (
                        "OUT_OF_MONTH_CANDIDATE",
                        "MONTH_BREAK_FILL_CANDIDATE",
                        "MONTH_BREAK_COMBINE_CANDIDATE",
                    )
                )
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-MONTH-BREAK-001",
                        priority_band="node_validity",
                        effect="open",
                        reason_code="MONTH_BREAK_OPEN",
                        source_key="month_break",
                        technical=f"{node_id} 地支{branch}受月支{month_branch}六冲，登记月破条件。",
                        plain="月破先作为当前约束，不扩大成永久无效。",
                    )
                )
                for rule_id, reason_code, plain in (
                    (
                        "LYV-MONTH-BREAK-OUT-OF-MONTH-CANDIDATE-001",
                        "OUT_OF_MONTH_CANDIDATE",
                        "出月只是月破解除候选，届时仍须重算其他条件。",
                    ),
                    (
                        "LYV-MONTH-BREAK-FILL-CANDIDATE-001",
                        "MONTH_BREAK_FILL_CANDIDATE",
                        "填实只是月破解除候选，不能清除其他义务。",
                    ),
                    (
                        "LYV-MONTH-BREAK-COMBINE-CANDIDATE-001",
                        "MONTH_BREAK_COMBINE_CANDIDATE",
                        "逢合只是月破解除候选，不能直接判为恢复。",
                    ),
                ):
                    hits.append(
                        _hit(
                            subject_id=node_id,
                            rule_id=rule_id,
                            priority_band="node_validity",
                            effect="defer",
                            reason_code=reason_code,
                            source_key="month_break",
                            remaining_obligations=("MONTH_BREAK_OPEN",),
                            technical=f"{node_id} 的月破登记条件性解除候选 {reason_code}。",
                            plain=plain,
                        )
                    )
            elif month_relation == "combine":
                obligations.append("MONTH_COMBINE_EFFECT_OPEN")
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-MONTH-COMBINE-DIRECTION-OPEN-001",
                        priority_band="node_validity",
                        effect="open",
                        reason_code="MONTH_COMBINE_EFFECT_OPEN",
                        source_key=None,
                        topic_scope="atomic_relation_observed_direction_unresolved",
                        technical=f"{node_id} 地支{branch}与月支{month_branch}六合。",
                        plain="这里只登记六合事实；合起、合绊等方向尚未闭合。",
                    )
                )
            if month_growth == "墓":
                obligations.append("MONTH_TOMB_EFFECT_OPEN")
                relief.append("STORAGE_RELEASE_BY_CLASH_CANDIDATE")
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-MONTH-TOMB-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="MONTH_TOMB_EFFECT_OPEN",
                        source_key="tomb",
                        normalized_relation="storage_constraint",
                        source_terms=("墓", "库", "入库"),
                        technical=f"{node_id} 的{element}在月支{month_branch}处于墓阶段。",
                        plain="入墓需要再看旺衰、扶助和冲库，不能单独判无力。",
                    )
                )
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-MONTH-STORAGE-RELEASE-POSSIBILITY-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="STORAGE_RELEASE_BY_CLASH_CANDIDATE",
                        source_key="storage_release",
                        remaining_obligations=("MONTH_TOMB_EFFECT_OPEN",),
                        normalized_relation="storage_release_by_clash",
                        source_terms=("冲库", "冲开库", "库之破"),
                        technical="月墓条件登记未来冲库解除候选，当前并未视为已解除。",
                        plain="冲库仍需具体冲关系，候选不会自动清除月墓义务。",
                    )
                )
            elif month_growth == "绝":
                obligations.append("MONTH_ABSOLUTE_EFFECT_OPEN")
                relief.append("GROWTH_RECOVERY_CANDIDATE")
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-MONTH-ABSOLUTE-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="MONTH_ABSOLUTE_EFFECT_OPEN",
                        source_key="absolute",
                        technical=f"{node_id} 的{element}在月支{month_branch}处于绝阶段。",
                        plain="绝处仍可能遇生扶；这里只登记当前力量未决，不删除结构节点。",
                    )
                )
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-MONTH-ABSOLUTE-RECOVERY-CANDIDATE-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="GROWTH_RECOVERY_CANDIDATE",
                        source_key="absolute",
                        remaining_obligations=("MONTH_ABSOLUTE_EFFECT_OPEN",),
                        technical="月绝条件登记逢生扶恢复候选。",
                        plain="逢生只是候选，月绝义务仍保持开放。",
                    )
                )
        if day_branch is None:
            obligations.append("CALENDAR_DAY_MISSING")
            hits.append(
                _hit(
                    subject_id=node_id,
                    rule_id="LYV-CALENDAR-DAY-MISSING-001",
                    priority_band="calendar_provenance_gate",
                    effect="open",
                    reason_code="CALENDAR_DAY_MISSING",
                    source_key=None,
                    technical="来源门禁已确认，但日柱字段缺失。",
                    plain="缺日柱时，旬空和依赖日支的条件不能闭合。",
                )
            )
        else:
            day_relation = classify_branch_relation(day_branch, branch)
            day_growth = growth_stage(element, day_branch)
            if day_relation == "clash":
                obligations.append("DAY_CLASH_EFFECT_OPEN")
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-DAY-CLASH-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="DAY_CLASH_EFFECT_OPEN",
                        source_key="day_clash",
                        technical=f"{node_id} 地支{branch}受日支{day_branch}六冲。",
                        plain="日冲须再判旺静、暗动或日破，当前不能直接归为有效或无用。",
                    )
                )
                if effective_is_void:
                    relief.append("VOID_CLASH_CANDIDATE")
                    hits.append(
                        _hit(
                            subject_id=node_id,
                            rule_id="LYV-VOID-CLASH-001",
                            priority_band="node_validity",
                            effect="defer",
                            reason_code="VOID_CLASH_CANDIDATE",
                            source_key="void_clash",
                            remaining_obligations=("VOID_EFFECT_OPEN",),
                            technical=f"{node_id} 旬空且受日支{day_branch}冲，登记冲空候选。",
                            plain="冲空只是解除候选，不能顺手清除月破、墓绝或其他条件。",
                        )
                    )
            elif day_relation == "combine":
                obligations.append("DAY_COMBINE_EFFECT_OPEN")
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-DAY-COMBINE-DIRECTION-OPEN-001",
                        priority_band="node_validity",
                        effect="open",
                        reason_code="DAY_COMBINE_EFFECT_OPEN",
                        source_key=None,
                        topic_scope="atomic_relation_observed_direction_unresolved",
                        technical=f"{node_id} 地支{branch}与日支{day_branch}六合。",
                        plain="这里只登记六合事实；合起、合绊等方向尚未闭合。",
                    )
                )
            elif day_relation == "same" and effective_is_void:
                relief.append("VOID_FILL_CANDIDATE")
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-VOID-FILL-CANDIDATE-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="VOID_FILL_CANDIDATE",
                        source_key="void_fill",
                        remaining_obligations=("VOID_EFFECT_OPEN",),
                        technical=f"{node_id} 旬空且地支与日支{day_branch}相同，登记填实候选。",
                        plain="填实候选只针对旬空，不能清除月破、墓绝等义务。",
                    )
                )
            if day_relation == "same" and "MONTH_BREAK_OPEN" in obligations:
                relief.append("MONTH_BREAK_FILL_BY_DAY_CANDIDATE")
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-MONTH-BREAK-FILL-BY-DAY-CANDIDATE-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="MONTH_BREAK_FILL_BY_DAY_CANDIDATE",
                        source_key="month_break",
                        remaining_obligations=("MONTH_BREAK_OPEN",),
                        technical=f"{node_id} 月破且受日支{day_branch}填实，登记解除候选。",
                        plain="日填月破只是候选，仍须重算旺衰和其他义务。",
                    )
                )
            if day_growth == "墓":
                obligations.append("DAY_TOMB_EFFECT_OPEN")
                relief.append("STORAGE_RELEASE_BY_CLASH_CANDIDATE")
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-DAY-TOMB-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="DAY_TOMB_EFFECT_OPEN",
                        source_key="tomb",
                        normalized_relation="storage_constraint",
                        source_terms=("墓", "库", "入库"),
                        technical=f"{node_id} 的{element}在日支{day_branch}处于墓阶段。",
                        plain="原书可靠用词是墓、库与冲库；当前只挂起条件义务。",
                    )
                )
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-DAY-STORAGE-RELEASE-POSSIBILITY-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="STORAGE_RELEASE_BY_CLASH_CANDIDATE",
                        source_key="storage_release",
                        remaining_obligations=("DAY_TOMB_EFFECT_OPEN",),
                        normalized_relation="storage_release_by_clash",
                        source_terms=("冲库", "冲开库", "库之破"),
                        technical="日墓条件登记未来冲库解除候选，当前并未视为已解除。",
                        plain="冲库仍需具体冲关系，候选不会自动清除日墓义务。",
                    )
                )
            elif day_growth == "绝":
                obligations.append("DAY_ABSOLUTE_EFFECT_OPEN")
                relief.append("GROWTH_RECOVERY_CANDIDATE")
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-DAY-ABSOLUTE-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="DAY_ABSOLUTE_EFFECT_OPEN",
                        source_key="absolute",
                        technical=f"{node_id} 的{element}在日支{day_branch}处于绝阶段。",
                        plain="绝不是终局失效；动爻生扶等救应尚未闭合，保持未决。",
                    )
                )
                hits.append(
                    _hit(
                        subject_id=node_id,
                        rule_id="LYV-DAY-ABSOLUTE-RECOVERY-CANDIDATE-001",
                        priority_band="node_validity",
                        effect="defer",
                        reason_code="GROWTH_RECOVERY_CANDIDATE",
                        source_key="absolute",
                        remaining_obligations=("DAY_ABSOLUTE_EFFECT_OPEN",),
                        technical="日绝条件登记逢生扶恢复候选。",
                        plain="逢生只是候选，日绝义务仍保持开放。",
                    )
                )

    if effective_is_void:
        obligations.append("VOID_EFFECT_OPEN")
        hits.append(
            _hit(
                subject_id=node_id,
                rule_id="LYV-VOID-001",
                priority_band="node_validity",
                effect="open",
                reason_code="VOID_EFFECT_OPEN",
                source_key="void",
                technical=f"{node_id} 地支{branch}落入旬空。",
                plain="旬空先登记条件义务；旺、动、冲、填实等说法尚需分别核对。",
            )
        )
        if motion_kind == "moving":
            obligations.append("RULE_EFFECT_CONFLICT")
            relief.append("MOVING_VOID_EXCEPTION_DISPUTED")
            hits.append(
                _hit(
                    subject_id=node_id,
                    rule_id="LYV-VOID-MOVING-CONFLICT-001",
                    priority_band="node_validity",
                    effect="defer",
                    reason_code="RULE_EFFECT_CONFLICT",
                    source_key="void_moving_conflict",
                    topic_scope="scope_unresolved_not_global_override",
                    conflict_group="void_effect",
                    remaining_obligations=("VOID_EFFECT_OPEN", "RULE_EFFECT_CONFLICT"),
                    technical="同一来源谱系同时出现动空不空与空待冲填等条件说法。",
                    plain="发动不能自动把旬空改成有效；这里保留原书内部条件冲突。",
                )
            )
            hits.append(
                _hit(
                    subject_id=node_id,
                    rule_id="LYV-MOVING-VOID-EXCEPTION-CANDIDATE-001",
                    priority_band="node_validity",
                    effect="defer",
                    reason_code="MOVING_VOID_EXCEPTION_DISPUTED",
                    source_key="void_moving_conflict",
                    topic_scope="scope_unresolved_not_global_override",
                    remaining_obligations=("VOID_EFFECT_OPEN", "RULE_EFFECT_CONFLICT"),
                    outcome="candidate_only_disputed",
                    technical="发动逢空的例外说法仅登记争议候选。",
                    plain="发动不能自动清除旬空；争议候选与冲突义务同时保留。",
                )
            )

    if (
        month_growth == "墓"
        and month_branch is not None
        and day_branch is not None
        and classify_branch_relation(month_branch, day_branch) == "clash"
    ) or (
        day_growth == "墓"
        and month_branch is not None
        and day_branch is not None
        and classify_branch_relation(month_branch, day_branch) == "clash"
    ):
        relief.append("TOMB_RELEASE_CANDIDATE")
        storage_obligations = tuple(
            code
            for code in ("MONTH_TOMB_EFFECT_OPEN", "DAY_TOMB_EFFECT_OPEN")
            if code in obligations
        )
        hits.append(
            _hit(
                subject_id=node_id,
                rule_id="LYV-TOMB-RELEASE-001",
                priority_band="node_validity",
                effect="defer",
                reason_code="TOMB_RELEASE_CANDIDATE",
                source_key="storage_release",
                remaining_obligations=storage_obligations,
                normalized_relation="storage_release_by_clash",
                source_terms=("冲库", "冲开库", "库之破"),
                technical="墓/库条件同时遇到月日相冲，登记冲库候选。",
                plain="冲库只是条件变化，不自动等于恢复旺相或事情能成。",
            )
        )

    obligations = list(dict.fromkeys(obligations))
    relief = list(dict.fromkeys(relief))
    state = _node_state(obligations)
    structural, current_force, manifestation, role_polarity = _node_axes(
        obligations=obligations,
        state=state,
        selected_use=selected_use,
    )
    hit_role = (
        "selected_use"
        if selected_use
        else "hidden_candidate"
        if node_kind == "hidden"
        else "unassigned"
    )
    hits = [replace(hit, node_role=hit_role) for hit in hits]
    return NodeValidity(
        node_id=node_id,
        node_kind=node_kind,
        position=position,
        branch=branch,
        element=element,
        motion_kind=motion_kind,
        selected_use=selected_use,
        structural_eligibility=structural,
        current_force=current_force,
        manifestation_state=manifestation,
        role_polarity=role_polarity,
        state=state,
        open_obligations=tuple(obligations),
        relief_candidates=tuple(relief),
        month_relation=month_relation,
        day_relation=day_relation,
        month_growth_stage=month_growth,
        day_growth_stage=day_growth,
        rule_hits=tuple(hits),
    )


def _node_conflicts(nodes: tuple[NodeValidity, ...]) -> list[ValidityConflict]:
    conflicts: list[ValidityConflict] = []
    effect_codes = _RELEASE_OBLIGATIONS | _DIRECTION_OPEN_OBLIGATIONS
    for node in nodes:
        active_effects = tuple(code for code in node.open_obligations if code in effect_codes)
        if len(active_effects) >= 2:
            conflicts.append(
                ValidityConflict(
                    conflict_id=f"node:{node.node_id}:multiple-effects",
                    code="MULTIPLE_EFFECT_CONSTRAINTS",
                    subjects=(node.node_id,),
                    severity="medium",
                    resolution="unresolved",
                    rule_ids=tuple(hit.rule_id for hit in node.rule_hits),
                    technical=f"{node.node_id} 同时存在：{', '.join(active_effects)}。",
                    plain="多个条件同时存在，任何单一解除候选都不能把其他条件一并清除。",
                )
            )
        if {"VOID_EFFECT_OPEN", "MONTH_BREAK_OPEN"}.issubset(node.open_obligations):
            conflicts.append(
                ValidityConflict(
                    conflict_id=f"node:{node.node_id}:void-month-break",
                    code="VOID_AND_MONTH_BREAK",
                    subjects=(node.node_id,),
                    severity="high",
                    resolution="unresolved",
                    rule_ids=("LYV-VOID-001", "LYV-MONTH-BREAK-001"),
                    technical=f"{node.node_id} 同时旬空与月破。",
                    plain="空与破分别保留，发动、填实或逢合不能自动同时解除两项。",
                )
            )
        if "RULE_EFFECT_CONFLICT" in node.open_obligations:
            conflicts.append(
                ValidityConflict(
                    conflict_id=f"node:{node.node_id}:source-rule-conflict",
                    code="AUTHOR_INTERNAL_CONFLICT",
                    subjects=(node.node_id,),
                    severity="high",
                    resolution="unresolved",
                    rule_ids=tuple(
                        hit.rule_id for hit in node.rule_hits if hit.conflict_group is not None
                    ),
                    technical="同一来源谱系对当前条件给出不能直接合并的说法。",
                    plain="这里不按加载顺序或分数强行选一条，保持未决。",
                )
            )
    return conflicts


def _hidden_validity(
    record: LiuYaoCaseRecord,
    advanced: AdvancedRuntimeReport,
    nodes_by_id: Mapping[str, NodeValidity],
    *,
    month_branch: str | None,
    day_branch: str | None,
) -> tuple[tuple[HiddenValidity, ...], list[ValidityConflict]]:
    results: list[HiddenValidity] = []
    conflicts: list[ValidityConflict] = []
    for fact in advanced.facts:
        if fact.category != "hidden_spirit" or len(fact.positions) != 1:
            continue
        position = fact.positions[0]
        hidden_branch, _flying_branch = fact.branches
        hidden_element, flying_element = fact.elements
        hidden_node_id = f"hidden:{fact.relation}:{position}"
        hidden_node = _evaluate_node(
            node_id=hidden_node_id,
            node_kind="hidden",
            position=position,
            branch=hidden_branch,
            element=hidden_element,
            motion_kind="hidden",
            selected_use=False,
            is_void=(
                None
                if record.chart.void_branches is None
                else hidden_branch in record.chart.void_branches
            ),
            advanced=advanced,
            month_branch=month_branch,
            day_branch=day_branch,
        )
        flying_node_id = f"original:{position}"
        flying = nodes_by_id[flying_node_id]
        flying_to_hidden = classify_element_relation(flying_element, hidden_element)
        hidden_to_flying = classify_element_relation(hidden_element, flying_element)
        obligations = ["HIDDEN_ACTIVATION_OPEN"]
        release_candidates: list[str] = []
        hits: list[RuleHit] = [
            _hit(
                subject_id=hidden_node_id,
                rule_id="LYV-HIDDEN-CANDIDATE-001",
                priority_band="hidden_self_gate",
                effect="open",
                reason_code="HIDDEN_ACTIVATION_OPEN",
                source_key="flying_hidden",
                technical=f"本卦缺{fact.relation}，第{position}爻登记伏神候选。",
                plain="伏神只进入候选流程，不自动成为用神或出伏。",
            )
        ]

        flying_release = tuple(
            code for code in flying.open_obligations if code in _RELEASE_OBLIGATIONS
        )
        if flying_release:
            release_candidates.extend(f"FLYING_{code}" for code in flying_release)
            for flying_code in flying_release:
                hits.append(
                    _hit(
                        subject_id=hidden_node_id,
                        rule_id=f"LYV-FLYING-{flying_code}-RELEASE-CANDIDATE-001",
                        priority_band="hidden_self_gate",
                        effect="defer",
                        reason_code=f"FLYING_{flying_code}",
                        source_key="flying_hidden",
                        opened_obligations=(),
                        remaining_obligations=("HIDDEN_ACTIVATION_OPEN",),
                        topic_scope="scope_unresolved_no_deterministic_outcome",
                        outcome="candidate_only",
                        technical=f"同位飞神存在释放候选条件：{flying_code}。",
                        plain="飞神空破墓绝只使伏神较易显露，不能推出必出或事情必成。",
                    )
                )

        hidden_self_open = tuple(
            code
            for code in hidden_node.open_obligations
            if code not in _UNKNOWN_OBLIGATIONS
        )
        if hidden_self_open:
            obligations.append("HIDDEN_SELF_VALIDITY_OPEN")
            hits.append(
                _hit(
                    subject_id=hidden_node_id,
                    rule_id="LYV-HIDDEN-SELF-VALIDITY-GATE-001",
                    priority_band="hidden_self_gate",
                    effect="open",
                    reason_code="HIDDEN_SELF_VALIDITY_OPEN",
                    source_key=None,
                    remaining_obligations=(
                        "HIDDEN_ACTIVATION_OPEN",
                        "HIDDEN_SELF_VALIDITY_OPEN",
                    ),
                    technical=f"伏神自身仍有开放义务：{', '.join(hidden_self_open)}。",
                    plain="伏神自身条件先于飞神释放候选，不能跨过该门禁。",
                )
            )
        if flying_to_hidden == "generates":
            release_candidates.append("FLYING_GENERATES_HIDDEN_CANDIDATE")
            hits.append(
                _hit(
                    subject_id=hidden_node_id,
                    rule_id="LYV-FLYING-GENERATES-HIDDEN-CANDIDATE-001",
                    priority_band="hidden_self_gate",
                    effect="defer",
                    reason_code="FLYING_GENERATES_HIDDEN_CANDIDATE",
                    source_key="flying_hidden",
                    remaining_obligations=("HIDDEN_ACTIVATION_OPEN",),
                    normalized_relation="flying_generates_hidden",
                    plain="飞生伏只登记显露候选，不自动出伏。",
                    technical="同位飞神五行生伏神五行，登记有向候选关系。",
                )
            )
        elif flying_to_hidden == "controls":
            obligations.append("FLYING_CONTROLS_HIDDEN_OPEN")
            hits.append(
                _hit(
                    subject_id=hidden_node_id,
                    rule_id="LYV-FLYING-CONTROLS-HIDDEN-OPEN-001",
                    priority_band="hidden_self_gate",
                    effect="open",
                    reason_code="FLYING_CONTROLS_HIDDEN_OPEN",
                    source_key="flying_hidden",
                    normalized_relation="flying_controls_hidden",
                    plain="飞克伏保持为开放约束，不直接裁掉伏神。",
                    technical="同位飞神五行克伏神五行，方向效果尚未闭合。",
                )
            )
        elif hidden_to_flying == "generates":
            obligations.append("HIDDEN_DRAINS_TO_FLYING_OPEN")
            hits.append(
                _hit(
                    subject_id=hidden_node_id,
                    rule_id="LYV-HIDDEN-DRAINS-TO-FLYING-OPEN-001",
                    priority_band="hidden_self_gate",
                    effect="open",
                    reason_code="HIDDEN_DRAINS_TO_FLYING_OPEN",
                    source_key="flying_hidden",
                    normalized_relation="hidden_generates_flying",
                    plain="伏生飞保持为开放约束，不直接翻译成吉凶。",
                    technical="伏神五行生同位飞神五行，方向效果尚未闭合。",
                )
            )
        elif hidden_to_flying == "controls":
            obligations.append("RULE_EFFECT_CONFLICT")
            hits.append(
                _hit(
                    subject_id=hidden_node_id,
                    rule_id="LYV-HIDDEN-CONTROLS-FLYING-CONFLICT-001",
                    priority_band="hidden_self_gate",
                    effect="defer",
                    reason_code="RULE_EFFECT_CONFLICT",
                    source_key="hidden_control_conflict",
                    conflict_group="hidden_controls_flying",
                    technical="同章对伏来克飞出现出暴与无事两种表述。",
                    plain="伏克飞只保留关系标签，不强行转成吉凶或必然出伏。",
                )
            )

        obligations = list(dict.fromkeys(obligations))
        release_candidates = list(dict.fromkeys(release_candidates))
        if "unknown_context" in {hidden_node.state, flying.state}:
            activation_state = "unknown_context"
        elif "RULE_EFFECT_CONFLICT" in obligations or (
            release_candidates and "HIDDEN_SELF_VALIDITY_OPEN" in obligations
        ):
            activation_state = "unresolved"
        else:
            activation_state = "conditional"

        result = HiddenValidity(
            hidden_node=hidden_node,
            relation=fact.relation,
            flying_node_id=flying_node_id,
            flying_state=flying.state,
            flying_to_hidden=flying_to_hidden,
            hidden_to_flying=hidden_to_flying,
            visibility_state="hidden_candidate",
            activation_state=activation_state,
            open_obligations=tuple(obligations),
            release_candidates=tuple(release_candidates),
            rule_hits=tuple(hits),
        )
        results.append(result)
        if release_candidates and "HIDDEN_SELF_VALIDITY_OPEN" in obligations:
            conflicts.append(
                ValidityConflict(
                    conflict_id=f"hidden:{fact.relation}:{position}:release-self-conflict",
                    code="HIDDEN_RELEASE_AND_SELF_CONSTRAINT",
                    subjects=(hidden_node_id, flying_node_id),
                    severity="high",
                    resolution="unresolved",
                    rule_ids=tuple(hit.rule_id for hit in hits),
                    technical="飞神释放候选与伏神自身约束同时存在。",
                    plain="先看伏神自身能否承受，再谈飞神是否让它显露；两者不能混成一条。",
                )
            )
        if "RULE_EFFECT_CONFLICT" in obligations:
            conflicts.append(
                ValidityConflict(
                    conflict_id=f"hidden:{fact.relation}:{position}:author-conflict",
                    code="AUTHOR_INTERNAL_CONFLICT",
                    subjects=(hidden_node_id, flying_node_id),
                    severity="high",
                    resolution="unresolved",
                    rule_ids=("LYV-HIDDEN-CONTROLS-FLYING-CONFLICT-001",),
                    technical="伏来克飞的同章解释发生语义冲突。",
                    plain="该关系不参与确定性方向裁决。",
                )
            )
    return (
        tuple(sorted(results, key=lambda item: (item.relation, item.hidden_node.position))),
        conflicts,
    )


def _edge_direction(relation: str) -> str:
    return {
        "generates": "supportive",
        "controls": "restrictive",
        "generated_by": "draining",
        "controlled_by": "contained",
        "same_element": "peer",
    }[relation]


def _make_edge(
    *,
    edge_id: str,
    source: NodeValidity,
    target: NodeValidity,
    edge_kind: str,
    priority_band: str,
    pruned: bool = False,
    prune_reason: str | None = None,
) -> InteractionEdge:
    relation = classify_element_relation(source.element, target.element)
    endpoint_obligations = tuple(
        dict.fromkeys(source.open_obligations + target.open_obligations)
    )
    if pruned:
        status = "pruned"
        effect = "exclude"
        reason_code = prune_reason or "PATH_PROFILE_EXCLUDED"
    elif "unknown_context" in {source.state, target.state}:
        status = "deferred"
        effect = "defer"
        reason_code = "PATH_ENDPOINT_UNKNOWN"
    elif source.state != "available_candidate" or target.state != "available_candidate":
        status = "deferred"
        effect = "defer"
        reason_code = "PATH_ENDPOINT_CONDITIONAL"
    else:
        status = "active_candidate"
        effect = "retain"
        reason_code = "PATH_ENDPOINTS_AVAILABLE"
    hits: list[RuleHit] = []
    if edge_kind == "changed_to_same_original":
        hits.append(
            _hit(
                subject_id=edge_id,
                rule_id="LYV-CHANGED-SAME-POSITION-SOURCE-SCOPE-001",
                priority_band=priority_band,
                effect="retain",
                reason_code="CHANGED_SAME_POSITION_SCOPE_CANDIDATE",
                source_key="changed_scope",
                topic_scope="original_changed_same_position",
                outcome="source_scope_candidate",
                technical="来源规则只支持变爻回头作用本位原爻。",
                plain="同位关系通过来源适用范围，实际边状态仍由工程端点门禁决定。",
            )
        )
    elif edge_kind == "changed_cross_position":
        hits.append(
            _hit(
                subject_id=edge_id,
                rule_id="LYV-CHANGED-CROSS-POSITION-SOURCE-SCOPE-001",
                priority_band=priority_band,
                effect="defer",
                reason_code="CHANGED_CROSS_POSITION_OUT_OF_SOURCE_SCOPE",
                source_key="changed_scope",
                topic_scope="original_changed_same_position",
                outcome="source_scope_exclusion",
                technical="来源规则只支持变爻回头作用本位原爻，未支持跨位作用。",
                plain="跨位关系超出当前来源适用范围；工程排除另有独立收据。",
            )
        )
    hits.append(
        _hit(
            subject_id=edge_id,
            rule_id=(
                "LYV-CHANGED-CROSS-POSITION-ENFORCEMENT-001"
                if pruned
                else "LYV-PATH-ENDPOINT-GATE-001"
            ),
            priority_band=priority_band,
            effect=effect,
            reason_code=reason_code,
            source_key=None,
            remaining_obligations=(
                endpoint_obligations if status == "deferred" else ()
            ),
            technical=(
                "工程 policy 根据来源适用范围排除跨位变爻边。"
                if pruned
                else f"边的两端状态为 {source.state}/{target.state}。"
            ),
            plain=(
                "跨位边不进入候选图；来源范围和工程执行分别留有收据。"
                if pruned
                else "只有两端通过当前门禁，关系边才进入活动候选。"
            ),
        )
    )
    return InteractionEdge(
        edge_id=edge_id,
        source_node_id=source.node_id,
        target_node_id=target.node_id,
        edge_kind=edge_kind,
        relation=relation,
        direction=_edge_direction(relation),
        priority_band=priority_band,
        source_state=source.state,
        target_state=target.state,
        status=status,
        prune_reason=prune_reason,
        rule_hits=tuple(hits),
    )


def _build_edges(
    record: LiuYaoCaseRecord,
    nodes_by_id: Mapping[str, NodeValidity],
    selection: FocusSelection,
) -> tuple[InteractionEdge, ...]:
    edges: list[InteractionEdge] = []
    selected_id = (
        None
        if selection.selected_position is None
        else f"original:{selection.selected_position}"
    )
    selected = None if selected_id is None else nodes_by_id[selected_id]

    changed_nodes = tuple(
        node for node in nodes_by_id.values() if node.node_kind == "changed"
    )
    for changed in changed_nodes:
        original = nodes_by_id[f"original:{changed.position}"]
        edges.append(
            _make_edge(
                edge_id=f"changed:{changed.position}:self",
                source=changed,
                target=original,
                edge_kind="changed_to_same_original",
                priority_band="same_position_change",
            )
        )
        if selected is not None and selected.position != changed.position:
            edges.append(
                _make_edge(
                    edge_id=f"changed:{changed.position}:cross-to-use:{selected.position}",
                    source=changed,
                    target=selected,
                    edge_kind="changed_cross_position",
                    priority_band="same_position_change",
                    pruned=True,
                    prune_reason="CHANGED_CROSS_POSITION_EXCLUDED",
                )
            )

    moving_originals = tuple(
        nodes_by_id[f"original:{line.position}"]
        for line in record.chart.lines
        if line.moving
    )
    actors = tuple(
        node for node in moving_originals if selected is None or node.node_id != selected.node_id
    )
    if selected is not None:
        for actor in actors:
            edges.append(
                _make_edge(
                    edge_id=f"moving:{actor.position}:to-use:{selected.position}",
                    source=actor,
                    target=selected,
                    edge_kind="moving_to_selected_use",
                    priority_band="direct_moving_to_use",
                )
            )
    for source in actors:
        for target in actors:
            if source.node_id == target.node_id:
                continue
            edges.append(
                _make_edge(
                    edge_id=f"moving:{source.position}:to-moving:{target.position}",
                    source=source,
                    target=target,
                    edge_kind="moving_pair_candidate",
                    priority_band="indirect_moving_path",
                )
            )
    unique = {edge.edge_id: edge for edge in edges}
    return tuple(unique[key] for key in sorted(unique))


def _enumerate_paths(
    edges: tuple[InteractionEdge, ...],
    nodes: tuple[NodeValidity, ...],
    selection: FocusSelection,
) -> tuple[tuple[InfluencePath, ...], bool]:
    if selection.selected_position is None:
        return (), False
    target_id = f"original:{selection.selected_position}"
    usable = tuple(edge for edge in edges if edge.status != "pruned")
    by_id = {edge.edge_id: edge for edge in usable}
    adjacency: dict[str, list[InteractionEdge]] = {}
    for edge in usable:
        adjacency.setdefault(edge.source_node_id, []).append(edge)
    for values in adjacency.values():
        values.sort(key=lambda item: item.edge_id)
    starts = tuple(
        sorted(
            node.node_id
            for node in nodes
            if node.node_id != target_id
            and (node.motion_kind == "moving" or node.node_kind == "changed")
        )
    )
    raw: set[tuple[str, str, tuple[str, ...], str, str | None]] = set()
    limit_reached = False

    def add(
        source_id: str,
        terminal_id: str,
        edge_ids: tuple[str, ...],
        enumeration_status: str,
        reason: str | None,
    ) -> None:
        nonlocal limit_reached
        if len(raw) >= _MAX_PATHS:
            limit_reached = True
            return
        raw.add((source_id, terminal_id, edge_ids, enumeration_status, reason))

    def walk(
        source_id: str,
        current_id: str,
        edge_ids: tuple[str, ...],
        visited: frozenset[str],
    ) -> None:
        outgoing = adjacency.get(current_id, [])
        if not outgoing and edge_ids:
            add(
                source_id,
                current_id,
                edge_ids,
                "profile_excluded",
                "PATH_NOT_FOCUS_RELEVANT",
            )
            return
        for edge in outgoing:
            next_id = edge.target_node_id
            next_edges = edge_ids + (edge.edge_id,)
            if next_id in visited:
                add(
                    source_id,
                    next_id,
                    next_edges,
                    "profile_excluded",
                    "PATH_CYCLE_PRUNED",
                )
                continue
            if len(next_edges) > _MAX_PATH_HOPS:
                add(
                    source_id,
                    next_id,
                    next_edges,
                    "profile_excluded",
                    "PATH_LENGTH_LIMIT",
                )
                continue
            if next_id == target_id:
                add(source_id, next_id, next_edges, "retained", None)
                continue
            if len(next_edges) >= _MAX_PATH_HOPS:
                add(
                    source_id,
                    next_id,
                    next_edges,
                    "profile_excluded",
                    "PATH_LENGTH_LIMIT",
                )
                continue
            walk(source_id, next_id, next_edges, visited | {next_id})

    for start in starts:
        walk(start, start, (), frozenset({start}))
        if limit_reached:
            break

    paths: list[InfluencePath] = []
    for index, (
        source_id,
        terminal_id,
        edge_ids,
        enumeration_status,
        reason,
    ) in enumerate(
        sorted(raw), start=1
    ):
        statuses = {by_id[item].status for item in edge_ids}
        validity_status = (
            "active_candidate" if statuses == {"active_candidate"} else "deferred"
        )
        if edge_ids:
            last = by_id[edge_ids[-1]]
            direction = last.direction if len(edge_ids) == 1 else f"indirect_{last.direction}"
        else:
            direction = "unresolved"
        paths.append(
            InfluencePath(
                path_id=f"path:{index:03d}",
                source_node_id=source_id,
                target_node_id=terminal_id,
                edge_ids=edge_ids,
                validity_status=validity_status,
                enumeration_status=enumeration_status,
                direction=direction,
                candidate_graph_reaches_focus=(
                    enumeration_status == "retained"
                    and validity_status == "active_candidate"
                    and terminal_id == target_id
                ),
                enumeration_reason=reason,
            )
        )
    return tuple(paths), limit_reached


def _path_conflicts(
    paths: tuple[InfluencePath, ...],
    *,
    limit_reached: bool,
) -> list[ValidityConflict]:
    conflicts: list[ValidityConflict] = []
    opposing_candidates = tuple(
        path
        for path in paths
        if path.enumeration_status == "retained"
        and path.validity_status == "active_candidate"
        and path.candidate_graph_reaches_focus
        and len(path.edge_ids) == 1
        and path.direction in {"supportive", "restrictive"}
    )
    directions = {path.direction for path in opposing_candidates}
    if "supportive" in directions and "restrictive" in directions:
        conflicts.append(
            ValidityConflict(
                conflict_id="path:opposing-direct-effects",
                code="OPPOSING_DIRECT_PATHS",
                subjects=tuple(path.path_id for path in opposing_candidates),
                severity="high",
                resolution="unresolved",
                rule_ids=("LYV-PATH-ENDPOINT-GATE-001",),
                technical="工程候选图中，到用神的活动直接路径同时存在生与克。",
                plain="直接候选方向相反，不能用条数或加载顺序强行决胜。",
            )
        )
    if any(path.enumeration_reason == "PATH_CYCLE_PRUNED" for path in paths):
        conflicts.append(
            ValidityConflict(
                conflict_id="path:cycle-pruned",
                code="PATH_CYCLE_PRUNED",
                subjects=tuple(
                    path.path_id
                    for path in paths
                    if path.enumeration_reason == "PATH_CYCLE_PRUNED"
                ),
                severity="low",
                resolution="profile_exclusion",
                rule_ids=("LYV-PATH-ENDPOINT-GATE-001",),
                technical="简单路径枚举发现循环，循环路径不进入聚焦候选。",
                plain="循环没有被删除，已作为裁剪记录保留。",
            )
        )
    if any(path.enumeration_reason == "PATH_LENGTH_LIMIT" for path in paths):
        conflicts.append(
            ValidityConflict(
                conflict_id="path:length-limit",
                code="PATH_LENGTH_LIMIT",
                subjects=tuple(
                    path.path_id
                    for path in paths
                    if path.enumeration_reason == "PATH_LENGTH_LIMIT"
                ),
                severity="low",
                resolution="profile_exclusion",
                rule_ids=("LYV-PATH-ENDPOINT-GATE-001",),
                technical=f"当前工程 policy 最多枚举 {_MAX_PATH_HOPS} 条边。",
                plain="过长链条只从聚焦图裁剪，不等于传统上永久无效。",
            )
        )
    if limit_reached:
        conflicts.append(
            ValidityConflict(
                conflict_id="path:enumeration-limit",
                code="PATH_ENUMERATION_LIMIT",
                subjects=(),
                severity="high",
                resolution="unresolved",
                rule_ids=("LYV-PATH-ENDPOINT-GATE-001",),
                technical=f"路径数量达到 {_MAX_PATHS} 条上限。",
                plain="系统停止继续展开，不把截断后的结果说成完整路径集。",
            )
        )
    return conflicts


def _trace_sha256(
    nodes: tuple[NodeValidity, ...],
    hidden: tuple[HiddenValidity, ...],
    edges: tuple[InteractionEdge, ...],
) -> str:
    hits = [hit for node in nodes for hit in node.rule_hits]
    hits.extend(hit for item in hidden for hit in item.hidden_node.rule_hits)
    hits.extend(hit for item in hidden for hit in item.rule_hits)
    hits.extend(hit for edge in edges for hit in edge.rule_hits)
    return digest([item.to_dict() for item in sorted(hits, key=lambda hit: hit.trace_id)])


def build_validity_matrix(
    record: LiuYaoCaseRecord,
    request: ValidityRequest,
) -> ValidityMatrixReport:
    if not isinstance(record, LiuYaoCaseRecord):
        raise LiuYaoError("INVALID_INPUT", "record 必须是 LiuYaoCaseRecord")
    if not isinstance(request, ValidityRequest):
        raise LiuYaoError("INVALID_INPUT", "request 必须是 ValidityRequest")

    advanced = build_advanced_runtime_report(record, request.advanced_context)
    selection = _focus_selection(record, request.interpretation)
    month_branch = record.chart.month_branch
    day_branch = None if record.chart.day_ganzhi is None else record.chart.day_ganzhi[1]
    original_nodes: list[NodeValidity] = []
    changed_nodes: list[NodeValidity] = []
    for line in record.chart.lines:
        original_nodes.append(
            _evaluate_node(
                node_id=f"original:{line.position}",
                node_kind="original",
                position=line.position,
                branch=line.najia_branch,
                element=line.element,
                motion_kind="moving" if line.moving else "static",
                selected_use=line.position == selection.selected_position,
                is_void=line.is_void,
                advanced=advanced,
                month_branch=month_branch,
                day_branch=day_branch,
            )
        )
        if line.moving and line.changed_najia_branch is not None and line.changed_element is not None:
            changed_nodes.append(
                _evaluate_node(
                    node_id=f"changed:{line.position}",
                    node_kind="changed",
                    position=line.position,
                    branch=line.changed_najia_branch,
                    element=line.changed_element,
                    motion_kind="changed",
                    selected_use=False,
                    is_void=line.changed_is_void,
                    advanced=advanced,
                    month_branch=month_branch,
                    day_branch=day_branch,
                )
            )
    nodes = tuple(sorted(original_nodes + changed_nodes, key=lambda item: item.node_id))
    nodes_by_id = {node.node_id: node for node in nodes}
    hidden, hidden_conflicts = _hidden_validity(
        record,
        advanced,
        nodes_by_id,
        month_branch=month_branch,
        day_branch=day_branch,
    )
    edges = _build_edges(record, nodes_by_id, selection)
    paths, path_limit_reached = _enumerate_paths(edges, nodes, selection)

    conflicts = _node_conflicts(nodes)
    conflicts.extend(_node_conflicts(tuple(item.hidden_node for item in hidden)))
    conflicts.extend(hidden_conflicts)
    conflicts.extend(_path_conflicts(paths, limit_reached=path_limit_reached))
    if selection.status not in _SELECTED_STATES:
        conflicts.append(
            ValidityConflict(
                conflict_id="focus:selection-required",
                code="USE_LINE_SELECTION_REQUIRED",
                subjects=tuple(f"original:{item}" for item in selection.candidate_positions),
                severity="high",
                resolution="unresolved",
                rule_ids=(),
                technical=selection.reason,
                plain="先确认用神，再裁剪到用神的作用路径。",
            )
        )

    reality_blocked = request.interpretation.reality_status == "blocking"
    if reality_blocked:
        conflicts.append(
            ValidityConflict(
                conflict_id="reality:blocking-with-evidence",
                code="REALITY_HARD_BLOCK_CONFIRMED",
                subjects=(),
                severity="hard",
                resolution="reality_override",
                rule_ids=(),
                technical="调用方确认现实阻断并在本请求绑定了证据引用。",
                plain="现实条件优先；盘面结构仍保留审计，但不覆盖现实阻断。",
            )
        )

    path_unresolved_codes = tuple(
        conflict.code
        for conflict in conflicts
        if conflict.code in {"OPPOSING_DIRECT_PATHS", "PATH_ENUMERATION_LIMIT"}
    )
    focus_dependencies: list[str] = []
    if advanced.context_status in {"provided_unconfirmed", "missing"}:
        focus_dependencies.append("CALENDAR_PROVENANCE_UNCONFIRMED")
    elif advanced.context_status == "confirmed_partial":
        focus_dependencies.append("CALENDAR_CONTEXT_PARTIAL")
    if selection.selected_position is None:
        focus_dependencies.append("USE_LINE_SELECTION_REQUIRED")
        selected_node = None
    else:
        selected_node = nodes_by_id[f"original:{selection.selected_position}"]
        focus_dependencies.extend(selected_node.open_obligations)
        if any(
            path.enumeration_status == "retained"
            and path.validity_status == "deferred"
            for path in paths
        ):
            focus_dependencies.append("FOCUS_PATHS_DEFERRED")
        focus_dependencies.extend(path_unresolved_codes)
    inventory_dependencies = list(
        dict.fromkeys(
            code
            for node in nodes
            for code in node.open_obligations
        )
    )
    for item in hidden:
        for code in item.hidden_node.open_obligations + item.open_obligations:
            if code not in inventory_dependencies:
                inventory_dependencies.append(code)

    if reality_blocked:
        focus_status = "reality_blocked"
        reality_override = "blocking_confirmed_with_bound_refs"
        headline = "现实阻断优先，结构候选只保留审计。"
    elif advanced.context_status in {"provided_unconfirmed", "missing"}:
        focus_status = "calendar_unconfirmed"
        reality_override = (
            "evidence_bound_no_override"
            if request.reality_evidence_confirmed
            else "none"
        )
        headline = "月日轴未通过来源确认门禁，后续用神、节点和路径只保留审计。"
    elif advanced.context_status == "confirmed_partial":
        focus_status = "calendar_partial"
        reality_override = (
            "evidence_bound_no_override"
            if request.reality_evidence_confirmed
            else "none"
        )
        headline = "月建或日柱缺失，空破墓绝矩阵不能闭合。"
    elif selected_node is None:
        focus_status = "needs_confirmation"
        reality_override = (
            "evidence_bound_no_override"
            if request.reality_evidence_confirmed
            else "none"
        )
        headline = "用神尚未唯一确认，路径不进入有效性裁决。"
    else:
        has_deferred_focus_path = any(
            path.target_node_id == selected_node.node_id
            and path.enumeration_status == "retained"
            and path.validity_status == "deferred"
            for path in paths
        )
        if selected_node.state == "available_candidate" and path_unresolved_codes:
            focus_status = "unresolved"
        elif selected_node.state == "available_candidate" and has_deferred_focus_path:
            focus_status = "conditional"
        else:
            focus_status = selected_node.state
        reality_override = (
            "evidence_bound_no_override"
            if request.reality_evidence_confirmed
            else "none"
        )
        headline = {
            "unknown_context": "月日轴或来源门禁不完整，焦点有效性未知。",
            "conditional": "焦点仍有空破等条件义务，作用路径保持条件性。",
            "unresolved": "焦点存在方向未决或规则冲突，暂不裁成单向结论。",
            "available_candidate": "焦点通过当前基础门禁，但仍只是结构候选。",
        }[focus_status]

    if any(node.state == "unknown_context" for node in nodes):
        inventory_status = "unknown_context"
    elif any(node.state != "available_candidate" for node in nodes) or hidden:
        inventory_status = "conditional"
    else:
        inventory_status = "complete"

    unique_conflicts = {item.conflict_id: item for item in conflicts}
    warnings = tuple(
        dict.fromkeys(
            advanced.warnings
            + (
                "活动规则的两本核心资料属于同一作者文本谱系，活动来源族数量为 1。",
                "张志春资料只用于作用域冲突和角色极性旁审，不把案例旁证升级为活动规则。",
                "规则证据仅为 source_only、human_reviewed=false；工程可复算不等于现实预测有效。",
                "现实证据引用和确认位都由调用方声明；当前运行时不核验证据内容真实性。",
                "路径有效性与工程枚举状态分轴；profile_excluded 不解释为传统上永久无效。",
            )
        )
    )
    limits = tuple(
        dict.fromkeys(
            advanced.limits
            + (
                "尚未闭合完整旺衰、暗动、合化、三合成局、真破和所有冲库条件。",
                "伏神不会自动出伏或升级为用神；飞伏口诀的内部冲突保持未决。",
                "工程 policy 最多枚举两条边的简单路径；循环、过长和跨位变爻均保留排除收据。",
                "本矩阵不输出应期、成功概率、确定日期或吉凶成品。",
            )
        )
    )
    return ValidityMatrixReport(
        case_id=record.cast.case_id,
        case_record_sha256=record.canonical_sha256,
        chart_sha256=record.chart.canonical_sha256,
        request=request,
        advanced_runtime_sha256=advanced.canonical_sha256,
        focus_selection=selection,
        focus_status=focus_status,
        inventory_status=inventory_status,
        nodes=nodes,
        hidden_candidates=hidden,
        edges=edges,
        paths=paths,
        conflicts=tuple(unique_conflicts[key] for key in sorted(unique_conflicts)),
        focus_dependencies=tuple(dict.fromkeys(focus_dependencies)),
        inventory_dependencies=tuple(dict.fromkeys(inventory_dependencies)),
        reality_override=reality_override,
        trace_sha256=_trace_sha256(nodes, hidden, edges),
        headline=headline,
        warnings=warnings,
        limits=limits,
    )


__all__ = [
    "VALIDITY_ENGINEERING_POLICY",
    "VALIDITY_ENGINEERING_POLICY_ID",
    "VALIDITY_ENGINEERING_POLICY_SHA256",
    "VALIDITY_MATRIX_METHOD_ID",
    "VALIDITY_MATRIX_PRODUCTION_ALLOWED",
    "VALIDITY_MATRIX_STATUS",
    "VALIDITY_GATE_PRIORITY",
    "VALIDITY_PRECONDITION_GATES",
    "VALIDITY_PRIORITY_BANDS",
    "VALIDITY_PRIORITY_TABLE_SHA256",
    "VALIDITY_RULE_PROFILE_ID",
    "VALIDITY_RULE_PROFILE_SHA256",
    "VALIDITY_RULE_CONTRACT",
    "FocusSelection",
    "HiddenValidity",
    "InfluencePath",
    "InteractionEdge",
    "NodeValidity",
    "PriorityBand",
    "RuleHit",
    "RuleSourceEvidence",
    "ValidityConflict",
    "ValidityMatrixReport",
    "ValidityRequest",
    "build_validity_matrix",
]
