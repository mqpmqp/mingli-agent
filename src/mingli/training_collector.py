from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Mapping

from .consumption_v1 import ConsumptionV1
from .phase4_1 import Phase41Pilot
from .rule_promotion import RulePromotionPipeline
from .training import TrainingError, TrainingStore


TRAINING_COLLECTOR_VERSION = "mingli-hourly-training-collector@1.1"
AUTOMATION_DOMAINS = {
    "bazi-dual-teacher-hourly-training": "bazi",
    "qimen-hourly-training": "qimen",
    "fengshui-hourly-training": "fengshui",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TrainingReportCollector:
    """Ingest reports, run non-human gates, and expose reviewed asset consumption.

    The collector deliberately stops before human approval and rule release. Consumption
    V1 has separate explicit review/approval/publish operations and never promotes assets
    automatically. A single service process serializes writes.
    """

    def __init__(self, store: TrainingStore) -> None:
        self.store = store
        self.pipeline = RulePromotionPipeline(store)
        self.phase4_1 = Phase41Pilot(store)
        self.consumption = ConsumptionV1(store)
        self._write_lock = RLock()

    def collect(
        self,
        report: Mapping[str, object],
        *,
        received_at: str | None = None,
    ) -> dict[str, object]:
        automation_id = str(report.get("automation_id", ""))
        expected_domain = AUTOMATION_DOMAINS.get(automation_id)
        if expected_domain is None:
            raise TrainingError(
                "AUTOMATION_NOT_ALLOWED",
                "hourly report automation_id is not registered for collection",
                field_path="$.automation_id",
            )
        if report.get("domain") != expected_domain:
            raise TrainingError(
                "AUTOMATION_DOMAIN_MISMATCH",
                f"{automation_id} reports must use domain={expected_domain}",
                field_path="$.domain",
            )

        checked_at = received_at or _utc_now()
        with self._write_lock:
            ingestion = self.pipeline.ingest_hourly_report(report)
            gate_results: list[dict[str, object]] = []
            for candidate_id in ingestion["candidate_ids"]:
                source_check = self.pipeline.verify_sources(
                    str(candidate_id), checked_at=checked_at
                )
                regression = self.pipeline.run_regression(
                    str(candidate_id), checked_at=checked_at
                )
                if source_check["status"] != "passed":
                    promotion_state = "blocked_source_review"
                elif regression["status"] != "passed":
                    promotion_state = "blocked_regression"
                else:
                    promotion_state = "awaiting_human_approval"
                gate_results.append(
                    {
                        "candidate_id": candidate_id,
                        "source_check_id": source_check["check_id"],
                        "source_status": source_check["status"],
                        "source_reasons": source_check["reasons"],
                        "regression_id": regression["regression_id"],
                        "regression_status": regression["status"],
                        "promotion_state": promotion_state,
                    }
                )

            stored_report = ingestion["report"]
            return {
                "schema_version": TRAINING_COLLECTOR_VERSION,
                "status": "accepted",
                "report_id": stored_report["report_id"],
                "report_hash": stored_report["report_hash"],
                "automation_id": stored_report["automation_id"],
                "domain": stored_report["domain"],
                "received_at": checked_at,
                "created_candidates": ingestion["created_candidates"],
                "deduplicated_candidates": ingestion["deduplicated_candidates"],
                "candidate_gates": gate_results,
                "human_approval_required": any(
                    item["promotion_state"] == "awaiting_human_approval"
                    for item in gate_results
                ),
                "auto_approved": False,
                "auto_published": False,
                "commercial_release_hold": "ACTIVE",
            }

    def status(self) -> dict[str, object]:
        with self._write_lock:
            pipeline_status = self.pipeline.status()
            queue = self.pipeline.review_queue()
            consumption_status = self.consumption.status()
        states: dict[str, int] = {}
        for item in queue["candidates"]:
            state = str(item["promotion_state"])
            states[state] = states.get(state, 0) + 1
        return {
            "schema_version": TRAINING_COLLECTOR_VERSION,
            "service_state": "ready",
            "accepted_automations": dict(AUTOMATION_DOMAINS),
            "single_process_writer_required": True,
            "pipeline": pipeline_status,
            "phase4_1": self.phase4_1.status(),
            "consumption_v1": consumption_status,
            "review_queue_counts": states,
            "automatic_steps": [
                "report_ingest",
                "content_deduplication",
                "source_gate_evaluation",
                "contract_regression",
            ],
            "manual_steps": [
                "source_review",
                "candidate_approval",
                "rule_publish",
                "consumption_asset_review",
                "consumption_asset_approval",
                "consumption_asset_publish",
            ],
        }

    def review_queue(self) -> dict[str, object]:
        with self._write_lock:
            return self.pipeline.review_queue()


__all__ = [
    "AUTOMATION_DOMAINS",
    "TRAINING_COLLECTOR_VERSION",
    "TrainingReportCollector",
]
