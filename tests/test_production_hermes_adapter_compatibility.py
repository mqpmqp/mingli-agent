from __future__ import annotations

from copy import deepcopy
import inspect
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import mingli.phase23 as phase23
from mingli.confirmed_pillar_runtime import (
    render_confirmed_pillar_follow_up,
    run_confirmed_pillar_agent,
)
from mingli.intake.image_chart import ImageChartIntakeRequest, intake_image_chart


def _confirmed_request() -> dict[str, object]:
    return {
        "pillars": {
            "year": "甲子",
            "month": "乙丑",
            "day": "丙寅",
            "hour": "丁卯",
        },
        "day_master": "丙",
        "gender": "female",
        "source": "image_confirmed",
        "confirmation_status": "confirmed",
        "trace_id": "production-hermes-compat-trace",
        "idempotency_key": "production-hermes-compat-key",
    }


def _provider_payload(*, day_master: str = "丙", gender: str | None = "female") -> dict[str, object]:
    payload: dict[str, object] = {
        "year_pillar": {"value": "甲子"},
        "month_pillar": {"value": "乙丑"},
        "day_pillar": {"value": "丙寅"},
        "hour_pillar": {"value": "丁卯"},
        "day_master": {"value": day_master},
    }
    if gender is not None:
        payload["gender"] = {"value": gender}
    return payload


def test_confirmed_pillar_follow_up_public_contract_stays_focused() -> None:
    """PRODUCTION_HERMES_ADAPTER_COMPATIBILITY_TEST core public contract."""

    assert tuple(inspect.signature(render_confirmed_pillar_follow_up).parameters) == (
        "completed_result",
        "question",
    )
    completed_result = run_confirmed_pillar_agent(_confirmed_request()).to_dict()
    original = deepcopy(completed_result)

    with patch.object(
        phase23,
        "render_yuan_eight_sections",
        wraps=phase23.render_yuan_eight_sections,
    ) as yuan:
        follow_up = render_confirmed_pillar_follow_up(
            completed_result, "她的事业怎么样？"
        ).to_dict()

    assert completed_result == original
    assert follow_up["source"] == "image_confirmed_follow_up"
    assert follow_up["chart"] == completed_result["chart"]
    assert "事业" in follow_up["final_answer"]
    assert yuan.call_count == 0


def test_image_intake_trace_and_missing_gender_contract_match_live_hermes() -> None:
    rejected_events: list[tuple[str, dict[str, object]]] = []

    def collect_rejected(
        trace_id: str | None,
        event: str,
        details: dict[str, object],
        **_source: object,
    ) -> bool:
        assert trace_id == "production-hermes-rejected"
        rejected_events.append((event, details))
        return True

    rejected = intake_image_chart(
        ImageChartIntakeRequest(
            source="telegram",
            provider_result=_provider_payload(day_master="甲"),
            trace_id="production-hermes-rejected",
            trace_writer=collect_rejected,
        )
    )

    assert rejected.status == "low_confidence"
    assert rejected.user_message.endswith("【IMGTRACE2】")
    assert [event for event, _ in rejected_events] == [
        "parser_result",
        "validator_result",
        "final_rejection",
    ]
    assert rejected_events[1][1]["day_master_matches_day_stem"] is False

    accepted_events: list[str] = []

    def collect_accepted(
        _trace_id: str | None,
        event: str,
        _details: dict[str, object],
        **_source: object,
    ) -> bool:
        accepted_events.append(event)
        return True

    accepted = intake_image_chart(
        ImageChartIntakeRequest(
            source="telegram",
            provider_result=_provider_payload(gender=None),
            trace_id="production-hermes-accepted",
            trace_writer=collect_accepted,
        )
    )

    assert accepted.accepted is True
    assert accepted.user_message == (
        "四柱已识别为甲子、乙丑、丙寅、丁卯，日主丙火。"
        "图片中未可靠识别性别，请回复男或女。"
    )
    assert accepted_events == ["parser_result", "validator_result"]


def test_production_hermes_adapter_compatibility() -> None:
    """Run the actual release Adapter against this candidate when explicitly bound."""

    adapter_root = os.environ.get("MINGLI_PRODUCTION_HERMES_ADAPTER_ROOT")
    if not adapter_root:
        pytest.skip("MINGLI_PRODUCTION_HERMES_ADAPTER_ROOT is required for the real Adapter probe")
    root = Path(adapter_root).resolve()
    if not (root / "mingli_console" / "console.py").is_file():
        pytest.fail("MINGLI_PRODUCTION_HERMES_ADAPTER_ROOT has no live mingli_console adapter")
    sys.path.insert(0, str(root))

    from mingli_console.console import MingLiRuntimeAdapter

    candidate_root = Path(__file__).resolve().parents[1]
    expected_sha = subprocess.run(
        ["git", "-C", str(candidate_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    adapter = MingLiRuntimeAdapter(repo=str(candidate_root), expected_sha=expected_sha)

    adapter._prepare()
    completed_result = run_confirmed_pillar_agent(_confirmed_request()).to_dict()
    result = adapter.confirmed_pillar_follow_up(
        {
            "source": "image_confirmed_follow_up",
            "question": "她的事业怎么样？",
            "candidate": {
                "year_pillar": "甲子",
                "month_pillar": "乙丑",
                "day_pillar": "丙寅",
                "hour_pillar": "丁卯",
                "day_master": "丙",
                "gender": "female",
            },
            "runtime_result": completed_result,
        }
    )

    assert result["chart"] == completed_result["chart"]
    assert result["final_answer"]
    assert "事业" in result["final_answer"]
