from __future__ import annotations

import pytest

from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.selection_core import AutoSelectionRequest
from mingli.liuyao.selection_runtime import (
    SELECTION_RUNTIME_PRODUCTION_ALLOWED,
    SelectionRuntimeRequest,
    build_selection_runtime_report,
)
from mingli.liuyao.tables import PREDICTION_VALIDITY, digest
from mingli.liuyao.validation import LiuYaoError


def _contract() -> EventContract:
    return EventContract(
        target_event="进入最终公示名单",
        deadline="2099-12-31",
        success_criteria="官方最终公示名单包含目标人",
        evidence_requirement="官方公示或可核验录用通知",
    )


def _record(
    lines: tuple[int, ...] = (6, 7, 7, 8, 7, 7),
    *,
    casting_mode: str = "self",
    proxy_relationship: str | None = None,
    month_branch: str | None = None,
    day_ganzhi: str | None = None,
):
    return create_case_record(
        LiuYaoCastInput(
            case_id="SELECTION-RUNTIME-TEST",
            question="本批次是否最终录用",
            line_values=lines,
            event_contract=_contract(),
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
            casting_mode=casting_mode,
            proxy_relationship=proxy_relationship,
            month_branch=month_branch,
            day_ganzhi=day_ganzhi,
        )
    )


def _runtime_request(
    record,
    *,
    topic: str = "exam",
    focus_dimension: str | None = "current_exam",
    querent_gender: str = "unknown",
    primary_relation_override: str | None = None,
    override_reason: str | None = None,
    primary_position: int | None = None,
    subject_mapping_confirmed: bool = False,
    subject_position: int | None = None,
    contract_focus_confirmed: bool = True,
    reality_status: str = "unknown",
    reality_facts: tuple[str, ...] = (),
    reality_evidence_refs: tuple[str, ...] = (),
) -> SelectionRuntimeRequest:
    selection = AutoSelectionRequest(
        topic=topic,
        focus_dimension=focus_dimension,
        querent_gender=querent_gender,
        primary_relation_override=primary_relation_override,
        override_reason=override_reason,
        primary_position=primary_position,
        subject_mapping_confirmed=subject_mapping_confirmed,
        subject_position=subject_position,
        contract_focus_confirmed=contract_focus_confirmed,
        contract_source_refs=("source:event-contract",) if contract_focus_confirmed else (),
        calendar_context_confirmed=False,
        reality_status=reality_status,
        reality_facts=reality_facts,
        reality_evidence_refs=reality_evidence_refs,
    )
    return SelectionRuntimeRequest(
        selection=selection,
        event_contract_sha256=(
            digest(record.cast.event_contract.to_dict())
            if contract_focus_confirmed
            else None
        ),
    )


def test_event_contract_hash_is_required_and_bound() -> None:
    record = _record()
    selection = AutoSelectionRequest(
        topic="exam",
        focus_dimension="current_exam",
        contract_focus_confirmed=True,
        contract_source_refs=("source:event-contract",),
    )
    with pytest.raises(LiuYaoError) as raised:
        SelectionRuntimeRequest(selection=selection)
    assert raised.value.code == "CONTRACT_HASH_REQUIRED"

    request = SelectionRuntimeRequest(
        selection=selection,
        event_contract_sha256="0" * 64,
    )
    with pytest.raises(LiuYaoError) as raised:
        build_selection_runtime_report(record, request)
    assert raised.value.code == "CONTRACT_BINDING_MISMATCH"


def test_exam_current_event_has_four_dimensions_and_unique_visible_officer() -> None:
    record = _record()
    report = build_selection_runtime_report(record, _runtime_request(record))

    assert len(report.topic_dimensions) == 4
    assert [item.dimension_id for item in report.topic_dimensions] == [
        "system_fit",
        "current_exam",
        "position_direction",
        "preparation_strategy",
    ]
    current = next(item for item in report.topic_dimensions if item.dimension_id == "current_exam")
    assert current.primary_relation == "官鬼"
    assert current.secondary_relations == ("父母", "兄弟")
    assert report.primary_relation == "官鬼"
    assert report.recommended_position == 3
    assert report.recommendation_status == "recommended_visible_candidate"


def test_exam_system_fit_cannot_be_bypassed_by_relation_override() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            focus_dimension="system_fit",
            primary_relation_override="官鬼",
            override_reason="attempted override",
        ),
    )

    assert report.recommended_position is None
    assert report.recommendation_status == "unsupported_focus"
    assert "不允许" in report.headline
    assert "unsupported_focus_override_blocked" in report.policy_checks


def test_relationship_requires_gender_and_maps_spouse_relation() -> None:
    record = _record()
    unknown = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            topic="relationship_reconciliation",
            focus_dimension="reconciliation",
            querent_gender="unknown",
        ),
    )
    male = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            topic="relationship_reconciliation",
            focus_dimension="reconciliation",
            querent_gender="male",
        ),
    )
    female = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            topic="relationship_reconciliation",
            focus_dimension="reconciliation",
            querent_gender="female",
        ),
    )

    assert unknown.recommendation_status == "gender_required"
    assert unknown.primary_relation is None
    assert male.primary_relation == "妻财"
    assert female.primary_relation == "官鬼"


def test_relationship_stability_requires_reality_context() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            topic="relationship_reconciliation",
            focus_dimension="stability",
            querent_gender="female",
        ),
    )
    assert report.recommendation_status == "reality_context_required"
    assert report.recommended_position is None


def test_pregnancy_medical_confirmation_cannot_be_overridden() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            topic="pregnancy",
            focus_dimension="medical_confirmation",
            primary_relation_override="子孙",
            override_reason="attempted medical bypass",
        ),
    )
    assert report.recommendation_status == "unsupported_focus"
    assert report.recommended_position is None


def test_pregnancy_conception_maps_to_child_relation_advisory_only() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            topic="pregnancy",
            focus_dimension="conception_opportunity",
        ),
    )
    assert report.primary_relation == "子孙"
    assert report.recommended_position == 5
    assert report.recommendation_status == "recommended_visible_candidate"
    dimension = next(item for item in report.topic_dimensions if item.dimension_id == "conception_opportunity")
    assert dimension.mode == "structural_advisory"


def test_general_requires_manual_relation_and_reason() -> None:
    record = _record()
    automatic = build_selection_runtime_report(
        record,
        _runtime_request(record, topic="general", focus_dimension="current_event"),
    )
    assert automatic.recommendation_status == "manual_relation_required"

    manual = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            topic="general",
            focus_dimension="current_event",
            primary_relation_override="官鬼",
            override_reason="事件合同明确把目标岗位作为观察对象",
        ),
    )
    assert manual.primary_relation == "官鬼"
    assert manual.relation_source == "manual_override"
    assert manual.recommended_position == 3


def test_contract_unconfirmed_stops_before_candidate_selection() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _runtime_request(record, contract_focus_confirmed=False),
    )
    assert report.recommendation_status == "contract_unconfirmed"
    assert report.candidates == ()
    assert report.recommended_position is None


def test_proxy_case_requires_confirmed_subject_mapping() -> None:
    record = _record(casting_mode="proxy", proxy_relationship="朋友")
    blocked = build_selection_runtime_report(record, _runtime_request(record))
    assert blocked.recommendation_status == "subject_mapping_required"
    assert blocked.subject_position is None

    confirmed = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            subject_mapping_confirmed=True,
            subject_position=record.chart.original.shi_line,
        ),
    )
    assert confirmed.subject_position == record.chart.original.shi_line
    assert confirmed.counterparty_position == record.chart.original.ying_line


def test_moving_line_does_not_break_same_availability_tie() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            topic="wealth",
            focus_dimension="current_money_event",
        ),
    )

    visible = [candidate for candidate in report.candidates if candidate.source == "visible"]
    assert [candidate.position for candidate in visible] == [1, 4]
    assert visible[0].moving is True
    assert visible[1].moving is False
    assert report.recommended_position is None
    assert report.recommendation_status == "tie_needs_confirmation"
    assert "moving_tiebreak_does_not_resolve_use_line" in report.policy_checks


def test_hidden_only_relation_is_never_auto_selected() -> None:
    record = _record(lines=(7, 8, 8, 6, 7, 7))
    report = build_selection_runtime_report(record, _runtime_request(record))
    assert report.primary_relation == "官鬼"
    assert report.recommended_position is None
    assert report.recommendation_status == "hidden_candidate_needs_confirmation"
    assert report.candidates and all(candidate.source == "hidden" for candidate in report.candidates)


def test_explicit_position_mismatch_is_rejected() -> None:
    record = _record()
    with pytest.raises(LiuYaoError) as raised:
        build_selection_runtime_report(
            record,
            _runtime_request(record, primary_position=1),
        )
    assert raised.value.code == "USE_GOD_MISMATCH"


def test_reality_block_overrides_candidate_recommendation() -> None:
    record = _record()
    report = build_selection_runtime_report(
        record,
        _runtime_request(
            record,
            reality_status="blocking",
            reality_facts=("资格审核已确认不通过",),
            reality_evidence_refs=("source:official-review",),
        ),
    )
    assert report.recommendation_status == "reality_blocked"
    assert report.recommended_position is None


def test_reality_shape_is_validated_even_on_early_return_paths() -> None:
    record = _record()
    with pytest.raises(LiuYaoError) as raised:
        build_selection_runtime_report(
            record,
            _runtime_request(
                record,
                focus_dimension="system_fit",
                reality_status="blocking",
            ),
        )
    assert raised.value.code == "REALITY_EVIDENCE_REQUIRED"

    invalid = _runtime_request(record)
    object.__setattr__(invalid.selection, "reality_status", "invalid")
    with pytest.raises(LiuYaoError) as raised:
        build_selection_runtime_report(record, invalid)
    assert raised.value.code == "INVALID_INPUT"


def test_report_is_deterministic_review_only_and_has_no_probability_or_timing() -> None:
    record = _record()
    request = _runtime_request(record)
    first = build_selection_runtime_report(record, request)
    second = build_selection_runtime_report(record, request)
    payload = first.to_dict()

    assert first.to_dict() == second.to_dict()
    assert payload["selection_runtime_status"] == "review_only"
    assert payload["production_allowed"] is False
    assert SELECTION_RUNTIME_PRODUCTION_ALLOWED is False
    assert payload["prediction_validity"] == PREDICTION_VALIDITY
    assert "probability" not in payload
    assert "timing" not in payload
    assert len(payload["canonical_sha256"]) == 64
