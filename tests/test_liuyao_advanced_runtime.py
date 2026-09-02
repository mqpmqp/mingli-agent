from __future__ import annotations

import json
from pathlib import Path

import pytest

from mingli.liuyao.advanced_cli import main
from mingli.liuyao.advanced_runtime import (
    ADVANCED_RUNTIME_PRODUCTION_ALLOWED,
    AdvancedContextRequest,
    build_advanced_runtime_report,
)
from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.tables import PREDICTION_VALIDITY
from mingli.liuyao.validation import LiuYaoError


def _record(*, month_branch: str | None = "亥", day_ganzhi: str | None = "甲申"):
    contract = EventContract(
        target_event="synthetic",
        deadline="2099-12-31",
        success_criteria="synthetic criterion",
        evidence_requirement="synthetic evidence",
    )
    return create_case_record(
        LiuYaoCastInput(
            case_id="ADVANCED-RUNTIME-TEST",
            question="synthetic",
            line_values=(7, 8, 8, 6, 7, 7),
            event_contract=contract,
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
            month_branch=month_branch,
            day_ganzhi=day_ganzhi,
        )
    )


def test_unconfirmed_calendar_context_cannot_emit_growth_stage_facts() -> None:
    report = build_advanced_runtime_report(_record(), AdvancedContextRequest())

    assert report.context_status == "provided_unconfirmed"
    assert report.provenance_status == "blocked_unconfirmed"
    assert not [fact for fact in report.facts if fact.category == "growth_stage"]
    assert any("已从可用输出中移除" in warning for warning in report.warnings)


def test_confirmed_calendar_context_requires_source_refs() -> None:
    with pytest.raises(LiuYaoError) as raised:
        AdvancedContextRequest(calendar_context_confirmed=True)

    assert raised.value.code == "CALENDAR_SOURCE_REQUIRED"


def test_source_refs_without_confirmation_are_rejected() -> None:
    with pytest.raises(LiuYaoError) as raised:
        AdvancedContextRequest(calendar_source_refs=("source:calendar",))

    assert raised.value.code == "CALENDAR_CONFIRMATION_REQUIRED"


def test_confirmed_context_emits_growth_facts_but_does_not_claim_verification() -> None:
    request = AdvancedContextRequest(
        calendar_context_confirmed=True,
        calendar_source_refs=("source:verified-calendar-receipt",),
    )
    report = build_advanced_runtime_report(_record(), request)
    payload = report.to_dict()

    assert report.context_status == "confirmed_complete"
    assert report.provenance_status == "declared_sources_present_not_runtime_verified"
    assert [fact for fact in report.facts if fact.category == "growth_stage"]
    assert any("不核验" in warning for warning in report.warnings)
    assert payload["production_allowed"] is False
    assert ADVANCED_RUNTIME_PRODUCTION_ALLOWED is False
    assert payload["prediction_validity"] == PREDICTION_VALIDITY


def test_partial_confirmed_context_is_explicit() -> None:
    report = build_advanced_runtime_report(
        _record(day_ganzhi=None),
        AdvancedContextRequest(
            calendar_context_confirmed=True,
            calendar_source_refs=("source:month-branch",),
        ),
    )

    assert report.context_status == "confirmed_partial"
    assert [fact for fact in report.facts if fact.scope == "month_original"]
    assert not [fact for fact in report.facts if fact.scope == "day_original"]


def test_absent_calendar_context_cannot_be_marked_confirmed() -> None:
    with pytest.raises(LiuYaoError) as raised:
        build_advanced_runtime_report(
            _record(month_branch=None, day_ganzhi=None),
            AdvancedContextRequest(
                calendar_context_confirmed=True,
                calendar_source_refs=("source:none",),
            ),
        )

    assert raised.value.code == "CALENDAR_CONTEXT_MISSING"


def test_context_request_round_trip_and_hash_tamper_gate() -> None:
    request = AdvancedContextRequest(
        calendar_context_confirmed=True,
        calendar_source_refs=("source:one", "source:two"),
    )
    payload = request.to_dict()

    assert AdvancedContextRequest.from_mapping(payload).to_dict() == payload
    payload["calendar_source_refs"] = ["source:changed"]
    with pytest.raises(LiuYaoError) as raised:
        AdvancedContextRequest.from_mapping(payload)
    assert raised.value.code == "RECORD_TAMPERED"


def test_runtime_report_is_deterministic_and_hash_bound() -> None:
    request = AdvancedContextRequest(
        calendar_context_confirmed=True,
        calendar_source_refs=("source:calendar",),
    )
    first = build_advanced_runtime_report(_record(), request)
    second = build_advanced_runtime_report(_record(), request)

    assert first.to_dict() == second.to_dict()
    assert first.raw_fact_report_sha256
    assert len(first.canonical_sha256) == 64


def test_advanced_cli_benchmark_emits_machine_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["benchmark"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "passed"


def test_advanced_cli_facts_enforces_context_gate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    context_path = tmp_path / "context.json"
    record_path.write_text(
        json.dumps(_record().to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    context_path.write_text(
        json.dumps(
            AdvancedContextRequest(
                calendar_context_confirmed=True,
                calendar_source_refs=("source:calendar",),
            ).to_dict(),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert main(["facts", "--record", str(record_path), "--context", str(context_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["context_status"] == "confirmed_complete"
    assert payload["advanced_runtime_status"] == "review_only"
    assert payload["production_allowed"] is False
