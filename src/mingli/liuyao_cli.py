from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

from .liuyao import (
    LiuYaoCaseRecord,
    LiuYaoCastInput,
    LiuYaoError,
    PredictionVersion,
    activate_prediction,
    append_prediction,
    benchmark_liuyao,
    build_liuyao_chart,
    invalidate_prediction,
    register_cast,
    settle_prediction,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli-liuyao", description="六爻确定性排盘、输入门禁与版本结算工具")
    commands = parser.add_subparsers(dest="command", required=True)

    chart = commands.add_parser("chart", help="校验六摇并输出本卦、变卦、八宫、世应、纳甲与六亲")
    chart.add_argument("--input", required=True, type=Path)

    register = commands.add_parser("register", help="新建案例或校验同 case_id 的重复输入")
    register.add_argument("--input", required=True, type=Path)
    register.add_argument("--existing", type=Path)

    add_version = commands.add_parser("add-version", help="向案例追加 draft/pending 预测版本")
    add_version.add_argument("--record", required=True, type=Path)
    add_version.add_argument("--version", required=True, type=Path)
    add_version.add_argument("--not-current", action="store_true")

    activate = commands.add_parser("activate", help="把冻结 draft 发布为 current pending 版本")
    activate.add_argument("--record", required=True, type=Path)
    activate.add_argument("--version-id", required=True)
    activate.add_argument("--at", required=True)

    invalidate = commands.add_parser("invalidate", help="作废旧预测版本但保留历史")
    invalidate.add_argument("--record", required=True, type=Path)
    invalidate.add_argument("--version-id", required=True)
    invalidate.add_argument("--reason", required=True)
    invalidate.add_argument("--at", required=True)

    settle = commands.add_parser("settle", help="按冻结事件合同登记结算结果")
    settle.add_argument("--record", required=True, type=Path)
    settle.add_argument("--version-id", required=True)
    settle.add_argument("--outcome", required=True, choices=("hit", "miss", "partial", "indeterminate"))
    settle.add_argument("--observed-at", required=True)
    settle.add_argument("--source", required=True)
    settle.add_argument("--note", action="append", default=[])

    commands.add_parser("benchmark", help="运行六爻确定性内置基准")
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
        if args.command == "chart":
            cast = LiuYaoCastInput.from_mapping(_read_object(args.input, "cast"))
            _print(build_liuyao_chart(cast).to_dict())
            return 0
        if args.command == "register":
            cast = LiuYaoCastInput.from_mapping(_read_object(args.input, "cast"))
            existing = None if args.existing is None else LiuYaoCaseRecord.from_mapping(_read_object(args.existing, "record"))
            _print(register_cast(existing, cast).to_dict())
            return 0
        if args.command == "add-version":
            record = LiuYaoCaseRecord.from_mapping(_read_object(args.record, "record"))
            version = PredictionVersion.from_mapping(_read_object(args.version, "version"))
            _print(append_prediction(record, version, make_current=not args.not_current).to_dict())
            return 0
        if args.command == "activate":
            record = LiuYaoCaseRecord.from_mapping(_read_object(args.record, "record"))
            _print(activate_prediction(record, args.version_id, published_at=args.at).to_dict())
            return 0
        if args.command == "invalidate":
            record = LiuYaoCaseRecord.from_mapping(_read_object(args.record, "record"))
            _print(invalidate_prediction(record, args.version_id, reason=args.reason, invalidated_at=args.at).to_dict())
            return 0
        if args.command == "settle":
            record = LiuYaoCaseRecord.from_mapping(_read_object(args.record, "record"))
            _print(
                settle_prediction(
                    record,
                    args.version_id,
                    outcome=args.outcome,
                    observed_at=args.observed_at,
                    evidence_source=args.source,
                    notes=tuple(args.note),
                ).to_dict()
            )
            return 0
        result = benchmark_liuyao()
        _print(result)
        return 0 if result["status"] == "passed" else 1
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if isinstance(exc, LiuYaoError) and exc.code in {"INPUT_CONFLICT", "CONTRACT_CONFLICT", "CASE_ID_CONFLICT"}:
            return 2
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
