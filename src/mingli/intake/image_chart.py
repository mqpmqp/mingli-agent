"""Safe image-chart intake: parse untrusted extracted text, then require confirmation.

This module deliberately has no OCR or image-reading dependency.  A caller may
pass text produced by an approved provider, but that text is never Runtime input
until an explicit confirmation or correction has been processed here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Literal, Mapping

from ..derived.static_engine import SEXAGENARY


GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
HEAVENLY_STEMS = frozenset(GAN)
VALID_GANZHI = frozenset(SEXAGENARY)
_PAIR = rf"([{GAN}][{ZHI}])"
_LABELS = {
    "year": ("年柱", "年"),
    "month": ("月柱", "月"),
    "day": ("日柱", "日"),
    "hour": ("时柱", "時柱", "时", "時"),
}
_DAY_MASTER = ("日主", "日元")
_CONFIRMATIONS = frozenset({"确认", "確認", "confirm", "confirmed"})
_GENDERS = {
    "男": "male",
    "男命": "male",
    "元男": "male",
    "乾造": "male",
    "male": "male",
    "女": "female",
    "女命": "female",
    "元女": "female",
    "坤造": "female",
    "female": "female",
}


@dataclass(frozen=True)
class ImageChartIntakeRequest:
    source: Literal["telegram", "api", "test"]
    image_ref: str | None = None
    ocr_text: str | None = None
    theme: str | None = None
    reality_context: Mapping[str, object] | None = None
    provider_result: object | None = None


@dataclass(frozen=True)
class ImageChartCandidate:
    pillars: Mapping[str, str]
    day_master: str | None
    gender: str | None
    birth_datetime: str | None
    birth_place: str | None
    calendar_type: str | None
    confidence: str
    evidence: tuple[str, ...]
    warnings: tuple[str, ...]
    requires_confirmation: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def display_lines(self) -> tuple[str, ...]:
        lines: list[str] = []
        for short, provider, label in (
            ("year", "year_pillar", "年柱"),
            ("month", "month_pillar", "月柱"),
            ("day", "day_pillar", "日柱"),
            ("hour", "hour_pillar", "时柱"),
        ):
            value = self.pillars.get(provider, self.pillars.get(short))
            if value is not None:
                lines.append(f"{label}：{value}")
        if self.day_master:
            lines.append(f"日主：{self.day_master}")
        if self.gender:
            lines.append("性别：" + ("女" if self.gender == "female" else "男"))
        return tuple(lines)


@dataclass(frozen=True)
class ImageChartIntakeResult:
    status: Literal[
        "candidate_requires_confirmation",
        "confirmed_runtime_ready",
        "provider_missing",
        "low_confidence",
        "not_a_chart",
        "invalid_chart",
    ]
    candidate: ImageChartCandidate | None
    user_message: str
    runtime_request: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def accepted(self) -> bool:
        return (
            self.status == "candidate_requires_confirmation"
            and self.candidate is not None
            and self.candidate.confidence == "high"
            and self.candidate.requires_confirmation is True
        )


def _labelled_pillars(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for field, labels in _LABELS.items():
        for label in labels:
            match = re.search(rf"{re.escape(label)}\s*(?:柱)?\s*(?:是|为|為|:|：)?\s*{_PAIR}", text)
            if match:
                found[field] = match.group(1)
                break
    return found


def _has_invalid_labelled_pillar(text: str) -> bool:
    for labels in _LABELS.values():
        for label in labels:
            match = re.search(
                rf"{re.escape(label)}\s*(?:柱)?\s*(?:是|为|為|:|：)?\s*([^\s，,。；;]+)",
                text,
            )
            if match:
                value = match.group(1)
                if re.fullmatch(_PAIR, value) is None or value not in SEXAGENARY:
                    return True
    return False


def _compact_pillars(text: str) -> dict[str, str]:
    pairs = re.findall(_PAIR, text)
    if len(pairs) == 4:
        return dict(zip(("year", "month", "day", "hour"), pairs, strict=True))
    return {}


def _day_master(text: str, day_pillar: str | None) -> str | None:
    for label in _DAY_MASTER:
        match = re.search(rf"{re.escape(label)}\s*(?:是|为|為|:|：)?\s*([{GAN}])(?:木|火|土|金|水)?", text)
        if match:
            return match.group(1)
    return day_pillar[0] if day_pillar else None


def _gender(text: str, previous: str | None = None) -> str | None:
    match = re.search(
        r"(?:性别|性別)\s*(?:是|为|為|:|：)?\s*"
        r"(男命|女命|元男|元女|男|女|male|female|乾造|坤造)",
        text,
        re.IGNORECASE,
    )
    if match:
        return _GENDERS[match.group(1).casefold()]
    for label in ("元男", "元女", "男命", "女命", "乾造", "坤造"):
        if label in text:
            return _GENDERS[label]
    return previous


def _candidate_from_text(text: str, *, previous: ImageChartCandidate | None = None) -> ImageChartCandidate | None:
    labelled = _labelled_pillars(text)
    pillars = dict(previous.pillars) if previous else {}
    pillars.update(labelled or _compact_pillars(text))
    if not pillars:
        return None
    if any(value not in SEXAGENARY for value in pillars.values()):
        return None
    complete = set(pillars) == {"year", "month", "day", "hour"}
    day_master = _day_master(text, pillars.get("day"))
    gender = _gender(text, previous.gender if previous else None)
    if day_master and pillars.get("day") and day_master != pillars["day"][0]:
        return ImageChartCandidate(pillars, day_master, gender, None, None, None, "low", (), ("day_master_conflicts_with_day_pillar",))
    warnings = () if complete else ("four_pillars_incomplete",)
    evidence = tuple(sorted(pillars))
    return ImageChartCandidate(
        pillars=pillars,
        day_master=day_master,
        gender=gender,
        birth_datetime=None,
        birth_place=None,
        calendar_type=None,
        confidence="high" if complete else "low",
        evidence=evidence,
        warnings=warnings,
    )


def _confirmation_message(candidate: ImageChartCandidate) -> str:
    lines = ["我从图片读取到："]
    lines.extend(candidate.display_lines())
    if not candidate.gender:
        lines.append("性别：图片未可靠识别，确认四柱后只需补充男/女。")
    lines.append("请确认四柱、日主和性别是否正确。回复“确认”后直接分析；如有错误，请直接更正。")
    return "\n".join(lines)


def _json_mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"\A```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\Z", "", text, count=1)
    try:
        decoded = json.loads(text)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, Mapping) else None


_PROVIDER_REQUIRED_FIELDS = (
    "year_pillar",
    "month_pillar",
    "day_pillar",
    "hour_pillar",
    "day_master",
)


def _provider_candidates(provider_result: object) -> tuple[Mapping[str, object], bool] | None:
    """Return one supported candidate object and whether strict metadata is required."""
    root = _json_mapping(provider_result)
    if root is None or root.get("success") is False:
        return None

    candidates = root.get("candidates")
    if isinstance(candidates, Mapping):
        return (candidates, True) if root.get("success") is True else None

    if any(field in root for field in _PROVIDER_REQUIRED_FIELDS):
        return root, False

    if root.get("success") is not True:
        return None

    child: Mapping[str, object] | None = None
    for key in ("analysis", "output_text", "content"):
        if key in root:
            child = _json_mapping(root.get(key))
            break
    if child is None:
        message = root.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        if (
            isinstance(content, list)
            and len(content) == 1
            and isinstance(content[0], Mapping)
        ):
            child = _json_mapping(content[0].get("text"))
    if child is None or child.get("success") is False:
        return None

    candidates = child.get("candidates")
    if isinstance(candidates, Mapping):
        return candidates, True
    if any(field in child for field in _PROVIDER_REQUIRED_FIELDS):
        return child, False
    return None


def _provider_field(
    candidates: Mapping[str, object],
    name: str,
    *,
    strict_metadata: bool,
) -> str | None:
    raw = candidates.get(name)
    if not isinstance(raw, Mapping):
        return None
    value = raw.get("value")
    if not isinstance(value, str) or not value.strip():
        return None
    if strict_metadata and not {
        "confidence",
        "source",
        "warning",
    }.issubset(raw):
        return None
    if raw.get("confidence", "high") != "high":
        return None
    if raw.get("source", "visible") != "visible":
        return None
    if raw.get("warning", "") not in ("", None):
        return None
    return value.strip()


def _candidate_from_provider(provider_result: object) -> ImageChartCandidate | None:
    normalized = _provider_candidates(provider_result)
    if normalized is None:
        return None
    candidates, strict_metadata = normalized
    values = {
        name: _provider_field(
            candidates,
            name,
            strict_metadata=strict_metadata,
        )
        for name in _PROVIDER_REQUIRED_FIELDS
    }
    if any(value is None for value in values.values()):
        return None

    pillars = {
        name: values[name]
        for name in (
            "year_pillar",
            "month_pillar",
            "day_pillar",
            "hour_pillar",
        )
    }
    if any(value not in VALID_GANZHI for value in pillars.values()):
        return None
    day_master = values["day_master"]
    if day_master not in HEAVENLY_STEMS or day_master != pillars["day_pillar"][0]:
        return None

    gender = None
    if "gender" in candidates:
        raw_gender = _provider_field(
            candidates,
            "gender",
            strict_metadata=strict_metadata,
        )
        if raw_gender is None or raw_gender.casefold() not in _GENDERS:
            return None
        gender = _GENDERS[raw_gender.casefold()]

    return ImageChartCandidate(
        pillars=pillars,
        day_master=day_master,
        gender=gender,
        birth_datetime=None,
        birth_place=None,
        calendar_type=None,
        confidence="high",
        evidence=tuple(pillars) + ("day_master",),
        warnings=(),
    )


def intake_image_chart(request: ImageChartIntakeRequest) -> ImageChartIntakeResult:
    """Create an untrusted candidate from extracted text without calling Runtime."""
    if isinstance(request.ocr_text, str) and request.ocr_text.strip():
        candidate = _candidate_from_text(request.ocr_text)
    elif request.provider_result is not None:
        candidate = _candidate_from_provider(request.provider_result)
        if candidate is None:
            return ImageChartIntakeResult(
                "low_confidence",
                None,
                "图片命盘信息不完整、置信度不足或存在冲突，请提供更清晰的命盘。",
            )
    else:
        return ImageChartIntakeResult(
            "provider_missing", None,
            "图片命盘识别暂不可用。请手动输入四柱或完整出生资料；如果是从图片读出的四柱，请先确认：请确认我读的四柱和日主是否正确？",
        )
    if candidate is None:
        return ImageChartIntakeResult("not_a_chart", None, "未能从图片文本识别出有效四柱，请手动输入或提供更清晰的命盘。")
    if candidate.confidence == "low":
        return ImageChartIntakeResult("low_confidence", candidate, "图片命盘信息不完整或存在冲突，请更正后再确认。")
    return ImageChartIntakeResult("candidate_requires_confirmation", candidate, _confirmation_message(candidate))


def _runtime_handoff(candidate: ImageChartCandidate, reality_context: Mapping[str, object] | None) -> dict[str, object]:
    """Return a handoff for the confirmed-pillar Runtime, not Phase 23."""
    return {
        "contract": "mingli-image-chart-confirmation@1.2",
        "confirmation_status": "confirmed",
        "chart_candidate": candidate.to_dict(),
        "reality_context": dict(reality_context or {}),
        "runtime_dispatch": "confirmed_pillars",
    }


def confirm_image_chart_candidate(
    candidate: ImageChartCandidate,
    reply: str,
    *,
    reality_context: Mapping[str, object] | None = None,
) -> ImageChartIntakeResult:
    """Confirm or correct a candidate.  No Runtime code is invoked here."""
    normalized = reply.strip().casefold()
    if normalized in _CONFIRMATIONS:
        if candidate.confidence != "high" or candidate.requires_confirmation is not True:
            return ImageChartIntakeResult("low_confidence", candidate, "四柱信息仍不完整，不能进入后续流程。")
        confirmed = ImageChartCandidate(**{**candidate.to_dict(), "requires_confirmation": False})
        return ImageChartIntakeResult(
            "confirmed_runtime_ready", confirmed, "已确认图片四柱；可直接调用 MingLi confirmed-pillar Runtime。",
            _runtime_handoff(confirmed, reality_context),
        )
    if _has_invalid_labelled_pillar(reply):
        return ImageChartIntakeResult(
            "invalid_chart",
            candidate,
            "更正包含非法干支，未更新候选命盘。请核对后重新输入。",
        )
    corrected = _candidate_from_text(reply, previous=candidate)
    if corrected is None or corrected.confidence != "high":
        return ImageChartIntakeResult("invalid_chart", candidate, "未识别出有效更正。请按“日柱是乙亥”这类格式提供更正。")
    return ImageChartIntakeResult("candidate_requires_confirmation", corrected, _confirmation_message(corrected))
