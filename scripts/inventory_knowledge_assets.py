#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path, PurePath
from typing import Iterable, Sequence

MIB = 1024 * 1024
OVER_50_MB = 50 * MIB
OVER_100_MB = 100 * MIB
HASH_CHUNK_SIZE = MIB


def display_path(path: str | os.PathLike[str] | PurePath) -> str:
    """保留当前平台或 PurePath 的原生路径分隔符。"""
    return os.fspath(path)


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _error(path: object, operation: str, exc: BaseException) -> dict[str, str]:
    return {
        "path": display_path(path),
        "operation": operation,
        "error": str(exc) or exc.__class__.__name__,
    }


def _collect_files(
    inputs: Iterable[str | os.PathLike[str]],
    errors: list[dict[str, str]],
) -> tuple[list[str], list[Path]]:
    roots: list[str] = []
    files: dict[str, Path] = {}

    def add_file(path: Path) -> None:
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            errors.append(_error(path, "resolve", exc))
            return
        key = os.path.normcase(str(resolved))
        files.setdefault(key, resolved)

    for raw_input in inputs:
        raw_path = Path(raw_input).expanduser()
        try:
            root = raw_path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            roots.append(display_path(raw_path))
            errors.append(_error(raw_path, "resolve", exc))
            continue
        roots.append(display_path(root))
        if root.is_file():
            add_file(root)
            continue
        if not root.is_dir():
            errors.append(_error(root, "scan", ValueError("路径不是普通文件或目录")))
            continue

        def on_walk_error(exc: OSError) -> None:
            errors.append(_error(exc.filename or root, "scan", exc))

        for directory, subdirectories, filenames in os.walk(root, followlinks=False, onerror=on_walk_error):
            subdirectories.sort(key=str.casefold)
            for filename in sorted(filenames, key=str.casefold):
                add_file(Path(directory) / filename)

    return roots, [files[key] for key in sorted(files, key=str.casefold)]


def build_inventory(inputs: Sequence[str | os.PathLike[str]]) -> dict:
    """递归读取资料元数据和 SHA-256；不修改任何输入文件。"""
    errors: list[dict[str, str]] = []
    roots, paths = _collect_files(inputs, errors)
    file_records: list[dict] = []
    extension_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "bytes": 0})
    duplicate_groups: dict[str, list[dict]] = defaultdict(list)

    for path in paths:
        try:
            size = path.stat().st_size
        except OSError as exc:
            errors.append(_error(path, "stat", exc))
            continue
        extension = path.suffix.lower() or "[no extension]"
        sha256: str | None = None
        try:
            sha256 = hash_file(path)
        except OSError as exc:
            errors.append(_error(path, "sha256", exc))
        record = {
            "path": display_path(path),
            "size_bytes": size,
            "extension": extension,
            "sha256": sha256,
        }
        file_records.append(record)
        extension_totals[extension]["count"] += 1
        extension_totals[extension]["bytes"] += size
        if sha256 is not None:
            duplicate_groups[sha256].append(record)

    file_records.sort(key=lambda item: item["path"].casefold())
    total_bytes = sum(item["size_bytes"] for item in file_records)
    largest_file = max(file_records, key=lambda item: (item["size_bytes"], item["path"]), default=None)
    duplicate_candidates = [
        {
            "sha256": sha256,
            "size_bytes": records[0]["size_bytes"],
            "files": sorted((item["path"] for item in records), key=str.casefold),
        }
        for sha256, records in sorted(duplicate_groups.items())
        if len(records) > 1
    ]
    return {
        "schema_version": 1,
        "roots": roots,
        "file_count": len(file_records),
        "total_bytes": total_bytes,
        "extensions": {key: extension_totals[key] for key in sorted(extension_totals)},
        "files": file_records,
        "largest_file": largest_file,
        "files_over_50_mb": [item for item in file_records if item["size_bytes"] > OVER_50_MB],
        "files_over_100_mb": [item for item in file_records if item["size_bytes"] > OVER_100_MB],
        "duplicate_candidates": duplicate_candidates,
        "errors": errors,
    }


def _escape_markdown(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def inventory_markdown(inventory: dict) -> str:
    lines = [
        "# 资料清单",
        "",
        "> 本报告只统计文件，不表示已复制、移动、删除或导入资料。",
        "",
        f"- 根路径：{len(inventory['roots'])}",
        f"- 文件数量：{inventory['file_count']}",
        f"- 总大小：{human_bytes(inventory['total_bytes'])}（{inventory['total_bytes']} bytes）",
        f"- 大于 50 MiB：{len(inventory['files_over_50_mb'])}",
        f"- 大于 100 MiB：{len(inventory['files_over_100_mb'])}",
        f"- 重复文件候选组：{len(inventory['duplicate_candidates'])}",
        f"- 读取错误：{len(inventory['errors'])}",
        "",
        "## 按扩展名",
        "",
        "| 扩展名 | 文件数 | 大小 | 字节数 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for extension, summary in inventory["extensions"].items():
        lines.append(
            f"| {_escape_markdown(extension)} | {summary['count']} | "
            f"{human_bytes(summary['bytes'])} | {summary['bytes']} |"
        )

    lines.extend(["", "## 最大文件", ""])
    largest = inventory["largest_file"]
    if largest is None:
        lines.append("无文件。")
    else:
        lines.append(f"- `{_escape_markdown(largest['path'])}`：{human_bytes(largest['size_bytes'])}")

    for title, key in (("大于 50 MiB", "files_over_50_mb"), ("大于 100 MiB", "files_over_100_mb")):
        lines.extend(["", f"## {title}", ""])
        records = inventory[key]
        if records:
            lines.extend(f"- `{_escape_markdown(item['path'])}`：{human_bytes(item['size_bytes'])}" for item in records)
        else:
            lines.append("无。")

    lines.extend(["", "## 重复文件候选", ""])
    if inventory["duplicate_candidates"]:
        for candidate in inventory["duplicate_candidates"]:
            lines.append(f"- SHA-256 `{candidate['sha256']}`，{human_bytes(candidate['size_bytes'])}")
            lines.extend(f"  - `{_escape_markdown(path)}`" for path in candidate["files"])
    else:
        lines.append("无。")

    lines.extend(["", "## 读取错误", ""])
    if inventory["errors"]:
        lines.extend(
            f"- `{_escape_markdown(item['path'])}`（{item['operation']}）：{_escape_markdown(item['error'])}"
            for item in inventory["errors"]
        )
    else:
        lines.append("无。")
    return "\n".join(lines) + "\n"


def write_report_pair(json_data: dict, markdown: str, json_output: Path, markdown_output: Path) -> None:
    outputs = (
        (Path(json_output), json.dumps(json_data, ensure_ascii=False, indent=2) + "\n"),
        (Path(markdown_output), markdown),
    )
    for path, _ in outputs:
        if path.exists():
            raise FileExistsError(f"拒绝覆盖已有文件：{path}")
    for path, _ in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for path, content in outputs:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            created.append(path)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def write_inventory_reports(inventory: dict, json_output: Path, markdown_output: Path) -> None:
    write_report_pair(inventory, inventory_markdown(inventory), json_output, markdown_output)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读统计 MingLi 原始资料")
    parser.add_argument("paths", nargs="+", type=Path, help="一个或多个文件或目录")
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    inventory = build_inventory(args.paths)
    try:
        write_inventory_reports(inventory, args.json_output, args.markdown_output)
    except (OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    print(f"资料统计完成：{inventory['file_count']} 个文件，{inventory['total_bytes']} bytes。")
    if inventory["errors"]:
        print(f"警告：{len(inventory['errors'])} 个路径无法完整读取，详情见报告。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
