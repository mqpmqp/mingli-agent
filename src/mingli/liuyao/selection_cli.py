from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Mapping, Sequence, TextIO

from .case_record import LiuYaoCaseRecord
from .selection_benchmark import benchmark_liuyao_selection_runtime
from .selection_runtime import SelectionRequest, build_selection_runtime_report
from .validation import LiuYaoError

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
_MAX_INPUT_BYTES = 1_048_576
_MAX_JSON_DEPTH = 64
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def _emit(value: object, *, stream: TextIO | None = None) -> None:
    target = sys.stdout if stream is None else stream
    print(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        file=target,
    )


def _emit_error(code: str, message: str) -> None:
    _emit(
        {"status": "error", "error": {"code": code, "message": message}},
        stream=sys.stderr,
    )


class _MachineJsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        _emit_error("USAGE_ERROR", message)
        raise SystemExit(EXIT_USAGE)


def _parser() -> argparse.ArgumentParser:
    parser = _MachineJsonArgumentParser(
        prog="python -m mingli.liuyao.selection_cli",
        description="六爻第三阶段事件合同驱动取用候选工具",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    evaluate = commands.add_parser(
        "evaluate",
        help="重算冻结案例和请求摘要后生成 review-only 取用候选报告",
    )
    evaluate.add_argument("--record", required=True, type=Path)
    evaluate.add_argument("--request", required=True, type=Path)

    commands.add_parser("benchmark", help="运行事件合同、主题门禁和候选矩阵合成基准")
    return parser


def _read_object(path: Path, name: str) -> Mapping[str, object]:
    with path.open("rb") as stream:
        raw = stream.read(_MAX_INPUT_BYTES + 1)
    if len(raw) > _MAX_INPUT_BYTES:
        raise LiuYaoError(
            "INPUT_TOO_LARGE",
            f"{name} 超过 {_MAX_INPUT_BYTES} 字节限制",
        )

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise LiuYaoError("INVALID_JSON", f"{name} 包含重复 JSON 键：{key}")
            result[key] = item
        return result

    def reject_nonstandard_constant(value: str) -> object:
        raise LiuYaoError("INVALID_JSON", f"{name} 包含非标准 JSON 常量：{value}")

    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_nonstandard_constant,
    )
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > _MAX_JSON_DEPTH:
            raise LiuYaoError(
                "INVALID_JSON",
                f"{name} JSON 嵌套超过 {_MAX_JSON_DEPTH} 层限制",
            )
        if isinstance(item, dict):
            pending.extend((nested, depth + 1) for nested in item.values())
        elif isinstance(item, list):
            pending.extend((nested, depth + 1) for nested in item)
    if not isinstance(value, dict):
        raise LiuYaoError("INVALID_INPUT", f"{name} 必须是 JSON 对象")
    return value


def _require_hash(value: Mapping[str, object], name: str) -> None:
    supplied = value.get("canonical_sha256")
    if supplied is None:
        raise LiuYaoError(
            "HASH_REQUIRED",
            f"{name} 缺少 canonical_sha256；evaluate 严格模式拒绝未绑定输入",
        )
    if not isinstance(supplied, str) or _SHA256_PATTERN.fullmatch(supplied) is None:
        raise LiuYaoError(
            "HASH_INVALID",
            f"{name}.canonical_sha256 必须是 64 位小写 SHA-256",
        )


def _require_nested_hash(
    value: Mapping[str, object],
    field: str,
    name: str,
) -> None:
    nested = value.get(field)
    if not isinstance(nested, dict):
        raise LiuYaoError("INVALID_INPUT", f"{name} 必须是 JSON 对象")
    _require_hash(nested, name)


def _error_message(exc: LiuYaoError) -> str:
    text = str(exc)
    prefix = f"{exc.code}: "
    return text[len(prefix) :] if text.startswith(prefix) else text


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "evaluate":
            record_payload = _read_object(args.record, "record")
            request_payload = _read_object(args.request, "request")
            _require_hash(record_payload, "case_record")
            _require_nested_hash(record_payload, "cast", "case_record.cast")
            _require_nested_hash(record_payload, "chart", "case_record.chart")
            _require_hash(request_payload, "selection_request")
            _require_nested_hash(
                request_payload,
                "advanced_context",
                "selection_request.advanced_context",
            )
            record = LiuYaoCaseRecord.from_mapping(record_payload)
            request = SelectionRequest.from_mapping(request_payload)
            _emit(build_selection_runtime_report(record, request).to_dict())
            return EXIT_OK

        result = benchmark_liuyao_selection_runtime()
        _emit(result)
        return EXIT_OK if result["status"] == "passed" else EXIT_FAILED
    except LiuYaoError as exc:
        _emit_error(exc.code, _error_message(exc))
        return EXIT_FAILED
    except json.JSONDecodeError as exc:
        _emit_error("INVALID_JSON", str(exc))
        return EXIT_FAILED
    except UnicodeError as exc:
        _emit_error("INVALID_ENCODING", str(exc))
        return EXIT_FAILED
    except RecursionError:
        _emit_error("INVALID_JSON", "JSON 嵌套过深")
        return EXIT_FAILED
    except OSError as exc:
        _emit_error("IO_ERROR", str(exc))
        return EXIT_FAILED
    except (TypeError, ValueError) as exc:
        _emit_error("INVALID_INPUT", str(exc))
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["EXIT_FAILED", "EXIT_OK", "EXIT_USAGE", "main"]
