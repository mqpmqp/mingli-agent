from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from .contracts import canonical_json, digest, get_schema
from .validation_privacy import scan_for_pii


TRAINING_SCHEMA_VERSION = "mingli-training-loop@1.0"
_CASE_ID = re.compile(r"^person:[0-9a-f]{64}$")
_KINDS = {
    "case": "cases",
    "run": "runs",
    "feedback": "feedback",
    "outcome": "outcomes",
    "candidate": "candidates",
    "iteration": "iterations",
}
_SCHEMAS = {
    "case": "training_case.schema.json",
    "run": "analysis_run.schema.json",
    "feedback": "user_feedback.schema.json",
    "outcome": "outcome_observation.schema.json",
    "candidate": "rule_review_candidate.schema.json",
    "iteration": "training_iteration.schema.json",
}


class TrainingError(ValueError):
    def __init__(self, code: str, message: str, *, field_path: str | None = None, exit_code: int = 2) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.field_path = field_path
        self.exit_code = exit_code

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"code": self.code, "message": self.message}
        if self.field_path is not None:
            result["field_path"] = self.field_path
        return result


def _record_name(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier or len(identifier) > 256:
        raise TrainingError("INVALID_RECORD_ID", "record id must be a non-empty string of at most 256 characters")
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest() + ".json"


def _case_ref_hash(case_id: str) -> str:
    return hashlib.sha256(case_id.encode("utf-8")).hexdigest()


def _plain_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return json.loads(canonical_json(value))


class TrainingStore:
    """Auditable JSON store. Real stores must resolve outside the repository."""

    def __init__(self, root: Path | str, *, repository_root: Path | str, synthetic: bool = False) -> None:
        self.root = Path(root).expanduser().resolve()
        self.repository_root = Path(repository_root).expanduser().resolve()
        self.synthetic = synthetic
        if not synthetic and (self.root == self.repository_root or self.repository_root in self.root.parents):
            raise TrainingError(
                "TRAINING_STORE_INSIDE_REPOSITORY",
                "real training store must be outside the Git repository; use synthetic mode only for fixtures",
                field_path="$.store",
            )

    def _path(self, kind: str, identifier: str) -> Path:
        return self.root / _KINDS[kind] / _record_name(identifier)

    def _validate(self, kind: str, value: Mapping[str, object]) -> dict[str, object]:
        payload = _plain_mapping(value)
        findings = scan_for_pii(payload)
        if findings:
            raise TrainingError(
                "PII_DETECTED",
                "record contains a forbidden direct identifier or identifier-like value",
                field_path=findings[0].field_path,
            )
        validator = Draft202012Validator(get_schema(_SCHEMAS[kind]), format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
        if errors:
            error = errors[0]
            path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
            raise TrainingError("SCHEMA_INCOMPATIBLE", error.message, field_path=path)
        return payload

    def _write(self, kind: str, identifier: str, payload: Mapping[str, object]) -> dict[str, object]:
        validated = self._validate(kind, payload)
        target = self._path(kind, identifier)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(validated) + "\n")
        except FileExistsError as exc:
            raise TrainingError("DUPLICATE_RECORD", f"{kind} record already exists") from exc
        return validated

    def _replace(self, kind: str, identifier: str, payload: Mapping[str, object]) -> dict[str, object]:
        validated = self._validate(kind, payload)
        target = self._path(kind, identifier)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(canonical_json(validated) + "\n", encoding="utf-8", newline="\n")
        temporary.replace(target)
        return validated

    def _read(self, kind: str, identifier: str) -> dict[str, object]:
        target = self._path(kind, identifier)
        if not target.is_file():
            raise TrainingError("RECORD_NOT_FOUND", f"{kind} record was not found")
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TrainingError("SCHEMA_INCOMPATIBLE", f"{kind} record must be an object")
        return value

    def _list(self, kind: str) -> list[dict[str, object]]:
        directory = self.root / _KINDS[kind]
        if not directory.is_dir():
            return []
        records: list[dict[str, object]] = []
        for path in sorted(directory.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                records.append(value)
        return records

    def _audit(self, action: str, case_id: str, *, occurred_at: str, details: Mapping[str, object] | None = None) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        record = {
            "action": action,
            "case_ref_hash": _case_ref_hash(case_id),
            "occurred_at": occurred_at,
            "details": dict(details or {}),
            "schema_version": TRAINING_SCHEMA_VERSION,
        }
        findings = scan_for_pii(record)
        if findings:
            raise TrainingError("PII_DETECTED", "audit record contains forbidden PII")
        with (self.root / "audit.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(record) + "\n")

    def create_case(self, value: Mapping[str, object]) -> dict[str, object]:
        case_id = str(value.get("case_id", ""))
        if _CASE_ID.fullmatch(case_id) is None:
            raise TrainingError("INVALID_CASE_ID", "case_id must be an HMAC-SHA256 person pseudonym", field_path="$.case_id")
        scopes = value.get("consent_scope")
        if not isinstance(scopes, Sequence) or isinstance(scopes, (str, bytes)) or "training" not in scopes:
            raise TrainingError("TRAINING_CONSENT_NOT_GRANTED", "training scope is required before creating a training case")
        result = self._write("case", case_id, value)
        self._audit("CASE_CREATED", case_id, occurred_at=str(result["created_at"]))
        return result

    def show_case(self, case_id: str) -> dict[str, object]:
        tombstone = self.root / "tombstones" / _record_name(case_id)
        if tombstone.exists():
            raise TrainingError("CASE_WITHDRAWN", "case consent was withdrawn and derived records were invalidated")
        case = self._read("case", case_id)
        return {
            "case": case,
            "runs": [item for item in self._list("run") if item.get("case_id") == case_id],
            "feedback": [item for item in self._list("feedback") if item.get("case_id") == case_id],
            "outcomes": [item for item in self._list("outcome") if item.get("case_id") == case_id],
            "candidates": [item for item in self._list("candidate") if case_id in item.get("source_case_ids", [])],
        }

    def save_analysis_run(self, value: Mapping[str, object]) -> dict[str, object]:
        case_id = str(value.get("case_id", ""))
        case = self._read("case", case_id)
        if case.get("lifecycle") != "active":
            raise TrainingError("CASE_WITHDRAWN", "analysis cannot be saved for an inactive case")
        result = self._write("run", str(value.get("run_id", "")), value)
        case.update({
            "runtime_output_ref": result["output_manifest_hash"],
            "confidence": result["confidence"],
        })
        self._replace("case", case_id, case)
        self._audit("ANALYSIS_RUN_SAVED", case_id, occurred_at=str(result["created_at"]), details={"run_ref_hash": digest(str(result["run_id"]))})
        return result

    def add_feedback(self, value: Mapping[str, object]) -> dict[str, object]:
        payload = {**value, "counts_toward_accuracy": False, "valid": True}
        case_id = str(payload.get("case_id", ""))
        self.show_case(case_id)
        run = self._read("run", str(payload.get("run_id", "")))
        if run.get("case_id") != case_id:
            raise TrainingError("RUN_CASE_MISMATCH", "feedback run_id does not belong to case_id")
        result = self._write("feedback", str(payload.get("feedback_id", "")), payload)
        case = self._read("case", case_id)
        case["feedback_status"] = "received"
        self._replace("case", case_id, case)
        self._audit("FEEDBACK_ADDED", case_id, occurred_at=str(result["submitted_at"]))
        return result

    def add_outcome(self, value: Mapping[str, object]) -> dict[str, object]:
        preregistered = bool(
            value.get("relation_to_prior_claim") == "preregistered_claim_outcome"
            and value.get("preregistered_claim_id")
            and value.get("source_reliability") == "independently_verified"
        )
        payload = {**value, "commercial_validation_eligible": preregistered, "valid": True}
        case_id = str(payload.get("case_id", ""))
        self.show_case(case_id)
        run = self._read("run", str(payload.get("run_id", "")))
        if run.get("case_id") != case_id:
            raise TrainingError("RUN_CASE_MISMATCH", "outcome run_id does not belong to case_id")
        result = self._write("outcome", str(payload.get("outcome_id", "")), payload)
        case = self._read("case", case_id)
        case["outcome_status"] = "observed"
        self._replace("case", case_id, case)
        self._audit("OUTCOME_ADDED", case_id, occurred_at=str(result["observed_at"]))
        return result

    def create_rule_candidate(self, value: Mapping[str, object]) -> dict[str, object]:
        if value.get("review_state") != "pending_human_review":
            raise TrainingError("HUMAN_REVIEW_REQUIRED", "new rule candidates must start pending human review")
        payload = {**value, "applied_to_rules": False, "valid": True}
        case_ids = payload.get("source_case_ids", [])
        if not isinstance(case_ids, list):
            raise TrainingError("SCHEMA_INCOMPATIBLE", "source_case_ids must be an array")
        for case_id in case_ids:
            self.show_case(str(case_id))
        result = self._write("candidate", str(payload.get("candidate_id", "")), payload)
        for case_id in case_ids:
            case = self._read("case", str(case_id))
            case["review_status"] = "in_review"
            self._replace("case", str(case_id), case)
        return result

    def create_iteration(self, value: Mapping[str, object]) -> dict[str, object]:
        payload = {**value, "valid": True}
        return self._write("iteration", str(payload.get("iteration_id", "")), payload)

    def generate_rule_candidates(self, *, created_at: str) -> list[dict[str, object]]:
        """Create review-only candidates from explicit negative/correction feedback."""
        created: list[dict[str, object]] = []
        for feedback in self._list("feedback"):
            has_review_signal = bool(
                feedback.get("inaccurate_sections")
                or feedback.get("missing_context")
                or feedback.get("feedback_kind") == "historical_correction"
            )
            if feedback.get("valid") is not True or not has_review_signal:
                continue
            feedback_id = str(feedback["feedback_id"])
            candidate_id = "candidate-" + digest({"record_type": "FeedbackCandidate", "payload": feedback_id})[7:23]
            if self._path("candidate", candidate_id).exists():
                continue
            failure_mode = "historical-context-correction" if feedback.get("feedback_kind") == "historical_correction" else "section-or-context-mismatch"
            created.append(self.create_rule_candidate({
                "candidate_id": candidate_id,
                "source_case_ids": [str(feedback["case_id"])],
                "suspected_failure_mode": failure_mode,
                "current_rule_ids": [],
                "proposed_change": "human reviewer must inspect the referenced run and decide whether any rule or knowledge change is warranted",
                "supporting_evidence": [f"feedback:{feedback_id}"],
                "counter_evidence": [],
                "confidence": "low",
                "review_state": "pending_human_review",
                "reviewer_note": None,
                "created_at": created_at,
            }))
        return created

    def create_review_iteration(self, *, created_at: str) -> dict[str, object]:
        candidates = self.generate_rule_candidates(created_at=created_at)
        feedback = [item for item in self._list("feedback") if item.get("valid") is True]
        outcomes = [item for item in self._list("outcome") if item.get("valid") is True]
        runs = [item for item in self._list("run") if item.get("valid") is True]
        seed = {
            "created_at": created_at,
            "source_run_ids": sorted(str(item["run_id"]) for item in runs),
            "feedback_ids": sorted(str(item["feedback_id"]) for item in feedback),
            "outcome_ids": sorted(str(item["outcome_id"]) for item in outcomes),
            "candidate_ids": sorted(str(item["candidate_id"]) for item in candidates),
        }
        return self.create_iteration({
            "iteration_id": "iteration-" + digest({"record_type": "TrainingIterationSeed", "payload": seed})[7:23],
            **seed,
            "review_state": "pending_human_review",
            "decision": None,
            "reviewer_note": None,
            "applied_rule_ids": [],
        })

    def candidates(self) -> list[dict[str, object]]:
        return [item for item in self._list("candidate") if item.get("review_state") == "pending_human_review" and item.get("valid") is True]

    def review(self) -> dict[str, object]:
        feedback = [item for item in self._list("feedback") if item.get("valid") is True]
        outcomes = [item for item in self._list("outcome") if item.get("valid") is True]
        candidates = self.candidates()
        eligible = [item for item in outcomes if item.get("commercial_validation_eligible") is True]
        return {
            "schema_version": TRAINING_SCHEMA_VERSION,
            "case_count": len([item for item in self._list("case") if item.get("lifecycle") == "active"]),
            "run_count": len([item for item in self._list("run") if item.get("valid") is True]),
            "feedback_count": len(feedback),
            "outcome_count": len(outcomes),
            "pending_rule_candidates": len(candidates),
            "benchmark_accuracy_observations": 0,
            "commercial_validation_eligible_observations": len(eligible),
            "limitations": [
                "training_feedback_is_not_prediction_accuracy",
                "commercial_validation_requires_separate_frozen_dataset_and_independent_scoring",
            ],
        }

    def withdraw(self, case_id: str, *, withdrawn_at: str) -> dict[str, object]:
        case = self._read("case", case_id)
        removed: dict[str, int] = {}
        candidate_ids: set[str] = set()
        run_ids: set[str] = set()
        for kind in ("run", "feedback", "outcome", "candidate"):
            count = 0
            for item in self._list(kind):
                matches = item.get("case_id") == case_id or case_id in item.get("source_case_ids", [])
                if matches:
                    if kind == "run":
                        run_ids.add(str(item.get("run_id")))
                    if kind == "candidate":
                        candidate_ids.add(str(item.get("candidate_id")))
                    self._path(kind, str(item.get(f"{kind}_id") or item.get("run_id"))).unlink(missing_ok=True)
                    count += 1
            removed[kind] = count
        for item in self._list("iteration"):
            if run_ids.intersection(str(value) for value in item.get("source_run_ids", [])) or candidate_ids.intersection(str(value) for value in item.get("candidate_ids", [])):
                self._path("iteration", str(item.get("iteration_id"))).unlink(missing_ok=True)
                removed["iteration"] = removed.get("iteration", 0) + 1
        self._path("case", case_id).unlink(missing_ok=True)
        tombstone = {
            "case_ref_hash": _case_ref_hash(case_id),
            "action": "CONSENT_WITHDRAWN",
            "withdrawn_at": withdrawn_at,
            "derived_records_invalidated": removed,
            "prior_lifecycle": case.get("lifecycle"),
            "schema_version": TRAINING_SCHEMA_VERSION,
        }
        directory = self.root / "tombstones"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / _record_name(case_id)).write_text(canonical_json(tombstone) + "\n", encoding="utf-8", newline="\n")
        self._audit("CONSENT_WITHDRAWN", case_id, occurred_at=withdrawn_at, details={"derived_records_invalidated": removed})
        return tombstone


__all__ = ["TRAINING_SCHEMA_VERSION", "TrainingError", "TrainingStore"]
