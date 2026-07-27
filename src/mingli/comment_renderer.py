from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from jsonschema import Draft202012Validator

from .contracts import get_schema
from .contracts.serialization import digest


COMMENT_REQUEST_SCHEMA_VERSION = "comment-render-request@1.0"
COMMENT_RESULT_SCHEMA_VERSION = "comment-render-result@1.0"
COMMENT_METHOD_ID = "bounded-high-confidence-comment-renderer@1.0.0"
COMMENT_CALCULATION_VERSION = "1.0.0"
COMMENT_DISCLAIMER = "仅供文化研究与娱乐参考。"
_FORBIDDEN_TEXT = (
    "一定", "必然", "注定", "百分之百", "保证上岸", "必复合", "稳赚", "必发财", "必离婚",
    "生死断言", "医疗诊断", "投资收益承诺", "微信", "手机", "二维码", "收款", "付款", "加V", "加v",
)
_YUAN_EIGHT_SECTION = (
    "1. 资料确认", "2. 称骨歌诀", "3. 结论", "4. 事业",
    "5. 财运", "6. 感情", "7. 五年断事", "8. 建议",
)


class CommentRenderInputError(ValueError):
    pass


@dataclass(frozen=True)
class CommentRenderResult:
    schema_version: str
    method_id: str
    calculation_version: str
    output_mode: Literal["comment"]
    status: Literal["ready", "needs_chart_confirmation", "insufficient_high_confidence"]
    max_characters: int
    rendered_text: str
    character_count: int
    selected_claim_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    canonical_hash: str
    prediction_validity: Literal["not_evaluated"] = "not_evaluated"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "method_id": self.method_id,
            "calculation_version": self.calculation_version,
            "output_mode": self.output_mode,
            "status": self.status,
            "max_characters": self.max_characters,
            "rendered_text": self.rendered_text,
            "character_count": self.character_count,
            "selected_claim_ids": list(self.selected_claim_ids),
            "warnings": list(self.warnings),
            "canonical_hash": self.canonical_hash,
            "prediction_validity": self.prediction_validity,
        }


def _validate_request(raw: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise CommentRenderInputError("comment render input must be an object")
    value = dict(raw)
    errors = sorted(
        Draft202012Validator(get_schema("comment_render_request.schema.json")).iter_errors(value),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    if errors:
        raise CommentRenderInputError(f"comment request contract error: {errors[0].message}")
    return value


def _safe_text(text: str) -> str:
    if any(token in text for token in _FORBIDDEN_TEXT):
        raise CommentRenderInputError("comment text contains forbidden content")
    if all(title in text for title in _YUAN_EIGHT_SECTION):
        raise CommentRenderInputError("comment text must not contain Yuan eight-section structure")
    return text


def _within_budget(lines: list[str], maximum: int) -> bool:
    return len("\n".join((*lines, COMMENT_DISCLAIMER))) <= maximum


def _result(
    *,
    status: Literal["ready", "needs_chart_confirmation", "insufficient_high_confidence"],
    maximum: int,
    lines: list[str],
    claim_ids: tuple[str, ...],
    warnings: tuple[str, ...],
    request_hash: str,
) -> CommentRenderResult:
    rendered_text = "\n".join((*lines, COMMENT_DISCLAIMER))
    _safe_text(rendered_text)
    if rendered_text.count(COMMENT_DISCLAIMER) != 1 or rendered_text.splitlines()[-1] != COMMENT_DISCLAIMER:
        raise AssertionError("comment disclaimer invariant violated")
    if len(rendered_text) > maximum:
        raise CommentRenderInputError("comment does not fit the requested character budget")
    body = {
        "schema_version": COMMENT_RESULT_SCHEMA_VERSION,
        "method_id": COMMENT_METHOD_ID,
        "calculation_version": COMMENT_CALCULATION_VERSION,
        "output_mode": "comment",
        "status": status,
        "max_characters": maximum,
        "rendered_text": rendered_text,
        "character_count": len(rendered_text),
        "selected_claim_ids": list(claim_ids),
        "warnings": list(warnings),
        "prediction_validity": "not_evaluated",
    }
    canonical_hash = digest({
        "record_type": "CommentRenderResult",
        "payload": body,
        "comment_request_hash": request_hash,
    })
    result = CommentRenderResult(canonical_hash=canonical_hash, **body)
    Draft202012Validator(get_schema("comment_render_result.schema.json")).validate(result.to_dict())
    return result


def render_comment(raw: Mapping[str, object]) -> CommentRenderResult:
    request = _validate_request(raw)
    request_hash = digest({"record_type": "CommentRenderRequest", "payload": request})
    maximum = int(request["max_characters"])
    confirmation = request["chart_confirmation"]
    assert isinstance(confirmation, Mapping)
    if confirmation["status"] == "unconfirmed":
        summary = str(confirmation["summary"])
        line = f"我读到的是：{summary}。请确认四柱、日主和性别，确认前不作具体判断。"
        return _result(
            status="needs_chart_confirmation",
            maximum=maximum,
            lines=[line],
            claim_ids=(),
            warnings=("chart_confirmation_required",),
            request_hash=request_hash,
        )

    candidates = request["claim_candidates"]
    assert isinstance(candidates, list)
    high = sorted(
        (item for item in candidates if isinstance(item, Mapping) and item["confidence"] == "high"),
        key=lambda item: (-int(item["priority"]), str(item["claim_id"])),
    )
    selected: list[str] = []
    lines: list[str] = []
    for item in high:
        text = _safe_text(str(item["text"]))
        if len(selected) == 2 or not _within_budget([*lines, text], maximum):
            continue
        lines.append(text)
        selected.append(str(item["claim_id"]))
    if not selected:
        return _result(
            status="insufficient_high_confidence",
            maximum=maximum,
            lines=["信息不足或仅有低置信趋势，暂不作具体判断。"],
            claim_ids=(),
            warnings=("high_confidence_claim_required",),
            request_hash=request_hash,
        )
    return _result(
        status="ready",
        maximum=maximum,
        lines=lines,
        claim_ids=tuple(selected),
        warnings=("high_confidence_only", "comment_mode_not_prediction_validation"),
        request_hash=request_hash,
    )
