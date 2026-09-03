from __future__ import annotations

from typing import Any

from .advanced_runtime import AdvancedContextRequest
from .case_record import LiuYaoCaseRecord, create_case_record
from .models import EventContract, LiuYaoCastInput
from .selection_profile import (
    SELECTION_ENGINEERING_POLICY_SHA256,
    SELECTION_PRIORITY_TABLE_SHA256,
    SELECTION_SOURCE_PROFILE_SHA256,
    SELECTION_TOPIC_POLICY_SHA256,
)
from .selection_runtime import (
    SELECTION_RUNTIME_PRODUCTION_ALLOWED,
    SelectionRequest,
    SelectionRuntimeReport,
    build_selection_runtime_report,
)
from .tables import PREDICTION_VALIDITY, digest
from .validation import LiuYaoError
from .validity_matrix import (
    VALIDITY_ENGINEERING_POLICY_SHA256,
    VALIDITY_PRIORITY_TABLE_SHA256,
    VALIDITY_RULE_PROFILE_SHA256,
)


def _record(
    case_id: str,
    *,
    line_values: tuple[int, ...] = (7, 7, 7, 9, 7, 7),
    month_branch: str | None = "卯",
    day_ganzhi: str | None = "丁卯",
    casting_mode: str = "self",
    reality_facts: tuple[str, ...] = (),
) -> LiuYaoCaseRecord:
    return create_case_record(
        LiuYaoCastInput(
            case_id=case_id,
            question="synthetic selection runtime benchmark",
            line_values=line_values,
            event_contract=EventContract(
                target_event=f"synthetic event {case_id}",
                deadline="2099-12-31",
                success_criteria="synthetic criterion",
                evidence_requirement="synthetic evidence",
            ),
            completed_at="2026-09-03T00:00:00+00:00",
            location="synthetic",
            casting_mode=casting_mode,
            proxy_relationship=("synthetic proxy subject" if casting_mode == "proxy" else None),
            month_branch=month_branch,
            day_ganzhi=day_ganzhi,
            reality_facts=reality_facts,
        )
    )


def _request(
    record: LiuYaoCaseRecord,
    *,
    topic: str = "exam",
    focus_dimension: str = "current_exam",
    calendar_confirmed: bool = True,
    contract_confirmed: bool = True,
    **overrides: Any,
) -> SelectionRequest:
    values: dict[str, object] = {
        "topic": topic,
        "focus_dimension": focus_dimension,
        "case_record_sha256": record.canonical_sha256,
        "event_contract_sha256": digest(record.cast.event_contract.to_dict()),
        "advanced_context": AdvancedContextRequest(
            calendar_context_confirmed=calendar_confirmed,
            calendar_source_refs=("source:synthetic-calendar",) if calendar_confirmed else (),
        ),
        "contract_focus_confirmed": contract_confirmed,
        "contract_source_refs": (
            ("source:synthetic-contract",) if contract_confirmed else ()
        ),
    }
    if topic == "exam":
        values.update(
            {
                "exam_scope": "martial",
                "exam_scope_confirmed": True,
                "exam_scope_refs": ("source:synthetic-exam-scope",),
            }
        )
    elif topic == "relationship_reconciliation":
        values.update(
            {
                "relationship_pairing_scope": "male_subject_female_spouse",
                "relationship_pairing_confirmed": True,
                "relationship_pairing_refs": ("source:synthetic-relationship-scope",),
            }
        )
    elif topic == "pregnancy":
        values.update(
            {
                "pregnancy_method": "children_relation",
                "pregnancy_method_confirmed": True,
                "pregnancy_method_refs": ("source:synthetic-pregnancy-method",),
            }
        )
    values.update(overrides)
    return SelectionRequest(**values)  # type: ignore[arg-type]


def _public_subobject_sha256(value: object, hash_field: str) -> str:
    assert isinstance(value, dict)
    payload = dict(value)
    payload.pop(hash_field)
    return digest(payload)


def _contains_key_concept(value: object, targets: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        return any(
            any(target in str(key).lower() for target in targets)
            or _contains_key_concept(item, targets)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_key_concept(item, targets) for item in value)
    return False


def _contract_mismatch_rejected(record: LiuYaoCaseRecord) -> bool:
    request = _request(record)
    payload = request.to_dict(include_hash=False)
    payload["event_contract_sha256"] = "0" * 64
    mismatched = SelectionRequest.from_mapping(payload)
    try:
        build_selection_runtime_report(record, mismatched)
    except LiuYaoError as exc:
        return exc.code == "CONTRACT_BINDING_MISMATCH"
    return False


def _case_record_mismatch_rejected(record: LiuYaoCaseRecord) -> bool:
    request = _request(record)
    changed_record = _record(
        record.cast.case_id,
        line_values=(6, 6, 6, 6, 6, 6),
    )
    try:
        build_selection_runtime_report(changed_record, request)
    except LiuYaoError as exc:
        return exc.code == "CASE_RECORD_BINDING_MISMATCH"
    return False


def _trace_sha256(report: SelectionRuntimeReport) -> str:
    payload = report.to_dict(include_hash=False)
    return digest(
        {
            "gates": payload["gate_receipts"],
            "subject_mapping": payload["subject_mapping"],
            "relation_decision": payload["relation_decision"],
            "matrix_receipts": payload["matrix_receipts"],
            "candidates": payload["candidates"],
            "provisional_candidate_id": payload["provisional_candidate_id"],
            "dependencies": payload["dependencies"],
        }
    )


def benchmark_liuyao_selection_runtime() -> dict[str, object]:
    unique_record = _record("SYNTHETIC-SELECTION-UNIQUE")
    unique_request = _request(unique_record)
    unique = build_selection_runtime_report(unique_record, unique_request)
    repeated = build_selection_runtime_report(unique_record, unique_request)
    payload = unique.to_dict()

    contract_unconfirmed = build_selection_runtime_report(
        unique_record,
        _request(unique_record, contract_confirmed=False),
    )
    professional_only = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            topic="pregnancy",
            focus_dimension="medical_confirmation",
        ),
    )
    outside_single_cast = build_selection_runtime_report(
        unique_record,
        _request(unique_record, focus_dimension="system_fit"),
    )
    written_dual = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            exam_scope="written_or_cultural",
            exam_scope_confirmed=True,
            exam_scope_refs=("source:synthetic-written-exam",),
        ),
    )
    modern_exam = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            exam_scope="modern_civil_service_unspecified",
            exam_scope_confirmed=True,
            exam_scope_refs=("source:synthetic-modern-exam",),
        ),
    )

    relationship_mapped = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            topic="relationship_reconciliation",
            focus_dimension="reconciliation",
        ),
    )
    relationship_structural_focuses = tuple(
        build_selection_runtime_report(
            unique_record,
            _request(
                unique_record,
                topic="relationship_reconciliation",
                focus_dimension=focus,
            ),
        )
        for focus in ("bond", "recontact")
    )
    relationship_outside = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            topic="relationship_reconciliation",
            focus_dimension="reconciliation",
            relationship_pairing_scope="outside_traditional_scope",
            relationship_pairing_confirmed=True,
            relationship_pairing_refs=("source:synthetic-outside-relationship",),
        ),
    )
    relationship_manual = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            topic="relationship_reconciliation",
            focus_dimension="reconciliation",
            relationship_pairing_scope="outside_traditional_scope",
            relationship_pairing_confirmed=True,
            relationship_pairing_refs=("source:synthetic-outside-relationship",),
            relation_choice="妻财",
            relation_choice_confirmed=True,
            relation_choice_refs=("source:synthetic-manual-relation",),
            relation_choice_reason="synthetic reviewer mapping",
        ),
    )

    pregnancy_conflict = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            topic="pregnancy",
            focus_dimension="conception_opportunity",
            pregnancy_method="unresolved",
            pregnancy_method_confirmed=False,
            pregnancy_method_refs=(),
        ),
    )
    pregnancy_children = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            topic="pregnancy",
            focus_dimension="conception_opportunity",
        ),
    )
    pregnancy_fetal = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            topic="pregnancy",
            focus_dimension="conception_opportunity",
            pregnancy_method="fetal_marker",
            pregnancy_method_confirmed=True,
            pregnancy_method_refs=("source:synthetic-fetal-method",),
        ),
    )

    reality_blocked = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            reality_status="blocking",
            reality_facts=("synthetic verified blocker",),
            reality_evidence_confirmed=True,
            reality_evidence_refs=("source:synthetic-reality",),
        ),
    )
    calendar_unconfirmed = build_selection_runtime_report(
        unique_record,
        _request(unique_record, calendar_confirmed=False),
    )
    partial_record = _record(
        "SYNTHETIC-SELECTION-PARTIAL-CALENDAR",
        day_ganzhi=None,
    )
    calendar_partial = build_selection_runtime_report(
        partial_record,
        _request(partial_record),
    )

    proxy_record = _record(
        "SYNTHETIC-SELECTION-PROXY",
        casting_mode="proxy",
    )
    proxy_missing = build_selection_runtime_report(proxy_record, _request(proxy_record))
    proxy_bound = build_selection_runtime_report(
        proxy_record,
        _request(
            proxy_record,
            subject_mapping_confirmed=True,
            subject_position=2,
            subject_mapping_refs=("source:synthetic-proxy-mapping",),
        ),
    )
    proxy_relationship_mapped_attempt = build_selection_runtime_report(
        proxy_record,
        _request(
            proxy_record,
            topic="relationship_reconciliation",
            focus_dimension="reconciliation",
            subject_mapping_confirmed=True,
            subject_position=2,
            subject_mapping_refs=("source:synthetic-proxy-mapping",),
        ),
    )
    proxy_relationship_manual = build_selection_runtime_report(
        proxy_record,
        _request(
            proxy_record,
            topic="relationship_reconciliation",
            focus_dimension="reconciliation",
            subject_mapping_confirmed=True,
            subject_position=2,
            subject_mapping_refs=("source:synthetic-proxy-mapping",),
            relation_choice="妻财",
            relation_choice_confirmed=True,
            relation_choice_refs=("source:synthetic-proxy-manual-relation",),
            relation_choice_reason="synthetic reviewer mapping outside source scope",
        ),
    )

    tie_record = _record(
        "SYNTHETIC-SELECTION-TIE",
        line_values=(7, 7, 9, 7, 7, 7),
    )
    tie_base = {
        "exam_scope": "written_or_cultural",
        "exam_scope_confirmed": True,
        "exam_scope_refs": ("source:synthetic-written-exam",),
        "relation_choice": "父母",
        "relation_choice_confirmed": True,
        "relation_choice_refs": ("source:synthetic-relation-choice",),
    }
    tie = build_selection_runtime_report(tie_record, _request(tie_record, **tie_base))
    position_confirmed = build_selection_runtime_report(
        tie_record,
        _request(
            tie_record,
            **tie_base,
            primary_position=3,
            primary_position_confirmed=True,
            primary_position_refs=("source:synthetic-position",),
        ),
    )
    unresolved = build_selection_runtime_report(
        unique_record,
        _request(
            unique_record,
            **tie_base,
            primary_position=6,
            primary_position_confirmed=True,
            primary_position_refs=("source:synthetic-position",),
        ),
    )
    conditional_record = _record(
        "SYNTHETIC-SELECTION-CONDITIONAL",
        line_values=(6, 6, 6, 6, 6, 6),
    )
    conditional = build_selection_runtime_report(
        conditional_record,
        _request(conditional_record),
    )

    hidden_record = _record(
        "SYNTHETIC-SELECTION-HIDDEN",
        line_values=(7, 8, 8, 6, 7, 7),
    )
    hidden = build_selection_runtime_report(hidden_record, _request(hidden_record))

    source_profile = payload["source_profile"]
    topic_policy = payload["topic_policy"]
    engineering_policy = payload["engineering_policy"]
    expected_upstream = {
        "rule_profile_sha256": VALIDITY_RULE_PROFILE_SHA256,
        "engineering_policy_sha256": VALIDITY_ENGINEERING_POLICY_SHA256,
        "priority_table_sha256": VALIDITY_PRIORITY_TABLE_SHA256,
    }
    tie_visible = tuple(
        item for item in tie.candidates if item.source_kind == "visible_original"
    )
    unique_visible = tuple(
        item for item in unique.candidates if item.source_kind == "visible_original"
    )
    hidden_only = tuple(
        item for item in hidden.candidates if item.source_kind == "hidden"
    )

    checks = {
        "source_profile_hash_recomputable": _public_subobject_sha256(
            source_profile, "profile_sha256"
        )
        == SELECTION_SOURCE_PROFILE_SHA256,
        "topic_policy_hash_recomputable": _public_subobject_sha256(
            topic_policy, "policy_sha256"
        )
        == SELECTION_TOPIC_POLICY_SHA256,
        "engineering_policy_hash_recomputable": _public_subobject_sha256(
            engineering_policy, "policy_sha256"
        )
        == SELECTION_ENGINEERING_POLICY_SHA256,
        "three_profile_hashes_bound": source_profile["profile_sha256"]
        == SELECTION_SOURCE_PROFILE_SHA256
        and topic_policy["policy_sha256"] == SELECTION_TOPIC_POLICY_SHA256
        and engineering_policy["policy_sha256"]
        == SELECTION_ENGINEERING_POLICY_SHA256,
        "priority_table_hash_recomputable": digest(
            {
                "priority_bands": engineering_policy["priority_bands"],
                "gate_priority": engineering_policy["gate_priority"],
            }
        )
        == SELECTION_PRIORITY_TABLE_SHA256,
        "upstream_validity_hashes_bound": payload["upstream_validity_hashes"]
        == expected_upstream,
        "contract_hash_bound": unique.event_contract_sha256
        == digest(unique_record.cast.event_contract.to_dict())
        == unique_request.event_contract_sha256,
        "case_record_hash_bound": unique.case_record_sha256
        == unique_record.canonical_sha256
        == unique_request.case_record_sha256,
        "contract_gate_passed": unique.gate_receipts[0].gate_id
        == "contract_integrity_gate"
        and unique.gate_receipts[0].reason_code == "INPUT_HASHES_BOUND",
        "contract_unconfirmed_blocks": contract_unconfirmed.selection_status
        == "contract_unconfirmed"
        and not contract_unconfirmed.matrix_receipts
        and not contract_unconfirmed.candidates,
        "contract_mismatch_rejected": _contract_mismatch_rejected(unique_record),
        "case_record_mismatch_rejected": _case_record_mismatch_rejected(unique_record),
        "professional_focus_blocks": professional_only.selection_status
        == "professional_only"
        and not professional_only.matrix_receipts,
        "outside_single_cast_blocks": outside_single_cast.selection_status
        == "focus_outside_single_cast"
        and not outside_single_cast.matrix_receipts,
        "exam_dual_roles_preserved": written_dual.relation_decision.status
        == "source_dual_relation"
        and tuple(item.relation for item in written_dual.relation_decision.active_roles)
        == ("官鬼", "父母"),
        "exam_dual_one_matrix_per_role": tuple(
            item.relation for item in written_dual.matrix_receipts
        )
        == ("官鬼", "父母"),
        "exam_dual_no_provisional": written_dual.selection_status
        == "relation_confirmation_required"
        and written_dual.provisional_candidate_id is None,
        "modern_exam_scope_unresolved": modern_exam.selection_status
        == "exam_scope_unresolved"
        and "MODERN_EXAM_SCOPE_UNRESOLVED" in modern_exam.dependencies,
        "relationship_traditional_scope_mapped": relationship_mapped.relation_decision.status
        == "source_scope_mapped"
        and relationship_mapped.relation_decision.active_roles[0].relation == "妻财",
        "relationship_bond_and_recontact_execute": tuple(
            (
                item.request.focus_dimension,
                item.selection_status,
                len(item.matrix_receipts),
            )
            for item in relationship_structural_focuses
        )
        == (
            ("bond", "single_review_candidate", 1),
            ("recontact", "single_review_candidate", 1),
        ),
        "relationship_outside_scope_requires_manual": relationship_outside.selection_status
        == "manual_relation_required"
        and not relationship_outside.candidates,
        "relationship_manual_unvalidated": relationship_manual.selection_status
        == "manual_unvalidated_mapping"
        and relationship_manual.relation_decision.manual_unvalidated,
        "relationship_manual_never_contributes": bool(relationship_manual.candidates)
        and not any(item.contributes for item in relationship_manual.candidates),
        "relationship_manual_gates_stay_unresolved": tuple(
            (item.gate_id, item.status, item.reason_code)
            for item in relationship_manual.gate_receipts
            if item.gate_id in {"source_scope_method_gate", "relation_resolution_gate"}
        )
        == (
            (
                "source_scope_method_gate",
                "review_required",
                "RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED",
            ),
            (
                "relation_resolution_gate",
                "review_required",
                "RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED",
            ),
        ),
        "pregnancy_method_conflict": pregnancy_conflict.selection_status
        == "source_method_conflict"
        and "PREGNANCY_SOURCE_METHOD_CONFLICT" in pregnancy_conflict.dependencies,
        "pregnancy_fetal_marker_unsupported": pregnancy_fetal.selection_status
        == "unsupported_method"
        and "FETAL_MARKER_NOT_IMPLEMENTED" in pregnancy_fetal.dependencies,
        "pregnancy_children_method_candidate": pregnancy_children.relation_decision.selected_method
        == "children_relation"
        and pregnancy_children.selection_status == "single_review_candidate",
        "reality_block_stops_before_matrix": reality_blocked.selection_status
        == "reality_blocked"
        and not reality_blocked.matrix_receipts
        and reality_blocked.advanced_runtime_sha256 is None,
        "calendar_unconfirmed_stops": calendar_unconfirmed.selection_status
        == "calendar_unconfirmed"
        and not calendar_unconfirmed.matrix_receipts,
        "calendar_partial_stops": calendar_partial.selection_status
        == "calendar_partial"
        and not calendar_partial.matrix_receipts
        and calendar_partial.advanced_runtime_sha256 is not None,
        "proxy_requires_subject_mapping": proxy_missing.selection_status
        == "subject_mapping_required"
        and not proxy_missing.matrix_receipts,
        "proxy_subject_binding": proxy_bound.subject_mapping.status == "caller_confirmed"
        and proxy_bound.subject_mapping.subject_position == 2
        and proxy_bound.selection_status == "single_review_candidate",
        "self_subject_mapping_has_source_receipt": unique.subject_mapping.source_rule_ids
        == ("SELF-TO-SHI",)
        and bool(unique.subject_mapping.source_refs),
        "proxy_relationship_never_uses_self_scope_mapping":
        proxy_relationship_mapped_attempt.selection_status == "manual_relation_required"
        and proxy_relationship_mapped_attempt.relation_decision.status
        == "manual_relation_required"
        and not proxy_relationship_mapped_attempt.matrix_receipts,
        "proxy_relationship_manual_mapping_never_contributes":
        proxy_relationship_manual.selection_status == "manual_unvalidated_mapping"
        and proxy_relationship_manual.relation_decision.manual_unvalidated
        and not any(item.contributes for item in proxy_relationship_manual.candidates),
        "unique_visible_candidate": len(unique_visible) == 1
        and unique.matrix_receipts[0].focus_selection_status == "unique_candidate"
        and unique.matrix_receipts[0].selected_position == unique_visible[0].position,
        "unique_is_provisional_review_only": unique.selection_status
        == "single_review_candidate"
        and unique.provisional_candidate_id == unique_visible[0].candidate_id
        and "PROVISIONAL_REVIEW_CANDIDATE_ONLY"
        in unique_visible[0].decision_codes,
        "tie_requires_confirmation": tie.selection_status == "tie_needs_confirmation"
        and tie.provisional_candidate_id is None
        and len(tie_visible) == 2,
        "tie_does_not_forge_position": tie.matrix_receipts[0].request.interpretation.primary_position
        is None
        and tie.matrix_receipts[0].focus_selection_status == "ambiguous",
        "tie_paths_not_evaluated": tie.matrix_receipts[0].path_evaluation_status
        == "not_run_use_line_unconfirmed"
        and all(not item.path_receipts for item in tie_visible),
        "moving_preference_never_tiebreaks": any(
            item.moving and "prefer_moving_over_static" in item.source_preference_hits
            for item in tie_visible
        )
        and not any(item.contributes for item in tie_visible),
        "confirmed_position_can_form_provisional": position_confirmed.selection_status
        == "single_review_candidate"
        and position_confirmed.matrix_receipts[0].focus_selection_status == "confirmed"
        and position_confirmed.matrix_receipts[0].path_evaluation_status == "evaluated",
        "unresolved_position_no_provisional": unresolved.selection_status
        == "validity_unresolved"
        and unresolved.provisional_candidate_id is None
        and unresolved.matrix_receipts[0].focus_status == "unresolved",
        "conditional_paths_no_provisional": conditional.selection_status
        == "validity_conditional"
        and conditional.provisional_candidate_id is None
        and conditional.matrix_receipts[0].focus_status == "conditional"
        and "FOCUS_PATHS_DEFERRED"
        in conditional.matrix_receipts[0].focus_dependencies,
        "hidden_inventory_only": hidden.selection_status
        == "hidden_candidate_needs_confirmation"
        and bool(hidden_only)
        and not any(item.contributes for item in hidden_only)
        and all(item.path_evaluation_status == "not_run_hidden_never_primary" for item in hidden_only),
        "deterministic": unique.to_dict() == repeated.to_dict(),
        "selection_request_round_trip": SelectionRequest.from_mapping(
            unique_request.to_dict()
        ).to_dict()
        == unique_request.to_dict(),
        "matrix_request_and_hash_receipts_present": bool(unique.matrix_receipts)
        and all(
            item.validity_request_sha256 == item.request.canonical_sha256
            and len(item.validity_matrix_sha256) == 64
            and len(item.validity_trace_sha256) == 64
            for item in unique.matrix_receipts
        ),
        "matrix_inventory_hash_bound": payload["matrix_receipts_sha256"]
        == digest(payload["matrix_receipts"]),
        "candidate_inventory_hash_bound": payload["candidate_inventory_sha256"]
        == digest(payload["candidates"]),
        "trace_hash_bound": unique.trace_sha256 == _trace_sha256(unique),
        "report_hash_bound": unique.canonical_sha256
        == digest(unique.to_dict(include_hash=False)),
        "gate_priority_ordered": tuple(item.gate_id for item in unique.gate_receipts)
        == tuple(payload["gate_priority_receipt"])
        and all(
            left.order > right.order
            for left, right in zip(unique.gate_receipts, unique.gate_receipts[1:])
        ),
        "review_only": payload["selection_runtime_status"] == "review_only",
        "not_production": SELECTION_RUNTIME_PRODUCTION_ALLOWED is False
        and payload["production_allowed"] is False,
        "not_prediction": payload["prediction_validity"] == PREDICTION_VALIDITY,
        "source_profile_not_validated": source_profile["profile_status"] == "draft"
        and source_profile["evidence_level"] == "source_only"
        and source_profile["human_reviewed"] is False
        and source_profile["empirical_validation_source_family_count"] == 0,
        "no_final_keys": not _contains_key_concept(payload, ("final",)),
        "no_probability_keys": not _contains_key_concept(payload, ("probability",)),
        "no_timing_keys": not _contains_key_concept(payload, ("timing",)),
        "no_exact_date_or_event_outcome_keys": not _contains_key_concept(
            payload, ("exact_date", "event_outcome")
        ),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "check_count": len(checks),
        "method_id": payload["method_id"],
        "source_profile_sha256": SELECTION_SOURCE_PROFILE_SHA256,
        "topic_policy_sha256": SELECTION_TOPIC_POLICY_SHA256,
        "engineering_policy_sha256": SELECTION_ENGINEERING_POLICY_SHA256,
        "selection_priority_table_sha256": SELECTION_PRIORITY_TABLE_SHA256,
        "prediction_validity": PREDICTION_VALIDITY,
        "report_sha256": unique.canonical_sha256,
    }


__all__ = ["benchmark_liuyao_selection_runtime"]
