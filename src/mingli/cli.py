from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .benchmark import benchmark_static
from .errors import MingLiError, RuleValidationError
from .models import RULE_STATUSES
from .rule_loader import load_rules
from .schema_loader import validate_spec


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli", description="MingLi 确定性核心运行时")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate_spec_parser = subcommands.add_parser("validate-spec", help="校验规范 JSON、JSONL 和 Schema")
    validate_spec_parser.add_argument("path", type=Path)

    validate_rules_parser = subcommands.add_parser("validate-rules", help="校验规则文件和唯一 ID")
    validate_rules_parser.add_argument("path", type=Path)

    benchmark_parser = subcommands.add_parser("benchmark-static", help="运行确定性静态策略校验")
    benchmark_parser.add_argument("path", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-spec":
            issues = validate_spec(args.path)
            if issues:
                for issue in issues:
                    print(f"错误：{issue}", file=sys.stderr)
                print(f"规范校验失败：共 {len(issues)} 个错误。", file=sys.stderr)
                return 1
            print(f"规范校验通过：{args.path}")
            return 0

        if args.command == "validate-rules":
            rules = load_rules(args.path, statuses=RULE_STATUSES)
            print(f"规则校验通过：{len(rules)} 条规则，ID 均唯一，状态未被修改。")
            return 0

        result = benchmark_static(args.path)
        if result.failures:
            for failure in result.failures:
                print(f"错误：{failure}", file=sys.stderr)
            print(
                f"静态基准失败：黄金案例 {result.passed}/{result.total}，"
                f"实战结构 {result.practical_passed}/{result.practical_total}。",
                file=sys.stderr,
            )
            return 1
        print(
            f"静态基准通过：黄金案例 {result.passed}/{result.total}，"
            f"实战结构 {result.practical_passed}/{result.practical_total}。"
        )
        print("说明：仅验证确定性策略与结构，不代表真实模型或命理预测准确率。")
        return 0
    except RuleValidationError as exc:
        for issue in exc.issues:
            print(f"错误：{issue}", file=sys.stderr)
        return 1
    except (MingLiError, OSError, UnicodeError, ValueError, TypeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
