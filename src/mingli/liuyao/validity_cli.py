from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence, TextIO

from .case_record import LiuYaoCaseRecord
from .validation import LiuYaoError
from .validity_benchmark import benchmark_liuyao_validity_matrix
from .validity_matrix import ValidityRequest, build_validity_matrix

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


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
        prog="python -m mingli.liuyao.validity_cli",
        description="六爻第三阶段高级事实有效性与冲突矩阵工具",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    evaluate = commands.add_parser(
        "evaluate",
        help="重算冻结案例和请求哈希后生成 review-only 有效性矩阵",
    )
    evaluate.add_argument("--record", required=True, type=Path)
    evaluate.add_argument("--request", required=True, type=Path)

    commands.add_parser("benchmark", help="运行有效性与路径裁剪合成基准")
    return parser


def _read_object(path: Path, name: str) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LiuYaoError("INVALID_INPUT", f"{name} 必须是 JSON 对象")
    return value


def _require_hash(value: Mapping[str, object], name: str) -> None:
    if value.get("canonical_sha256") is None:
        raise LiuYaoError(
            "HASH_REQUIRED",
            f"{name} 缺少 canonical_sha256；evaluate 严格模式拒绝未绑定输入",
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
            _require_hash(request_payload, "validity_request")
            _require_nested_hash(
                request_payload,
                "interpretation",
                "validity_request.interpretation",
            )
            _require_nested_hash(
                request_payload,
                "advanced_context",
                "validity_request.advanced_context",
            )
            record = LiuYaoCaseRecord.from_mapping(record_payload)
            request = ValidityRequest.from_mapping(request_payload)
            _emit(build_validity_matrix(record, request).to_dict())
            return EXIT_OK

        result = benchmark_liuyao_validity_matrix()
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
    except OSError as exc:
        _emit_error("IO_ERROR", str(exc))
        return EXIT_FAILED
    except (TypeError, ValueError) as exc:
        _emit_error("INVALID_INPUT", str(exc))
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["EXIT_FAILED", "EXIT_OK", "EXIT_USAGE", "main"]
