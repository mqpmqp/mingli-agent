from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
import re
from threading import RLock
from typing import Mapping, Sequence, cast

from .contracts import canonical_json, digest
from .training import TrainingError, TrainingStore
from .validation_privacy import scan_for_pii


PHASE4_1_VERSION = "mingli-phase4.1-pilot@1.0"
_CANDIDATE_ID = re.compile(r"^candidate:[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^person:[0-9a-f]{64}$")
_PREDICTION_ID = re.compile(r"^prediction:[0-9a-f]{64}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_PRIOR_STAGES = frozenset(
    {"none", "prediction_created", "prediction_frozen", "feedback_received"}
)
_KINDS = {
    "candidate": "phase4_1_candidate_intakes",
    "screen": "phase4_1_screens",
    "prediction": "phase4_1_predictions",
    "feedback": "phase4_1_feedback",
    "retrospective": "phase4_1_retrospective_audits",
}
_HASH_RECORD_TYPES = {
    "practice_phase4_candidate_intake": "Phase41CandidateIntake",
    "practice_phase4_pilot_screen": "Phase41PilotScreen",
    "practice_phase4_frozen_prediction": "Phase41FrozenPrediction",
    "practice_phase4_feedback": "Phase41Feedback",
    "practice_phase4_retrospective_audit": "Phase41RetrospectiveAudit",
}
_PHASE4_1_LOCK = RLock()


def _record_name(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest() + ".json"


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise TrainingError("PHASE4_1_INVALID_TIMESTAMP", f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrainingError("PHASE4_1_INVALID_TIMESTAMP", f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise TrainingError("PHASE4_1_INVALID_TIMESTAMP", f"{field} must include a timezone")
    return parsed


def _enum(value: object, allowed: frozenset[str], *, field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise TrainingError(
            "PHASE4_1_INVALID_FIELD",
            f"{field} must be one of {', '.join(sorted(allowed))}",
            field_path=f"$.{field}",
        )
    return value


def _identifier(value: object, pattern: re.Pattern[str], *, field: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise TrainingError(
            "PHASE4_1_INVALID_ID",
            f"{field} must be a deidentified SHA-256 identifier",
            field_path=f"$.{field}",
        )
    return value


def _codes(value: object, *, field: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TrainingError("PHASE4_1_INVALID_FIELD", f"{field} must be an array")
    result = [str(item) for item in value]
    if any(not item or len(item) > 128 for item in result):
        raise TrainingError("PHASE4_1_INVALID_FIELD", f"{field} entries must contain 1 to 128 characters")
    return result


class Phase41Pilot:
    """Append-only, deidentified Phase 4.1 intake and validation ledger."""

    def __init__(self, store: TrainingStore) -> None:
        self.store = store
        self.root = store.root
        self._lock = _PHASE4_1_LOCK

    def _path(self, kind: str, identifier: str) -> Path:
        return self.root / _KINDS[kind] / _record_name(identifier)

    def _validate_privacy(self, value: Mapping[str, object]) -> dict[str, object]:
        payload = cast(dict[str, object], json.loads(canonical_json(value)))
        findings = scan_for_pii(payload)
        if findings:
            raise TrainingError(
                "PII_DETECTED",
                "Phase 4.1 records may contain only deidentified fields and evidence codes",
                field_path=findings[0].field_path,
            )
        return payload

    def _verify_integrity(self, value: Mapping[str, object]) -> dict[str, object]:
        payload = self._validate_privacy(value)
        record_type = _HASH_RECORD_TYPES.get(str(payload.get("record_type", "")))
        stored_hash = payload.get("canonical_hash")
        body = {key: item for key, item in payload.items() if key != "canonical_hash"}
        expected_hash = (
            digest({"record_type": record_type, "payload": body})
            if record_type is not None
            else None
        )
        if expected_hash is None or stored_hash != expected_hash:
            raise TrainingError(
                "PHASE4_1_INTEGRITY_FAILED",
                "record type or canonical hash does not match stored content",
            )
        return payload

    def _write(self, kind: str, identifier: str, value: Mapping[str, object]) -> tuple[dict[str, object], bool]:
        payload = self._validate_privacy(value)
        target = self._path(kind, identifier)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(payload) + "\n")
            return payload, True
        except FileExistsError:
            existing = self._read(kind, identifier)
            if existing == payload:
                return existing, False
            raise TrainingError(
                "PHASE4_1_IMMUTABLE_CONFLICT",
                f"{kind} record already exists with different content",
            )

    def _read(self, kind: str, identifier: str) -> dict[str, object]:
        path = self._path(kind, identifier)
        if not path.is_file():
            raise TrainingError("PHASE4_1_RECORD_NOT_FOUND", f"{kind} record was not found")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TrainingError("PHASE4_1_INTEGRITY_FAILED", f"{kind} record is not an object")
        return self._verify_integrity(value)

    def _list(self, kind: str) -> list[dict[str, object]]:
        directory = self.root / _KINDS[kind]
        if not directory.is_dir():
            return []
        records: list[dict[str, object]] = []
        for path in sorted(directory.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise TrainingError("PHASE4_1_INTEGRITY_FAILED", f"invalid record: {path.name}")
            records.append(self._verify_integrity(value))
        return records

    def intake(self, value: Mapping[str, object]) -> dict[str, object]:
        candidate_id = _identifier(value.get("candidate_id"), _CANDIDATE_ID, field="candidate_id")
        received_at = str(value.get("received_at", ""))
        source_timestamp = str(value.get("source_timestamp", ""))
        _timestamp(received_at, field="received_at")
        if _timestamp(source_timestamp, field="source_timestamp") > _timestamp(received_at, field="received_at"):
            raise TrainingError("PHASE4_1_TIME_ORDER", "source_timestamp cannot be after received_at")
        human = value.get("human") is True
        synthetic = value.get("synthetic") is True
        if human == synthetic:
            raise TrainingError("PHASE4_1_INVALID_SUBJECT", "exactly one of human or synthetic must be true")
        consent_status = _enum(
            value.get("consent_status"), frozenset({"unknown", "granted", "denied"}), field="consent_status"
        )
        privacy_status = _enum(
            value.get("privacy_status"), frozenset({"pending", "pass", "fail"}), field="privacy_status"
        )
        input_gate_status = _enum(
            value.get("input_gate_status"), frozenset({"pending", "pass", "fail"}), field="input_gate_status"
        )
        prior_stage = _enum(value.get("prior_stage", "none"), _PRIOR_STAGES, field="prior_stage")
        violation = prior_stage != "none"
        body: dict[str, object] = {
            "record_type": "practice_phase4_candidate_intake",
            "schema_version": PHASE4_1_VERSION,
            "candidate_id": candidate_id,
            "received_at": received_at,
            "source_timestamp": source_timestamp,
            "human": human,
            "synthetic": synthetic,
            "consent_status": consent_status,
            "privacy_status": privacy_status,
            "input_gate_status": input_gate_status,
            "prior_stage": prior_stage,
            "intake_sequence_violation": violation,
        }
        body["canonical_hash"] = digest({"record_type": "Phase41CandidateIntake", "payload": body})
        with self._lock:
            record, created = self._write("candidate", candidate_id, body)
        return {
            "status": "accepted_for_audit" if violation else "accepted",
            "created": created,
            "candidate": record,
            "eligible_for_pilot": False if violation else None,
            "commercial_release_hold": "ACTIVE",
        }

    def screen(self, value: Mapping[str, object]) -> dict[str, object]:
        candidate_id = _identifier(value.get("candidate_id"), _CANDIDATE_ID, field="candidate_id")
        screened_at = str(value.get("screened_at", ""))
        screened_time = _timestamp(screened_at, field="screened_at")
        with self._lock:
            candidate = self._read("candidate", candidate_id)
            if candidate.get("intake_sequence_violation") is True:
                raise TrainingError(
                    "PHASE4_1_SEQUENCE_VIOLATION",
                    "a candidate received after prediction or feedback cannot enter the pilot",
                )
            if screened_time < _timestamp(candidate["received_at"], field="received_at"):
                raise TrainingError("PHASE4_1_TIME_ORDER", "screened_at cannot be before received_at")
            failures: list[str] = []
            if candidate.get("consent_status") != "granted":
                failures.append("consent_not_granted")
            if candidate.get("privacy_status") != "pass":
                failures.append("privacy_gate_failed")
            if candidate.get("input_gate_status") != "pass":
                failures.append("input_gate_failed")
            if candidate.get("human") is not True or candidate.get("synthetic") is True:
                failures.append("not_a_real_human_case")
            body: dict[str, object] = {
                "record_type": "practice_phase4_pilot_screen",
                "schema_version": PHASE4_1_VERSION,
                "candidate_id": candidate_id,
                "screened_at": screened_at,
                "pilot_screen_status": "ineligible" if failures else "eligible",
                "screen_fail_reasons": failures,
            }
            body["canonical_hash"] = digest({"record_type": "Phase41PilotScreen", "payload": body})
            record, created = self._write("screen", candidate_id, body)
        return {"status": "screened", "created": created, "screen": record}

    def freeze_prediction(self, value: Mapping[str, object]) -> dict[str, object]:
        candidate_id = _identifier(value.get("candidate_id"), _CANDIDATE_ID, field="candidate_id")
        case_id = _identifier(value.get("case_id"), _CASE_ID, field="case_id")
        prediction_id = _identifier(value.get("prediction_id"), _PREDICTION_ID, field="prediction_id")
        frozen_at = str(value.get("frozen_at", ""))
        frozen_time = _timestamp(frozen_at, field="frozen_at")
        manifest_hash = _identifier(
            value.get("prediction_manifest_hash"), _SHA256, field="prediction_manifest_hash"
        )
        rule_set_version = value.get("rule_set_version")
        if not isinstance(rule_set_version, str) or not rule_set_version.strip():
            raise TrainingError("PHASE4_1_INVALID_FIELD", "rule_set_version is required")
        claim_ids = _codes(value.get("claim_ids", []), field="claim_ids")
        if not claim_ids:
            raise TrainingError("PHASE4_1_INVALID_FIELD", "at least one frozen claim_id is required")
        with self._lock:
            candidate = self._read("candidate", candidate_id)
            screen = self._read("screen", candidate_id)
            if candidate.get("intake_sequence_violation") is True or screen.get("pilot_screen_status") != "eligible":
                raise TrainingError("PHASE4_1_NOT_ELIGIBLE", "candidate is not eligible for a real pilot slot")
            if frozen_time <= _timestamp(screen["screened_at"], field="screened_at"):
                raise TrainingError("PHASE4_1_TIME_ORDER", "frozen_at must be after screened_at")
            predictions = self._list("prediction")
            existing_prediction = next(
                (item for item in predictions if item.get("prediction_id") == prediction_id),
                None,
            )
            if existing_prediction is not None:
                expected = {
                    "candidate_id": candidate_id,
                    "case_id": case_id,
                    "frozen_at": frozen_at,
                    "prediction_manifest_hash": manifest_hash,
                    "rule_set_version": rule_set_version,
                    "claim_ids": claim_ids,
                }
                if all(existing_prediction.get(key) == item for key, item in expected.items()):
                    return {"status": "frozen", "created": False, "prediction": existing_prediction}
                raise TrainingError(
                    "PHASE4_1_IMMUTABLE_CONFLICT",
                    "prediction record already exists with different content",
                )
            if any(item.get("candidate_id") == candidate_id and item.get("prediction_id") != prediction_id for item in predictions):
                raise TrainingError("PHASE4_1_CANDIDATE_ALREADY_BOUND", "candidate is already bound to a prediction")
            if any(item.get("case_id") == case_id and item.get("prediction_id") != prediction_id for item in predictions):
                raise TrainingError("PHASE4_1_CASE_ALREADY_BOUND", "case is already bound to another candidate")
            slot = f"slot_{len(predictions) + 1:02d}"
            body: dict[str, object] = {
                "record_type": "practice_phase4_frozen_prediction",
                "schema_version": PHASE4_1_VERSION,
                "prediction_id": prediction_id,
                "candidate_id": candidate_id,
                "case_id": case_id,
                "pilot_slot": slot,
                "frozen_at": frozen_at,
                "prediction_manifest_hash": manifest_hash,
                "rule_set_version": rule_set_version,
                "claim_ids": claim_ids,
                "counts_toward_registered_real_cases": True,
            }
            body["canonical_hash"] = digest({"record_type": "Phase41FrozenPrediction", "payload": body})
            record, created = self._write("prediction", prediction_id, body)
        return {"status": "frozen", "created": created, "prediction": record}

    def add_feedback(self, value: Mapping[str, object]) -> dict[str, object]:
        feedback_id = _identifier(value.get("feedback_id"), _SHA256, field="feedback_id")
        prediction_id = _identifier(value.get("prediction_id"), _PREDICTION_ID, field="prediction_id")
        submitted_at = str(value.get("submitted_at", ""))
        submitted_time = _timestamp(submitted_at, field="submitted_at")
        evidence_codes = _codes(value.get("evidence_codes", []), field="evidence_codes")
        with self._lock:
            prediction = self._read("prediction", prediction_id)
            if submitted_time < _timestamp(prediction["frozen_at"], field="frozen_at"):
                raise TrainingError("PHASE4_1_TIME_ORDER", "feedback cannot precede prediction freeze")
            body: dict[str, object] = {
                "record_type": "practice_phase4_feedback",
                "schema_version": PHASE4_1_VERSION,
                "feedback_id": feedback_id,
                "prediction_id": prediction_id,
                "candidate_id": prediction["candidate_id"],
                "case_id": prediction["case_id"],
                "submitted_at": submitted_at,
                "evidence_codes": evidence_codes,
                "review_status": "pending_independent_review",
                "counts_toward_accuracy": False,
            }
            body["canonical_hash"] = digest({"record_type": "Phase41Feedback", "payload": body})
            record, created = self._write("feedback", feedback_id, body)
        return {"status": "accepted", "created": created, "feedback": record}

    def add_retrospective_audit(self, value: Mapping[str, object]) -> dict[str, object]:
        candidate_id = _identifier(value.get("candidate_id"), _CANDIDATE_ID, field="candidate_id")
        recorded_at = str(value.get("recorded_at", ""))
        recorded_time = _timestamp(recorded_at, field="recorded_at")
        evidence_codes = _codes(value.get("evidence_codes", []), field="evidence_codes")
        topic_codes = _codes(value.get("topic_codes", []), field="topic_codes")
        with self._lock:
            candidate = self._read("candidate", candidate_id)
            if candidate.get("human") is not True or candidate.get("intake_sequence_violation") is not True:
                raise TrainingError(
                    "PHASE4_1_RETROSPECTIVE_NOT_ALLOWED",
                    "retrospective audit is reserved for human sequence-violation cases",
                )
            if candidate.get("consent_status") != "granted":
                raise TrainingError("TRAINING_CONSENT_NOT_GRANTED", "training consent is required")
            if recorded_time < _timestamp(candidate["received_at"], field="received_at"):
                raise TrainingError("PHASE4_1_TIME_ORDER", "recorded_at cannot be before received_at")
            body: dict[str, object] = {
                "record_type": "practice_phase4_retrospective_audit",
                "schema_version": PHASE4_1_VERSION,
                "candidate_id": candidate_id,
                "recorded_at": recorded_at,
                "topic_codes": topic_codes,
                "evidence_codes": evidence_codes,
                "intake_sequence_violation": True,
                "counts_toward_observed_real_cases": True,
                "counts_toward_registered_real_cases": False,
                "counts_toward_accuracy": False,
                "review_status": "audit_only",
            }
            body["canonical_hash"] = digest({"record_type": "Phase41RetrospectiveAudit", "payload": body})
            record, created = self._write("retrospective", candidate_id, body)
        return {"status": "accepted_for_audit", "created": created, "audit": record}

    def status(self) -> dict[str, object]:
        with self._lock:
            candidates = self._list("candidate")
            screens = self._list("screen")
            predictions = self._list("prediction")
            feedback = self._list("feedback")
            retrospectives = self._list("retrospective")
        sequence_violations = sum(item.get("intake_sequence_violation") is True for item in candidates)
        human_candidates = [item for item in candidates if item.get("human") is True]
        screen_by_candidate = {str(item["candidate_id"]): item for item in screens}
        eligible = [item for item in screens if item.get("pilot_screen_status") == "eligible"]
        ineligible = [item for item in screens if item.get("pilot_screen_status") == "ineligible"]
        expected_slots = [f"slot_{index:02d}" for index in range(1, len(predictions) + 1)]
        actual_slots = [str(item.get("pilot_slot")) for item in sorted(predictions, key=lambda item: str(item.get("pilot_slot")))]
        intake_integrity: str = "not_evaluated" if not candidates else ("broken" if sequence_violations else "pass")
        screen_integrity: str = "not_evaluated" if not screens else "pass"
        slot_integrity: str = "not_evaluated" if not predictions else ("pass" if actual_slots == expected_slots else "broken")
        no_selective_enrollment: bool | str
        if not candidates:
            no_selective_enrollment = "not_evaluated"
        else:
            no_selective_enrollment = (
                intake_integrity == "pass"
                and slot_integrity in {"pass", "not_evaluated"}
                and all(
                    str(item["candidate_id"]) in screen_by_candidate
                    or item.get("consent_status") == "unknown"
                    or item.get("privacy_status") == "pending"
                    or item.get("input_gate_status") == "pending"
                    for item in candidates
                )
            )
        validation = {
            "pilot_target": 10,
            "registered_real_cases": len(predictions),
            "eligible_real_cases": len(eligible),
            "observed_real_cases": len(predictions) + len(retrospectives),
            "accuracy": None,
            "prediction_validity": "not_evaluated",
            "product_accuracy_claim_allowed": False,
            "commercial_release_hold": "ACTIVE",
        }
        return {
            "schema_version": PHASE4_1_VERSION,
            "candidate_ledger": {
                "candidate_total": len(candidates),
                "candidate_human_total": len(human_candidates),
                "candidate_synthetic_total": len(candidates) - len(human_candidates),
                "consent_granted": sum(item.get("consent_status") == "granted" for item in candidates),
                "consent_denied": sum(item.get("consent_status") == "denied" for item in candidates),
                "input_gate_pass": sum(item.get("input_gate_status") == "pass" for item in candidates),
                "input_gate_fail": sum(item.get("input_gate_status") == "fail" for item in candidates),
                "pilot_screen_eligible": len(eligible),
                "pilot_screen_ineligible": len(ineligible),
                "registered_to_pilot": len(predictions),
                "not_yet_screened": len(candidates) - len(screens),
                "sequence_violations": sequence_violations,
                "feedback_records": len(feedback),
                "retrospective_audits": len(retrospectives),
            },
            "integrity": {
                "candidate_intake_integrity": intake_integrity,
                "pilot_screen_integrity": screen_integrity,
                "pilot_slot_integrity": slot_integrity,
                "no_selective_enrollment": no_selective_enrollment,
            },
            "phase4_1_validation": validation,
        }


__all__ = ["PHASE4_1_VERSION", "Phase41Pilot"]
