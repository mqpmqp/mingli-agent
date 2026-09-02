from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import mingli.liuyao.validity_cli as validity_cli
from mingli.liuyao.advanced_runtime import AdvancedContextRequest
from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.interpretation import InterpretationRequest
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.tables import digest
from mingli.liuyao.validity_matrix import ValidityRequest


def _record():
    return create_case_record(
        LiuYaoCastInput(
            case_id="VALIDITY-CLI-TEST",
            question="synthetic",
            line_values=(9, 8, 9, 6, 7, 7),
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
            calendar_source_refs=("source:calendar",),
        ),
        reality_evidence_confirmed=reality_confirmed,
        reality_evidence_refs=("source:reality",) if reality_confirmed else (),
    )


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _error(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    streams = capsys.readouterr()
    assert streams.out == ""
    return json.loads(streams.err)


def _delete_path(value: dict[str, object], path: tuple[str, ...]) -> None:
    target = value
    for field in path[:-1]:
        nested = target[field]
        assert isinstance(nested, dict)
        target = nested
    del target[path[-1]]


def _rehash(value: dict[str, object]) -> None:
    value.pop("canonical_sha256", None)
    value["canonical_sha256"] = digest(value)


def test_validity_cli_benchmark_is_machine_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert validity_cli.main(["benchmark"]) == validity_cli.EXIT_OK
    streams = capsys.readouterr()
    payload = json.loads(streams.out)

    assert streams.err == ""
    assert payload["status"] == "passed"
    assert payload["checks"]["review_only"] is True
    assert payload["checks"]["not_production"] is True
    assert payload["checks"]["maximum_two_hops"] is True


def test_validity_cli_evaluate_round_trips_hashed_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, _record().to_dict())
    _write(request_path, _request().to_dict())

    assert validity_cli.main(
        ["evaluate", "--record", str(record_path), "--request", str(request_path)]
    ) == validity_cli.EXIT_OK
    streams = capsys.readouterr()
    payload = json.loads(streams.out)

    assert streams.err == ""
    assert payload["validity_matrix_status"] == "review_only"
    assert payload["production_allowed"] is False
    assert payload["focus_selection"]["status"] == "confirmed"
    assert payload["focus_selection"]["selected_position"] == 4
    assert all(len(item["edge_ids"]) <= 2 for item in payload["paths"])
    assert len(payload["canonical_sha256"]) == 64


def test_validity_cli_rejects_tampered_record_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    payload = _record().to_dict()
    payload["chart"]["input_sha256"] = "0" * 64
    _write(record_path, payload)
    _write(request_path, _request().to_dict())

    assert validity_cli.main(
        ["evaluate", "--record", str(record_path), "--request", str(request_path)]
    ) == validity_cli.EXIT_FAILED
    error = _error(capsys)
    assert error["status"] == "error"
    assert error["error"]["code"] == "RECORD_TAMPERED"


def test_validity_cli_rejects_tampered_request_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    payload = _request().to_dict()
    payload["advanced_context"]["calendar_source_refs"] = ["source:changed"]
    _write(record_path, _record().to_dict())
    _write(request_path, payload)

    assert validity_cli.main(
        ["evaluate", "--record", str(record_path), "--request", str(request_path)]
    ) == validity_cli.EXIT_FAILED
    error = _error(capsys)
    assert error["error"]["code"] == "RECORD_TAMPERED"


@pytest.mark.parametrize("document", ("record", "request"))
def test_validity_cli_rejects_outer_hash_tampering(
    document: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_payload = _record().to_dict()
    request_payload = _request().to_dict()
    target = record_payload if document == "record" else request_payload
    target["canonical_sha256"] = "f" * 64
    _write(record_path, record_payload)
    _write(request_path, request_payload)

    assert validity_cli.main(
        ["evaluate", "--record", str(record_path), "--request", str(request_path)]
    ) == validity_cli.EXIT_FAILED
    error = _error(capsys)
    assert error["error"]["code"] == "RECORD_TAMPERED"


@pytest.mark.parametrize(
    ("document", "path"),
    (
        ("record", ("canonical_sha256",)),
        ("record", ("cast", "canonical_sha256")),
        ("request", ("canonical_sha256",)),
        ("request", ("interpretation", "canonical_sha256")),
        ("request", ("advanced_context", "canonical_sha256")),
    ),
)
def test_validity_cli_requires_all_input_hashes(
    document: str,
    path: tuple[str, ...],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_payload = _record().to_dict()
    request_payload = _request().to_dict()
    if document == "record":
        _delete_path(record_payload, path)
    else:
        _delete_path(request_payload, path)
    _write(record_path, record_payload)
    _write(request_path, request_payload)

    assert validity_cli.main(
        ["evaluate", "--record", str(record_path), "--request", str(request_path)]
    ) == validity_cli.EXIT_FAILED
    error = _error(capsys)
    assert error["error"]["code"] == "HASH_REQUIRED"


@pytest.mark.parametrize(
    ("scenario", "expected_code"),
    (
        ("blocking_without_confirmation", "REALITY_CONFIRMATION_REQUIRED"),
        ("blocking_without_refs", "REALITY_EVIDENCE_REQUIRED"),
        ("unknown_with_evidence", "REALITY_STATUS_REQUIRED"),
    ),
)
def test_validity_cli_rejects_unbound_reality_evidence(
    scenario: str,
    expected_code: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    request_payload = _request().to_dict()
    interpretation = request_payload["interpretation"]
    assert isinstance(interpretation, dict)
    if scenario != "unknown_with_evidence":
        interpretation["reality_status"] = "blocking"
        interpretation["reality_facts"] = ["synthetic verified blocker"]
        _rehash(interpretation)
    request_payload["reality_evidence_confirmed"] = (
        scenario != "blocking_without_confirmation"
    )
    request_payload["reality_evidence_refs"] = (
        [] if scenario == "blocking_without_refs" else ["source:reality"]
    )
    _rehash(request_payload)
    _write(record_path, _record().to_dict())
    _write(request_path, request_payload)

    assert validity_cli.main(
        ["evaluate", "--record", str(record_path), "--request", str(request_path)]
    ) == validity_cli.EXIT_FAILED
    error = _error(capsys)
    assert error["error"]["code"] == expected_code


def test_validity_cli_requires_confirmed_reality_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, _record().to_dict())
    _write(request_path, _request(reality_status="blocking").to_dict())

    assert validity_cli.main(
        ["evaluate", "--record", str(record_path), "--request", str(request_path)]
    ) == validity_cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)

    assert payload["focus_status"] == "reality_blocked"
    assert payload["reality_override"] == "blocking_confirmed_with_bound_refs"
    assert payload["request"]["reality_evidence_confirmed"] is True


def test_validity_cli_invalid_json_is_machine_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text("{", encoding="utf-8")
    _write(request_path, _request().to_dict())

    assert validity_cli.main(
        ["evaluate", "--record", str(record_path), "--request", str(request_path)]
    ) == validity_cli.EXIT_FAILED
    error = _error(capsys)
    assert error["error"]["code"] == "INVALID_JSON"


def test_validity_cli_failed_benchmark_returns_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        validity_cli,
        "benchmark_liuyao_validity_matrix",
        lambda: {"status": "failed", "checks": {"synthetic": False}},
    )

    assert validity_cli.main(["benchmark"]) == validity_cli.EXIT_FAILED
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_validity_cli_usage_error_returns_two_as_machine_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        validity_cli.main([])

    assert raised.value.code == validity_cli.EXIT_USAGE
    error = _error(capsys)
    assert error["error"]["code"] == "USAGE_ERROR"


@pytest.mark.parametrize(
    ("args", "expected_exit", "stream_name"),
    (
        (("benchmark",), validity_cli.EXIT_OK, "stdout"),
        ((), validity_cli.EXIT_USAGE, "stderr"),
    ),
)
def test_validity_cli_module_entrypoint_uses_os_exit_codes_and_machine_json(
    args: tuple[str, ...],
    expected_exit: int,
    stream_name: str,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    existing_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath = str(project_root / "src")
    if existing_pythonpath:
        pythonpath = os.pathsep.join((pythonpath, existing_pythonpath))
    completed = subprocess.run(
        [sys.executable, "-m", "mingli.liuyao.validity_cli", *args],
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": pythonpath},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == expected_exit
    selected = completed.stdout if stream_name == "stdout" else completed.stderr
    other = completed.stderr if stream_name == "stdout" else completed.stdout
    assert other == ""
    assert isinstance(json.loads(selected), dict)
