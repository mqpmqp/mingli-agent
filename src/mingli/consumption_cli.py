from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .consumption_v1 import ConsumptionV1
from .training import TrainingError, TrainingStore


def _read_json(path: str) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("输入 JSON 必须是对象")
    return value


def _manager(args: argparse.Namespace) -> ConsumptionV1:
    store = TrainingStore(
        args.store,
        repository_root=args.repository_root,
        synthetic=args.synthetic,
    )
    return ConsumptionV1(store)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli-consumption")
    parser.add_argument("--store", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--synthetic", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    stage = sub.add_parser("stage-review")
    stage.add_argument("--input", required=True)

    decide = sub.add_parser("decide")
    decide.add_argument("--input", required=True)

    publish = sub.add_parser("publish")
    publish.add_argument("--input", required=True)

    retrieve = sub.add_parser("retrieve")
    retrieve.add_argument("--domain", required=True, choices=["bazi", "qimen", "fengshui"])
    retrieve.add_argument("--scenario", required=True)
    retrieve.add_argument("--topic", required=True)
    retrieve.add_argument("--query-id", required=True)
    retrieve.add_argument("--consumed-at", required=True)
    retrieve.add_argument("--mode", choices=["SHADOW", "ACTIVE"], default="SHADOW")

    sub.add_parser("status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manager = _manager(args)
        if args.command == "stage-review":
            data = manager.stage_review_asset(_read_json(args.input))
        elif args.command == "decide":
            data = manager.decide_review(_read_json(args.input))
        elif args.command == "publish":
            data = manager.publish_approved_asset(_read_json(args.input))
        elif args.command == "retrieve":
            data = manager.retrieve(
                domain=args.domain,
                scenario=args.scenario,
                topic=args.topic,
                query_id=args.query_id,
                consumed_at=args.consumed_at,
                mode=args.mode,
            )
        else:
            data = manager.status()
    except (TrainingError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "ok", "data": data}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
