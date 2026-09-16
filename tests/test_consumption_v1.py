from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

import pytest

from mingli.consumption_v1 import ConsumptionV1
from mingli.training import TrainingError, TrainingStore


NOW = "2026-09-16T08:30:00+00:00"
LATER = "2026-09-16T08:31:00+00:00"
REVIEWER = "reviewer:" + "a" * 64


def _manager() -> tuple[tempfile.TemporaryDirectory[str], ConsumptionV1, Path]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    repo = root / "repo"
    repo.mkdir()
    store = TrainingStore(root / "training", repository_root=repo)
    return temp, ConsumptionV1(store), store.root


def _stage(
    manager: ConsumptionV1,
    *,
    outcome: str,
    index: int = 1,
    domain: str = "bazi",
    source_case_id: str | None = None,
) -> dict[str, object]:
    return manager.stage_review_asset(
        {
            "domain": domain,
            "scenario": "career_exam",
            "topic": "civil_service_exam",
            "outcome_class": outcome,
            "content": f"结构化训练资产 {outcome} {index}",
            "source_case_ids": [source_case_id or f"case-ref-{outcome.lower()}-{index}"],
            "source_prediction_ids": [f"prediction-ref-{index}"],
            "error_types": ["wrong_timing"] if outcome == "FAILURE" else [],
            "created_at": NOW,
        }
    )


def _approve(
    manager: ConsumptionV1,
    review: dict[str, object],
    *,
    decided_at: str = NOW,
) -> dict[str, object]:
    return manager.decide_review(
        {
            "review_id": review["review_id"],
            "decision": "approved",
            "reviewer_id": REVIEWER,
            "review_note": "人工复核通过，仅供受控检索。",
            "decided_at": decided_at,
        }
    )


def _approve_publish(
    manager: ConsumptionV1,
    review: dict[str, object],
    *,
    published_at: str = NOW,
) -> dict[str, object]:
    approval = _approve(manager, review)
    return manager.publish_approved_asset(
        {
            "review_id": review["review_id"],
            "approval_id": approval["approval_id"],
            "published_at": published_at,
        }
    )


def _write_withdrawal_tombstone(root: Path, case_id: str) -> None:
    filename = hashlib.sha256(case_id.encode("utf-8")).hexdigest() + ".json"
    directory = root / "tombstones"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(
        json.dumps(
            {
                "case_ref_hash": hashlib.sha256(case_id.encode("utf-8")).hexdigest(),
                "action": "CONSENT_WITHDRAWN",
                "withdrawn_at": LATER,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
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


def test_later_rejection_invalidates_older_approval_before_publish() -> None:
    temp, manager, _root = _manager()
    try:
        review = _stage(manager, outcome="VERIFIED_HIT")
        approved = _approve(manager, review)
        manager.decide_review(
            {
                "review_id": review["review_id"],
                "decision": "rejected",
                "reviewer_id": REVIEWER,
                "review_note": "复核后撤回批准。",
                "decided_at": LATER,
            }
        )
        with pytest.raises(TrainingError, match="STALE_APPROVAL_RECEIPT"):
            manager.publish_approved_asset(
                {
                    "review_id": review["review_id"],
                    "approval_id": approved["approval_id"],
                    "published_at": LATER,
                }
            )
    finally:
        temp.cleanup()


def test_later_rejection_revokes_already_published_asset_from_retrieval() -> None:
    temp, manager, _root = _manager()
    try:
        review = _stage(manager, outcome="VERIFIED_HIT")
        _approve_publish(manager, review)
        before = manager.retrieve(
            domain="bazi",
            scenario="career_exam",
            topic="civil_service_exam",
            query_id="query-before-rejection",
            consumed_at=NOW,
        )
        assert before["status"] == "CONTEXT_AVAILABLE"

        manager.decide_review(
            {
                "review_id": review["review_id"],
                "decision": "rejected",
                "reviewer_id": REVIEWER,
                "review_note": "发布后复核撤销。",
                "decided_at": LATER,
            }
        )
        after = manager.retrieve(
            domain="bazi",
            scenario="career_exam",
            topic="civil_service_exam",
            query_id="query-after-rejection",
            consumed_at=LATER,
        )
        assert after["status"] == "NO_HISTORICAL_CONTEXT"
        assert after["positive_cases"] == []
        status = manager.status()
        assert status["published_assets"] == 1
        assert status["retrievable_assets"] == 0
        assert status["revoked_or_withdrawn_assets"] == 1
    finally:
        temp.cleanup()


def test_withdrawn_source_case_revokes_already_published_asset() -> None:
    temp, manager, root = _manager()
    try:
        case_id = "person:" + "b" * 64
        review = _stage(
            manager,
            outcome="FAILURE",
            source_case_id=case_id,
        )
        _approve_publish(manager, review)
        _write_withdrawal_tombstone(root, case_id)
        context = manager.retrieve(
            domain="bazi",
            scenario="career_exam",
            topic="civil_service_exam",
            query_id="query-after-withdrawal",
            consumed_at=LATER,
        )
        assert context["status"] == "NO_HISTORICAL_CONTEXT"
        assert context["failure_cases"] == []
        assert manager.status()["revoked_or_withdrawn_assets"] == 1
    finally:
        temp.cleanup()


def test_withdrawn_source_case_cannot_enter_review() -> None:
    temp, manager, root = _manager()
    try:
        case_id = "person:" + "c" * 64
        _write_withdrawal_tombstone(root, case_id)
        with pytest.raises(TrainingError, match="SOURCE_CASE_WITHDRAWN"):
            _stage(
                manager,
                outcome="VERIFIED_HIT",
                source_case_id=case_id,
            )
    finally:
        temp.cleanup()


def test_same_review_cannot_be_published_twice() -> None:
    temp, manager, _root = _manager()
    try:
        review = _stage(manager, outcome="VERIFIED_HIT")
        approval = _approve(manager, review)
        manager.publish_approved_asset(
            {
                "review_id": review["review_id"],
                "approval_id": approval["approval_id"],
                "published_at": NOW,
            }
        )
        with pytest.raises(TrainingError, match="ASSET_ALREADY_PUBLISHED"):
            manager.publish_approved_asset(
                {
                    "review_id": review["review_id"],
                    "approval_id": approval["approval_id"],
                    "published_at": LATER,
                }
            )
        assert manager.status()["published_assets"] == 1
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
        assert context["usage_policy"]["failure_cases"] == "risk_warning_only_do_not_imitate"
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
