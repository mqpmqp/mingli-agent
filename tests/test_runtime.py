from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from importlib.metadata import version

import mingli
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mingli.benchmark import benchmark_static
from mingli.chart_provider import UnavailableChartProvider
from mingli.cli import main
from mingli.confidence import evaluate_confidence
from mingli.errors import (
    ChartProviderUnavailable,
    ForbiddenPhraseError,
    ModelValidationError,
    RuleValidationError,
)
from mingli.evidence import fuse_evidence
from mingli.models import ChartInput, Evidence, RealityContext
from mingli.reality import apply_reality_overrides
from mingli.renderer import DISCLAIMER, render_answer
from mingli.router import IntentRouter
from mingli.rule_loader import load_rules
from mingli.schema_loader import validate_spec


def rule(rule_id: str, *, domain: str = "pattern", status: str = "reviewed", priority: int = 50) -> dict:
    return {
        "id": rule_id,
        "domain": domain,
        "trigger": ["signal"],
        "support": [],
        "exclude": [],
        "judgement": "测试判断",
        "plain_language": "测试白话",
        "confidence": "medium",
        "priority": priority,
        "source": "test",
        "status": status,
    }


class SchemaLoaderTests(unittest.TestCase):
    def test_reports_json_and_jsonl_parse_locations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.json").write_text('{"value":', encoding="utf-8")
            (root / "broken.jsonl").write_text('{}\n{"value":\n', encoding="utf-8")

            issues = validate_spec(root)

        rendered = "\n".join(str(issue) for issue in issues)
        self.assertIn("broken.json:1", rendered)
        self.assertIn("broken.jsonl:2", rendered)
        self.assertIn("JSON", rendered)

    def test_validates_schema_and_matching_data_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"type": "integer"}},
                "additionalProperties": False,
            }
            (root / "sample.schema.json").write_text(json.dumps(schema), encoding="utf-8")
            (root / "sample.json").write_text('{"value": "bad"}', encoding="utf-8")

            issues = validate_spec(root)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].path, "$.value")

    def test_rejects_non_object_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.schema.json").write_text("[]", encoding="utf-8")

            issues = validate_spec(root)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].file, "bad.schema.json")
        self.assertEqual(issues[0].path, "$")
        self.assertIn("顶层必须是 object", issues[0].message)


class ModelTests(unittest.TestCase):
    def test_runtime_version_matches_package_metadata(self):
        self.assertEqual(version("mingli-agent"), mingli.__version__)
    def test_models_are_strict_and_frozen(self) -> None:
        chart_input = ChartInput(
            gender="female",
            calendar="solar",
            birth_date="2000-01-02",
            birth_time="03:04",
            birth_location={"country": "中国", "city": "台北"},
        )
        with self.assertRaises(FrozenInstanceError):
            chart_input.gender = "male"  # type: ignore[misc]
        with self.assertRaises(ModelValidationError):
            Evidence(source_type="chart", detail="x", direction="unknown", weight=1)

    def test_reality_context_rejects_unknown_enum(self) -> None:
        with self.assertRaises(ModelValidationError):
            RealityContext(relationship_status="complicated")


class RuleLoaderTests(unittest.TestCase):
    def test_rejects_duplicate_rule_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.jsonl").write_text(json.dumps(rule("duplicate")), encoding="utf-8")
            (root / "b.jsonl").write_text(json.dumps(rule("duplicate")), encoding="utf-8")
            with self.assertRaises(RuleValidationError):
                load_rules(root, statuses={"draft", "reviewed", "verified", "deprecated"})

    def test_filters_status_and_prioritizes_reality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = [
                rule("draft", status="draft", priority=100),
                rule("normal", status="reviewed", priority=100),
                rule("reality", domain="reality", status="verified", priority=1),
            ]
            (root / "rules.jsonl").write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in records),
                encoding="utf-8",
            )

            loaded = load_rules(root)

        self.assertEqual([item.id for item in loaded], ["reality", "normal"])
        self.assertEqual(loaded[0].status, "verified")


class EvidenceAndConfidenceTests(unittest.TestCase):
    def test_verified_reality_is_a_hard_override(self) -> None:
        result = fuse_evidence(
            [
                Evidence("chart", "盘面象意一", "support", 10),
                Evidence("chart", "盘面象意二", "support", 10),
                Evidence("reality", "现实硬事实", "contradict", 0, verified=True),
            ]
        )
        self.assertFalse(result.has_conflict)
        self.assertEqual(result.support_score, 0)
        self.assertGreater(result.contradict_score, 0)
        self.assertEqual(result.hard_override_direction, "contradict")

    def test_confidence_gate_handles_image_conflict_and_reality_facts(self) -> None:
        evidence = [
            Evidence("rule", "规则", "support", 4),
            Evidence("reality", "事实", "support", 8, verified=True),
        ]
        self.assertEqual(evaluate_confidence(evidence, image_unconfirmed=True).level, "low")
        self.assertEqual(evaluate_confidence(evidence).level, "high")
        conflicted = evidence + [Evidence("case", "反例", "contradict", 3)]
        self.assertEqual(evaluate_confidence(conflicted).level, "medium")
        medical = evaluate_confidence(evidence, high_stakes="medical")
        self.assertEqual(medical.scope, "现实处置")


class RealityOverrideTests(unittest.TestCase):
    def codes(self, intent: str, facts: dict, signals: tuple[str, ...] = ()) -> set[str]:
        return {item.code for item in apply_reality_overrides(intent, facts, signals)}

    def test_relationship_and_reunion_boundaries(self) -> None:
        self.assertIn(
            "married_taohua",
            self.codes("relationship", {"relationship_status": "married"}, ("桃花信号",)),
        )
        reunion = self.codes(
            "relationship_reunion",
            {"other_party_status": "married", "contact_status": "blocked", "no_contact_months": 24},
        )
        self.assertTrue({"other_party_married", "blocked", "long_no_contact"}.issubset(reunion))

    def assert_reality_contract(
        self,
        intent: str,
        facts: dict,
        signals: tuple[str, ...],
        override_code: str,
        chart_claim: str,
    ) -> None:
        self.assertIn(override_code, self.codes(intent, facts, signals))
        result = fuse_evidence(
            [
                Evidence("chart", chart_claim, "support", 10),
                Evidence("rule", chart_claim, "support", 10),
                Evidence("reality", override_code, "contradict", 0, verified=True),
            ]
        )
        self.assertEqual(result.hard_override_direction, "contradict")
        self.assertEqual(result.support_score, 0)
        self.assertGreater(result.contradict_score, 0)

    def test_reality_hard_override_contracts(self) -> None:
        self.assert_reality_contract(
            "relationship",
            {"relationship_status": "married"},
            ("桃花信号",),
            "married_taohua",
            "桃花等于出轨",
        )
        self.assert_reality_contract(
            "career",
            {"career_status": "unemployed"},
            (),
            "unemployed",
            "事业象意等于升职",
        )
        self.assert_reality_contract(
            "health",
            {"symptoms": ["持续胸痛"]},
            ("五行象意",),
            "urgent_medical",
            "五行象意替代医疗评估",
        )
        self.assert_reality_contract(
            "investment",
            {"contract_leverage": True},
            ("偏财信号",),
            "leverage_risk",
            "偏财象意决定杠杆重仓",
        )

    def test_career_exam_startup_health_and_investment_boundaries(self) -> None:
        self.assertIn("unemployed", self.codes("career", {"career_status": "unemployed"}))
        self.assertIn("major_ineligible", self.codes("career_exam", {"major_eligible": False}))
        self.assertIn(
            "low_cost_validation",
            self.codes("startup", {"capital_level": "low", "customer_validation": False}),
        )
        self.assertIn("urgent_medical", self.codes("health", {"symptoms": ["持续胸痛"]}))
        self.assertIn("leverage_risk", self.codes("investment", {"contract_leverage": True}))


class RouterRendererAndProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.router = IntentRouter.from_file(ROOT / "spec" / "routing" / "intent_router.yaml")

    def test_router_returns_required_fields_sections_and_capabilities(self) -> None:
        route = self.router.route("career_exam")
        self.assertIn("major", route.required_fields)
        self.assertEqual(route.sections, ("体制适配度", "能否上岸", "岗位方向", "备考策略"))
        self.assertIn("decision", route.capabilities)

    def test_unconfirmed_image_only_requests_confirmation_at_low_confidence(self) -> None:
        rendered = render_answer(
            intent="full_bazi",
            conclusion="这段内容不应出现",
            chart_confirmed=False,
        )
        self.assertIn("请确认", rendered)
        self.assertIn("低置信", rendered)
        self.assertNotIn("这段内容不应出现", rendered)
        self.assertEqual(rendered.count(DISCLAIMER), 1)

    def test_exam_and_reunion_have_all_required_sections(self) -> None:
        exam = render_answer(intent="career_exam", conclusion="先看现实条件。")
        for section in ("体制适配度", "能否上岸", "岗位方向", "备考策略"):
            self.assertIn(section, exam)
        reunion = render_answer(intent="relationship_reunion", conclusion="现实边界优先。")
        for section in ("缘分牵引", "复联可能", "复合可能", "稳定可能"):
            self.assertIn(section, reunion)

    def test_renderer_limits_advice_explains_terms_and_has_one_disclaimer(self) -> None:
        rendered = render_answer(
            intent="wealth",
            conclusion="先稳住现金流。",
            terminology=(("财星", f"资源与现金流象意{DISCLAIMER}"),),
            advice=("一", "二", "三", "四"),
        )
        self.assertTrue(rendered.startswith("先稳住现金流。"))
        self.assertIn("财星（资源与现金流象意）", rendered)
        self.assertNotIn("4. 四", rendered)
        self.assertEqual(rendered.count(DISCLAIMER), 1)
        self.assertTrue(rendered.endswith(DISCLAIMER))

    def test_renderer_blocks_forbidden_phrases(self) -> None:
        with self.assertRaises(ForbiddenPhraseError):
            render_answer(intent="wealth", conclusion="你注定发财。")

    def test_chart_provider_explicitly_refuses_fabricated_chart(self) -> None:
        provider = UnavailableChartProvider()
        with self.assertRaises(ChartProviderUnavailable) as raised:
            provider.calculate({})
        self.assertIn("未配置可靠排盘器", str(raised.exception))
        self.assertIn("不可生成四柱或旺衰", str(raised.exception))


class BenchmarkAndCliTests(unittest.TestCase):
    def test_all_40_golden_and_24_practical_cases_pass_static_checks(self) -> None:
        result = benchmark_static(ROOT / "spec" / "evaluation" / "golden_cases_v0.2.jsonl")
        self.assertEqual(result.total, 40)
        self.assertEqual(result.passed, 40)
        self.assertEqual(result.practical_total, 24)
        self.assertEqual(result.failures, ())

    def test_cli_returns_nonzero_and_clear_message_for_bad_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.json").write_text("{", encoding="utf-8")
            output = io.StringIO()
            errors = io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                exit_code = main(["validate-spec", str(root)])
        self.assertNotEqual(exit_code, 0)
        self.assertIn("bad.json:1", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
