"""Phase 4 pilot control plane layered on the existing validation records.

The module stores only bounded pilot-control metadata. Detailed predictions,
outcome observations, and claim adjudications remain owned by ``practice_phase3``
and ``real_case_learning_v2``. Synthetic engineering runs have their own shadow
slots and can never consume a real pilot slot.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import re
from typing import Mapping

from .contracts.serialization import digest
from .practice_phase2 import _closed, _text, _time
from .practice_phase3 import (
    _claim_record,
    _list as _phase3_list,
    _read as _phase3_read,
    dispatch_phase3,
    pilot_template,
    validation_summary as phase3_validation_summary,
)
from .real_case_learning_v2 import COMMERCIAL_RELEASE_HOLD
from .training import TrainingError, TrainingStore


VERSION = "prospective-real-case-validation-phase4@1"
PHASE4_COMMANDS = {
    "pilot-candidate-intake",
    "pilot-candidate-list",
    "pilot-candidate-show",
    "pilot-start",
    "pilot-screen",
    "pilot-list",
    "pilot-mature",
    "pilot-quality-append",
    "pilot-revision-freeze",
    "pilot-summary",
    "pilot-withdraw",
}
QUALITY_LABELS = {
    "USER_ACCEPTED",
    "USER_REJECTED",
    "TOO_VAGUE",
    "TOO_VERBOSE",
    "TEMPLATE_LIKE",
    "GOOD_STYLE",
    "BAD_STYLE",
    "OVERCLAIMED",
    "GOOD_SPECIFICITY",
}
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_PERSON_ID = re.compile(r"^person:[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^case:[0-9a-f]{64}$")
_CANDIDATE_ID = re.compile(r"^candidate:[0-9a-f]{64}$")
_CLAIM_LIMITS = {"L2": 3, "current_state": 2, "L3": 3, "total": 8}


def _fail(code: str, message: str) -> None:
    raise TrainingError(code, message)


def _seal(value: Mapping[str, object]) -> dict[str, object]:
    body = {key: item for key, item in value.items() if key != "canonical_hash"}
    return {**body, "canonical_hash": digest(body)}


def _save(
    store: TrainingStore,
    kind: str,
    identifier: str,
    value: Mapping[str, object],
    *,
    synthetic: bool,
    counts_toward_real_pilot: bool = False,
) -> dict[str, object]:
    return store._write(
        kind,
        identifier,
        _seal(
            {
                "schema_version": VERSION,
                "record_type": kind,
                "synthetic": synthetic,
                "counts_toward_real_pilot": counts_toward_real_pilot,
                "accuracy_eligible": False,
                "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
                **value,
            }
        ),
    )


def _verified(store: TrainingStore, kind: str, value: Mapping[str, object]) -> dict[str, object]:
    checked = store._validate(kind, value)
    if checked.get("record_type") != kind or checked != _seal(checked):
        _fail("RECORD_INTEGRITY_ERROR", "Pilot 记录完整性校验失败")
    return checked


def _read(store: TrainingStore, kind: str, identifier: str) -> dict[str, object]:
    return _verified(store, kind, store._read(kind, identifier))


def _list(store: TrainingStore, kind: str) -> list[dict[str, object]]:
    return [_verified(store, kind, item) for item in store._list(kind)]


def _sha(value: object, field: str) -> str:
    text = _text(value, field)
    if _SHA256.fullmatch(text) is None:
        _fail("SCHEMA_INCOMPATIBLE", f"{field} 必须是 sha256 hash")
    return text


def _batch(store: TrainingStore, batch_id: str) -> dict[str, object]:
    return _read(store, "pilot_batch", batch_id)


def _candidate_records(store: TrainingStore, batch_id: str) -> list[dict[str, object]]:
    return [item for item in _list(store, "pilot_candidate_intake") if item["batch_id"] == batch_id]


def _candidate(store: TrainingStore, batch_id: str, candidate_id: str) -> dict[str, object]:
    if _CANDIDATE_ID.fullmatch(candidate_id) is None:
        _fail("INVALID_CANDIDATE_ID", "candidate_id 必须是不可逆 SHA256 假名")
    try:
        item = _read(store, "pilot_candidate_intake", candidate_id)
    except TrainingError as exc:
        if exc.code == "RECORD_NOT_FOUND":
            _fail("CANDIDATE_INTAKE_REQUIRED", "pilot-screen 前必须存在 candidate intake receipt")
        raise
    if item["batch_id"] != batch_id:
        _fail("CANDIDATE_BATCH_MISMATCH", "candidate 不属于当前 Pilot batch")
    return item


def _identity_seen_in_audit(store: TrainingStore, identity_hash: str) -> bool:
    audit_path = store.root / "audit.jsonl"
    if not audit_path.is_file():
        return False
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            _fail("AUDIT_INTEGRITY_ERROR", "Candidate intake audit 无法解析")
        if item.get("action") == "PILOT_CANDIDATE_INTAKE" and item.get("details", {}).get("identity_hash") == identity_hash:
            return True
    return False


def _prior_candidate_state(store: TrainingStore, proposed_case_id: str) -> list[str]:
    states: list[str] = []
    cases = [item for item in _phase3_list(store, "validation_case") if item["case_id"] == proposed_case_id]
    predictions = [
        item for item in _phase3_list(store, "validation_prediction") if item["case_id"] == proposed_case_id
    ]
    prediction_ids = {item["prediction_id"] for item in predictions}
    if cases:
        states.append("case")
    if predictions:
        states.append("prediction")
    if any(item["prediction_id"] in prediction_ids for item in _phase3_list(store, "validation_observation")):
        states.append("feedback")
    if any(item["prediction_id"] in prediction_ids for item in _list(store, "pilot_quality")):
        states.append("feedback")
    return sorted(set(states))


def intake_candidate(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(
        payload,
        {
            "batch_id",
            "received_at",
            "source_timestamp",
            "source_type",
            "deidentified_source_fingerprint",
            "intake_nonce",
            "proposed_case_id",
            "human",
            "synthetic",
            "consent_status",
            "privacy_status",
            "input_gate_status",
        },
        label="pilot-candidate-intake",
    )
    batch = _batch(store, data["batch_id"])
    received_at = _time(data["received_at"], "received_at")
    source_timestamp = _time(data["source_timestamp"], "source_timestamp")
    if received_at < source_timestamp:
        _fail("INVALID_TIME_ORDER", "candidate.received_at 不能早于 source_timestamp")
    if received_at < _time(batch["pilot_start_at"], "pilot_start_at"):
        _fail("BEFORE_PILOT_START", "Candidate intake 不能早于 Pilot 启动时间")
    if data["source_type"] not in {"direct_inquiry", "authorized_import", "synthetic_fixture"}:
        _fail("SCHEMA_INCOMPATIBLE", "source_type 不受支持")
    fingerprint = _sha(data["deidentified_source_fingerprint"], "deidentified_source_fingerprint")
    nonce = _sha(data["intake_nonce"], "intake_nonce")
    proposed_case_id = _text(data["proposed_case_id"], "proposed_case_id")
    if not store.synthetic and _CASE_ID.fullmatch(proposed_case_id) is None:
        _fail("INVALID_PILOT_CASE_ID", "真人 proposed_case_id 必须是去标识化 SHA256 假名")
    if data["synthetic"] is not store.synthetic or data["human"] is store.synthetic:
        _fail("STORE_MODE_MISMATCH", "Candidate human/synthetic 标记必须匹配 store 模式")
    if store.synthetic and data["source_type"] != "synthetic_fixture":
        _fail("SYNTHETIC_SOURCE_REQUIRED", "工程 fixture 必须显式标记 synthetic_fixture")
    if data["consent_status"] not in {"unknown", "granted", "denied"}:
        _fail("SCHEMA_INCOMPATIBLE", "consent_status 不受支持")
    if data["privacy_status"] not in {"pending", "pass", "fail"}:
        _fail("SCHEMA_INCOMPATIBLE", "privacy_status 不受支持")
    if data["input_gate_status"] not in {"pending", "pass", "fail"}:
        _fail("SCHEMA_INCOMPATIBLE", "input_gate_status 不受支持")
    identity = {
        "batch_id": data["batch_id"],
        "source_timestamp": data["source_timestamp"],
        "source_type": data["source_type"],
        "deidentified_source_fingerprint": fingerprint,
    }
    identity_hash = digest(identity)
    if _identity_seen_in_audit(store, identity_hash):
        _fail("CANDIDATE_IDENTITY_REUSE", "已登记或删除的 candidate 不得通过新 nonce 重新编号")
    candidate_id = "candidate:" + digest(
        {**identity, "proposed_case_id": proposed_case_id, "intake_nonce": nonce}
    ).split(":", 1)[1]
    prior_state = _prior_candidate_state(store, proposed_case_id)
    sequence_violation = bool(prior_state)
    record = _save(
        store,
        "pilot_candidate_intake",
        candidate_id,
        {
            "schema_version": "practice-phase4-candidate-intake@1.0",
            "batch_id": data["batch_id"],
            "candidate_id": candidate_id,
            "received_at": data["received_at"],
            "source_timestamp": data["source_timestamp"],
            "source_type": data["source_type"],
            "deidentified_source_fingerprint": fingerprint,
            "proposed_case_id": proposed_case_id,
            "human": data["human"],
            "consent_status": data["consent_status"],
            "privacy_status": data["privacy_status"],
            "input_gate_status": data["input_gate_status"],
            "pilot_screen_status": "not_screened",
            "screen_fail_reason": None,
            "registered_case_id": None,
            "pilot_slot": None,
            "simulated_slot": None,
            "prediction_created": "prediction" in prior_state,
            "prior_state_detected": prior_state,
            "intake_sequence_violation": sequence_violation,
            "intake_status": "blocked_sequence_violation" if sequence_violation else "accepted",
            "identity_hash": identity_hash,
        },
        synthetic=store.synthetic,
    )
    store._audit(
        "PILOT_CANDIDATE_INTAKE",
        candidate_id,
        occurred_at=data["received_at"],
        details={"identity_hash": identity_hash, "candidate_hash": record["canonical_hash"]},
    )
    return record


def start_pilot(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(
        payload,
        {
            "batch_id",
            "pilot_start_at",
            "target_real_cases",
            "grace_period_days",
            "synthetic",
            "real_intake_enabled",
        },
        label="pilot-start",
    )
    _text(data["batch_id"], "batch_id")
    _time(data["pilot_start_at"], "pilot_start_at")
    if data["target_real_cases"] != pilot_template()["target_real_cases"]:
        _fail("PILOT_TARGET_LOCKED", "Phase 4 Pilot 目标固定为 10 个连续真人案例")
    if isinstance(data["grace_period_days"], bool) or not isinstance(data["grace_period_days"], int):
        _fail("SCHEMA_INCOMPATIBLE", "grace_period_days 必须是整数")
    if not 0 <= data["grace_period_days"] <= 90:
        _fail("INVALID_GRACE_PERIOD", "grace_period_days 必须在 0 到 90 天之间")
    if data["synthetic"] is not store.synthetic:
        _fail("STORE_MODE_MISMATCH", "Pilot batch 的 synthetic 标记必须匹配 store 模式")
    expected_real = not store.synthetic
    if data["real_intake_enabled"] is not expected_real:
        _fail("REAL_INTAKE_MODE_MISMATCH", "真实入组只允许写入仓库外的非 synthetic store")
    return _save(
        store,
        "pilot_batch",
        data["batch_id"],
        data,
        synthetic=store.synthetic,
    )


def _claim_counts(value: object) -> tuple[dict[str, int], list[str]]:
    data = _closed(value, set(_CLAIM_LIMITS), label="claim_counts")
    reasons: list[str] = []
    for key, limit in _CLAIM_LIMITS.items():
        count = data[key]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            _fail("SCHEMA_INCOMPATIBLE", f"claim_counts.{key} 必须是非负整数")
        if count > limit:
            reasons.append(f"{key.upper()}_CLAIM_LIMIT")
    if data["total"] != data["L2"] + data["current_state"] + data["L3"]:
        _fail("CLAIM_COUNT_MISMATCH", "claim_counts.total 必须等于三个分池计数之和")
    if data["total"] == 0:
        reasons.append("NO_FREEZABLE_CLAIM")
    return data, reasons


def _screen_records(store: TrainingStore, batch_id: str) -> list[dict[str, object]]:
    return [item for item in _list(store, "pilot_screen") if item["batch_id"] == batch_id]


def _withdrawals(store: TrainingStore, batch_id: str) -> list[dict[str, object]]:
    return [item for item in _list(store, "pilot_withdrawal") if item["batch_id"] == batch_id]


def _eligible_screens(records: list[dict[str, object]], *, synthetic: bool) -> list[dict[str, object]]:
    result = [
        item
        for item in records
        if item["synthetic"] is synthetic and item["eligibility_status"] == "eligible"
    ]
    return sorted(result, key=lambda item: (_time(item["source_timestamp"], "source_timestamp"), item["screen_id"]))


def _slot_integrity(records: list[dict[str, object]], *, synthetic: bool, target: int) -> dict[str, object]:
    eligible = _eligible_screens(records, synthetic=synthetic)
    slot_field = "simulated_slot" if synthetic else "assigned_real_slot"
    expected = list(range(1, min(len(eligible), target) + 1))
    actual = [item[slot_field] for item in eligible[:target]]
    broken = actual != expected
    return {
        "no_selective_enrollment": not broken,
        "selection_integrity_broken": broken,
        "eligible_screens": len(eligible),
        "slots_used": len([item for item in eligible if item[slot_field] is not None]),
    }


def _candidate_integrity(
    store: TrainingStore,
    candidates: list[dict[str, object]],
    screens: list[dict[str, object]],
    *,
    synthetic: bool | None,
    target: int,
) -> dict[str, object]:
    selected_candidates = [
        item for item in candidates if synthetic is None or item["synthetic"] is synthetic
    ]
    selected_screens = [item for item in screens if synthetic is None or item["synthetic"] is synthetic]
    if not selected_candidates:
        return {
            "candidate_intake_integrity": "not_evaluated",
            "pilot_screen_integrity": "not_evaluated",
            "pilot_slot_integrity": "not_evaluated",
            "no_selective_enrollment": "not_evaluated",
        }
    received_order = sorted(
        selected_candidates,
        key=lambda item: (_time(item["received_at"], "received_at"), item["candidate_id"]),
    )
    source_times = [_time(item["source_timestamp"], "source_timestamp") for item in received_order]
    intake_broken = (
        source_times != sorted(source_times)
        or any(item["intake_sequence_violation"] for item in selected_candidates)
        or any("INTAKE_SEQUENCE_VIOLATION" in item["failure_reasons"] for item in selected_screens)
        or len({item["identity_hash"] for item in selected_candidates}) != len(selected_candidates)
    )
    candidate_rank = {item["candidate_id"]: index for index, item in enumerate(received_order)}
    screen_order = sorted(
        selected_screens,
        key=lambda item: (_time(item["screened_at"], "screened_at"), item["screen_id"]),
    )
    ranks = [candidate_rank.get(item.get("candidate_id"), -1) for item in screen_order]
    screen_broken = (
        any(rank < 0 for rank in ranks)
        or ranks != sorted(ranks)
        or any("INTAKE_SEQUENCE_VIOLATION" in item["failure_reasons"] for item in selected_screens)
        or any(
            _time(item["screened_at"], "screened_at")
            < _time(next(candidate["received_at"] for candidate in selected_candidates if candidate["candidate_id"] == item.get("candidate_id")), "received_at")
            for item in screen_order
            if item.get("candidate_id") in candidate_rank
        )
        or len({item["candidate_id"] for item in selected_screens if item["eligibility_status"] == "eligible"})
        != sum(item["eligibility_status"] == "eligible" for item in selected_screens)
    )
    eligible_screens = [item for item in selected_screens if item["eligibility_status"] == "eligible"]
    case_ids = [item["candidate_case_id"] for item in eligible_screens]
    slot_pairs = [
        (item["synthetic"], item["simulated_slot"] if item["synthetic"] else item["assigned_real_slot"])
        for item in eligible_screens
        if (item["simulated_slot"] if item["synthetic"] else item["assigned_real_slot"]) is not None
    ]
    if len(case_ids) != len(set(case_ids)) or len(slot_pairs) != len(set(slot_pairs)):
        screen_broken = True
    cases = _phase3_list(store, "validation_case")
    predictions = _phase3_list(store, "validation_prediction")
    for screen in eligible_screens:
        screened_at = _time(screen["screened_at"], "screened_at")
        matching_cases = [item for item in cases if item["case_id"] == screen["candidate_case_id"]]
        if len(matching_cases) > 1 or any(
            _time(item["registered_at"], "registered_at") < screened_at for item in matching_cases
        ):
            screen_broken = True
        matching_predictions = [
            item for item in predictions if item["case_id"] == screen["candidate_case_id"]
        ]
        if any(
            _time(item["prediction_snapshot"]["freeze_timestamp"], "freeze_timestamp") <= screened_at
            for item in matching_predictions
        ):
            screen_broken = True
    slot_modes = [False, True] if synthetic is None else [synthetic]
    slot_broken = any(
        _slot_integrity(selected_screens, synthetic=mode, target=target)["selection_integrity_broken"]
        for mode in slot_modes
    )
    statuses = {
        "candidate_intake_integrity": "broken" if intake_broken else "pass",
        "pilot_screen_integrity": "broken" if screen_broken else "pass",
        "pilot_slot_integrity": "broken" if slot_broken else "pass",
    }
    statuses["no_selective_enrollment"] = all(value == "pass" for value in statuses.values())
    return statuses


def _candidate_view(candidate: dict[str, object], screens: list[dict[str, object]]) -> dict[str, object]:
    matches = [item for item in screens if item.get("candidate_id") == candidate["candidate_id"]]
    if not matches:
        return dict(candidate)
    latest = max(matches, key=lambda item: (_time(item["screened_at"], "screened_at"), item["screen_id"]))
    eligible = latest["eligibility_status"] == "eligible"
    return {
        **candidate,
        "consent_status": "granted" if latest["consent"]["granted"] is True else "denied",
        "privacy_status": "pass" if latest["deidentified"] is True else "fail",
        "input_gate_status": "pass" if latest["minimum_input_gate_passed"] is True else "fail",
        "pilot_screen_status": "eligible" if eligible else "ineligible",
        "screen_fail_reason": None if eligible else list(latest["failure_reasons"]),
        "registered_case_id": latest["candidate_case_id"] if eligible else None,
        "pilot_slot": latest["assigned_real_slot"],
        "simulated_slot": latest["simulated_slot"],
    }


def list_candidates(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(payload, {"batch_id"}, label="pilot-candidate-list")
    _batch(store, data["batch_id"])
    candidates = _candidate_records(store, data["batch_id"])
    screens = _screen_records(store, data["batch_id"])
    views = [_candidate_view(item, screens) for item in candidates]
    return {
        "batch_id": data["batch_id"],
        "candidate_total": len(views),
        "candidate_human_total": sum(item["human"] is True for item in views),
        "candidate_synthetic_total": sum(item["synthetic"] is True for item in views),
        "consent_granted": sum(item["consent_status"] == "granted" for item in views),
        "consent_denied": sum(item["consent_status"] == "denied" for item in views),
        "input_gate_pass": sum(item["input_gate_status"] == "pass" for item in views),
        "input_gate_fail": sum(item["input_gate_status"] == "fail" for item in views),
        "pilot_screen_eligible": sum(item["pilot_screen_status"] == "eligible" for item in views),
        "pilot_screen_ineligible": sum(item["pilot_screen_status"] == "ineligible" for item in views),
        "registered_to_pilot": sum(item["registered_case_id"] is not None for item in views),
        "not_yet_screened": sum(item["pilot_screen_status"] == "not_screened" for item in views),
        "sequence_violations": sum(item["intake_sequence_violation"] is True for item in views),
        "candidates": views,
    }


def show_candidate(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(payload, {"batch_id", "candidate_id"}, label="pilot-candidate-show")
    candidate = _candidate(store, data["batch_id"], data["candidate_id"])
    return _candidate_view(candidate, _screen_records(store, data["batch_id"]))


def screen_pilot_case(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    required = {
        "batch_id",
        "screen_id",
        "candidate_id",
        "candidate_case_id",
        "person_case_id",
        "source_timestamp",
        "screened_at",
        "synthetic",
        "engineering_dry_run",
        "consent",
        "deidentified",
        "minimum_input_gate_passed",
        "chart_gate_passed",
        "freeze_ready",
        "claim_counts",
        "case_role",
        "engine_version",
        "source_commit_sha",
        "rule_set_version",
        "input_manifest_sha",
        "visible_input_hash",
        "prediction_snapshot_hash",
    }
    data = _closed(payload, required, optional={"supersedes_screen_id"}, label="pilot-screen")
    batch = _batch(store, data["batch_id"])
    candidate = _candidate(store, data["batch_id"], data["candidate_id"])
    if candidate["intake_sequence_violation"] is True:
        _fail("CANDIDATE_INTAKE_SEQUENCE_VIOLATION", "事后补登记的 candidate 不得进入 Pilot")
    for field in (
        "screen_id",
        "candidate_id",
        "candidate_case_id",
        "person_case_id",
        "engine_version",
        "source_commit_sha",
        "rule_set_version",
    ):
        _text(data[field], field)
    for field in ("input_manifest_sha", "visible_input_hash", "prediction_snapshot_hash"):
        _sha(data[field], field)
    if _PERSON_ID.fullmatch(data["person_case_id"]) is None:
        _fail("INVALID_PERSON_CASE_ID", "person_case_id 必须是去标识化 SHA256 假名")
    if not store.synthetic and _CASE_ID.fullmatch(data["candidate_case_id"]) is None:
        _fail("INVALID_PILOT_CASE_ID", "真人 candidate_case_id 必须是去标识化 SHA256 假名")
    if data["case_role"] not in {"development", "pilot_evaluation", "holdout_evaluation"}:
        _fail("SCHEMA_INCOMPATIBLE", "case_role 不受支持")
    if data["synthetic"] is not store.synthetic:
        _fail("STORE_MODE_MISMATCH", "screen synthetic 标记必须匹配 store 模式")
    if store.synthetic and data["engineering_dry_run"] is not True:
        _fail("SYNTHETIC_DRY_RUN_REQUIRED", "synthetic screen 必须明确为 engineering_dry_run")
    if not store.synthetic and data["engineering_dry_run"] is not False:
        _fail("REAL_SCREEN_CANNOT_BE_DRY_RUN", "真实 screen 不能伪装为工程 dry run")
    if candidate["synthetic"] is not data["synthetic"] or candidate["human"] is data["synthetic"]:
        _fail("CANDIDATE_MODE_MISMATCH", "Candidate 与 screen 的 human/synthetic 模式不一致")
    if candidate["proposed_case_id"] != data["candidate_case_id"]:
        _fail("CANDIDATE_CASE_BINDING_MISMATCH", "screen case 必须匹配 intake 预留的去标识化 case")
    if candidate["source_timestamp"] != data["source_timestamp"]:
        _fail("CANDIDATE_SOURCE_TIME_MISMATCH", "screen 必须保留 candidate 原始 source_timestamp")
    existing = _screen_records(store, data["batch_id"])
    matching = [
        item
        for item in existing
        if item["candidate_case_id"] == data["candidate_case_id"]
        or item["person_case_id"] == data["person_case_id"]
        or item.get("candidate_id") == data["candidate_id"]
    ]
    if matching:
        latest = max(matching, key=lambda item: _time(item["screened_at"], "screened_at"))
        if (
            latest["eligibility_status"] != "screen_fail"
            or data.get("supersedes_screen_id") != latest["screen_id"]
            or data["candidate_case_id"] != latest["candidate_case_id"]
            or data["person_case_id"] != latest["person_case_id"]
            or data["source_timestamp"] != latest["source_timestamp"]
        ):
            _fail("DUPLICATE_PILOT_CANDIDATE", "重复筛选必须只追加修正后的 screen_fail，并保持候选身份与原始时间")
    elif data.get("supersedes_screen_id"):
        _fail("SCREEN_REVISION_NOT_FOUND", "supersedes_screen_id 没有对应的 screen_fail")
    source_time = _time(data["source_timestamp"], "source_timestamp")
    screened_at = _time(data["screened_at"], "screened_at")
    if screened_at < _time(candidate["received_at"], "candidate.received_at"):
        _fail("CANDIDATE_SCREEN_TIME_INVALID", "pilot-screen 必须晚于 candidate receipt")
    prior_case_state = _prior_candidate_state(store, data["candidate_case_id"])
    if screened_at < source_time:
        _fail("INVALID_TIME_ORDER", "screened_at 不能早于 source_timestamp")
    consent = _closed(
        data["consent"],
        {"granted", "scope", "recorded_at", "withdrawal_supported"},
        label="consent",
    )
    consent_at = _time(consent["recorded_at"], "consent.recorded_at")
    if not isinstance(consent["scope"], list) or any(not isinstance(item, str) for item in consent["scope"]):
        _fail("SCHEMA_INCOMPATIBLE", "consent.scope 必须是字符串数组")
    counts, reasons = _claim_counts(data["claim_counts"])
    if prior_case_state:
        reasons.append("INTAKE_SEQUENCE_VIOLATION")
    if candidate["consent_status"] == "denied":
        reasons.append("CONSENT_REQUIRED")
    if candidate["privacy_status"] == "fail":
        reasons.append("DEIDENTIFICATION_REQUIRED")
    if candidate["input_gate_status"] == "fail":
        reasons.append("INPUT_GATE_FAILED")
    if source_time < _time(batch["pilot_start_at"], "pilot_start_at"):
        reasons.append("BEFORE_PILOT_START")
    if consent_at > screened_at:
        reasons.append("CONSENT_TIME_INVALID")
    if consent["granted"] is not True or "deidentified_training_evaluation" not in consent["scope"]:
        reasons.append("CONSENT_REQUIRED")
    if consent["withdrawal_supported"] is not True:
        reasons.append("WITHDRAWAL_REQUIRED")
    for field, reason in (
        ("deidentified", "DEIDENTIFICATION_REQUIRED"),
        ("minimum_input_gate_passed", "INPUT_GATE_FAILED"),
        ("chart_gate_passed", "CHART_GATE_FAILED"),
        ("freeze_ready", "FREEZE_NOT_READY"),
    ):
        if data[field] is not True:
            reasons.append(reason)
    reasons = sorted(set(reasons))
    eligible = not reasons
    target = batch["target_real_cases"]
    prior_eligible = _eligible_screens(existing, synthetic=store.synthetic)
    next_slot = len(prior_eligible) + 1
    if eligible and next_slot > target:
        screen_status = "synthetic_pilot_full" if store.synthetic else "pilot_full"
        assigned_real_slot = None
        simulated_slot = None
    elif eligible and store.synthetic:
        screen_status = "synthetic_simulation_eligible"
        assigned_real_slot = None
        simulated_slot = next_slot
    elif eligible:
        screen_status = "enrolled"
        assigned_real_slot = next_slot
        simulated_slot = None
    else:
        screen_status = "synthetic_screen_fail" if store.synthetic else "screen_fail"
        assigned_real_slot = None
        simulated_slot = None
    return _save(
        store,
        "pilot_screen",
        data["screen_id"],
        {
            **data,
            "claim_counts": counts,
            "eligibility_status": "eligible" if eligible else "screen_fail",
            "failure_reasons": reasons,
            "screen_status": screen_status,
            "assigned_real_slot": assigned_real_slot,
            "simulated_slot": simulated_slot,
        },
        synthetic=store.synthetic,
        counts_toward_real_pilot=not store.synthetic and screen_status == "enrolled",
    )


def list_pilot(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(payload, {"batch_id"}, label="pilot-list")
    _batch(store, data["batch_id"])
    records = _screen_records(store, data["batch_id"])
    return {
        "batch_id": data["batch_id"],
        "real_screens": [item for item in records if item["synthetic"] is False],
        "engineering_simulations": [item for item in records if item["synthetic"] is True],
    }


def mature_claim(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(
        payload,
        {"batch_id", "maturity_id", "prediction_id", "claim_id", "as_of", "resolution", "synthetic"},
        label="pilot-mature",
    )
    batch = _batch(store, data["batch_id"])
    if data["synthetic"] is not True or not store.synthetic:
        _fail("SYNTHETIC_ONLY", "当前 maturity 入口只验证 synthetic Phase 3 工程记录")
    prediction = _phase3_read(store, "validation_prediction", data["prediction_id"])
    claim, _contract = _claim_record(prediction, data["claim_id"])
    if prediction["simulated_validation_track"] != "prospective":
        _fail("L3_REQUIRED", "Pilot maturity 仅适用于 L3 prospective claim")
    raw_end = claim["event_window"].split("/", 1)[1]
    end = datetime.fromisoformat(raw_end.replace("Z", "+00:00"))
    maturity = end + timedelta(days=batch["grace_period_days"])
    as_of = _time(data["as_of"], "as_of")
    observations = [
        item
        for item in _phase3_list(store, "validation_observation")
        if item["prediction_id"] == data["prediction_id"] and item["claim_id"] == data["claim_id"]
    ]
    if as_of < maturity.astimezone(as_of.tzinfo):
        if data["resolution"] != "pending":
            _fail("OUTCOME_PENDING", "grace period 到期前只能保持 pending")
        status = "pending"
    elif observations:
        if data["resolution"] != "with_feedback":
            _fail("FEEDBACK_RESOLUTION_REQUIRED", "已有事实反馈时必须进入人工结果裁决")
        status = "matured_with_feedback"
    else:
        if data["resolution"] == "miss":
            _fail("AUTO_MISS_FORBIDDEN", "成熟但无反馈不得自动记 miss")
        if data["resolution"] not in {"lost_to_followup", "awaiting_manual_confirmation"}:
            _fail("MATURE_RESOLUTION_REQUIRED", "成熟且无反馈时只能失访或等待人工确认")
        status = data["resolution"]
    return _save(
        store,
        "pilot_maturity",
        data["maturity_id"],
        {
            **data,
            "case_id": prediction["case_id"],
            "event_window": claim["event_window"],
            "maturity_at": maturity.isoformat(),
            "observation_count": len(observations),
            "maturity_status": status,
        },
        synthetic=True,
    )


def append_quality_feedback(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(
        payload,
        {
            "batch_id",
            "quality_feedback_id",
            "prediction_id",
            "collected_at",
            "labels",
            "raw_feedback_excerpt",
            "synthetic",
        },
        label="pilot-quality-append",
    )
    _batch(store, data["batch_id"])
    if data["synthetic"] is not True or not store.synthetic:
        _fail("SYNTHETIC_ONLY", "当前质量反馈入口只接收 synthetic 工程样例")
    _phase3_read(store, "validation_prediction", data["prediction_id"])
    _time(data["collected_at"], "collected_at")
    _text(data["raw_feedback_excerpt"], "raw_feedback_excerpt")
    if (
        not isinstance(data["labels"], list)
        or not data["labels"]
        or len(set(data["labels"])) != len(data["labels"])
        or any(item not in QUALITY_LABELS for item in data["labels"])
    ):
        _fail("SCHEMA_INCOMPATIBLE", "labels 必须是唯一的受控产品质量标签")
    return _save(
        store,
        "pilot_quality",
        data["quality_feedback_id"],
        data,
        synthetic=True,
    )


def freeze_revision(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(
        payload,
        {
            "batch_id",
            "revision_receipt_id",
            "freeze_payload",
            "revision_reason",
            "feedback_visibility_at_generation",
            "synthetic",
        },
        label="pilot-revision-freeze",
    )
    _batch(store, data["batch_id"])
    if data["synthetic"] is not True or not store.synthetic:
        _fail("SYNTHETIC_ONLY", "当前 revision 验收只接收 synthetic 工程样例")
    if not isinstance(data["revision_reason"], str) or not data["revision_reason"].strip():
        _fail("REVISION_REASON_REQUIRED", "Phase 4 revision 必须保留非空修改原因")
    _text(data["revision_reason"], "revision_reason")
    if data["feedback_visibility_at_generation"] not in {"hidden", "visible"}:
        _fail("SCHEMA_INCOMPATIBLE", "feedback_visibility_at_generation 不受支持")
    freeze_payload = data["freeze_payload"]
    if not isinstance(freeze_payload, Mapping) or not freeze_payload.get("revision_of"):
        _fail("REVISION_LINK_REQUIRED", "Phase 4 revision 必须显式绑定 v1")
    parent = _phase3_read(store, "validation_prediction", freeze_payload["revision_of"])
    revision = dispatch_phase3("freeze-prediction", freeze_payload, store=store)
    return _save(
        store,
        "pilot_revision",
        data["revision_receipt_id"],
        {
            "batch_id": data["batch_id"],
            "revision_receipt_id": data["revision_receipt_id"],
            "case_id": revision["case_id"],
            "parent_prediction_id": parent["prediction_id"],
            "revision_prediction_id": revision["prediction_id"],
            "parent_prediction_hash": parent["canonical_hash"],
            "revision_prediction_hash": revision["canonical_hash"],
            "revision_generated_at": revision["prediction_snapshot"]["generated_at"],
            "revision_reason": data["revision_reason"],
            "feedback_visibility_at_generation": data["feedback_visibility_at_generation"],
        },
        synthetic=True,
    )


def withdraw_pilot_case(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(
        payload,
        {"batch_id", "withdrawal_id", "person_case_id", "withdrawn_at", "source_withdrawal_ref", "synthetic"},
        label="pilot-withdraw",
    )
    batch = _batch(store, data["batch_id"])
    if data["synthetic"] is not store.synthetic:
        _fail("STORE_MODE_MISMATCH", "withdrawal synthetic 标记必须匹配 store 模式")
    _time(data["withdrawn_at"], "withdrawn_at")
    _sha(data["source_withdrawal_ref"], "source_withdrawal_ref")
    screens = [
        item
        for item in _screen_records(store, data["batch_id"])
        if item["person_case_id"] == data["person_case_id"]
        and item["eligibility_status"] == "eligible"
    ]
    if len(screens) != 1:
        _fail("ENROLLMENT_NOT_FOUND", "撤回必须绑定一个已入组或模拟入组记录")
    screen = screens[0]
    if any(item["person_case_id"] == data["person_case_id"] for item in _withdrawals(store, data["batch_id"])):
        _fail("DUPLICATE_WITHDRAWAL", "同一 Pilot case 只能保留一份撤回记录")
    slot = screen["simulated_slot"] if store.synthetic else screen["assigned_real_slot"]
    return _save(
        store,
        "pilot_withdrawal",
        data["withdrawal_id"],
        {
            **data,
            "assigned_real_slot": None if store.synthetic else slot,
            "simulated_slot": slot if store.synthetic else None,
            "slot_released": False,
            "withdrawal_status": "withdrawn",
            "pilot_target": batch["target_real_cases"],
        },
        synthetic=store.synthetic,
        counts_toward_real_pilot=not store.synthetic,
    )


def summarize_pilot(payload: Mapping[str, object], store: TrainingStore) -> dict[str, object]:
    data = _closed(payload, {"batch_id", "as_of"}, label="pilot-summary")
    batch = _batch(store, data["batch_id"])
    _time(data["as_of"], "as_of")
    screens = _screen_records(store, data["batch_id"])
    candidates = _candidate_records(store, data["batch_id"])
    candidate_ledger = list_candidates({"batch_id": data["batch_id"]}, store)
    withdrawals = _withdrawals(store, data["batch_id"])
    real_integrity = _slot_integrity(screens, synthetic=False, target=batch["target_real_cases"])
    simulated_integrity = _slot_integrity(screens, synthetic=True, target=batch["target_real_cases"])
    overall_candidate_integrity = _candidate_integrity(
        store, candidates, screens, synthetic=None, target=batch["target_real_cases"]
    )
    real_candidate_integrity = _candidate_integrity(
        store, candidates, screens, synthetic=False, target=batch["target_real_cases"]
    )
    simulated_candidate_integrity = _candidate_integrity(
        store, candidates, screens, synthetic=True, target=batch["target_real_cases"]
    )
    real_enrolled = [item for item in screens if item["screen_status"] == "enrolled"]
    withdrawn_real = {item["person_case_id"] for item in withdrawals if item["synthetic"] is False}
    active_real = [item for item in real_enrolled if item["person_case_id"] not in withdrawn_real]
    real_slots = [dict(item) for item in pilot_template()["slots"]]
    for item in real_enrolled:
        index = item["assigned_real_slot"] - 1
        real_slots[index] = {
            "slot": item["assigned_real_slot"],
            "case_id": item["person_case_id"],
            "status": "withdrawn" if item["person_case_id"] in withdrawn_real else "registered",
        }
    maturities = [
        item
        for item in _list(store, "pilot_maturity")
        if item["batch_id"] == data["batch_id"] and _time(item["as_of"], "as_of") <= _time(data["as_of"], "as_of")
    ]
    latest_maturity: dict[tuple[str, str], dict[str, object]] = {}
    for item in maturities:
        key = (item["prediction_id"], item["claim_id"])
        current = latest_maturity.get(key)
        if current is None or _time(item["as_of"], "as_of") > _time(current["as_of"], "as_of"):
            latest_maturity[key] = item
    quality = [
        item
        for item in _list(store, "pilot_quality")
        if item["batch_id"] == data["batch_id"] and _time(item["collected_at"], "collected_at") <= _time(data["as_of"], "as_of")
    ]
    quality_counts = {label: sum(label in item["labels"] for item in quality) for label in sorted(QUALITY_LABELS)}
    phase3 = phase3_validation_summary({"as_of": data["as_of"]}, store)
    synthetic_l2 = dict(phase3["pools"]["L2"]["synthetic_claim_counts"])
    synthetic_l3 = dict(phase3["pools"]["L3"]["synthetic_claim_counts"])
    for item in latest_maturity.values():
        status = item["maturity_status"]
        if status == "pending" and synthetic_l3["missing"] > 0:
            synthetic_l3["missing"] -= 1
            synthetic_l3["pending"] += 1
        elif status == "lost_to_followup":
            if synthetic_l3["missing"] > 0:
                synthetic_l3["missing"] -= 1
            elif synthetic_l3["pending"] > 0:
                synthetic_l3["pending"] -= 1
            synthetic_l3["lost_to_followup"] += 1
    synthetic_l3["matured"] = sum(item["maturity_status"] != "pending" for item in latest_maturity.values())
    real_l2_claims = sum(item["claim_counts"]["L2"] for item in active_real)
    real_l3_claims = sum(item["claim_counts"]["L3"] for item in active_real)
    return {
        "schema_version": VERSION,
        "batch_id": data["batch_id"],
        "as_of": data["as_of"],
        "pilot_target": batch["target_real_cases"],
        "pilot_start_at": batch["pilot_start_at"],
        "grace_period_days": batch["grace_period_days"],
        "registered_real_cases": len(real_enrolled),
        "eligible_real_cases": len(active_real),
        "screen_failed_real_cases": sum(item["screen_status"] == "screen_fail" for item in screens),
        "withdrawn_real_cases": len(withdrawn_real),
        "synthetic_real_mix": any(item["synthetic"] is True and item["assigned_real_slot"] is not None for item in screens),
        "candidate_intake": {key: value for key, value in candidate_ledger.items() if key not in {"batch_id", "candidates"}},
        "candidate_intake_integrity": overall_candidate_integrity["candidate_intake_integrity"],
        "pilot_screen_integrity": overall_candidate_integrity["pilot_screen_integrity"],
        "pilot_slot_integrity": overall_candidate_integrity["pilot_slot_integrity"],
        "no_selective_enrollment": overall_candidate_integrity["no_selective_enrollment"],
        "selection_integrity_broken": real_integrity["selection_integrity_broken"],
        "real_pilot_integrity": real_candidate_integrity,
        "real_slots": real_slots,
        "L2": {
            "eligible_claims": real_l2_claims,
            "hit": 0,
            "partial": 0,
            "miss": 0,
            "unverifiable": 0,
        },
        "L3": {
            "eligible_claims": real_l3_claims,
            "pending": real_l3_claims,
            "matured": 0,
            "hit": 0,
            "partial": 0,
            "miss": 0,
            "unverifiable": 0,
            "lost_to_followup": 0,
        },
        "quality_feedback": {"population": "real_pilot_only", **{label: 0 for label in sorted(QUALITY_LABELS)}},
        "engineering_simulation": {
            "eligible_screens": simulated_integrity["eligible_screens"],
            "simulated_slots_used": simulated_integrity["slots_used"],
            "no_selective_enrollment": simulated_integrity["no_selective_enrollment"],
            "selection_integrity_broken": simulated_integrity["selection_integrity_broken"],
            **simulated_candidate_integrity,
            "withdrawn": sum(item["synthetic"] is True for item in withdrawals),
            "L2": synthetic_l2,
            "L3": synthetic_l3,
            "quality_feedback": quality_counts,
            "counts_toward_real_pilot": False,
        },
        "accuracy": None,
        "metrics": None,
        "status": "not_evaluated",
        "product_accuracy_claim_allowed": False,
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
    }


def dispatch_phase4(command: str, payload: Mapping[str, object], *, store: TrainingStore) -> dict[str, object]:
    handlers = {
        "pilot-candidate-intake": intake_candidate,
        "pilot-candidate-list": list_candidates,
        "pilot-candidate-show": show_candidate,
        "pilot-start": start_pilot,
        "pilot-screen": screen_pilot_case,
        "pilot-list": list_pilot,
        "pilot-mature": mature_claim,
        "pilot-quality-append": append_quality_feedback,
        "pilot-revision-freeze": freeze_revision,
        "pilot-summary": summarize_pilot,
        "pilot-withdraw": withdraw_pilot_case,
    }
    if command not in handlers:
        _fail("UNKNOWN_COMMAND", "未知 Phase 4 命令")
    return handlers[command](payload, store)


__all__ = [
    "PHASE4_COMMANDS",
    "QUALITY_LABELS",
    "VERSION",
    "dispatch_phase4",
    "intake_candidate",
    "list_candidates",
    "screen_pilot_case",
    "start_pilot",
    "summarize_pilot",
]
