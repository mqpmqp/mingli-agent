from __future__ import annotations

import json
from pathlib import Path

import pytest

from mingli.liuyao import (
    EventContract,
    LiuYaoCastInput,
    LiuYaoError,
    PredictionVersion,
    append_prediction,
    create_case_record,
    settle_prediction,
)
from mingli.liuyao_cli import main


def _record():
    cast = LiuYaoCastInput(
        case_id="TEMPORAL-CASE",
        question="截止日前是否满足成功标准",
        line_values=(6, 7, 7, 8, 7, 7),
        event_contract=EventContract(
            target_event="满足成功标准",
            deadline="2026-12-31",
            success_criteria="可核验证据确认目标事件成立",
            evidence_requirement="带时间的正式记录",
        ),
        completed_at="2026-08-31T21:57:00+08:00",
        location="测试地点",
    )
    version = PredictionVersion(
        version_id="V1",
        created_at="2026-09-01T08:00:00+08:00",
        status="pending",
        conclusion="等待截止日结算",
        confidence="medium",
        published_at="2026-09-01T08:00:00+08:00",
    )
    return append_prediction(create_case_record(cast), version)


def test_prediction_deadline_is_evaluated_in_cast_timezone() -> None:
    record = create_case_record(_record().cast)
    cross_zone_late = PredictionVersion(
        version_id="LATE",
        created_at="2026-12-31T12:30:00-12:00",
        status="pending",
        conclusion="该时间换算到起卦时区已是次日",
        confidence="low",
        published_at="2026-12-31T12:30:00-12:00",
    )

    with pytest.raises(LiuYaoError, match="截止日当天或之前创建"):
        append_prediction(record, cross_zone_late)


def test_negative_settlement_cannot_use_foreign_offset_to_bypass_deadline() -> None:
    record = _record()

    with pytest.raises(LiuYaoError) as raised:
        settle_prediction(
            record,
            "V1",
            outcome="miss",
            observed_at="2026-12-31T00:30:00+14:00",
            evidence_source="测试证据",
        )

    assert raised.value.code == "PREMATURE_SETTLEMENT"


def test_hit_after_contract_deadline_is_not_counted() -> None:
    record = _record()

    with pytest.raises(LiuYaoError) as raised:
        settle_prediction(
            record,
            "V1",
            outcome="hit",
            occurred_at="2027-01-01T00:01:00+08:00",
            observed_at="2027-01-01T09:00:00+08:00",
            evidence_source="测试证据",
        )

    assert raised.value.code == "OUTSIDE_EVENT_WINDOW"


def test_late_evidence_can_settle_an_on_time_hit() -> None:
    record = _record()

    settled = settle_prediction(
        record,
        "V1",
        outcome="hit",
        occurred_at="2026-12-31T23:00:00+08:00",
        observed_at="2027-01-02T09:00:00+08:00",
        evidence_source="正式记录",
    )

    assert settled.settlement is not None
    assert settled.settlement.occurred_at == "2026-12-31T23:00:00+08:00"
    assert settled.settlement.observed_at == "2027-01-02T09:00:00+08:00"


def test_hit_occurrence_cannot_predate_publication() -> None:
    record = _record()

    with pytest.raises(LiuYaoError, match="occurred_at 不能早于预测版本发布时间"):
        settle_prediction(
            record,
            "V1",
            outcome="hit",
            occurred_at="2026-09-01T07:59:59+08:00",
            observed_at="2026-09-01T09:00:00+08:00",
            evidence_source="测试证据",
        )


def test_non_hit_cannot_carry_occurrence_time() -> None:
    record = _record()

    with pytest.raises(LiuYaoError, match="只有 hit 结算可以填写"):
        settle_prediction(
            record,
            "V1",
            outcome="miss",
            occurred_at="2026-12-31T23:00:00+08:00",
            observed_at="2027-01-01T09:00:00+08:00",
            evidence_source="测试证据",
        )


def test_cli_preserves_explicit_occurrence_time(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record_path = tmp_path / "record.json"
    record_path.write_text(json.dumps(_record().to_dict(), ensure_ascii=False), encoding="utf-8")

    assert main(
        [
            "settle",
            "--record",
            str(record_path),
            "--version-id",
            "V1",
            "--outcome",
            "hit",
            "--occurred-at",
            "2026-12-31T23:00:00+08:00",
            "--observed-at",
            "2027-01-02T09:00:00+08:00",
            "--source",
            "正式记录",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["settlement"]["occurred_at"] == "2026-12-31T23:00:00+08:00"
