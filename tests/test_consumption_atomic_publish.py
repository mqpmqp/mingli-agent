from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile

from mingli.consumption_v1 import ConsumptionV1
from mingli.contracts import digest
from mingli.training import TrainingError, TrainingStore


NOW = "2026-09-16T08:30:00+00:00"
LATER = "2026-09-16T08:31:00+00:00"
REVIEWER = "reviewer:" + "a" * 64


def _manager() -> tuple[tempfile.TemporaryDirectory[str], ConsumptionV1]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    repo = root / "repo"
    repo.mkdir()
    return temp, ConsumptionV1(TrainingStore(root / "training", repository_root=repo))


def _review_and_approval(manager: ConsumptionV1) -> tuple[dict[str, object], dict[str, object]]:
    review = manager.stage_review_asset(
        {
            "domain": "bazi",
            "scenario": "career_exam",
            "topic": "civil_service_exam",
            "outcome_class": "VERIFIED_HIT",
            "content": "发布唯一性测试资产。",
            "source_case_ids": ["case-ref-concurrency-1"],
            "source_prediction_ids": ["prediction-ref-concurrency-1"],
            "error_types": [],
            "created_at": NOW,
        }
    )
    approval = manager.decide_review(
        {
            "review_id": review["review_id"],
            "decision": "approved",
            "reviewer_id": REVIEWER,
            "review_note": "人工批准。",
            "decided_at": NOW,
        }
    )
    return review, approval


def test_same_review_concurrent_publish_has_exactly_one_winner() -> None:
    temp, manager = _manager()
    try:
        review, approval = _review_and_approval(manager)

        def publish(published_at: str) -> str:
            try:
                result = manager.publish_approved_asset(
                    {
                        "review_id": review["review_id"],
                        "approval_id": approval["approval_id"],
                        "published_at": published_at,
                    }
                )
                return "ok:" + str(result["asset_id"])
            except TrainingError as exc:
                return "error:" + exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(publish, [NOW, LATER]))

        assert sum(item.startswith("ok:") for item in outcomes) == 1
        assert outcomes.count("error:ASSET_ALREADY_PUBLISHED") == 1
        assert manager.status()["published_assets"] == 1
    finally:
        temp.cleanup()


def test_legacy_v1_asset_blocks_republish_under_new_deterministic_id() -> None:
    temp, manager = _manager()
    try:
        review, approval = _review_and_approval(manager)
        body = {
            "review_id": review["review_id"],
            "review_hash": review["review_hash"],
            "approval_id": approval["approval_id"],
            "domain": review["domain"],
            "scenario": review["scenario"],
            "topic": review["topic"],
            "outcome_class": review["outcome_class"],
            "content": review["content"],
            "source_case_ids": review["source_case_ids"],
            "source_prediction_ids": review.get("source_prediction_ids", []),
            "error_types": review.get("error_types", []),
            "published_at": NOW,
            "consumption_eligible": True,
        }
        legacy_hash = digest({"record_type": "ConsumptionAsset", "payload": body})
        legacy_id = "consumption-asset:" + legacy_hash.split(":", 1)[1]
        manager._write_once(
            "asset",
            legacy_id,
            {"asset_id": legacy_id, "asset_hash": legacy_hash, **body},
        )

        try:
            manager.publish_approved_asset(
                {
                    "review_id": review["review_id"],
                    "approval_id": approval["approval_id"],
                    "published_at": LATER,
                }
            )
        except TrainingError as exc:
            assert exc.code == "ASSET_ALREADY_PUBLISHED"
        else:
            raise AssertionError("legacy REVIEW must not be republished")

        assert manager.status()["published_assets"] == 1
    finally:
        temp.cleanup()
