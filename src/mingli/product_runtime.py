from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

from .contracts import canonical_json, digest
from .phase20 import PHASE20_METHOD_ID
from .phase23 import PHASE23_METHOD_ID, Phase23InputError, run_mingli_agent
from .knowledge import inventory, validate_knowledge
from .training import TrainingError, TrainingStore
from .validation_privacy import scan_for_pii


PRODUCT_RUNTIME_SCHEMA_VERSION = "mingli-product-runtime-envelope@1.0"
_CASE_ID = re.compile(r"^person:[0-9a-f]{64}$")
_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _error(code: str, message: str, field_path: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {"code": code, "message": message}
    if field_path is not None:
        result["field_path"] = field_path
    return result


def _blocked(raw: object, error: Mapping[str, object]) -> dict[str, object]:
    created_at = raw.get("created_at") if isinstance(raw, Mapping) and isinstance(raw.get("created_at"), str) else None
    case_id = raw.get("case_id") if isinstance(raw, Mapping) and isinstance(raw.get("case_id"), str) and _CASE_ID.fullmatch(str(raw.get("case_id"))) else None
    seed = {"created_at": created_at, "case_id": case_id, "error": dict(error)}
    return {
        "run_id": digest({"record_type": "BlockedProductRuntime", "payload": seed})[7:31],
        "schema_version": PRODUCT_RUNTIME_SCHEMA_VERSION,
        "engine_version": PHASE23_METHOD_ID,
        "rule_manifest_hash": None,
        "renderer_version": PHASE20_METHOD_ID,
        "created_at": created_at,
        "status": "blocked",
        "confidence": "low",
        "confidence_reason": "reliable deterministic calculation was not available",
        "limitations": ["no_result_was_fabricated", "prediction_validity_not_evaluated"],
        "reality_evidence_used": [],
        "sections": [],
        "domain_results": {},
        "trace": {"status": "blocked", "stage_refs": []},
        "errors": [dict(error)],
        "training_write": {"attempted": False, "stored": False, "reason": "RUNTIME_BLOCKED"},
        "prediction_validity": "not_evaluated",
    }


def _validated_datetime(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return value


def _confidence(levels: Mapping[str, str]) -> tuple[str, str, str]:
    normalized = [value if value in _CONFIDENCE_RANK else "low" for value in levels.values()]
    overall = min(normalized, key=lambda value: _CONFIDENCE_RANK[value]) if normalized else "low"
    unresolved = sorted(domain for domain, level in levels.items() if level == "low")
    if overall == "low":
        return overall, "low confidence: unresolved or insufficient evidence in " + ",".join(unresolved), "degraded"
    return overall, f"minimum confidence across {len(normalized)} domain results is {overall}", "completed"


def _reality_evidence(fusion: Mapping[str, object]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    claims = fusion.get("claims")
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
        return records
    for claim in claims:
        if not isinstance(claim, Mapping) or claim.get("hard_override_direction") not in {"support", "contradict"}:
            continue
        evidence_ids = claim.get("winning_evidence_ids")
        records.append({
            "claim_id": claim.get("claim_id"),
            "scope": claim.get("scope"),
            "direction": claim.get("hard_override_direction"),
            "resolution": claim.get("status"),
            "confidence": claim.get("confidence"),
            "evidence_ids": list(evidence_ids) if isinstance(evidence_ids, Sequence) and not isinstance(evidence_ids, (str, bytes)) else [],
        })
    return sorted(records, key=lambda item: (str(item["scope"]), str(item["claim_id"])))


def _knowledge_trace(root: Path | None) -> dict[str, object]:
    knowledge_root = root or Path(__file__).resolve().parents[2] / "knowledge"
    if not knowledge_root.is_dir():
        return {"status": "unavailable", "manifest_hash": None, "issue_count": 1, "inventory": {}}
    issues = validate_knowledge(knowledge_root)
    assets: list[dict[str, str]] = []
    for path in sorted(item for item in knowledge_root.rglob("*") if item.is_file() and not item.is_symlink()):
        content = path.read_bytes()
        try:
            content = content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        except UnicodeDecodeError:
            pass
        assets.append({
            "path": path.relative_to(knowledge_root).as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    counts = inventory(knowledge_root)
    return {
        "status": "validated" if not issues else "invalid",
        "manifest_hash": digest({"record_type": "KnowledgeOSManifest", "payload": {"assets": assets, "inventory": counts}}),
        "issue_count": len(issues),
        "inventory": counts,
    }


def _ensure_training_case(store: TrainingStore, raw: Mapping[str, object], envelope: Mapping[str, object]) -> None:
    case_id = str(raw["case_id"])
    try:
        store.show_case(case_id)
        return
    except TrainingError as exc:
        if exc.code != "RECORD_NOT_FOUND":
            raise
    store.create_case({
        "case_id": case_id,
        "consent_scope": ["analysis", "training"],
        "consent_version": str(raw["consent"].get("consent_version", "")),  # type: ignore[union-attr]
        "intake_snapshot_ref": digest({"record_type": "ProductIntake", "payload": {"topic": raw.get("topic"), "anchor_year": raw.get("anchor_year")}}),
        "chart_snapshot_ref": digest({"record_type": "ChartInput", "payload": raw["chart_input"]}),
        "runtime_output_ref": str(envelope["canonical_hash"]),
        "analysis_version": str(envelope["engine_version"]),
        "created_at": str(envelope["created_at"]),
        "topic": str(raw.get("topic") or "general"),
        "confidence": str(envelope["confidence"]),
        "feedback_status": "pending",
        "outcome_status": "pending",
        "review_status": "pending",
        "provenance": {"runtime_schema": envelope["schema_version"]},
        "lifecycle": "active",
    })


def run_product_runtime(
    raw: Mapping[str, object],
    *,
    store: TrainingStore | None = None,
    knowledge_root: Path | None = None,
) -> dict[str, object]:
    """Run the existing deterministic Phase 23 chain behind product safety gates."""
    if not isinstance(raw, Mapping):
        return _blocked(raw, _error("INVALID_INPUT", "runtime input must be an object", "$"))
    findings = scan_for_pii(raw)
    if findings:
        return _blocked(raw, _error("PII_DETECTED", "direct identity fields are forbidden", findings[0].field_path))
    case_id = raw.get("case_id")
    if not isinstance(case_id, str) or _CASE_ID.fullmatch(case_id) is None:
        return _blocked(raw, _error("INVALID_CASE_ID", "case_id must be an HMAC-SHA256 person pseudonym", "$.case_id"))
    created_at = _validated_datetime(raw.get("created_at"))
    if created_at is None:
        return _blocked(raw, _error("INVALID_CREATED_AT", "created_at must be a timezone-aware ISO 8601 timestamp", "$.created_at"))
    consent = raw.get("consent")
    if not isinstance(consent, Mapping) or consent.get("analysis_allowed") is not True:
        return _blocked(raw, _error("ANALYSIS_CONSENT_REQUIRED", "analysis consent must be explicitly granted", "$.consent.analysis_allowed"))
    if not isinstance(raw.get("chart_input"), Mapping):
        return _blocked(raw, _error("MISSING_CHART_INPUT", "chart_input is required for deterministic calculation", "$.chart_input"))
    knowledge = _knowledge_trace(knowledge_root)
    try:
        runtime = run_mingli_agent(raw)
    except (Phase23InputError, KeyError, TypeError, ValueError):
        return _blocked(raw, _error("CALCULATION_INPUT_REJECTED", "deterministic calculation rejected the supplied chart contract", "$.chart_input"))
    except Exception:
        return _blocked(raw, _error("CALCULATION_UNAVAILABLE", "deterministic calculation was unavailable; no result was fabricated"))

    confidence, confidence_reason, status = _confidence(runtime.effective_domain_confidence)
    rule_hash = str(runtime.artifacts["domain_contracts"]["rule_set_hash"])
    trace = {
        "runtime_result_hash": runtime.canonical_hash,
        "stage_refs": [
            {"stage": stage.stage, "status": stage.status, "artifact_hash": stage.artifact_hash}
            for stage in runtime.stages
        ],
        "evidence_provenance": runtime.evidence_fusion.get("provenance_index", {}),
        "knowledge_os": knowledge,
    }
    sections = runtime.renderer.get("sections")
    body: dict[str, object] = {
        "run_id": runtime.run_id,
        "schema_version": PRODUCT_RUNTIME_SCHEMA_VERSION,
        "engine_version": PHASE23_METHOD_ID,
        "rule_manifest_hash": rule_hash,
        "renderer_version": PHASE20_METHOD_ID,
        "created_at": created_at,
        "status": status,
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "limitations": [
            "traditional_culture_not_decision_advice",
            "trend_only_no_guaranteed_event",
            "prediction_validity_not_evaluated",
        ],
        "reality_evidence_used": _reality_evidence(runtime.evidence_fusion),
        "sections": list(sections) if isinstance(sections, Sequence) and not isinstance(sections, (str, bytes)) else [],
        "domain_results": dict(runtime.effective_domain_statuses),
        "trace": trace,
        "errors": [],
        "prediction_validity": "not_evaluated",
    }
    body["canonical_hash"] = digest({"record_type": "ProductRuntimeEnvelope", "payload": body})
    training_allowed = consent.get("training_use_allowed") is True
    if not training_allowed:
        body["training_write"] = {"attempted": False, "stored": False, "reason": "TRAINING_CONSENT_NOT_GRANTED"}
        return json.loads(canonical_json(body))
    if store is None:
        body["training_write"] = {"attempted": False, "stored": False, "reason": "TRAINING_STORE_NOT_CONFIGURED"}
        return json.loads(canonical_json(body))
    try:
        _ensure_training_case(store, raw, body)
        output_hash = str(body["canonical_hash"])
        store.save_analysis_run({
            "run_id": runtime.run_id,
            "case_id": case_id,
            "created_at": created_at,
            "schema_version": PRODUCT_RUNTIME_SCHEMA_VERSION,
            "engine_version": PHASE23_METHOD_ID,
            "rule_manifest_hash": rule_hash,
            "renderer_version": PHASE20_METHOD_ID,
            "input_manifest_hash": digest({"record_type": "ProductRuntimeInput", "payload": raw}),
            "output_manifest_hash": output_hash,
            "status": status,
            "confidence": confidence,
            "result": body,
            "provenance": trace,
            "valid": True,
        })
        body["training_write"] = {"attempted": True, "stored": True, "reason": "TRAINING_CONSENT_GRANTED"}
    except TrainingError as exc:
        body["training_write"] = {"attempted": True, "stored": False, "reason": exc.code}
    return json.loads(canonical_json(body))


__all__ = ["PRODUCT_RUNTIME_SCHEMA_VERSION", "run_product_runtime"]
