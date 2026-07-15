from __future__ import annotations

from typing import Mapping

from .contracts.serialization import digest


def verify_validation_protocol(protocol: Mapping[str, object]) -> bool:
    expected = protocol.get("canonical_hash")
    body = {key: value for key, value in protocol.items() if key != "canonical_hash"}
    return bool(
        protocol.get("protocol_version")
        and protocol.get("source_commit_sha")
        and protocol.get("frozen_timestamp")
        and protocol.get("primary_metric")
        and expected == digest({"record_type": "ValidationProtocol", "payload": body})
    )
