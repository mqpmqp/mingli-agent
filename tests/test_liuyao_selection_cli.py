from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import mingli.liuyao.selection_cli as selection_cli
from mingli.liuyao.advanced_runtime import AdvancedContextRequest
from mingli.liuyao.case_record import create_case_record
from mingli.liuyao.models import EventContract, LiuYaoCastInput
from mingli.liuyao.selection_runtime import SelectionRequest
from mingli.liuyao.tables import digest


def _record(
    line_values: tuple[int, ...] = (7, 7, 7, 9, 7, 7),
):
    return create_case_record(
        LiuYaoCastInput(
            case_id="SELECTION-CLI-TEST",
            question="冻结的合成验收事件是否达到标准",
            line_values=line_values,
            event_contract=EventContract(
                target_event="冻结的合成验收事件",
                deadline="2099-12-31",
                success_criteria="满足冻结的合成布尔标准",
                evidence_requirement="提供可核验的合成证据",
            ),
            completed_at="2026-09-03T00:00:00+00:00",
            location="合成测试地点",
            month_branch="卯",
            day_ganzhi="丁卯",
        )
    )


def _request(record) -> SelectionRequest:
    return SelectionRequest(
        topic="exam",
        focus_dimension="current_exam",
        case_record_sha256=record.canonical_sha256,
        event_contract_sha256=digest(record.cast.event_contract.to_dict()),
        advanced_context=AdvancedContextRequest(
            calendar_context_confirmed=True,
            calendar_source_refs=("fixture:calendar",),
        ),
        contract_focus_confirmed=True,
        contract_source_refs=("fixture:event-contract",),
        exam_scope="martial",
        exam_scope_confirmed=True,
        exam_scope_refs=("fixture:exam-scope",),
    )


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _error(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    streams = capsys.readouterr()
    assert streams.out == ""
    payload = json.loads(streams.err)
    assert streams.err.count("\n") == 1
    assert payload["status"] == "error"
    return payload


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


def _evaluate(
    record_path: Path,
    request_path: Path,
) -> list[str]:
    return [
        "evaluate",
        "--record",
        str(record_path),
        "--request",
        str(request_path),
    ]


def test_selection_cli_benchmark_is_machine_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert selection_cli.main(["benchmark"]) == selection_cli.EXIT_OK
    streams = capsys.readouterr()
    payload = json.loads(streams.out)

    assert streams.err == ""
    assert streams.out.count("\n") == 1
    assert payload["status"] == "passed"
    assert payload["check_count"] == len(payload["checks"])
    assert payload["check_count"] == 61
    assert all(payload["checks"].values())
    for check in (
        "contract_mismatch_rejected",
        "exam_dual_roles_preserved",
        "relationship_manual_never_contributes",
        "pregnancy_method_conflict",
        "relationship_bond_and_recontact_execute",
        "conditional_paths_no_provisional",
        "moving_preference_never_tiebreaks",
        "hidden_inventory_only",
        "no_final_keys",
        "no_probability_keys",
        "no_timing_keys",
    ):
        assert payload["checks"][check] is True


def test_selection_cli_evaluate_round_trips_strict_hashed_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _record()
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, record.to_dict())
    _write(request_path, _request(record).to_dict())

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_OK
    streams = capsys.readouterr()
    payload = json.loads(streams.out)

    assert streams.err == ""
    assert streams.out.count("\n") == 1
    assert payload["selection_runtime_status"] == "review_only"
    assert payload["production_allowed"] is False
    assert payload["prediction_validity"] == "not_evaluated"
    assert payload["selection_status"] == "single_review_candidate"
    assert payload["provisional_candidate_id"] == "exam_officer:visible:4"
    assert payload["case_record_sha256"] == record.canonical_sha256
    assert payload["selection_request_sha256"] == _request(record).canonical_sha256
    assert len(payload["canonical_sha256"]) == 64


@pytest.mark.parametrize(
    ("document", "path"),
    (
        ("record", ("canonical_sha256",)),
        ("record", ("cast", "canonical_sha256")),
        ("record", ("chart", "canonical_sha256")),
        ("request", ("canonical_sha256",)),
        ("request", ("advanced_context", "canonical_sha256")),
    ),
)
def test_selection_cli_requires_every_input_hash(
    document: str,
    path: tuple[str, ...],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _record()
    record_payload = record.to_dict()
    request_payload = _request(record).to_dict()
    target = record_payload if document == "record" else request_payload
    _delete_path(target, path)
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, record_payload)
    _write(request_path, request_payload)

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    error = _error(capsys)
    assert error["error"]["code"] == "HASH_REQUIRED"


@pytest.mark.parametrize("document", ("record", "request"))
def test_selection_cli_rejects_outer_hash_tampering(
    document: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _record()
    record_payload = record.to_dict()
    request_payload = _request(record).to_dict()
    target = record_payload if document == "record" else request_payload
    target["canonical_sha256"] = "f" * 64
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, record_payload)
    _write(request_path, request_payload)

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "RECORD_TAMPERED"


@pytest.mark.parametrize("malformed_hash", ("", True, "A" * 64, "0" * 63))
def test_selection_cli_rejects_malformed_outer_hash(
    malformed_hash: object,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _record()
    record_payload = record.to_dict()
    record_payload["canonical_sha256"] = malformed_hash
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, record_payload)
    _write(request_path, _request(record).to_dict())

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "HASH_INVALID"


@pytest.mark.parametrize("document", ("record", "request"))
def test_selection_cli_rejects_nested_hash_tampering(
    document: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _record()
    record_payload = record.to_dict()
    request_payload = _request(record).to_dict()
    if document == "record":
        cast = record_payload["cast"]
        assert isinstance(cast, dict)
        cast["location"] = "changed"
    else:
        advanced = request_payload["advanced_context"]
        assert isinstance(advanced, dict)
        advanced["calendar_source_refs"] = ["fixture:changed"]
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, record_payload)
    _write(request_path, request_payload)

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "RECORD_TAMPERED"


def test_selection_cli_rejects_event_contract_binding_mismatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _record()
    payload = _request(record).to_dict()
    payload["event_contract_sha256"] = "0" * 64
    _rehash(payload)
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, record.to_dict())
    _write(request_path, payload)

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "CONTRACT_BINDING_MISMATCH"


def test_selection_cli_rejects_request_bound_to_another_case_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_record = _record()
    changed_record = _record((6, 6, 6, 6, 6, 6))
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, changed_record.to_dict())
    _write(request_path, _request(first_record).to_dict())

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "CASE_RECORD_BINDING_MISMATCH"


def test_selection_cli_rejects_unknown_request_field_even_if_rehashed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _record()
    payload = _request(record).to_dict()
    payload["production_allowed"] = True
    _rehash(payload)
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, record.to_dict())
    _write(request_path, payload)

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "INVALID_INPUT"


def test_selection_cli_rejects_non_object_json_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    _write(record_path, [])
    _write(request_path, {})

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "INVALID_INPUT"


def test_selection_cli_invalid_json_is_machine_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text("{", encoding="utf-8")
    _write(request_path, _request(_record()).to_dict())

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "INVALID_JSON"


@pytest.mark.parametrize(
    "invalid_json",
    (
        '{"canonical_sha256":"' + "0" * 64 + '","canonical_sha256":"' + "1" * 64 + '"}',
        '{"canonical_sha256":NaN}',
        '{"canonical_sha256":Infinity}',
        '{"canonical_sha256":-Infinity}',
    ),
)
def test_selection_cli_rejects_ambiguous_or_nonstandard_json(
    invalid_json: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text(invalid_json, encoding="utf-8")
    _write(request_path, _request(_record()).to_dict())

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "INVALID_JSON"


def test_selection_cli_deep_json_is_machine_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_text("[" * 2_000 + "0" + "]" * 2_000, encoding="utf-8")
    _write(request_path, _request(_record()).to_dict())

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "INVALID_JSON"


def test_selection_cli_rejects_oversized_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_bytes(b" " * (selection_cli._MAX_INPUT_BYTES + 1))
    _write(request_path, _request(_record()).to_dict())

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "INPUT_TOO_LARGE"


def test_selection_cli_invalid_encoding_is_machine_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "record.json"
    request_path = tmp_path / "request.json"
    record_path.write_bytes(b"\xff")
    _write(request_path, _request(_record()).to_dict())

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "INVALID_ENCODING"


def test_selection_cli_missing_file_is_machine_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record_path = tmp_path / "missing.json"
    request_path = tmp_path / "request.json"
    _write(request_path, _request(_record()).to_dict())

    assert selection_cli.main(_evaluate(record_path, request_path)) == selection_cli.EXIT_FAILED
    assert _error(capsys)["error"]["code"] == "IO_ERROR"


def test_selection_cli_failed_benchmark_returns_one_on_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        selection_cli,
        "benchmark_liuyao_selection_runtime",
        lambda: {"status": "failed", "checks": {"synthetic": False}},
    )
    assert selection_cli.main(["benchmark"]) == selection_cli.EXIT_FAILED
    streams = capsys.readouterr()
    assert streams.err == ""
    assert json.loads(streams.out)["status"] == "failed"


def test_selection_cli_usage_error_returns_two_as_machine_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        selection_cli.main([])

    assert raised.value.code == selection_cli.EXIT_USAGE
    assert _error(capsys)["error"]["code"] == "USAGE_ERROR"


@pytest.mark.parametrize(
    ("args", "expected_exit", "stream_name"),
    (
        (("benchmark",), selection_cli.EXIT_OK, "stdout"),
        ((), selection_cli.EXIT_USAGE, "stderr"),
    ),
)
def test_selection_cli_module_entrypoint_uses_real_exit_codes_and_machine_json(
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
        [sys.executable, "-m", "mingli.liuyao.selection_cli", *args],
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
    assert selected.count("\n") == 1
    assert isinstance(json.loads(selected), dict)
