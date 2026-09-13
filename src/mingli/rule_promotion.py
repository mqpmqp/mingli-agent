from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from jsonschema import Draft202012Validator, FormatChecker

from .contracts import canonical_json, digest, get_schema
from .training import TrainingError, TrainingStore
from .validation_privacy import scan_for_pii


RULE_PROMOTION_VERSION = "mingli-hourly-rule-promotion@1.0"
_REVIEWED_SOURCE_STATES = frozenset({"reviewed", "verified"})
_INSTRUCTION_DENYLIST = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "忽略此前",
    "忽略之前",
    "系统提示词",
)
_DISCLAIMER = "仅供文化研究与娱乐参考。"
_KINDS = {
    "training_source": "training_sources",
    "hourly_report": "hourly_reports",
    "promotion_candidate": "promotion_candidates",
    "source_check": "source_checks",
    "regression": "promotion_regressions",
    "approval": "promotion_approvals",
    "release": "rule_releases",
}
_SCHEMAS = {
    "training_source": "training_source.schema.json",
    "hourly_report": "hourly_training_report.schema.json",
    "promotion_candidate": "promotion_rule_candidate.schema.json",
    "source_check": "promotion_source_check.schema.json",
    "regression": "promotion_regression.schema.json",
    "approval": "promotion_approval.schema.json",
    "release": "runtime_rule_release.schema.json",
}


def _identifier(prefix: str, value: object) -> str:
    return f"{prefix}:{digest(value).split(':', 1)[1]}"


def _record_name(identifier: str) -> str:
    if not identifier or len(identifier) > 256:
        raise TrainingError("INVALID_RECORD_ID", "record id must contain 1 to 256 characters")
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest() + ".json"


class _PromotionRecords:
    """Versioned additive records that leave the frozen TrainingStore contract unchanged."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, kind: str, identifier: str) -> Path:
        return self.root / _KINDS[kind] / _record_name(identifier)

    def _validate(self, kind: str, value: Mapping[str, object]) -> dict[str, object]:
        payload = cast(dict[str, object], json.loads(canonical_json(value)))
        findings = scan_for_pii(payload)
        if findings:
            raise TrainingError(
                "PII_DETECTED",
                "record contains a forbidden direct identifier or identifier-like value",
                field_path=findings[0].field_path,
            )
        validator = Draft202012Validator(get_schema(_SCHEMAS[kind]), format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(cast(Any, payload)), key=lambda item: list(item.absolute_path))
        if errors:
            error = errors[0]
            path = "$" + "".join(
                f"[{part}]" if isinstance(part, int) else f".{part}"
                for part in error.absolute_path
            )
            raise TrainingError("SCHEMA_INCOMPATIBLE", error.message, field_path=path)
        return payload

    def _write(self, kind: str, identifier: str, value: Mapping[str, object]) -> dict[str, object]:
        payload = self._validate(kind, value)
        target = self._path(kind, identifier)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(payload) + "\n")
        except FileExistsError as exc:
            raise TrainingError("DUPLICATE_RECORD", f"{kind} record already exists") from exc
        return payload

    def _replace(self, kind: str, identifier: str, value: Mapping[str, object]) -> dict[str, object]:
        payload = self._validate(kind, value)
        target = self._path(kind, identifier)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(canonical_json(payload) + "\n", encoding="utf-8", newline="\n")
        temporary.replace(target)
        return payload

    def _read(self, kind: str, identifier: str) -> dict[str, object]:
        target = self._path(kind, identifier)
        if not target.is_file():
            raise TrainingError("RECORD_NOT_FOUND", f"{kind} record was not found")
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TrainingError("SCHEMA_INCOMPATIBLE", f"{kind} record must be an object")
        return self._validate(kind, value)

    def _list(self, kind: str) -> list[dict[str, object]]:
        directory = self.root / _KINDS[kind]
        if not directory.is_dir():
            return []
        records: list[dict[str, object]] = []
        for path in sorted(directory.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise TrainingError("SCHEMA_INCOMPATIBLE", f"{kind} record must be an object")
            records.append(self._validate(kind, value))
        return records


def _normalized_text(value: object) -> str:
    return " ".join(str(value).split())


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise TrainingError("INVALID_TIMESTAMP", f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrainingError("INVALID_TIMESTAMP", f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise TrainingError("INVALID_TIMESTAMP", f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _normalized_rule(value: Mapping[str, object]) -> dict[str, object]:
    examples = value.get("regression_examples", [])
    if not isinstance(examples, Sequence) or isinstance(examples, (str, bytes)):
        raise TrainingError("SCHEMA_INCOMPATIBLE", "regression_examples must be an array")
    normalized_examples: list[dict[str, object]] = []
    for item in examples:
        if not isinstance(item, Mapping):
            raise TrainingError("SCHEMA_INCOMPATIBLE", "each regression example must be an object")
        normalized_examples.append({
            "text": str(item.get("text", "")),
            "expected_violation": item.get("expected_violation"),
        })
    source_ids = value.get("supporting_source_ids", [])
    counter = value.get("counter_evidence", [])
    if not isinstance(source_ids, Sequence) or isinstance(source_ids, (str, bytes)):
        raise TrainingError("SCHEMA_INCOMPATIBLE", "supporting_source_ids must be an array")
    if not isinstance(counter, Sequence) or isinstance(counter, (str, bytes)):
        raise TrainingError("SCHEMA_INCOMPATIBLE", "counter_evidence must be an array")
    return {
        "kind": str(value.get("kind", "")),
        "statement": _normalized_text(value.get("statement", "")),
        "value": _normalized_text(value.get("value", "")),
        "supporting_source_ids": sorted({str(item) for item in source_ids}),
        "counter_evidence": sorted({_normalized_text(item) for item in counter}),
        "regression_examples": normalized_examples,
    }


def _candidate_hash(candidate: Mapping[str, object]) -> str:
    return digest({
        "record_type": "PromotionCandidateContent",
        "payload": {
            "domain": candidate["domain"],
            "rule": candidate["rule"],
            "source_ids": candidate["source_ids"],
            "counter_evidence": candidate["counter_evidence"],
        },
    })


class RulePromotionPipeline:
    """Fail-closed promotion path from hourly reports to pilot Runtime releases."""

    def __init__(self, store: TrainingStore) -> None:
        self.training_store = store
        self.store = _PromotionRecords(store.root)

    def register_source_file(self, path: Path | str, metadata: Mapping[str, object]) -> dict[str, object]:
        source_path = Path(path)
        if not source_path.is_file():
            raise TrainingError("SOURCE_FILE_NOT_FOUND", "source file was not found", field_path="$.file")
        hasher = hashlib.sha256()
        with source_path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(block)
        sha256 = hasher.hexdigest()
        source_id = f"source:{sha256}"
        payload = {
            "source_id": source_id,
            "title": metadata.get("title", ""),
            "source_type": metadata.get("source_type", "other"),
            "sha256": sha256,
            "source_family": metadata.get("source_family", ""),
            "scope_note": metadata.get("scope_note", ""),
            "review_state": "pending_human_review",
            "reviewer_id": None,
            "reviewed_at": None,
            "review_note": None,
            "registered_at": metadata.get("registered_at", ""),
        }
        try:
            existing = self.store._read("training_source", source_id)
        except TrainingError as exc:
            if exc.code != "RECORD_NOT_FOUND":
                raise
            return self.store._write("training_source", source_id, payload)
        immutable = ("source_id", "title", "source_type", "sha256", "source_family", "scope_note")
        if any(existing.get(field) != payload[field] for field in immutable):
            raise TrainingError("SOURCE_METADATA_CONFLICT", "the same source bytes were registered with different metadata")
        return existing

    def review_source(self, value: Mapping[str, object]) -> dict[str, object]:
        source_id = str(value.get("source_id", ""))
        source = self.store._read("training_source", source_id)
        review_state = value.get("review_state")
        if review_state not in {"reviewed", "verified", "rejected"}:
            raise TrainingError("INVALID_SOURCE_REVIEW", "source review_state must be reviewed, verified, or rejected")
        source.update({
            "review_state": review_state,
            "reviewer_id": value.get("reviewer_id"),
            "reviewed_at": value.get("reviewed_at"),
            "review_note": value.get("review_note"),
        })
        return self.store._replace("training_source", source_id, source)

    def ingest_hourly_report(self, value: Mapping[str, object]) -> dict[str, object]:
        proposed = value.get("proposed_rules", [])
        if not isinstance(proposed, Sequence) or isinstance(proposed, (str, bytes)):
            raise TrainingError("SCHEMA_INCOMPATIBLE", "proposed_rules must be an array")
        rules = [_normalized_rule(item) for item in proposed if isinstance(item, Mapping)]
        if len(rules) != len(proposed):
            raise TrainingError("SCHEMA_INCOMPATIBLE", "each proposed rule must be an object")
        report_sources = value.get("source_ids", [])
        if not isinstance(report_sources, Sequence) or isinstance(report_sources, (str, bytes)):
            raise TrainingError("SCHEMA_INCOMPATIBLE", "source_ids must be an array")
        source_ids = sorted({str(item) for item in report_sources})
        all_source_ids = sorted({*source_ids, *(source for rule in rules for source in rule["supporting_source_ids"])})
        for source_id in all_source_ids:
            self.store._read("training_source", str(source_id))
        if _timestamp(value.get("window_end"), field="window_end") <= _timestamp(value.get("window_start"), field="window_start"):
            raise TrainingError("INVALID_REPORT_WINDOW", "window_end must be later than window_start")
        if _timestamp(value.get("generated_at"), field="generated_at") < _timestamp(value.get("window_end"), field="window_end"):
            raise TrainingError("INVALID_REPORT_WINDOW", "generated_at cannot precede window_end")
        seed = {
            "automation_id": value.get("automation_id"),
            "domain": value.get("domain"),
            "window_start": value.get("window_start"),
            "window_end": value.get("window_end"),
            "generated_at": value.get("generated_at"),
            "run_count": value.get("run_count"),
            "summary": value.get("summary"),
            "findings": list(value.get("findings", [])) if isinstance(value.get("findings", []), list) else value.get("findings"),
            "source_ids": all_source_ids,
            "proposed_rules": rules,
            "synthetic": value.get("synthetic", False),
        }
        report_hash = digest({"record_type": "HourlyTrainingReport", "payload": seed})
        report_id = f"report:{report_hash.split(':', 1)[1]}"
        report = {**seed, "report_id": report_id, "report_hash": report_hash, "status": "ingested"}
        try:
            stored_report = self.store._write("hourly_report", report_id, report)
        except TrainingError as exc:
            if exc.code != "DUPLICATE_RECORD":
                raise
            stored_report = self.store._read("hourly_report", report_id)
        candidate_ids: list[str] = []
        deduplicated = 0
        for rule in rules:
            dedupe_key = digest({
                "record_type": "PromotionRuleDedupe",
                "payload": {"domain": seed["domain"], "kind": rule["kind"], "value": rule["value"]},
            })
            candidate_id = f"candidate:{dedupe_key.split(':', 1)[1]}"
            candidate_ids.append(candidate_id)
            try:
                candidate = self.store._read("promotion_candidate", candidate_id)
            except TrainingError as exc:
                if exc.code != "RECORD_NOT_FOUND":
                    raise
                candidate = {
                    "candidate_id": candidate_id,
                    "dedupe_key": dedupe_key,
                    "candidate_hash": "",
                    "report_ids": [report_id],
                    "domain": seed["domain"],
                    "rule": rule,
                    "source_ids": list(rule["supporting_source_ids"]),
                    "counter_evidence": list(rule["counter_evidence"]),
                    "review_state": "pending_source_verification",
                    "created_at": seed["generated_at"],
                    "valid": True,
                }
                candidate["candidate_hash"] = _candidate_hash(candidate)
                self.store._write("promotion_candidate", candidate_id, candidate)
                continue
            deduplicated += 1
            merged_sources = sorted({*candidate.get("source_ids", []), *rule["supporting_source_ids"]})
            merged_counter = sorted({*candidate.get("counter_evidence", []), *rule["counter_evidence"]})
            merged_reports = sorted({*candidate.get("report_ids", []), report_id})
            existing_rule = candidate["rule"]
            merged_examples = list(existing_rule.get("regression_examples", []))
            for example in rule["regression_examples"]:
                if example not in merged_examples:
                    merged_examples.append(example)
            changed = (
                merged_sources != candidate.get("source_ids")
                or merged_counter != candidate.get("counter_evidence")
                or merged_examples != existing_rule.get("regression_examples")
            )
            candidate.update({
                "source_ids": merged_sources,
                "counter_evidence": merged_counter,
                "report_ids": merged_reports,
            })
            candidate["rule"] = {
                **existing_rule,
                "supporting_source_ids": merged_sources,
                "counter_evidence": merged_counter,
                "regression_examples": merged_examples,
            }
            if changed:
                candidate["review_state"] = "pending_source_verification"
                candidate["candidate_hash"] = _candidate_hash(candidate)
            self.store._replace("promotion_candidate", candidate_id, candidate)
        return {
            "schema_version": RULE_PROMOTION_VERSION,
            "report": stored_report,
            "candidate_ids": candidate_ids,
            "created_candidates": len(candidate_ids) - deduplicated,
            "deduplicated_candidates": deduplicated,
        }

    def verify_sources(self, candidate_id: str, *, checked_at: str) -> dict[str, object]:
        candidate = self.store._read("promotion_candidate", candidate_id)
        sources: list[dict[str, object]] = []
        reasons: list[str] = []
        for source_id in candidate["source_ids"]:
            try:
                source = self.store._read("training_source", str(source_id))
            except TrainingError as exc:
                if exc.code != "RECORD_NOT_FOUND":
                    raise
                reasons.append(f"unregistered_source:{source_id}")
                continue
            if source.get("source_id") != f"source:{source.get('sha256')}":
                reasons.append(f"source_hash_identity_mismatch:{source_id}")
            if source.get("review_state") not in _REVIEWED_SOURCE_STATES:
                reasons.append(f"source_not_human_reviewed:{source_id}")
            sources.append(source)
        state_snapshot = [
            {
                "source_id": item["source_id"],
                "sha256": item["sha256"],
                "source_family": item["source_family"],
                "review_state": item["review_state"],
            }
            for item in sorted(sources, key=lambda item: str(item["source_id"]))
        ]
        check_id = _identifier("source-check", {
            "candidate_hash": candidate["candidate_hash"],
            "sources": state_snapshot,
        })
        result = {
            "check_id": check_id,
            "candidate_id": candidate_id,
            "candidate_hash": candidate["candidate_hash"],
            "source_ids": sorted(str(item) for item in candidate["source_ids"]),
            "source_receipts": state_snapshot,
            "source_family_count": len({str(item["source_family"]) for item in sources}),
            "status": "failed" if reasons else "passed",
            "reasons": sorted(reasons),
            "checked_at": checked_at,
        }
        try:
            stored = self.store._write("source_check", check_id, result)
        except TrainingError as exc:
            if exc.code != "DUPLICATE_RECORD":
                raise
            stored = self.store._read("source_check", check_id)
        candidate["review_state"] = "source_check_passed" if stored["status"] == "passed" else "source_check_failed"
        self.store._replace("promotion_candidate", candidate_id, candidate)
        return stored

    def run_regression(self, candidate_id: str, *, checked_at: str) -> dict[str, object]:
        candidate = self.store._read("promotion_candidate", candidate_id)
        rule = candidate["rule"]
        kind = str(rule["kind"])
        value = str(rule["value"])
        receipts: list[dict[str, object]] = []
        if kind == "runtime_instruction":
            lowered = value.casefold()
            checks = {
                "single_line": "\n" not in value and "\r" not in value,
                "denylist_clear": not any(term in lowered for term in _INSTRUCTION_DENYLIST),
                "bounded": 0 < len(value) <= 500,
            }
            receipts.extend({"case": name, "passed": passed} for name, passed in checks.items())
        else:
            examples = rule.get("regression_examples", [])
            if not examples:
                receipts.append({"case": "examples_present", "passed": False})
            for index, example in enumerate(examples):
                text = str(example["text"])
                actual = value in text if kind == "output_forbidden_phrase" else value not in text
                receipts.append({
                    "case": f"example-{index + 1}",
                    "expected_violation": example["expected_violation"],
                    "actual_violation": actual,
                    "passed": actual is example["expected_violation"],
                })
            expected_values = {bool(item.get("expected_violation")) for item in examples}
            receipts.append({"case": "positive_and_negative_examples", "passed": expected_values == {False, True}})
        passed = sum(item["passed"] is True for item in receipts)
        regression_id = _identifier("regression", {
            "candidate_hash": candidate["candidate_hash"],
            "receipts": receipts,
        })
        result = {
            "regression_id": regression_id,
            "candidate_id": candidate_id,
            "candidate_hash": candidate["candidate_hash"],
            "status": "passed" if passed == len(receipts) else "failed",
            "total": len(receipts),
            "passed": passed,
            "failed": len(receipts) - passed,
            "receipts": receipts,
            "limitations": [
                "contract_regression_is_not_prediction_accuracy",
                "semantic_effectiveness_requires_phase4_1_real_case_validation",
            ],
            "checked_at": checked_at,
        }
        try:
            return self.store._write("regression", regression_id, result)
        except TrainingError as exc:
            if exc.code != "DUPLICATE_RECORD":
                raise
            return self.store._read("regression", regression_id)

    def decide_candidate(self, value: Mapping[str, object]) -> dict[str, object]:
        candidate_id = str(value.get("candidate_id", ""))
        candidate = self.store._read("promotion_candidate", candidate_id)
        source_check = self.store._read("source_check", str(value.get("source_check_id", "")))
        regression = self.store._read("regression", str(value.get("regression_id", "")))
        for receipt, label in ((source_check, "source check"), (regression, "regression")):
            if receipt.get("candidate_id") != candidate_id or receipt.get("candidate_hash") != candidate["candidate_hash"]:
                raise TrainingError("STALE_GATE_RECEIPT", f"{label} does not bind the current candidate hash")
        decision = value.get("decision")
        if decision not in {"approved", "rejected"}:
            raise TrainingError("INVALID_APPROVAL_DECISION", "decision must be approved or rejected")
        if decision == "approved" and (source_check.get("status") != "passed" or regression.get("status") != "passed"):
            raise TrainingError("PROMOTION_GATES_FAILED", "approval requires passing source and regression receipts")
        seed = {
            "candidate_id": candidate_id,
            "candidate_hash": candidate["candidate_hash"],
            "source_check_id": source_check["check_id"],
            "regression_id": regression["regression_id"],
            "decision": decision,
            "reviewer_id": value.get("reviewer_id"),
            "review_note": value.get("review_note"),
            "decided_at": value.get("decided_at"),
        }
        approval_id = _identifier("approval", seed)
        return self.store._write("approval", approval_id, {"approval_id": approval_id, **seed})

    def publish(self, value: Mapping[str, object]) -> dict[str, object]:
        candidate_ids = value.get("candidate_ids", [])
        if not isinstance(candidate_ids, Sequence) or isinstance(candidate_ids, (str, bytes)) or not candidate_ids:
            raise TrainingError("EMPTY_RELEASE", "candidate_ids must be a non-empty array")
        rules: list[dict[str, object]] = []
        source_check_ids: list[str] = []
        regression_ids: list[str] = []
        approval_ids: list[str] = []
        for candidate_id_value in sorted({str(item) for item in candidate_ids}):
            candidate = self.store._read("promotion_candidate", candidate_id_value)
            decisions = [
                item for item in self.store._list("approval")
                if item.get("candidate_id") == candidate_id_value
                and item.get("candidate_hash") == candidate["candidate_hash"]
            ]
            if not decisions:
                raise TrainingError("HUMAN_APPROVAL_REQUIRED", f"candidate has no approval: {candidate_id_value}")
            approval = sorted(
                decisions,
                key=lambda item: (_timestamp(item["decided_at"], field="decided_at"), str(item["approval_id"])),
            )[-1]
            if approval.get("decision") != "approved":
                raise TrainingError("HUMAN_APPROVAL_REQUIRED", f"candidate's latest decision is not approved: {candidate_id_value}")
            source_check = self.store._read("source_check", str(approval["source_check_id"]))
            regression = self.store._read("regression", str(approval["regression_id"]))
            if source_check.get("status") != "passed" or regression.get("status") != "passed":
                raise TrainingError("PROMOTION_GATES_FAILED", "approved candidate has a non-passing gate receipt")
            rule = candidate["rule"]
            rules.append({
                "candidate_id": candidate_id_value,
                "candidate_hash": candidate["candidate_hash"],
                "domain": candidate["domain"],
                "kind": rule["kind"],
                "statement": rule["statement"],
                "value": rule["value"],
                "source_ids": candidate["source_ids"],
            })
            source_check_ids.append(str(source_check["check_id"]))
            regression_ids.append(str(regression["regression_id"]))
            approval_ids.append(str(approval["approval_id"]))
        forbidden = {str(item["value"]) for item in rules if item["kind"] == "output_forbidden_phrase"}
        required = {str(item["value"]) for item in rules if item["kind"] == "output_required_notice"}
        if forbidden.intersection(required):
            raise TrainingError("CONFLICTING_RELEASE_RULES", "the same phrase cannot be both forbidden and required")
        body = {
            "version": value.get("version"),
            "created_at": value.get("created_at"),
            "rules": rules,
            "source_check_ids": source_check_ids,
            "regression_ids": regression_ids,
            "approval_ids": approval_ids,
            "runtime_loadable": True,
            "deployment_scope": "development_and_pilot",
            "phase4_1_validation": {
                "pilot_target": 10,
                "registered_real_cases": 0,
                "accuracy": None,
                "prediction_validity": "not_evaluated",
                "commercial_release_hold": "ACTIVE",
            },
        }
        manifest_hash = digest({"record_type": "RuntimeRuleRelease", "payload": body})
        release_id = _identifier("release", {"version": body["version"], "manifest_hash": manifest_hash})
        return self.store._write("release", str(body["version"]), {
            "release_id": release_id,
            **body,
            "manifest_hash": manifest_hash,
        })

    def load_release(self, version: str | None = None) -> dict[str, object]:
        if version is None:
            releases = self.store._list("release")
            if not releases:
                raise TrainingError("RULE_RELEASE_NOT_FOUND", "no published rule release is available")
            release = sorted(
                releases,
                key=lambda item: (_timestamp(item["created_at"], field="created_at"), str(item["version"])),
            )[-1]
        else:
            release = self.store._read("release", version)
        body = {key: item for key, item in release.items() if key not in {"release_id", "manifest_hash"}}
        expected = digest({"record_type": "RuntimeRuleRelease", "payload": body})
        if release.get("manifest_hash") != expected:
            raise TrainingError("RULE_RELEASE_INTEGRITY_FAILED", "published rule release manifest hash does not match")
        expected_release_id = _identifier(
            "release",
            {"version": release["version"], "manifest_hash": release["manifest_hash"]},
        )
        if release.get("release_id") != expected_release_id or (version is not None and release.get("version") != version):
            raise TrainingError("RULE_RELEASE_INTEGRITY_FAILED", "published rule release identity does not match")
        for rule in release["rules"]:
            for source_id in rule["source_ids"]:
                source = self.store._read("training_source", str(source_id))
                if (
                    source.get("source_id") != f"source:{source.get('sha256')}"
                    or source.get("review_state") not in _REVIEWED_SOURCE_STATES
                ):
                    raise TrainingError(
                        "RULE_RELEASE_SOURCE_REVOKED",
                        "published rule release references a source that is no longer review-approved",
                    )
        return release

    def status(self) -> dict[str, object]:
        from .phase4_1 import Phase41Pilot

        releases = self.store._list("release")
        candidates = self.store._list("promotion_candidate")
        phase4_1 = Phase41Pilot(self.training_store).status()["phase4_1_validation"]
        return {
            "schema_version": RULE_PROMOTION_VERSION,
            "hourly_reports": len(self.store._list("hourly_report")),
            "sources": len(self.store._list("training_source")),
            "candidates": len(candidates),
            "pending_source_verification": sum(item.get("review_state") != "source_check_passed" for item in candidates),
            "approvals": len(self.store._list("approval")),
            "releases": len(releases),
            "active_release": self.load_release()["version"] if releases else None,
            "phase4_1_validation": phase4_1,
        }

    def review_queue(self) -> dict[str, object]:
        """Return current gate receipts without changing approval state."""

        candidates: list[dict[str, object]] = []
        source_checks = self.store._list("source_check")
        regressions = self.store._list("regression")
        approvals = self.store._list("approval")
        releases = self.store._list("release")
        for candidate in sorted(
            self.store._list("promotion_candidate"),
            key=lambda item: str(item["candidate_id"]),
        ):
            candidate_id = str(candidate["candidate_id"])
            candidate_hash = str(candidate["candidate_hash"])
            matching_checks = [
                item
                for item in source_checks
                if item.get("candidate_id") == candidate_id
                and item.get("candidate_hash") == candidate_hash
            ]
            matching_regressions = [
                item
                for item in regressions
                if item.get("candidate_id") == candidate_id
                and item.get("candidate_hash") == candidate_hash
            ]
            matching_approvals = [
                item
                for item in approvals
                if item.get("candidate_id") == candidate_id
                and item.get("candidate_hash") == candidate_hash
            ]
            source_check = (
                sorted(
                    matching_checks,
                    key=lambda item: (
                        _timestamp(item["checked_at"], field="checked_at"),
                        str(item["check_id"]),
                    ),
                )[-1]
                if matching_checks
                else None
            )
            regression = (
                sorted(
                    matching_regressions,
                    key=lambda item: (
                        _timestamp(item["checked_at"], field="checked_at"),
                        str(item["regression_id"]),
                    ),
                )[-1]
                if matching_regressions
                else None
            )
            approval = (
                sorted(
                    matching_approvals,
                    key=lambda item: (
                        _timestamp(item["decided_at"], field="decided_at"),
                        str(item["approval_id"]),
                    ),
                )[-1]
                if matching_approvals
                else None
            )
            published_versions = sorted(
                str(release["version"])
                for release in releases
                if any(
                    rule.get("candidate_id") == candidate_id
                    and rule.get("candidate_hash") == candidate_hash
                    for rule in release.get("rules", [])
                    if isinstance(rule, Mapping)
                )
            )
            if source_check is None or source_check.get("status") != "passed":
                promotion_state = "blocked_source_review"
            elif regression is None or regression.get("status") != "passed":
                promotion_state = "blocked_regression"
            elif approval is None:
                promotion_state = "awaiting_human_approval"
            elif approval.get("decision") == "approved":
                promotion_state = (
                    "published" if published_versions else "approved_not_published"
                )
            else:
                promotion_state = "rejected"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_hash": candidate_hash,
                    "domain": candidate["domain"],
                    "rule": candidate["rule"],
                    "source_ids": candidate["source_ids"],
                    "report_ids": candidate["report_ids"],
                    "source_check_id": source_check.get("check_id")
                    if source_check
                    else None,
                    "source_status": source_check.get("status")
                    if source_check
                    else "not_run",
                    "source_reasons": source_check.get("reasons", [])
                    if source_check
                    else [],
                    "regression_id": regression.get("regression_id")
                    if regression
                    else None,
                    "regression_status": regression.get("status")
                    if regression
                    else "not_run",
                    "latest_approval_id": approval.get("approval_id")
                    if approval
                    else None,
                    "latest_decision": approval.get("decision")
                    if approval
                    else None,
                    "published_release_versions": published_versions,
                    "promotion_state": promotion_state,
                }
            )
        return {
            "schema_version": RULE_PROMOTION_VERSION,
            "candidates": candidates,
            "auto_approval": False,
            "auto_publish": False,
            "commercial_release_hold": "ACTIVE",
        }


def apply_runtime_release(
    result: Mapping[str, object],
    release: Mapping[str, object],
    *,
    domain: str = "bazi",
) -> dict[str, object]:
    """Apply only published text guardrails and attach an auditable release receipt."""
    updated = dict(result)
    text = str(updated.get("final_answer", ""))
    instructions: list[str] = []
    applied_candidates: list[str] = []
    for rule in release.get("rules", []):
        if not isinstance(rule, Mapping) or rule.get("domain") not in {domain, "cross_domain"}:
            continue
        kind = rule.get("kind")
        value = str(rule.get("value", ""))
        if kind == "runtime_instruction":
            instructions.append(value)
        elif kind == "output_forbidden_phrase":
            text = text.replace(value, "【受已发布规则约束的表述】")
        elif kind == "output_required_notice" and value not in text:
            if text.endswith(_DISCLAIMER):
                text = text[: -len(_DISCLAIMER)].rstrip() + "\n\n" + value + "\n\n" + _DISCLAIMER
            else:
                text = text.rstrip() + "\n\n" + value
        else:
            continue
        applied_candidates.append(str(rule.get("candidate_id")))
    updated["final_answer"] = text
    renderer = updated.get("renderer")
    if isinstance(renderer, Mapping):
        updated["renderer"] = {**renderer, "rendered_text": text}
    warnings = list(updated.get("warnings", []))
    if applied_candidates and "published_training_rule_release_loaded" not in warnings:
        warnings.append("published_training_rule_release_loaded")
    updated["warnings"] = warnings
    updated["active_rule_release"] = {
        "version": release["version"],
        "manifest_hash": release["manifest_hash"],
        "applied_candidate_ids": applied_candidates,
        "runtime_instructions": instructions,
        "deployment_scope": release["deployment_scope"],
        "phase4_1_validation": release["phase4_1_validation"],
    }
    without_hash = {key: item for key, item in updated.items() if key != "canonical_hash"}
    updated["canonical_hash"] = digest({"record_type": "MingLiRuntimeWithRuleRelease", "payload": without_hash})
    return __import__("json").loads(canonical_json(updated))


__all__ = [
    "RULE_PROMOTION_VERSION",
    "RulePromotionPipeline",
    "apply_runtime_release",
]
