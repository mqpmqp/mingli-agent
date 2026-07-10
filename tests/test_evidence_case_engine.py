from __future__ import annotations

import json
from pathlib import Path

import pytest

from mingli.evidence_conflict import resolve_evidence
from mingli.knowledge import validate_knowledge


ROOT = Path(__file__).resolve().parents[1]


def record(identifier: str, priority: str, polarity: str, claim: str = "claim") -> dict:
    return {"id": identifier, "priority_class": priority, "polarity": polarity, "claim": claim}


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_reality_fact_overrides_all_lower_evidence() -> None:
    result = resolve_evidence(
        [
            record("traditional", "single_traditional_claim", "support"),
            record("cases", "multi_case_observation", "support"),
            record("event", "user_confirmed_event", "support"),
            record("reality", "reality_fact", "contradict"),
        ]
    )
    assert result.status == "resolved"
    assert result.priority_class == "reality_fact"
    assert result.accepted_ids == ("reality",)
    assert result.overridden_ids == ("cases", "event", "traditional")


def test_priority_order_between_non_reality_evidence() -> None:
    result = resolve_evidence(
        [
            record("traditional", "single_traditional_claim", "support"),
            record("cases", "multi_case_observation", "support"),
            record("event", "user_confirmed_event", "contradict"),
        ]
    )
    assert result.accepted_ids == ("event",)
    assert result.priority_class == "user_confirmed_event"


def test_same_priority_conflict_remains_unresolved() -> None:
    result = resolve_evidence(
        [
            record("fact_a", "reality_fact", "support"),
            record("fact_b", "reality_fact", "contradict"),
        ]
    )
    assert result.status == "unresolved"
    assert result.accepted_ids == ()
    assert result.conflict_ids == ("fact_a", "fact_b")


@pytest.mark.parametrize(
    "records",
    [[], [record("a", "unknown", "support")], [record("a", "reality_fact", "unknown")], [record("a", "reality_fact", "support", "a"), record("b", "reality_fact", "support", "b")]],
)
def test_rejects_invalid_resolution_inputs(records: list[dict]) -> None:
    with pytest.raises(ValueError):
        resolve_evidence(records)


def test_case_assets_are_synthetic_reviewed_and_traceable() -> None:
    cases = jsonl(ROOT / "knowledge/cases/reviewed/bazi/synthetic_boundaries_v0.1.jsonl")
    assert len(cases) == 6
    assert all(item["case_type"] == "synthetic_boundary_case" for item in cases)
    assert all(item["verification_level"] == "synthetic" for item in cases)
    assert all(item["lifecycle"] == "reviewed" and item["source_id"] for item in cases)
    assert all(item["event_timeline"] for item in cases)


def test_evidence_types_and_case_benchmark_count() -> None:
    evidence = jsonl(ROOT / "knowledge/evidence/reviewed/bazi/case_engine_v0.1.jsonl")
    benchmarks = jsonl(ROOT / "knowledge/benchmarks/draft/bazi/evidence_case_boundaries_v0.1.jsonl")
    assert {item["evidence_type"] for item in evidence} == {
        "traditional_source", "expert_rule", "reality_fact", "case_observation"
    }
    assert len(benchmarks) == 30
    assert all(item["lifecycle"] == "draft" and item["case_id"] and item["evidence_ids"] for item in benchmarks)


def test_knowledge_validation_includes_cases() -> None:
    assert validate_knowledge(ROOT / "knowledge") == ()
