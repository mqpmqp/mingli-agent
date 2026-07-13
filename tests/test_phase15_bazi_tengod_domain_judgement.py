from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mingli.derived.static_engine import BRANCHES, STEMS, TEN_GOD_LABELS
from mingli.phase8_contracts import EvidenceRecord as Phase8EvidenceRecord
from mingli.phase15 import (
    PHASE15_METHOD_ID,
    PHASE15_SCHEMA_VERSION,
    Phase15InputError,
    benchmark_phase15,
    build_phase15_fixture,
    domain_result_to_phase8_evidence,
    evaluate_bazi_tengod_domains,
    load_phase15_domain_profiles,
    query_domain_judgements,
    validate_phase15_profiles,
)
from mingli.phase15_contracts import CONFLICT_STATUSES, DOMAINS, DOMAIN_LABELS, TARGET_TYPES

ROOT = Path(__file__).resolve().parents[1]


def fixture(day_stem: str = STEMS[0], month_branch: str = BRANCHES[2]):
    return build_phase15_fixture(day_stem, month_branch)


class Phase15EvaluationTests(unittest.TestCase):
    def test_profile_and_large_assertion_matrix_pass(self) -> None:
        self.assertTrue(load_phase15_domain_profiles()["profiles"])
        self.assertEqual((), validate_phase15_profiles())
        result = benchmark_phase15()
        self.assertGreaterEqual(result.assertions_total, 7200)
        self.assertEqual(result.assertions_total, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.unresolved)
        self.assertEqual(0, result.schema_failures)
        self.assertEqual(0, result.provenance_failures)
        self.assertEqual(0, result.hash_mismatches)
        self.assertEqual(0, result.ten_god_mapping_failures)
        self.assertEqual(0, result.domain_partition_failures)
        self.assertEqual(0, result.query_failures)
        self.assertEqual(0, result.reality_override_failures)
        self.assertEqual(0, result.claim_boundary_failures)
        self.assertEqual(0, result.prediction_boundary_failures)

    def test_evaluation_is_deterministic_and_candidate_only(self) -> None:
        graph, interaction, trend = fixture()
        result = evaluate_bazi_tengod_domains(graph, interaction, trend)
        reordered = evaluate_bazi_tengod_domains(
            json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True)),
            json.loads(json.dumps(interaction, ensure_ascii=False, sort_keys=True)),
            json.loads(json.dumps(trend, ensure_ascii=False, sort_keys=True)),
        )
        payload = result.to_dict()
        self.assertEqual(result.canonical_hash, reordered.canonical_hash)
        self.assertEqual(PHASE15_SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(PHASE15_METHOD_ID, payload["method_id"])
        self.assertEqual("not_evaluated", payload["prediction_validity"])
        self.assertEqual("candidate_only", payload["domain_judgement_validity"])
        self.assertTrue(result.dynamic_hits)
        self.assertTrue(all(item.ten_god_code in TEN_GOD_LABELS for item in result.dynamic_hits))
        self.assertTrue(all(item.target_type in TARGET_TYPES for item in result.dynamic_hits))
        target_ids = {item.target_id for item in result.dynamic_hits}
        self.assertEqual(len(target_ids) * len(DOMAINS), len(result.domain_judgements))
        self.assertTrue(all(item.domain in DOMAINS for item in result.domain_judgements))
        self.assertTrue(all(item.judgement_label in DOMAIN_LABELS for item in result.domain_judgements))
        self.assertTrue(all(item.confidence != "high" for item in result.domain_judgements))
        self.assertTrue(all("domain_tendency_candidate_only" in item.claim_boundary_codes for item in result.domain_judgements))
        self.assertTrue({"event_prediction", "promotion_prediction", "profit_prediction"}.isdisjoint(payload))

    def test_natal_context_and_cross_domain_conflicts_are_complete(self) -> None:
        result = evaluate_bazi_tengod_domains(*fixture())
        self.assertEqual(set(TEN_GOD_LABELS), set(result.natal_context.total_scores))
        self.assertEqual(set(DOMAINS), set(result.natal_context.domain_activation_scores))
        self.assertEqual(set(DOMAINS), set(result.domain_index))
        target_ids = {item.target_id for item in result.domain_judgements}
        self.assertEqual(target_ids, {item.target_id for item in result.cross_domain_conflicts})
        self.assertTrue(all(item.status in CONFLICT_STATUSES for item in result.cross_domain_conflicts))

    def test_reality_hard_override_is_domain_scoped(self) -> None:
        graph, interaction, trend = fixture()
        baseline = evaluate_bazi_tengod_domains(graph, interaction, trend)
        target = baseline.domain_judgements[0].target_id
        domain = baseline.domain_judgements[0].domain
        support = {
            "target_id": target,
            "domain": domain,
            "direction": "support",
            "detail": "verified domain condition",
            "weight": 10,
            "verified": True,
            "source_id": "phase15-test-support",
        }
        overridden = evaluate_bazi_tengod_domains(graph, interaction, trend, reality_evidence=(support,))
        item = next(record for record in overridden.domain_judgements if record.target_id == target and record.domain == domain)
        self.assertEqual("support_tendency", item.judgement_label)
        self.assertEqual("high", item.confidence)
        self.assertEqual("support", item.reality_override_direction)
        other_domains = [record for record in overridden.domain_judgements if record.target_id == target and record.domain != domain]
        self.assertTrue(all(record.reality_override_direction is None for record in other_domains))
        conflicted = evaluate_bazi_tengod_domains(graph, interaction, trend, reality_evidence=(
            support,
            {
                "target_id": target,
                "domain": domain,
                "direction": "contradict",
                "detail": "verified contradictory domain condition",
                "weight": 10,
                "verified": True,
                "source_id": "phase15-test-conflict",
            },
        ))
        conflict_item = next(record for record in conflicted.domain_judgements if record.target_id == target and record.domain == domain)
        self.assertEqual("unresolved", conflict_item.judgement_label)
        self.assertEqual("low", conflict_item.confidence)

    def test_year_age_target_and_domain_queries(self) -> None:
        result = evaluate_bazi_tengod_domains(*fixture())
        year_item = next(item for item in result.domain_judgements if item.label_year is not None)
        age_item = next(item for item in result.domain_judgements if item.start_age is not None)
        self.assertTrue(query_domain_judgements(result, year=year_item.label_year, domain=year_item.domain))
        self.assertTrue(query_domain_judgements(result, age=age_item.start_age, domain=age_item.domain))
        target_matches = query_domain_judgements(result, target_id=year_item.target_id)
        self.assertEqual(set(DOMAINS), {str(item["domain"]) for item in target_matches})
        with self.assertRaisesRegex(Phase15InputError, "exactly one"):
            query_domain_judgements(result)
        with self.assertRaisesRegex(Phase15InputError, "exactly one"):
            query_domain_judgements(result, year=year_item.label_year, age=age_item.start_age)
        with self.assertRaisesRegex(Phase15InputError, "unsupported domain"):
            query_domain_judgements(result, target_id=year_item.target_id, domain="health")

    def test_evidence_converts_to_phase8_records(self) -> None:
        records = domain_result_to_phase8_evidence(evaluate_bazi_tengod_domains(*fixture()))
        self.assertTrue(records)
        self.assertTrue(all(isinstance(item, Phase8EvidenceRecord) for item in records))
        self.assertTrue(all(item.canonical_digest.startswith("sha256:") for item in records))

    def test_invalid_inputs_and_event_requests_are_blocked(self) -> None:
        graph, interaction, trend = fixture()
        with self.assertRaisesRegex(Phase15InputError, "Fact Graph is required"):
            evaluate_bazi_tengod_domains({}, interaction, trend)
        with self.assertRaisesRegex(Phase15InputError, "Interaction Result is required"):
            evaluate_bazi_tengod_domains(graph, {}, trend)
        with self.assertRaisesRegex(Phase15InputError, "Temporal Trend Result is required"):
            evaluate_bazi_tengod_domains(graph, interaction, {})
        with self.assertRaisesRegex(Phase15InputError, "canonical_hash mismatch"):
            evaluate_bazi_tengod_domains({**graph, "canonical_hash": "sha256:bad"}, interaction, trend)
        with self.assertRaisesRegex(Phase15InputError, "unknown"):
            evaluate_bazi_tengod_domains(graph, interaction, trend, reality_evidence=({
                "target_id": "unknown-target",
                "domain": "career",
                "direction": "support",
                "detail": "invalid",
                "weight": 1,
                "verified": True,
                "source_id": "invalid",
            },))
        with self.assertRaisesRegex(Phase15InputError, "cannot return"):
            evaluate_bazi_tengod_domains(graph, interaction, trend, requested_outputs=("promotion_prediction",))


class Phase15CliTests(unittest.TestCase):
    def test_cli_surface_outputs_json(self) -> None:
        graph, interaction, trend = fixture()
        result = evaluate_bazi_tengod_domains(graph, interaction, trend)
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}
        }
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory() as directory:
            graph_path = Path(directory) / "graph.json"
            interaction_path = Path(directory) / "interaction.json"
            trend_path = Path(directory) / "trend.json"
            result_path = Path(directory) / "result.json"
            graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
            interaction_path.write_text(json.dumps(interaction, ensure_ascii=False), encoding="utf-8")
            trend_path.write_text(json.dumps(trend, ensure_ascii=False), encoding="utf-8")
            result_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False), encoding="utf-8")
            year_item = next(item for item in result.domain_judgements if item.label_year is not None)
            commands = (
                ("evaluate", "--graph", str(graph_path), "--interaction", str(interaction_path), "--trend", str(trend_path)),
                ("query", "--result", str(result_path), "--year", str(year_item.label_year), "--domain", year_item.domain),
                ("validate",),
                ("profiles",),
                ("schemas",),
                ("provenance", "--expected-root", str(ROOT)),
            )
            for command in commands:
                completed = subprocess.run(
                    [sys.executable, "-m", "mingli.phase15_cli", *command],
                    cwd=ROOT,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertTrue(json.loads(completed.stdout))


if __name__ == "__main__":
    unittest.main()
