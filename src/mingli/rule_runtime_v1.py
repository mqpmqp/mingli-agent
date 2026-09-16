from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from .consumption_v1 import ConsumptionV1
from .phase4_1 import Phase41Pilot
from .rule_promotion import RulePromotionPipeline, apply_runtime_release
from .service import analyze_mingli_payload, get_service_capabilities
from .training import TrainingError, TrainingStore


RULE_RUNTIME_VERSION = "mingli-rule-aware-runtime@1.1"


class RuleAwareRuntime:
    """Additive Runtime adapter; frozen service contracts stay unchanged.

    Published rule releases remain mandatory for rule application. Consumption V1
    is additive and fail-closed: only explicitly human-approved, published training
    assets can be retrieved, and retrieval is exact-match by domain/scenario/topic.
    """

    def __init__(
        self,
        store_root: Path | str,
        *,
        repository_root: Path | str,
        version: str | None = None,
        synthetic: bool = False,
    ) -> None:
        store = TrainingStore(store_root, repository_root=repository_root, synthetic=synthetic)
        self.store = store
        self.phase4_1 = Phase41Pilot(store)
        self.consumption = ConsumptionV1(store)
        self.release = RulePromotionPipeline(store).load_release(version)

    def analyze(self, payload: object) -> dict[str, object]:
        return self.apply(analyze_mingli_payload(payload), domain="bazi")

    def apply(self, result: Mapping[str, object], *, domain: str) -> dict[str, object]:
        if domain not in {"bazi", "qimen", "fengshui"}:
            raise ValueError("domain must be bazi, qimen, or fengshui")
        return apply_runtime_release(result, self.release, domain=domain)

    def retrieve_training_context(
        self,
        *,
        domain: str,
        scenario: str,
        topic: str,
        query_id: str,
        consumed_at: str,
        mode: str | None = None,
    ) -> dict[str, object]:
        """Retrieve a bounded, audited historical context pack.

        SHADOW is the default even when the caller omits mode. ACTIVE must be an
        explicit deployment choice; this method itself never changes model weights,
        rule releases, or Phase 4.1 accuracy state.
        """

        selected_mode = mode or os.environ.get("MINGLI_CONSUMPTION_MODE", "SHADOW").strip() or "SHADOW"
        return self.consumption.retrieve(
            domain=domain,
            scenario=scenario,
            topic=topic,
            query_id=query_id,
            consumed_at=consumed_at,
            mode=selected_mode,
        )

    def capabilities(self) -> dict[str, object]:
        base = get_service_capabilities()
        binding = self.phase4_1_binding()
        base["rule_runtime_version"] = RULE_RUNTIME_VERSION
        base["rule_release"] = {
            "status": "loaded",
            "version": self.release["version"],
            "manifest_hash": self.release["manifest_hash"],
            "deployment_scope": self.release["deployment_scope"],
            "phase4_1_validation": {
                key: value
                for key, value in binding.items()
                if key not in {"rule_set_version", "rule_manifest_hash"}
            },
        }
        base["consumption_v1"] = self.consumption.status()
        return base

    def phase4_1_binding(self) -> dict[str, object]:
        return {
            "rule_set_version": self.release["version"],
            "rule_manifest_hash": self.release["manifest_hash"],
            **self.phase4_1.status()["phase4_1_validation"],
        }

    def bind_phase4_1_prediction(
        self, prediction: Mapping[str, object]
    ) -> dict[str, object]:
        """Bind a pre-freeze Phase 4.1 prediction to the loaded release.

        The V2 prediction contract stores the exact rule version. A conflicting
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
