from __future__ import annotations

import json
from pathlib import Path

import pytest

from mingli.liuyao import (
    EventContract,
    LiuYaoCaseRecord,
    LiuYaoCastInput,
    LiuYaoError,
    LiuYaoInputConflictError,
    PredictionVersion,
    STATIC_TABLE_SHA256,
    activate_prediction,
    append_prediction,
    benchmark_liuyao,
    build_liuyao_chart,
    create_case_record,
    invalidate_prediction,
    register_cast,
    settle_prediction,
)
from mingli.liuyao_cli import main


def _contract(deadline: str = "2026-12-31") -> EventContract:
    return EventContract(
        target_event="进入最终公示名单",
        deadline=deadline,
        success_criteria="官方最终公示名单包含目标人",
        evidence_requirement="官方公示或可核验录用通知",
    )


def _cast(case_id: str = "CASE-1", lines: tuple[int, ...] = (6, 7, 7, 8, 7, 7), **overrides: object) -> LiuYaoCastInput:
    values: dict[str, object] = {
        "case_id": case_id,
        "question": "本批次是否最终录用",
        "line_values": lines,
        "event_contract": _contract(),
        "completed_at": "2026-08-31T21:57:00+08:00",
        "location": "测试地点",
        "casting_mode": "self",
    }
    values.update(overrides)
    return LiuYaoCastInput(**values)  # type: ignore[arg-type]


def _version(version_id: str = "V1", status: str = "pending") -> PredictionVersion:
    return PredictionVersion(
        version_id=version_id,
        created_at="2026-08-31T22:00:00+08:00",
        status=status,
        conclusion="保留机会，等待合同截止后结算",
        confidence="medium",
        published_at="2026-08-31T22:00:00+08:00" if status == "pending" else None,
        probability_range=(50, 65),
        time_windows=("2026-09",),
        conditions=("实际参加该批次",),
        falsifiers=("未报名或资格审核未通过",),
    )


def test_wind_case_has_expected_original_changed_and_najia() -> None:
    chart = build_liuyao_chart(_cast())

    assert chart.original.name == "巽为风"
    assert chart.changed.name == "风天小畜"
    assert chart.moving_lines == (1,)
    assert chart.original.palace == "巽"
    assert chart.original.palace_stage == "本宫"
    assert (chart.original.shi_line, chart.original.ying_line) == (6, 3)
    assert [line.to_dict()["najia"] for line in chart.lines] == ["辛丑", "辛亥", "辛酉", "辛未", "辛巳", "辛卯"]
    assert chart.lines[0].changed_najia_stem + chart.lines[0].changed_najia_branch == "甲子"


def test_benefit_case_has_expected_original_changed_and_palace() -> None:
    chart = build_liuyao_chart(_cast(lines=(7, 8, 8, 6, 7, 7)))

    assert chart.original.name == "风雷益"
    assert chart.changed.name == "天雷无妄"
    assert chart.moving_lines == (4,)
    assert chart.original.palace == "巽"
    assert chart.original.palace_stage == "三世"
    assert (chart.original.shi_line, chart.original.ying_line) == (3, 6)
    assert chart.lines[3].to_dict()["najia"] == "辛未"
    assert chart.lines[3].to_dict()["changed_najia"] == "壬午"


def test_chinese_coin_labels_and_day_context_are_normalized() -> None:
    cast = _cast(
        lines=("三个字", "两字一花", "两字一花", "一字两花", "两字一花", "两字一花"),
        coin_convention="字为阴，花为阳",
        day_ganzhi="丙午日",
        month_branch="申月",
    )
    chart = build_liuyao_chart(cast)

    assert cast.line_values == (6, 7, 7, 8, 7, 7)
    assert cast.day_ganzhi == "丙午"
    assert cast.month_branch == "申"
    assert chart.void_branches == ("寅", "卯")
    assert chart.month_branch == "申"
    assert chart.day_ganzhi == "丙午"
    assert chart.to_dict()["line_values"] == [6, 7, 7, 8, 7, 7]
    assert chart.to_dict()["calendar_context"] == {"month_branch": "申", "day_ganzhi": "丙午"}
    assert chart.lines[0].six_spirit == "朱雀"
    assert chart.lines[-1].six_spirit == "青龙"


def test_invalid_sequence_and_unzoned_time_fail_closed() -> None:
    with pytest.raises(LiuYaoError, match="恰好包含六项"):
        _cast(lines=(6, 7, 7, 8, 7))
    with pytest.raises(LiuYaoError, match="包含时区偏移"):
        _cast(completed_at="2026-08-31T21:57:00")


def test_conflicting_sequence_blocks_same_case_id() -> None:
    record = create_case_record(_cast())

    with pytest.raises(LiuYaoInputConflictError) as raised:
        register_cast(record, _cast(lines=(7, 7, 8, 7, 7, 6)))

    assert raised.value.code == "INPUT_CONFLICT"


def test_contract_change_blocks_same_case_id() -> None:
    record = create_case_record(_cast())

    with pytest.raises(LiuYaoInputConflictError) as raised:
        register_cast(record, _cast(question="另一个问题"))

    assert raised.value.code == "CONTRACT_CONFLICT"


def test_prediction_correction_preserves_invalid_history() -> None:
    record = append_prediction(create_case_record(_cast()), _version("V1"))
    record = invalidate_prediction(record, "V1", reason="纳甲表错误", invalidated_at="2026-09-01T08:00:00+08:00")
    record = append_prediction(record, _version("V2"))

    assert [version.status for version in record.predictions] == ["invalid", "pending"]
    assert record.predictions[0].invalid_reason == "纳甲表错误"
    assert record.current_version_id == "V2"


def test_new_current_version_requires_old_current_to_be_closed() -> None:
    record = append_prediction(create_case_record(_cast()), _version("V1"))

    with pytest.raises(LiuYaoError, match="必须先作废或结算"):
        append_prediction(record, _version("V2"))


def test_miss_cannot_be_settled_before_contract_deadline() -> None:
    record = append_prediction(create_case_record(_cast()), _version())

    with pytest.raises(LiuYaoError) as raised:
        settle_prediction(
            record,
            "V1",
            outcome="miss",
            observed_at="2026-09-01T00:00:00+08:00",
            evidence_source="官方公示",
        )

    assert raised.value.code == "PREMATURE_SETTLEMENT"


def test_hit_settlement_is_append_only_and_round_trips() -> None:
    record = append_prediction(create_case_record(_cast()), _version())
    settled = settle_prediction(
        record,
        "V1",
        outcome="hit",
        observed_at="2026-10-01T00:00:00+08:00",
        evidence_source="官方公示",
        notes=("已核验",),
    )
    payload = settled.to_dict()

    assert settled.predictions[0].status == "settled"
    assert settled.current_version_id is None
    assert settled.settlement is not None
    assert LiuYaoCaseRecord.from_mapping(payload).to_dict() == payload
    with pytest.raises(LiuYaoError, match="已经结算"):
        settle_prediction(
            settled,
            "V1",
            outcome="hit",
            observed_at="2026-10-02T00:00:00+08:00",
            evidence_source="再次提交",
        )


def test_record_tampering_is_detected() -> None:
    payload = create_case_record(_cast()).to_dict()
    payload["chart"]["original"]["name"] = "兑为泽"  # type: ignore[index]

    with pytest.raises(LiuYaoError) as raised:
        LiuYaoCaseRecord.from_mapping(payload)

    assert raised.value.code == "RECORD_TAMPERED"


def test_benchmark_passes() -> None:
    assert benchmark_liuyao()["status"] == "passed"


def test_cli_chart_and_conflict_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cast_path = tmp_path / "cast.json"
    cast_path.write_text(json.dumps(_cast().to_dict(), ensure_ascii=False), encoding="utf-8")

    assert main(["chart", "--input", str(cast_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["original"]["name"] == "巽为风"

    record_path = tmp_path / "record.json"
    record_path.write_text(json.dumps(create_case_record(_cast()).to_dict(), ensure_ascii=False), encoding="utf-8")
    conflict_path = tmp_path / "conflict.json"
    conflict_path.write_text(json.dumps(_cast(lines=(7, 7, 8, 7, 7, 6)).to_dict(), ensure_ascii=False), encoding="utf-8")

    assert main(["register", "--existing", str(record_path), "--input", str(conflict_path)]) == 2
    assert "INPUT_CONFLICT" in capsys.readouterr().err


def test_all_64_static_hexagrams_are_unique_and_classified() -> None:
    names: set[str] = set()
    contract = _contract()
    for mask in range(64):
        values = tuple(7 if mask & (1 << index) else 8 for index in range(6))
        cast = LiuYaoCastInput(
            case_id=f"STATIC-{mask}",
            question="静卦覆盖测试",
            line_values=values,
            event_contract=contract,
            completed_at="2026-08-31T21:57:00+08:00",
            location="测试地点",
        )
        chart = build_liuyao_chart(cast)
        names.add(chart.original.name)
        assert chart.original.palace in {"乾", "兑", "离", "震", "巽", "坎", "艮", "坤"}
        assert 1 <= chart.original.shi_line <= 6
        assert 1 <= chart.original.ying_line <= 6
        assert chart.original.shi_line != chart.original.ying_line
    assert len(names) == 64


def test_each_xun_void_pair_is_deterministic() -> None:
    expected = {
        "甲子": ("戌", "亥"),
        "甲戌": ("申", "酉"),
        "甲申": ("午", "未"),
        "甲午": ("辰", "巳"),
        "甲辰": ("寅", "卯"),
        "甲寅": ("子", "丑"),
    }
    for day_ganzhi, void_branches in expected.items():
        assert build_liuyao_chart(_cast(day_ganzhi=day_ganzhi)).void_branches == void_branches


def test_idempotent_registration_keeps_same_record() -> None:
    record = create_case_record(_cast())
    assert register_cast(record, _cast()) is record


def test_non_current_pending_and_reopen_after_settlement_are_blocked() -> None:
    record = create_case_record(_cast())
    with pytest.raises(LiuYaoError, match="pending 版本必须登记为 current"):
        append_prediction(record, _version(), make_current=False)

    settled = settle_prediction(
        append_prediction(record, _version()),
        "V1",
        outcome="hit",
        observed_at="2026-10-01T00:00:00+08:00",
        evidence_source="官方公示",
    )
    with pytest.raises(LiuYaoError, match="案例已结算"):
        append_prediction(settled, _version("V2"))


def test_event_contract_deadline_cannot_precede_cast_date() -> None:
    with pytest.raises(LiuYaoError, match="deadline 不能早于"):
        _cast(event_contract=_contract("2026-08-30"))


def test_prediction_registration_must_be_after_cast_and_before_deadline() -> None:
    record = create_case_record(_cast())
    early = PredictionVersion(
        version_id="EARLY",
        created_at="2026-08-31T21:56:59+08:00",
        status="pending",
        conclusion="测试",
        confidence="low",
        published_at="2026-08-31T21:56:59+08:00",
    )
    with pytest.raises(LiuYaoError, match="不能早于起卦完成时间"):
        append_prediction(record, early)

    late = PredictionVersion(
        version_id="LATE",
        created_at="2027-01-01T00:00:00+08:00",
        status="pending",
        conclusion="测试",
        confidence="low",
        published_at="2027-01-01T00:00:00+08:00",
    )
    with pytest.raises(LiuYaoError, match="截止日当天或之前"):
        append_prediction(record, late)


def test_invalidation_cannot_predate_version_creation() -> None:
    record = append_prediction(create_case_record(_cast()), _version(status="draft"))
    with pytest.raises(LiuYaoError, match="invalidated_at 不能早于 created_at"):
        invalidate_prediction(
            record,
            "V1",
            reason="测试",
            invalidated_at="2026-08-31T21:59:59+08:00",
        )


def test_invalidation_cannot_predate_publication() -> None:
    published_later = PredictionVersion(
        version_id="V1",
        created_at="2026-08-31T22:00:00+08:00",
        status="pending",
        conclusion="待检验判断",
        confidence="medium",
        published_at="2026-08-31T22:05:00+08:00",
    )
    record = append_prediction(create_case_record(_cast()), published_later)
    with pytest.raises(LiuYaoError, match="invalidated_at 不能早于 published_at"):
        invalidate_prediction(
            record,
            "V1",
            reason="测试",
            invalidated_at="2026-08-31T22:02:00+08:00",
        )


def test_settled_record_cannot_keep_open_prediction() -> None:
    base = create_case_record(_cast())
    pending = _version("V1")
    settled = settle_prediction(
        append_prediction(base, pending),
        "V1",
        outcome="hit",
        observed_at="2026-10-01T00:00:00+08:00",
        evidence_source="官方公示",
    )
    open_draft = _version("V2", status="draft")
    with pytest.raises(LiuYaoError, match="不能保留 current、draft 或 pending"):
        LiuYaoCaseRecord(
            cast=settled.cast,
            chart=settled.chart,
            predictions=settled.predictions + (open_draft,),
            current_version_id="V2",
            settlement=settled.settlement,
        )


def test_settlement_cannot_predate_prediction_registration() -> None:
    record = append_prediction(create_case_record(_cast()), _version())
    with pytest.raises(LiuYaoError, match="不能早于预测版本发布时间"):
        settle_prediction(
            record,
            "V1",
            outcome="hit",
            observed_at="2026-08-31T21:59:59+08:00",
            evidence_source="测试证据",
        )


def test_external_structure_oracle_covers_all_hexagrams_and_najia() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "liuyao_structure_oracle_v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["input_order"] == "bottom_to_top"
    assert fixture["source"]["verification_role"] == "secondary_external_cross_check_not_authority"
    assert len(fixture["hexagrams"]) == 64

    contract = _contract()
    for bits, expected in fixture["hexagrams"].items():
        values = tuple(7 if bit == "1" else 8 for bit in bits)
        chart = build_liuyao_chart(
            LiuYaoCastInput(
                case_id=f"ORACLE-{bits}",
                question="外部结构差分夹具",
                line_values=values,
                event_contract=contract,
                completed_at="2026-08-31T21:57:00+08:00",
                location="测试地点",
            )
        )
        actual = chart.original.to_dict()
        assert actual == expected

    for trigram_index, (trigram, expected) in enumerate(fixture["trigrams"].items()):
        bits = expected["bits"] * 2
        chart = build_liuyao_chart(
            LiuYaoCastInput(
                case_id=f"NAJIA-{trigram_index}",
                question="外部纳甲差分夹具",
                line_values=tuple(7 if bit == "1" else 8 for bit in bits),
                event_contract=contract,
                completed_at="2026-08-31T21:57:00+08:00",
                location="测试地点",
            )
        )
        expected_najia = [
            expected["inner_stem"] + branch for branch in expected["inner_branches"]
        ] + [
            expected["outer_stem"] + branch for branch in expected["outer_branches"]
        ]
        assert [line.to_dict()["najia"] for line in chart.lines] == expected_najia


def test_all_4096_moving_patterns_match_frozen_name_oracle() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "liuyao_structure_oracle_v1.json"
    names = {
        bits: expected["name"]
        for bits, expected in json.loads(fixture_path.read_text(encoding="utf-8"))["hexagrams"].items()
    }
    contract = _contract()
    for pattern in range(4 ** 6):
        remaining = pattern
        values = []
        for _ in range(6):
            values.append(6 + remaining % 4)
            remaining //= 4
        original_bits = "".join("1" if value in (7, 9) else "0" for value in values)
        changed_bits = "".join(
            "1" if value in (6, 7) else "0"
            for value in values
        )
        chart = build_liuyao_chart(
            LiuYaoCastInput(
                case_id=f"PATTERN-{pattern}",
                question="四千零九十六种动爻组合覆盖",
                line_values=tuple(values),
                event_contract=contract,
                completed_at="2026-08-31T21:57:00+08:00",
                location="测试地点",
            )
        )
        assert chart.original.name == names[original_bits]
        assert chart.changed.name == names[changed_bits]
        assert chart.moving_lines == tuple(index for index, value in enumerate(values, start=1) if value in (6, 9))


def test_draft_can_be_frozen_then_published_as_pending() -> None:
    record = append_prediction(create_case_record(_cast()), _version("D1", status="draft"), make_current=False)
    activated = activate_prediction(record, "D1", published_at="2026-09-01T08:00:00+08:00")

    assert activated.current_version_id == "D1"
    assert activated.predictions[0].status == "pending"
    assert activated.predictions[0].published_at == "2026-09-01T08:00:00+08:00"


def test_draft_publication_obeys_current_and_deadline_gates() -> None:
    base = create_case_record(_cast())
    record = append_prediction(base, _version("D1", status="draft"), make_current=False)
    record = append_prediction(record, _version("P1"))
    with pytest.raises(LiuYaoError, match="必须先作废当前版本"):
        activate_prediction(record, "D1", published_at="2026-09-01T08:00:00+08:00")

    closed = invalidate_prediction(record, "P1", reason="切换版本", invalidated_at="2026-09-01T08:01:00+08:00")
    with pytest.raises(LiuYaoError, match="截止日当天或之前发布"):
        activate_prediction(closed, "D1", published_at="2027-01-01T00:00:00+08:00")


def test_settlement_requires_timezone_aware_timestamp() -> None:
    record = append_prediction(create_case_record(_cast()), _version())
    with pytest.raises(LiuYaoError, match="包含时区偏移"):
        settle_prediction(
            record,
            "V1",
            outcome="hit",
            observed_at="2026-10-01",
            evidence_source="官方公示",
        )


def test_static_table_hash_is_frozen() -> None:
    assert STATIC_TABLE_SHA256 == "503d5339505e5ca77db270f5a046591980153c78970f54b756c2f8bb2d54709e"
