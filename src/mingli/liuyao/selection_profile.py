from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .tables import PREDICTION_VALIDITY, digest

SELECTION_SOURCE_PROFILE_ID = "liuyao-shaoweihua-source-only-selection@0.1.0"
SELECTION_SOURCE_PROFILE_STATUS = "draft"
SELECTION_SOURCE_EVIDENCE_LEVEL = "source_only"
SELECTION_SOURCE_HUMAN_REVIEWED = False
SELECTION_SOURCE_FAMILY_ID = "shaoweihua-liuyao-lineage"

SELECTION_TOPIC_POLICY_ID = "liuyao-selection-topic-policy@0.1.0"
SELECTION_TOPIC_POLICY_STATUS = "review_only"
SELECTION_ENGINEERING_POLICY_ID = "liuyao-selection-engineering-policy@0.1.0"
SELECTION_ENGINEERING_POLICY_STATUS = "review_only"


@dataclass(frozen=True, slots=True)
class SelectionSourceFile:
    source_id: str
    title: str
    sha256: str
    source_family_id: str
    activates_rules: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "sha256": self.sha256,
            "source_family_id": self.source_family_id,
            "activates_rules": self.activates_rules,
        }


@dataclass(frozen=True, slots=True)
class SelectionSourceEvidence:
    source_ref: str
    source_level: str
    topic_scope: str
    source_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "source_ref": self.source_ref,
            "source_family": SELECTION_SOURCE_FAMILY_ID,
            "source_level": self.source_level,
            "topic_scope": self.topic_scope,
            "source_terms": list(self.source_terms),
        }


@dataclass(frozen=True, slots=True)
class SelectionSourceRule:
    rule_id: str
    purpose: str
    output_candidates: tuple[str, ...]
    automation_effect: str
    conflict_code: str | None
    evidence: tuple[SelectionSourceEvidence, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "purpose": self.purpose,
            "output_candidates": list(self.output_candidates),
            "automation_effect": self.automation_effect,
            "conflict_code": self.conflict_code,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class SelectionTopicDimension:
    topic: str
    dimension: str
    scope: str
    plain: str

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "dimension": self.dimension,
            "scope": self.scope,
            "plain": self.plain,
        }


@dataclass(frozen=True, slots=True)
class SelectionPriorityBand:
    band_id: str
    order: int
    purpose: str

    def to_dict(self) -> dict[str, object]:
        return {"band_id": self.band_id, "order": self.order, "purpose": self.purpose}


SELECTION_TOPIC_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "exam": "exam",
        "考公考编": "exam",
        "考试": "exam",
        "relationship_reconciliation": "relationship_reconciliation",
        "感情复合": "relationship_reconciliation",
        "复合": "relationship_reconciliation",
        "pregnancy": "pregnancy",
        "求孕": "pregnancy",
    }
)

SELECTION_TOPIC_DIMENSIONS = (
    SelectionTopicDimension(
        "exam",
        "system_fit",
        "outside_single_cast",
        "体制适配不能由单次六爻候选集推出。",
    ),
    SelectionTopicDimension(
        "exam",
        "current_exam",
        "structural",
        "只登记事件合同冻结的本次考试候选关系与爻位。",
    ),
    SelectionTopicDimension(
        "exam",
        "position_direction",
        "reality_required",
        "岗位方向依赖专业、地区、资格和竞争资料。",
    ),
    SelectionTopicDimension(
        "exam",
        "preparation_strategy",
        "reality_required",
        "备考策略依赖成绩、时间和薄弱项等现实资料。",
    ),
    SelectionTopicDimension(
        "relationship_reconciliation",
        "bond",
        "structural",
        "缘分牵引是独立事件焦点，不推出复联。",
    ),
    SelectionTopicDimension(
        "relationship_reconciliation",
        "recontact",
        "structural",
        "复联是独立事件焦点，不推出复合。",
    ),
    SelectionTopicDimension(
        "relationship_reconciliation",
        "reconciliation",
        "structural",
        "复合是独立事件焦点，不推出关系稳定。",
    ),
    SelectionTopicDimension(
        "relationship_reconciliation",
        "stability",
        "structural_with_reality_gate",
        "稳定性除独立事件合同外，还必须绑定现实关系资料。",
    ),
    SelectionTopicDimension(
        "pregnancy",
        "conception_opportunity",
        "advisory_only",
        "只允许传统结构候选；不能替代医学检查。",
    ),
    SelectionTopicDimension(
        "pregnancy",
        "medical_confirmation",
        "professional_only",
        "是否临床妊娠只能由医学检查确认。",
    ),
    SelectionTopicDimension(
        "pregnancy",
        "pregnancy_stability",
        "professional_only",
        "妊娠稳定性不能由传统结构候选推出。",
    ),
    SelectionTopicDimension(
        "pregnancy",
        "medical_factors",
        "professional_only",
        "年龄、周期与生殖健康等因素属于医学范围。",
    ),
)

SELECTION_DEFAULT_FOCUS: Mapping[str, str] = MappingProxyType(
    {
        "exam": "current_exam",
        "relationship_reconciliation": "reconciliation",
        "pregnancy": "conception_opportunity",
    }
)

_SOURCE_FILES = (
    SelectionSourceFile(
        "src_039",
        "周易预测宝典",
        "afa2cd2ad5acc09f3d7b4f4bb65f98d71f2199125ddef6ada84a0d114a626f79",
        SELECTION_SOURCE_FAMILY_ID,
        True,
    ),
    SelectionSourceFile(
        "src_037",
        "周易与预测学",
        "c00449b2a1d58da4da091a0078e580ad7657f015b3bed770131d11db158b4fb8",
        SELECTION_SOURCE_FAMILY_ID,
        True,
    ),
    SelectionSourceFile(
        "src_040",
        "未知之门",
        "3e7a8c70fb0d4554f5b17d25bf50069c3366fd0e7aaecb79c097a8ee32dedb01",
        "zhangzhichun-commentary",
        False,
    ),
)

_GENERAL_EVIDENCE = (
    SelectionSourceEvidence(
        "src_039:print163-164/pdf163-164",
        "author_rule",
        "general_object_relation_mapping",
    ),
    SelectionSourceEvidence(
        "src_037:print179-180/pdf194-195",
        "author_rule",
        "general_object_relation_mapping",
    ),
)

SELECTION_SOURCE_RULES = (
    SelectionSourceRule(
        "SELF-TO-SHI",
        "本人摇卦时把世爻登记为主体位置；不外推代摇主体。",
        ("self_subject:世爻",),
        "self_cast_subject_selector_only",
        "PROXY_SUBJECT_MAPPING_NOT_FOUND",
        _GENERAL_EVIDENCE,
    ),
    SelectionSourceRule(
        "GENERAL-SIX-RELATION-MAPPING",
        "登记资料明确列举的人、事、物与五类六亲的候选对应。",
        ("父母", "兄弟", "子孙", "妻财", "官鬼"),
        "normalized_candidates_only",
        None,
        _GENERAL_EVIDENCE,
    ),
    SelectionSourceRule(
        "TWO-USE-SOURCE-PREFERENCES",
        "登记用神两现时的来源偏好，但不形成总排序。",
        (
            "prefer_vigorous_over_weak",
            "prefer_moving_over_static",
            "prefer_not_month_broken",
            "prefer_not_void",
            "prefer_uninjured",
            "prefer_nearer_shi",
            "prefer_supported",
            "prefer_vigorous_in_month_or_day",
        ),
        "receipt_only_no_automatic_tiebreak",
        "SOURCE_PREFERENCES_HAVE_NO_TOTAL_ORDER",
        (
            SelectionSourceEvidence(
                "src_039:print173/pdf173",
                "attributed_quote",
                "multiple_visible_use_candidates",
            ),
            SelectionSourceEvidence(
                "src_037:print189/pdf204",
                "attributed_quote",
                "multiple_visible_use_candidates",
            ),
            SelectionSourceEvidence(
                "src_039:print174/pdf174",
                "author_rule",
                "multiple_visible_use_candidates",
            ),
            SelectionSourceEvidence(
                "src_037:print190/pdf205",
                "author_rule",
                "multiple_visible_use_candidates",
            ),
        ),
    ),
    SelectionSourceRule(
        "EXAM-DUAL-RELATION",
        "文试登记官鬼与父母并列角色；武试仅登记官鬼。",
        ("written:官鬼+父母", "martial:官鬼"),
        "relation_set_requires_event_scope",
        "MODERN_EXAM_SCOPE_UNRESOLVED",
        (
            SelectionSourceEvidence(
                "src_039:print242/pdf242,print247/pdf247",
                "author_rule",
                "historical_written_or_martial_exam",
            ),
            SelectionSourceEvidence(
                "src_037:print259/pdf274,print264/pdf279",
                "author_rule",
                "historical_written_or_martial_exam",
            ),
        ),
    ),
    SelectionSourceRule(
        "RELATIONSHIP-TRADITIONAL-PAIRING",
        "仅登记经确认的传统异性婚姻角色映射。",
        (
            "male_subject_female_spouse:妻财",
            "female_subject_male_spouse:官鬼",
        ),
        "strict_source_scope_only",
        "RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED",
        (
            SelectionSourceEvidence(
                "src_039:print257/pdf257",
                "author_rule",
                "traditional_heterosexual_marriage",
            ),
            SelectionSourceEvidence(
                "src_037:print275/pdf290",
                "author_rule",
                "traditional_heterosexual_marriage",
            ),
        ),
    ),
    SelectionSourceRule(
        "PREGNANCY-METHOD-CONFLICT",
        "同时登记子孙法和胎爻法；作者偏好不解除方法冲突。",
        ("children_relation:子孙", "fetal_marker:胎爻"),
        "explicit_method_confirmation_required",
        "PREGNANCY_SOURCE_METHOD_CONFLICT",
        (
            SelectionSourceEvidence(
                "src_039:print277/pdf277",
                "author_rule",
                "pregnancy_method_author_preference",
                ("method_coexistence", "author_preference_children_relation"),
            ),
            SelectionSourceEvidence(
                "src_037:print296/pdf311",
                "author_rule",
                "pregnancy_method_author_preference",
                ("method_coexistence", "author_preference_children_relation"),
            ),
            SelectionSourceEvidence(
                "src_039:print277/pdf277",
                "attributed_quote",
                "pregnancy_children_relation_method",
                ("增删卜易", "children_relation"),
            ),
            SelectionSourceEvidence(
                "src_037:print296/pdf311",
                "attributed_quote",
                "pregnancy_children_relation_method",
                ("增删卜易", "children_relation"),
            ),
            SelectionSourceEvidence(
                "src_039:print277-278/pdf277-278",
                "attributed_quote",
                "pregnancy_fetal_marker_method",
                ("卜筮正宗", "fetal_marker"),
            ),
            SelectionSourceEvidence(
                "src_037:print296-297/pdf311-312",
                "attributed_quote",
                "pregnancy_fetal_marker_method",
                ("卜筮正宗", "fetal_marker"),
            ),
        ),
    ),
)

_SOURCE_EXCLUSIONS = (
    "parallel_texts_do_not_count_as_independent_validation",
    "author_success_claims_do_not_create_accuracy_weights",
    "author_cases_do_not_create_universal_rules",
    "moving_line_does_not_auto_break_ties",
    "proxy_subject_mapping_not_found",
    "modern_civil_service_equivalence_not_found",
    "same_sex_and_nonbinary_relationship_mapping_not_found",
    "relationship_focus_specific_use_mapping_not_found",
    "medical_and_reproductive_outcome_claims_excluded",
    "timing_probability_and_final_fortune_excluded",
)

SELECTION_SOURCE_RULE_CONTRACT: Mapping[str, object] = MappingProxyType(
    {
        "parallel_text_family_policy": "count_as_one_active_source_family",
        "general_mapping_policy": "normalized_object_semantics_only",
        "multiple_use_policy": "receipts_only_no_total_order",
        "exam_policy": "scope_confirmed_dual_relation_or_martial_single_relation",
        "relationship_policy": "traditional_pairing_scope_only",
        "pregnancy_policy": "method_conflict_requires_explicit_confirmation",
        "author_preference_policy": "never_resolves_source_conflict_automatically",
        "source_exclusions": _SOURCE_EXCLUSIONS,
    }
)

SELECTION_ENGINEERING_POLICY: Mapping[str, object] = MappingProxyType(
    {
        "entrypoint": "single_runtime_entrypoint_no_exported_core_builder",
        "matrix_strategy": "one_matrix_per_relation_hypothesis",
        "upstream_matrix_binding": "complete_candidate_focus_and_node_semantics_required",
        "ambiguous_candidate_strategy": "no_counterfactual_primary_position",
        "primary_position_policy": "caller_confirmation_and_refs_required",
        "automatic_candidate_scope": "visible_original_lines_only",
        "changed_line_policy": "never_independent_use_candidate",
        "hidden_policy": "inventory_only_never_contributes",
        "multiple_candidate_policy": "tie_requires_confirmation",
        "moving_preference_policy": "receipt_only_never_tiebreak",
        "available_candidate_semantics": "provisional_review_candidate_not_event_result",
        "outside_source_manual_mapping": "inventory_allowed_never_automatic_contribution",
        "calendar_gate": "confirmed_complete_month_and_day_required",
        "reality_gate": "confirmed_blocking_stops_before_matrix",
        "forbidden_outputs": (
            "final_use",
            "success_probability",
            "timing_candidates",
            "exact_date",
            "event_outcome",
            "auspiciousness",
        ),
    }
)

SELECTION_PRIORITY_BANDS = (
    SelectionPriorityBand("contract_integrity_gate", 1100, "类型、摘要和事件合同绑定。"),
    SelectionPriorityBand("reality_gate", 1000, "有证据的现实硬阻断先于结构候选。"),
    SelectionPriorityBand("topic_safety_gate", 900, "专业或单卦范围外维度停止。"),
    SelectionPriorityBand("contract_focus_gate", 800, "topic 与 focus 必须由事件合同确认。"),
    SelectionPriorityBand("calendar_provenance_gate", 700, "月日轴必须完整且来源已确认。"),
    SelectionPriorityBand("subject_mapping_gate", 600, "本人绑定世爻；代摇主体必须确认。"),
    SelectionPriorityBand("source_scope_method_gate", 500, "来源范围和方法冲突显式处理。"),
    SelectionPriorityBand("relation_resolution_gate", 400, "关系角色未决不得形成单一候选。"),
    SelectionPriorityBand("use_position_gate", 300, "多爻不自动决胜，显式位置必须有收据。"),
    SelectionPriorityBand("validity_matrix_gate", 200, "消费第二切片焦点和路径有效性。"),
    SelectionPriorityBand("candidate_review_gate", 100, "只生成待人工复核的临时候选。"),
)

SELECTION_GATE_PRIORITY = tuple(item.band_id for item in SELECTION_PRIORITY_BANDS)
SELECTION_PRIORITY_TABLE_SHA256 = digest(
    {
        "priority_bands": [item.to_dict() for item in SELECTION_PRIORITY_BANDS],
        "gate_priority": list(SELECTION_GATE_PRIORITY),
    }
)


def selection_source_profile_payload() -> dict[str, object]:
    return {
        "profile_id": SELECTION_SOURCE_PROFILE_ID,
        "profile_status": SELECTION_SOURCE_PROFILE_STATUS,
        "evidence_level": SELECTION_SOURCE_EVIDENCE_LEVEL,
        "human_reviewed": SELECTION_SOURCE_HUMAN_REVIEWED,
        "production_allowed": False,
        "prediction_validity": PREDICTION_VALIDITY,
        "source_family_id": SELECTION_SOURCE_FAMILY_ID,
        "active_rule_source_family_count": 1,
        "referenced_text_family_count": 2,
        "empirical_validation_source_family_count": 0,
        "source_files": [item.to_dict() for item in _SOURCE_FILES],
        "rules": [item.to_dict() for item in SELECTION_SOURCE_RULES],
        "rule_contract": {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in SELECTION_SOURCE_RULE_CONTRACT.items()
        },
    }


def selection_topic_policy_payload() -> dict[str, object]:
    return {
        "policy_id": SELECTION_TOPIC_POLICY_ID,
        "policy_status": SELECTION_TOPIC_POLICY_STATUS,
        "supported_topics": sorted(set(SELECTION_TOPIC_ALIASES.values())),
        "topic_aliases": dict(SELECTION_TOPIC_ALIASES),
        "default_focus": dict(SELECTION_DEFAULT_FOCUS),
        "dimensions": [item.to_dict() for item in SELECTION_TOPIC_DIMENSIONS],
        "separate_contract_per_dimension": True,
        "medical_and_professional_override": "cannot_be_bypassed_by_relation_choice",
    }


def selection_engineering_policy_payload() -> dict[str, object]:
    return {
        "policy_id": SELECTION_ENGINEERING_POLICY_ID,
        "policy_status": SELECTION_ENGINEERING_POLICY_STATUS,
        "priority_bands": [item.to_dict() for item in SELECTION_PRIORITY_BANDS],
        "priority_table_sha256": SELECTION_PRIORITY_TABLE_SHA256,
        "gate_priority": list(SELECTION_GATE_PRIORITY),
        "policy_contract": {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in SELECTION_ENGINEERING_POLICY.items()
        },
    }


SELECTION_SOURCE_PROFILE_SHA256 = digest(selection_source_profile_payload())
SELECTION_TOPIC_POLICY_SHA256 = digest(selection_topic_policy_payload())
SELECTION_ENGINEERING_POLICY_SHA256 = digest(selection_engineering_policy_payload())


def find_topic_dimension(topic: str, dimension: str) -> SelectionTopicDimension | None:
    return next(
        (
            item
            for item in SELECTION_TOPIC_DIMENSIONS
            if item.topic == topic and item.dimension == dimension
        ),
        None,
    )


__all__ = [
    "SELECTION_ENGINEERING_POLICY",
    "SELECTION_ENGINEERING_POLICY_ID",
    "SELECTION_ENGINEERING_POLICY_SHA256",
    "SELECTION_GATE_PRIORITY",
    "SELECTION_PRIORITY_BANDS",
    "SELECTION_PRIORITY_TABLE_SHA256",
    "SELECTION_SOURCE_FAMILY_ID",
    "SELECTION_SOURCE_PROFILE_ID",
    "SELECTION_SOURCE_PROFILE_SHA256",
    "SELECTION_SOURCE_RULE_CONTRACT",
    "SELECTION_SOURCE_RULES",
    "SELECTION_TOPIC_ALIASES",
    "SELECTION_TOPIC_DIMENSIONS",
    "SELECTION_TOPIC_POLICY_ID",
    "SELECTION_TOPIC_POLICY_SHA256",
    "SelectionPriorityBand",
    "SelectionSourceEvidence",
    "SelectionSourceRule",
    "SelectionTopicDimension",
    "find_topic_dimension",
    "selection_engineering_policy_payload",
    "selection_source_profile_payload",
    "selection_topic_policy_payload",
]
