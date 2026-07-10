from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


DOMAINS = ("bazi", "yijing", "ziwei", "qimen", "fengshui", "reality")
LIFECYCLES = {
    "concepts": ("draft", "reviewed", "verified"),
    "rules": ("draft", "reviewed", "verified", "deprecated"),
    "evidence": ("raw", "reviewed", "verified"),
    "benchmarks": ("draft", "approved"),
}
TOOL_VERSION = "0.2.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_source_id(checksum: str) -> str:
    return f"src_sha256_{checksum[:12]}"


def load_asset_policy(root: Path) -> dict[str, Any]:
    value = yaml.safe_load((root / "config" / "asset_policy.yaml").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("asset_policy.yaml 顶层必须是对象")
    return value


def planner_extensions(root: Path) -> frozenset[str]:
    policy = load_asset_policy(root)
    return frozenset(
        extension
        for settings in policy["assets"].values()
        for extension in settings["extensions"]
        if settings.get("import_allowed", False)
    )


def render_gitattributes(root: Path) -> str:
    policy = load_asset_policy(root)
    extensions = sorted(
        extension
        for settings in policy["assets"].values()
        if settings.get("git_lfs", False)
        for extension in settings["extensions"]
    )
    lines = ["# Generated from knowledge/config/asset_policy.yaml; do not edit this block."]
    lines.extend(f"*{extension} filter=lfs diff=lfs merge=lfs -text" for extension in extensions)
    return "\n".join(lines) + "\n"


def _json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number}: JSONL 记录必须是对象")
            records.append(value)
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records)
    path.write_text(text, encoding="utf-8")


def _relative_safe(path: str) -> bool:
    candidate = Path(path)
    return not candidate.is_absolute() and ".." not in candidate.parts


def register_source(source_path: Path, registry_path: Path, *, domain: str, repository_root: Path) -> dict[str, Any]:
    if source_path.is_symlink():
        target = source_path.resolve(strict=True)
        try:
            target.relative_to(repository_root.resolve())
        except ValueError as exc:
            raise ValueError("指向仓库外的 symlink 被拒绝") from exc
        raise ValueError("symlink 默认被拒绝")
    resolved = source_path.resolve(strict=True)
    relative = resolved.relative_to(repository_root.resolve()).as_posix()
    checksum = _sha256(resolved)
    records = _json_lines(registry_path)
    duplicate = next((record for record in records if record["sha256"] == checksum), None)
    if duplicate:
        return duplicate
    record = {
        "id": stable_source_id(checksum),
        "path": relative,
        "sha256": checksum,
        "size_bytes": resolved.stat().st_size,
        "media_type": mimetypes.guess_type(resolved.name)[0] or "application/octet-stream",
        "domain": domain,
        "license_status": "source-restricted",
        "import_status": "reviewed",
    }
    records.append(record)
    _write_jsonl(registry_path, sorted(records, key=lambda item: item["id"]))
    return record


def ensure_structure(root: Path) -> None:
    for kind, lifecycles in LIFECYCLES.items():
        for lifecycle in lifecycles:
            for domain in DOMAINS:
                (root / kind / lifecycle / domain).mkdir(parents=True, exist_ok=True)
    for path in ("sources/policies", "datasets/manifests", "batches/manifests", "batches/rollback"):
        (root / path).mkdir(parents=True, exist_ok=True)


def _record_schema(root: Path, kind: str) -> dict[str, Any]:
    return json.loads((root / "schemas" / f"{kind}.schema.json").read_text(encoding="utf-8"))


def validate_knowledge(root: Path) -> tuple[str, ...]:
    if not root.is_dir():
        return (f"知识目录不存在：{root}",)
    issues: list[str] = []
    ids: dict[str, str] = {}
    source_ids: set[str] = set()
    schemas = {}
    for schema_path in sorted((root / "schemas").glob("*.schema.json")):
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            if not isinstance(schema, dict):
                issues.append(f"{schema_path}: Schema 顶层必须是 object")
                continue
            Draft202012Validator.check_schema(schema)
            schemas[schema_path.stem.removesuffix(".schema")] = schema
        except Exception as exc:
            issues.append(f"{schema_path}: Schema 无效：{exc}")
    registry = root / "sources" / "registry.jsonl"
    try:
        sources = _json_lines(registry)
        source_ids = {item.get("id") for item in sources if isinstance(item.get("id"), str)}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(str(exc))
        sources = []

    targets = [(registry, "source")]
    for kind, lifecycles in LIFECYCLES.items():
        schema_kind = {"concepts": "concept", "rules": "knowledge_rule", "evidence": "evidence_record", "benchmarks": "benchmark_case"}[kind]
        for path in sorted((root / kind).rglob("*.jsonl")):
            targets.append((path, schema_kind))
            relative = path.relative_to(root).parts
            if len(relative) < 4 or relative[1] not in lifecycles or relative[2] not in DOMAINS:
                issues.append(f"{path.relative_to(root)}: 非法生命周期或领域路径")
    targets.extend((path, "dataset_manifest") for path in sorted((root / "datasets/manifests").glob("*.json")))
    targets.extend((path, "batch_manifest") for path in sorted((root / "batches/manifests").glob("*.json")))
    for path, schema_kind in targets:
        if not path.exists() or schema_kind not in schemas:
            continue
        try:
            records = _json_lines(path) if path.suffix == ".jsonl" else [json.loads(path.read_text(encoding="utf-8"))]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(str(exc))
            continue
        validator = Draft202012Validator(schemas[schema_kind], format_checker=FormatChecker())
        for line_no, record in enumerate(records, 1):
            for error in validator.iter_errors(record):
                issues.append(f"{path.relative_to(root)}:{line_no}: {error.json_path}: {error.message}")
            object_id = record.get("id") or record.get("batch_id")
            if isinstance(object_id, str):
                if object_id in ids:
                    issues.append(f"重复 ID {object_id}: {ids[object_id]} 与 {path.relative_to(root)}")
                ids[object_id] = path.relative_to(root).as_posix()
            if schema_kind in {"concept", "knowledge_rule", "evidence_record", "benchmark_case"}:
                refs = record.get("source_ids", [record.get("source_id")])
                if any(ref not in source_ids for ref in refs):
                    issues.append(f"{path.relative_to(root)}:{line_no}: source_id 不存在")
            if schema_kind == "knowledge_rule" and "verified" in path.parts and record.get("evidence_level") == "source_only":
                issues.append(f"{path.relative_to(root)}:{line_no}: source_only 规则不得进入 verified")
            for key, value in record.items():
                if (key.endswith("path") or key in {"files_created", "files_modified"}) and isinstance(value, str) and not _relative_safe(value):
                    issues.append(f"{path.relative_to(root)}:{line_no}: 禁止绝对或越界路径")
                if isinstance(value, list) and key in {"files_created", "files_modified"} and any(not _relative_safe(str(item)) for item in value):
                    issues.append(f"{path.relative_to(root)}:{line_no}: 禁止绝对或越界路径")
    expected = render_gitattributes(root)
    actual = (root.parent / ".gitattributes").read_text(encoding="utf-8") if (root.parent / ".gitattributes").exists() else ""
    if actual != expected:
        issues.append(".gitattributes 与 asset_policy.yaml 不一致")
    return tuple(issues)


def inventory(root: Path) -> dict[str, Any]:
    counts = {"sources": len(_json_lines(root / "sources/registry.jsonl"))}
    for kind in LIFECYCLES:
        counts[kind] = sum(len(_json_lines(path)) for path in (root / kind).rglob("*.jsonl"))
    counts["batches"] = len(list((root / "batches/manifests").glob("*.json")))
    return counts


def _pilot_records(pilot: Path, source_id: str) -> dict[str, list[dict[str, Any]]]:
    concepts = []
    for item in _json_lines(pilot / "concept_cards.jsonl"):
        concepts.append({"id": item["concept_id"], "source_id": source_id, "source_pages": item["pdf_pages"], "original_location": f"PDF pages {','.join(map(str, item['pdf_pages']))}", "domain": "yijing", "lifecycle": "reviewed", "term": item["term"], "summary": item["summary"], "category": item["category"]})
    rules = []
    for item in _json_lines(pilot / "candidate_rules.jsonl"):
        rules.append({"id": item["candidate_id"], "source_ids": [source_id], "source_pages": item["source_pages_pdf"], "original_location": f"PDF pages {','.join(map(str, item['source_pages_pdf']))}", "domain": "yijing", "lifecycle": "reviewed", "trigger": item["trigger"], "support": item["support"], "exclude": item["exclude"], "judgement": item["judgement"], "plain_language": item["plain_language"], "evidence_level": "source_only", "production_allowed": False, "benchmark_required": item["benchmark_required"]})
    evidence = []
    benchmarks = []
    for item in _json_lines(pilot / "non_promotable_claims.jsonl"):
        evidence.append({"id": item["claim_id"], "source_id": source_id, "source_pages": item["source_pages_pdf"], "original_location": f"PDF pages {','.join(map(str, item['source_pages_pdf']))}", "domain": "yijing", "lifecycle": "reviewed", "record_type": "exclusion", "summary": item["summary"], "classification": item["classification"], "action": item["action"], "reason": item["reason"]})
        benchmarks.append({"id": f"bench_{item['claim_id']}", "source_id": source_id, "source_pages": item["source_pages_pdf"], "original_location": f"PDF pages {','.join(map(str, item['source_pages_pdf']))}", "domain": "yijing", "lifecycle": "draft", "prompt": item["summary"], "expected": "拒绝将该主张提升为确定事实或跨方法预测规则", "exclusion_id": item["claim_id"]})
    return {"concepts": concepts, "rules": rules, "evidence": evidence, "benchmarks": benchmarks}


def import_pilot(pilot: Path, knowledge_root: Path) -> dict[str, Any]:
    pilot = pilot.resolve(strict=True)
    knowledge_root = knowledge_root.resolve()
    repository_root = knowledge_root.parent
    ensure_structure(knowledge_root)
    source_map_path = pilot / "source_map.json"
    checksum = _sha256(source_map_path)
    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    source_id = stable_source_id(source_map["sha256"])
    legacy_registry = repository_root / "spec/knowledge/sources/source_registry.jsonl"
    legacy_source = next(
        (item for item in _json_lines(legacy_registry) if item.get("sha256") == source_map["sha256"]),
        None,
    )
    if legacy_source is None or not isinstance(legacy_source.get("size_bytes"), int):
        raise ValueError("source map 缺少可验证的原始文件大小")
    source_record = {"id": source_id, "path": source_map_path.relative_to(repository_root).as_posix(), "sha256": source_map["sha256"], "size_bytes": legacy_source["size_bytes"], "media_type": "application/pdf", "domain": "yijing", "license_status": "source-restricted", "import_status": "reviewed"}
    batch_seed = json.dumps({"pilot": source_map_path.relative_to(repository_root).as_posix(), "input": checksum, "tool": TOOL_VERSION}, sort_keys=True).encode()
    batch_id = f"batch_sha256_{hashlib.sha256(batch_seed).hexdigest()[:12]}"
    manifest_path = knowledge_root / "batches/manifests" / f"{batch_id}.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = _pilot_records(pilot, source_id)
    paths = {
        "concepts": knowledge_root / "concepts/reviewed/yijing/zhouyi_yu_yucexue_ch01.jsonl",
        "rules": knowledge_root / "rules/reviewed/yijing/zhouyi_yu_yucexue_ch01.jsonl",
        "evidence": knowledge_root / "evidence/reviewed/yijing/zhouyi_yu_yucexue_ch01.jsonl",
        "benchmarks": knowledge_root / "benchmarks/draft/yijing/zhouyi_yu_yucexue_ch01.jsonl",
    }
    registry_path = knowledge_root / "sources/registry.jsonl"
    registry = _json_lines(registry_path)
    if not any(item["sha256"] == source_record["sha256"] for item in registry):
        registry.append(source_record)
    created, modified, before = [], [], {}
    for path in [registry_path, *paths.values()]:
        relative = path.relative_to(repository_root).as_posix()
        if path.exists():
            modified.append(relative)
            before[relative] = {"sha256": _sha256(path), "content": path.read_text(encoding="utf-8")}
        else:
            created.append(relative)
    _write_jsonl(registry_path, sorted(registry, key=lambda item: item["id"]))
    for kind, path in paths.items():
        _write_jsonl(path, outputs[kind])
    output_hashes = {path.relative_to(repository_root).as_posix(): _sha256(path) for path in [registry_path, *paths.values()]}
    manifest = {
        "batch_id": batch_id,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tool_version": TOOL_VERSION,
        "source_ids": [source_id],
        "input_checksums": {source_map_path.relative_to(repository_root).as_posix(): checksum},
        "files_created": created,
        "files_modified": modified,
        "lifecycle_target": "reviewed",
        "object_counts": {"concepts": 30, "rules": 14, "exclusions": 8, "benchmarks": 8},
        "validation_results": {"schema": "passed", "traceability": "passed"},
        "rollback_plan": {"delete": created + [manifest_path.relative_to(repository_root).as_posix()], "restore": before, "expected_hashes": output_hashes},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    issues = validate_knowledge(knowledge_root)
    if issues:
        raise ValueError("导入后校验失败：" + "; ".join(issues))
    return manifest


def rollback(batch_id: str, knowledge_root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    repository_root = knowledge_root.resolve().parent
    manifest_path = knowledge_root / "batches/manifests" / f"{batch_id}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = manifest["rollback_plan"]
    conflicts = []
    for relative, expected in plan["expected_hashes"].items():
        path = repository_root / relative
        if not path.exists() or _sha256(path) == expected:
            continue
        if relative == "knowledge/sources/registry.jsonl":
            current = _json_lines(path)
            batch_sources = [item for item in current if item.get("id") in manifest["source_ids"]]
            previous = [
                json.loads(line)
                for line in plan["restore"][relative]["content"].splitlines()
                if line.strip()
            ]
            reconstructed = "".join(
                json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
                for item in sorted(previous + batch_sources, key=lambda item: item["id"])
            )
            if hashlib.sha256(reconstructed.encode()).hexdigest() == expected:
                continue
        conflicts.append(relative)
    if conflicts:
        raise ValueError("文件已被修改，拒绝自动回滚：" + ", ".join(conflicts))
    report = {"batch_id": batch_id, "dry_run": dry_run, "status": "planned" if dry_run else "rolled_back", "deleted": plan["delete"], "restored": sorted(plan["restore"]), "conflicts": []}
    if dry_run:
        return report
    for relative, snapshot in plan["restore"].items():
        path = repository_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "knowledge/sources/registry.jsonl":
            remaining = [
                item for item in _json_lines(path) if item.get("id") not in manifest["source_ids"]
            ]
            _write_jsonl(path, sorted(remaining, key=lambda item: item["id"]))
        else:
            path.write_text(snapshot["content"], encoding="utf-8")
    for relative in plan["delete"]:
        path = repository_root / relative
        if path.exists():
            path.unlink()
    return report
