from __future__ import annotations

from decimal import Decimal
import json
from importlib.resources import files
from pathlib import Path
from typing import Mapping

from .contracts.serialization import digest
from .derived.static_engine import BRANCHES, STEMS, STEM_ELEMENT
from .phase8_engine import validate_import_origin
from .phase9_contracts import (
    CLASSIFICATIONS,
    ELEMENTS,
    PHASE9_CALCULATION_VERSION,
    PHASE9_DECISION_ID,
    PHASE9_METHOD_ID,
    PHASE9_SCHEMA_VERSION,
    Phase9BenchmarkResult,
    Phase9InputError,
)
from .phase9_engine import (
    build_strength_fixture_fact_graph,
    calculate_day_master_strength,
    relationship_to_day_master,
    strength_result_to_phase8_evidence,
)
from .phase9_profiles import (
    DEFAULT_PHASE9_PROFILE_ID,
    classify_ratio,
    get_strength_profile,
    load_phase9_strength_profiles,
    load_strength_profiles,
    threshold_gap_overlap_counts,
    validate_phase9_profiles,
)


def _data_file(name: str):
    if "/" in name or "\\" in name:
        raise ValueError("data resource name must be a file name")
    return files("mingli.derived.data").joinpath(name)


def load_phase9_strength_assertions() -> dict[str, object]:
    value = json.loads(_data_file("phase9_strength_assertions_v0.1.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("phase9 assertion resource must be an object")
    return value


def phase9_schema_summary() -> dict[str, object]:
    return {
        "schemas": {
            "DayMasterStrengthResult": PHASE9_SCHEMA_VERSION,
            "StrengthProfile": "phase9-strength-profile@0.1",
            "ElementContribution": "phase9-element-contribution@0.1",
            "RootContribution": "phase9-root-contribution@0.1",
            "SeasonalContribution": "phase9-seasonal-contribution@0.1",
            "StemContribution": "phase9-stem-contribution@0.1",
            "BranchContribution": "phase9-branch-contribution@0.1",
            "StrengthEvidenceRecord": "phase9-strength-evidence-record@0.1",
        },
        "method_id": PHASE9_METHOD_ID,
        "calculation_version": PHASE9_CALCULATION_VERSION,
        "decision_id": PHASE9_DECISION_ID,
        "default_profile_id": DEFAULT_PHASE9_PROFILE_ID,
        "classifications": sorted(CLASSIFICATIONS),
        "prediction_validity": "not_evaluated",
    }


def _assert(condition: bool, failures: list[str], message: str) -> int:
    if condition:
        return 1
    failures.append(message)
    return 0


def _fixture_for(day_stem: str, month_branch: str) -> dict[str, object]:
    return build_strength_fixture_fact_graph(
        year=(STEMS[0], BRANCHES[0]),
        month=(STEMS[2], month_branch),
        day=(day_stem, BRANCHES[4]),
        hour=(STEMS[6], BRANCHES[8]),
    )


def _canonical_reordered(value: Mapping[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def benchmark_phase9() -> Phase9BenchmarkResult:
    failures: list[str] = []
    profile_assertions = element_assertions = seasonal_assertions = contribution_assertions = 0
    classification_assertions = deterministic_assertions = blocked_assertions = 0
    schema_failures = provenance_failures = hash_mismatches = 0
    passed = 0

    profiles = load_strength_profiles()
    profile = get_strength_profile()
    profile_issues = validate_phase9_profiles()
    gaps, overlaps = threshold_gap_overlap_counts(profile)
    assertion_manifest = load_phase9_strength_assertions()
    profile_checks = (
        not profile_issues,
        len(profiles) == 1,
        profile.reviewed,
        len(profile.source_ids) >= 1,
        len(profile.independence_groups) >= 2,
        bool(profile.explicit_exclusions),
        profile.canonical_hash.startswith("sha256:"),
        gaps == 0,
        overlaps == 0,
        assertion_manifest.get("minimum_expected_assertions_total") == 300,
    )
    for index, check in enumerate(profile_checks, 1):
        profile_assertions += 1
        passed += _assert(check, failures, f"profile assertion failed: {index}")

    allowed_relations = {"peer", "resource", "output", "wealth", "authority"}
    for day_stem in STEMS:
        day_element = STEM_ELEMENT[day_stem]
        coverage: set[str] = set()
        for target_stem in STEMS:
            target_element = STEM_ELEMENT[target_stem]
            relation, direction = relationship_to_day_master(day_element, target_element)
            coverage.add(relation)
            element_assertions += 3
            passed += _assert(relation in allowed_relations, failures, "unexpected element relationship")
            passed += _assert(direction in {"support", "oppose"}, failures, "unexpected support direction")
            passed += _assert((relation in {"peer", "resource"}) == (direction == "support"), failures, "same/different type mapping mismatch")
        element_assertions += 1
        passed += _assert(coverage == allowed_relations, failures, f"relationship coverage mismatch for {day_stem}")
    element_assertions += len(ELEMENTS)
    covered_elements = {STEM_ELEMENT[stem] for stem in STEMS}
    for element in ELEMENTS:
        passed += _assert(element in covered_elements, failures, f"element not covered: {element}")

    for branch in BRANCHES:
        graph = _fixture_for(STEMS[0], branch)
        result = calculate_day_master_strength(graph)
        payload = result.to_dict()
        seasonal = payload["seasonal_state"]
        seasonal_assertions += 4
        passed += _assert(seasonal["month_branch"] == branch, failures, "seasonal month branch mismatch")
        passed += _assert(len(seasonal["contributions"]) >= 1, failures, "seasonal contributions missing")  # type: ignore[arg-type]
        passed += _assert(str(seasonal["dominant_element"]) in ELEMENTS, failures, "seasonal dominant element missing")
        passed += _assert(all(item["canonical_digest"].startswith("sha256:") for item in seasonal["contributions"]), failures, "seasonal digest missing")  # type: ignore[index]

    classifications_seen: set[str] = set()
    hashes: set[str] = set()
    for day_stem in STEMS:
        for branch in BRANCHES:
            graph = _fixture_for(day_stem, branch)
            result = calculate_day_master_strength(graph)
            payload = result.to_dict()
            classifications_seen.add(str(payload["classification"]))
            hashes.add(result.canonical_hash)
            contribution_assertions += 6
            passed += _assert(payload["prediction_validity"] == "not_evaluated", failures, "prediction boundary changed")
            passed += _assert(set(payload["element_scores"]) == set(ELEMENTS), failures, "element score coverage mismatch")  # type: ignore[arg-type]
            passed += _assert(len(payload["visible_stems"]) == 4, failures, "visible stem count mismatch")  # type: ignore[arg-type]
            passed += _assert(len(payload["hidden_stems"]) >= 4, failures, "hidden stem records missing")  # type: ignore[arg-type]
            passed += _assert(all(str(item["canonical_digest"]).startswith("sha256:") for item in payload["contribution_records"]), failures, "contribution digest missing")  # type: ignore[index]
            passed += _assert(bool(payload["supporting_evidence"]) or bool(payload["contradicting_evidence"]), failures, "strength evidence missing")
    contribution_assertions += 2
    passed += _assert(len(hashes) > 20, failures, "fixture hash diversity too low")
    passed += _assert(classifications_seen <= CLASSIFICATIONS, failures, "unknown classification emitted")

    for ratio, expected in (
        (Decimal("0.0000"), "very_weak"),
        (Decimal("0.2000"), "weak"),
        (Decimal("0.4500"), "balanced"),
        (Decimal("0.5500"), "strong"),
        (Decimal("0.8000"), "very_strong"),
    ):
        classification, band = classify_ratio(profile, ratio)
        classification_assertions += 2
        passed += _assert(classification == expected, failures, f"classification boundary mismatch: {ratio}")
        passed += _assert(band.get("classification") == expected, failures, "classification band mismatch")
    sample_graph = _fixture_for(STEMS[0], BRANCHES[0])
    sample = calculate_day_master_strength(sample_graph)
    sample_reordered = calculate_day_master_strength(_canonical_reordered(sample_graph))
    deterministic_assertions += 6
    passed += _assert(sample.canonical_hash == sample_reordered.canonical_hash, failures, "hash changed after JSON key reorder")
    passed += _assert(sample.to_dict() == sample_reordered.to_dict(), failures, "payload changed after JSON key reorder")
    passed += _assert(digest(sample.to_dict()).startswith("sha256:"), failures, "result digest missing")
    passed += _assert(sample.method_id == PHASE9_METHOD_ID, failures, "method id mismatch")
    passed += _assert(sample.schema_version == PHASE9_SCHEMA_VERSION, failures, "schema version mismatch")
    passed += _assert(sample.profile_id == profile.profile_id, failures, "profile id mismatch")

    for bad_graph, pattern in (
        ({}, "missing nodes"),
        ({**sample_graph, "prediction_validity": "evaluated"}, "prediction_validity"),
        ({**sample_graph, "nodes": [node for node in sample_graph["nodes"] if node.get("node_type") != "Pillar"]}, "missing four pillars"),
        ({**sample_graph, "edges": []}, "hidden-stem structure"),
    ):
        blocked_assertions += 1
        try:
            calculate_day_master_strength(bad_graph)  # type: ignore[arg-type]
        except Phase9InputError as exc:
            passed += _assert(pattern.lower() in str(exc).lower(), failures, f"blocked error mismatch: {pattern}")
        else:
            failures.append(f"blocked input did not fail: {pattern}")

    assertions_total = (
        profile_assertions
        + element_assertions
        + seasonal_assertions
        + contribution_assertions
        + classification_assertions
        + deterministic_assertions
        + blocked_assertions
    )
    if assertions_total < int(assertion_manifest["minimum_expected_assertions_total"]):
        failures.append("assertion matrix below declared minimum")
    if any(not item.startswith("phase") for item in profile.source_ids):
        provenance_failures += 1
    if not sample.canonical_hash.startswith("sha256:"):
        hash_mismatches += 1
    if sample.schema_version != PHASE9_SCHEMA_VERSION:
        schema_failures += 1
    return Phase9BenchmarkResult(
        assertions_total=assertions_total,
        profile_assertions=profile_assertions,
        element_assertions=element_assertions,
        seasonal_assertions=seasonal_assertions,
        contribution_assertions=contribution_assertions,
        classification_assertions=classification_assertions,
        deterministic_assertions=deterministic_assertions,
        blocked_assertions=blocked_assertions,
        passed=passed,
        failed=len(failures),
        unresolved=0,
        schema_failures=schema_failures,
        provenance_failures=provenance_failures,
        hash_mismatches=hash_mismatches,
        threshold_gaps=gaps,
        threshold_overlaps=overlaps,
        failures=tuple(failures),
    )


__all__ = [
    "PHASE9_SCHEMA_VERSION",
    "PHASE9_METHOD_ID",
    "PHASE9_CALCULATION_VERSION",
    "PHASE9_DECISION_ID",
    "DEFAULT_PHASE9_PROFILE_ID",
    "calculate_day_master_strength",
    "strength_result_to_phase8_evidence",
    "build_strength_fixture_fact_graph",
    "relationship_to_day_master",
    "load_phase9_strength_profiles",
    "load_phase9_strength_assertions",
    "load_strength_profiles",
    "get_strength_profile",
    "validate_phase9_profiles",
    "validate_import_origin",
    "phase9_schema_summary",
    "benchmark_phase9",
]
