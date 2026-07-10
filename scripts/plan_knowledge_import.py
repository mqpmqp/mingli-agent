#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

try:
    from scripts.inventory_knowledge_assets import human_bytes, write_report_pair
except ModuleNotFoundError:  # Direct execution: python scripts/plan_knowledge_import.py
    from inventory_knowledge_assets import human_bytes, write_report_pair

MIB = 1024 * 1024
SPLIT_THRESHOLD_BYTES = 500 * MIB
MAIN_REPOSITORY = "mqpmqp/mingli-agent"
KNOWLEDGE_REPOSITORY = "mqpmqp/mingli-knowledge"

STRUCTURED_EXTENSIONS = {".md", ".json", ".jsonl", ".yaml", ".yml"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar", ".tar", ".gz"}
DATASET_EXTENSIONS = {".csv", ".tsv", ".parquet", ".sqlite", ".db"}

CATEGORY_RECOMMENDATIONS = (
    {
        "category": "structured_knowledge",
        "extensions": sorted(STRUCTURED_EXTENSIONS),
        "target": "knowledge/<人工确认的领域>/",
        "rule": "仅存放经过整理、可检索且已标明来源的内容。",
    },
    {
        "category": "source_document",
        "extensions": [".pdf", ".doc", ".docx", ".epub", ".txt"],
        "target": "references/books/ 或 references/papers/",
        "rule": "保持原始来源，不混入规则目录。",
    },
    {
        "category": "source_image",
        "extensions": sorted(IMAGE_EXTENSIONS),
        "target": "references/images/ 或 references/screenshots/",
        "rule": "按来源类型人工确认，不从图片自动生成规则真值。",
    },
    {
        "category": "source_archive",
        "extensions": sorted(ARCHIVE_EXTENSIONS),
        "target": "references/courses/（需人工确认内容）",
        "rule": "压缩档案保持原样并记录来源。",
    },
    {
        "category": "dataset",
        "extensions": sorted(DATASET_EXTENSIONS),
        "target": "datasets/",
        "rule": "提交前检查许可、隐私、格式和体积。",
    },
    {
        "category": "unclassified_source",
        "extensions": ["其他"],
        "target": "references/cases/（暂存前人工确认）",
        "rule": "不得自动提升为规则或已验证知识。",
    },
)


def _classify(extension: str) -> tuple[str, str, bool]:
    extension = extension.lower()
    if extension in STRUCTURED_EXTENSIONS:
        return "structured_knowledge", "knowledge/<人工确认的领域>/", False
    if extension == ".pdf" or extension in {".doc", ".docx", ".epub", ".txt"}:
        return "source_document", "references/books/ 或 references/papers/", True
    if extension in IMAGE_EXTENSIONS:
        return "source_image", "references/images/ 或 references/screenshots/", True
    if extension in ARCHIVE_EXTENSIONS:
        return "source_archive", "references/courses/（需人工确认内容）", True
    if extension in DATASET_EXTENSIONS:
        return "dataset", "datasets/", True
    return "unclassified_source", "references/cases/（暂存前人工确认）", True


def _validate_inventory(inventory: object) -> dict:
    if not isinstance(inventory, dict):
        raise ValueError("inventory JSON 顶层必须是对象")
    for key in ("file_count", "total_bytes", "files"):
        if key not in inventory:
            raise ValueError(f"inventory JSON 缺少字段：{key}")
    if not isinstance(inventory["total_bytes"], int) or inventory["total_bytes"] < 0:
        raise ValueError("total_bytes 必须是非负整数")
    if not isinstance(inventory["files"], list):
        raise ValueError("files 必须是数组")
    return inventory


def create_import_plan(inventory: dict) -> dict:
    inventory = _validate_inventory(inventory)
    total_bytes = inventory["total_bytes"]
    decision = "single_repo" if total_bytes < SPLIT_THRESHOLD_BYTES else "split_repo"
    recommended_repository = MAIN_REPOSITORY if decision == "single_repo" else KNOWLEDGE_REPOSITORY
    file_plans: list[dict] = []
    for item in inventory["files"]:
        if not isinstance(item, dict):
            raise ValueError("files 只能包含对象")
        extension = item.get("extension", "[no extension]")
        if not isinstance(extension, str):
            raise ValueError("文件 extension 必须是字符串")
        category, target, raw_source = _classify(extension)
        repository = KNOWLEDGE_REPOSITORY if decision == "split_repo" and raw_source else MAIN_REPOSITORY
        file_plans.append(
            {
                "source_path": item.get("path"),
                "size_bytes": item.get("size_bytes"),
                "extension": extension,
                "category": category,
                "recommended_repository": repository,
                "recommended_target": target,
                "action": "plan_only",
            }
        )

    warnings = ["本计划不执行复制、移动、删除、改名、远端建仓或 Git 提交。"]
    if inventory.get("errors"):
        warnings.append("inventory 含读取错误；修复并重新统计后再执行真实迁移。")
    if inventory.get("files_over_100_mb"):
        warnings.append("存在大于 100 MiB 的文件，不能直接提交到普通 Git；需使用 Git LFS 或外部存储。")
    if decision == "split_repo":
        warnings.append("达到 500 MiB 阈值；原始二进制资料应进入独立 mingli-knowledge 仓库。")

    return {
        "schema_version": 1,
        "decision": decision,
        "threshold_bytes": SPLIT_THRESHOLD_BYTES,
        "total_bytes": total_bytes,
        "recommended_repository": recommended_repository,
        "rationale": (
            "原始资料总量小于 500 MiB，可保留在 mingli-agent/references。"
            if decision == "single_repo"
            else "原始资料总量达到或超过 500 MiB，原始二进制资料应与运行时代码分仓。"
        ),
        "category_recommendations": list(CATEGORY_RECOMMENDATIONS),
        "suggested_split_repository_layout": [
            "references/books/",
            "references/papers/",
            "references/courses/",
            "references/screenshots/",
            "references/images/",
            "references/cases/",
            "datasets/",
            "inventories/",
        ],
        "files": file_plans,
        "warnings": warnings,
    }


def plan_markdown(plan: dict) -> str:
    lines = [
        "# 资料导入计划",
        "",
        "> 本计划不执行复制或移动，也不创建远端仓库。",
        "",
        f"- 决策：`{plan['decision']}`",
        f"- 总大小：{human_bytes(plan['total_bytes'])}（{plan['total_bytes']} bytes）",
        f"- 500 MiB 阈值：{plan['threshold_bytes']} bytes",
        f"- 建议仓库：`{plan['recommended_repository']}`",
        f"- 原因：{plan['rationale']}",
        "",
        "## 分类建议",
        "",
        "| 类别 | 扩展名 | 目标 | 约束 |",
        "| --- | --- | --- | --- |",
    ]
    for item in plan["category_recommendations"]:
        lines.append(
            f"| {item['category']} | {', '.join(item['extensions'])} | "
            f"{item['target']} | {item['rule']} |"
        )
    lines.extend(["", "## 文件计划", ""])
    if plan["files"]:
        for item in plan["files"]:
            lines.append(
                f"- `{item['source_path']}` → `{item['recommended_repository']}` / "
                f"`{item['recommended_target']}`（仅规划）"
            )
    else:
        lines.append("inventory 中没有文件。")
    lines.extend(["", "## 警告", ""])
    lines.extend(f"- {warning}" for warning in plan["warnings"])
    return "\n".join(lines) + "\n"


def write_plan_reports(plan: dict, json_output: Path, markdown_output: Path) -> None:
    write_report_pair(plan, plan_markdown(plan), json_output, markdown_output)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="根据资料 inventory 生成只读导入计划")
    parser.add_argument("inventory", type=Path, help="inventory JSON")
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        plan = create_import_plan(inventory)
        write_plan_reports(plan, args.json_output, args.markdown_output)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    print(f"导入计划已生成：{plan['decision']}；未执行任何迁移。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
