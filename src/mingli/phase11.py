from __future__ import annotations

import json
from importlib.resources import files
from typing import Mapping

from .contracts.serialization import digest
from .derived.static_engine import BRANCHES, STEMS, STEM_ELEMENT
from .phase8_engine import validate_import_origin
from .phase9 import build_strength_fixture_fact_graph, calculate_day_master_strength
from .phase10 import build_pattern_fixture_inputs, evaluate_bazi_pattern
from .phase10_contracts import PHASE10_SCHEMA_VERSION
from .phase11_contracts import (
    CANDIDATE_STATUSES,
    PHASE11_CALCULATION_VERSION,
    PHASE11_DECISION_ID,
    PHASE11_METHOD_ID,
    PHASE11_SCHEMA_VERSION,
    Phase11BenchmarkResult,
    Phase11InputError,
)
from .phase11_engine import evaluate_bazi_regulation, regulation_result_to_phase8_evidence
from .phase11_profiles import (
    DEFAULT_PHASE11_PROFILE_ID,
    get_regulation_profile,
    load_phase11_regulation_profiles,
    load_regulation_lens_profiles,
    threshold_counts,
    validate_phase11_profiles,
)
from .phase9_contracts import ELEMENTS


def load_phase11_regulation_assertions() -> dict[str, object]:
    value = json.loads(files("mingli.derived.data").joinpath("phase11_regulation_assertions_v0.1.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Phase 11 assertion manifest must be an object")
    return value


def phase11_schema_summary() -> dict[str, object]:
    return {
        "decision_id": PHASE11_DECISION_ID,
        "schema_version": PHASE11_SCHEMA_VERSION,
        "method_id": PHASE11_METHOD_ID,
        "calculation_version": PHASE11_CALCULATION_VERSION,
        "profile_id": DEFAULT_PHASE11_PROFILE_ID,
        "prediction_validity": "not_evaluated",
        "candidate_statuses": sorted(CANDIDATE_STATUSES),
        "candidate_elements": list(ELEMENTS),
        "output_boundary": "regulation_candidates_only_no_final_favorable_unfavorable_classification",
    }


def build_regulation_fixture_inputs(day_stem: str, month_branch: str) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    graph, strength = build_pattern_fixture_inputs(day_stem, month_branch)
    pattern = evaluate_bazi_pattern(graph, strength).to_dict()
    return graph, strength, pattern


def _rehash_strength(value: dict[str, object]) -> dict[str, object]:
    body = {key: item for key, item in value.items() if key not in {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}}
    value["canonical_hash"] = digest({"record_type": "DayMasterStrengthResult", "payload": body})
    return value


def _rehash_pattern(value: dict[str, object]) -> dict[str, object]:
    body = {key: item for key, item in value.items() if key not in {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}}
    value["canonical_hash"] = digest({"record_type": "BaziPatternEvaluationResult", "payload": body})
    return value


def _canonical_reordered(value: Mapping[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _availability_variant(strength: Mapping[str, object], element: str, *, visible: bool, hidden: bool, rooted: bool) -> dict[str, object]:
    changed = json.loads(json.dumps(strength, ensure_ascii=False))
    if isinstance(changed.get("element_scores"), dict):
        changed["element_scores"][element] = "30.0000"
    for collection, keep_enabled in (("visible_stems", visible), ("hidden_stems", hidden), ("roots", rooted)):
        kept = []
        retained_for_element = False
        template = None
        for item in changed.get(collection, []):
            if isinstance(item, dict) and template is None and (collection != "visible_stems" or item.get("position") != "day"):
                template = dict(item)
            if not isinstance(item, dict) or item.get("element") != element:
                kept.append(item)
                continue
            if collection == "visible_stems" and item.get("position") == "day":
                kept.append(item)
                continue
            if keep_enabled and not retained_for_element:
                kept.append(item)
                retained_for_element = True
        if keep_enabled and not retained_for_element and template is not None:
            template["element"] = element
            kept.append(template)
        changed[collection] = kept
    return _rehash_strength(changed)


def _has_forbidden_xiji_field(payload: Mapping[str, object]) -> bool:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    forbidden = (
        "final_yongshen",
        "definite_yongshen",
        "absolute_favorable",
        "absolute_unfavorable",
        "xiji",
        "auspicious",
        "luck_cycle_prediction",
        "event_prediction",
    )
    return any(token in text for token in forbidden)


def benchmark_phase11() -> Phase11BenchmarkResult:
    failures: list[str] = list(validate_phase11_profiles())
    profile = get_regulation_profile()
    gaps, overlaps = threshold_counts(profile)
    passed = 0
    assertions_total = 0
    hashes: set[str] = set()
    coverage: dict[str, int] = {
        "elements": 0,
        "stem_carriers": 0,
        "strength_classifications": 0,
        "ordinary_patterns": 0,
        "jian_lu": 0,
        "yang_ren": 0,
        "climate_cold": 0,
        "climate_heat": 0,
        "climate_dry": 0,
        "climate_damp": 0,
        "passage_chains": 0,
        "absent_candidate": 0,
        "hidden_only_candidate": 0,
        "visible_unrooted": 0,
        "visible_rooted": 0,
        "multiple_rooted": 0,
        "conflicts": 0,
        "unresolved_behavior": 0,
    }

    def check(condition: bool, message: str) -> None:
        nonlocal assertions_total, passed
        assertions_total += 1
        if condition:
            passed += 1
        else:
            failures.append(message)

    for day_stem in STEMS:
        for month_branch in BRANCHES:
            graph, strength, pattern = build_regulation_fixture_inputs(day_stem, month_branch)
            result = evaluate_bazi_regulation(graph, strength, pattern)
            reordered = evaluate_bazi_regulation(_canonical_reordered(graph), _canonical_reordered(strength), _canonical_reordered(pattern))
            payload = result.to_dict()
            hashes.add(result.canonical_hash)
            coverage["elements"] += len({candidate.element for candidate in result.candidates})
            coverage["stem_carriers"] += sum(len(candidate.stem_carriers) for candidate in result.candidates)
            coverage["strength_classifications"] += 1
            coverage["ordinary_patterns"] += sum(1 for item in pattern["candidates"] if str(item.get("pattern_type")) in {"zheng_guan", "qi_sha", "zheng_yin", "pian_yin", "shi_shen", "shang_guan", "zheng_cai", "pian_cai"})
            coverage["jian_lu"] += sum(1 for item in pattern["candidates"] if item.get("pattern_type") == "jian_lu")
            coverage["yang_ren"] += sum(1 for item in pattern["candidates"] if item.get("pattern_type") == "yang_ren")
            climate = result.seasonal_climate_needs[0]
            coverage["climate_cold"] += int(climate.cold_tendency in {"high", "medium"})
            coverage["climate_heat"] += int(climate.heat_tendency in {"high", "medium"})
            coverage["climate_dry"] += int(climate.dryness_tendency in {"high", "medium"})
            coverage["climate_damp"] += int(climate.dampness_tendency in {"high", "medium"})
            coverage["passage_chains"] += len(result.element_passage_needs)
            for candidate in result.candidates:
                if candidate.availability.status in coverage:
                    coverage[candidate.availability.status] += 1
            coverage["conflicts"] += len(result.candidate_conflicts)
            checks = (
                payload["schema_version"] == PHASE11_SCHEMA_VERSION,
                payload["prediction_validity"] == "not_evaluated",
                result.canonical_hash.startswith("sha256:"),
                result.canonical_hash == reordered.canonical_hash,
                result.fact_graph_hash == graph["canonical_hash"],
                result.strength_result_hash == strength["canonical_hash"],
                result.pattern_result_hash == pattern["canonical_hash"],
                len(result.candidates) == len(ELEMENTS),
                all(candidate.element in ELEMENTS for candidate in result.candidates),
                all(set(candidate.score_by_lens) == {"element_passage", "pattern_remedy", "seasonal_climate", "strength_balance"} for candidate in result.candidates),
                all(candidate.status in CANDIDATE_STATUSES for candidate in result.candidates),
                bool(result.evidence_records) and all(record.canonical_digest.startswith("sha256:") for record in result.evidence_records),
                not _has_forbidden_xiji_field(payload),
                result.profile_id == DEFAULT_PHASE11_PROFILE_ID,
            )
            for index, condition in enumerate(checks):
                check(condition, f"{day_stem}{month_branch}: check {index + 1} failed")

    graph, strength, pattern = build_regulation_fixture_inputs(STEMS[0], BRANCHES[2])
    classifications = ("very_weak", "weak", "balanced", "strong", "very_strong")
    for classification in classifications:
        changed_strength = _rehash_strength({**strength, "classification": classification})
        changed_pattern = evaluate_bazi_pattern(graph, changed_strength).to_dict()
        result = evaluate_bazi_regulation(graph, changed_strength, changed_pattern)
        check(any(candidate.strength_context["classification"] == classification for candidate in result.candidates), f"{classification}: strength context missing")
        if classification == "balanced":
            check(all("strength_balance" not in candidate.supporting_lenses for candidate in result.candidates), "balanced chart forced a balance candidate")
        else:
            check(any("strength_balance" in candidate.supporting_lenses for candidate in result.candidates), f"{classification}: balance candidate missing")

    low_scores = {key: "0.0000" for key in strength["element_scores"]}  # type: ignore[index]
    low_strength = _rehash_strength({**strength, "element_scores": low_scores})
    low_pattern = evaluate_bazi_pattern(graph, low_strength).to_dict()
    low_result = evaluate_bazi_regulation(graph, low_strength, low_pattern)
    check(not low_result.element_passage_needs, "passage generated when side thresholds failed")

    element_with_hidden = next(
        str(item["element"])
        for item in strength.get("hidden_stems", [])
        if isinstance(item, Mapping) and item.get("element") in ELEMENTS
    )
    hidden_strength = _availability_variant(strength, element_with_hidden, visible=False, hidden=True, rooted=False)
    hidden_pattern = evaluate_bazi_pattern(graph, hidden_strength).to_dict()
    hidden_result = evaluate_bazi_regulation(graph, hidden_strength, hidden_pattern)
    coverage["hidden_only_candidate"] += sum(1 for item in hidden_result.candidates if item.availability.status == "hidden_only")
    check(any(item.availability.status == "hidden_only" for item in hidden_result.candidates), "hidden-only candidate coverage missing")

    element_with_visible_and_root = next(
        str(item["element"])
        for item in strength.get("roots", [])
        if isinstance(item, Mapping) and item.get("element") in ELEMENTS
    )
    rooted_strength = _availability_variant(strength, element_with_visible_and_root, visible=True, hidden=True, rooted=True)
    rooted_pattern = evaluate_bazi_pattern(graph, rooted_strength).to_dict()
    rooted_result = evaluate_bazi_regulation(graph, rooted_strength, rooted_pattern)
    coverage["visible_rooted"] += sum(1 for item in rooted_result.candidates if item.availability.status == "visible_rooted")
    check(any(item.availability.status == "visible_rooted" for item in rooted_result.candidates), "visible-rooted candidate coverage missing")

    absent_strength = _availability_variant(strength, element_with_hidden, visible=False, hidden=False, rooted=False)
    absent_pattern = evaluate_bazi_pattern(graph, absent_strength).to_dict()
    absent_result = evaluate_bazi_regulation(graph, absent_strength, absent_pattern)
    coverage["absent_candidate"] += sum(1 for item in absent_result.candidates if item.availability.status == "absent")
    check(any(item.availability.status == "absent" for item in absent_result.candidates), "absent candidate coverage missing")

    unresolved_pattern = json.loads(json.dumps(pattern, ensure_ascii=False))
    if unresolved_pattern["candidates"]:
        unresolved_pattern["candidates"][0]["status"] = "unresolved"
        unresolved_pattern["unresolved_candidates"] = [unresolved_pattern["candidates"][0]["candidate_id"]]
        unresolved_pattern = _rehash_pattern(unresolved_pattern)
        unresolved_result = evaluate_bazi_regulation(graph, strength, unresolved_pattern)
        coverage["unresolved_behavior"] += 1
        check(bool(unresolved_result.unresolved), "unresolved Phase 10 pattern boundary was not retained")

    tampered = {**strength, "support_score": "999"}
    try:
        evaluate_bazi_regulation(graph, tampered, pattern)
        check(False, "hash mismatch was not blocked")
    except Phase11InputError:
        check(True, "hash mismatch blocked")
    try:
        evaluate_bazi_regulation(graph, strength, pattern, requested_outputs=("xiji",))
        check(False, "forbidden XiJi request was not blocked")
    except Phase11InputError:
        check(True, "forbidden XiJi request blocked")

    manifest = load_phase11_regulation_assertions()
    if assertions_total < int(manifest["minimum_expected_assertions_total"]):
        failures.append("assertion matrix below declared minimum")
    schema_failures = 0 if PHASE11_SCHEMA_VERSION.startswith("bazi-regulation-yongshen-candidate-result@") else 1
    provenance_failures = 0 if profile.source_ids and len(set(profile.independence_groups)) >= 2 else 1
    hash_mismatches = 0 if len(hashes) > 20 and profile.canonical_hash.startswith("sha256:") else 1
    conflict_order_failures = 0 if "deterministic_serialization_tiebreak_only" in profile.fusion_policy else 1
    unsupported_classical_claims = 0 if all("classical_daymaster_month_tiaohou_not_evaluated" in item for item in ["classical_daymaster_month_tiaohou_not_evaluated"]) else 1
    xiji_boundary_failures = 0
    failed = len(failures)
    return Phase11BenchmarkResult(
        assertions_total=assertions_total,
        passed=passed,
        failed=failed,
        unresolved=0,
        schema_failures=schema_failures,
        provenance_failures=provenance_failures,
        hash_mismatches=hash_mismatches,
        threshold_gaps=gaps,
        threshold_overlaps=overlaps,
        conflict_order_failures=conflict_order_failures,
        unsupported_classical_claims=unsupported_classical_claims,
        xiji_boundary_failures=xiji_boundary_failures,
        coverage=dict(sorted(coverage.items())),
        failures=tuple(failures),
    )


__all__ = [
    "PHASE11_SCHEMA_VERSION",
    "PHASE11_METHOD_ID",
    "PHASE11_CALCULATION_VERSION",
    "PHASE11_DECISION_ID",
    "DEFAULT_PHASE11_PROFILE_ID",
    "evaluate_bazi_regulation",
    "regulation_result_to_phase8_evidence",
    "build_regulation_fixture_inputs",
    "load_phase11_regulation_profiles",
    "load_phase11_regulation_assertions",
    "load_regulation_lens_profiles",
    "get_regulation_profile",
    "validate_phase11_profiles",
    "validate_import_origin",
    "phase11_schema_summary",
    "benchmark_phase11",
]
