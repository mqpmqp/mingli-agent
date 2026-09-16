from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from .contracts import canonical_json, digest
from .training import TrainingError, TrainingStore
from .validation_privacy import scan_for_pii


CONSUMPTION_VERSION = "mingli-consumption-v1@1.3"
_ALLOWED_DOMAINS = frozenset({"bazi", "qimen", "fengshui"})
_ALLOWED_OUTCOMES = frozenset({
    "VERIFIED_HIT", "PARTIAL_HIT", "FAILURE", "UNVERIFIED", "CONTAMINATED", "INPUT_ERROR"
})
_POSITIVE = frozenset({"VERIFIED_HIT"})
_BOUNDARY = frozenset({"PARTIAL_HIT"})
_FAILURE = frozenset({"FAILURE"})
_RETRIEVABLE = _POSITIVE | _BOUNDARY | _FAILURE
_ALLOWED_MODES = frozenset({"SHADOW", "ACTIVE"})


def _record_name(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier or len(identifier) > 256:
        raise TrainingError("INVALID_RECORD_ID", "记录 ID 必须是非空字符串且长度不超过 256 个字符")
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest() + ".json"


def _parse_time(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TrainingError("INVALID_TIMESTAMP", f"{field} 必须是带时区的 ISO-8601 时间")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrainingError("INVALID_TIMESTAMP", f"{field} 必须使用 ISO-8601 格式") from exc
    if parsed.tzinfo is None:
        raise TrainingError("INVALID_TIMESTAMP", f"{field} 必须包含时区")
    return parsed


def _plain(value: Mapping[str, object]) -> dict[str, object]:
    return json.loads(canonical_json(value))


class ConsumptionV1:
    """人工批准训练资产的发布、检索与审计。

    REVIEW 与 approval 均绑定精确哈希。发布后的资产只有在当前最新人工决定仍为
    approved、来源案例未撤回、且 domain/scenario/topic 精确匹配时才可被检索。
    """

    def __init__(self, store: TrainingStore) -> None:
        self.training_store = store
        self.root = store.root

    def _path(self, kind: str, identifier: str) -> Path:
        directories = {
            "review": "consumption_review_assets",
            "approval": "consumption_approvals",
            "asset": "consumption_assets",
        }
        return self.root / directories[kind] / _record_name(identifier)

    def _write_once(self, kind: str, identifier: str, value: Mapping[str, object]) -> dict[str, object]:
        payload = _plain(value)
        findings = scan_for_pii(payload)
        if findings:
            raise TrainingError("PII_DETECTED", "Consumption 记录包含禁止保存的直接身份信息", field_path=findings[0].field_path)
        target = self._path(kind, identifier)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(payload) + "\n")
        except FileExistsError as exc:
            raise TrainingError("DUPLICATE_RECORD", f"{kind} 记录已存在") from exc
        return payload

    def _read(self, kind: str, identifier: str) -> dict[str, object]:
        target = self._path(kind, identifier)
        if not target.is_file():
            raise TrainingError("RECORD_NOT_FOUND", f"未找到 {kind} 记录")
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TrainingError("SCHEMA_INCOMPATIBLE", f"{kind} 记录必须是 JSON 对象")
        return value

    def _list(self, kind: str) -> list[dict[str, object]]:
        directories = {
            "review": "consumption_review_assets",
            "approval": "consumption_approvals",
            "asset": "consumption_assets",
        }
        directory = self.root / directories[kind]
        if not directory.is_dir():
            return []
        records: list[dict[str, object]] = []
        for path in sorted(directory.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                records.append(value)
        return records

    def _latest_decision_index(
        self,
        approvals: Sequence[Mapping[str, object]] | None = None,
    ) -> dict[tuple[str, str], dict[str, object]]:
        latest: dict[tuple[str, str], dict[str, object]] = {}
        records = approvals if approvals is not None else self._list("approval")
        for raw_item in records:
            item = dict(raw_item)
            key = (str(item.get("review_id", "")), str(item.get("review_hash", "")))
            current = latest.get(key)
            item_key = (
                _parse_time(item.get("decided_at"), field="decided_at"),
                str(item.get("approval_id", "")),
            )
            if current is None:
                latest[key] = item
                continue
            current_key = (
                _parse_time(current.get("decided_at"), field="decided_at"),
                str(current.get("approval_id", "")),
            )
            if item_key > current_key:
                latest[key] = item
        return latest

    def _latest_decision(self, review_id: str, review_hash: str) -> dict[str, object] | None:
        return self._latest_decision_index().get((review_id, review_hash))

    def _source_case_withdrawn(self, case_id: str) -> bool:
        return (self.root / "tombstones" / _record_name(case_id)).is_file()

    def _withdrawn_source_ids(self, source_case_ids: object) -> list[str]:
        if not isinstance(source_case_ids, Sequence) or isinstance(source_case_ids, (str, bytes)):
            return []
        return sorted(
            str(case_id) for case_id in source_case_ids
            if self._source_case_withdrawn(str(case_id))
        )

    def _asset_authorized_now(
        self,
        asset: Mapping[str, object],
        *,
        latest_decisions: Mapping[tuple[str, str], Mapping[str, object]] | None = None,
    ) -> bool:
        if asset.get("consumption_eligible") is not True:
            return False
        review_id = str(asset.get("review_id", ""))
        review_hash = str(asset.get("review_hash", ""))
        decision_index = latest_decisions if latest_decisions is not None else self._latest_decision_index()
        latest = decision_index.get((review_id, review_hash))
        if latest is None or latest.get("decision") != "approved":
            return False
        return not self._withdrawn_source_ids(asset.get("source_case_ids", []))

    def _asset_id_for_review(self, review_id: str, review_hash: str) -> str:
        identity_hash = digest(
            {
                "record_type": "ConsumptionAssetIdentity",
                "review_id": review_id,
                "review_hash": review_hash,
            }
        )
        return "consumption-asset:" + identity_hash.split(":", 1)[1]

    def _review_already_published(self, review_id: str, review_hash: str) -> bool:
        return any(
            item.get("review_id") == review_id and item.get("review_hash") == review_hash
            for item in self._list("asset")
        )

    def stage_review_asset(self, value: Mapping[str, object]) -> dict[str, object]:
        domain = str(value.get("domain", ""))
        outcome = str(value.get("outcome_class", ""))
        scenario = str(value.get("scenario", "")).strip()
        topic = str(value.get("topic", "")).strip()
        content = str(value.get("content", "")).strip()
        source_case_ids = value.get("source_case_ids", [])
        if domain not in _ALLOWED_DOMAINS:
            raise TrainingError("INVALID_CONSUMPTION_DOMAIN", "domain 只能是 bazi、qimen 或 fengshui")
        if outcome not in _ALLOWED_OUTCOMES:
            raise TrainingError("INVALID_OUTCOME_CLASS", "outcome_class 不在支持范围内")
        if not scenario or not topic:
            raise TrainingError("MISSING_RETRIEVAL_TAGS", "进入 REVIEW 前必须提供 scenario 和 topic")
        if not content:
            raise TrainingError("EMPTY_TRAINING_ASSET", "训练资产 content 不能为空")
        if not isinstance(source_case_ids, Sequence) or isinstance(source_case_ids, (str, bytes)) or not source_case_ids:
            raise TrainingError("MISSING_SOURCE_CASES", "source_case_ids 必须是非空数组")
        withdrawn = self._withdrawn_source_ids(source_case_ids)
        if withdrawn:
            raise TrainingError("SOURCE_CASE_WITHDRAWN", "来源案例已撤回同意，不能进入 Consumption REVIEW")
        created_at = str(value.get("created_at", ""))
        _parse_time(created_at, field="created_at")
        seed = {
            "domain": domain,
            "scenario": scenario,
            "topic": topic,
            "outcome_class": outcome,
            "content": content,
            "source_case_ids": sorted({str(item) for item in source_case_ids}),
            "source_prediction_ids": sorted({str(item) for item in value.get("source_prediction_ids", [])}) if isinstance(value.get("source_prediction_ids", []), list) else [],
            "error_types": sorted({str(item) for item in value.get("error_types", [])}) if isinstance(value.get("error_types", []), list) else [],
            "created_at": created_at,
            "review_state": "REVIEW",
        }
        review_hash = digest({"record_type": "ConsumptionReviewAsset", "payload": seed})
        review_id = "consumption-review:" + review_hash.split(":", 1)[1]
        return self._write_once("review", review_id, {"review_id": review_id, "review_hash": review_hash, **seed})

    def decide_review(self, value: Mapping[str, object]) -> dict[str, object]:
        review_id = str(value.get("review_id", ""))
        review = self._read("review", review_id)
        decision = str(value.get("decision", ""))
        if decision not in {"approved", "rejected"}:
            raise TrainingError("INVALID_APPROVAL_DECISION", "decision 只能是 approved 或 rejected")
        reviewer_id = str(value.get("reviewer_id", ""))
        if not reviewer_id:
            raise TrainingError("HUMAN_APPROVAL_REQUIRED", "必须提供 reviewer_id")
        decided_at = str(value.get("decided_at", ""))
        _parse_time(decided_at, field="decided_at")
        seed = {
            "review_id": review_id,
            "review_hash": review["review_hash"],
            "decision": decision,
            "reviewer_id": reviewer_id,
            "review_note": value.get("review_note"),
            "decided_at": decided_at,
        }
        approval_hash = digest({"record_type": "ConsumptionApproval", "payload": seed})
        approval_id = "consumption-approval:" + approval_hash.split(":", 1)[1]
        return self._write_once("approval", approval_id, {"approval_id": approval_id, **seed})

    def publish_approved_asset(self, value: Mapping[str, object]) -> dict[str, object]:
        review_id = str(value.get("review_id", ""))
        approval_id = str(value.get("approval_id", ""))
        review = self._read("review", review_id)
        approval = self._read("approval", approval_id)
        review_hash = str(review["review_hash"])
        if approval.get("review_id") != review_id or approval.get("review_hash") != review_hash:
            raise TrainingError("STALE_APPROVAL_RECEIPT", "批准回执未绑定当前 REVIEW 哈希")
        latest = self._latest_decision(review_id, review_hash)
        if latest is None or latest.get("approval_id") != approval_id:
            raise TrainingError("STALE_APPROVAL_RECEIPT", "只有当前最新人工决定可以授权发布")
        if approval.get("decision") != "approved":
            raise TrainingError("HUMAN_APPROVAL_REQUIRED", "只有人工 approved 的 REVIEW 才能发布")
        withdrawn = self._withdrawn_source_ids(review.get("source_case_ids", []))
        if withdrawn:
            raise TrainingError("SOURCE_CASE_WITHDRAWN", "来源案例已撤回同意，禁止发布 Consumption 资产")
        if self._review_already_published(review_id, review_hash):
            raise TrainingError("ASSET_ALREADY_PUBLISHED", "同一 REVIEW 只能发布一个 Consumption 资产")
        published_at = str(value.get("published_at", ""))
        _parse_time(published_at, field="published_at")
        body = {
            "review_id": review_id,
            "review_hash": review_hash,
            "approval_id": approval_id,
            "domain": review["domain"],
            "scenario": review["scenario"],
            "topic": review["topic"],
            "outcome_class": review["outcome_class"],
            "content": review["content"],
            "source_case_ids": review["source_case_ids"],
            "source_prediction_ids": review.get("source_prediction_ids", []),
            "error_types": review.get("error_types", []),
            "published_at": published_at,
            "consumption_eligible": review["outcome_class"] in _RETRIEVABLE,
        }
        asset_hash = digest({"record_type": "ConsumptionAsset", "payload": body})
        asset_id = self._asset_id_for_review(review_id, review_hash)
        try:
            return self._write_once(
                "asset",
                asset_id,
                {"asset_id": asset_id, "asset_hash": asset_hash, **body},
            )
        except TrainingError as exc:
            if exc.code == "DUPLICATE_RECORD":
                raise TrainingError(
                    "ASSET_ALREADY_PUBLISHED",
                    "同一 REVIEW 只能发布一个 Consumption 资产",
                ) from exc
            raise

    def retrieve(
        self,
        *,
        domain: str,
        scenario: str,
        topic: str,
        query_id: str,
        consumed_at: str,
        mode: str = "SHADOW",
    ) -> dict[str, object]:
        if domain not in _ALLOWED_DOMAINS:
            raise TrainingError("INVALID_CONSUMPTION_DOMAIN", "domain 只能是 bazi、qimen 或 fengshui")
        if mode not in _ALLOWED_MODES:
            raise TrainingError("INVALID_CONSUMPTION_MODE", "mode 只能是 SHADOW 或 ACTIVE")
        _parse_time(consumed_at, field="consumed_at")
        if not scenario.strip() or not topic.strip():
            return self._audit_and_return(
                query_id=query_id,
                consumed_at=consumed_at,
                domain=domain,
                scenario=scenario,
                topic=topic,
                mode=mode,
                status="NO_HISTORICAL_CONTEXT",
                positives=[],
                boundaries=[],
                failures=[],
                reason="scenario_or_topic_missing",
            )
        latest_decisions = self._latest_decision_index()
        matches = [
            item for item in self._list("asset")
            if self._asset_authorized_now(item, latest_decisions=latest_decisions)
            and item.get("domain") == domain
            and item.get("scenario") == scenario
            and item.get("topic") == topic
            and item.get("outcome_class") in _RETRIEVABLE
        ]
        matches.sort(
            key=lambda item: (
                _parse_time(item.get("published_at"), field="published_at"),
                str(item.get("asset_id", "")),
            ),
            reverse=True,
        )
        positives = [item for item in matches if item.get("outcome_class") in _POSITIVE][:3]
        boundaries = [item for item in matches if item.get("outcome_class") in _BOUNDARY][:2]
        failures = [item for item in matches if item.get("outcome_class") in _FAILURE][:2]
        status = "CONTEXT_AVAILABLE" if positives or boundaries or failures else "NO_HISTORICAL_CONTEXT"
        reason = None if status == "CONTEXT_AVAILABLE" else "no_same_domain_scenario_topic_assets"
        return self._audit_and_return(
            query_id=query_id,
            consumed_at=consumed_at,
            domain=domain,
            scenario=scenario,
            topic=topic,
            mode=mode,
            status=status,
            positives=positives,
            boundaries=boundaries,
            failures=failures,
            reason=reason,
        )

    def _audit_and_return(
        self,
        *,
        query_id: str,
        consumed_at: str,
        domain: str,
        scenario: str,
        topic: str,
        mode: str,
        status: str,
        positives: list[dict[str, object]],
        boundaries: list[dict[str, object]],
        failures: list[dict[str, object]],
        reason: str | None,
    ) -> dict[str, object]:
        selected = [str(item["asset_id"]) for item in [*positives, *boundaries, *failures]]
        body = {
            "query_id": query_id,
            "domain": domain,
            "scenario": scenario,
            "topic": topic,
            "mode": mode,
            "status": status,
            "selected_asset_ids": selected,
            "consumed_at": consumed_at,
            "reason": reason,
        }
        audit_hash = digest({"record_type": "ConsumptionAudit", "payload": body})
        audit = {"audit_id": "consumption-audit:" + audit_hash.split(":", 1)[1], **body}
        findings = scan_for_pii(audit)
        if findings:
            raise TrainingError("PII_DETECTED", "Consumption 审计记录包含禁止保存的直接身份信息", field_path=findings[0].field_path)
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "consumption_audit.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(audit) + "\n")
        return {
            "schema_version": CONSUMPTION_VERSION,
            "status": status,
            "mode": mode,
            "domain": domain,
            "scenario": scenario,
            "topic": topic,
            "positive_cases": positives,
            "boundary_cases": boundaries,
            "failure_cases": failures,
            "usage_policy": {
                "positive_cases": "reference_only_not_ground_truth",
                "boundary_cases": "boundary_learning_only",
                "failure_cases": "risk_warning_only_do_not_imitate",
            },
            "positive_limit": 3,
            "failure_limit": 2,
            "cross_domain_allowed": False,
            "audit_id": audit["audit_id"],
            "reason": reason,
        }

    def status(self) -> dict[str, object]:
        reviews = self._list("review")
        approvals = self._list("approval")
        assets = self._list("asset")
        latest_decisions = self._latest_decision_index(approvals)
        retrievable = [
            item for item in assets
            if self._asset_authorized_now(item, latest_decisions=latest_decisions)
        ]
        revoked = [
            item for item in assets
            if item.get("consumption_eligible") is True and item not in retrievable
        ]
        return {
            "schema_version": CONSUMPTION_VERSION,
            "reviews": len(reviews),
            "approvals": len(approvals),
            "published_assets": len(assets),
            "retrievable_assets": len(retrievable),
            "revoked_or_withdrawn_assets": len(revoked),
            "mode_default": "SHADOW",
            "positive_limit": 3,
            "failure_limit": 2,
            "cross_domain_allowed": False,
        }


__all__ = ["CONSUMPTION_VERSION", "ConsumptionV1"]
