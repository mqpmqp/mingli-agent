from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

CAPABILITIES = frozenset({"hidden_stems", "visible_stem_ten_gods", "hidden_stem_ten_gods", "nayin", "xunkong"})


@dataclass(frozen=True)
class SourceManifestValidation:
    implementation_ready: tuple[str, ...]
    issues: tuple[str, ...]


def validate_source_manifest(manifest: Mapping[str, object]) -> SourceManifestValidation:
    issues: list[str] = []
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        return SourceManifestValidation((), ("sources must be a list",))
    groups: dict[str, set[str]] = {capability: set() for capability in CAPABILITIES}
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            issues.append(f"sources[{index}] must be an object")
            continue
        required = {"source_id", "title", "author_institution", "locator", "version_edition", "page_anchor", "accessed_at", "license_usage_note", "independence_group", "verification_status", "capabilities"}
        missing = sorted(required - source.keys())
        if missing:
            issues.append(f"sources[{index}] missing: {', '.join(missing)}")
            continue
        if source["verification_status"] != "reviewed":
            continue
        capabilities = source["capabilities"]
        if not isinstance(capabilities, list):
            issues.append(f"sources[{index}].capabilities must be a list")
            continue
        for capability in capabilities:
            if capability in groups:
                groups[capability].add(str(source["independence_group"]))
    ready = tuple(sorted(capability for capability, values in groups.items() if len(values) >= 2))
    for capability in sorted(CAPABILITIES - set(ready)):
        issues.append(f"{capability} requires two reviewed independence groups")
    return SourceManifestValidation(ready, tuple(issues))
