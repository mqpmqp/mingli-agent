from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

from .validation_dataset import verify_dataset_manifest


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def evaluate_product_release(
    manifest: Mapping[str, object] | None,
    authorization: Mapping[str, object] | None,
    gates: Mapping[str, object] | None,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    current = now or datetime.now(timezone.utc)
    blockers: list[str] = []
    if manifest is None or not verify_dataset_manifest(manifest) or manifest.get("validation_closure_passed") is not True:
        blockers.append("P22_VALIDATION_CLOSURE")
    if authorization is None:
        blockers.append("PRODUCT_RELEASE_AUTHORIZATION")
    else:
        status = authorization.get("authorization_status")
        due = _timestamp(authorization.get("expires_at") or authorization.get("review_due_at"))
        matching = bool(
            manifest
            and authorization.get("dataset_id") == manifest.get("dataset_id")
            and authorization.get("dataset_manifest_sha") == manifest.get("aggregate_canonical_hash")
        )
        complete_independent_authorization = bool(
            str(authorization.get("authorized_by_role", "")).startswith("independent-")
            and authorization.get("validation_report_sha")
            and authorization.get("authorized_at")
            and authorization.get("approved_use_scope")
            and authorization.get("prohibited_claims")
            and not authorization.get("unresolved_conflicts")
            and manifest
            and authorization.get("source_commit_sha") == manifest.get("source_commit_sha")
            and authorization.get("product_accuracy_claim_allowed") is manifest.get("product_accuracy_claim_allowed")
        )
        if status != "approved" or not matching or not complete_independent_authorization or due is None or due <= current or authorization.get("validation_closure_passed") is not True:
            blockers.append("PRODUCT_RELEASE_AUTHORIZATION")
    resolved_gates = gates or {}
    p1 = resolved_gates.get("p1_findings")
    p2 = resolved_gates.get("p2_findings")
    gate_contract = {
        "P1_FINDINGS": isinstance(p1, int) and not isinstance(p1, bool) and p1 == 0,
        "P2_FINDINGS": isinstance(p2, int) and not isinstance(p2, bool) and p2 == 0,
        "PRIVACY_GATE": resolved_gates.get("privacy_gate") is True,
        "PACKAGE_GATE": resolved_gates.get("package_gate") is True,
        "MAIN_CI": resolved_gates.get("main_ci") is True,
    }
    blockers.extend(name for name, passed in gate_contract.items() if not passed)
    allowed = not blockers
    return {
        "status": "PRODUCT_RELEASE_ALLOWED" if allowed else "PRODUCT_RELEASE_HOLD",
        "allowed": allowed,
        "blockers": sorted(set(blockers)),
        "product_accuracy_claim_allowed": bool(manifest and manifest.get("product_accuracy_claim_allowed") is True),
        "prediction_validity": "evaluated" if allowed else "not_evaluated",
    }
