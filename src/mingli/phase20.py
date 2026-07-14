from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal, Mapping, Sequence

from .contracts.serialization import canonical_json, digest

PHASE20_SCHEMA_VERSION = "yuan-eight-section-render@0.2"
PHASE20_METHOD_ID = "yuan-controlled-template-renderer@0.2.0"
PHASE20_CALCULATION_VERSION = "0.2.0"
PHASE20_DECISION_ID = "PHASE_20_YUAN_EIGHT_SECTION_RENDERER_R2_APPROVED"
DISCLAIMER = "仅供文化研究与娱乐参考。"
SECTION_TITLES = ("资料确认", "称骨歌诀", "结论", "事业", "财运", "感情", "五年断事", "建议")
FORBIDDEN_PROMISES = ("一定发生", "必然发生", "保证上岸", "稳赚", "必复合", "百分之百")
LEVEL_TEXT = {
    "supportive": "当前结构呈支持倾向，但仍需结合现实条件验证。",
    "mixed": "当前结构有利弊并存，结论保持条件化。",
    "challenging": "当前结构提示阻力偏多，宜先处理可验证的现实约束。",
    "unresolved": "现有证据不足或互相冲突，暂不下定论。",
}
CONFIDENCE_TEXT = {"high": "高", "medium": "中", "low": "低"}


class Phase20InputError(ValueError):
    pass


@dataclass(frozen=True)
class RenderedSection:
    index: int
    title: str
    content: str


@dataclass(frozen=True)
class YuanRenderResult:
    sections: tuple[RenderedSection, ...]
    rendered_text: str
    source_hashes: Mapping[str, str]
    warnings: tuple[str, ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE20_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE20_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE20_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return json.loads(canonical_json(asdict(self)))


def _status(value: object) -> str:
    key = str(value or "unresolved")
    if key not in LEVEL_TEXT:
        raise Phase20InputError(f"unsupported controlled status: {key}")
    return key


def _source_hash(value: object) -> str:
    if isinstance(value, Mapping) and isinstance(value.get("canonical_hash"), str):
        return str(value["canonical_hash"])
    return digest({"record_type": "RendererSource", "payload": value})


def _aggregate_status(statuses: Sequence[str]) -> str:
    values = set(statuses)
    if "unresolved" in values:
        return "unresolved"
    if len(values) == 1:
        return next(iter(values))
    return "mixed"


def _confidence(value: object) -> str:
    key = str(value or "")
    if key not in CONFIDENCE_TEXT:
        raise Phase20InputError(f"unsupported confidence: {key}")
    return key


def render_yuan_eight_sections(raw: Mapping[str, object]) -> YuanRenderResult:
    if not isinstance(raw, Mapping):
        raise Phase20InputError("renderer input must be an object")
    profile = raw.get("profile")
    chenggu = raw.get("chenggu")
    domains = raw.get("domains")
    domain_confidence = raw.get("domain_confidence")
    five_years = raw.get("five_years")
    if not isinstance(profile, Mapping) or not isinstance(chenggu, Mapping) or not isinstance(domains, Mapping) or not isinstance(domain_confidence, Mapping) or not isinstance(five_years, Sequence) or isinstance(five_years, (str, bytes)):
        raise Phase20InputError("profile, chenggu, domains, domain_confidence and five_years are required structured values")
    birth_date = str(profile.get("birth_date", "未提供"))
    birth_time = str(profile.get("birth_time", "未提供"))
    calendar = str(profile.get("calendar", "未提供"))
    weight = str(chenggu.get("display_weight", "未计算"))
    if chenggu.get("verse_available") is not False or "verified_verse" in chenggu:
        raise Phase20InputError("RC2 core renderer requires verse_available=false and rejects verse text")
    if "overall_status" in raw:
        raise Phase20InputError("overall_status is derived from upstream domain statuses and cannot be supplied")
    career = _status(domains.get("career"))
    wealth = _status(domains.get("wealth"))
    relationship = _status(domains.get("relationship"))
    career_confidence = _confidence(domain_confidence.get("career"))
    wealth_confidence = _confidence(domain_confidence.get("wealth"))
    relationship_confidence = _confidence(domain_confidence.get("relationship"))
    for status, confidence in (
        (career, career_confidence),
        (wealth, wealth_confidence),
        (relationship, relationship_confidence),
    ):
        if status == "unresolved" and confidence != "low":
            raise Phase20InputError("unresolved domain status requires low confidence")
    overall = _aggregate_status((career, wealth, relationship))
    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    overall_confidence = min(
        (career_confidence, wealth_confidence, relationship_confidence),
        key=confidence_rank.__getitem__,
    )
    year_lines: list[str] = []
    years: set[int] = set()
    for item in five_years:
        if not isinstance(item, Mapping) or isinstance(item.get("year"), bool) or not isinstance(item.get("year"), int):
            raise Phase20InputError("each five_year item requires integer year")
        year = int(item["year"])
        if year in years:
            raise Phase20InputError(f"duplicate five_year year: {year}")
        years.add(year)
        year_status = _status(item.get("status"))
        year_confidence = _confidence(item.get("confidence"))
        if year_status == "unresolved" and year_confidence != "low":
            raise Phase20InputError("unresolved five_year status requires low confidence")
        year_lines.append(f"{year}：{LEVEL_TEXT[year_status]} 置信度：{CONFIDENCE_TEXT[year_confidence]}。")
    if len(year_lines) != 5:
        raise Phase20InputError("five_years must contain exactly five records")
    if sorted(years) != list(range(min(years), min(years) + 5)):
        raise Phase20InputError("five_years must be five consecutive years")
    advice_codes = raw.get("advice_codes", [])
    if not isinstance(advice_codes, Sequence) or isinstance(advice_codes, (str, bytes)):
        raise Phase20InputError("advice_codes must be an array")
    advice_map = {
        "verify_reality": "先核对现实事实与目标约束，再调整判断。",
        "build_plan": "把目标拆成可执行、可复盘的小步骤。",
        "risk_buffer": "为时间、现金流和情绪波动预留缓冲。",
        "seek_professional_help": "涉及高风险决定时，咨询相应持证专业人士。",
    }
    advice = [advice_map[str(code)] for code in advice_codes if str(code) in advice_map]
    if not advice:
        advice = [advice_map["verify_reality"], advice_map["build_plan"]]
    section_contents = (
        f"历法：{calendar}；出生日期：{birth_date}；出生时间：{birth_time}。资料如有误，应先更正后重算。",
        f"骨重：{weight}。当前版本仅完成可靠骨重计算；完整歌诀不属于核心包，暂不补写。",
        LEVEL_TEXT[overall] + f" 置信度：{CONFIDENCE_TEXT[overall_confidence]}。",
        LEVEL_TEXT[career] + f" 置信度：{CONFIDENCE_TEXT[career_confidence]}。",
        LEVEL_TEXT[wealth] + f" 置信度：{CONFIDENCE_TEXT[wealth_confidence]}。 不据此提供收益承诺或具体投资指令。",
        LEVEL_TEXT[relationship] + f" 置信度：{CONFIDENCE_TEXT[relationship_confidence]}。 不替代双方意愿、沟通和现实关系状态。",
        "\n".join(year_lines),
        " ".join(advice) + "\n" + DISCLAIMER,
    )
    rendered = "\n\n".join(f"{index}. {title}\n{content}" for index, (title, content) in enumerate(zip(SECTION_TITLES, section_contents), 1))
    if rendered.count(DISCLAIMER) != 1 or not rendered.endswith(DISCLAIMER):
        raise AssertionError("disclaimer invariant violated")
    if any(token in rendered for token in FORBIDDEN_PROMISES):
        raise Phase20InputError("rendered output contains a forbidden guarantee")
    sections = tuple(RenderedSection(i, title, section_contents[i - 1]) for i, title in enumerate(SECTION_TITLES, 1))
    source_hashes = {name: _source_hash(raw[name]) for name in ("profile", "chenggu", "domains", "domain_confidence", "five_years")}
    body = {"sections": [asdict(item) for item in sections], "rendered_text": rendered, "source_hashes": source_hashes, "warnings": ["controlled_template_only", "traditional_culture_not_decision_advice"]}
    return YuanRenderResult(sections, rendered, source_hashes, tuple(body["warnings"]), digest({"record_type": "YuanRenderResult", "payload": body}))


def benchmark_phase20() -> dict[str, object]:
    payload = {"profile": {"calendar": "solar", "birth_date": "1990-03-15", "birth_time": "10:30"}, "chenggu": {"display_weight": "3两7钱", "verse_available": False}, "domains": {"career": "mixed", "wealth": "challenging", "relationship": "unresolved"}, "domain_confidence": {"career": "medium", "wealth": "medium", "relationship": "low"}, "five_years": [{"year": year, "status": "mixed" if year % 2 else "supportive", "confidence": "low"} for year in range(2026, 2031)], "advice_codes": ["verify_reality", "risk_buffer"]}
    result = render_yuan_eight_sections(payload)
    checks = [(len(result.sections) == 8, "section_count"), (tuple(x.title for x in result.sections) == SECTION_TITLES, "section_order"), (result.rendered_text.count(DISCLAIMER) == 1, "disclaimer_once"), (result.rendered_text.endswith(DISCLAIMER), "disclaimer_at_end"), ("暂不补写" in result.sections[1].content, "verse_boundary"), (result.canonical_hash == render_yuan_eight_sections(json.loads(json.dumps(payload))).canonical_hash, "determinism"), (result.prediction_validity == "not_evaluated", "prediction_boundary")]
    failures = [name for ok, name in checks if not ok]
    return {"assertions_total": len(checks), "passed": len(checks) - len(failures), "failed": len(failures), "unresolved": 0, "failures": failures}
