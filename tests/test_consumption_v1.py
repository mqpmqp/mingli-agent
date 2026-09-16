from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from mingli.consumption_v1 import ConsumptionV1
from mingli.training import TrainingError, TrainingStore


NOW = "2026-09-16T08:30:00+00:00"
REVIEWER = "reviewer:" + "a" * 64


def _manager() -> tuple[tempfile.TemporaryDirectory[str], ConsumptionV1, Path]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    repo = root / "repo"
    repo.mkdir()
    store = TrainingStore(root / "training", repository_root=repo)
    return temp, ConsumptionV1(store), store.root


def _stage(manager: ConsumptionV1, *, outcome: str, index: int = 1, domain: str = "bazi") -> dict[str, object]:
    return manager.stage_review_asset(
        {
            "domain": domain,
            "scenario": "career_exam",
            "topic": "civil_service_exam",
            "outcome_class": outcome,
            "content": f"结构化训练资产 {outcome} {index}",
            "source_case_ids": [f"case-ref-{outcome.lower()}-{index}"],
            "source_prediction_ids": [f"prediction-ref-{index}"],
            "error_types": ["wrong_timing"] if outcome == "FAILURE" else [],
            "created_at": NOW,
        }
    )


def _approve_publish(manager: ConsumptionV1, review: dict[str, object], *, published_at: str = NOW) -> dict[str, object]:
    approval = manager.decide_review(
        {
            "review_id": review["review_id"],
            "decision": "approved",
            "reviewer_id": REVIEWER,
            "review_note": "人工复核通过，仅供受控检索。",
            "decided_at": NOW,
        }
    )
    return manager.publish_approved_asset(
        {
            "review_id": review["review_id"],
            "approval_id": approval["approval_id"],
            "published_at": published_at,
        }
    )


def test_review_requires_domain_scenario_topic_and_source_case() -> None:
    temp, manager, _root = _manager()
    try:
        with pytest.raises(TrainingError, match="MISSING_RETRIEVAL_TAGS"):
            manager.stage_review_asset(
                {
                    "domain": "bazi",
                    "scenario": "",
                    "topic": "civil_service_exam",
                    "outcome_class": "VERIFIED_HIT",
                    "content": "x",
                    "source_case_ids": ["case-ref"],
                    "created_at": NOW,
                }
            )
    finally:
        temp.cleanup()


def test_rejected_review_cannot_publish() -> None:
    temp, manager, _root = _manager()
    try:
        review = _stage(manager, outcome="VERIFIED_HIT")
        approval = manager.decide_review(
            {
                "review_id": review["review_id"],
                "decision": "rejected",
                "reviewer_id": REVIEWER,
                "review_note": "证据不足。",
                "decided_at": NOW,
            }
        )
        with pytest.raises(TrainingError, match="HUMAN_APPROVAL_REQUIRED"):
            manager.publish_approved_asset(
                {
                    "review_id": review["review_id"],
                    "approval_id": approval["approval_id"],
                    "published_at": NOW,
                }
            )
    finally:
        temp.cleanup()


def test_unverified_can_be_archived_but_never_retrieved() -> None:
    temp, manager, _root = _manager()
    try:
        _approve_publish(manager, _stage(manager, outcome="UNVERIFIED"))
        context = manager.retrieve(
            domain="bazi",
            scenario="career_exam",
            topic="civil_service_exam",
            query_id="query-unverified",
            consumed_at=NOW,
        )
        assert context["status"] == "NO_HISTORICAL_CONTEXT"
        assert context["positive_cases"] == []
        assert context["failure_cases"] == []
        assert manager.status()["retrievable_assets"] == 0
    finally:
        temp.cleanup()


def test_exact_same_domain_scenario_topic_retrieval_and_limits() -> None:
    temp, manager, root = _manager()
    try:
        for index in range(1, 6):
            _approve_publish(manager, _stage(manager, outcome="VERIFIED_HIT", index=index))
        for index in range(1, 5):
            _approve_publish(manager, _stage(manager, outcome="FAILURE", index=index))
        for index in range(1, 4):
            _approve_publish(manager, _stage(manager, outcome="PARTIAL_HIT", index=index))
        _approve_publish(manager, _stage(manager, outcome="VERIFIED_HIT", index=99, domain="qimen"))

        context = manager.retrieve(
            domain="bazi",
            scenario="career_exam",
            topic="civil_service_exam",
            query_id="query-bazi",
            consumed_at=NOW,
            mode="SHADOW",
        )
        assert context["status"] == "CONTEXT_AVAILABLE"
        assert context["mode"] == "SHADOW"
        assert len(context["positive_cases"]) == 3
        assert len(context["failure_cases"]) == 2
        assert len(context["boundary_cases"]) == 2
        assert all(item["domain"] == "bazi" for item in context["positive_cases"])
        assert context["cross_domain_allowed"] is False
        assert (root / "consumption_audit.jsonl").is_file()
    finally:
        temp.cleanup()


def test_cross_scenario_or_topic_fails_closed() -> None:
    temp, manager, _root = _manager()
    try:
        _approve_publish(manager, _stage(manager, outcome="VERIFIED_HIT"))
        wrong_scenario = manager.retrieve(
            domain="bazi",
            scenario="relationship_reunion",
            topic="civil_service_exam",
            query_id="query-wrong-scenario",
            consumed_at=NOW,
        )
        wrong_topic = manager.retrieve(
            domain="bazi",
            scenario="career_exam",
            topic="marriage_timing",
            query_id="query-wrong-topic",
            consumed_at=NOW,
        )
        assert wrong_scenario["status"] == "NO_HISTORICAL_CONTEXT"
        assert wrong_topic["status"] == "NO_HISTORICAL_CONTEXT"
    finally:
        temp.cleanup()


def test_missing_query_tags_returns_no_context_and_audits() -> None:
    temp, manager, root = _manager()
    try:
        context = manager.retrieve(
            domain="bazi",
            scenario="",
            topic="civil_service_exam",
            query_id="query-missing-tag",
            consumed_at=NOW,
        )
        assert context["status"] == "NO_HISTORICAL_CONTEXT"
        assert context["reason"] == "scenario_or_topic_missing"
        assert (root / "consumption_audit.jsonl").read_text(encoding="utf-8").count("query-missing-tag") == 1
    finally:
        temp.cleanup()
