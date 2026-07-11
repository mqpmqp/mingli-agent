from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal

DERIVED_SCHEMA_VERSION = "bazi-derived-structure-result@0.1"
DERIVED_METHOD_ID = "bazi-derived-structure@0.1.0"
DERIVED_CALCULATION_VERSION = "0.1.0"


class Serializable:
    def to_dict(self) -> dict[str, object]:
        from .serialization import canonical_json

        return json.loads(canonical_json(asdict(self)))


@dataclass(frozen=True)
class BaseChartRef(Serializable):
    base_method_id: str
    base_calculation_version: str
    base_result_sha256: str
    pillar_fingerprint: str
    base_convention_digest: str


@dataclass(frozen=True)
class DerivedConventionProfile(Serializable):
    profile_id: str
    profile_version: str
    components: tuple[tuple[str, str], ...]
    canonical_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "components": dict(self.components),
            "canonical_sha256": self.canonical_sha256,
        }


@dataclass(frozen=True)
class TenGodRecord(Serializable):
    code: str
    label: str
    source_ids: tuple[str, ...]
    determinism_level: Literal["D1", "D2"] = "D1"
    verification_status: Literal["verified", "unresolved"] = "verified"


@dataclass(frozen=True)
class HiddenStemRecord(Serializable):
    ordinal: int
    stem: str
    ten_god: TenGodRecord | None = None


@dataclass(frozen=True)
class NayinRecord(Serializable):
    code: str
    label: str
    source_ids: tuple[str, ...]
    verification_status: Literal["verified", "unresolved"] = "verified"


@dataclass(frozen=True)
class XunKongRecord(Serializable):
    xun_start: str
    xun_sequence: int
    void_branches: tuple[str, str]
    source_ids: tuple[str, ...]
    verification_status: Literal["verified", "unresolved"] = "verified"


@dataclass(frozen=True)
class DerivedPillar(Serializable):
    position: Literal["year", "month", "day", "hour"]
    stem: str
    branch: str
    stem_ten_god: TenGodRecord | None = None
    hidden_stems: tuple[HiddenStemRecord, ...] = ()
    nayin: NayinRecord | None = None
    xunkong: XunKongRecord | None = None


@dataclass(frozen=True)
class DependencyAmbiguity(Serializable):
    dependency: str
    field_paths: tuple[str, ...]
    source_ids: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class DerivedError(Serializable):
    code: str
    message: str
    field_path: str
    dependency: str
    method_id: str
    profile_id: str


@dataclass(frozen=True)
class DerivedChartResult(Serializable):
    base_ref: BaseChartRef
    convention_profile: DerivedConventionProfile
    status: Literal["complete", "partial", "refused"] = "complete"
    pillars: tuple[DerivedPillar, ...] = ()
    ambiguities: tuple[DependencyAmbiguity, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[DerivedError, ...] = ()
    schema_version: str = field(default=DERIVED_SCHEMA_VERSION, init=False)
    method_id: str = field(default=DERIVED_METHOD_ID, init=False)
    calculation_version: str = field(default=DERIVED_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def __post_init__(self) -> None:
        if self.status == "partial" and not self.ambiguities:
            raise ValueError("partial result requires at least one ambiguity")
        if self.status == "complete" and (self.ambiguities or self.errors):
            raise ValueError("complete result cannot contain ambiguities or errors")

    def to_dict(self) -> dict[str, object]:
        return {
            "base_ref": self.base_ref.to_dict(),
            "convention_profile": self.convention_profile.to_dict(),
            "status": self.status,
            "pillars": [pillar.to_dict() for pillar in self.pillars],
            "ambiguities": [ambiguity.to_dict() for ambiguity in self.ambiguities],
            "warnings": list(self.warnings),
            "errors": [error.to_dict() for error in self.errors],
            "schema_version": self.schema_version,
            "method_id": self.method_id,
            "calculation_version": self.calculation_version,
            "prediction_validity": self.prediction_validity,
        }
