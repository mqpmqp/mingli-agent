from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from .chart import build_liuyao_chart
from .models import LiuYaoCastInput, LiuYaoChart
from .prediction import PredictionVersion, SettlementRecord
from .tables import PREDICTION_VALIDITY, digest
from .validation import LiuYaoError, LiuYaoInputConflictError, _aware_datetime, _non_empty, _reject_unknown, _require_mapping

_digest = digest


def _date_in_cast_timezone(value: str, cast_completed_at: str) -> date:
    cast_datetime = datetime.fromisoformat(cast_completed_at)
    if cast_datetime.tzinfo is None:
        raise RuntimeError("validated cast timestamp unexpectedly lacks timezone")
    return datetime.fromisoformat(value).astimezone(cast_datetime.tzinfo).date()


@dataclass(frozen=True, slots=True)
class LiuYaoCaseRecord:
    cast: LiuYaoCastInput
    chart: LiuYaoChart
    predictions: tuple[PredictionVersion, ...] = ()
    current_version_id: str | None = None
    settlement: SettlementRecord | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.cast, LiuYaoCastInput) or not isinstance(self.chart, LiuYaoChart):
            raise LiuYaoError("INVALID_INPUT", "cast/chart 类型无效")
        expected = build_liuyao_chart(self.cast)
        if self.chart.to_dict() != expected.to_dict():
            raise LiuYaoError("RECORD_TAMPERED", "chart 与 cast 的确定性重算结果不一致")
        predictions = tuple(self.predictions)
        if any(not isinstance(item, PredictionVersion) for item in predictions):
            raise LiuYaoError("INVALID_INPUT", "predictions 只能包含 PredictionVersion")
        ids = [item.version_id for item in predictions]
        if len(ids) != len(set(ids)):
            raise LiuYaoError("DUPLICATE_VERSION", "version_id 必须唯一")
        object.__setattr__(self, "predictions", predictions)
        cast_completed = datetime.fromisoformat(self.cast.completed_at)
        contract_deadline = date.fromisoformat(self.cast.event_contract.deadline)
        for prediction in predictions:
            created = datetime.fromisoformat(prediction.created_at)
            if created < cast_completed:
                raise LiuYaoError("INVALID_TRANSITION", "预测版本 created_at 不能早于起卦完成时间")
            if _date_in_cast_timezone(prediction.created_at, self.cast.completed_at) > contract_deadline:
                raise LiuYaoError("INVALID_TRANSITION", "预测版本必须在事件合同截止日当天或之前创建")
            if prediction.published_at is not None:
                published = datetime.fromisoformat(prediction.published_at)
                if published < cast_completed:
                    raise LiuYaoError("INVALID_TRANSITION", "published_at 不能早于起卦完成时间")
                if _date_in_cast_timezone(prediction.published_at, self.cast.completed_at) > contract_deadline:
                    raise LiuYaoError("INVALID_TRANSITION", "预测版本必须在事件合同截止日当天或之前发布")
        if self.current_version_id is not None:
            matches = [item for item in predictions if item.version_id == self.current_version_id]
            if len(matches) != 1 or matches[0].status not in {"draft", "pending"}:
                raise LiuYaoError("INVALID_TRANSITION", "current_version_id 必须指向 draft 或 pending 版本")
        pending_ids = {item.version_id for item in predictions if item.status == "pending"}
        if pending_ids and pending_ids != {self.current_version_id}:
            raise LiuYaoError("INVALID_TRANSITION", "pending 版本必须且只能是 current_version_id")
        settled_versions = [item for item in predictions if item.status == "settled"]
        if self.settlement is None and settled_versions:
            raise LiuYaoError("INVALID_TRANSITION", "settled 版本必须有对应 settlement")
        if self.settlement is not None:
            if not isinstance(self.settlement, SettlementRecord):
                raise LiuYaoError("INVALID_INPUT", "settlement 类型无效")
            if self.current_version_id is not None or any(item.status in {"draft", "pending"} for item in predictions):
                raise LiuYaoError("INVALID_TRANSITION", "案例结算后不能保留 current、draft 或 pending 版本")
            matches = [item for item in settled_versions if item.version_id == self.settlement.version_id]
            if len(settled_versions) != 1 or len(matches) != 1:
                raise LiuYaoError("INVALID_TRANSITION", "settlement 必须唯一指向 settled 版本")
            settled_version = matches[0]
            if settled_version.published_at is None:
                raise LiuYaoError("INVALID_TRANSITION", "settled 版本必须保留 published_at")
            observed = datetime.fromisoformat(self.settlement.observed_at)
            published = datetime.fromisoformat(settled_version.published_at)
            if observed < published:
                raise LiuYaoError("INVALID_TRANSITION", "settlement.observed_at 不能早于预测版本发布时间")
            if self.settlement.outcome == "hit":
                if self.settlement.occurred_at is None:
                    raise LiuYaoError("INVALID_TRANSITION", "hit 结算必须记录成功事件发生时间")
                occurred = datetime.fromisoformat(self.settlement.occurred_at)
                if occurred < published:
                    raise LiuYaoError("INVALID_TRANSITION", "settlement.occurred_at 不能早于预测版本发布时间")
                if occurred > observed:
                    raise LiuYaoError("INVALID_TRANSITION", "settlement.occurred_at 不能晚于 observed_at")
                if _date_in_cast_timezone(self.settlement.occurred_at, self.cast.completed_at) > contract_deadline:
                    raise LiuYaoError("OUTSIDE_EVENT_WINDOW", "成功事件发生时间超过事件合同截止日")
            elif _date_in_cast_timezone(self.settlement.observed_at, self.cast.completed_at) < contract_deadline:
                raise LiuYaoError("PREMATURE_SETTLEMENT", "未到事件合同截止日，不能登记 miss/partial/indeterminate")

    @property
    def canonical_sha256(self) -> str:
        return _digest(self.to_dict(include_hash=False))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "case_id": self.cast.case_id,
            "cast": self.cast.to_dict(),
            "chart": self.chart.to_dict(),
            "predictions": [item.to_dict() for item in self.predictions],
            "current_version_id": self.current_version_id,
            "settlement": None if self.settlement is None else self.settlement.to_dict(),
            "prediction_validity": PREDICTION_VALIDITY,
        }
        if include_hash:
            payload["canonical_sha256"] = _digest(payload)
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LiuYaoCaseRecord":
        allowed = {
            "case_id", "cast", "chart", "predictions", "current_version_id", "settlement",
            "prediction_validity", "canonical_sha256",
        }
        _reject_unknown(value, allowed, "case_record")
        required = {"cast", "chart", "predictions", "current_version_id", "settlement"}
        missing = required - set(value)
        if missing:
            raise LiuYaoError("INVALID_INPUT", f"case_record 缺少字段：{', '.join(sorted(missing))}")
        if value.get("prediction_validity", PREDICTION_VALIDITY) != PREDICTION_VALIDITY:
            raise LiuYaoError("INVALID_INPUT", "prediction_validity 必须是 not_evaluated")
        cast = LiuYaoCastInput.from_mapping(_require_mapping(value["cast"], "cast"))
        if value.get("case_id", cast.case_id) != cast.case_id:
            raise LiuYaoError("RECORD_TAMPERED", "case_id 与 cast.case_id 不一致")
        chart = build_liuyao_chart(cast)
        supplied_chart = _require_mapping(value["chart"], "chart")
        if supplied_chart != chart.to_dict():
            raise LiuYaoError("RECORD_TAMPERED", "chart 与 cast 的确定性重算结果不一致")
        raw_predictions = value["predictions"]
        if isinstance(raw_predictions, (str, bytes)) or not isinstance(raw_predictions, Sequence):
            raise LiuYaoError("INVALID_INPUT", "predictions 必须是数组")
        predictions = tuple(PredictionVersion.from_mapping(_require_mapping(item, "prediction")) for item in raw_predictions)
        settlement_value = value["settlement"]
        settlement = None if settlement_value is None else SettlementRecord.from_mapping(_require_mapping(settlement_value, "settlement"))
        record = cls(
            cast=cast,
            chart=chart,
            predictions=predictions,
            current_version_id=value["current_version_id"],
            settlement=settlement,
        )
        supplied_hash = value.get("canonical_sha256")
        if supplied_hash is not None and supplied_hash != record.canonical_sha256:
            raise LiuYaoError("RECORD_TAMPERED", "case_record canonical_sha256 与重算结果不一致")
        return record


def create_case_record(cast: LiuYaoCastInput) -> LiuYaoCaseRecord:
    return LiuYaoCaseRecord(cast=cast, chart=build_liuyao_chart(cast))


def register_cast(existing: LiuYaoCaseRecord | None, incoming: LiuYaoCastInput) -> LiuYaoCaseRecord:
    if existing is None:
        return create_case_record(incoming)
    if existing.cast.case_id != incoming.case_id:
        raise LiuYaoInputConflictError("CASE_ID_CONFLICT", "existing 与 incoming 的 case_id 不一致")
    if existing.cast.line_values != incoming.line_values:
        raise LiuYaoInputConflictError(
            "INPUT_CONFLICT",
            f"同一 case_id 的六摇序列冲突：已有 {existing.cast.line_values}，新输入 {incoming.line_values}",
        )
    if existing.cast.to_dict(include_hash=False) != incoming.to_dict(include_hash=False):
        raise LiuYaoInputConflictError("CONTRACT_CONFLICT", "同一 case_id 的问题、事件合同或起卦元数据发生变化")
    return existing


def append_prediction(record: LiuYaoCaseRecord, version: PredictionVersion, *, make_current: bool = True) -> LiuYaoCaseRecord:
    if record.settlement is not None:
        raise LiuYaoError("INVALID_TRANSITION", "案例已结算，不能追加预测版本")
    if version.status not in {"draft", "pending"}:
        raise LiuYaoError("INVALID_TRANSITION", "新版本只能以 draft 或 pending 状态登记")
    if version.status == "pending" and not make_current:
        raise LiuYaoError("INVALID_TRANSITION", "pending 版本必须登记为 current")
    if any(item.version_id == version.version_id for item in record.predictions):
        raise LiuYaoError("DUPLICATE_VERSION", f"version_id 已存在：{version.version_id}")
    if make_current and record.current_version_id is not None:
        raise LiuYaoError("INVALID_TRANSITION", "必须先作废或结算当前版本，再登记新的 current 版本")
    current = version.version_id if make_current else record.current_version_id
    return LiuYaoCaseRecord(
        cast=record.cast,
        chart=record.chart,
        predictions=record.predictions + (version,),
        current_version_id=current,
        settlement=record.settlement,
    )


def activate_prediction(record: LiuYaoCaseRecord, version_id: str, *, published_at: str) -> LiuYaoCaseRecord:
    if record.settlement is not None:
        raise LiuYaoError("INVALID_TRANSITION", "案例已结算，不能发布预测版本")
    target = _non_empty(version_id, "version_id")
    published = _aware_datetime(published_at, "published_at")
    if record.current_version_id not in {None, target}:
        raise LiuYaoError("INVALID_TRANSITION", "必须先作废当前版本，再发布其他 draft")
    updated: list[PredictionVersion] = []
    found = False
    for version in record.predictions:
        if version.version_id != target:
            updated.append(version)
            continue
        found = True
        if version.status != "draft":
            raise LiuYaoError("INVALID_TRANSITION", "只有 draft 版本可以发布为 pending")
        updated.append(replace(version, status="pending", published_at=published))
    if not found:
        raise LiuYaoError("VERSION_NOT_FOUND", f"未找到版本：{target}")
    return LiuYaoCaseRecord(
        cast=record.cast,
        chart=record.chart,
        predictions=tuple(updated),
        current_version_id=target,
        settlement=record.settlement,
    )


def invalidate_prediction(record: LiuYaoCaseRecord, version_id: str, *, reason: str, invalidated_at: str) -> LiuYaoCaseRecord:
    target = _non_empty(version_id, "version_id")
    reason_text = _non_empty(reason, "reason")
    invalidated = _aware_datetime(invalidated_at, "invalidated_at")
    updated: list[PredictionVersion] = []
    found = False
    for version in record.predictions:
        if version.version_id != target:
            updated.append(version)
            continue
        found = True
        if version.status not in {"draft", "pending"}:
            raise LiuYaoError("INVALID_TRANSITION", "只有 draft 或 pending 版本可以作废")
        updated.append(replace(version, status="invalid", invalid_reason=reason_text, invalidated_at=invalidated))
    if not found:
        raise LiuYaoError("VERSION_NOT_FOUND", f"未找到版本：{target}")
    return LiuYaoCaseRecord(
        cast=record.cast,
        chart=record.chart,
        predictions=tuple(updated),
        current_version_id=None if record.current_version_id == target else record.current_version_id,
        settlement=record.settlement,
    )


def settle_prediction(
    record: LiuYaoCaseRecord,
    version_id: str,
    *,
    outcome: str,
    observed_at: str,
    evidence_source: str,
    occurred_at: str | None = None,
    notes: Sequence[str] = (),
) -> LiuYaoCaseRecord:
    if record.settlement is not None:
        raise LiuYaoError("INVALID_TRANSITION", "该案例已经结算，不能覆盖既有结算记录")
    target = _non_empty(version_id, "version_id")
    if record.current_version_id != target:
        raise LiuYaoError("INVALID_TRANSITION", "只能结算 current_version_id 指向的 pending 版本")
    settlement = SettlementRecord(
        version_id=target,
        outcome=outcome,
        occurred_at=observed_at if outcome == "hit" and occurred_at is None else occurred_at,
        observed_at=observed_at,
        evidence_source=evidence_source,
        notes=tuple(notes),
    )
    contract_deadline = date.fromisoformat(record.cast.event_contract.deadline)
    if outcome == "hit":
        if settlement.occurred_at is None:
            raise LiuYaoError("INVALID_TRANSITION", "hit 结算必须记录成功事件发生时间")
        if _date_in_cast_timezone(settlement.occurred_at, record.cast.completed_at) > contract_deadline:
            raise LiuYaoError("OUTSIDE_EVENT_WINDOW", "成功事件发生时间超过事件合同截止日")
    elif _date_in_cast_timezone(settlement.observed_at, record.cast.completed_at) < contract_deadline:
        raise LiuYaoError("PREMATURE_SETTLEMENT", "未到事件合同截止日，不能登记 miss/partial/indeterminate")
    updated: list[PredictionVersion] = []
    found = False
    for version in record.predictions:
        if version.version_id != target:
            updated.append(version)
            continue
        found = True
        if version.status != "pending":
            raise LiuYaoError("INVALID_TRANSITION", "只有 pending 版本可以结算")
        updated.append(replace(version, status="settled"))
    if not found:
        raise LiuYaoError("VERSION_NOT_FOUND", f"未找到版本：{target}")
    return LiuYaoCaseRecord(
        cast=record.cast,
        chart=record.chart,
        predictions=tuple(updated),
        current_version_id=None if record.current_version_id == target else record.current_version_id,
        settlement=settlement,
    )
