from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

from .case_record import LiuYaoCaseRecord
from .validation import LiuYaoError
from .validity_benchmark import benchmark_liuyao_validity_matrix
from .validity_matrix import ValidityRequest, build_validity_matrix


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mingli.liuyao.validity_cli",
        description="六爻第三阶段作用资格与冲突矩阵工具",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    evaluate = commands.add_parser(
        "evaluate",
        help="从冻结案例生成 review-only 有效性矩阵",
    )
    evaluate.add_argument("--record", required=True, type=Path)
    evaluate.add_argument("--request", required=True, type=Path)

    commands.add_parser("benchmark", help="运行有效性与冲突矩阵合成基准")
    return parser


def _read_object(path: Path, name: str) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "evaluate":
            record = LiuYaoCaseRecord.from_mapping(_read_object(args.record, "record"))
            request = ValidityRequest.from_mapping(_read_object(args.request, "request"))
            _print(build_validity_matrix(record, request).to_dict())
            return 0
        result = benchmark_liuyao_validity_matrix()
        _print(result)
        return 0 if result["status"] == "passed" else 1
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
