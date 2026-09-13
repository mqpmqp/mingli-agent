"""Offline claim-level validation; synthetic engineering evidence is never accuracy.

The adapter uses the existing TrainingStore append-only boundary, prediction and
reality-evidence freezes, and Real Case Learning V2 time-window semantics. It does
not import real cases or replace V2's independently reviewed production contract.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Mapping

from .contracts.serialization import digest
from .practice_phase2 import _closed, _text, _time
from .real_case_learning_v2 import (
    COMMERCIAL_RELEASE_HOLD,
    RealCaseLearningV2Error,
    _parse_event_window,
)
from .training import TrainingError, TrainingStore
from .validation_freeze import FreezeError, freeze_prediction, verify_prediction_snapshot
from .validation_reality import freeze_reality_evidence, verify_reality_evidence


VERSION = "prospective-real-case-validation@1"
PHASE3_COMMANDS = {
    "case-create", "case-show", "freeze-prediction", "outcome-append",
    "claim-adjudicate", "validation-summary", "pilot-show",
}
POOLS = {"L0": "unverified", "L1": "retrospective_visible",
         "L2": "retrospective_blind", "L3": "prospective"}
STATUSES = ("hit", "partial", "miss", "unverifiable", "pending", "lost_to_followup", "refused", "missing")
CLAIM_TYPES = ("current_state", "prior_event", "future_event", "timing", "outcome", "relationship_action", "exam_result", "fertility_stage", "other")
CLAIM_FIELDS = {"claim_id", "domain", "claim_type", "validation_track", "predicted_event_or_state",
                "predicted_direction", "event_window", "confidence", "specificity_level", "given_dependency_ids",
                "exclusion_conditions", "result_variable", "atomic", "outcome_criterion", "basis_source_ids"}


def _simulated_level(record: Mapping[str, object]) -> str:
    return next(level for level, track in POOLS.items() if track == record["simulated_validation_track"])


def _fail(code: str, message: str) -> None:
    raise TrainingError(code, message)


def _window(value: object):
    try:
        return _parse_event_window(value, code="INVALID_EVENT_WINDOW")
    except RealCaseLearningV2Error as exc:
        raise TrainingError(exc.code, exc.message) from exc


def _seal(value: Mapping[str, object]) -> dict[str, object]:
    body = {key: item for key, item in value.items() if key != "canonical_hash"}
    return {**body, "canonical_hash": digest(body)}


def _save(store: TrainingStore, kind: str, identifier: str, value: Mapping[str, object]):
    return store._write(kind, identifier, _seal({
        "schema_version": VERSION, "record_type": kind, "synthetic": True,
        "accuracy_eligible": False, "commercial_release_hold": COMMERCIAL_RELEASE_HOLD, **value,
    }))


def _verified(store: TrainingStore, kind: str, value: Mapping[str, object]):
    checked = store._validate(kind, value)
    if checked.get("record_type") != kind or checked != _seal(checked):
        _fail("RECORD_INTEGRITY_ERROR", "记录完整性校验失败")
    if kind == "validation_prediction" and not verify_prediction_snapshot(checked["prediction_snapshot"]):
        _fail("RECORD_INTEGRITY_ERROR", "预测快照完整性校验失败")
    if kind == "validation_observation" and not verify_reality_evidence(checked["evidence_snapshot"]):
        _fail("RECORD_INTEGRITY_ERROR", "事实证据完整性校验失败")
    return checked


def _read(store: TrainingStore, kind: str, identifier: str):
    return _verified(store, kind, store._read(kind, identifier))


def _list(store: TrainingStore, kind: str):
    return [_verified(store, kind, item) for item in store._list(kind)]


def _normalized(text: str) -> str:
    text = re.sub(r"[\W_]", "", text).lower()
    for source, replacement in (("面试", "面谈"), ("邀请", "通知"), ("获得", "收到")):
        text = text.replace(source, replacement)
    return re.sub(r"已经|已|曾经|岗位|一次|一份|正式|你|了|将会|将|会", "", text)


def visible_input(case: Mapping[str, object]) -> dict[str, object]:
    """Only this projection is allowed into prediction input identity."""
    return {key: case[key] for key in ("question", "sources", "given_facts")}


def _string_array(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value) or len(set(value)) != len(value):
        _fail("SCHEMA_INCOMPATIBLE", f"{field} 必须是唯一且非空的字符串数组")
    return value


def validate_scorable_claim(
    claim: Mapping[str, object], case: Mapping[str, object], *, generated_at: str, frozen_at: str,
) -> dict[str, object]:
    """Fail-closed structural contract plus conservative wording/GIVEN checks.

    This is not a natural-language proof of independence. Arbitrary paraphrase
    and omitted knowledge still require a separate independent human review.
    """
    data = _closed(claim, CLAIM_FIELDS, label="claim")
    for field in ("claim_id", "domain", "predicted_event_or_state", "claim_type", "validation_track",
                  "predicted_direction", "specificity_level", "result_variable", "outcome_criterion"):
        _text(data[field], field)
    if data["claim_type"] not in CLAIM_TYPES:
        _fail("SCHEMA_INCOMPATIBLE", "claim_type 不受支持")
    if data["validation_track"] != case["simulated_validation_track"]:
        _fail("VALIDATION_TRACK_MISMATCH", "claim validation_track 必须与案例模拟轨道一致")
    if data["predicted_direction"] not in {"support", "contradict"}:
        _fail("SCHEMA_INCOMPATIBLE", "predicted_direction 使用 V2 support/contradict 枚举")
    if data["specificity_level"] not in {"bounded", "vague"}:
        _fail("SCHEMA_INCOMPATIBLE", "specificity_level 必须是 bounded 或 vague")
    if isinstance(data["confidence"], bool) or not isinstance(data["confidence"], (int, float)) or not 0 <= data["confidence"] <= 1:
        _fail("SCHEMA_INCOMPATIBLE", "claim confidence 必须在 0 到 1 之间")
    if not isinstance(data["atomic"], bool):
        _fail("SCHEMA_INCOMPATIBLE", "atomic 必须是布尔值")
    references = _string_array(data["basis_source_ids"], "basis_source_ids")
    dependencies = _string_array(data["given_dependency_ids"], "given_dependency_ids")
    _string_array(data["exclusion_conditions"], "exclusion_conditions")
    given = {item["fact_id"]: {**item, "role": "given"} for item in case["given_facts"]}
    sources = {**{item["source_id"]: item for item in case["sources"]}, **given}
    if any(item not in given for item in dependencies):
        _fail("UNKNOWN_GIVEN_DEPENDENCY", "given_dependency_ids 必须引用已登记 GIVEN")
    if any(item not in sources for item in references):
        _fail("UNKNOWN_SOURCE", "claim 引用了不存在的来源")
    generated, frozen = _time(generated_at, "generated_at"), _time(frozen_at, "frozen_at")
    reasons = []
    if _simulated_level(case) in {"L0", "L1"}:
        reasons.append("insufficient_evidence_level")
    if not references:
        reasons.append("missing_independent_basis")
    if any(_time(sources[item]["available_at"], "available_at") > generated for item in references):
        _fail("SOURCE_NOT_AVAILABLE", "依据不能晚于预测生成时间")
    text = data["predicted_event_or_state"]
    normalized = _normalized(text)
    if (dependencies or any(sources[item]["role"] == "given" for item in references)
            or any(len(_normalized(source["text"])) >= 4
                   and (_normalized(source["text"]) in normalized or normalized in _normalized(source["text"])
                        or SequenceMatcher(None, normalized, _normalized(source["text"])).ratio() >= 0.72)
                   for source in sources.values())):
        reasons.append("given_not_scored")
    if data["specificity_level"] == "vague":
        reasons.append("vague")
    patterns = {
        "vague": r"有机会|会变化|压力大|慢慢稳定|可能会好|得到改善|有所改善|一切顺利|somehow|things may change",
        "disclaimer": r"仅供|娱乐参考|免责声明|disclaimer|for entertainment",
        "advice": r"建议|最好|应当|你应该|recommend|you should",
        "risk": r"风险|小心|注意|risk|beware",
        "compound": r"并且|而且|同时|以及|又会|也会|[；;、]|\band\b|\balso\b",
    }
    for reason, pattern in patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            reasons.append(reason)
    if data["atomic"] is not True:
        reasons.append("compound")
    if len([part for part in re.split(r"[。！？!?]|\.(?:\s|$)", text) if part.strip()]) > 1:
        reasons.append("compound")
    try:
        start, end = _window(data["event_window"])
    except TrainingError:
        reasons.append("unbounded_time")
    else:
        if _simulated_level(case) == "L3" and start <= frozen:
            _fail("PROSPECTIVE_WINDOW_NOT_FUTURE", "前瞻窗口必须严格晚于冻结时间，过期窗口禁止冻结")
        if _simulated_level(case) == "L2" and end >= generated:
            _fail("RETROSPECTIVE_WINDOW_NOT_PAST", "L2 前事窗口必须早于预测生成时间")
    if (data["claim_type"] == "prior_event" and _simulated_level(case) == "L3"
            or data["claim_type"] == "future_event" and _simulated_level(case) == "L2"):
        _fail("CLAIM_TYPE_TIME_MISMATCH", "事件类型与前事/前瞻验证轨道不一致")
    if _simulated_level(case) in {"L2", "L3"}:
        slots = case["hidden_answer_fields"] if _simulated_level(case) == "L2" else case["future_outcome_fields"]
        if data["result_variable"] not in slots:
            _fail("RESULT_VARIABLE_NOT_REGISTERED", "结果变量必须对应事先登记的空答案字段")
    return {**data, "scorable": not reasons,
            "reasons": sorted(set(reasons)), "accuracy_eligible": False}


def validate_pilot_claim_limits(claims: object, case: Mapping[str, object]) -> None:
    """Bound one frozen version so broad claim splitting cannot inflate a pilot."""

    if not isinstance(claims, list):
        _fail("SCHEMA_INCOMPATIBLE", "structured_claims 必须是数组")
    current = sum(isinstance(item, Mapping) and item.get("claim_type") == "current_state" for item in claims)
    bounded = len(claims) - current
    level = _simulated_level(case)
    if len(claims) > 8:
        _fail("CLAIM_LIMIT_EXCEEDED", "每个 Pilot 预测版本最多 8 条 claim")
    if current > 2:
        _fail("CLAIM_LIMIT_EXCEEDED", "当前状态 claim 最多 2 条")
    if level == "L2" and bounded > 3:
        _fail("CLAIM_LIMIT_EXCEEDED", "L2 前事 claim 最多 3 条")
    if level == "L3" and bounded > 3:
        _fail("CLAIM_LIMIT_EXCEEDED", "L3 未来 claim 最多 3 条")


def create_case(payload: Mapping[str, object], store: TrainingStore):
    data = _closed(payload, {"case_id", "synthetic", "evidence_level", "registered_at", "question",
                             "outcome_hidden_from_prediction", "sources", "given_facts", "pilot_batch_id", "case_role",
                             "consent", "hidden_answer_fields", "future_outcome_fields", "simulated_validation_track"}, label="case-create")
    if data["synthetic"] is not True:
        _fail("SYNTHETIC_ONLY", "当前阶段禁止导入真人资料")
    for field in ("case_id", "question", "evidence_level", "pilot_batch_id", "case_role"):
        _text(data[field], field)
    if data["evidence_level"] != "L0":
        _fail("SYNTHETIC_EVIDENCE_LEVEL_REQUIRED", "所有 synthetic 案例真实证据等级必须为 L0")
    if not isinstance(data["simulated_validation_track"], str) or data["simulated_validation_track"] not in POOLS.values():
        _fail("SCHEMA_INCOMPATIBLE", "simulated_validation_track 必须使用规定模拟轨道")
    if data["case_role"] not in {"development", "pilot_evaluation", "holdout_evaluation"}:
        _fail("SCHEMA_INCOMPATIBLE", "case_role 不受支持")
    consent = _closed(data["consent"], {"status", "analysis", "storage", "followup", "withdrawal_available"}, label="consent")
    if (consent["status"] != "synthetic_not_applicable" or any(consent[key] is not False for key in ("analysis", "storage", "followup"))
            or consent["withdrawal_available"] is not True):
        _fail("SYNTHETIC_CONSENT_REQUIRED", "合成样例只能登记未获得真人授权的 consent 骨架")
    for field in ("hidden_answer_fields", "future_outcome_fields"):
        for slot in _string_array(data[field], field):
            if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", slot) is None:
                _fail("ANSWER_SLOT_ONLY", "隐藏答案和未来结局只能登记字段名，不能填入答案")
    if set(data["hidden_answer_fields"]) & set(data["future_outcome_fields"]):
        _fail("ANSWER_SLOT_OVERLAP", "前事答案与未来结局字段必须分开")
    if not isinstance(data["outcome_hidden_from_prediction"], bool):
        _fail("SCHEMA_INCOMPATIBLE", "盲测标记必须是布尔值")
    if _simulated_level(data) == "L2" and data["outcome_hidden_from_prediction"] is not True:
        _fail("RETROSPECTIVE_BLIND_REQUIRED", "L2 必须隔离已知结局")
    registered = _time(data["registered_at"], "registered_at")
    if not isinstance(data["sources"], list) or not isinstance(data["given_facts"], list):
        _fail("SCHEMA_INCOMPATIBLE", "sources 和 given_facts 必须是数组")
    ids = set()
    for source in data["sources"]:
        item = _closed(source, {"source_id", "role", "text", "available_at"}, label="source")
        for field in ("source_id", "text", "role"):
            _text(item[field], field)
        if item["role"] != "independent" or item["source_id"] in ids:
            _fail("SCHEMA_INCOMPATIBLE", "来源角色无效或 source_id 重复")
        if _time(item["available_at"], "available_at") > registered:
            _fail("SOURCE_NOT_AVAILABLE", "登记输入不能包含未来才可见的来源")
        ids.add(item["source_id"])
    for fact in data["given_facts"]:
        item = _closed(fact, {"fact_id", "text", "available_at"}, label="given_fact")
        _text(item["fact_id"], "fact_id")
        _text(item["text"], "text")
        if item["fact_id"] in ids:
            _fail("SCHEMA_INCOMPATIBLE", "GIVEN 与来源 ID 必须唯一")
        if _time(item["available_at"], "available_at") > registered:
            _fail("SOURCE_NOT_AVAILABLE", "GIVEN 不能晚于登记时间")
        ids.add(item["fact_id"])
    return _save(store, "validation_case", data["case_id"], {**data, "visible_input_hash": digest(visible_input(data))})


def freeze_case_prediction(payload: Mapping[str, object], store: TrainingStore):
    data = _closed(payload, {"case_id", "prediction", "frozen_at"}, optional={"revision_of"}, label="freeze-prediction")
    case = _read(store, "validation_case", data["case_id"])
    prediction = _closed(data["prediction"], {
        "prediction_id", "person_case_id", "scenario_id", "engine_version", "source_commit_sha", "rule_set_version",
        "knowledge_manifest_sha", "input_manifest_sha", "generated_at", "prediction_content", "structured_claims",
        "confidence", "blocked_fields", "reality_evidence_visibility",
    }, label="prediction")
    for field in ("prediction_id", "person_case_id", "scenario_id", "engine_version", "source_commit_sha",
                  "rule_set_version", "knowledge_manifest_sha", "input_manifest_sha", "prediction_content"):
        _text(prediction[field], field)
    if prediction["person_case_id"] != case["case_id"]:
        _fail("CASE_MISMATCH", "预测必须绑定已登记案例")
    if prediction["input_manifest_sha"] != case["visible_input_hash"]:
        _fail("VISIBLE_INPUT_HASH_MISMATCH", "预测必须绑定仅覆盖可见输入的 hash")
    generated, frozen = _time(prediction["generated_at"], "generated_at"), _time(data["frozen_at"], "frozen_at")
    if not _time(case["registered_at"], "registered_at") <= generated <= frozen:
        _fail("INVALID_TIME_ORDER", "必须先登记、生成，再冻结")
    if prediction["reality_evidence_visibility"] is not False:
        _fail("FEEDBACK_VISIBLE", "冻结预测不能看到结局或反馈")
    if (isinstance(prediction["confidence"], bool) or not isinstance(prediction["confidence"], (int, float))
            or not 0 <= prediction["confidence"] <= 1):
        _fail("SCHEMA_INCOMPATIBLE", "confidence 必须在 0 到 1 之间")
    if not isinstance(prediction["blocked_fields"], list) or not all(isinstance(item, str) for item in prediction["blocked_fields"]):
        _fail("SCHEMA_INCOMPATIBLE", "blocked_fields 必须是字符串数组")
    if not isinstance(prediction["structured_claims"], list) or not prediction["structured_claims"]:
        _fail("SCHEMA_INCOMPATIBLE", "必须逐条登记 claim")
    validate_pilot_claim_limits(prediction["structured_claims"], case)
    contracts = [validate_scorable_claim(item, case, generated_at=prediction["generated_at"], frozen_at=data["frozen_at"])
                 for item in prediction["structured_claims"]]
    revision_of = data.get("revision_of")
    existing = [item for item in _list(store, "validation_prediction") if item["case_id"] == case["case_id"]]
    if any(item["prediction_id"] == prediction["prediction_id"] for item in existing):
        _fail("DUPLICATE_RECORD", "冻结 ID 已存在；修订必须创建新 prediction_id")
    if existing and not revision_of:
        _fail("REVISION_LINK_REQUIRED", "同一案例的后续预测必须关联原冻结 ID")
    if revision_of:
        parent = _read(store, "validation_prediction", revision_of)
        if parent["case_id"] != case["case_id"] or generated < _time(parent["prediction_snapshot"]["freeze_timestamp"], "freeze_timestamp"):
            _fail("INVALID_REVISION", "修订必须绑定同一案例且不能早于原冻结")
        # Revisions are retained for engineering comparison, never new independent samples.
        contracts = [{**item, "scorable": False, "reasons": sorted(set(item["reasons"] + ["revision_not_independent"]))}
                     for item in contracts]
    try:
        snapshot = freeze_prediction(prediction, frozen_at=data["frozen_at"])
    except FreezeError as exc:
        raise TrainingError("INVALID_PREDICTION", str(exc)) from exc
    return _save(store, "validation_prediction", prediction["prediction_id"], {
        "case_id": case["case_id"], "prediction_id": prediction["prediction_id"],
        "evidence_level": case["evidence_level"], "simulated_validation_track": case["simulated_validation_track"],
        "prediction_snapshot": snapshot,
        "claim_contracts": contracts, "revision_of": revision_of,
    })


def _claim_record(record, claim_id):
    for claim, contract in zip(record["prediction_snapshot"]["structured_claims"], record["claim_contracts"]):
        if claim["claim_id"] == claim_id:
            return claim, contract
    _fail("CLAIM_NOT_FOUND", "claim_id 不在冻结预测中")


def append_outcome(payload: Mapping[str, object], store: TrainingStore):
    data = _closed(payload, {"prediction_id", "evidence_id", "claim_id", "event_window", "observed_at", "collected_at",
                             "source_provenance", "evidence_quality", "fact", "synthetic"}, label="outcome-append")
    if data["synthetic"] is not True:
        _fail("SYNTHETIC_ONLY", "本阶段只接收 synthetic 事实样例")
    for field in ("evidence_id", "fact", "source_provenance", "evidence_quality"):
        _text(data[field], field)
    if re.search(r"感觉.{0,4}(很)?准|算得.{0,4}准|说得.{0,4}准|很满意|用户满意", data["fact"]):
        _fail("QUALITY_FEEDBACK_NOT_OUTCOME", "用户满意度或主观准感必须进入质量反馈，不能作为事件结果证据")
    prediction = _read(store, "validation_prediction", data["prediction_id"])
    claim, _contract = _claim_record(prediction, data["claim_id"])
    if data["event_window"] != claim["event_window"]:
        _fail("EVENT_WINDOW_MISMATCH", "事实必须指向冻结 claim 的同一时间窗")
    observed, collected = _time(data["observed_at"], "observed_at"), _time(data["collected_at"], "collected_at")
    frozen = _time(prediction["prediction_snapshot"]["freeze_timestamp"], "freeze_timestamp")
    start, end = _window(claim["event_window"])
    if observed > collected or collected <= frozen:
        _fail("INVALID_OBSERVATION_TIME", "事实接收必须晚于冻结且不能早于事件观察时间")
    if not start <= observed <= end:
        _fail("OBSERVATION_OUTSIDE_WINDOW", "观察时间必须位于冻结事件窗内")
    if _simulated_level(prediction) == "L3" and observed <= frozen:
        _fail("INVALID_OBSERVATION_TIME", "前瞻观察必须晚于预测冻结")
    try:
        evidence = freeze_reality_evidence({
            **data, "person_case_id": prediction["case_id"],
            "scenario_id": prediction["prediction_snapshot"]["scenario_id"],
        })
    except ValueError as exc:
        raise TrainingError("INVALID_REALITY_EVIDENCE", str(exc)) from exc
    return _save(store, "validation_observation", data["evidence_id"], {
        "case_id": prediction["case_id"], "prediction_id": data["prediction_id"],
        "claim_id": data["claim_id"], "evidence_id": data["evidence_id"], "evidence_snapshot": evidence,
    })


def adjudicate_claim(payload: Mapping[str, object], store: TrainingStore):
    data = _closed(payload, {"prediction_id", "adjudication_id", "claim_id", "outcome_evidence_ids", "status", "reason",
                             "adjudicated_at", "verdict", "timing_verdict", "direction_verdict", "adjudicator",
                             "adjudication_status"}, optional={"supersedes"}, label="claim-adjudicate")
    for field in ("adjudication_id", "reason", "status", "verdict", "timing_verdict", "direction_verdict", "adjudicator", "adjudication_status"):
        _text(data[field], field)
    if data["status"] not in STATUSES:
        _fail("SCHEMA_INCOMPATIBLE", "不支持该裁决状态")
    if data["verdict"] != data["status"]:
        _fail("VERDICT_STATUS_MISMATCH", "兼容 status 字段必须等于 verdict")
    if data["adjudication_status"] != "single_reviewer":
        _fail("INDEPENDENT_REVIEW_NOT_IMPLEMENTED", "当前只支持 single_reviewer，不得伪装独立复核共识")
    if data["timing_verdict"] not in {"in_window", "out_of_window", "pending", "unverifiable"} or data["direction_verdict"] not in {"support", "contradict", "pending", "unverifiable"}:
        _fail("SCHEMA_INCOMPATIBLE", "时间和方向裁决必须使用规定枚举")
    if data["status"] == "pending" and (data["timing_verdict"] != "pending" or data["direction_verdict"] != "pending"):
        _fail("PENDING_VERDICT_CONFLICT", "pending 不能提前裁定方向或时间命中")
    if data["status"] == "hit" and (data["timing_verdict"] != "in_window" or data["direction_verdict"] != "support"):
        _fail("HIT_VERDICT_CONFLICT", "hit 必须同时支持方向和时间窗")
    prediction = _read(store, "validation_prediction", data["prediction_id"])
    claim, contract = _claim_record(prediction, data["claim_id"])
    if contract["scorable"] is not True and data["status"] != "unverifiable":
        _fail("CLAIM_UNSCORABLE", "不可计分 claim 不能转成 hit/miss/partial")
    adjudicated = _time(data["adjudicated_at"], "adjudicated_at")
    if adjudicated < _time(prediction["prediction_snapshot"]["freeze_timestamp"], "freeze_timestamp"):
        _fail("INVALID_ADJUDICATION_TIME", "裁决不得早于冻结")
    if _simulated_level(prediction) == "L3" and adjudicated <= _window(claim["event_window"])[1] and data["status"] != "pending":
        _fail("OUTCOME_PENDING", "前瞻窗口尚未结束，只能 pending 且不能计分")
    ids = data["outcome_evidence_ids"]
    if not isinstance(ids, list) or not all(isinstance(item, str) and item for item in ids) or len(set(ids)) != len(ids):
        _fail("SCHEMA_INCOMPATIBLE", "outcome_evidence_ids 必须是唯一字符串数组")
    if data["status"] in {"hit", "miss", "partial"} and not ids:
        _fail("OUTCOME_EVIDENCE_REQUIRED", "计分裁决必须引用逐条事实证据")
    for evidence_id in ids:
        evidence = _read(store, "validation_observation", evidence_id)
        if evidence["prediction_id"] != data["prediction_id"] or evidence["claim_id"] != data["claim_id"]:
            _fail("EVIDENCE_CLAIM_MISMATCH", "事实必须绑定相同 prediction_id 和 claim_id")
        if _time(evidence["evidence_snapshot"]["collected_at"], "collected_at") > adjudicated:
            _fail("INVALID_ADJUDICATION_TIME", "裁决不能引用尚未接收的证据")
    existing = [item for item in _list(store, "validation_adjudication")
                if item["prediction_id"] == data["prediction_id"] and item["claim_id"] == data["claim_id"]]
    if any(item["adjudication_id"] == data["adjudication_id"] for item in existing):
        _fail("DUPLICATE_RECORD", "裁决 ID 已存在")
    if existing:
        latest = max(existing, key=lambda item: _time(item["adjudicated_at"], "adjudicated_at"))
        if data.get("supersedes") != latest["adjudication_id"] or adjudicated <= _time(latest["adjudicated_at"], "adjudicated_at"):
            _fail("ADJUDICATION_REVISION_REQUIRED", "裁决修订必须以新 ID、较晚时间显式关联上一裁决")
    elif data.get("supersedes"):
        _fail("ADJUDICATION_REVISION_REQUIRED", "不存在可替代的同 claim 裁决")
    return _save(store, "validation_adjudication", data["adjudication_id"], {"case_id": prediction["case_id"], **data})


def pilot_template() -> dict[str, object]:
    return {"schema_version": VERSION, "target_real_cases": 10, "registered_cases": 0,
            "eligible_sample_count": 0, "accuracy": None, "metrics": None, "status": "not_evaluated",
            "commercial_release_hold": COMMERCIAL_RELEASE_HOLD, "real_intake_enabled": False,
            "pilot_batch_id": "pilot-10-v1", "case_role": "pilot_evaluation", "public_accuracy_claim_allowed": False,
            "slots": [{"slot": index, "case_id": None, "status": "not_registered"} for index in range(1, 11)]}


def _empty_real_validation_pool(*, prospective: bool):
    return {"population": "real_registered_cases_only", "total_cases": 0, "eligible_cases": 0,
            "scorable_claims": 0, "hit": 0, "partial": 0, "miss": 0, "unverifiable": 0,
            "verdict_counts": {status: 0 for status in STATUSES}, "by_domain": {}, "by_claim_type": {},
            "eligible_sample_count": 0, "accuracy": None, "metrics": None, "status": "not_evaluated",
            **({"pending": 0, "lost": 0, "refused": 0, "missing": 0} if prospective else
               {"confidence_calibration_status": "insufficient_sample"})}


def validation_summary(payload: Mapping[str, object], store: TrainingStore):
    data = _closed(payload, {"as_of"}, label="validation-summary")
    as_of = _time(data["as_of"], "as_of")
    pools = {level: {"mode": mode, "synthetic_claim_counts": {status: 0 for status in (*STATUSES, "unscorable")},
                     "population": "synthetic_engineering_only", "simulated_cases": 0,
                     "eligible_sample_count": 0, "accuracy": None, "metrics": None, "status": "not_evaluated"}
             for level, mode in POOLS.items()}
    cases = [item for item in _list(store, "validation_case") if _time(item["registered_at"], "registered_at") <= as_of]
    for case in cases:
        pools[_simulated_level(case)]["simulated_cases"] += 1
    decisions = _list(store, "validation_adjudication")
    # Read and verify all referenced facts even though summary does not display them.
    for item in decisions:
        for evidence_id in item["outcome_evidence_ids"]:
            _read(store, "validation_observation", evidence_id)
    for prediction in _list(store, "validation_prediction"):
        if _time(prediction["prediction_snapshot"]["freeze_timestamp"], "freeze_timestamp") > as_of:
            continue
        for contract in prediction["claim_contracts"]:
            claim, _ = _claim_record(prediction, contract["claim_id"])
            candidates = [item for item in decisions if item["prediction_id"] == prediction["prediction_id"]
                          and item["claim_id"] == claim["claim_id"] and _time(item["adjudicated_at"], "adjudicated_at") <= as_of]
            status = "missing"
            if not contract["scorable"]:
                status = "unscorable"
            elif _simulated_level(prediction) == "L3" and as_of <= _window(claim["event_window"])[1]:
                status = "pending"
            elif candidates:
                status = max(candidates, key=lambda item: _time(item["adjudicated_at"], "adjudicated_at"))["status"]
            pools[_simulated_level(prediction)]["synthetic_claim_counts"][status] += 1
    return {"schema_version": VERSION, "as_of": data["as_of"], "pools": pools,
            "synthetic_engineering": {"total_cases": len(cases), "by_simulated_track": {item["mode"]: item for item in pools.values()},
                                      "eligible_sample_count": 0, "accuracy": None},
            "l0_synthetic_count": len(cases),
            "l1_historical_count": 0, "l2_retrospective_count": 0, "l3_prospective_count": 0,
            "prospective_pending_count": 0,
            "cases": {"population": "registered_cases_by_actual_evidence_level", "total": len(cases), "l0_synthetic": len(cases),
                      "real_registered_cases": 0,
                      "l1_historical": 0, "l2_retrospective": 0, "l3_prospective": 0, "pending": 0,
                      "development": sum(item["case_role"] == "development" for item in cases),
                      "pilot_evaluation": sum(item["case_role"] == "pilot_evaluation" for item in cases),
                      "holdout_evaluation": sum(item["case_role"] == "holdout_evaluation" for item in cases)},
            "claims": {"population": "real_registered_cases_only", "scorable": 0, "hit": 0,
                       "partial": 0, "miss": 0, "unverifiable": 0},
            "retrospective_validation": _empty_real_validation_pool(prospective=False),
            "prospective_validation": _empty_real_validation_pool(prospective=True),
            "public_accuracy_claim_allowed": False,
            "pooled_accuracy_allowed": False, "registered_cases": 0, "eligible_sample_count": 0, "accuracy": None, "metrics": None,
            "status": "not_evaluated", "accuracy_eligible": False, "commercial_release_hold": COMMERCIAL_RELEASE_HOLD}


def dispatch_phase3(command: str, payload: Mapping[str, object], *, store: TrainingStore):
    if not store.synthetic:
        _fail("SYNTHETIC_ONLY", "本阶段必须显式启用 synthetic 离线模式")
    handlers = {"case-create": create_case, "freeze-prediction": freeze_case_prediction,
                "outcome-append": append_outcome, "claim-adjudicate": adjudicate_claim,
                "validation-summary": validation_summary}
    if command in handlers:
        return handlers[command](payload, store)
    if command == "pilot-show":
        _closed(payload, set(), label="pilot-show")
        return pilot_template()
    if command == "case-show":
        data = _closed(payload, {"case_id"}, label="case-show")
        case = _read(store, "validation_case", data["case_id"])
        return {"case": case, "predictions": [item for item in _list(store, "validation_prediction") if item["case_id"] == case["case_id"]],
                "outcome_observations": [item for item in _list(store, "validation_observation") if item["case_id"] == case["case_id"]],
                "claim_adjudications": [item for item in _list(store, "validation_adjudication") if item["case_id"] == case["case_id"]]}
    _fail("UNKNOWN_COMMAND", "未知 Phase 3 命令")
