"""Synthetic career contract rehearsal on the existing append-only training store.

This validates supplied, pre-cutoff rule fixtures; it is not a chart algorithm or
an assessment of predictive ability. No generator reads feedback or outcomes.
"""
from __future__ import annotations

import calendar
from copy import deepcopy
from datetime import datetime
import json
import re
from typing import Any, Mapping, Sequence

from .contracts.serialization import digest
from .renderer import DISCLAIMER, find_forbidden
from .training import TrainingError, TrainingStore
from .validation_freeze import freeze_prediction, verify_prediction_snapshot
from .validation_privacy import scan_for_pii

VERSION = "synthetic-career-practice@1"
BOUNDARY = {
    "synthetic": True,
    "release_hold": "ACTIVE",
    "commercial_release_hold": "ACTIVE",
    "prediction_validity": "not_evaluated",
}
_RUN_FIELDS = {"synthetic", "case_id", "run_id", "as_of", "recorded_at", "question", "rule_version", "known_facts", "bases", "claims"}
_MONTH = r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})"
_TIME_PHRASE = re.compile(rf"现在到今年{_MONTH}月|(?:回顾)?(?:今年|\d{{4}}年){_MONTH}月|\d{{4}}-\d{{2}}-\d{{2}}")


def _fail(code: str, message: str) -> None:
    raise TrainingError(code, message)


def _closed(
    value: object,
    fields: set[str],
    *,
    label: str,
    optional_fields: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("SCHEMA_INCOMPATIBLE", f"{label} 必须是对象")
    allowed = fields | (optional_fields or set())
    if set(value) - allowed:
        _fail("INPUT_FIELD_NOT_ALLOWED", f"{label} 含非白名单字段；标题、反馈及结果资料不得进入生成")
    if fields - set(value):
        _fail("SCHEMA_INCOMPATIBLE", f"{label} 缺少字段：{','.join(sorted(fields - set(value)))}")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        _fail("SCHEMA_INCOMPATIBLE", f"{field} 必须是非空短文本")
    return value


def _time(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(_text(value, "时间").replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrainingError("INVALID_TIME", "时间必须是 ISO 8601 日期时间") from exc
    if parsed.tzinfo is None:
        _fail("TIMEZONE_REQUIRED", "as_of 及全部资料时间必须包含时区偏移")
    return parsed


def _records(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 30 or any(not isinstance(x, dict) for x in value):
        _fail("SCHEMA_INCOMPATIBLE", f"{label} 必须是最多30项的对象列表")
    return value


def _ids(value: object) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value) or len(set(value)) != len(value):
        _fail("SCHEMA_INCOMPATIBLE", "来源关联必须是无重复的字符串列表")
    return value


def _confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 0.8:
        _fail("UNSUPPORTED_CONFIDENCE", "合成底稿置信度必须在 (0,0.8]；不代表已验证概率")
    return float(value)


def _month(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {char: n for n, char in enumerate("一二三四五六七八九", 1)}
    if value == "十":
        return 10
    if value.startswith("十") and value[1:] in digits:
        return 10 + digits[value[1:]]
    return digits.get(value, 0)


def parse_window(value: Mapping[str, Any], *, as_of: str) -> dict[str, Any]:
    value = _closed(value, {"text", "intent"}, label="window")
    ref = _time(as_of)
    text = _text(value["text"], "window.text")
    intent = value["intent"]
    if not isinstance(intent, str) or intent not in {"future", "historical", "present"}:
        _fail("INVALID_WINDOW", "窗口意图必须是 future、historical 或 present")
    match = re.fullmatch(rf"(现在到)?(?:回顾)?(今年|\d{{4}}年)({_MONTH})月", text)
    try:
        if match:
            year = ref.year if match[2] == "今年" else int(match[2][:-1])
            month = _month(match[3])
            start = datetime(year, month, 1, tzinfo=ref.tzinfo)
            end = start.replace(day=calendar.monthrange(year, month)[1], hour=23, minute=59, second=59)
            if match[1]:
                start = ref
        elif text == "as_of":
            start = end = ref
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:/\d{4}-\d{2}-\d{2})?", text):
            dates = text.split("/")
            start = datetime.fromisoformat(dates[0]).replace(tzinfo=ref.tzinfo)
            end = datetime.fromisoformat(dates[-1]).replace(tzinfo=ref.tzinfo, hour=23, minute=59, second=59)
        else:
            _fail("UNSUPPORTED_TIME_EXPRESSION", "请明确年份月份或 YYYY-MM-DD/YYYY-MM-DD 窗口")
    except ValueError as exc:
        raise TrainingError("INVALID_WINDOW", "窗口包含非法日期") from exc
    if intent == "future" and end < ref:
        _fail("EXPIRED_FUTURE_WINDOW", f"未来窗口结束于 {end.date().isoformat()}，早于 as_of={ref.date().isoformat()}；请确认时间意图，不自动顺延年份")
    if end < start or (intent == "historical" and end >= ref) or (intent == "future" and start < ref):
        _fail("WINDOW_INTENT_MISMATCH", "窗口起止日期与过去/未来意图不一致")
    if intent == "present" and not start <= ref <= end:
        _fail("WINDOW_INTENT_MISMATCH", "现在窗口必须包含 as_of")
    return {"text": text, "start": start.isoformat(), "end": end.isoformat(), "relation": "past" if end < ref else "future" if start > ref else "present", "historical": intent == "historical", "intent": intent, "as_of": as_of, "timezone": ref.strftime("%z")}


def _safe(text: str) -> None:
    # Only mask locally negated promises and quotes explicitly rejected by the
    # speaker. A separate positive promise in the same sentence remains visible.
    assessed = re.sub(r'(?:不得|不能|不要|不应)(?:写|说|承诺|输出|使用|把|将)[：: ]*[“「"][^”」"\n]*[”」"]', "", text)
    assessed = re.sub(r"(?:并)?不一定|(?:并非|不是)(?:必然|注定|百分百)|(?:不能|不得|无法|不可|不予|不)保证(?:上岸|升职|录取|复合)", "", assessed)
    if find_forbidden(assessed) or DISCLAIMER in text or re.search(r"保证(?:上岸|升职|录取|复合)", assessed):
        _fail("UNSAFE_CLAIM", "底稿含保证性输出或嵌入的免责声明，请修订原判断")


def _fact_key(text: str) -> str:
    # Deliberately small status normalization, not a general semantic matcher.
    return re.sub(r"你|我|可能|已经|目前|现在|[。 ，,、\s]", "", text)


def render_claims(claims: Sequence[Mapping[str, Any]], *, tier: str) -> str:
    """Both tiers preserve every inference verbatim; only paragraph spacing varies."""
    if tier not in {"comment", "paid"}:
        _fail("INVALID_TIER", "仅支持 comment 和 paid")
    parts = [str(item["original_text"]) for item in claims if item["origin"] != "given"]
    for part in parts:
        _safe(part)
    if not parts:
        _fail("NO_SUPPORTED_CLAIMS", "只有已知事实，尚无有依据的工作判断")
    return ("\n\n" if tier == "paid" else "\n").join(parts) + "\n" + DISCLAIMER


def _prepare(payload: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = deepcopy(_closed(payload, _RUN_FIELDS, label="practice-run"))
    if data["synthetic"] is not True:
        _fail("SYNTHETIC_ONLY", "本入口仅接受明确标记 synthetic 的合成数据")
    for key in ("case_id", "run_id", "question", "rule_version"):
        _text(data[key], key)
    if not re.fullmatch(r"person:[0-9a-f]{64}", data["case_id"]):
        _fail("INVALID_CASE_ID", "case_id 必须是合成人物伪名")
    if not re.search(r"工作|事业|岗位|职业", data["question"]):
        _fail("UNSUPPORTED_TOPIC", "此切片仅处理工作类问题")
    cutoff = _time(data["as_of"])
    if _time(data["recorded_at"]) < cutoff:
        _fail("INVALID_CHRONOLOGY", "导入/记录时间不得早于 as_of")
    facts: dict[str, Any] = {}
    claims: list[dict[str, Any]] = []
    for fact in _records(data["known_facts"], "known_facts"):
        _closed(fact, {"source_id", "text", "available_at"}, label="known_fact")
        source_id = _text(fact["source_id"], "source_id")
        _text(fact["text"], "fact.text")
        if source_id in facts:
            _fail("DUPLICATE_SOURCE", "已知事实来源 id 重复")
        if _time(fact["available_at"]) > cutoff:
            _fail("POST_CUTOFF_INPUT", "已知事实晚于可见资料截止点")
        facts[source_id] = fact
        claims.append({"claim_id": "given:" + source_id, "original_text": fact["text"], "origin": "given", "known_fact_ids": [source_id], "basis_id": None, "rule_version": data["rule_version"], "visible_cutoff": data["as_of"], "time_window": parse_window({"text": "as_of", "intent": "present"}, as_of=data["as_of"]), "confidence": None, "independent_prediction_eligible": False})
    bases: dict[str, Any] = {}
    for basis in _records(data["bases"], "bases"):
        _closed(basis, {"basis_id", "kind", "available_at", "supported_claims"}, label="basis")
        basis_id = _text(basis["basis_id"], "basis_id")
        if basis_id in bases or basis["kind"] != "synthetic_rule_fixture":
            _fail("INVALID_BASIS", "依据须为具有唯一 id 的合成规则夹具，不接受结果资料")
        if _time(basis["available_at"]) > cutoff:
            _fail("POST_CUTOFF_INPUT", "规则依据晚于可见资料截止点")
        for support in _records(basis["supported_claims"], "supported_claims"):
            _closed(support, {"text", "window", "confidence", "required_fact_ids"}, label="support")
            _text(support["text"], "support.text")
            _confidence(support["confidence"])
            _ids(support["required_fact_ids"])
        bases[basis_id] = basis
    used_ids = {claim["claim_id"] for claim in claims}
    for raw in _records(data["claims"], "claims"):
        _closed(raw, {"claim_id", "text", "window", "confidence", "basis_id", "known_fact_ids"}, label="claim")
        claim_id = _text(raw["claim_id"], "claim_id")
        if claim_id in used_ids:
            _fail("DUPLICATE_CLAIM", "claim_id 重复")
        used_ids.add(claim_id)
        text = _text(raw["text"], "claim.text")
        _safe(text)
        window = parse_window(raw["window"], as_of=data["as_of"])
        # Validate time in the rendered original, even if a separate window looks valid.
        phrases = _TIME_PHRASE.findall(text)
        residue = _TIME_PHRASE.sub("", text)
        if re.search(rf"{_MONTH}月|明年|去年|后年|前年|下个月|上个月|本月|年底|年初|年后|年内|下周|明天|中旬|上旬|下旬|月底|月初|季度|\d+[日号]", residue):
            _fail("UNSUPPORTED_TIME_EXPRESSION", "原文含未解析时间，请改为与结构化窗口一致的明确年月或日期")
        for phrase in phrases:
            mentioned = parse_window({"text": phrase, "intent": raw["window"]["intent"]}, as_of=data["as_of"])
            if _time(mentioned["start"]) < _time(window["start"]) or _time(mentioned["end"]) > _time(window["end"]):
                _fail("TEXT_WINDOW_MISMATCH", "原文时间与结构化窗口不一致")
        confidence = _confidence(raw["confidence"])
        refs = _ids(raw["known_fact_ids"])
        if not set(refs) <= facts.keys():
            _fail("UNKNOWN_FACT_SOURCE", "claim 关联了不存在的已知事实来源")
        repeated = [source_id for source_id, fact in facts.items() if _fact_key(text) == _fact_key(fact["text"])]
        if not repeated and not re.search(r"可能|倾向|若|如果|存在", text):
            _fail("UNSUPPORTED_CERTAINTY", "合成判断须保留条件或不确定性，不可变为事实保证")
        for state in ("失业", "待业", "没有工作", "在职", "已婚"):
            if state in text and not any(state in facts[ref]["text"] for ref in refs):
                _fail("UNSUPPORTED_EMPLOYMENT_STATE", "不得根据问题或规则夹具擅自补入用户未提供的就业/婚姻状态")
        basis_id = _text(raw["basis_id"], "basis_id")
        basis = bases.get(basis_id)
        if basis is None:
            _fail("MISSING_BASIS", "日期合法不代表应期有依据：claim 缺少可见的依据关联")
        supports = [item for item in basis["supported_claims"] if item["text"] == text and item["window"] == raw["window"] and confidence <= item["confidence"] and set(item["required_fact_ids"]) <= set(refs)]
        if not supports:
            _fail("UNSUPPORTED_CLAIM", "判断、时间、置信度或事实条件超出合成底稿支持范围")
        claims.append({"claim_id": claim_id, "original_text": text, "origin": "given" if repeated else "inference", "known_fact_ids": sorted(set(refs + repeated)), "basis_id": basis_id, "rule_version": data["rule_version"], "visible_cutoff": data["as_of"], "time_window": window, "confidence": confidence, "independent_prediction_eligible": not repeated})
    return data, claims


def _generation_identity(data: Mapping[str, Any]) -> str:
    # A fair replay keeps the person's visible input fixed while allowing the
    # rule fixture and structured judgement to change as a new dev version.
    fields = ("synthetic", "case_id", "as_of", "question", "known_facts")
    return digest({key: data[key] for key in fields})


def run_practice(payload: Mapping[str, Any], store: TrainingStore, *, replay_of: str | None = None) -> dict[str, Any]:
    data, claims = _prepare(payload)
    rendered = {tier: render_claims(claims, tier=tier) for tier in ("comment", "paid")}
    # Check id before creating or updating any record.
    if store._path("run", data["run_id"]).exists():
        _fail("DUPLICATE_RECORD", "原 run 已冻结；请使用新 run_id")
    if replay_of is None and store._path("case", data["case_id"]).exists():
        _fail("FROZEN_CASE_INPUT", "本工作类案例输入已冻结；后续版本须通过 practice-replay 使用原可见资料")
    prediction = freeze_prediction({
        "prediction_id": data["run_id"], "person_case_id": data["case_id"], "scenario_id": "career:synthetic-practice",
        "engine_version": VERSION, "source_commit_sha": "0" * 40, "rule_set_version": data["rule_version"],
        "knowledge_manifest_sha": digest(data["bases"]), "input_manifest_sha": digest(data), "generated_at": data["recorded_at"],
        "prediction_content": rendered["comment"], "structured_claims": claims, "confidence": max(item["confidence"] or 0 for item in claims),
        "blocked_fields": ["precise_chart_analysis", "real_prediction_accuracy"], "reality_evidence_visibility": False,
        "prediction_validity": "not_evaluated",
    }, frozen_at=data["recorded_at"])
    result = {**BOUNDARY, "schema_version": VERSION, "generation_input": data, "prediction": prediction, "rendered": rendered,
              "visible_input_hash": _generation_identity(data), "replay_of": replay_of, "partition": "development",
              "provenance": {"imported_at": data["recorded_at"], "original_published_at": None, "historical_prepublication_verified": False,
                             "timestamp_origin": "caller_supplied_synthetic", "basis_validity": "synthetic_fixture_only", "source_commit_attested": False}}
    if not store._path("case", data["case_id"]).exists():
        store.create_case({"case_id": data["case_id"], "consent_scope": ["analysis", "training"], "consent_version": VERSION,
                           "intake_snapshot_ref": digest(data), "chart_snapshot_ref": "not_used:synthetic-contract", "runtime_output_ref": "pending",
                           "analysis_version": VERSION, "created_at": data["recorded_at"], "topic": "career", "confidence": "pending",
                           "feedback_status": "pending", "outcome_status": "pending", "review_status": "pending",
                           "provenance": {"synthetic": True}, "lifecycle": "active"})
    else:
        case = store._read("case", data["case_id"])
        if case.get("provenance", {}).get("synthetic") is not True:
            _fail("SYNTHETIC_ONLY", "不能把已有真人案例转为合成案例")
    store.save_analysis_run({"run_id": data["run_id"], "case_id": data["case_id"], "created_at": data["recorded_at"],
                             "schema_version": VERSION, "engine_version": VERSION, "rule_manifest_hash": digest(data["bases"]),
                             "renderer_version": VERSION, "input_manifest_hash": digest(data), "output_manifest_hash": digest(result),
                             "status": "completed", "confidence": "low", "result": result, "provenance": {"synthetic": True}, "valid": True})
    return result


def _run(store: TrainingStore, run_id: object) -> dict[str, Any]:
    # Intentionally use the narrow existing record reader, never show_case/_list:
    # those aggregate feedback and outcomes and must not feed historical replay.
    run = store._read("run", _text(run_id, "run_id"))
    result = run.get("result", {})
    if result.get("schema_version") != VERSION or result.get("synthetic") is not True:
        _fail("SYNTHETIC_ONLY", "仅可读取本合成闭环生成的 run")
    if not verify_prediction_snapshot(result.get("prediction", {})) or digest(result) != run.get("output_manifest_hash"):
        _fail("SNAPSHOT_CHANGED", "原预测快照或 run 内容校验失败")
    return run


def replay_practice(payload: Mapping[str, Any], store: TrainingStore) -> dict[str, Any]:
    data = _closed(
        payload,
        {"source_run_id", "run_id", "rule_version", "recorded_at"},
        label="practice-replay",
        optional_fields={"bases", "claims"},
    )
    if ("bases" in data) != ("claims" in data):
        _fail("SCHEMA_INCOMPATIBLE", "候选 bases 与 claims 必须同时提供")
    source = _run(store, data["source_run_id"])
    original = source["result"]["generation_input"]
    if data["rule_version"] == original["rule_version"]:
        _fail("NEW_RULE_VERSION_REQUIRED", "反馈后的候选必须使用新规则版本")
    if _time(data["recorded_at"]) < _time(source["created_at"]):
        _fail("INVALID_CHRONOLOGY", "重放记录时间不能早于原记录")
    projected = {key: deepcopy(original[key]) for key in _RUN_FIELDS}
    projected.update({key: data[key] for key in ("run_id", "rule_version", "recorded_at")})
    if "bases" in data:
        projected["bases"] = deepcopy(data["bases"])
        projected["claims"] = deepcopy(data["claims"])
    return run_practice(projected, store, replay_of=source["run_id"])


def feedback_practice(payload: Mapping[str, Any], store: TrainingStore) -> dict[str, Any]:
    data = _closed(
        payload,
        {"run_id", "feedback_id", "claim_id", "submitted_at", "outcome", "text", "experience"},
        label="practice-feedback",
    )
    experience = _closed(
        data["experience"],
        {
            "overall_rating", "useful_sections", "inaccurate_sections", "missing_context",
            "user_correction", "clarity_rating", "actionability_rating", "feedback_kind",
        },
        label="practice-feedback.experience",
    )
    run = _run(store, data["run_id"])
    submitted = _time(data["submitted_at"])
    if submitted < _time(run["created_at"]):
        _fail("INVALID_CHRONOLOGY", "反馈提交时间不得早于冻结记录")
    if not isinstance(data["outcome"], str) or data["outcome"] not in {"hit", "partial", "miss", "unverifiable"}:
        _fail("INVALID_OUTCOME", "反馈判定须为 hit、partial、miss 或 unverifiable")
    _text(data["text"], "feedback.text")
    claim = next((item for item in run["result"]["prediction"]["structured_claims"] if item["claim_id"] == data["claim_id"]), None)
    if claim is None:
        _fail("UNKNOWN_CLAIM", "反馈须关联原预测中的 claim_id")
    reason = "given" if claim["origin"] == "given" else "not_due" if submitted <= _time(claim["time_window"]["end"]) else "unverifiable" if data["outcome"] == "unverifiable" else None
    adjudication = {"claim_id": data["claim_id"], "status": data["outcome"], "independent_hit": reason is None and data["outcome"] == "hit", "exclusion_reason": reason,
                    "prediction_hash": run["result"]["prediction"]["canonical_hash"], "scoring_version": VERSION, "synthetic": True, "counts_toward_real_accuracy": False}
    record_id = _text(data["feedback_id"], "feedback_id")
    feedback_record = {
        "feedback_id": record_id,
        "case_id": run["case_id"],
        "run_id": run["run_id"],
        **experience,
        "free_text": data["text"],
        "submitted_at": data["submitted_at"],
    }
    outcome_record = {
        "outcome_id": record_id,
        "case_id": run["case_id"],
        "run_id": run["run_id"],
        "event_type": VERSION,
        "event_time": data["submitted_at"],
        "observed_at": data["submitted_at"],
        "source_type": "synthetic_fixture_feedback",
        "source_reliability": "unverified",
        "relation_to_prior_claim": "later_outcome",
        "notes": json.dumps({"text": data["text"], "adjudication": adjudication}, ensure_ascii=False),
        "preregistered_claim_id": data["claim_id"],
    }
    # Validate both append-only writes before either one is created so an input
    # or duplicate-id error cannot leave half of the paired synthetic receipt.
    if store._path("feedback", record_id).exists() or store._path("outcome", record_id).exists():
        _fail("DUPLICATE_RECORD", "feedback/outcome record already exists")
    store._validate("feedback", {**feedback_record, "counts_toward_accuracy": False, "valid": True})
    store._validate("outcome", {**outcome_record, "commercial_validation_eligible": False, "valid": True})
    saved_feedback = store.add_feedback(feedback_record)
    saved_outcome = store.add_outcome(outcome_record)
    return {
        **BOUNDARY,
        "feedback_id": saved_feedback["feedback_id"],
        "outcome_id": saved_outcome["outcome_id"],
        "adjudication": adjudication,
    }


def _scores(run: Mapping[str, Any], records: Sequence[Mapping[str, Any]], *, as_of: str) -> dict[str, Any]:
    cutoff = _time(as_of)
    totals = {"independent_hits": 0, "evaluated": 0, "given_excluded": 0, "not_due": 0, "missing": 0, "unverifiable": 0, "conflicting_feedback": 0}
    for claim in run["result"]["prediction"]["structured_claims"]:
        if claim["origin"] == "given":
            totals["given_excluded"] += 1
            continue
        if _time(claim["time_window"]["end"]) >= cutoff:
            totals["not_due"] += 1
            continue
        matches = [json.loads(item["notes"])["adjudication"] for item in records if item.get("run_id") == run["run_id"] and item.get("event_type") == VERSION and item.get("preregistered_claim_id") == claim["claim_id"] and _time(item["observed_at"]) <= cutoff]
        matches = [item for item in matches if item["exclusion_reason"] != "not_due"]
        if not matches:
            totals["missing"] += 1
        elif len({item["status"] for item in matches}) > 1:
            totals["conflicting_feedback"] += 1
        elif matches[0]["status"] == "unverifiable":
            totals["unverifiable"] += 1
        else:
            totals["evaluated"] += 1
            totals["independent_hits"] += int(matches[0]["independent_hit"])
    return {**totals, "scoring_version": VERSION, "accuracy": None, "lost_to_followup": None, "refused": 0}


def compare_practice(payload: Mapping[str, Any], store: TrainingStore) -> dict[str, Any]:
    data = _closed(payload, {"baseline_run_id", "candidate_run_id", "as_of"}, label="practice-compare")
    baseline = _run(store, data["baseline_run_id"])
    candidate = _run(store, data["candidate_run_id"])
    cutoff = _time(data["as_of"])
    if any(_time(run["created_at"]) > cutoff for run in (baseline, candidate)):
        _fail("INVALID_CHRONOLOGY", "比较时间不得早于被比较记录")
    if baseline["case_id"] != candidate["case_id"] or _generation_identity(baseline["result"]["generation_input"]) != _generation_identity(candidate["result"]["generation_input"]):
        _fail("INCOMPARABLE_INPUT", "仅比较同人物、同事件和同一冻结可见输入")
    records = store._list("outcome")
    runs = {"baseline": baseline, "candidate": candidate}
    expected = {name: _prepare(run["result"]["generation_input"])[1] for name, run in runs.items()}
    scores = {name: _scores(run, records, as_of=data["as_of"]) for name, run in runs.items()}

    def product(run: Mapping[str, Any]) -> dict[str, Any]:
        claims = [x for x in run["result"]["prediction"]["structured_claims"] if x["origin"] != "given"]
        expected_claims = expected["baseline" if run is baseline else "candidate"]
        supported = [x for x in expected_claims if x["origin"] != "given"]
        texts = [x["original_text"] for x in claims]
        rendered = run["result"]["rendered"]
        additions = sum(
            line.strip() not in {*texts, DISCLAIMER}
            for text in rendered.values() for line in text.splitlines() if line.strip()
        )
        covered = bool(texts) and all(all(text in answer for text in texts) for answer in rendered.values())
        topic_words = r"工作|事业|岗位|职业|面谈|升职|换岗|职责|交接|录取|上岸"
        vague_phrases = ("有机会", "会变化", "压力大", "注意沟通", "慢慢稳定")
        return {"substantive_claim_count": len(claims), "rendered": run["result"]["rendered"], "claim_ids": [x["claim_id"] for x in claims],
                "answered_current_question": covered and all(re.search(topic_words, text) is not None for text in texts),
                "unsupported_detail_count": sum(claim not in supported for claim in claims) + additions,
                "template_or_vague_phrase_count": sum(text.count(phrase) for text in texts for phrase in vague_phrases) + len(texts) - len(set(texts)),
                "over_refusal": bool(supported) and not covered,
                "tier_additions": additions, "manual_rewrite_amount": None, "human_quality_review": "not_evaluated",
                "assessment_scope": "synthetic_contract_and_bounded_phrase_checks"}

    products = {name: product(run) for name, run in runs.items()}
    improved_checks: list[str] = []
    regressed_checks: list[str] = []
    for field in ("unsupported_detail_count", "template_or_vague_phrase_count"):
        if products["candidate"][field] < products["baseline"][field]:
            improved_checks.append(field)
        elif products["candidate"][field] > products["baseline"][field]:
            regressed_checks.append(field)
    for field in ("answered_current_question",):
        if products["candidate"][field] and not products["baseline"][field]:
            improved_checks.append(field)
        elif products["baseline"][field] and not products["candidate"][field]:
            regressed_checks.append(field)
    if not products["candidate"]["over_refusal"] and products["baseline"]["over_refusal"]:
        improved_checks.append("over_refusal")
    elif products["candidate"]["over_refusal"] and not products["baseline"]["over_refusal"]:
        regressed_checks.append("over_refusal")
    improvement = {
        "status": "machine_checks_improved" if improved_checks and not regressed_checks else "machine_checks_regressed" if regressed_checks else "not_established",
        "improved_checks": improved_checks,
        "regressed_checks": regressed_checks,
        "human_quality_review": "not_evaluated",
        "scope": "paired_synthetic_entry_output",
    }
    time_consistent = all(
        [(claim["claim_id"], claim["time_window"], claim["visible_cutoff"]) for claim in run["result"]["prediction"]["structured_claims"]]
        == [(claim["claim_id"], claim["time_window"], claim["visible_cutoff"]) for claim in expected[name]]
        for name, run in runs.items()
    )
    given_excluded = all(
        scores[name]["given_excluded"] == sum(claim["origin"] == "given" for claim in expected[name])
        and all(claim["independent_prediction_eligible"] is False for claim in expected[name] if claim["origin"] == "given")
        for name in runs
    )
    snapshots_verified = all(verify_prediction_snapshot(run["result"]["prediction"]) for run in runs.values())
    feedback_bound = all(
        json.loads(record["notes"])["adjudication"]["prediction_hash"] == run["result"]["prediction"]["canonical_hash"]
        for run in runs.values() for record in records
        if record.get("event_type") == VERSION and record.get("run_id") == run["run_id"]
    )
    feedback_hidden = all(
        set(run["result"]["generation_input"]) == _RUN_FIELDS
        and run["result"]["prediction"]["reality_evidence_visibility"] is False
        and run["result"]["visible_input_hash"] == _generation_identity(run["result"]["generation_input"])
        for run in runs.values()
    )
    comparison = {
        "baseline_run_id": baseline["run_id"],
        "candidate_run_id": candidate["run_id"],
        "baseline_rule_version": baseline["result"]["generation_input"]["rule_version"],
        "candidate_rule_version": candidate["result"]["generation_input"]["rule_version"],
        "baseline_prediction_hash": baseline["result"]["prediction"]["canonical_hash"],
        "candidate_prediction_hash": candidate["result"]["prediction"]["canonical_hash"],
    }
    return {**BOUNDARY, "comparison": comparison, "engineering": {
                "same_visible_input": _generation_identity(baseline["result"]["generation_input"]) == _generation_identity(candidate["result"]["generation_input"]),
                "time_consistency": time_consistent, "given_not_scored": given_excluded,
                "original_snapshot_verified": snapshots_verified, "original_snapshot_not_overwritten": snapshots_verified and feedback_bound,
                "feedback_visible_to_replay": not feedback_hidden, "feedback_hidden_from_replay": feedback_hidden,
                "normal_flow_completed": all(run["status"] == "completed" and products[name]["substantive_claim_count"] > 0 for name, run in runs.items()),
                "verification_scope": "current_frozen_records_and_registered_feedback"},
            "product": {**products, "same_rendered_output": baseline["result"]["rendered"] == candidate["result"]["rendered"], "improvement": improvement, "all_compared_samples_retained": True},
            "synthetic_results": scores,
            "real_results": {"data_source": "none", "eligible_sample_count": 0, "accuracy": None, "metrics": None, "status": "not_evaluated",
                             "due_with_feedback": 0, "not_due": 0, "lost_to_followup": 0, "unverifiable": 0, "refused": 0, "missing": 0},
            "partition": "development", "holdout_eligible": False}


def dispatch_practice(command: str, payload: Mapping[str, Any], *, store: TrainingStore) -> dict[str, Any]:
    if not store.synthetic:
        _fail("SYNTHETIC_ONLY", "本轮闭环必须显式使用 --synthetic，不接入真人资料")
    if scan_for_pii(payload):
        _fail("PII_DETECTED", "输入含直接身份标识；仅允许匿名合成资料")
    handlers = {"practice-run": run_practice, "practice-replay": replay_practice, "practice-feedback": feedback_practice, "practice-compare": compare_practice}
    return handlers[command](payload, store)
