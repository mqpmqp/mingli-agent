from __future__ import annotations

from typing import Mapping


PRODUCT_GATE_VERSION = "v2-product-commercial-gates@1.0"
PRODUCT_REQUIREMENTS = (
    "runtime",
    "knowledge",
    "rules",
    "evidence",
    "renderer",
    "etl",
    "training",
    "privacy",
    "fast_tests",
    "build",
    "static_checks",
)
COMMERCIAL_REQUIREMENTS = (
    "claims_prefrozen",
    "outcome_time_boundary",
    "independent_scoring",
    "leakage_detection",
    "reproducible_benchmark",
    "accuracy_report",
    "commercial_risk_review",
)


def assess_v2_readiness(
    product_gates: Mapping[str, object],
    commercial_evidence: Mapping[str, object],
) -> dict[str, object]:
    """Assess capability and commercial evidence independently.

    Training feedback and unauthorized cases are deliberately never counted.
    """
    product_failures = [name for name in PRODUCT_REQUIREMENTS if product_gates.get(name) is not True]
    product_ready = not product_failures
    authorized = commercial_evidence.get("authorized_real_cases")
    authorized_count = authorized if isinstance(authorized, int) and not isinstance(authorized, bool) and authorized > 0 else 0
    accuracy = commercial_evidence.get("independently_scored_preregistered_outcomes")
    accuracy_count = accuracy if isinstance(accuracy, int) and not isinstance(accuracy, bool) and accuracy > 0 else 0
    commercial_failures = [name for name in COMMERCIAL_REQUIREMENTS if commercial_evidence.get(name) is not True]
    if authorized_count == 0:
        commercial_failures.append("authorized_real_cases")
    if accuracy_count == 0:
        commercial_failures.append("independently_scored_preregistered_outcomes")
    commercial_ready = not commercial_failures
    return {
        "schema_version": PRODUCT_GATE_VERSION,
        "product_status": "PRODUCT_CAPABILITY_READY" if product_ready else "PRODUCT_CAPABILITY_BLOCKED",
        "commercial_status": "COMMERCIAL_VALIDATION_READY" if commercial_ready else "COMMERCIAL_VALIDATION_PENDING",
        "product_blockers": sorted(product_failures),
        "commercial_blockers": sorted(set(commercial_failures)),
        "allowed_modes": {
            "development": product_ready,
            "production-commercial": product_ready and commercial_ready,
        },
        "commercial_evidence_counted": {
            "authorized_real_cases": authorized_count,
            "accuracy_observations": accuracy_count,
            "unauthorized_cases": 0,
            "training_feedback": 0,
        },
        "legacy_product_release_status": "PRODUCT_RELEASE_ALLOWED" if product_ready and commercial_ready else "PRODUCT_RELEASE_HOLD",
        "limitations": [
            "product_capability_ready_does_not_establish_prediction_accuracy",
            "training_feedback_does_not_count_as_benchmark_accuracy",
            "unauthorized_cases_are_excluded_from_commercial_validation",
        ],
    }


__all__ = ["COMMERCIAL_REQUIREMENTS", "PRODUCT_GATE_VERSION", "PRODUCT_REQUIREMENTS", "assess_v2_readiness"]
