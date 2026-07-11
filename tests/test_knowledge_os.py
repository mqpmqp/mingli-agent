from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from mingli.errors import RuleValidationError
from mingli.knowledge import (
    import_pilot,
    inventory,
    planner_extensions,
    register_source,
    render_gitattributes,
    rollback,
    stable_source_id,
    validate_knowledge,
)
from mingli.rule_loader import load_rules


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "spec/knowledge/pilots/zhouyi_yu_yucexue_ch01"


def copy_fixture(directory: str) -> tuple[Path, Path]:
    repo = Path(directory) / "repo"
    shutil.copytree(ROOT / "knowledge", repo / "knowledge")
    shutil.copytree(PILOT, repo / "spec/knowledge/pilots/zhouyi_yu_yucexue_ch01")
    registry = repo / "spec/knowledge/sources/source_registry.jsonl"
    registry.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "spec/knowledge/sources/source_registry.jsonl", registry)
    shutil.copy2(ROOT / ".gitattributes", repo / ".gitattributes")
    knowledge = repo / "knowledge"
    manifest = next((knowledge / "batches/manifests").glob("*.json"))
    rollback(manifest.stem, knowledge)
    return repo, knowledge


class SourceRegistryTests(unittest.TestCase):
    def test_source_id_is_stable_across_repository_paths(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            ids = []
            for directory in (first, second):
                root = Path(directory)
                source = root / "sources/book.txt"
                source.parent.mkdir()
                source.write_text("same bytes", encoding="utf-8")
                record = register_source(source, root / "registry.jsonl", domain="yijing", repository_root=root)
                ids.append(record["id"])
            self.assertEqual(ids[0], ids[1])

    def test_registry_has_relative_path_and_detects_duplicate_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "a.txt"
            second = root / "nested/b.txt"
            second.parent.mkdir()
            first.write_text("duplicate", encoding="utf-8")
            second.write_text("duplicate", encoding="utf-8")
            registry = root / "registry.jsonl"
            one = register_source(first, registry, domain="yijing", repository_root=root)
            two = register_source(second, registry, domain="yijing", repository_root=root)
            self.assertEqual(one, two)
            text = registry.read_text(encoding="utf-8")
            self.assertNotIn(str(root), text)
            self.assertEqual(len(text.splitlines()), 1)

    def test_symlinks_are_rejected_including_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            inside = root / "inside.txt"
            inside.write_text("inside", encoding="utf-8")
            link = root / "inside-link"
            try:
                link.symlink_to(inside)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 1314:
                    self.skipTest("Windows symlink privilege is unavailable")
                raise
            with self.assertRaisesRegex(ValueError, "symlink 默认"):
                register_source(link, root / "registry.jsonl", domain="yijing", repository_root=root)
            external = Path(outside) / "outside.txt"
            external.write_text("outside", encoding="utf-8")
            outside_link = root / "outside-link"
            outside_link.symlink_to(external)
            with self.assertRaisesRegex(ValueError, "仓库外"):
                register_source(outside_link, root / "registry.jsonl", domain="yijing", repository_root=root)


class PolicyAndLifecycleTests(unittest.TestCase):
    def test_lfs_and_planner_share_policy(self) -> None:
        self.assertEqual((ROOT / ".gitattributes").read_text(encoding="utf-8"), render_gitattributes(ROOT / "knowledge"))
        self.assertIn(".pdf", planner_extensions(ROOT / "knowledge"))

    def test_invalid_lifecycle_and_source_only_verified_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / "knowledge", repo / "knowledge")
            shutil.copy2(ROOT / ".gitattributes", repo / ".gitattributes")
            source = ROOT / "knowledge/rules/reviewed/yijing/zhouyi_yu_yucexue_ch01.jsonl"
            invalid = repo / "knowledge/rules/invalid/yijing/rules.jsonl"
            invalid.parent.mkdir(parents=True)
            shutil.copy2(source, invalid)
            verified = repo / "knowledge/rules/verified/yijing/rules.jsonl"
            verified.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, verified)
            issues = "\n".join(validate_knowledge(repo / "knowledge"))
            self.assertIn("非法生命周期", issues)
            self.assertIn("source_only 规则不得进入 verified", issues)

    def test_production_loader_excludes_disallowed_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.jsonl"
            path.write_text(json.dumps({"id":"blocked","domain":"pattern","trigger":["x"],"support":[],"exclude":[],"judgement":"x","plain_language":"x","confidence":"low","priority":1,"source":"x","status":"reviewed","production_allowed":False}) + "\n", encoding="utf-8")
            self.assertEqual(load_rules(Path(directory)), ())


class BatchTests(unittest.TestCase):
    def test_pilot_counts_traceability_manifest_reproducibility_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, knowledge = copy_fixture(directory)
            pilot = repo / "spec/knowledge/pilots/zhouyi_yu_yucexue_ch01"
            manifest = import_pilot(pilot, knowledge)
            self.assertEqual(manifest["object_counts"], {"concepts":30,"rules":14,"exclusions":8,"benchmarks":8})
            required = {"batch_id","created_at","tool_version","source_ids","input_checksums","files_created","files_modified","lifecycle_target","object_counts","validation_results","rollback_plan"}
            self.assertTrue(required.issubset(manifest))
            pilot_concepts = knowledge / "concepts/reviewed/yijing/zhouyi_yu_yucexue_ch01.jsonl"
            self.assertEqual(len(pilot_concepts.read_text(encoding="utf-8").splitlines()), 30)
            for kind in ("concepts", "rules", "evidence", "benchmarks"):
                for path in (knowledge / kind).rglob("*.jsonl"):
                    for record in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line):
                        self.assertTrue(record.get("source_id") or record.get("source_ids"))
                        self.assertTrue(record["source_pages"])
            repeated = import_pilot(pilot, knowledge)
            self.assertEqual(manifest, repeated)
            dry_run = rollback(manifest["batch_id"], knowledge, dry_run=True)
            self.assertEqual(dry_run["status"], "planned")
            rollback(manifest["batch_id"], knowledge)
            self.assertFalse(pilot_concepts.exists())

    def test_rollback_preserves_sources_added_by_later_batches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            shutil.copytree(ROOT / "knowledge", repo / "knowledge")
            knowledge = repo / "knowledge"
            manifest = next((knowledge / "batches/manifests").glob("*.json"))

            rollback(manifest.stem, knowledge)

            remaining = {
                item["id"]
                for item in (
                    json.loads(line)
                    for line in (knowledge / "sources/registry.jsonl").read_text(encoding="utf-8").splitlines()
                )
            }
            self.assertEqual(
                remaining,
                {"src_sha256_1d4a97526c60", "src_sha256_c7ac90538958", "src_sha256_e3fa415da369"},
            )

    def test_modified_file_refuses_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, knowledge = copy_fixture(directory)
            manifest = import_pilot(repo / "spec/knowledge/pilots/zhouyi_yu_yucexue_ch01", knowledge)
            path = knowledge / "concepts/reviewed/yijing/zhouyi_yu_yucexue_ch01.jsonl"
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "文件已被修改"):
                rollback(manifest["batch_id"], knowledge)


if __name__ == "__main__":
    unittest.main()
