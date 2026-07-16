from __future__ import annotations

import json
from typing import Mapping

from .contracts.serialization import canonical_json, digest


def freeze_reality_evidence(value: Mapping[str, object]) -> dict[str, object]:
    payload = json.loads(canonical_json(value))
    for field in ("evidence_id", "person_case_id", "scenario_id", "observed_at", "collected_at", "source_provenance", "evidence_quality"):
        if payload.get(field) in (None, ""):
            raise ValueError(f"reality_evidence.{field} is required")
    if payload.get("source_provenance") in {"model_generated", "prediction_output", "self_proving"}:
        raise ValueError("prediction or model output cannot serve as reality evidence")
    payload["freeze_status"] = "frozen"
    payload["canonical_hash"] = digest({"record_type": "RealityEvidence", "payload": payload})
    return payload


def verify_reality_evidence(value: Mapping[str, object]) -> bool:
    expected = value.get("canonical_hash")
    body = {key: item for key, item in value.items() if key != "canonical_hash"}
    return value.get("freeze_status") == "frozen" and expected == digest({"record_type": "RealityEvidence", "payload": body})
