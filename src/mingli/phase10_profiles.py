from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from importlib.resources import files
from typing import Mapping

from .contracts.serialization import digest
from .phase10_contracts import ORDINARY_PATTERN_TYPES, PatternProfile, SUPPORTED_PATTERN_TYPES

DEFAULT_PHASE10_PROFILE_ID = "bazi-pattern-evaluation-r1@0.1"
PROFILE_RESOURCE = "phase10_pattern_profiles_v0.1.json"


def _resource(name: str):
    if "/" in name or "\\" in name:
        raise ValueError("data resource name must be a file name")
    return files("mingli.derived.data").joinpath(name)


def load_phase10_pattern_profiles() -> dict[str, object]:
    value = json.loads(_resource(PROFILE_RESOURCE).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Phase 10 profile manifest must be an object")
    return value


def decimal_value(value: object, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field_name} must be a decimal string")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a decimal string") from exc
    if not number.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return number


def _profile_hash(raw: Mapping[str, object]) -> str:
    return digest({"record_type": "PatternProfile", "payload": {key: value for key, value in raw.items() if key != "canonical_hash"}})


def _string_tuple(raw: object, field_name: str, *, minimum: int = 1) -> tuple[str, ...]:
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item for item in raw) or len(raw) < minimum:
        raise ValueError(f"{field_name} must contain at least {minimum} non-empty strings")
    return tuple(raw)


def _validate_thresholds(raw: object) -> tuple[tuple[Mapping[str, object], ...], int, int, list[str]]:
    if not isinstance(raw, list) or not raw:
        return (), 0, 0, ["purity_thresholds must be a non-empty array"]
    gaps = overlaps = 0
    issues: list[str] = []
    previous = Decimal("0")
    parsed: list[Mapping[str, object]] = []
    for index, band in enumerate(raw):
        if not isinstance(band, Mapping):
            issues.append(f"purity_thresholds[{index}] must be an object")
            continue
        lower = decimal_value(band.get("min_inclusive"), "min_inclusive")
        upper_key = "max_inclusive" if "max_inclusive" in band else "max_exclusive"
        upper = decimal_value(band.get(upper_key), upper_key)
        if lower > previous:
            gaps += 1
        elif lower < previous:
            overlaps += 1
        if upper <= lower:
            issues.append(f"purity_thresholds[{index}] is empty")
        previous = upper
        parsed.append(dict(band))
    if previous != Decimal("100"):
        gaps += 1
    return tuple(parsed), gaps, overlaps, issues


def _parse_profile(raw: Mapping[str, object]) -> tuple[PatternProfile | None, list[str], int, int]:
    issues: list[str] = []
    try:
        required_maps = (
            "hidden_stem_priority", "establishment_weights", "break_weights", "rescue_weights",
            "ordinary_pattern_rules", "jianlu_rules", "yangren_rules", "special_pattern_candidate_rules",
        )
        for key in required_maps:
            if not isinstance(raw.get(key), Mapping) or not raw[key]:
                issues.append(f"{key} must be a non-empty object")
        thresholds, gaps, overlaps, threshold_issues = _validate_thresholds(raw.get("purity_thresholds"))
        issues.extend(threshold_issues)
        for group in ("establishment_weights", "break_weights", "rescue_weights"):
            value = raw.get(group, {})
            if isinstance(value, Mapping):
                for key, weight in value.items():
                    if decimal_value(weight, f"{group}.{key}") < 0:
                        issues.append(f"{group}.{key} must be non-negative")
        rules = raw.get("ordinary_pattern_rules", {})
        if isinstance(rules, Mapping) and set(rules) != set(ORDINARY_PATTERN_TYPES):
            issues.append("ordinary_pattern_rules must cover all eight ordinary patterns")
        source_order = _string_tuple(raw.get("candidate_source_order"), "candidate_source_order", minimum=7)
        conflict_order = _string_tuple(raw.get("conflict_resolution_order"), "conflict_resolution_order", minimum=9)
        expected_conflicts = {"month_command_over_non_month", "principal_over_middle_over_residual", "transparent_over_nontransparent", "equal_rank_conflict_is_unresolved"}
        if not expected_conflicts.issubset(conflict_order):
            issues.append("conflict_resolution_order is incomplete")
        profile = PatternProfile(
            profile_id=str(raw.get("profile_id", "")), version=str(raw.get("version", "")),
            reviewed=raw.get("reviewed") is True, convention_summary=str(raw.get("convention_summary", "")),
            candidate_source_order=source_order,
            hidden_stem_priority={str(key): int(value) for key, value in dict(raw.get("hidden_stem_priority", {})).items()},
            establishment_weights={str(key): str(value) for key, value in dict(raw.get("establishment_weights", {})).items()},
            break_weights={str(key): str(value) for key, value in dict(raw.get("break_weights", {})).items()},
            rescue_weights={str(key): str(value) for key, value in dict(raw.get("rescue_weights", {})).items()},
            purity_thresholds=thresholds, primary_candidate_threshold=str(raw.get("primary_candidate_threshold", "")),
            conflict_resolution_order=conflict_order, ordinary_pattern_rules=dict(raw.get("ordinary_pattern_rules", {})),
            jianlu_rules=dict(raw.get("jianlu_rules", {})), yangren_rules=dict(raw.get("yangren_rules", {})),
            special_pattern_candidate_rules=dict(raw.get("special_pattern_candidate_rules", {})),
            source_ids=_string_tuple(raw.get("source_ids"), "source_ids"),
            independence_groups=_string_tuple(raw.get("independence_groups"), "independence_groups", minimum=2),
            explicit_exclusions=_string_tuple(raw.get("explicit_exclusions"), "explicit_exclusions"),
            unresolved_conditions=_string_tuple(raw.get("unresolved_conditions"), "unresolved_conditions"),
            compatibility_version=str(raw.get("compatibility_version", "")), canonical_hash=_profile_hash(raw),
        )
        if not profile.profile_id or not profile.version or not profile.convention_summary or not profile.compatibility_version:
            issues.append("profile identity, summary and compatibility_version are required")
        if not profile.reviewed:
            issues.append(f"{profile.profile_id}: reviewed must be true")
        if len(set(profile.independence_groups)) < 2:
            issues.append(f"{profile.profile_id}: at least two independent groups are required")
        if set(profile.special_pattern_candidate_rules.get("very_weak", [])) - set(SUPPORTED_PATTERN_TYPES):
            issues.append("special pattern rules contain unsupported types")
        return profile, issues, gaps, overlaps
    except (TypeError, ValueError) as exc:
        return None, issues + [str(exc)], 0, 0


def load_pattern_profiles() -> tuple[PatternProfile, ...]:
    raw_profiles = load_phase10_pattern_profiles().get("profiles")
    if not isinstance(raw_profiles, list):
        raise ValueError("profiles must be an array")
    parsed: list[PatternProfile] = []
    issues: list[str] = []
    seen: set[str] = set()
    for raw in raw_profiles:
        if not isinstance(raw, Mapping):
            issues.append("profile entry must be an object")
            continue
        profile, found, _, _ = _parse_profile(raw)
        issues.extend(found)
        if profile:
            if profile.profile_id in seen:
                issues.append(f"duplicate profile_id: {profile.profile_id}")
            seen.add(profile.profile_id)
            parsed.append(profile)
    if issues:
        raise ValueError("; ".join(issues))
    return tuple(sorted(parsed, key=lambda item: item.profile_id))


def get_pattern_profile(profile_id: str = DEFAULT_PHASE10_PROFILE_ID) -> PatternProfile:
    for profile in load_pattern_profiles():
        if profile.profile_id == profile_id:
            return profile
    raise ValueError(f"unsupported pattern profile: {profile_id}")


def validate_phase10_profiles() -> tuple[str, ...]:
    raw_profiles = load_phase10_pattern_profiles().get("profiles")
    if not isinstance(raw_profiles, list):
        return ("profiles must be an array",)
    issues: list[str] = []
    seen: set[str] = set()
    for raw in raw_profiles:
        if not isinstance(raw, Mapping):
            issues.append("profile entry must be an object")
            continue
        profile, found, gaps, overlaps = _parse_profile(raw)
        issues.extend(found)
        profile_id = profile.profile_id if profile else str(raw.get("profile_id", "<missing>"))
        if profile_id in seen:
            issues.append(f"duplicate profile_id: {profile_id}")
        seen.add(profile_id)
        if gaps:
            issues.append(f"{profile_id}: threshold gaps={gaps}")
        if overlaps:
            issues.append(f"{profile_id}: threshold overlaps={overlaps}")
    return tuple(issues)


def threshold_counts(profile: PatternProfile) -> tuple[int, int]:
    _, gaps, overlaps, _ = _validate_thresholds(list(profile.purity_thresholds))
    return gaps, overlaps
