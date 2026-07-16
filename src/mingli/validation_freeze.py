from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Mapping

from .contracts.serialization import canonical_json, digest


class FreezeError(ValueError):
    pass


_HASH_FIELDS = frozenset({"canonical_hash"})


def _hash_payload(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in snapshot.items() if key not in _HASH_FIELDS}


def freeze_prediction(
    value: Mapping[str, object],
    *,
    frozen_at: str,
    store: Path | None = None,
) -> dict[str, object]:
    payload = json.loads(canonical_json(value))
    required = (
        "prediction_id", "person_case_id", "scenario_id", "engine_version", "source_commit_sha",
        "rule_set_version", "knowledge_manifest_sha", "input_manifest_sha", "generated_at",
        "prediction_content", "structured_claims", "confidence", "blocked_fields",
    )
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        raise FreezeError(f"missing prediction fields: {','.join(missing)}")
    if payload.get("reality_evidence_visibility") is not False:
        raise FreezeError("reality evidence must be invisible when prediction is generated")
    claims = payload.get("structured_claims")
    if not isinstance(claims, list) or not claims:
        raise FreezeError("structured claims must be registered before freeze")
    claim_ids = [str(item.get("claim_id", "")) for item in claims if isinstance(item, Mapping)]
    if len(claim_ids) != len(claims) or any(not item for item in claim_ids) or len(set(claim_ids)) != len(claim_ids):
        raise FreezeError("structured claim ids must be present and unique")
    payload["freeze_status"] = "frozen"
    payload["freeze_timestamp"] = frozen_at
    payload["canonical_hash"] = digest({"record_type": "PredictionSnapshot", "payload": _hash_payload(payload)})
    if store is not None:
        target_dir = Path(store) / "predictions"
        target_dir.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^a-zA-Z0-9._-]", "_", str(payload["prediction_id"]))
        target = target_dir / f"{name}.json"
        try:
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(payload) + "\n")
        except FileExistsError as exc:
            raise FreezeError("frozen prediction id already exists; create a new prediction_id") from exc
    return payload


def verify_prediction_snapshot(snapshot: Mapping[str, object]) -> bool:
    expected = snapshot.get("canonical_hash")
    return (
        snapshot.get("freeze_status") == "frozen"
        and snapshot.get("reality_evidence_visibility") is False
        and isinstance(expected, str)
        and expected == digest({"record_type": "PredictionSnapshot", "payload": _hash_payload(snapshot)})
    )
