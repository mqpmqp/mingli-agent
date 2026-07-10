from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

from scripts.inventory_knowledge_assets import (
    build_inventory,
    display_path,
    write_inventory_reports,
)
from scripts.plan_knowledge_import import (
    SPLIT_THRESHOLD_BYTES,
    create_import_plan,
    write_plan_reports,
)


class KnowledgeInventoryTests(unittest.TestCase):
    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            inventory = build_inventory([Path(directory)])

        self.assertEqual(inventory["file_count"], 0)
        self.assertEqual(inventory["total_bytes"], 0)
        self.assertIsNone(inventory["largest_file"])
        self.assertEqual(inventory["duplicate_candidates"], [])
        self.assertEqual(inventory["errors"], [])

    def test_mixed_text_and_pdf_are_grouped_by_lowercase_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.md").write_text("资料", encoding="utf-8")
            (root / "scan.PDF").write_bytes(b"%PDF-test")

            inventory = build_inventory([root])

        self.assertEqual(inventory["file_count"], 2)
        self.assertEqual(inventory["extensions"][".md"]["count"], 1)
        self.assertEqual(inventory["extensions"][".pdf"]["count"], 1)
        self.assertEqual(inventory["largest_file"]["extension"], ".pdf")

    def test_duplicate_files_are_reported_by_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.txt").write_bytes(b"same-content")
            (root / "second.txt").write_bytes(b"same-content")

            inventory = build_inventory([root])

        self.assertEqual(len(inventory["duplicate_candidates"]), 1)
        duplicate = inventory["duplicate_candidates"][0]
        self.assertEqual(duplicate["size_bytes"], len(b"same-content"))
        self.assertEqual(len(duplicate["files"]), 2)
        self.assertEqual(len(duplicate["sha256"]), 64)

    def test_unreadable_file_is_reported_without_aborting_other_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readable = root / "readable.txt"
            unreadable = root / "unreadable.pdf"
            readable.write_text("ok", encoding="utf-8")
            unreadable.write_bytes(b"blocked")

            def fake_hash(path: Path) -> str:
                if path == unreadable.resolve():
                    raise PermissionError("permission denied")
                return "a" * 64

            with patch("scripts.inventory_knowledge_assets.hash_file", side_effect=fake_hash):
                inventory = build_inventory([root])

        self.assertEqual(inventory["file_count"], 2)
        self.assertEqual(len(inventory["errors"]), 1)
        self.assertIn("unreadable.pdf", inventory["errors"][0]["path"])
        self.assertIn("permission denied", inventory["errors"][0]["error"])

    def test_windows_path_format_is_preserved(self) -> None:
        windows_path = PureWindowsPath("D:/命理资料/books/source.pdf")
        self.assertEqual(display_path(windows_path), r"D:\命理资料\books\source.pdf")

    def test_reports_do_not_overwrite_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = build_inventory([root])
            json_output = root / "reports" / "inventory.json"
            markdown_output = root / "reports" / "inventory.md"

            write_inventory_reports(inventory, json_output, markdown_output)

            self.assertEqual(json.loads(json_output.read_text(encoding="utf-8"))["file_count"], 0)
            self.assertIn("资料清单", markdown_output.read_text(encoding="utf-8"))
            with self.assertRaises(FileExistsError):
                write_inventory_reports(inventory, json_output, root / "other.md")


class KnowledgeImportPlanTests(unittest.TestCase):
    def inventory(self, total_bytes: int, files: list[dict] | None = None) -> dict:
        return {
            "schema_version": 1,
            "roots": [r"D:\资料"],
            "file_count": len(files or []),
            "total_bytes": total_bytes,
            "extensions": {},
            "files": files or [],
            "largest_file": None,
            "files_over_50_mb": [],
            "files_over_100_mb": [],
            "duplicate_candidates": [],
            "errors": [],
        }

    def test_500_mb_threshold_selects_split_repo(self) -> None:
        single = create_import_plan(self.inventory(SPLIT_THRESHOLD_BYTES - 1))
        split = create_import_plan(self.inventory(SPLIT_THRESHOLD_BYTES))

        self.assertEqual(single["decision"], "single_repo")
        self.assertEqual(split["decision"], "split_repo")
        self.assertEqual(split["recommended_repository"], "mqpmqp/mingli-knowledge")

    def test_plan_only_does_not_copy_or_move_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            source.write_bytes(b"pdf")
            inventory = self.inventory(
                3,
                [{"path": str(source), "size_bytes": 3, "extension": ".pdf", "sha256": "b" * 64}],
            )

            plan = create_import_plan(inventory)
            json_output = root / "plan.json"
            markdown_output = root / "plan.md"
            write_plan_reports(plan, json_output, markdown_output)

            self.assertTrue(source.exists())
            self.assertFalse((root / "references").exists())
            self.assertTrue(all(item["action"] == "plan_only" for item in plan["files"]))
            self.assertIn("不执行复制或移动", markdown_output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
