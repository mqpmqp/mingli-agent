from __future__ import annotations

from typing import Mapping

from mingli.contracts.models import BaseChartRef
from mingli.contracts.serialization import digest
from mingli.contracts.validation import contract_error

_SUPPORTED_BASES = frozenset({("bazi-deterministic-lichun-jie-noaa-v0.1", "0.1.0")})
_POSITIONS = ("year", "month", "day", "hour")


def adapt_base_chart(base: Mapping[str, object], *, expected_pillar_fingerprint: str | None = None) -> BaseChartRef:
    method = base.get("method_id")
    version = base.get("calculation_version")
    if not isinstance(method, str) or not isinstance(version, str):
        raise contract_error("DERIVED_BASE_RESULT_INVALID", "base method/version is missing", field_path="method_id")
    if (method, version) not in _SUPPORTED_BASES:
        raise contract_error("DERIVED_BASE_METHOD_UNSUPPORTED", "base method/version is not allowlisted", field_path="calculation_version", dependency=f"{method}@{version}")
    pillars = base.get("pillars")
    conventions = base.get("conventions")
    if not isinstance(pillars, Mapping) or not isinstance(conventions, Mapping):
        raise contract_error("DERIVED_BASE_RESULT_INVALID", "base pillars or conventions is invalid", field_path="pillars")
    ordered: dict[str, str] = {}
    for position in _POSITIONS:
        value = pillars.get(position)
        if not isinstance(value, str) or len(value) != 2:
            raise contract_error("DERIVED_BASE_RESULT_INVALID", "pillar must be a two-character string", field_path=f"pillars.{position}")
        ordered[position] = value
    fingerprint = digest(ordered)
    if expected_pillar_fingerprint is not None and expected_pillar_fingerprint != fingerprint:
        raise contract_error("DERIVED_BASE_FINGERPRINT_MISMATCH", "pillar fingerprint does not match", field_path="pillar_fingerprint", dependency=fingerprint)
    return BaseChartRef(method, version, digest(base), fingerprint, digest(conventions))
