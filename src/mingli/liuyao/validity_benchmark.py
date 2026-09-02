from __future__ import annotations

from .advanced_runtime import AdvancedContextRequest
from .case_record import create_case_record
from .interpretation import InterpretationRequest
from .models import EventContract, LiuYaoCastInput
from .tables import PREDICTION_VALIDITY, digest
from .validity_matrix import (
    VALIDITY_ENGINEERING_POLICY_ID,
    VALIDITY_ENGINEERING_POLICY_SHA256,
    VALIDITY_MATRIX_PRODUCTION_ALLOWED,
    VALIDITY_RULE_PROFILE_ID,
    VALIDITY_RULE_PROFILE_SHA256,
    VALIDITY_PRIORITY_TABLE_SHA256,
    ValidityMatrixReport,
    ValidityRequest,
    build_validity_matrix,
)


def _record():
    return create_case_record(
        LiuYaoCastInput(
            case_id="SYNTHETIC-VALIDITY-MATRIX",
            question="synthetic validity matrix benchmark",
            line_values=(9, 8, 9, 6, 7, 7),
            event_contract=EventContract(
                target_event="synthetic validity event",
                deadline="2099-12-31",
                success_criteria="synthetic criterion",
                evidence_requirement="synthetic evidence",
            ),
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
            month_branch="丑",
            day_ganzhi="甲申",
        )
    )


def _active_path_record():
    return create_case_record(
        LiuYaoCastInput(
            case_id="SYNTHETIC-ACTIVE-PATH",
            question="synthetic active path benchmark",
            line_values=(7, 7, 7, 9, 7, 7),
            event_contract=EventContract(
                target_event="synthetic active path event",
                deadline="2099-12-31",
                success_criteria="synthetic active path criterion",
                evidence_requirement="synthetic active path evidence",
            ),
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
            month_branch="卯",
            day_ganzhi="丁卯",
        )
    )


def _request(*, reality_status: str = "unknown") -> ValidityRequest:
    reality_confirmed = reality_status != "unknown"
    return ValidityRequest(
        interpretation=InterpretationRequest(
            topic="general",
            use_relation="妻财",
            primary_position=4,
            calendar_context_confirmed=True,
            reality_status=reality_status,
            reality_facts=("synthetic verified blocker",) if reality_confirmed else (),
        ),
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=True,
            calendar_source_refs=("source:synthetic-calendar",),
        ),
        reality_evidence_confirmed=reality_confirmed,
        reality_evidence_refs=("source:synthetic-reality",) if reality_confirmed else (),
    )


def _unconfirmed_request() -> ValidityRequest:
    return ValidityRequest(
        interpretation=InterpretationRequest(
            topic="general",
            use_relation="妻财",
            primary_position=4,
            calendar_context_confirmed=False,
        ),
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=False,
        ),
    )


def _active_path_request() -> ValidityRequest:
    return ValidityRequest(
        interpretation=InterpretationRequest(
            topic="general",
            use_relation="兄弟",
            primary_position=5,
            calendar_context_confirmed=True,
        ),
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=True,
            calendar_source_refs=("source:synthetic-active-calendar",),
        ),
    )


def _contains_key_concept(value: object, targets: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        return any(
            any(
                target in str(key).lower().split("_")
                if target == "date"
                else target in str(key).lower()
                for target in targets
            )
            or _contains_key_concept(item, targets)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_key_concept(item, targets) for item in value)
    return False


def _expected_trace_sha256(report: ValidityMatrixReport) -> str:
    hits = [hit for node in report.nodes for hit in node.rule_hits]
    hits.extend(
        hit for item in report.hidden_candidates for hit in item.hidden_node.rule_hits
    )
    hits.extend(hit for item in report.hidden_candidates for hit in item.rule_hits)
    hits.extend(hit for edge in report.edges for hit in edge.rule_hits)
    return digest([item.to_dict() for item in sorted(hits, key=lambda hit: hit.trace_id)])


def _public_subobject_sha256(value: object, hash_field: str) -> str:
    assert isinstance(value, dict)
    payload = dict(value)
    payload.pop(hash_field)
    return digest(payload)


def _ledger_complete(report: ValidityMatrixReport) -> bool:
    nodes = tuple(report.nodes) + tuple(
        item.hidden_node for item in report.hidden_candidates
    )
    for node in nodes:
        opened = {
            obligation
            for hit in node.rule_hits
            for obligation in hit.opened_obligations
        }
        reasons = {hit.reason_code for hit in node.rule_hits}
        if not set(node.open_obligations).issubset(opened):
            return False
        if not set(node.relief_candidates).issubset(reasons):
            return False
    for hidden in report.hidden_candidates:
        opened = {
            obligation
            for hit in hidden.rule_hits
            for obligation in hit.opened_obligations
        }
        reasons = {hit.reason_code for hit in hidden.rule_hits}
        if not set(hidden.open_obligations).issubset(opened):
            return False
        if not set(hidden.release_candidates).issubset(reasons):
            return False
    return True


def _path_axes_valid(report: ValidityMatrixReport) -> bool:
    selected_node_id = f"original:{report.focus_selection.selected_position}"
    return bool(report.paths) and all(
        item.validity_status in {"active_candidate", "deferred"}
        and item.enumeration_status in {"retained", "profile_excluded"}
        and (
            (item.enumeration_status == "retained" and item.enumeration_reason is None)
            or (
                item.enumeration_status == "profile_excluded"
                and item.enumeration_reason is not None
            )
        )
        and item.candidate_graph_reaches_focus
        == (
            item.validity_status == "active_candidate"
            and item.enumeration_status == "retained"
            and item.target_node_id == selected_node_id
        )
        for item in report.paths
    )


def benchmark_liuyao_validity_matrix() -> dict[str, object]:
    record = _record()
    request = _request()
    report = build_validity_matrix(record, request)
    repeated = build_validity_matrix(record, request)
    blocked = build_validity_matrix(record, _request(reality_status="blocking"))
    unconfirmed = build_validity_matrix(record, _unconfirmed_request())
    active_path_report = build_validity_matrix(
        _active_path_record(),
        _active_path_request(),
    )
    payload = report.to_dict()
    conflict_codes = {item.code for item in report.conflicts}
    blocked_codes = {item.code for item in blocked.conflicts}
    moving_pair_ids = {
        (item.source_node_id, item.target_node_id)
        for item in report.edges
        if item.edge_kind == "moving_pair_candidate"
    }

    checks = {
        "deterministic": report.to_dict() == repeated.to_dict(),
        "request_round_trip": ValidityRequest.from_mapping(request.to_dict()).to_dict()
        == request.to_dict(),
        "explicit_focus_selected": report.focus_selection.status == "confirmed"
        and report.focus_selection.selected_position == 4,
        "focus_not_reopened": report.focus_status != "needs_confirmation",
        "void_month_break_conflict": "VOID_AND_MONTH_BREAK" in conflict_codes,
        "moving_to_use_edges": any(
            item.edge_kind == "moving_to_selected_use" for item in report.edges
        ),
        "two_way_moving_edges": bool(moving_pair_ids)
        and all((target, source) in moving_pair_ids for source, target in moving_pair_ids),
        "cross_position_changed_pruned": any(
            item.prune_reason == "CHANGED_CROSS_POSITION_EXCLUDED"
            for item in report.edges
        ),
        "maximum_two_hops": all(len(item.edge_ids) <= 2 for item in report.paths),
        "node_four_axes": bool(report.nodes)
        and all(
            item.structural_eligibility == "retained_candidate"
            and item.current_force
            in {"unknown_context", "unresolved", "constrained", "available_candidate"}
            and item.manifestation_state
            in {"unknown_context", "unresolved", "deferred", "conditional", "candidate"}
            and item.role_polarity in {"selected_use", "unassigned"}
            for item in report.nodes
        ),
        "hidden_self_gate": bool(report.hidden_candidates)
        and all(
            not (
                set(item.hidden_node.open_obligations)
                - {
                    "CALENDAR_PROVENANCE_UNCONFIRMED",
                    "CALENDAR_MONTH_MISSING",
                    "CALENDAR_DAY_MISSING",
                }
            )
            or "HIDDEN_SELF_VALIDITY_OPEN" in item.open_obligations
            for item in report.hidden_candidates
        ),
        "obligation_ledger_complete": _ledger_complete(report),
        "inventory_hidden_self_dependencies": all(
            set(item.hidden_node.open_obligations + item.open_obligations).issubset(
                report.inventory_dependencies
            )
            for item in report.hidden_candidates
        ),
        "unconfirmed_calendar_no_fact_leak": unconfirmed.focus_status
        == "calendar_unconfirmed"
        and all(
            item.open_obligations == ("CALENDAR_PROVENANCE_UNCONFIRMED",)
            and all(hit.policy_id == VALIDITY_ENGINEERING_POLICY_ID for hit in item.rule_hits)
            for item in tuple(unconfirmed.nodes)
            + tuple(hidden.hidden_node for hidden in unconfirmed.hidden_candidates)
        ),
        "path_dual_axes": _path_axes_valid(report)
        and _path_axes_valid(active_path_report)
        and {
            item.validity_status
            for item in report.paths + active_path_report.paths
        }
        == {"active_candidate", "deferred"}
        and {
            item.candidate_graph_reaches_focus
            for item in report.paths + active_path_report.paths
        }
        == {True, False},
        "path_exclusion_receipts": {
            "PATH_CYCLE_PRUNED",
            "PATH_LENGTH_LIMIT",
        }.issubset(conflict_codes)
        and any(item.enumeration_reason == "PATH_CYCLE_PRUNED" for item in report.paths)
        and any(item.enumeration_reason == "PATH_LENGTH_LIMIT" for item in report.paths),
        "reality_block_requires_confirmed_evidence": blocked.focus_status
        == "reality_blocked"
        and blocked.reality_override == "blocking_confirmed_with_bound_refs"
        and "REALITY_HARD_BLOCK_CONFIRMED" in blocked_codes,
        "review_only": payload["validity_matrix_status"] == "review_only",
        "not_production": VALIDITY_MATRIX_PRODUCTION_ALLOWED is False
        and payload["production_allowed"] is False,
        "not_prediction": payload["prediction_validity"] == PREDICTION_VALIDITY,
        "draft_source_only_profile": payload["rule_profile"]["profile_id"]
        == VALIDITY_RULE_PROFILE_ID
        and payload["rule_profile"]["profile_status"] == "draft"
        and payload["rule_profile"]["evidence_level"] == "source_only"
        and payload["rule_profile"]["human_reviewed"] is False
        and payload["rule_profile"]["active_rule_source_family_count"] == 1
        and payload["rule_profile"]["referenced_text_family_count"] == 2
        and payload["rule_profile"]["empirical_validation_source_family_count"] == 0,
        "profile_hash_bound": payload["rule_profile"]["profile_sha256"]
        == VALIDITY_RULE_PROFILE_SHA256,
        "profile_hash_recomputable": _public_subobject_sha256(
            payload["rule_profile"], "profile_sha256"
        )
        == VALIDITY_RULE_PROFILE_SHA256,
        "engineering_policy_hash_bound": payload["engineering_policy"]["policy_sha256"]
        == VALIDITY_ENGINEERING_POLICY_SHA256
        and payload["engineering_policy_sha256"]
        == VALIDITY_ENGINEERING_POLICY_SHA256,
        "engineering_policy_hash_recomputable": _public_subobject_sha256(
            payload["engineering_policy"], "policy_sha256"
        )
        == VALIDITY_ENGINEERING_POLICY_SHA256,
        "priority_table_hash_recomputable": digest(
            {
                "priority_bands": payload["engineering_policy"]["priority_bands"],
                "precondition_gates": payload["engineering_policy"]["precondition_gates"],
                "gate_priority": payload["engineering_policy"]["gate_priority"],
            }
        )
        == VALIDITY_PRIORITY_TABLE_SHA256,
        "report_hash_bound": report.canonical_sha256
        == digest(report.to_dict(include_hash=False)),
        "trace_hash_bound": report.trace_sha256 == _expected_trace_sha256(report),
        "no_probability": not _contains_key_concept(payload, ("probability",)),
        "no_confidence_or_score": not _contains_key_concept(
            payload,
            ("confidence", "score"),
        ),
        "no_timing_date_or_deadline": not _contains_key_concept(
            payload,
            ("timing", "date", "deadline"),
        ),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "method_id": payload["method_id"],
        "rule_profile_id": VALIDITY_RULE_PROFILE_ID,
        "rule_profile_sha256": VALIDITY_RULE_PROFILE_SHA256,
        "engineering_policy_sha256": VALIDITY_ENGINEERING_POLICY_SHA256,
        "prediction_validity": PREDICTION_VALIDITY,
        "report_sha256": report.canonical_sha256,
    }


__all__ = ["benchmark_liuyao_validity_matrix"]
