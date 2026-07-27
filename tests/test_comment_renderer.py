from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mingli.comment_renderer import (
    COMMENT_DISCLAIMER,
    CommentRenderInputError,
    render_comment,
)
from mingli.contracts import get_schema
from mingli.phase20 import benchmark_phase20
from mingli.phase23 import benchmark_phase23


pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[1]


def request(*, confirmed: bool = True, maximum: int = 80) -> dict[str, object]:
    return {
        "schema_version": "comment-render-request@1.0",
        "output_mode": "comment",
        "max_characters": maximum,
        "require_chart_confirmation": True,
        "confidence_filter": "high_only",
        "include_disclaimer": "compact",
        "chart_confirmation": {
            "status": "confirmed" if confirmed else "unconfirmed",
            "summary": "甲子、乙丑、丙寅、丁卯；日主丙；性别已确认",
        },
        "claim_candidates": [
            {
                "claim_id": "career-high",
                "topic": "career",
                "text": "事业节奏更适合先稳住现有优势，再按现实条件推进。",
                "confidence": "high",
                "priority": 20,
                "source_hash": "sha256:" + "1" * 64,
            },
            {
                "claim_id": "relationship-high",
                "topic": "relationship",
                "text": "感情互动宜重视沟通与边界，不宜急于下结论。",
                "confidence": "high",
                "priority": 10,
                "source_hash": "sha256:" + "2" * 64,
            },
            {
                "claim_id": "wealth-medium",
                "topic": "wealth",
                "text": "财务节奏需要持续观察。",
                "confidence": "medium",
                "priority": 99,
                "source_hash": "sha256:" + "3" * 64,
            },
            {
                "claim_id": "study-low",
                "topic": "study",
                "text": "学习方向仍有不确定性。",
                "confidence": "low",
                "priority": 98,
                "source_hash": "sha256:" + "4" * 64,
            },
        ],
    }


def test_schemas_are_loadable_objects_and_validate_contracts() -> None:
    request_schema = get_schema("comment_render_request.schema.json")
    result_schema = get_schema("comment_render_result.schema.json")
    assert request_schema["type"] == "object"
    assert result_schema["type"] == "object"
    Draft202012Validator.check_schema(request_schema)
    Draft202012Validator.check_schema(result_schema)
    Draft202012Validator(request_schema).validate(request())


@pytest.mark.parametrize("field,value", [
    ("output_mode", "runtime"),
    ("max_characters", 100),
    ("require_chart_confirmation", False),
    ("confidence_filter", "all"),
    ("include_disclaimer", "full"),
])
def test_request_contract_rejects_non_comment_mode_values(field: str, value: object) -> None:
    raw = request()
    raw[field] = value
    with pytest.raises(CommentRenderInputError):
        render_comment(raw)


def test_unconfirmed_chart_fails_closed_without_claims() -> None:
    result = render_comment(request(confirmed=False)).to_dict()
    assert result["status"] == "needs_chart_confirmation"
    assert result["selected_claim_ids"] == []
    assert "事业" not in result["rendered_text"]
    assert result["rendered_text"].count(COMMENT_DISCLAIMER) == 1
    assert result["rendered_text"].endswith(COMMENT_DISCLAIMER)
    assert result["character_count"] == len(result["rendered_text"])
    assert result["character_count"] <= result["max_characters"]


def test_confirmed_comment_uses_only_high_claims_in_stable_priority_order() -> None:
    result = render_comment(request()).to_dict()
    assert result["status"] == "ready"
    assert result["selected_claim_ids"] == ["career-high", "relationship-high"]
    assert "medium" not in result["rendered_text"]
    assert "财务节奏需要持续观察" not in result["rendered_text"]
    assert "学习方向仍有不确定性" not in result["rendered_text"]
    assert result["rendered_text"].count(COMMENT_DISCLAIMER) == 1
    assert result["rendered_text"].endswith(COMMENT_DISCLAIMER)


def test_no_high_confidence_claim_fails_closed() -> None:
    raw = request()
    raw["claim_candidates"] = [
        {**item, "confidence": "medium"}
        for item in raw["claim_candidates"]  # type: ignore[index]
    ]
    result = render_comment(raw).to_dict()
    assert result["status"] == "insufficient_high_confidence"
    assert result["selected_claim_ids"] == []
    assert "具体判断" in result["rendered_text"]


@pytest.mark.parametrize("maximum", [80, 120])
def test_character_budget_includes_single_final_disclaimer(maximum: int) -> None:
    result = render_comment(request(maximum=maximum)).to_dict()
    assert result["max_characters"] == maximum
    assert result["character_count"] == len(result["rendered_text"])
    assert result["character_count"] <= maximum
    assert result["rendered_text"].splitlines()[-1] == COMMENT_DISCLAIMER


@pytest.mark.parametrize("text", [
    "你一定会成功。",
    "保证上岸。",
    "加V联系我。",
    "微信号 abc123。",
    "扫码付款。",
    "1. 资料确认\n2. 称骨歌诀\n3. 结论\n4. 事业\n5. 财运\n6. 感情\n7. 五年断事\n8. 建议",
])
def test_forbidden_content_fails_closed(text: str) -> None:
    raw = request()
    raw["claim_candidates"] = [{
        "claim_id": "bad",
        "topic": "career",
        "text": text,
        "confidence": "high",
        "priority": 1,
        "source_hash": "sha256:" + "5" * 64,
    }]
    with pytest.raises(CommentRenderInputError):
        render_comment(raw)


def test_identical_input_is_deterministic_and_changed_input_changes_hash() -> None:
    raw = request()
    left = render_comment(raw).to_dict()
    right = render_comment(json.loads(json.dumps(raw, ensure_ascii=False))).to_dict()
    assert left["selected_claim_ids"] == right["selected_claim_ids"]
    assert left["rendered_text"] == right["rendered_text"]
    assert left["character_count"] == right["character_count"]
    assert left["canonical_hash"] == right["canonical_hash"]
    changed = request()
    changed["chart_confirmation"] = {"status": "confirmed", "summary": "另一份已确认命盘"}
    assert render_comment(changed).canonical_hash != left["canonical_hash"]


def test_result_schema_and_release_boundary_are_preserved() -> None:
    result = render_comment(request()).to_dict()
    Draft202012Validator(get_schema("comment_render_result.schema.json")).validate(result)
    assert result["output_mode"] == "comment"
    assert result["prediction_validity"] == "not_evaluated"
    assert result["canonical_hash"].startswith("sha256:")


def test_comment_render_cli_json_smoke(tmp_path: Path) -> None:
    input_path = tmp_path / "request.json"
    input_path.write_text(json.dumps(request(), ensure_ascii=False), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-m", "mingli.cli", "comment-render", "--input", str(input_path)],
        cwd=ROOT,
            env={
                "PYTHONPATH": str(ROOT / "src"),
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            },
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    result = json.loads(completed.stdout)
    assert result["status"] == "ready"
    assert result["character_count"] <= 80


def test_phase20_and_phase23_defaults_remain_unchanged() -> None:
    assert benchmark_phase20()["failed"] == 0
    assert benchmark_phase23()["failed"] == 0
