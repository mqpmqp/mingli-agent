from __future__ import annotations

import re
from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

import mingli.liuyao as liuyao_package
import mingli.liuyao.selection_runtime as selection_runtime_module
from mingli.liuyao.advanced_runtime import AdvancedContextRequest
from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.selection_profile import (
    SELECTION_ENGINEERING_POLICY,
    SELECTION_ENGINEERING_POLICY_SHA256,
    SELECTION_GATE_PRIORITY,
    SELECTION_SOURCE_PROFILE_SHA256,
    SELECTION_TOPIC_POLICY_SHA256,
)
from mingli.liuyao.selection_runtime import (
    SELECTION_RUNTIME_PRODUCTION_ALLOWED,
    SELECTION_RUNTIME_STATUS,
    SelectionRequest,
    build_selection_runtime_report,
)
from mingli.liuyao.tables import PREDICTION_VALIDITY, digest
from mingli.liuyao.validation import LiuYaoError
from mingli.liuyao.validity_matrix import (
    VALIDITY_ENGINEERING_POLICY_SHA256,
    VALIDITY_PRIORITY_TABLE_SHA256,
    VALIDITY_RULE_PROFILE_SHA256,
)


def _record(
    *,
    case_id: str = "SELECTION-RUNTIME-TEST",
    lines: tuple[int, ...] = (7, 7, 7, 9, 7, 7),
    month_branch: str | None = "卯",
    day_ganzhi: str | None = "丁卯",
    casting_mode: str = "self",
    proxy_relationship: str | None = None,
    deadline: str = "2099-12-31",
    reality_facts: tuple[str, ...] = (),
):
    return create_case_record(
        LiuYaoCastInput(
            case_id=case_id,
            question="冻结的合成验收事件是否达到标准",
            line_values=lines,
            event_contract=EventContract(
                target_event="冻结的合成验收事件",
                deadline=deadline,
                success_criteria="满足冻结的合成布尔标准",
                evidence_requirement="提供可核验的合成证据",
            ),
            completed_at="2026-09-03T00:00:00+00:00",
            location="合成测试地点",
            casting_mode=casting_mode,
            proxy_relationship=proxy_relationship,
            month_branch=month_branch,
            day_ganzhi=day_ganzhi,
            reality_facts=reality_facts,
        )
    )


def _request(
    record,
    *,
    topic: str = "exam",
    focus_dimension: str | None = None,
    contract_focus_confirmed: bool = True,
    calendar_confirmed: bool = True,
    reality_status: str = "unknown",
    reality_facts: tuple[str, ...] = (),
    reality_confirmed: bool | None = None,
    reality_refs: tuple[str, ...] | None = None,
    **overrides: Any,
) -> SelectionRequest:
    focus = focus_dimension or {
        "exam": "current_exam",
        "relationship_reconciliation": "reconciliation",
        "pregnancy": "conception_opportunity",
    }[topic]
    if reality_confirmed is None:
        reality_confirmed = reality_status != "unknown"
    if reality_refs is None:
        reality_refs = (
            ("fixture:reality",) if reality_status != "unknown" else ()
        )
    values: dict[str, Any] = {
        "topic": topic,
        "focus_dimension": focus,
        "case_record_sha256": record.canonical_sha256,
        "event_contract_sha256": digest(record.cast.event_contract.to_dict()),
        "advanced_context": AdvancedContextRequest(
            calendar_context_confirmed=calendar_confirmed,
            calendar_source_refs=("fixture:calendar",) if calendar_confirmed else (),
        ),
        "contract_focus_confirmed": contract_focus_confirmed,
        "contract_source_refs": (
            ("fixture:event-contract",) if contract_focus_confirmed else ()
        ),
        "reality_status": reality_status,
        "reality_facts": reality_facts,
        "reality_evidence_confirmed": reality_confirmed,
        "reality_evidence_refs": reality_refs,
    }
    if topic == "exam":
        values.update(
            exam_scope="martial",
            exam_scope_confirmed=True,
            exam_scope_refs=("fixture:exam-scope",),
        )
    elif topic == "relationship_reconciliation":
        values.update(
            relationship_pairing_scope="male_subject_female_spouse",
            relationship_pairing_confirmed=True,
            relationship_pairing_refs=("fixture:relationship-scope",),
        )
    else:
        values.update(
            pregnancy_method="children_relation",
            pregnancy_method_confirmed=True,
            pregnancy_method_refs=("fixture:pregnancy-method",),
        )
    values.update(overrides)
    return SelectionRequest(**values)


def _raises_code(code: str, callback) -> None:
    with pytest.raises(LiuYaoError) as raised:
        callback()
    assert raised.value.code == code


def _rehash(value: dict[str, object]) -> None:
    value.pop("canonical_sha256", None)
    value["canonical_sha256"] = digest(value)


def _candidate_projection(report) -> tuple[object, ...]:
    return (
        report.selection_status,
        report.provisional_candidate_id,
        tuple(
            (
                item.source_kind,
                item.relation,
                item.position,
                item.node_id,
                item.node_state,
                item.contributes,
            )
            for item in report.candidates
        ),
    )


def _all_keys(value: object) -> tuple[str, ...]:
    keys: list[str] = []

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                keys.append(str(key))
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return tuple(keys)


def test_selection_request_and_report_bind_complete_input_chain() -> None:
    record = _record()
    request = _request(record)
    before = request.to_dict()
    report = build_selection_runtime_report(record, request)
    payload = report.to_dict()

    assert request.to_dict() == before
    assert report.case_record_sha256 == record.canonical_sha256
    assert report.cast_sha256 == record.cast.canonical_sha256
    assert report.chart_sha256 == record.chart.canonical_sha256
    assert report.event_contract_sha256 == digest(record.cast.event_contract.to_dict())
    assert payload["selection_request_sha256"] == request.canonical_sha256
    assert payload["canonical_sha256"] == digest(report.to_dict(include_hash=False))
    assert len(report.trace_sha256) == 64
    assert report.matrix_receipts
    for receipt in report.matrix_receipts:
        assert receipt.validity_request_sha256 == receipt.request.canonical_sha256
        assert len(receipt.validity_matrix_sha256) == 64
        assert len(receipt.validity_trace_sha256) == 64


def test_selection_request_is_frozen_and_rejects_unknown_fields() -> None:
    record = _record()
    request = _request(record)
    with pytest.raises(FrozenInstanceError):
        request.topic = "pregnancy"  # type: ignore[misc]

    payload = request.to_dict()
    payload["priority_override"] = {"reality_gate": 0}
    _raises_code("INVALID_INPUT", lambda: SelectionRequest.from_mapping(payload))


@pytest.mark.parametrize(
    "field",
    (
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
    ),
)
def test_selection_request_rejects_null_array_fields(field: str) -> None:
    record = _record()
    payload = _request(record).to_dict(include_hash=False)
    payload[field] = None

    _raises_code("INVALID_INPUT", lambda: SelectionRequest.from_mapping(payload))


@pytest.mark.parametrize("scope", ("outer", "advanced"))
def test_selection_request_rejects_outer_and_nested_hash_tampering(scope: str) -> None:
    payload = _request(_record()).to_dict()
    if scope == "outer":
        payload["focus_dimension"] = "system_fit"
    else:
        advanced = payload["advanced_context"]
        assert isinstance(advanced, dict)
        advanced["calendar_source_refs"] = ["fixture:changed"]

    _raises_code("RECORD_TAMPERED", lambda: SelectionRequest.from_mapping(payload))


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    (
        ("source_profile_id", "other", "UNSUPPORTED_RULE_PROFILE"),
        ("topic_policy_id", "other", "UNSUPPORTED_RULE_PROFILE"),
        ("engineering_policy_id", "other", "UNSUPPORTED_RULE_PROFILE"),
    ),
)
def test_selection_request_rejects_profile_overrides(
    field: str,
    value: str,
    expected: str,
) -> None:
    payload = _request(_record()).to_dict()
    payload[field] = value
    _rehash(payload)
    _raises_code(expected, lambda: SelectionRequest.from_mapping(payload))


def test_only_runtime_builder_is_exposed_as_selection_entrypoint() -> None:
    assert not hasattr(liuyao_package, "build_selection_report")
    assert not hasattr(liuyao_package, "AutoSelectionRequest")


def test_case_and_event_contract_hashes_are_required_and_bound() -> None:
    record = _record()
    payload = _request(record).to_dict()
    payload.pop("case_record_sha256")
    payload.pop("canonical_sha256")
    _raises_code("CASE_RECORD_HASH_REQUIRED", lambda: SelectionRequest.from_mapping(payload))

    payload = _request(record).to_dict()
    payload.pop("event_contract_sha256")
    payload.pop("canonical_sha256")
    _raises_code("CONTRACT_HASH_REQUIRED", lambda: SelectionRequest.from_mapping(payload))

    stale_request = _request(record)
    changed_record = _record(lines=(6, 6, 6, 6, 6, 6))
    _raises_code(
        "CASE_RECORD_BINDING_MISMATCH",
        lambda: build_selection_runtime_report(changed_record, stale_request),
    )

    request = _request(record, event_contract_sha256="0" * 64)
    _raises_code(
        "CONTRACT_BINDING_MISMATCH",
        lambda: build_selection_runtime_report(record, request),
    )


@pytest.mark.parametrize(
    ("overrides", "expected"),
    (
        ({"contract_focus_confirmed": True, "contract_source_refs": ()}, "CONTRACT_SOURCE_REQUIRED"),
        ({"contract_focus_confirmed": False, "contract_source_refs": ("fixture:contract",)}, "CONTRACT_CONFIRMATION_REQUIRED"),
    ),
)
def test_contract_confirmation_and_refs_are_atomic(
    overrides: dict[str, object],
    expected: str,
) -> None:
    record = _record()
    _raises_code(expected, lambda: _request(record, **overrides))


def test_contract_unconfirmed_stops_before_matrix() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _request(record, contract_focus_confirmed=False),
    )

    assert report.selection_status == "contract_unconfirmed"
    assert report.matrix_receipts == ()
    assert report.candidates == ()
    assert report.provisional_candidate_id is None


def test_exam_topic_pack_and_source_scope_are_fail_closed() -> None:
    record = _record()
    report = build_selection_runtime_report(record, _request(record))
    dimensions = report.to_dict()["topic_pack_dimensions"]
    assert isinstance(dimensions, list)

    assert [item["dimension"] for item in dimensions] == [
        "system_fit",
        "current_exam",
        "position_direction",
        "preparation_strategy",
    ]
    assert report.relation_decision.status == "source_single_relation"
    assert report.relation_decision.active_roles[0].relation == "官鬼"
    assert report.selection_status == "single_review_candidate"
    assert report.provisional_candidate_id == "exam_officer:visible:4"

    modern = build_selection_runtime_report(
        record,
        _request(
            record,
            exam_scope="modern_civil_service_unspecified",
            exam_scope_confirmed=True,
            exam_scope_refs=("fixture:modern-exam",),
        ),
    )
    assert modern.selection_status == "exam_scope_unresolved"
    assert modern.relation_decision.source_relation_candidates == ("官鬼", "父母")
    assert modern.matrix_receipts == ()


def test_exam_written_scope_preserves_dual_relation_until_caller_narrows() -> None:
    record = _record()
    dual = build_selection_runtime_report(
        record,
        _request(
            record,
            exam_scope="written_or_cultural",
            exam_scope_confirmed=True,
            exam_scope_refs=("fixture:written-exam",),
        ),
    )

    assert dual.selection_status == "relation_confirmation_required"
    assert dual.relation_decision.status == "source_dual_relation"
    assert dual.relation_decision.source_relation_candidates == ("官鬼", "父母")
    assert {item.relation for item in dual.matrix_receipts} == {"官鬼", "父母"}
    assert dual.provisional_candidate_id is None
    assert all(not item.contributes for item in dual.candidates)

    narrowed = build_selection_runtime_report(
        record,
        _request(
            record,
            exam_scope="written_or_cultural",
            exam_scope_confirmed=True,
            exam_scope_refs=("fixture:written-exam",),
            relation_choice="官鬼",
            relation_choice_confirmed=True,
            relation_choice_refs=("fixture:relation-choice",),
        ),
    )
    assert narrowed.relation_decision.status == "caller_narrowed_source_relations"
    assert narrowed.selection_status == "single_review_candidate"
    assert narrowed.provisional_candidate_id == "exam_officer:visible:4"


@pytest.mark.parametrize(
    ("focus", "expected"),
    (
        ("system_fit", "focus_outside_single_cast"),
        ("position_direction", "reality_context_required"),
        ("preparation_strategy", "reality_context_required"),
    ),
)
def test_exam_non_structural_dimensions_cannot_be_bypassed(
    focus: str,
    expected: str,
) -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _request(
            record,
            focus_dimension=focus,
            relation_choice="官鬼",
            relation_choice_confirmed=True,
            relation_choice_refs=("fixture:attempted-override",),
        ),
    )

    assert report.selection_status == expected
    assert report.matrix_receipts == ()
    assert report.provisional_candidate_id is None


def test_relationship_pack_has_four_independent_layers_and_scoped_mapping() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _request(record, topic="relationship_reconciliation"),
    )
    dimensions = report.to_dict()["topic_pack_dimensions"]
    assert isinstance(dimensions, list)

    assert [item["dimension"] for item in dimensions] == [
        "bond",
        "recontact",
        "reconciliation",
        "stability",
    ]
    assert report.relation_decision.status == "source_scope_mapped"
    assert report.relation_decision.active_roles[0].relation == "妻财"
    assert report.selection_status == "single_review_candidate"
    assert report.provisional_candidate_id == "relationship_counterparty:visible:2"

    female = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="relationship_reconciliation",
            relationship_pairing_scope="female_subject_male_spouse",
            relationship_pairing_confirmed=True,
            relationship_pairing_refs=("fixture:relationship-scope",),
        ),
    )
    assert female.relation_decision.active_roles[0].relation == "官鬼"
    assert female.provisional_candidate_id == "relationship_counterparty:visible:4"


@pytest.mark.parametrize("focus_dimension", ("bond", "recontact"))
def test_relationship_structural_focuses_execute_their_own_matrix(
    focus_dimension: str,
) -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="relationship_reconciliation",
            focus_dimension=focus_dimension,
        ),
    )

    assert report.request.focus_dimension == focus_dimension
    assert report.selection_status == "single_review_candidate"
    assert len(report.matrix_receipts) == 1
    assert report.provisional_candidate_id == "relationship_counterparty:visible:2"


def test_relationship_outside_source_scope_never_auto_contributes() -> None:
    record = _record()
    blocked = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="relationship_reconciliation",
            relationship_pairing_scope="outside_traditional_scope",
            relationship_pairing_confirmed=True,
            relationship_pairing_refs=("fixture:outside-scope",),
        ),
    )
    assert blocked.selection_status == "manual_relation_required"
    assert blocked.matrix_receipts == ()

    manual = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="relationship_reconciliation",
            relationship_pairing_scope="outside_traditional_scope",
            relationship_pairing_confirmed=True,
            relationship_pairing_refs=("fixture:outside-scope",),
            relation_choice="妻财",
            relation_choice_confirmed=True,
            relation_choice_refs=("fixture:manual-relation",),
            relation_choice_reason="调用方只要求保留未经来源验证的审计候选",
        ),
    )
    assert manual.selection_status == "manual_unvalidated_mapping"
    assert manual.relation_decision.manual_unvalidated is True
    assert manual.matrix_receipts
    assert manual.provisional_candidate_id is None
    assert all(not item.contributes for item in manual.candidates)
    source_gate = next(
        item for item in manual.gate_receipts if item.gate_id == "source_scope_method_gate"
    )
    relation_gate = next(
        item for item in manual.gate_receipts if item.gate_id == "relation_resolution_gate"
    )
    assert source_gate.status == "review_required"
    assert source_gate.reason_code == "RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED"
    assert relation_gate.status == "review_required"
    assert relation_gate.reason_code == "RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED"


def test_relationship_stability_requires_bound_reality_context() -> None:
    record = _record()
    blocked = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="relationship_reconciliation",
            focus_dimension="stability",
        ),
    )
    assert blocked.selection_status == "reality_context_required"
    assert blocked.matrix_receipts == ()

    allowed = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="relationship_reconciliation",
            focus_dimension="stability",
            reality_status="supportive",
            reality_facts=("已确认的合成现实关系资料",),
        ),
    )
    assert allowed.selection_status == "single_review_candidate"
    assert allowed.matrix_receipts


def test_pregnancy_source_method_conflict_and_professional_boundaries() -> None:
    record = _record()
    conflict = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="pregnancy",
            pregnancy_method="not_applicable",
            pregnancy_method_confirmed=False,
            pregnancy_method_refs=(),
        ),
    )
    assert conflict.selection_status == "source_method_conflict"
    assert conflict.relation_decision.method_options == (
        "children_relation",
        "fetal_marker",
    )
    assert conflict.matrix_receipts == ()

    children = build_selection_runtime_report(
        record,
        _request(record, topic="pregnancy"),
    )
    assert children.relation_decision.selected_method == "children_relation"
    assert children.relation_decision.active_roles[0].relation == "子孙"
    assert children.selection_status == "single_review_candidate"
    assert children.provisional_candidate_id == "pregnancy_children:visible:1"

    fetal = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="pregnancy",
            pregnancy_method="fetal_marker",
            pregnancy_method_confirmed=True,
            pregnancy_method_refs=("fixture:fetal-method",),
        ),
    )
    assert fetal.selection_status == "unsupported_method"
    assert fetal.matrix_receipts == ()


@pytest.mark.parametrize(
    "focus",
    ("medical_confirmation", "pregnancy_stability", "medical_factors"),
)
def test_pregnancy_professional_focus_cannot_be_overridden(focus: str) -> None:
    record = _record()
    _raises_code(
        "INVALID_INPUT",
        lambda: _request(
            record,
            topic="pregnancy",
            focus_dimension=focus,
            relation_choice="子孙",
            relation_choice_confirmed=True,
            relation_choice_refs=("fixture:attempted-override",),
        ),
    )
    report = build_selection_runtime_report(
        record,
        _request(record, topic="pregnancy", focus_dimension=focus),
    )
    assert report.selection_status == "professional_only"
    assert report.matrix_receipts == ()
    assert report.provisional_candidate_id is None


def test_self_subject_binds_shi_and_rejects_caller_override() -> None:
    record = _record()
    report = build_selection_runtime_report(record, _request(record))
    assert report.subject_mapping.status == "bound_to_shi"
    assert report.subject_mapping.subject_position == record.chart.original.shi_line
    assert report.subject_mapping.source_rule_ids == ("SELF-TO-SHI",)
    assert report.subject_mapping.source_refs == (
        "src_039:print163-164/pdf163-164",
        "src_037:print179-180/pdf194-195",
    )

    request = _request(
        record,
        subject_mapping_confirmed=True,
        subject_position=2,
        subject_mapping_refs=("fixture:subject",),
    )
    _raises_code(
        "SUBJECT_MAPPING_NOT_APPLICABLE",
        lambda: build_selection_runtime_report(record, request),
    )


def test_proxy_requires_confirmed_subject_mapping() -> None:
    record = _record(casting_mode="proxy", proxy_relationship="朋友")
    blocked = build_selection_runtime_report(record, _request(record))
    assert blocked.selection_status == "subject_mapping_required"
    assert blocked.matrix_receipts == ()
    assert blocked.provisional_candidate_id is None

    allowed = build_selection_runtime_report(
        record,
        _request(
            record,
            subject_mapping_confirmed=True,
            subject_position=2,
            subject_mapping_refs=("fixture:proxy-subject",),
        ),
    )
    assert allowed.subject_mapping.status == "caller_confirmed"
    assert allowed.subject_mapping.subject_position == 2
    assert allowed.subject_mapping.source_rule_ids == ()
    assert allowed.subject_mapping.source_refs == ("fixture:proxy-subject",)
    assert allowed.matrix_receipts


def test_proxy_relationship_pairing_never_extends_self_cast_source_scope() -> None:
    record = _record(casting_mode="proxy", proxy_relationship="朋友")
    report = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="relationship_reconciliation",
            subject_mapping_confirmed=True,
            subject_position=2,
            subject_mapping_refs=("fixture:proxy-subject",),
        ),
    )

    assert report.subject_mapping.status == "caller_confirmed"
    assert report.relation_decision.status != "source_scope_mapped"
    assert report.selection_status == "manual_relation_required"
    assert "RELATIONSHIP_SOURCE_SCOPE_NOT_COVERED" in report.dependencies
    assert report.matrix_receipts == ()
    assert report.candidates == ()
    assert report.provisional_candidate_id is None


@pytest.mark.parametrize(
    ("overrides", "expected"),
    (
        ({"subject_mapping_confirmed": True}, "SUBJECT_POSITION_REQUIRED"),
        ({"subject_position": 2}, "SUBJECT_CONFIRMATION_REQUIRED"),
        ({"subject_mapping_refs": ("fixture:subject",)}, "SUBJECT_CONFIRMATION_REQUIRED"),
    ),
)
def test_subject_confirmation_shape_is_strict(
    overrides: dict[str, object],
    expected: str,
) -> None:
    _raises_code(expected, lambda: _request(_record(), **overrides))


def test_reality_hard_block_precedes_calendar_and_candidate_selection() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _request(
            record,
            calendar_confirmed=False,
            reality_status="blocking",
            reality_facts=("资格已经由合成现实证据确认不成立",),
        ),
    )
    assert report.selection_status == "reality_blocked"
    assert report.matrix_receipts == ()
    assert report.candidates == ()
    assert report.provisional_candidate_id is None
    assert report.gate_receipts[1].gate_id == "reality_gate"
    assert report.gate_receipts[1].status == "blocked"


@pytest.mark.parametrize(
    ("status", "facts", "confirmed", "refs", "expected"),
    (
        ("unknown", ("fact",), False, (), "REALITY_STATUS_REQUIRED"),
        ("blocking", ("fact",), False, ("ref",), "REALITY_CONFIRMATION_REQUIRED"),
        ("blocking", ("fact",), True, (), "REALITY_EVIDENCE_REQUIRED"),
    ),
)
def test_reality_evidence_shape_is_strict(
    status: str,
    facts: tuple[str, ...],
    confirmed: bool,
    refs: tuple[str, ...],
    expected: str,
) -> None:
    _raises_code(
        expected,
        lambda: _request(
            _record(),
            reality_status=status,
            reality_facts=facts,
            reality_confirmed=confirmed,
            reality_refs=refs,
        ),
    )


def test_frozen_cast_reality_facts_cannot_be_ignored() -> None:
    record = _record(reality_facts=("冻结案例现实事实",))
    _raises_code(
        "REALITY_CONTEXT_MISMATCH",
        lambda: build_selection_runtime_report(record, _request(record)),
    )


def test_unconfirmed_and_partial_calendar_never_build_candidate_matrix() -> None:
    complete = _record()
    unconfirmed = build_selection_runtime_report(
        complete,
        _request(complete, calendar_confirmed=False),
    )
    assert unconfirmed.selection_status == "calendar_unconfirmed"
    assert unconfirmed.matrix_receipts == ()
    assert unconfirmed.provisional_candidate_id is None

    partial_record = _record(day_ganzhi=None)
    partial = build_selection_runtime_report(
        partial_record,
        _request(partial_record),
    )
    assert partial.selection_status == "calendar_partial"
    assert partial.matrix_receipts == ()
    assert partial.provisional_candidate_id is None

    missing_record = _record(month_branch=None, day_ganzhi=None)
    _raises_code(
        "CALENDAR_CONTEXT_MISSING",
        lambda: build_selection_runtime_report(missing_record, _request(missing_record)),
    )


def test_unique_unresolved_visible_candidate_is_not_provisional() -> None:
    record = _record(lines=(6, 7, 7, 8, 7, 7))
    report = build_selection_runtime_report(record, _request(record))
    assert report.selection_status == "validity_unresolved"
    assert report.provisional_candidate_id is None
    assert [(item.position, item.node_state) for item in report.candidates] == [
        (3, "unresolved")
    ]
    assert all(not item.contributes for item in report.candidates)


def test_deferred_focus_paths_remain_conditional_and_do_not_contribute() -> None:
    record = _record(lines=(6, 6, 6, 6, 6, 6))
    report = build_selection_runtime_report(record, _request(record))

    assert report.selection_status == "validity_conditional"
    assert report.provisional_candidate_id is None
    assert report.matrix_receipts[0].focus_status == "conditional"
    assert "FOCUS_PATHS_DEFERRED" in report.matrix_receipts[0].focus_dependencies
    assert all(not item.contributes for item in report.candidates)


def test_moving_source_preference_does_not_break_same_tier_tie() -> None:
    record = _record(lines=(6, 7, 7, 8, 7, 7))
    report = build_selection_runtime_report(
        record,
        _request(record, topic="relationship_reconciliation"),
    )
    visible = [item for item in report.candidates if item.source_kind == "visible_original"]

    assert report.selection_status == "tie_needs_confirmation"
    assert report.provisional_candidate_id is None
    assert [(item.position, item.moving, item.node_state) for item in visible] == [
        (1, True, "available_candidate"),
        (4, False, "available_candidate"),
    ]
    assert "prefer_moving_over_static" in visible[0].source_preference_hits
    assert all(item.to_dict()["source_preferences_applied_to_ranking"] is False for item in visible)
    assert all(not item.contributes for item in visible)


def test_nearer_shi_preference_requires_same_motion_comparison_group() -> None:
    record = _record(lines=(6, 7, 7, 8, 7, 7))
    report = build_selection_runtime_report(
        record,
        _request(record, topic="relationship_reconciliation"),
    )
    visible = tuple(
        item
        for item in report.candidates
        if item.source_kind == "visible_original" and item.position in {1, 4}
    )

    assert {item.moving for item in visible} == {False, True}
    assert all("prefer_nearer_shi" not in item.source_preference_hits for item in visible)


def test_rejects_upstream_matrix_from_another_validity_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record()
    request = _request(record)
    real_builder = selection_runtime_module.build_validity_matrix

    def wrong_relation_builder(record_arg, validity_request):
        wrong_interpretation = replace(
            validity_request.interpretation,
            use_relation="兄弟",
        )
        wrong_request = replace(validity_request, interpretation=wrong_interpretation)
        return real_builder(record_arg, wrong_request)

    monkeypatch.setattr(
        selection_runtime_module,
        "build_validity_matrix",
        wrong_relation_builder,
    )
    _raises_code(
        "VALIDITY_MATRIX_BINDING_MISMATCH",
        lambda: build_selection_runtime_report(record, request),
    )


def test_rejects_upstream_matrix_that_truncates_candidate_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record(lines=(6, 7, 7, 8, 7, 7))
    request = _request(record, topic="relationship_reconciliation")
    real_builder = selection_runtime_module.build_validity_matrix

    def truncated_inventory_builder(record_arg, validity_request):
        matrix = real_builder(record_arg, validity_request)
        forged_nodes = tuple(
            replace(
                node,
                selected_use=node.node_id == "original:1",
                role_polarity=(
                    "selected_use" if node.node_id == "original:1" else "unassigned"
                ),
                state=(
                    "available_candidate"
                    if node.node_id == "original:1"
                    else node.state
                ),
            )
            for node in matrix.nodes
        )
        forged_focus = replace(
            matrix.focus_selection,
            status="unique_candidate",
            selected_position=1,
            candidate_positions=(1,),
        )
        return replace(
            matrix,
            focus_selection=forged_focus,
            focus_status="available_candidate",
            focus_dependencies=(),
            nodes=forged_nodes,
        )

    monkeypatch.setattr(
        selection_runtime_module,
        "build_validity_matrix",
        truncated_inventory_builder,
    )
    _raises_code(
        "VALIDITY_MATRIX_BINDING_MISMATCH",
        lambda: build_selection_runtime_report(record, request),
    )


def test_rejects_upstream_available_focus_with_open_node_obligations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record(lines=(6, 7, 7, 8, 7, 7))
    request = _request(record)
    real_builder = selection_runtime_module.build_validity_matrix

    def forged_available_focus_builder(record_arg, validity_request):
        matrix = real_builder(record_arg, validity_request)
        assert matrix.focus_selection.status == "unique_candidate"
        assert matrix.focus_status != "available_candidate"
        assert matrix.focus_dependencies
        return replace(matrix, focus_status="available_candidate")

    monkeypatch.setattr(
        selection_runtime_module,
        "build_validity_matrix",
        forged_available_focus_builder,
    )
    _raises_code(
        "VALIDITY_MATRIX_BINDING_MISMATCH",
        lambda: build_selection_runtime_report(record, request),
    )


def test_rejects_upstream_available_focus_with_unresolved_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record(lines=(9, 9, 9, 9, 9, 9))
    request = _request(record)
    real_builder = selection_runtime_module.build_validity_matrix

    def forged_available_focus_builder(record_arg, validity_request):
        matrix = real_builder(record_arg, validity_request)
        selected_id = f"original:{matrix.focus_selection.selected_position}"
        selected = next(node for node in matrix.nodes if node.node_id == selected_id)
        assert selected.state == "available_candidate"
        assert matrix.focus_status == "unresolved"
        assert "OPPOSING_DIRECT_PATHS" in {
            conflict.code for conflict in matrix.conflicts
        }
        return replace(
            matrix,
            focus_status="available_candidate",
            focus_dependencies=(),
        )

    monkeypatch.setattr(
        selection_runtime_module,
        "build_validity_matrix",
        forged_available_focus_builder,
    )
    _raises_code(
        "VALIDITY_MATRIX_BINDING_MISMATCH",
        lambda: build_selection_runtime_report(record, request),
    )


def test_rejects_upstream_matrix_with_tampered_trace_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record()
    request = _request(record)
    real_builder = selection_runtime_module.build_validity_matrix

    def tampered_trace_builder(record_arg, validity_request):
        return replace(
            real_builder(record_arg, validity_request),
            trace_sha256="1" * 64,
        )

    monkeypatch.setattr(
        selection_runtime_module,
        "build_validity_matrix",
        tampered_trace_builder,
    )
    _raises_code(
        "VALIDITY_MATRIX_BINDING_MISMATCH",
        lambda: build_selection_runtime_report(record, request),
    )


@pytest.mark.parametrize("position", (1, 4))
def test_caller_confirmed_position_resolves_tie_only_as_review_candidate(
    position: int,
) -> None:
    record = _record(lines=(6, 7, 7, 8, 7, 7))
    report = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="relationship_reconciliation",
            primary_position=position,
            primary_position_confirmed=True,
            primary_position_refs=("fixture:position",),
        ),
    )
    assert report.selection_status == "single_review_candidate"
    assert report.provisional_candidate_id == f"relationship_counterparty:visible:{position}"
    assert [item.position for item in report.candidates if item.contributes] == [position]


def test_confirmed_position_must_match_active_relation() -> None:
    record = _record(lines=(6, 7, 7, 8, 7, 7))
    request = _request(
        record,
        topic="relationship_reconciliation",
        primary_position=2,
        primary_position_confirmed=True,
        primary_position_refs=("fixture:position",),
    )
    _raises_code(
        "USE_GOD_MISMATCH",
        lambda: build_selection_runtime_report(record, request),
    )


def test_hidden_only_relation_is_inventory_never_contribution() -> None:
    record = _record(lines=(7, 8, 8, 6, 7, 7))
    report = build_selection_runtime_report(record, _request(record))
    assert report.selection_status == "hidden_candidate_needs_confirmation"
    assert report.provisional_candidate_id is None
    assert report.candidates
    assert all(item.source_kind == "hidden" for item in report.candidates)
    assert all(item.visibility_state == "hidden_candidate" for item in report.candidates)
    assert all(not item.contributes for item in report.candidates)
    assert all(
        "HIDDEN_NEVER_AUTO_CONTRIBUTES" in item.decision_codes
        for item in report.candidates
    )


def test_changed_line_never_becomes_independent_use_candidate() -> None:
    report = build_selection_runtime_report(_record(), _request(_record()))
    assert report.candidates
    assert all(item.source_kind in {"visible_original", "hidden"} for item in report.candidates)
    assert all(not item.node_id.startswith("changed:") for item in report.candidates)


def test_path_conflict_propagates_to_selection_status() -> None:
    record = _record(lines=(9, 9, 9, 9, 9, 9))
    report = build_selection_runtime_report(record, _request(record))
    assert report.selection_status == "validity_unresolved"
    assert report.provisional_candidate_id is None
    assert "OPPOSING_DIRECT_PATHS" in report.matrix_receipts[0].conflict_codes


def test_path_conflict_is_only_attributed_to_selected_candidate() -> None:
    record = _record(lines=(6, 6, 6, 7, 6, 6))
    report = build_selection_runtime_report(
        record,
        _request(
            record,
            topic="relationship_reconciliation",
            primary_position=1,
            primary_position_confirmed=True,
            primary_position_refs=("fixture:selected-position",),
        ),
    )
    by_position = {item.position: item for item in report.candidates}

    assert "OPPOSING_DIRECT_PATHS" in report.matrix_receipts[0].conflict_codes
    assert "OPPOSING_DIRECT_PATHS" in by_position[1].conflict_codes
    assert "OPPOSING_DIRECT_PATHS" not in by_position[6].conflict_codes


def test_profile_subhashes_and_candidate_inventory_are_independently_recomputable() -> None:
    report = build_selection_runtime_report(_record(), _request(_record()))
    payload = report.to_dict()
    for field, hash_field, expected in (
        ("source_profile", "profile_sha256", SELECTION_SOURCE_PROFILE_SHA256),
        ("topic_policy", "policy_sha256", SELECTION_TOPIC_POLICY_SHA256),
        ("engineering_policy", "policy_sha256", SELECTION_ENGINEERING_POLICY_SHA256),
    ):
        child = dict(payload[field])
        supplied = child.pop(hash_field)
        assert supplied == expected
        assert digest(child) == supplied

    upstream = payload["upstream_validity_hashes"]
    assert upstream == {
        "rule_profile_sha256": VALIDITY_RULE_PROFILE_SHA256,
        "engineering_policy_sha256": VALIDITY_ENGINEERING_POLICY_SHA256,
        "priority_table_sha256": VALIDITY_PRIORITY_TABLE_SHA256,
    }
    assert payload["matrix_receipts_sha256"] == digest(payload["matrix_receipts"])
    assert payload["candidate_inventory_sha256"] == digest(payload["candidates"])


def test_public_policy_and_report_payload_are_mutation_safe() -> None:
    with pytest.raises(TypeError):
        SELECTION_ENGINEERING_POLICY["calendar_gate"] = "bypassed"  # type: ignore[index]

    report = build_selection_runtime_report(_record(), _request(_record()))
    before = report.to_dict()
    mutated = report.to_dict()
    source_profile = mutated["source_profile"]
    assert isinstance(source_profile, dict)
    source_profile["human_reviewed"] = True
    candidates = mutated["candidates"]
    assert isinstance(candidates, list)
    candidates.clear()
    assert report.to_dict() == before


def test_report_is_deterministic_review_only_and_has_no_decision_leakage() -> None:
    record = _record()
    request = _request(record)
    first = build_selection_runtime_report(record, request)
    second = build_selection_runtime_report(record, request)
    payload = first.to_dict()

    assert payload == second.to_dict()
    assert payload["selection_runtime_status"] == SELECTION_RUNTIME_STATUS == "review_only"
    assert payload["production_allowed"] is SELECTION_RUNTIME_PRODUCTION_ALLOWED is False
    assert payload["prediction_validity"] == PREDICTION_VALIDITY == "not_evaluated"
    assert payload["gate_priority_receipt"] == list(SELECTION_GATE_PRIORITY)

    forbidden_keys = {
        "final_use",
        "final_relation",
        "final_position",
        "success_probability",
        "probability",
        "timing",
        "timing_candidates",
        "yingqi",
        "exact_date",
        "event_outcome",
        "verdict",
        "auspiciousness",
    }
    assert forbidden_keys.isdisjoint(_all_keys(payload))

    decision_text = "\n".join(
        [first.headline, first.relation_decision.detail]
        + [item.detail for item in first.gate_receipts]
        + [code for item in first.candidates for code in item.decision_codes]
    )
    assert re.search(r"20\d{2}-\d{2}-\d{2}", decision_text) is None
    assert not any(
        phrase in decision_text
        for phrase in (
            "必然成功",
            "一定成功",
            "注定成功",
            "百分百",
            "成功率为",
            "应期为",
            "吉凶为",
        )
    )
    assert "不构成最终用神或事件结论" in first.headline
    assert all(
        item.decision_codes == ("PROVISIONAL_REVIEW_CANDIDATE_ONLY",)
        for item in first.candidates
        if item.contributes
    )


def test_deadline_changes_hash_receipts_not_candidate_semantics() -> None:
    first_record = _record(case_id="SELECTION-DEADLINE-A", deadline="2099-12-30")
    second_record = _record(case_id="SELECTION-DEADLINE-B", deadline="2099-12-31")
    first = build_selection_runtime_report(first_record, _request(first_record))
    second = build_selection_runtime_report(second_record, _request(second_record))

    assert first.event_contract_sha256 != second.event_contract_sha256
    assert first.canonical_sha256 != second.canonical_sha256
    assert _candidate_projection(first) == _candidate_projection(second)
