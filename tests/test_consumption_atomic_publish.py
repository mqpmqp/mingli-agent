from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile

from mingli.consumption_v1 import ConsumptionV1
from mingli.training import TrainingError, TrainingStore


NOW = "2026-09-16T08:30:00+00:00"
LATER = "2026-09-16T08:31:00+00:00"
REVIEWER = "reviewer:" + "a" * 64


def test_same_review_concurrent_publish_has_exactly_one_winner() -> None:
    with tempfile.TemporaryDirectory() as value:
        root = Path(value)
        repo = root / "repo"
        repo.mkdir()
        manager = ConsumptionV1(
            TrainingStore(root / "training", repository_root=repo)
        )
        review = manager.stage_review_asset(
            {
                "domain": "bazi",
                "scenario": "career_exam",
                "topic": "civil_service_exam",
                "outcome_class": "VERIFIED_HIT",
                "content": "并发发布唯一性测试资产。",
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
