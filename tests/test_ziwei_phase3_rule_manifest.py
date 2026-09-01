from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ziwei_phase3_rule_manifest_v0.1.json"
ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = [f"ZW-PAT-{n:03d}" for n in range(1, 42)]
EXPECTED_COUNTS = {
    "MINOR_FIX": 13,
    "MAJOR_REWRITE": 24,
    "QUARANTINE": 3,
    "HEURISTIC_ONLY": 1,
    "DIRECT_PASS": 0,
}
QUARANTINE = {"ZW-PAT-028", "ZW-PAT-029", "ZW-PAT-030"}
HEURISTIC = {"ZW-PAT-037"}
EDGES = {
    ("ZW-PAT-001", "ZW-PAT-017"),
    ("ZW-PAT-001", "ZW-PAT-039"),
    ("ZW-PAT-025", "ZW-PAT-024"),
}
CASE_CODES = {"POS", "NEG", "BND", "BRK", "SUP"}
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


class ZiweiPhase3ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.rules = cls.manifest["rules"]
        cls.by_id = {item["id"]: item for item in cls.rules}

    def test_provenance_is_frozen(self) -> None:
        self.assertEqual(
            self.manifest["manifest_version"],
            "ziwei-external-pattern-audit-phase3@0.1",
        )
        self.assertEqual(
            self.manifest["base_commit"],
            "2b4282dc803ed9fb78f2152eadb0bbf673bea54c",
        )
        source = self.manifest["source"]
        self.assertEqual(source["repo"], "Renhuai123/ziwei-doushu")
        self.assertEqual(
            source["commit"], "88194a404242bfe5c6d5cc512e4117e3e245cdd5"
        )
        self.assertEqual(
            source["patterns_blob"],
            "532f90a65dfeee330bcc9214c2462db6aa0f954e",
        )
        self.assertEqual(
            source["phase2_json_sha256"],
            "d1673012cab6ded85b97cbdd8f58ed815d5832c1582ac26dd045e58e23f7d7f0",
        )

    def test_isolation_blocks_all_import_paths(self) -> None:
        isolation = self.manifest["isolation"]
        self.assertEqual(isolation["path"], "tests/fixtures")
        self.assertEqual(isolation["runtime"], "blocked")
        self.assertFalse(isolation["formal_knowledge"])
        self.assertEqual(isolation["rag"], "blocked")
        self.assertEqual(isolation["training"], "blocked")
        self.assertEqual(isolation["synthetic"], "regression_only")
        self.assertEqual(isolation["prediction"], "not_evaluated")
        self.assertEqual(self.manifest["runtime_rules_added"], 0)
        self.assertEqual(self.manifest["formal_knowledge_records_added"], 0)
        self.assertEqual(self.manifest["behavioral_rule_tests_implemented"], 0)

    def test_inventory_is_complete_unique_and_counted(self) -> None:
        ids = [item["id"] for item in self.rules]
        self.assertEqual(ids, EXPECTED_IDS)
        self.assertEqual(len(ids), len(set(ids)))
        counts = {key: 0 for key in EXPECTED_COUNTS}
        for item in self.rules:
            counts[item["decision"]] += 1
        self.assertEqual(counts, EXPECTED_COUNTS)

    def test_every_rule_is_non_runtime_and_non_verified(self) -> None:
        for item in self.rules:
            self.assertEqual(item["runtime"], "not_imported")
            self.assertNotEqual(item["state"], "verified")
            self.assertIn(item["output"], {"blocked", "blocked_pending_validation"})
            self.assertRegex(item["record_sha256"], SHA256)

    def test_quarantine_and_heuristic_boundaries_are_exact(self) -> None:
        quarantined = {
            item["id"] for item in self.rules if item["state"] == "quarantined"
        }
        heuristic = {
            item["id"] for item in self.rules if item["kind"] == "heuristic"
        }
        self.assertEqual(quarantined, QUARANTINE)
        self.assertEqual(heuristic, HEURISTIC)
        for rule_id in QUARANTINE:
            item = self.by_id[rule_id]
            self.assertEqual(item["decision"], "QUARANTINE")
            self.assertEqual(item["output"], "blocked")
        heuristic_item = self.by_id["ZW-PAT-037"]
        self.assertEqual(heuristic_item["decision"], "HEURISTIC_ONLY")
        self.assertEqual(heuristic_item["source"], "low")
        self.assertEqual(heuristic_item["state"], "draft")

    def test_five_case_classes_expand_to_205_planned_cases(self) -> None:
        self.assertEqual(set(self.manifest["case_classes"]), CASE_CODES)
        generated = {
            f"{item['id']}-{code}-001"
            for item in self.rules
            for code in CASE_CODES
        }
        self.assertEqual(len(generated), 205)
        self.assertEqual(
            self.manifest["case_id_pattern"],
            "{rule_id}-{POS|NEG|BND|BRK|SUP}-001",
        )

    def test_rules_digest_is_reproducible(self) -> None:
        expected = "sha256:" + hashlib.sha256(canonical(self.rules)).hexdigest()
        self.assertEqual(self.manifest["rules_sha256"], expected)

    def test_suppression_edges_are_valid(self) -> None:
        edges = {tuple(edge) for edge in self.manifest["suppression_edges"]}
        self.assertEqual(edges, EDGES)
        for parent, child in edges:
            self.assertIn(parent, self.by_id)
            self.assertIn(child, self.by_id)
            self.assertNotEqual(parent, child)

    def test_fixture_is_not_referenced_by_runtime_files(self) -> None:
        self.assertEqual(FIXTURE.parent.name, "fixtures")
        self.assertEqual(FIXTURE.parent.parent.name, "tests")
        runtime = ROOT / "src" / "mingli"
        if not runtime.exists():
            return
        forbidden = {
            FIXTURE.name,
            self.manifest["manifest_version"],
            self.manifest["source"]["repo"],
        }
        for path in runtime.rglob("*"):
            if not path.is_file() or path.suffix not in {
                ".py", ".json", ".toml", ".yaml", ".yml"
            }:
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{token!r} leaked into {path}")


if __name__ == "__main__":
    unittest.main()
