from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

from .product_runtime import run_product_runtime
from .training import TrainingError, TrainingStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli training", description="MingLi 日常训练闭环")
    commands = parser.add_subparsers(dest="training_command", required=True)
    for name in ("run", "feedback", "outcome"):
        command = commands.add_parser(name)
        command.add_argument("--input", required=True, help="JSON 文件；- 表示 stdin")
        _store_arguments(command)
    show = commands.add_parser("show")
    show.add_argument("--case-id", required=True)
    _store_arguments(show)
    review = commands.add_parser("review")
    review.add_argument("--create-iteration-at", help="ISO 8601 时间；提供时生成待人工审查候选和迭代快照")
    _store_arguments(review)
    candidates = commands.add_parser("candidates")
    _store_arguments(candidates)
    withdraw = commands.add_parser("withdraw")
    withdraw.add_argument("--case-id", required=True)
    withdraw.add_argument("--withdrawn-at", required=True)
    _store_arguments(withdraw)
    return parser


def _store_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--json", action="store_true", help="输出稳定 JSON envelope（当前唯一输出格式）")


def _read(path: str) -> dict[str, object]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise TrainingError("SCHEMA_INCOMPATIBLE", "input JSON must be an object")
    return value


def _emit(value: Mapping[str, object]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        store = TrainingStore(args.store, repository_root=args.repository_root, synthetic=args.synthetic)
        command = args.training_command
        if command == "run":
            result = run_product_runtime(_read(args.input), store=store)
            _emit({"status": "ok" if result["status"] != "blocked" else "blocked", "data": result})
            if result["status"] == "blocked":
                return 3
            training_write = result.get("training_write", {})
            if isinstance(training_write, Mapping) and training_write.get("attempted") is True and training_write.get("stored") is not True:
                return 2
            return 0
        if command == "feedback":
            result = store.add_feedback(_read(args.input))
        elif command == "outcome":
            result = store.add_outcome(_read(args.input))
        elif command == "show":
            result = store.show_case(args.case_id)
        elif command == "candidates":
            result = {"candidates": store.candidates()}
        elif command == "withdraw":
            result = store.withdraw(args.case_id, withdrawn_at=args.withdrawn_at)
        else:
            report = store.review()
            result = {
                **report,
                "iteration": store.create_review_iteration(created_at=args.create_iteration_at)
                if args.create_iteration_at
                else None,
            }
        _emit({"status": "ok", "data": result})
        return 0
    except TrainingError as exc:
        _emit({"status": "error", "error": exc.to_dict()})
        return exc.exit_code
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _emit({"status": "error", "error": {"code": "INPUT_IO_ERROR", "message": type(exc).__name__}})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
