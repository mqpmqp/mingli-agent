from __future__ import annotations

import json
from importlib.resources import files

from .models import DERIVED_METHOD_ID, DerivedConventionProfile, DerivedError
from .serialization import digest


class DerivedContractError(ValueError):
    def __init__(self, error: DerivedError):
        self.error = error
        super().__init__(f"{error.code}: {error.message}")


_PROFILE_COMPONENTS = {
    "derived-static-r1@0.1": {
        "hidden_stems": "hidden-stems-r1@0.1",
        "ten_gods": "ten-gods-r1@0.1",
        "nayin": "nayin-r1@0.1",
        "xunkong": "xunkong-r1@0.1",
    }
}


def contract_error(code: str, message: str, *, field_path: str = "", dependency: str = "", profile_id: str = "") -> DerivedContractError:
    return DerivedContractError(DerivedError(code, message, field_path, dependency, DERIVED_METHOD_ID, profile_id))


def load_convention_profile(profile_id: str) -> DerivedConventionProfile:
    components = _PROFILE_COMPONENTS.get(profile_id)
    if components is None:
        raise contract_error("DERIVED_CONVENTION_UNSUPPORTED", "unsupported convention profile", field_path="convention_profile.profile_id", profile_id=profile_id)
    payload = {"profile_id": profile_id, "profile_version": "0.1.0", "components": components}
    return DerivedConventionProfile(profile_id, "0.1.0", tuple(sorted(components.items())), digest(payload))


def get_schema(name: str) -> dict[str, object]:
    if "/" in name or "\\" in name:
        raise ValueError("schema name must be a file name")
    resource = files("mingli.contracts.schemas").joinpath(name)
    if not resource.is_file():
        raise FileNotFoundError(name)
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"schema is not an object: {name}")
    return value
