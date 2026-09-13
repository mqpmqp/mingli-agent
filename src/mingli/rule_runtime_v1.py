from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from .rule_promotion import RulePromotionPipeline, apply_runtime_release
from .service import analyze_mingli_payload, get_service_capabilities
from .training import TrainingError, TrainingStore


RULE_RUNTIME_VERSION = "mingli-rule-aware-runtime@1.0"


class RuleAwareRuntime:
    """Additive Runtime adapter; the frozen Phase 23 and service contracts stay unchanged."""

    def __init__(
        self,
        store_root: Path | str,
        *,
        repository_root: Path | str,
        version: str | None = None,
        synthetic: bool = False,
    ) -> None:
        store = TrainingStore(store_root, repository_root=repository_root, synthetic=synthetic)
        self.release = RulePromotionPipeline(store).load_release(version)

    def analyze(self, payload: object) -> dict[str, object]:
        return self.apply(analyze_mingli_payload(payload), domain="bazi")

    def apply(self, result: Mapping[str, object], *, domain: str) -> dict[str, object]:
        if domain not in {"bazi", "qimen", "fengshui"}:
            raise ValueError("domain must be bazi, qimen, or fengshui")
        return apply_runtime_release(result, self.release, domain=domain)

    def capabilities(self) -> dict[str, object]:
        base = get_service_capabilities()
        base["rule_runtime_version"] = RULE_RUNTIME_VERSION
        base["rule_release"] = {
            "status": "loaded",
            "version": self.release["version"],
            "manifest_hash": self.release["manifest_hash"],
            "deployment_scope": self.release["deployment_scope"],
            "phase4_1_validation": self.release["phase4_1_validation"],
        }
        return base

    def phase4_1_binding(self) -> dict[str, object]:
        return {
            "rule_set_version": self.release["version"],
            "rule_manifest_hash": self.release["manifest_hash"],
            **self.release["phase4_1_validation"],
        }

    def bind_phase4_1_prediction(
        self, prediction: Mapping[str, object]
    ) -> dict[str, object]:
        """Bind a pre-freeze Phase 4.1 prediction to the loaded release.

        The V2 prediction contract stores the exact rule version.  A conflicting
        caller-provided version is rejected so a case cannot be silently moved
        between rule cohorts after the prediction was produced.
        """

        existing = prediction.get("rule_set_version")
        if existing not in {None, "", self.release["version"]}:
            raise TrainingError(
                "PHASE4_1_RULE_VERSION_CONFLICT",
                "prediction rule_set_version conflicts with the loaded release",
                field_path="$.rule_set_version",
            )
        return {**prediction, "rule_set_version": self.release["version"]}

    def runtime_instructions(self) -> dict[str, object]:
        directives = [
            str(item["value"])
            for item in self.release["rules"]
            if item["kind"] == "runtime_instruction" and item["domain"] in {"bazi", "cross_domain"}
        ]
        return {
            "rule_set_version": self.release["version"],
            "rule_manifest_hash": self.release["manifest_hash"],
            "instructions": directives,
        }

    def mcp_instructions(self, base_instructions: str) -> str:
        directives = self.runtime_instructions()["instructions"]
        if not directives:
            return base_instructions
        return base_instructions.rstrip() + " Published, human-approved runtime instructions: " + " ".join(directives)


def configured_rule_runtime(
    *,
    repository_root: Path | str,
    environ: Mapping[str, str] | None = None,
) -> RuleAwareRuntime | None:
    settings = os.environ if environ is None else environ
    store_root = settings.get("MINGLI_RULE_RELEASE_STORE", "").strip()
    if not store_root:
        return None
    version = settings.get("MINGLI_RULE_RELEASE_VERSION", "").strip() or None
    return RuleAwareRuntime(store_root, repository_root=repository_root, version=version)


__all__ = ["RULE_RUNTIME_VERSION", "RuleAwareRuntime", "configured_rule_runtime"]
