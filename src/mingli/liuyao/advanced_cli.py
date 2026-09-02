from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

from .advanced_benchmark import benchmark_liuyao_advanced_facts
from .advanced_runtime import AdvancedContextRequest, build_advanced_runtime_report
from .case_record import LiuYaoCaseRecord
from .validation import LiuYaoError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mingli.liuyao.advanced_cli",
        description="六爻第三阶段高级结构事实与来源门禁工具",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    facts = commands.add_parser(
        "facts",
        help="从冻结案例生成 review-only 高级结构事实报告",
    )
    facts.add_argument("--record", required=True, type=Path)
    facts.add_argument("--context", required=True, type=Path)

    commands.add_parser("benchmark", help="运行第三阶段高级事实合成基准")
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
        if args.command == "facts":
            record = LiuYaoCaseRecord.from_mapping(_read_object(args.record, "record"))
            request = AdvancedContextRequest.from_mapping(_read_object(args.context, "context"))
            _print(build_advanced_runtime_report(record, request).to_dict())
            return 0
        result = benchmark_liuyao_advanced_facts()
        _print(result)
        return 0 if result["status"] == "passed" else 1
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
