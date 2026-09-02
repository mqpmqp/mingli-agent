from __future__ import annotations

import json
from pathlib import Path

import pytest

from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.selection_cli import main
from mingli.liuyao.selection_core import AutoSelectionRequest
from mingli.liuyao.selection_runtime import SelectionRuntimeRequest
from mingli.liuyao.tables import digest


def _record():
    return create_case_record(
        LiuYaoCastInput(
            case_id="SELECTION-CLI-TEST",
            question="本批次是否最终录用",
            line_values=(6, 7, 7, 8, 7, 7),
            event_contract=EventContract(
                target_event="进入最终公示名单",
                deadline="2099-12-31",
                success_criteria="官方最终公示名单包含目标人",
                evidence_requirement="官方公示或可核验录用通知",
            ),
            completed_at="2026-08-31T21:12:00+08:00",
            location="synthetic",
        )
    )


def _request(record) -> SelectionRuntimeRequest:
    selection = AutoSelectionRequest(
        topic="exam",
        focus_dimension="current_exam",
        contract_focus_confirmed=True,
        contract_source_refs=("source:event-contract",),
    )
    return SelectionRuntimeRequest(
        selection=selection,
        event_contract_sha256=digest(record.cast.event_contract.to_dict()),
    )


def test_selection_cli_benchmark(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["benchmark"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "passed"
    assert payload["checks"]["moving_does_not_break_tie"] is True


def test_selection_cli_evaluate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record = _record()
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False), encoding="utf-8")
    request_path.write_text(json.dumps(_request(record).to_dict(), ensure_ascii=False), encoding="utf-8")

    assert main(["evaluate", "--record", str(record_path), "--request", str(request_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["recommendation_status"] == "recommended_visible_candidate"
    assert payload["recommended_position"] == 3
    assert payload["selection_runtime_status"] == "review_only"
    assert payload["production_allowed"] is False


def test_selection_cli_rejects_contract_hash_mismatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _record()
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False), encoding="utf-8")
    payload = _request(record).to_dict()
    payload["event_contract_sha256"] = "0" * 64
    payload.pop("canonical_sha256", None)
    request_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert main(["evaluate", "--record", str(record_path), "--request", str(request_path)]) == 1
    assert "CONTRACT_BINDING_MISMATCH" in capsys.readouterr().err
