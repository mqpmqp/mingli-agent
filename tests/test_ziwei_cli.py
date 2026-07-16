from __future__ import annotations

import json
import io
import sys

from mingli.cli import main


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
    assert output["calculation_status"] == "partial"
    assert len(output["palaces"]) == 12
    assert "primary_stars" in output["unsupported_fields"]


def test_ziwei_coverage_cli_reports_no_go_without_rules(capsys) -> None:
    assert main(["ziwei", "coverage"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["star_palace_implemented"] == 0
    assert output["release_gate"] == "NO-GO"
