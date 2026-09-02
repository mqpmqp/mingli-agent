from __future__ import annotations

import json
from pathlib import Path

import pytest

from mingli.liuyao.advanced_runtime import AdvancedContextRequest
from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.interpretation import InterpretationRequest
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.validity_cli import main
from mingli.liuyao.validity_matrix import ValidityRequest


def _record():
    return create_case_record(
        LiuYaoCastInput(
            case_id="VALIDITY-CLI-TEST",
            question="synthetic",
            line_values=(7, 8, 8, 6, 7, 7),
            event_contract=EventContract(
                target_event="synthetic",
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


def _request() -> ValidityRequest:
    interpretation = InterpretationRequest.from_mapping(
        {
            "topic": "general",
            "use_relation": "妻财",
            "primary_position": 4,
            "calendar_context_confirmed": True,
            "calendar_source_refs": ["source:calendar"],
            "reality_status": "unknown",
        }
    )
    return ValidityRequest(
        interpretation=interpretation,
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=True,
            calendar_source_refs=("source:calendar",),
        ),
    )


def test_validity_cli_benchmark(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["benchmark"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "passed"
    assert payload["checks"]["no_probability"] is True


def test_validity_cli_evaluate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text(json.dumps(_record().to_dict(), ensure_ascii=False), encoding="utf-8")
    request_path.write_text(json.dumps(_request().to_dict(), ensure_ascii=False), encoding="utf-8")

    assert main(["evaluate", "--record", str(record_path), "--request", str(request_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["matrix_status"] == "conditional"
    assert payload["validity_matrix_status"] == "review_only"
    assert payload["production_allowed"] is False


def test_validity_cli_rejects_tampered_request(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text(json.dumps(_record().to_dict(), ensure_ascii=False), encoding="utf-8")
    payload = _request().to_dict()
    payload["advanced_context"]["calendar_source_refs"] = ["source:changed"]
    request_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert main(["evaluate", "--record", str(record_path), "--request", str(request_path)]) == 1
    assert "RECORD_TAMPERED" in capsys.readouterr().err
