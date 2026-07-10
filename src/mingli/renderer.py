from __future__ import annotations

from collections.abc import Mapping, Sequence

from .errors import ForbiddenPhraseError, ModelValidationError

DISCLAIMER = "仅供文化研究与娱乐参考。"
FORBIDDEN_PHRASES = (
    "必然",
    "一定",
    "注定",
    "百分百",
    "必死",
    "必离婚",
    "必发财",
    "必有第三者",
    "命中无财",
    "家人克你",
    "六法速览",
    "共同结论",
    "分歧与置信度",
    "我用了以下方法",
)

SPECIALIZED_SECTIONS = {
    "career_exam": (
        ("体制适配度", "需结合规则环境偏好与现实经历评估。"),
        ("能否上岸", "上岸取决于专业资格、备考质量与岗位竞争，命理不能保证录取。"),
        ("岗位方向", "先按专业限制、岗位职责与地区竞争筛选。"),
        ("备考策略", "先建立模考基线，再按薄弱项安排复习。"),
    ),
    "relationship_reunion": (
        ("缘分牵引", "象意只能说明关系主题，不能覆盖现实状态。"),
        ("复联可能", "先看双方是否仍有联系及对方边界。"),
        ("复合可能", "复合取决于分手原因能否被现实解决。"),
        ("稳定可能", "稳定取决于长期沟通、信任与可执行方案。"),
    ),
}


def find_forbidden(text: str, extra_phrases: Sequence[str] = ()) -> tuple[str, ...]:
    phrases = tuple(FORBIDDEN_PHRASES) + tuple(extra_phrases)
    return tuple(dict.fromkeys(phrase for phrase in phrases if phrase and phrase in text))


def ensure_safe_text(text: str, extra_phrases: Sequence[str] = ()) -> None:
    hits = find_forbidden(text, extra_phrases)
    if hits:
        raise ForbiddenPhraseError(f"输出含禁词：{', '.join(hits)}")


def _without_disclaimer(text: str) -> str:
    if not isinstance(text, str):
        raise ModelValidationError("渲染内容必须是字符串")
    return text.replace(DISCLAIMER, "").strip()


def render_answer(
    *,
    intent: str,
    conclusion: str,
    confidence: str = "medium",
    chart_confirmed: bool = True,
    terminology: Sequence[tuple[str, str]] = (),
    sections: Mapping[str, str] | None = None,
    advice: Sequence[str] = (),
) -> str:
    """生成确定性中文文本；不会调用模型或排盘器。"""
    if confidence not in {"high", "medium", "low"}:
        raise ModelValidationError("confidence 必须是 high、medium 或 low")

    if not chart_confirmed:
        rendered = (
            "请确认图片中的四柱、日主、性别及可读的大运流年；"
            "确认前只能给出低置信限制说明，不能据此生成精确分析。"
            f"\n\n{DISCLAIMER}"
        )
        ensure_safe_text(rendered)
        return rendered

    clean_conclusion = _without_disclaimer(conclusion)
    if not clean_conclusion:
        raise ModelValidationError("conclusion 不能为空")
    blocks: list[str] = [clean_conclusion]
    confidence_label = {"high": "高", "medium": "中", "low": "低"}[confidence]
    blocks.append(f"置信度：{confidence_label}。")

    if terminology:
        explained: list[str] = []
        for term, plain_language in terminology:
            if not term or not plain_language:
                raise ModelValidationError("术语及白话解释不能为空")
            explained.append(f"{term}（{plain_language}）")
        blocks.append("术语说明：" + "；".join(explained) + "。")

    requested_sections = dict(sections or {})
    for title, default in SPECIALIZED_SECTIONS.get(intent, ()):
        content = _without_disclaimer(requested_sections.pop(title, default))
        blocks.append(f"## {title}\n{content}")
    for title, content in requested_sections.items():
        blocks.append(f"## {title}\n{_without_disclaimer(content)}")

    selected_advice = tuple(advice[:3])
    if selected_advice:
        lines = ["## 建议"]
        lines.extend(f"{index}. {_without_disclaimer(item)}" for index, item in enumerate(selected_advice, 1))
        blocks.append("\n".join(lines))

    body = "\n\n".join(block for block in blocks if block).replace(DISCLAIMER, "").strip()
    rendered = body + f"\n\n{DISCLAIMER}"
    ensure_safe_text(rendered)
    return rendered
