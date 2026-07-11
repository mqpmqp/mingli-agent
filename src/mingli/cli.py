from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .benchmark import benchmark_static
from .bazi import benchmark_charts, validate_benchmarks
from .contracts import get_schema
from .derived import (
    benchmark_static_mappings,
    derive_static_chart,
    load_packaged_capability_manifest,
    load_packaged_source_manifest,
    load_static_assertions,
    validate_static_assertions,
)
from .errors import MingLiError, RuleValidationError
from .phase7 import (
    benchmark_phase7,
    build_bazi_fact_graph,
    build_luck_timeline,
    detect_structural_relations,
    load_phase7_profiles,
    phase7_schema_summary,
    validate_phase7_profiles,
)
from .models import RULE_STATUSES
from .rule_loader import load_rules
from .schema_loader import validate_spec
from .knowledge import import_pilot, inventory, rollback, validate_knowledge


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli", description="MingLi 确定性核心运行时")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate_spec_parser = subcommands.add_parser("validate-spec", help="校验规范 JSON、JSONL 和 Schema")
    validate_spec_parser.add_argument("path", type=Path)

    validate_rules_parser = subcommands.add_parser("validate-rules", help="校验规则文件和唯一 ID")
    validate_rules_parser.add_argument("path", type=Path)

    benchmark_parser = subcommands.add_parser("benchmark-static", help="运行确定性静态策略校验")
    benchmark_parser.add_argument("path", type=Path)
    knowledge_validate = subcommands.add_parser("knowledge-validate", help="校验 Knowledge OS")
    knowledge_validate.add_argument("path", type=Path)
    knowledge_inventory = subcommands.add_parser("knowledge-inventory", help="统计 Knowledge OS 对象")
    knowledge_inventory.add_argument("path", type=Path)
    knowledge_import = subcommands.add_parser("knowledge-import", help="确定性导入知识批次")
    knowledge_import.add_argument("path", type=Path)
    knowledge_rollback = subcommands.add_parser("knowledge-rollback", help="按 manifest 回滚批次")
    knowledge_rollback.add_argument("batch_id")
    knowledge_rollback.add_argument("--dry-run", action="store_true")
    chart_validate = subcommands.add_parser("chart-validate", help="validate deterministic chart contracts")
    chart_validate.add_argument("--strict", action="store_true")
    chart_validate.add_argument(
        "--path",
        type=Path,
        default=Path("tests/fixtures/bazi_independent_benchmarks_v0.1.jsonl"),
    )
    chart_benchmark = subcommands.add_parser("chart-benchmark", help="run deterministic chart benchmarks")
    chart_benchmark.add_argument("--independent-only", action="store_true")
    chart_benchmark.add_argument(
        "--path",
        type=Path,
        default=Path("tests/fixtures/bazi_independent_benchmarks_v0.1.jsonl"),
    )
    phase6 = subcommands.add_parser("phase6", help="Phase 6 静态派生结构工具")
    phase6_subcommands = phase6.add_subparsers(dest="phase6_command", required=True)
    phase6_map = phase6_subcommands.add_parser("map", help="从 Phase 5 结构化结果映射 Phase 6 派生结构")
    phase6_map.add_argument("--input", default="-", help="JSON 文件路径；默认为 stdin")
    phase6_map.add_argument("--profile", default="derived-static-r1@0.1")
    phase6_map.add_argument("--capability", action="append", dest="capabilities")
    phase6_map.add_argument("--allow-partial", action="store_true", help="显式允许 unresolved 依赖返回 partial")
    phase6_validate = phase6_subcommands.add_parser("validate", help="校验 Phase 6 assertion matrix")
    phase6_validate.add_argument("--assertions", type=Path)
    phase6_benchmark = phase6_subcommands.add_parser("benchmark", help="运行 Phase 6 静态映射 benchmark")
    phase6_benchmark.add_argument("--assertions", type=Path)
    phase6_subcommands.add_parser("capabilities", help="输出 Phase 6 capability manifest")
    phase6_subcommands.add_parser("schemas", help="输出 Phase 6 schema 清单")
    phase7 = subcommands.add_parser("phase7", help="Phase 7 deterministic fact graph tools")
    phase7_subcommands = phase7.add_subparsers(dest="phase7_command", required=True)
    phase7_build = phase7_subcommands.add_parser("build", help="build a Phase 7 Bazi fact graph from a Phase 5 base chart")
    phase7_build.add_argument("--input", default="-", help="JSON file path; defaults to stdin")
    phase7_build.add_argument("--dayun-count", type=int, default=10)
    phase7_build.add_argument("--liunian-start-year", type=int)
    phase7_build.add_argument("--liunian-end-year", type=int)
    phase7_timeline = phase7_subcommands.add_parser("timeline", help="build deterministic DaYun and LiuNian timeline facts")
    phase7_timeline.add_argument("--input", default="-", help="JSON file path; defaults to stdin")
    phase7_timeline.add_argument("--dayun-count", type=int, default=10)
    phase7_timeline.add_argument("--liunian-start-year", type=int)
    phase7_timeline.add_argument("--liunian-end-year", type=int)
    phase7_relations = phase7_subcommands.add_parser("relations", help="detect structural stem/branch relations from a derived chart")
    phase7_relations.add_argument("--input", default="-", help="JSON file path; defaults to stdin")
    phase7_subcommands.add_parser("validate", help="validate packaged Phase 7 profiles")
    phase7_subcommands.add_parser("benchmark", help="run Phase 7 assertion matrix")
    phase7_subcommands.add_parser("profiles", help="output Phase 7 profile manifest")
    phase7_subcommands.add_parser("schemas", help="output Phase 7 schema/profile/source metadata")
    return parser


def _read_json_argument(path: str) -> object:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(text)


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

        if args.command == "knowledge-validate":
            issues = validate_knowledge(args.path)
            if issues:
                for issue in issues:
                    print(f"错误：{issue}", file=sys.stderr)
                return 1
            print(f"知识校验通过：{args.path}")
            return 0
        if args.command == "knowledge-inventory":
            print(json.dumps(inventory(args.path), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "knowledge-import":
            manifest = import_pilot(args.path, Path("knowledge"))
            print(f"知识导入完成：{manifest['batch_id']} {json.dumps(manifest['object_counts'], ensure_ascii=False, sort_keys=True)}")
            return 0
        if args.command == "knowledge-rollback":
            print(json.dumps(rollback(args.batch_id, Path("knowledge"), dry_run=args.dry_run), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "chart-validate":
            issues = validate_benchmarks(args.path, strict=args.strict)
            if issues:
                for issue in issues:
                    print(f"error: {issue}", file=sys.stderr)
                return 1
            print(json.dumps({"status": "passed", "strict": args.strict, "path": str(args.path)}, sort_keys=True))
            return 0
        if args.command == "chart-benchmark":
            result = benchmark_charts(args.path, independent_only=args.independent_only)
            payload = {
                "total": result.total,
                "independent": result.independent,
                "passed": result.passed,
                "failed": result.failed,
                "unresolved": result.unresolved,
                "source_agreement": result.source_agreement,
                "categories": result.categories,
            }
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            for failure in result.failures:
                print(f"error: {failure}", file=sys.stderr)
            return 1 if result.failed else 0
        if args.command == "phase6":
            if args.phase6_command == "map":
                value = _read_json_argument(args.input)
                if not isinstance(value, dict):
                    raise ValueError("Phase 6 map input must be a JSON object")
                result = derive_static_chart(
                    value,
                    capabilities=args.capabilities,
                    profile_id=args.profile,
                    strict=not args.allow_partial,
                )
                print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
                return 0
            if args.phase6_command == "validate":
                assertions = load_static_assertions(args.assertions)
                issues = validate_static_assertions(assertions)
                payload = {
                    "assertions": len(assertions),
                    "issues": list(issues),
                    "status": "passed" if not issues else "failed",
                }
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                return 1 if issues else 0
            if args.phase6_command == "benchmark":
                result = benchmark_static_mappings(args.assertions)
                payload = {
                    "total": result.total,
                    "passed": result.passed,
                    "failed": result.failed,
                    "unresolved": result.unresolved,
                    "capabilities": result.capability_counts,
                    "source_groups": result.source_group_counts,
                    "independence_group_violations": result.independence_group_violations,
                    "deterministic_hash_mismatches": result.deterministic_hash_mismatches,
                    "schema_failures": result.schema_failures,
                    "provenance_failures": result.provenance_failures,
                }
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                for failure in result.failures:
                    print(f"error: {failure}", file=sys.stderr)
                return 1 if (result.failed or result.independence_group_violations or result.deterministic_hash_mismatches or result.schema_failures or result.provenance_failures) else 0
            if args.phase6_command == "capabilities":
                print(json.dumps(load_packaged_capability_manifest(), ensure_ascii=False, sort_keys=True))
                return 0
            schema_names = [
                "base_chart_ref.schema.json",
                "derived_chart_result.schema.json",
                "derived_convention_profile.schema.json",
                "derived_error.schema.json",
                "source_manifest.schema.json",
            ]
            payload = {
                "schemas": {name: get_schema(name).get("$id") for name in schema_names},
                "source_manifest": load_packaged_source_manifest()["manifest_version"],
            }
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0

        if args.command == "phase7":
            if args.phase7_command == "build":
                value = _read_json_argument(args.input)
                if not isinstance(value, dict):
                    raise ValueError("Phase 7 build input must be a JSON object")
                result = build_bazi_fact_graph(
                    value,
                    dayun_count=args.dayun_count,
                    liunian_start_year=args.liunian_start_year,
                    liunian_end_year=args.liunian_end_year,
                )
                print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
                return 0
            if args.phase7_command == "timeline":
                value = _read_json_argument(args.input)
                if not isinstance(value, dict):
                    raise ValueError("Phase 7 timeline input must be a JSON object")
                result = build_luck_timeline(
                    value,
                    dayun_count=args.dayun_count,
                    liunian_start_year=args.liunian_start_year,
                    liunian_end_year=args.liunian_end_year,
                )
                print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
                return 0
            if args.phase7_command == "relations":
                value = _read_json_argument(args.input)
                if not isinstance(value, dict):
                    raise ValueError("Phase 7 relations input must be a JSON object")
                payload = {"relations": [fact.to_dict() for fact in detect_structural_relations(value)]}
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
                return 0
            if args.phase7_command == "validate":
                issues = validate_phase7_profiles()
                payload = {"status": "passed" if not issues else "failed", "issues": list(issues)}
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                return 1 if issues else 0
            if args.phase7_command == "benchmark":
                result = benchmark_phase7()
                print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
                for failure in result.failures:
                    print(f"error: {failure}", file=sys.stderr)
                return 1 if (
                    result.failed
                    or result.schema_failures
                    or result.provenance_failures
                    or result.hash_mismatches
                    or result.interval_gaps
                    or result.interval_overlaps
                ) else 0
            if args.phase7_command == "profiles":
                print(json.dumps(load_phase7_profiles(), ensure_ascii=False, sort_keys=True))
                return 0
            print(json.dumps(phase7_schema_summary(), ensure_ascii=False, sort_keys=True))
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
