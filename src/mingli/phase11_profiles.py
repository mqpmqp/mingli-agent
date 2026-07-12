from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from importlib.resources import files
from typing import Mapping

from .contracts.serialization import digest
from .phase11_contracts import (
    AVAILABILITY_STATUSES,
    REGULATION_LENSES,
    RegulationLensProfile,
    RegulationProfile,
)
from .phase9_contracts import ELEMENTS

DEFAULT_PHASE11_PROFILE_ID = "regulation-fusion-policy-r1@0.1"
PROFILE_RESOURCE = "phase11_regulation_profiles_v0.1.json"

FUSION_POLICY_STEPS = (
    "blocked_or_provenance_failure",
    "reality_evidence_boundary",
    "pattern_hard_contradiction",
    "multiple_lens_consensus",
    "pattern_remedy_requirement",
    "severe_structural_climate_requirement",
    "strength_balance_requirement",
    "element_passage_requirement",
    "candidate_availability",
    "deterministic_serialization_tiebreak_only",
)


def _resource(name: str):
    if "/" in name or "\\" in name:
        raise ValueError("data resource name must be a file name")
    return files("mingli.derived.data").joinpath(name)


def load_phase11_regulation_profiles() -> dict[str, object]:
    value = json.loads(_resource(PROFILE_RESOURCE).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Phase 11 profile manifest must be an object")
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


def _profile_hash(record_type: str, raw: Mapping[str, object]) -> str:
    return digest({"record_type": record_type, "payload": {key: value for key, value in raw.items() if key != "canonical_hash"}})


def _string_tuple(raw: object, field_name: str, *, minimum: int = 1) -> tuple[str, ...]:
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item for item in raw) or len(raw) < minimum:
        raise ValueError(f"{field_name} must contain at least {minimum} non-empty strings")
    return tuple(raw)


def _nonnegative_map(raw: object, field_name: str) -> tuple[dict[str, str], list[str]]:
    issues: list[str] = []
    if not isinstance(raw, Mapping) or not raw:
        return {}, [f"{field_name} must be a non-empty object"]
    parsed: dict[str, str] = {}
    for key, value in raw.items():
        number = decimal_value(value, f"{field_name}.{key}")
        if number < 0:
            issues.append(f"{field_name}.{key} must be non-negative")
        parsed[str(key)] = str(value)
    return parsed, issues


def _validate_bands(raw: object) -> tuple[tuple[Mapping[str, object], ...], int, int, list[str]]:
    if not isinstance(raw, list) or not raw:
        return (), 1, 0, ["candidate_thresholds must be a non-empty array"]
    issues: list[str] = []
    gaps = overlaps = 0
    previous = Decimal("0")
    parsed: list[Mapping[str, object]] = []
    for index, band in enumerate(raw):
        if not isinstance(band, Mapping):
            issues.append(f"candidate_thresholds[{index}] must be an object")
            continue
        lower = decimal_value(band.get("min_inclusive"), "min_inclusive")
        upper_key = "max_inclusive" if "max_inclusive" in band else "max_exclusive"
        upper = decimal_value(band.get(upper_key), upper_key)
        if lower > previous:
            gaps += 1
        elif lower < previous:
            overlaps += 1
        if upper <= lower:
            issues.append(f"candidate_thresholds[{index}] is empty")
        previous = upper
        parsed.append(dict(band))
    if previous != Decimal("100"):
        gaps += 1
    return tuple(parsed), gaps, overlaps, issues


def _parse_lens_profile(raw: Mapping[str, object]) -> tuple[RegulationLensProfile | None, list[str]]:
    issues: list[str] = []
    try:
        weights, weight_issues = _nonnegative_map(raw.get("weights"), "weights")
        issues.extend(weight_issues)
        thresholds = raw.get("thresholds")
        if not isinstance(thresholds, Mapping) or not thresholds:
            issues.append("thresholds must be a non-empty object")
            thresholds = {}
        profile = RegulationLensProfile(
            profile_id=str(raw.get("profile_id", "")),
            version=str(raw.get("version", "")),
            lens=str(raw.get("lens", "")),
            reviewed=raw.get("reviewed") is True,
            convention_summary=str(raw.get("convention_summary", "")),
            applicable_inputs=_string_tuple(raw.get("applicable_inputs"), "applicable_inputs"),
            weights=weights,
            thresholds=dict(thresholds),
            conflict_policy=_string_tuple(raw.get("conflict_policy"), "conflict_policy"),
            confidence_ceiling=str(raw.get("confidence_ceiling", "")),
            source_ids=_string_tuple(raw.get("source_ids"), "source_ids"),
            independence_groups=_string_tuple(raw.get("independence_groups"), "independence_groups", minimum=2),
            explicit_exclusions=_string_tuple(raw.get("explicit_exclusions"), "explicit_exclusions"),
            unresolved_conditions=_string_tuple(raw.get("unresolved_conditions"), "unresolved_conditions"),
            compatibility_version=str(raw.get("compatibility_version", "")),
            canonical_hash=_profile_hash("RegulationLensProfile", raw),
        )
        if not profile.profile_id or not profile.version or not profile.convention_summary or not profile.compatibility_version:
            issues.append("profile identity, summary and compatibility_version are required")
        if not profile.reviewed:
            issues.append(f"{profile.profile_id}: reviewed must be true")
        if profile.lens not in (*REGULATION_LENSES, "fusion"):
            issues.append(f"{profile.profile_id}: unsupported lens {profile.lens}")
        if len(set(profile.independence_groups)) < 2:
            issues.append(f"{profile.profile_id}: at least two independent groups are required")
        if not profile.confidence_ceiling:
            issues.append(f"{profile.profile_id}: confidence_ceiling is required")
        return profile, issues
    except (TypeError, ValueError) as exc:
        return None, issues + [str(exc)]


def load_regulation_lens_profiles() -> tuple[RegulationLensProfile, ...]:
    raw_profiles = load_phase11_regulation_profiles().get("profiles")
    if not isinstance(raw_profiles, list):
        raise ValueError("profiles must be an array")
    parsed: list[RegulationLensProfile] = []
    issues: list[str] = []
    seen: set[str] = set()
    for raw in raw_profiles:
        if not isinstance(raw, Mapping):
            issues.append("profile entry must be an object")
            continue
        profile, found = _parse_lens_profile(raw)
        issues.extend(found)
        if profile:
            if profile.profile_id in seen:
                issues.append(f"duplicate profile_id: {profile.profile_id}")
            seen.add(profile.profile_id)
            parsed.append(profile)
    if issues:
        raise ValueError("; ".join(issues))
    return tuple(sorted(parsed, key=lambda item: item.profile_id))


def _aggregate_profile(raw: Mapping[str, object], lenses: tuple[RegulationLensProfile, ...]) -> tuple[RegulationProfile | None, list[str], int, int]:
    issues: list[str] = []
    try:
        candidate_thresholds, gaps, overlaps, band_issues = _validate_bands(raw.get("candidate_thresholds"))
        issues.extend(band_issues)
        per_lens_weights, weight_issues = _nonnegative_map(raw.get("per_lens_weights"), "per_lens_weights")
        availability_weights, availability_issues = _nonnegative_map(raw.get("availability_weights"), "availability_weights")
        overcorrection_penalties, penalty_issues = _nonnegative_map(raw.get("overcorrection_penalties"), "overcorrection_penalties")
        issues.extend(weight_issues + availability_issues + penalty_issues)
        conflict_thresholds, conflict_issues = _nonnegative_map(raw.get("conflict_thresholds"), "conflict_thresholds")
        confidence_thresholds, confidence_issues = _nonnegative_map(raw.get("confidence_thresholds"), "confidence_thresholds")
        issues.extend(conflict_issues + confidence_issues)
        if set(per_lens_weights) != set(REGULATION_LENSES):
            issues.append("per_lens_weights must cover all four regulation lenses")
        if set(availability_weights) != set(AVAILABILITY_STATUSES):
            issues.append("availability_weights must cover all availability statuses")
        expected_lenses = set(REGULATION_LENSES) | {"fusion"}
        if {item.lens for item in lenses} != expected_lenses:
            issues.append("profile manifest must include four lens profiles and one fusion profile")
        if not set(FUSION_POLICY_STEPS).issubset(set(raw.get("fusion_policy", []))):
            issues.append("fusion_policy is incomplete")
        if set(raw.get("candidate_elements", [])) != set(ELEMENTS):
            issues.append("candidate_elements must cover all five elements")
        profile = RegulationProfile(
            profile_id=str(raw.get("profile_id", "")),
            version=str(raw.get("version", "")),
            reviewed=raw.get("reviewed") is True,
            convention_summary=str(raw.get("convention_summary", "")),
            lens_profiles=tuple(sorted(lenses, key=lambda item: item.profile_id)),
            score_precision=str(raw.get("score_precision", "")),
            ratio_precision=str(raw.get("ratio_precision", "")),
            rounding_mode=str(raw.get("rounding_mode", "")),
            candidate_thresholds=candidate_thresholds,
            conflict_thresholds=conflict_thresholds,
            confidence_thresholds=confidence_thresholds,
            per_lens_weights=per_lens_weights,
            availability_weights=availability_weights,
            overcorrection_penalties=overcorrection_penalties,
            fusion_policy=_string_tuple(raw.get("fusion_policy"), "fusion_policy", minimum=10),
            source_ids=_string_tuple(raw.get("source_ids"), "source_ids"),
            independence_groups=_string_tuple(raw.get("independence_groups"), "independence_groups", minimum=2),
            explicit_exclusions=_string_tuple(raw.get("explicit_exclusions"), "explicit_exclusions"),
            unresolved_conditions=_string_tuple(raw.get("unresolved_conditions"), "unresolved_conditions"),
            compatibility_version=str(raw.get("compatibility_version", "")),
            canonical_hash=digest({
                "record_type": "RegulationProfile",
                "payload": {
                    key: value for key, value in raw.items()
                    if key != "canonical_hash"
                } | {"lens_profile_hashes": [item.canonical_hash for item in sorted(lenses, key=lambda value: value.profile_id)]},
            }),
        )
        if not profile.profile_id or not profile.score_precision or not profile.ratio_precision or not profile.rounding_mode:
            issues.append("fusion profile identity and precision settings are required")
        if not profile.reviewed:
            issues.append(f"{profile.profile_id}: reviewed must be true")
        return profile, issues, gaps, overlaps
    except (TypeError, ValueError) as exc:
        return None, issues + [str(exc)], 0, 0


def get_regulation_profile(profile_id: str = DEFAULT_PHASE11_PROFILE_ID) -> RegulationProfile:
    raw_profiles = load_phase11_regulation_profiles().get("profiles")
    if not isinstance(raw_profiles, list):
        raise ValueError("profiles must be an array")
    lens_profiles = load_regulation_lens_profiles()
    for raw in raw_profiles:
        if isinstance(raw, Mapping) and raw.get("profile_id") == profile_id:
            profile, issues, _, _ = _aggregate_profile(raw, lens_profiles)
            if issues or profile is None:
                raise ValueError("; ".join(issues))
            return profile
    raise ValueError(f"unsupported regulation profile: {profile_id}")


def validate_phase11_profiles() -> tuple[str, ...]:
    raw_profiles = load_phase11_regulation_profiles().get("profiles")
    if not isinstance(raw_profiles, list):
        return ("profiles must be an array",)
    issues: list[str] = []
    parsed: list[RegulationLensProfile] = []
    seen: set[str] = set()
    for raw in raw_profiles:
        if not isinstance(raw, Mapping):
            issues.append("profile entry must be an object")
            continue
        profile, found = _parse_lens_profile(raw)
        issues.extend(found)
        profile_id = profile.profile_id if profile else str(raw.get("profile_id", "<missing>"))
        if profile_id in seen:
            issues.append(f"duplicate profile_id: {profile_id}")
        seen.add(profile_id)
        if profile:
            parsed.append(profile)
    if DEFAULT_PHASE11_PROFILE_ID in seen:
        fusion_raw = next(raw for raw in raw_profiles if isinstance(raw, Mapping) and raw.get("profile_id") == DEFAULT_PHASE11_PROFILE_ID)
        profile, found, gaps, overlaps = _aggregate_profile(fusion_raw, tuple(parsed))
        issues.extend(found)
        if gaps:
            issues.append(f"{DEFAULT_PHASE11_PROFILE_ID}: threshold gaps={gaps}")
        if overlaps:
            issues.append(f"{DEFAULT_PHASE11_PROFILE_ID}: threshold overlaps={overlaps}")
        if profile and profile.canonical_hash != get_regulation_profile(DEFAULT_PHASE11_PROFILE_ID).canonical_hash:
            issues.append(f"{DEFAULT_PHASE11_PROFILE_ID}: canonical hash is unstable")
    else:
        issues.append(f"missing fusion profile: {DEFAULT_PHASE11_PROFILE_ID}")
    return tuple(issues)


def threshold_counts(profile: RegulationProfile) -> tuple[int, int]:
    _, gaps, overlaps, _ = _validate_bands(list(profile.candidate_thresholds))
    return gaps, overlaps
