from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


FIXTURE = Path(__file__).parent / "fixtures" / "ziwei_phase3_rule_manifest_v0.3.json"
ROOT = Path(__file__).resolve().parents[1]
CASE_CODES = ("POS", "NEG", "BND", "BRK", "SUP")
EXPECTED_COUNTS = {
    "MINOR_FIX": 13,
    "MAJOR_REWRITE": 24,
    "QUARANTINE": 3,
    "HEURISTIC_ONLY": 1,
    "DIRECT_PASS": 0,
}
EXPECTED_IDS = [f"ZW-PAT-{number:03d}" for number in range(1, 42)]
QUARANTINE = {"ZW-PAT-028", "ZW-PAT-029", "ZW-PAT-030"}
HEURISTIC = {"ZW-PAT-037"}


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


MANIFEST = json.loads(FIXTURE.read_text(encoding="utf-8"))
COLUMNS = MANIFEST["columns"]
RULES = [dict(zip(COLUMNS, row, strict=True)) for row in MANIFEST["rules"]]
BY_ID = {rule["id"]: rule for rule in RULES}


def positive_facts(rule: dict[str, object]) -> set[str]:
    facts = set(rule["required_all"])
    for alternatives in rule["required_any_groups"]:
        facts.add(alternatives[0])
    return facts


def evaluate(rule: dict[str, object], facts: set[str]) -> dict[str, object]:
    matched = set(rule["required_all"]).issubset(facts)
    if matched:
        matched = all(
            any(alternative in facts for alternative in alternatives)
            for alternatives in rule["required_any_groups"]
        )
    if matched and set(rule["forbidden_any"]).intersection(facts):
        matched = False
    breaking = rule["breaking"] in facts
    return {
        "matched": matched,
        "broken": matched and breaking,
        "output_allowed": False,
        "promotion_allowed": False,
    }


def negative_facts(rule: dict[str, object]) -> set[str]:
    facts = positive_facts(rule)
    if rule["required_all"]:
        facts.remove(rule["required_all"][-1])
    else:
        facts.difference_update(rule["required_any_groups"][0])
    return facts


def boundary_facts(rule: dict[str, object]) -> set[str]:
    facts = positive_facts(rule)
    facts.discard(rule["boundary_drop"])
    facts.add(rule["boundary_add"])
    return facts


def apply_suppression(matched: set[str]) -> set[str]:
    remaining = set(matched)
    for rule_id in sorted(matched):
        if rule_id in remaining:
            remaining.difference_update(BY_ID[rule_id]["suppresses"])
    return remaining


def execute_case(rule: dict[str, object], code: str) -> None:
    if code == "POS":
        result = evaluate(rule, positive_facts(rule))
        assert result == {
            "matched": True,
            "broken": False,
            "output_allowed": False,
            "promotion_allowed": False,
        }
    elif code == "NEG":
        assert evaluate(rule, negative_facts(rule))["matched"] is False
    elif code == "BND":
        facts = boundary_facts(rule)
        assert facts != negative_facts(rule)
        assert evaluate(rule, facts)["matched"] is False
    elif code == "BRK":
        facts = positive_facts(rule) | {rule["breaking"]}
        result = evaluate(rule, facts)
        assert result["matched"] is True
        assert result["broken"] is True
        assert result["output_allowed"] is False
        assert result["promotion_allowed"] is False
    elif code == "SUP":
        matched = {rule["id"], *rule["suppresses"]}
        assert apply_suppression(matched) == {rule["id"]}
    else:
        raise AssertionError(f"unknown case code: {code}")


class ZiweiPhase3ManifestContractTests(unittest.TestCase):
    def test_provenance_is_frozen(self) -> None:
        self.assertEqual(MANIFEST["v"], "ziwei-external-pattern-audit-phase3@0.3")
        self.assertEqual(MANIFEST["base"], "2b4282dc803ed9fb78f2152eadb0bbf673bea54c")
        upstream = MANIFEST["upstream"]
        self.assertEqual(upstream["repo"], "Renhuai123/ziwei-doushu")
        self.assertEqual(upstream["commit"], "88194a404242bfe5c6d5cc512e4117e3e245cdd5")
        self.assertEqual(upstream["blob"], "532f90a65dfeee330bcc9214c2462db6aa0f954e")
        self.assertEqual(
            upstream["phase2_json_sha256"],
            "d1673012cab6ded85b97cbdd8f58ed815d5832c1582ac26dd045e58e23f7d7f0",
        )

    def test_isolation_blocks_import_and_promotion(self) -> None:
        isolation = MANIFEST["isolation"]
        self.assertEqual(isolation["path"], "tests/fixtures")
        self.assertEqual(isolation["runtime"], "blocked")
        self.assertFalse(isolation["formal_knowledge"])
        self.assertEqual(isolation["rag"], "blocked")
        self.assertEqual(isolation["training"], "blocked")
        self.assertEqual(isolation["synthetic"], "regression_only")
        self.assertEqual(isolation["prediction"], "not_evaluated")
        self.assertEqual(MANIFEST["runtime_rules_added"], 0)
        self.assertEqual(MANIFEST["formal_knowledge_records_added"], 0)
        self.assertEqual(MANIFEST["engine_integration_tests_implemented"], 0)
        self.assertEqual(MANIFEST["defaults"]["runtime"], "not_imported")
        self.assertNotEqual(MANIFEST["defaults"]["state"], "verified")

    def test_validation_scope_is_explicitly_limited(self) -> None:
        limits = MANIFEST["limits"]
        self.assertTrue(limits["declarative_fact_contract"])
        self.assertEqual(limits["valid_full_chart_cases"], 0)
        self.assertFalse(limits["production_evaluator_integration"])
        self.assertEqual(limits["doctrine_verified_rules"], 0)
        self.assertEqual(limits["real_case_outcomes"], 0)
        self.assertIn("does not validate divination accuracy", limits["claim"])

    def test_inventory_is_complete_unique_and_counted(self) -> None:
        ids = [rule["id"] for rule in RULES]
        self.assertEqual(ids, EXPECTED_IDS)
        self.assertEqual(len(ids), len(set(ids)))
        counts = {key: 0 for key in EXPECTED_COUNTS}
        for rule in RULES:
            counts[rule["decision"]] += 1
        self.assertEqual(counts, EXPECTED_COUNTS)
        self.assertEqual(MANIFEST["counts"], EXPECTED_COUNTS)

    def test_predicates_are_executable(self) -> None:
        for rule in RULES:
            self.assertTrue(rule["required_all"] or rule["required_any_groups"])
            self.assertTrue(rule["breaking"])
            self.assertTrue(rule["boundary_drop"])
            self.assertTrue(rule["boundary_add"])
            self.assertTrue(all(group for group in rule["required_any_groups"]))

    def test_quarantine_and_heuristic_boundaries_are_exact(self) -> None:
        quarantined = {r["id"] for r in RULES if r["decision"] == "QUARANTINE"}
        heuristic = {r["id"] for r in RULES if r["decision"] == "HEURISTIC_ONLY"}
        self.assertEqual(quarantined, QUARANTINE)
        self.assertEqual(heuristic, HEURISTIC)
        self.assertTrue(all(BY_ID[r]["scope"] == "research_only" for r in QUARANTINE))
        self.assertEqual(BY_ID["ZW-PAT-037"]["kind"], "derived_heuristic")

    def test_case_matrix_declares_205_executable_cases(self) -> None:
        self.assertEqual(tuple(MANIFEST["case_codes"]), CASE_CODES)
        self.assertEqual(MANIFEST["case_count"], 205)
        self.assertEqual(MANIFEST["behavioral_rule_tests_implemented"], 205)
        self.assertEqual(len(RULES) * len(CASE_CODES), 205)

    def test_rules_digest_is_reproducible(self) -> None:
        expected = "sha256:" + hashlib.sha256(canonical(MANIFEST["rules"])).hexdigest()
        self.assertEqual(MANIFEST["rules_sha256"], expected)

    def test_suppression_graph_is_valid_and_acyclic(self) -> None:
        graph = {r["id"]: set(r["suppresses"]) for r in RULES}
        for parent, children in graph.items():
            self.assertNotIn(parent, children)
            self.assertTrue(children.issubset(BY_ID))
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            self.assertNotIn(node, visiting, f"suppression cycle at {node}")
            visiting.add(node)
            for child in graph[node]:
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    def test_fixture_is_not_referenced_by_runtime_files(self) -> None:
        runtime = ROOT / "src" / "mingli"
        if not runtime.exists():
            return
        for path in runtime.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".json", ".toml", ".yaml", ".yml"}:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(FIXTURE.name, text)
            self.assertNotIn(MANIFEST["v"], text)


class ZiweiPhase3DeclarativeCases(unittest.TestCase):
    """Generated test-only cases; no production evaluator or knowledge import."""


def _install_case(rule: dict[str, object], code: str) -> None:
    def test_case(self: unittest.TestCase) -> None:
        with self.subTest(case_id=f"{rule['id']}-{code}-001"):
            execute_case(rule, code)

    name = f"test_{rule['id'].lower().replace('-', '_')}_{code.lower()}"
    test_case.__name__ = name
    test_case.__qualname__ = f"ZiweiPhase3DeclarativeCases.{name}"
    setattr(ZiweiPhase3DeclarativeCases, name, test_case)


for _rule in RULES:
    for _code in CASE_CODES:
        _install_case(_rule, _code)


if __name__ == "__main__":
    unittest.main()
