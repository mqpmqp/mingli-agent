from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .rule_runtime_v1 import RuleAwareRuntime
from .training import TrainingError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mingli-rule-runtime",
        description="加载已人工批准的小时训练规则版本并运行开发/真人试点 Runtime",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "analyze",
        "apply",
        "capabilities",
        "runtime-instructions",
        "phase4-1-binding",
        "phase4-1-bind-prediction",
    ):
        command = commands.add_parser(name)
        command.add_argument("--store", type=Path, required=True)
        command.add_argument("--repository-root", type=Path, default=Path.cwd())
        command.add_argument("--version")
        command.add_argument("--synthetic", action="store_true")
        if name in {"analyze", "apply", "phase4-1-bind-prediction"}:
            command.add_argument("--input", required=True, help="Runtime JSON 文件；- 表示 stdin")
        if name == "apply":
            command.add_argument("--domain", required=True, choices=("bazi", "qimen", "fengshui"))
    return parser


def _read(path: str) -> object:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        runtime = RuleAwareRuntime(
            args.store,
            repository_root=args.repository_root,
            version=args.version,
            synthetic=args.synthetic,
        )
        if args.command == "analyze":
            result = runtime.analyze(_read(args.input))
        elif args.command == "apply":
            raw_result = _read(args.input)
            if not isinstance(raw_result, dict):
                raise ValueError("Runtime result must be an object")
            result = runtime.apply(raw_result, domain=args.domain)
        elif args.command == "capabilities":
            result = runtime.capabilities()
        elif args.command == "runtime-instructions":
            result = runtime.runtime_instructions()
        elif args.command == "phase4-1-bind-prediction":
            prediction = _read(args.input)
            if not isinstance(prediction, dict):
                raise ValueError("Phase 4.1 prediction must be an object")
            result = runtime.bind_phase4_1_prediction(prediction)
        else:
            result = runtime.phase4_1_binding()
        print(json.dumps({"status": "ok", "data": result}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    except TrainingError as exc:
        print(json.dumps({"status": "error", "error": exc.to_dict()}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return exc.exit_code
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": {"code": "RUNTIME_INPUT_ERROR", "message": type(exc).__name__}}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
