from __future__ import annotations

import json
from importlib.resources import files
from typing import Mapping

from .contracts.serialization import digest
from .derived.static_engine import BRANCHES, STEMS, map_ten_god
from .phase8_engine import validate_import_origin
from .phase9 import build_strength_fixture_fact_graph, calculate_day_master_strength
from .phase10_contracts import (
    PHASE10_CALCULATION_VERSION,
    PHASE10_DECISION_ID,
    PHASE10_METHOD_ID,
    PHASE10_SCHEMA_VERSION,
    SUPPORTED_PATTERN_TYPES,
    Phase10BenchmarkResult,
)
from .phase10_engine import evaluate_bazi_pattern, pattern_result_to_phase8_evidence
from .phase10_profiles import (
    DEFAULT_PHASE10_PROFILE_ID,
    get_pattern_profile,
    load_pattern_profiles,
    load_phase10_pattern_profiles,
    threshold_counts,
    validate_phase10_profiles,
)


def load_phase10_pattern_assertions() -> dict[str, object]:
    value = json.loads(files("mingli.derived.data").joinpath("phase10_pattern_assertions_v0.1.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Phase 10 assertion manifest must be an object")
    return value


def phase10_schema_summary() -> dict[str, object]:
    return {
        "decision_id": PHASE10_DECISION_ID,
        "schema_version": PHASE10_SCHEMA_VERSION,
        "method_id": PHASE10_METHOD_ID,
        "calculation_version": PHASE10_CALCULATION_VERSION,
        "profile_id": DEFAULT_PHASE10_PROFILE_ID,
        "prediction_validity": "not_evaluated",
        "pattern_statuses": ["supported", "conditionally_supported", "weakened", "contradicted", "rejected", "unresolved"],
        "supported_pattern_types": list(SUPPORTED_PATTERN_TYPES),
    }


def build_pattern_fixture_inputs(day_stem: str, month_branch: str) -> tuple[dict[str, object], dict[str, object]]:
    graph = build_strength_fixture_fact_graph(
        year=(STEMS[(STEMS.index(day_stem) + 6) % 10], BRANCHES[8]),
        month=(STEMS[(STEMS.index(day_stem) + 2) % 10], month_branch),
        day=(day_stem, BRANCHES[4]),
        hour=(STEMS[(STEMS.index(day_stem) + 4) % 10], BRANCHES[10]),
    )
    strength = calculate_day_master_strength(graph).to_dict()
    nodes = list(graph["nodes"])
    edges = list(graph["edges"])
    for position in ("year", "month", "day", "hour"):
        pillar = next(node for node in nodes if node.get("node_id") == f"pillar:{position}")
        stem = str(pillar["stem"])
        ten_god = map_ten_god(day_stem, stem)
        node = {"node_id": f"ten-god:{position}:{ten_god.code}", "node_type": "TenGod", "code": ten_god.code, "label": ten_god.label}
        node["canonical_digest"] = digest({"record_type": "GraphNode", "payload": node})
        nodes.append(node)
        edge = {"edge_id": f"relative_to_day_master:stem:{position}:{stem}->ten-god:{position}:{ten_god.code}", "edge_type": "relative_to_day_master", "source": f"stem:{position}:{stem}", "target": node["node_id"]}
        edge["canonical_digest"] = digest({"record_type": "GraphEdge", "payload": edge})
        edges.append(edge)
    graph = {**graph, "nodes": sorted(nodes, key=lambda item: item["node_id"]), "edges": sorted(edges, key=lambda item: item["edge_id"])}
    return _rehash_fixture_graph(graph), strength


def _rehash_strength(value: dict[str, object]) -> dict[str, object]:
    metadata = {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}
    body = {key: item for key, item in value.items() if key not in metadata}
    value["canonical_hash"] = digest({"record_type": "DayMasterStrengthResult", "payload": body})
    return value


def _rehash_fixture_graph(value: dict[str, object]) -> dict[str, object]:
    body = {key: item for key, item in value.items() if key not in {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}}
    value["canonical_hash"] = digest(body)
    return value


def benchmark_phase10() -> Phase10BenchmarkResult:
    failures: list[str] = list(validate_phase10_profiles())
    profile = get_pattern_profile()
    gaps, overlaps = threshold_counts(profile)
    passed = 0
    assertions_total = 0

    def check(condition: bool, message: str) -> None:
        nonlocal assertions_total, passed
        assertions_total += 1
        if condition:
            passed += 1
        else:
            failures.append(message)
    coverage: dict[str, int] = {pattern: 0 for pattern in SUPPORTED_PATTERN_TYPES}
    hashes: set[str] = set()
    for day_stem in STEMS:
        for month_branch in BRANCHES:
            graph, strength = build_pattern_fixture_inputs(day_stem, month_branch)
            result = evaluate_bazi_pattern(graph, strength)
            reordered = evaluate_bazi_pattern(
                json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True)),
                json.loads(json.dumps(strength, ensure_ascii=False, sort_keys=True)),
            )
            payload = result.to_dict()
            for candidate in result.candidates:
                coverage[candidate.pattern_type] = coverage.get(candidate.pattern_type, 0) + 1
            hashes.add(result.canonical_hash)
            checks = (
                payload["schema_version"] == PHASE10_SCHEMA_VERSION,
                payload["prediction_validity"] == "not_evaluated",
                result.canonical_hash.startswith("sha256:"),
                bool(result.candidates) and all(item.pattern_type in SUPPORTED_PATTERN_TYPES for item in result.candidates),
                bool(result.evidence_records) and all(item.canonical_digest.startswith("sha256:") for item in result.evidence_records),
                all(item.establishment_conditions and isinstance(item.breaking_conditions, tuple) and isinstance(item.rescue_conditions, tuple) for item in result.candidates),
                result.canonical_hash == reordered.canonical_hash,
                result.fact_graph_hash == graph["canonical_hash"],
                result.strength_result_hash == strength["canonical_hash"],
                all(item.source_ids for item in result.evidence_records),
            )
            for index, condition in enumerate(checks):
                check(condition, f"{day_stem}{month_branch}: check {index + 1} failed")

    graph, strength = build_pattern_fixture_inputs(STEMS[0], BRANCHES[2])
    very_strong = evaluate_bazi_pattern(graph, _rehash_strength({**strength, "classification": "very_strong"}))
    for candidate in very_strong.candidates:
        coverage[candidate.pattern_type] = coverage.get(candidate.pattern_type, 0) + 1
    check(any(item.pattern_type == "cong_qiang_candidate" for item in very_strong.candidates), "cong_qiang candidate boundary missing")
    check(all(item.status != "supported" for item in very_strong.candidates if item.pattern_type.endswith("_candidate")), "special candidate exceeded status ceiling")

    relation = {
        "node_id": "relation:benchmark-stem-five-combine", "node_type": "Relation",
        "relation_type": "stem_five_combine", "participants": ["stem:year:庚", "stem:day:甲"],
    }
    relation["canonical_digest"] = digest({"record_type": "GraphNode", "payload": relation})
    graph_with_combine = {**graph, "nodes": sorted([*graph["nodes"], relation], key=lambda item: item["node_id"])}
    hua_result = evaluate_bazi_pattern(_rehash_fixture_graph(graph_with_combine), strength)
    for candidate in hua_result.candidates:
        coverage[candidate.pattern_type] = coverage.get(candidate.pattern_type, 0) + 1
    hua = [item for item in hua_result.candidates if item.pattern_type == "hua_qi_candidate"]
    check(bool(hua), "hua_qi candidate boundary missing")
    check(bool(hua) and hua[0].status == "unresolved", "hua_qi must remain unresolved")
    check(bool(hua) and bool(hua[0].unresolved_conditions), "hua_qi unresolved conditions missing")

    very_weak = evaluate_bazi_pattern(graph, _rehash_strength({**strength, "classification": "very_weak"}))
    check(any(item.resolution_status == "unresolved" for item in very_weak.conflicts), "equal-priority special conflict was not retained")
    check(all(item.retained_breaking_evidence_ids is not None for item in very_weak.conflicts), "conflict did not retain breaking evidence field")
    for pattern_type in SUPPORTED_PATTERN_TYPES:
        check(coverage.get(pattern_type, 0) > 0, f"pattern coverage missing: {pattern_type}")
    manifest = load_phase10_pattern_assertions()
    if assertions_total < int(manifest["minimum_expected_assertions_total"]):
        failures.append("assertion matrix below declared minimum")
    schema_failures = 0 if PHASE10_SCHEMA_VERSION.startswith("bazi-pattern-evaluation-result@") else 1
    provenance_failures = 0 if len(set(profile.independence_groups)) >= 2 and profile.source_ids else 1
    hash_mismatches = 0 if len(hashes) > 20 and profile.canonical_hash == digest({"record_type": "PatternProfile", "payload": {key: value for key, value in profile.to_dict().items() if key != "canonical_hash"}}) else 1
    failed = len(failures)
    return Phase10BenchmarkResult(
        assertions_total=assertions_total, passed=passed, failed=failed, unresolved=0,
        schema_failures=schema_failures, provenance_failures=provenance_failures,
        hash_mismatches=hash_mismatches, threshold_gaps=gaps, threshold_overlaps=overlaps,
        conflict_order_failures=0, coverage=dict(sorted(coverage.items())), failures=tuple(failures),
    )


__all__ = [
    "PHASE10_SCHEMA_VERSION", "PHASE10_METHOD_ID", "PHASE10_CALCULATION_VERSION", "PHASE10_DECISION_ID",
    "DEFAULT_PHASE10_PROFILE_ID", "evaluate_bazi_pattern", "pattern_result_to_phase8_evidence",
    "build_pattern_fixture_inputs",
    "load_phase10_pattern_profiles", "load_phase10_pattern_assertions", "load_pattern_profiles",
    "get_pattern_profile", "validate_phase10_profiles", "validate_import_origin", "phase10_schema_summary",
    "benchmark_phase10",
]
