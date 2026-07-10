from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .errors import ForbiddenPhraseError
from .reality import apply_reality_overrides
from .renderer import DISCLAIMER, ensure_safe_text, render_answer


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    total: int
    passed: int
    practical_total: int
    practical_passed: int
    failures: tuple[str, ...]


def _read_jsonl(path: Path, failures: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        failures.append(f"{path}: 无法读取：{exc}")
        return records
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append(f"{path.name}:{line_no}: JSONL 解析失败（列 {exc.colno}）：{exc.msg}")
            continue
        if not isinstance(value, dict):
            failures.append(f"{path.name}:{line_no}: 案例必须是 JSON 对象")
            continue
        value["__line__"] = line_no
        records.append(value)
    return records


def _string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def _forbidden_guard_works(phrases: Sequence[str]) -> bool:
    for phrase in phrases:
        try:
            ensure_safe_text(phrase, phrases)
        except ForbiddenPhraseError:
            continue
        return False
    return True


def _requires_reality_override(intent: str, facts: Mapping[str, object], signals: Sequence[str]) -> bool:
    joined = " ".join(signals)
    if facts.get("relationship_status") == "married" and "桃花" in joined:
        return True
    no_contact_duration = facts.get("no_contact_months", facts.get("no_contact_duration_months", 0))
    if intent == "relationship_reunion" and (
        facts.get("other_party_status") == "married"
        or facts.get("contact_status") == "blocked"
        or (
            facts.get("contact_status") == "no_contact"
            and isinstance(no_contact_duration, (int, float))
            and no_contact_duration >= 12
        )
    ):
        return True
    if facts.get("career_status") == "unemployed":
        return True
    if intent == "career_exam" and facts.get("major_eligible") is False:
        return True
    if intent == "startup" and (
        facts.get("capital_level") == "low"
        or (isinstance(facts.get("cash_runway_months"), (int, float)) and facts["cash_runway_months"] <= 2)
    ) and facts.get("customer_validation") is not True:
        return True
    symptoms = facts.get("symptoms", facts.get("symptom"))
    if intent == "health" and (
        symptoms in {"持续胸痛", "persistent_chest_pain", "high_fever", "difficulty_breathing"}
        if isinstance(symptoms, str)
        else isinstance(symptoms, list)
        and any(item in {"持续胸痛", "persistent_chest_pain", "high_fever", "difficulty_breathing"} for item in symptoms)
    ):
        return True
    return intent in {"investment", "wealth"} and (
        facts.get("contract_leverage") is True or facts.get("financial_risk") == "high"
    )


def _check_common_case(case: dict[str, Any], *, practical: bool, failures: list[str]) -> None:
    case_id = case.get("id", f"line-{case.get('__line__', '?')}")
    if not isinstance(case_id, str) or not case_id:
        failures.append(f"案例行 {case.get('__line__', '?')}: 缺少有效 id")
        return
    facts_key = "facts" if practical else "reality"
    facts = case.get(facts_key, {})
    if not isinstance(facts, dict):
        failures.append(f"{case_id}: {facts_key} 必须是对象")
        facts = {}
    forbidden_key = "must_not" if practical else "forbidden"
    forbidden = case.get(forbidden_key)
    if not _string_list(forbidden):
        failures.append(f"{case_id}: {forbidden_key} 必须是非空字符串数组")
        forbidden = []
    elif not _forbidden_guard_works(forbidden):
        failures.append(f"{case_id}: 禁止结论扫描未生效")

    intent = case.get("category" if practical else "intent")
    if not isinstance(intent, str) or not intent:
        failures.append(f"{case_id}: 缺少意图或类别")
        return
    signals = case.get("chart_signals", [])
    if not isinstance(signals, list):
        failures.append(f"{case_id}: chart_signals 必须是数组")
        signals = []
    overrides = apply_reality_overrides(intent, facts, signals)
    if _requires_reality_override(intent, facts, signals) and not overrides:
        failures.append(f"{case_id}: 应触发现实校正但未触发")

    render_intent = intent
    if practical and intent == "image_chart":
        render_intent = "full_bazi"
    chart_confirmed = not (
        (not practical and case.get("input_type") == "image")
        or (practical and intent == "image_chart")
    )
    confidence = case.get("target_confidence", "medium") if practical else "medium"
    if confidence == "mixed":
        confidence = "medium"
    if confidence not in {"high", "medium", "low"}:
        failures.append(f"{case_id}: target_confidence 无效")
        confidence = "low"
    rendered = render_answer(
        intent=render_intent,
        conclusion="先按现实条件进行确定性策略校验。",
        confidence=confidence,
        chart_confirmed=chart_confirmed,
    )
    if rendered.count(DISCLAIMER) != 1 or not rendered.endswith(DISCLAIMER):
        failures.append(f"{case_id}: 免责声明不是末行唯一一次")
    required_sections = {
        "career_exam": ("体制适配度", "能否上岸", "岗位方向", "备考策略"),
        "relationship_reunion": ("缘分牵引", "复联可能", "复合可能", "稳定可能"),
    }.get(intent, ())
    missing_sections = [section for section in required_sections if section not in rendered]
    if missing_sections:
        failures.append(f"{case_id}: 缺少章节 {', '.join(missing_sections)}")
    if practical and not _string_list(case.get("must_include")):
        failures.append(f"{case_id}: must_include 必须是非空字符串数组")
    if practical and not _string_list(case.get("target_outline")):
        failures.append(f"{case_id}: target_outline 必须是非空字符串数组")
    if not practical and not _string_list(case.get("expected")):
        failures.append(f"{case_id}: expected 必须是非空字符串数组")


def benchmark_static(path: str | Path) -> BenchmarkResult:
    """校验确定性策略合同；结果不表示模型或命理预测准确率。"""
    golden_path = Path(path).resolve()
    failures: list[str] = []
    golden = _read_jsonl(golden_path, failures)
    if golden_path.name == "golden_cases_v0.2.jsonl" and len(golden) != 40:
        failures.append(f"黄金案例数量应为 40，实际为 {len(golden)}")
    seen: set[str] = set()
    failed_golden: set[str] = set()
    for case in golden:
        case_id = case.get("id")
        before = len(failures)
        if isinstance(case_id, str):
            if case_id in seen:
                failures.append(f"{case_id}: 重复案例 ID")
            seen.add(case_id)
        _check_common_case(case, practical=False, failures=failures)
        if len(failures) > before:
            failed_golden.add(str(case_id))

    practical_path = golden_path.parent / "practical_blind_test" / "practical_cases.jsonl"
    practical: list[dict[str, Any]] = []
    failed_practical: set[str] = set()
    if practical_path.is_file():
        practical = _read_jsonl(practical_path, failures)
        if len(practical) != 24:
            failures.append(f"实战案例数量应为 24，实际为 {len(practical)}")
        practical_seen: set[str] = set()
        for case in practical:
            case_id = case.get("id")
            before = len(failures)
            if isinstance(case_id, str):
                if case_id in practical_seen:
                    failures.append(f"{case_id}: 重复实战案例 ID")
                practical_seen.add(case_id)
            _check_common_case(case, practical=True, failures=failures)
            if len(failures) > before:
                failed_practical.add(str(case_id))

    return BenchmarkResult(
        total=len(golden),
        passed=len(golden) - len(failed_golden),
        practical_total=len(practical),
        practical_passed=len(practical) - len(failed_practical),
        failures=tuple(failures),
    )
