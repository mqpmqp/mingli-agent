from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    file: str
    line: int
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.path}: {self.message}"


@dataclass(frozen=True, slots=True)
class _Record:
    line: int
    value: Any


def _json_path(parts: object) -> str:
    result = "$"
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}"
    return result


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _schema_key(path: Path) -> str | None:
    suffix = ".schema.json"
    return path.name[: -len(suffix)] if path.name.endswith(suffix) else None


def _singular(name: str) -> str:
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("s"):
        return name[:-1]
    return name


def _matching_schema(
    path: Path,
    root: Path,
) -> Path | None:
    base = path.name.removesuffix(path.suffix)
    candidates = (base, _singular(base))
    for key in candidates:
        sibling = path.parent / f"{key}.schema.json"
        if sibling.is_file():
            return sibling

    try:
        under_rules = (root / "rules") in path.parents
    except OSError:
        under_rules = False
    rule_schema = root / "rules" / "rule.schema.json"
    if path.suffix == ".jsonl" and under_rules and rule_schema.is_file():
        return rule_schema

    return None


def validate_spec(root: str | Path) -> tuple[ValidationIssue, ...]:
    """只读解析所有 JSON/JSONL，并验证 schemas 与可匹配的数据文件。"""
    source_root = Path(root).resolve()
    if not source_root.is_dir():
        return (ValidationIssue(str(source_root), 1, "$", "规范目录不存在或不是目录"),)

    issues: list[ValidationIssue] = []
    records: dict[Path, list[_Record]] = {}
    paths = sorted((*source_root.rglob("*.json"), *source_root.rglob("*.jsonl")))
    for path in paths:
        rel = _relative(path, source_root)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(ValidationIssue(rel, 1, "$", f"无法读取 UTF-8 文件：{exc}"))
            continue
        if path.suffix == ".jsonl":
            parsed: list[_Record] = []
            for line_no, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    parsed.append(_Record(line_no, json.loads(line)))
                except json.JSONDecodeError as exc:
                    issues.append(
                        ValidationIssue(rel, line_no, "$", f"JSONL 解析失败（列 {exc.colno}）：{exc.msg}")
                    )
            records[path] = parsed
        else:
            try:
                records[path] = [_Record(1, json.loads(text))]
            except json.JSONDecodeError as exc:
                issues.append(
                    ValidationIssue(rel, exc.lineno, "$", f"JSON 解析失败（列 {exc.colno}）：{exc.msg}")
                )

    schemas: dict[Path, dict[str, Any]] = {}
    for path, parsed in records.items():
        if _schema_key(path) is None or not parsed:
            continue
        schema = parsed[0].value
        if not isinstance(schema, dict):
            issues.append(
                ValidationIssue(
                    _relative(path, source_root),
                    parsed[0].line,
                    "$",
                    "JSON Schema 顶层必须是 object",
                )
            )
            continue
        schemas[path] = schema
        try:
            validator_for(schema).check_schema(schema)
        except SchemaError as exc:
            issues.append(
                ValidationIssue(
                    _relative(path, source_root),
                    1,
                    _json_path(exc.absolute_path),
                    f"JSON Schema 无效：{exc.message}",
                )
            )

    registry: Registry = Registry()
    validation_schemas: dict[Path, dict[str, Any]] = {}
    for path, schema in schemas.items():
        schema_with_base = dict(schema)
        schema_with_base.setdefault("$id", path.resolve().as_uri())
        validation_schemas[path] = schema_with_base
        registry = registry.with_resource(
            path.resolve().as_uri(),
            Resource.from_contents(schema_with_base, default_specification=DRAFT202012),
        )

    for path, parsed in records.items():
        if path in schemas:
            continue
        schema_path = _matching_schema(path, source_root)
        if schema_path is None or schema_path not in schemas:
            continue
        schema = validation_schemas[schema_path]
        validator_class = validator_for(schema)
        validator = validator_class(schema, registry=registry, format_checker=FormatChecker())
        for record in parsed:
            for error in sorted(
                validator.iter_errors(record.value),
                key=lambda item: tuple(str(part) for part in item.absolute_path),
            ):
                issues.append(
                    ValidationIssue(
                        _relative(path, source_root),
                        record.line,
                        _json_path(error.absolute_path),
                        f"Schema 校验失败：{error.message}",
                    )
                )

    return tuple(issues)
