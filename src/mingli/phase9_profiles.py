from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from importlib.resources import files
from typing import Mapping

from .contracts.serialization import digest
from .phase9_contracts import (
    CLASSIFICATIONS,
    ELEMENTS,
    StrengthProfile,
)

DEFAULT_PHASE9_PROFILE_ID = "strength-quantification-r1@0.1"
PROFILE_RESOURCE = "phase9_strength_profiles_v0.1.json"


def _data_file(name: str):
    if "/" in name or "\\" in name:
        raise ValueError("data resource name must be a file name")
    return files("mingli.derived.data").joinpath(name)


def _load_json_resource(name: str) -> dict[str, object]:
    value = json.loads(_data_file(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"data resource is not an object: {name}")
    return value


def load_phase9_strength_profiles() -> dict[str, object]:
    return _load_json_resource(PROFILE_RESOURCE)


def decimal_from(value: object, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field_name} must be a Decimal string")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a Decimal string") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


def _require_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _string_tuple(value: object, field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, list | tuple):
        raise ValueError(f"{field_name} must be an array of strings")
    result = tuple(value)
    if not allow_empty and not result:
        raise ValueError(f"{field_name} must not be empty")
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{field_name} must contain non-empty strings only")
    return result


def _profile_hash(raw: Mapping[str, object]) -> str:
    body = {key: value for key, value in raw.items() if key != "canonical_hash"}
    return digest({"record_type": "StrengthProfile", "payload": body})


def _threshold_bounds(threshold: Mapping[str, object]) -> tuple[Decimal, Decimal | None]:
    lower = decimal_from(threshold.get("min_inclusive"), "classification_thresholds.min_inclusive")
    upper_value = threshold.get("max_exclusive", threshold.get("max_inclusive"))
    upper = None if upper_value is None else decimal_from(upper_value, "classification_thresholds.max")
    return lower, upper


def _validate_thresholds(thresholds: object) -> tuple[list[str], int, int]:
    issues: list[str] = []
    gaps = 0
    overlaps = 0
    if not isinstance(thresholds, list) or not thresholds:
        return ["classification_thresholds must be a non-empty array"], 0, 0
    seen: set[str] = set()
    previous_upper: Decimal | None = None
    balanced_seen = False
    for index, item in enumerate(thresholds):
        if not isinstance(item, Mapping):
            issues.append(f"classification_thresholds[{index}] must be an object")
            continue
        classification = item.get("classification")
        if classification not in CLASSIFICATIONS - {"unresolved"}:
            issues.append(f"classification_thresholds[{index}] has invalid classification")
            continue
        if classification in seen:
            issues.append(f"classification threshold duplicated: {classification}")
        seen.add(str(classification))
        balanced_seen = balanced_seen or classification == "balanced"
        lower, upper = _threshold_bounds(item)
        if lower < Decimal("0") or (upper is not None and upper > Decimal("1")):
            issues.append(f"classification threshold out of ratio bounds: {classification}")
        if upper is not None and lower >= upper:
            issues.append(f"classification threshold lower >= upper: {classification}")
        if previous_upper is not None:
            if lower > previous_upper:
                gaps += 1
            if lower < previous_upper:
                overlaps += 1
        previous_upper = upper
    if previous_upper is not None and previous_upper != Decimal("1"):
        gaps += 1
    if not balanced_seen:
        issues.append("balanced classification threshold is required")
    return issues, gaps, overlaps


def _walk_weights(value: object, prefix: str = "weights") -> tuple[str, ...]:
    issues: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            issues.extend(_walk_weights(child, f"{prefix}.{key}"))
        return tuple(issues)
    if isinstance(value, list | tuple):
        for index, child in enumerate(value):
            issues.extend(_walk_weights(child, f"{prefix}[{index}]"))
        return tuple(issues)
    number = decimal_from(value, prefix)
    if number < Decimal("0"):
        return (f"{prefix} must be non-negative",)
    return ()


def _validate_single_profile(raw: Mapping[str, object]) -> tuple[StrengthProfile | None, tuple[str, ...], int, int]:
    issues: list[str] = []
    threshold_gaps = threshold_overlaps = 0
    try:
        profile_id = _require_string(raw.get("profile_id"), "profile_id")
        version = _require_string(raw.get("version"), "version")
        convention_summary = _require_string(raw.get("convention_summary"), "convention_summary")
        reviewed = raw.get("reviewed")
        if reviewed is not True:
            issues.append(f"{profile_id}: reviewed must be true")
        source_ids = _string_tuple(raw.get("source_ids"), "source_ids")
        independence_groups = _string_tuple(raw.get("independence_groups"), "independence_groups")
        if len(set(independence_groups)) < 2:
            issues.append(f"{profile_id}: at least two independence_groups are required")
        explicit_exclusions = _string_tuple(raw.get("explicit_exclusions"), "explicit_exclusions")
        unresolved_conditions = _string_tuple(raw.get("unresolved_conditions"), "unresolved_conditions", allow_empty=True)
        compatibility_version = _require_string(raw.get("compatibility_version"), "compatibility_version")
        weights = raw.get("weights")
        if not isinstance(weights, Mapping):
            issues.append(f"{profile_id}: weights must be an object")
            weights = {}
        else:
            issues.extend(f"{profile_id}: {issue}" for issue in _walk_weights(weights))
            branch_weights = weights.get("branch_position_weights")
            if isinstance(branch_weights, Mapping):
                month_weight = decimal_from(branch_weights.get("month"), "weights.branch_position_weights.month")
                for position, value in branch_weights.items():
                    if position != "month" and decimal_from(value, f"weights.branch_position_weights.{position}") > month_weight:
                        issues.append(f"{profile_id}: month branch must remain the highest branch-position weight")
        thresholds = raw.get("classification_thresholds")
        threshold_issues, threshold_gaps, threshold_overlaps = _validate_thresholds(thresholds)
        issues.extend(f"{profile_id}: {issue}" for issue in threshold_issues)
        quantity = raw.get("quantity")
        if not isinstance(quantity, Mapping):
            issues.append(f"{profile_id}: quantity must be an object")
            quantity = {}
        toggles = raw.get("toggles")
        if not isinstance(toggles, Mapping):
            issues.append(f"{profile_id}: toggles must be an object")
            toggles = {}
        same_type_relations = _string_tuple(raw.get("same_type_relations"), "same_type_relations")
        different_type_relations = _string_tuple(raw.get("different_type_relations"), "different_type_relations")
        expected_relations = {"peer", "resource", "output", "wealth", "authority"}
        if set(same_type_relations) != {"peer", "resource"}:
            issues.append(f"{profile_id}: same_type_relations must be peer/resource")
        if set(different_type_relations) != {"output", "wealth", "authority"}:
            issues.append(f"{profile_id}: different_type_relations must be output/wealth/authority")
        if set(same_type_relations) | set(different_type_relations) != expected_relations:
            issues.append(f"{profile_id}: relationship coverage is incomplete")
        if "classification_thresholds" not in raw:
            thresholds = []
        profile = StrengthProfile(
            profile_id=profile_id,
            version=version,
            convention_summary=convention_summary,
            reviewed=reviewed is True,
            weights=dict(weights),
            classification_thresholds=tuple(dict(item) for item in thresholds if isinstance(item, Mapping)),  # type: ignore[arg-type]
            source_ids=source_ids,
            independence_groups=tuple(dict.fromkeys(independence_groups)),
            explicit_exclusions=explicit_exclusions,
            unresolved_conditions=unresolved_conditions,
            compatibility_version=compatibility_version,
            quantity=dict(quantity),
            toggles=dict(toggles),
            same_type_relations=same_type_relations,
            different_type_relations=different_type_relations,
            canonical_hash=_profile_hash(raw),
        )
    except ValueError as exc:
        issues.append(str(exc))
        return None, tuple(issues), threshold_gaps, threshold_overlaps
    stable_hash = _profile_hash(profile.to_dict())
    if stable_hash != profile.canonical_hash:
        issues.append(f"{profile.profile_id}: canonical hash is not stable")
    return profile, tuple(issues), threshold_gaps, threshold_overlaps


def load_strength_profiles() -> tuple[StrengthProfile, ...]:
    manifest = load_phase9_strength_profiles()
    raw_profiles = manifest.get("profiles")
    if not isinstance(raw_profiles, list):
        raise ValueError("profiles must be an array")
    profiles: list[StrengthProfile] = []
    issues: list[str] = []
    seen: set[str] = set()
    for raw in raw_profiles:
        if not isinstance(raw, Mapping):
            issues.append("profile entry must be an object")
            continue
        profile, profile_issues, _, _ = _validate_single_profile(raw)
        issues.extend(profile_issues)
        if profile is None:
            continue
        if profile.profile_id in seen:
            issues.append(f"profile_id duplicated: {profile.profile_id}")
        seen.add(profile.profile_id)
        profiles.append(profile)
    if issues:
        raise ValueError("; ".join(issues))
    return tuple(sorted(profiles, key=lambda item: item.profile_id))


def get_strength_profile(profile_id: str = DEFAULT_PHASE9_PROFILE_ID) -> StrengthProfile:
    for profile in load_strength_profiles():
        if profile.profile_id == profile_id:
            return profile
    raise ValueError(f"profile not found: {profile_id}")


def validate_phase9_profiles() -> tuple[str, ...]:
    manifest = load_phase9_strength_profiles()
    raw_profiles = manifest.get("profiles")
    if not isinstance(raw_profiles, list):
        return ("profiles must be an array",)
    issues: list[str] = []
    seen: set[str] = set()
    for raw in raw_profiles:
        if not isinstance(raw, Mapping):
            issues.append("profile entry must be an object")
            continue
        profile_id = str(raw.get("profile_id", "<missing>"))
        if profile_id in seen:
            issues.append(f"profile_id duplicated: {profile_id}")
        seen.add(profile_id)
        _, profile_issues, gaps, overlaps = _validate_single_profile(raw)
        issues.extend(profile_issues)
        if gaps:
            issues.append(f"{profile_id}: threshold gaps={gaps}")
        if overlaps:
            issues.append(f"{profile_id}: threshold overlaps={overlaps}")
    return tuple(issues)


def threshold_gap_overlap_counts(profile: StrengthProfile) -> tuple[int, int]:
    _, gaps, overlaps = _validate_thresholds(list(profile.classification_thresholds))
    return gaps, overlaps


def classify_ratio(profile: StrengthProfile, ratio: Decimal) -> tuple[str, Mapping[str, object]]:
    if ratio < Decimal("0") or ratio > Decimal("1"):
        return "unresolved", {"reason": "ratio_out_of_bounds"}
    for threshold in profile.classification_thresholds:
        lower, upper = _threshold_bounds(threshold)
        upper_key = "max_inclusive" if "max_inclusive" in threshold else "max_exclusive"
        upper_value = threshold.get(upper_key)
        lower_ok = ratio >= lower
        upper_ok = True if upper is None else (ratio <= upper if upper_key == "max_inclusive" else ratio < upper)
        if lower_ok and upper_ok:
            return str(threshold["classification"]), dict(threshold)
    return "unresolved", {"reason": "no_classification_band_matched"}


def profile_decimal(profile: StrengthProfile, path: str) -> Decimal:
    current: object = profile.to_dict()
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ValueError(f"profile path not found: {path}")
        current = current[part]
    return decimal_from(current, path)


def element_zero_scores() -> dict[str, Decimal]:
    return {element: Decimal("0") for element in ELEMENTS}

