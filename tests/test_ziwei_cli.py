from __future__ import annotations

import json
import io
import sys

from mingli.cli import main
from mingli.ziwei import build_ziwei_chart


def test_ziwei_chart_cli_smoke(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "calendar_type": "solar",
                    "birth_date": "2000-01-07",
                    "birth_time": "12:00",
                    "timezone": "Asia/Shanghai",
                    "longitude": 121.4737,
                    "latitude": 31.2304,
                    "solar_time_mode": "civil",
                    "late_zi_policy": "midnight",
                    "gender": "male",
                }
            )
        ),
    )

    assert main(["ziwei", "chart", "--input", "-"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["calculation_status"] == "complete"
    assert len(output["palaces"]) == 12
    assert output["unsupported_fields"] == []


def test_ziwei_engine_benchmark_cli(capsys) -> None:
    assert main(["ziwei", "benchmark"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["total_cases"] == 5
    assert output["passed_cases"] == 5
    assert output["failed_cases"] == 0


def test_ziwei_coverage_cli_reports_no_go_without_rules(capsys) -> None:
    assert main(["ziwei", "coverage"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["star_palace_implemented"] == 168
    assert output["star_palace_behaviorally_evaluated"] == 168
    assert output["release_gate"] == "REVIEW_REQUIRED"


def test_ziwei_rule_content_validate_and_evaluate_cli(tmp_path, capsys) -> None:
    assert main(["ziwei", "rules-validate"]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["rule_count"] == 184
    assert validated["primary_star_palace_rules"] == 168

    chart_path = tmp_path / "chart.json"
    chart_path.write_text(
        json.dumps(
            build_ziwei_chart(
                {
                    "calendar_type": "solar",
                    "birth_date": "2000-01-07",
                    "birth_time": "12:00",
                    "timezone": "Asia/Shanghai",
                    "longitude": 121.4737,
                    "latitude": 31.2304,
                    "solar_time_mode": "civil",
                    "late_zi_policy": "midnight",
                    "gender": "male",
                }
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert main(["ziwei", "rules-evaluate", "--input", str(chart_path)]) == 0
    evaluated = json.loads(capsys.readouterr().out)
    assert evaluated["algorithm_version"] == "ziwei-traditional-natal@1.0.0"
    assert evaluated["matched_rules"] >= 14
    assert all(item["resolution"] != "suppressed_by_higher_priority" for item in evaluated["effective_matches"])
