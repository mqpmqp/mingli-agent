from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

from .case_record import LiuYaoCaseRecord
from .timing_benchmark import benchmark_liuyao_timing_candidates
from .timing_candidates import TimingRequest, build_timing_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mingli.liuyao.timing_cli",
        description="六爻第三阶段条件化时间候选工具",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    evaluate = commands.add_parser(
        "evaluate",
        help="从冻结案例和有来源锚点生成 review-only 时间候选",
    )
    evaluate.add_argument("--record", required=True, type=Path)
    evaluate.add_argument("--request", required=True, type=Path)

    commands.add_parser("benchmark", help="运行条件化时间候选合成基准")
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
            request = TimingRequest.from_mapping(_read_object(args.request, "request"))
            _print(build_timing_report(record, request).to_dict())
            return 0
        result = benchmark_liuyao_timing_candidates()
        _print(result)
        return 0 if result["status"] == "passed" else 1
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
