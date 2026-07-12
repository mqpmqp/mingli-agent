from __future__ import annotations

import json

from .phase8_contracts import (
    EXECUTABLE_RULE_STATUSES,
    FACT_COLLECTIONS,
    FACT_QUANTIFIERS,
    PHASE8_CALCULATION_VERSION,
    PHASE8_DECISION_ID,
    PHASE8_METHOD_ID,
    PHASE8_SCHEMA_VERSION,
    REALITY_OPERATORS,
    RULE_MATCH_STATUSES,
    ConditionSpec,
    EvaluationRule,
    Phase8BenchmarkResult,
)
from .phase8_engine import (
    evaluate_condition,
    evaluate_rule_set,
    load_phase8_rules,
    parse_rule_set,
    validate_import_origin,
    validate_phase8_rules,
)


def phase8_schema_summary() -> dict[str, object]:
    return {
        "schemas": {
            "RuleEvaluationResult": PHASE8_SCHEMA_VERSION,
            "EvaluationRule": "phase8-evaluation-rule@0.1",
            "ConditionSpec": "phase8-condition-spec@0.1",
            "EvidenceRecord": "phase8-evidence-record@0.1",
            "ConflictRecord": "phase8-conflict-record@0.1",
            "ConfidenceInputRecord": "phase8-confidence-input-record@0.1",
        },
        "decision_id": PHASE8_DECISION_ID,
        "executable_rule_statuses": sorted(EXECUTABLE_RULE_STATUSES),
        "fact_collections": sorted(FACT_COLLECTIONS),
        "fact_quantifiers": sorted(FACT_QUANTIFIERS),
        "reality_operators": sorted(REALITY_OPERATORS),
        "prediction_validity": "not_evaluated",
    }


def _fixture_graph() -> dict[str, object]:
    return {
        "canonical_hash": "sha256:phase8-fixture-graph",
        "nodes": [
            {"node_id": "pillar:year", "node_type": "Pillar", "position": "year"},
            {"node_id": "relation:clash", "node_type": "Relation", "relation_type": "branch_six_clash"},
        ],
        "edges": [],
        "relations": [{"relation_id": "clash", "relation_type": "branch_six_clash"}],
        "growth_stages": [],
        "profiles": [],
        "timeline": {"interval_gaps": 0, "interval_overlaps": 0},
        "prediction_validity": "not_evaluated",
    }


def _fixture_rules() -> tuple[dict[str, object], ...]:
    relation_condition = {
        "condition_id": "has_clash",
        "source": "fact_graph",
        "collection": "relations",
        "where": {"relation_type": "branch_six_clash"},
        "quantifier": "any",
    }
    pillar_condition = {
        "condition_id": "has_pillar",
        "source": "fact_graph",
        "collection": "nodes",
        "where": {"node_type": "Pillar"},
        "quantifier": "any",
    }
    return (
        {
            "rule_id": "structural-support",
            "version": "0.1",
            "domain": "structural",
            "claim_id": "structural-signal",
            "claim_text": "A structural signal is present.",
            "direction": "support",
            "weight": 6,
            "priority": 80,
            "status": "verified",
            "required_conditions": [relation_condition],
            "blocking_conditions": [],
            "evidence_detail": "A relation fact matched the structural selector.",
            "plain_language": "The graph contains the requested structural relation.",
            "reality_override_codes": [],
            "source_ids": ["phase8-fixture-source-a"],
        },
        {
            "rule_id": "structural-counter",
            "version": "0.1",
            "domain": "structural",
            "claim_id": "structural-signal",
            "claim_text": "A structural signal is present.",
            "direction": "contradict",
            "weight": 4,
            "priority": 40,
            "status": "reviewed",
            "required_conditions": [pillar_condition],
            "blocking_conditions": [],
            "evidence_detail": "A lower-priority counter-rule matched.",
            "plain_language": "The counter-rule is retained as conflicting evidence.",
            "reality_override_codes": [],
            "source_ids": ["phase8-fixture-source-b"],
        },
        {
            "rule_id": "career-promotion",
            "version": "0.1",
            "domain": "career",
            "claim_id": "career-promotion",
            "claim_text": "The current career condition should be described as promotion.",
            "direction": "support",
            "weight": 8,
            "priority": 70,
            "status": "verified",
            "required_conditions": [pillar_condition],
            "blocking_conditions": [],
            "evidence_detail": "A synthetic career rule matched for contract testing.",
            "plain_language": "This is a contract fixture, not a prediction.",
            "reality_override_codes": ["unemployed"],
            "source_ids": ["phase8-fixture-source-c"],
        },
        {
            "rule_id": "blocked-rule",
            "version": "0.1",
            "domain": "career",
            "claim_id": "blocked-claim",
            "claim_text": "A blocked claim must not emit evidence.",
            "direction": "support",
            "weight": 5,
            "priority": 60,
            "status": "reviewed",
            "required_conditions": [pillar_condition],
            "blocking_conditions": [
                {
                    "condition_id": "unemployed_blocks",
                    "source": "reality",
                    "path": "career_status",
                    "operator": "equals",
                    "value": "unemployed",
                }
            ],
            "evidence_detail": "Blocked evidence must not be emitted.",
            "plain_language": "Reality blocks this rule.",
            "reality_override_codes": [],
            "source_ids": ["phase8-fixture-source-d"],
        },
        {
            "rule_id": "draft-rule",
            "version": "0.1",
            "domain": "structural",
            "claim_id": "draft-claim",
            "claim_text": "Draft claims are not executable.",
            "direction": "support",
            "weight": 5,
            "priority": 100,
            "status": "draft",
            "required_conditions": [pillar_condition],
            "blocking_conditions": [],
            "evidence_detail": "Draft evidence must not be emitted.",
            "plain_language": "Draft rules are skipped.",
            "reality_override_codes": [],
            "source_ids": ["phase8-fixture-source-e"],
        },
        {
            "rule_id": "not-matched-rule",
            "version": "0.1",
            "domain": "structural",
            "claim_id": "not-matched-claim",
            "claim_text": "Missing facts must not emit evidence.",
            "direction": "support",
            "weight": 5,
            "priority": 50,
            "status": "reviewed",
            "required_conditions": [
                {
                    "condition_id": "missing_node",
                    "source": "fact_graph",
                    "collection": "nodes",
                    "where": {"node_type": "Missing"},
                    "quantifier": "any",
                }
            ],
            "blocking_conditions": [],
            "evidence_detail": "Missing evidence must not be emitted.",
            "plain_language": "The required fact is absent.",
            "reality_override_codes": [],
            "source_ids": ["phase8-fixture-source-f"],
        },
    )


def _assert(condition: bool, failures: list[str], message: str) -> int:
    if condition:
        return 1
    failures.append(message)
    return 0


def benchmark_phase8() -> Phase8BenchmarkResult:
    failures: list[str] = []
    rule_assertions = evidence_assertions = conflict_assertions = confidence_assertions = provenance_assertions = deterministic_assertions = 0
    passed = 0
    graph = _fixture_graph()
    rules = parse_rule_set(list(_fixture_rules()))
    result = evaluate_rule_set(graph, rules, intent="career", reality={"career_status": "unemployed"})
    payload = result.to_dict()

    match_status = {item["rule_id"]: item["status"] for item in payload["rule_matches"]}  # type: ignore[index]
    checks = {
        "structural-support": "matched",
        "structural-counter": "matched",
        "career-promotion": "matched",
        "blocked-rule": "blocked",
        "draft-rule": "skipped",
        "not-matched-rule": "not_matched",
    }
    for rule_id, expected in checks.items():
        rule_assertions += 1
        passed += _assert(match_status.get(rule_id) == expected, failures, f"rule status mismatch: {rule_id}")
    rule_assertions += 2
    passed += _assert(len(payload["rule_matches"]) == 6, failures, "rule match count mismatch")  # type: ignore[arg-type]
    passed += _assert(all(item["status"] in RULE_MATCH_STATUSES for item in payload["rule_matches"]), failures, "unknown rule match status")  # type: ignore[index]

    evidence_records = payload["evidence_records"]  # type: ignore[index]
    evidence_assertions += 5
    passed += _assert(len(evidence_records) == 4, failures, "evidence count mismatch")
    passed += _assert(not any(item["source_id"] == "blocked-rule" for item in evidence_records), failures, "blocked rule emitted evidence")
    passed += _assert(not any(item["source_id"] == "draft-rule" for item in evidence_records), failures, "draft rule emitted evidence")
    passed += _assert(any(item["source_type"] == "reality" and item["verified"] for item in evidence_records), failures, "verified reality evidence missing")
    passed += _assert(all(str(item["canonical_digest"]).startswith("sha256:") for item in evidence_records), failures, "evidence digest missing")

    resolutions = {item["claim_id"]: item for item in payload["claim_resolutions"]}  # type: ignore[index]
    conflict_assertions += 7
    passed += _assert(resolutions["structural-signal"]["resolution_status"] == "resolved_by_priority", failures, "priority resolution missing")
    passed += _assert(resolutions["structural-signal"]["final_direction"] == "support", failures, "priority winner mismatch")
    passed += _assert(resolutions["career-promotion"]["resolution_status"] == "resolved_by_reality_override", failures, "reality resolution missing")
    passed += _assert(resolutions["career-promotion"]["final_direction"] == "contradict", failures, "reality winner mismatch")
    passed += _assert(resolutions["career-promotion"]["support_score"] == 0, failures, "reality hard override did not clear support score")
    passed += _assert(resolutions["career-promotion"]["hard_override_direction"] == "contradict", failures, "hard override direction missing")
    passed += _assert(len(payload["conflicts"]) == 2, failures, "conflict count mismatch")  # type: ignore[arg-type]

    confidence_assertions += 5
    passed += _assert(resolutions["career-promotion"]["confidence"]["level"] == "high", failures, "reality confidence must be high")
    passed += _assert(resolutions["structural-signal"]["confidence"]["level"] == "medium", failures, "priority conflict confidence must be medium")
    low_rule = next(rule for rule in rules if rule.rule_id == "structural-support")
    low_result = evaluate_rule_set(graph, (low_rule,), missing_information=True)
    low_resolution = low_result.to_dict()["claim_resolutions"][0]  # type: ignore[index]
    passed += _assert(low_resolution["confidence"]["level"] == "low", failures, "missing information must lower confidence")
    tie_rules = [dict(_fixture_rules()[0]), dict(_fixture_rules()[1])]
    tie_rules[1]["priority"] = 80
    tie = evaluate_rule_set(graph, parse_rule_set(tie_rules))
    tie_resolution = tie.to_dict()["claim_resolutions"][0]  # type: ignore[index]
    passed += _assert(tie_resolution["resolution_status"] == "unresolved_conflict", failures, "equal priority conflict must remain unresolved")
    passed += _assert(tie_resolution["confidence"]["level"] == "low", failures, "unresolved conflict must be low confidence")

    provenance = payload["provenance_index"]  # type: ignore[index]
    provenance_assertions += 5
    passed += _assert(provenance["fact_graph_hash"] == graph["canonical_hash"], failures, "fact graph provenance mismatch")
    passed += _assert(str(provenance["rule_set_hash"]).startswith("sha256:"), failures, "rule set hash missing")
    passed += _assert(provenance["decision_id"] == PHASE8_DECISION_ID, failures, "decision id mismatch")
    passed += _assert("unemployed" in provenance["reality_override_codes"], failures, "override provenance missing")
    passed += _assert(payload["prediction_validity"] == "not_evaluated", failures, "prediction boundary changed")

    deterministic_assertions += 5
    reordered_graph = json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True))
    reordered_rules = tuple(reversed(rules))
    repeated = evaluate_rule_set(reordered_graph, reordered_rules, intent="career", reality={"career_status": "unemployed"})
    passed += _assert(result.canonical_hash == repeated.canonical_hash, failures, "canonical hash changed after input reorder")
    passed += _assert(result.rule_set_hash == repeated.rule_set_hash, failures, "rule set hash changed after input reorder")
    passed += _assert(str(result.canonical_hash).startswith("sha256:"), failures, "canonical hash missing")
    passed += _assert(result.schema_version == PHASE8_SCHEMA_VERSION, failures, "schema version mismatch")
    passed += _assert(result.method_id == PHASE8_METHOD_ID, failures, "method id mismatch")

    assertions_total = rule_assertions + evidence_assertions + conflict_assertions + confidence_assertions + provenance_assertions + deterministic_assertions
    return Phase8BenchmarkResult(
        assertions_total=assertions_total,
        rule_assertions=rule_assertions,
        evidence_assertions=evidence_assertions,
        conflict_assertions=conflict_assertions,
        confidence_assertions=confidence_assertions,
        provenance_assertions=provenance_assertions,
        deterministic_assertions=deterministic_assertions,
        passed=passed,
        failed=len(failures),
        unresolved=0,
        failures=tuple(failures),
    )


__all__ = [
    "PHASE8_SCHEMA_VERSION", "PHASE8_METHOD_ID", "PHASE8_CALCULATION_VERSION", "PHASE8_DECISION_ID",
    "ConditionSpec", "EvaluationRule", "parse_rule_set", "load_phase8_rules", "validate_phase8_rules",
    "evaluate_condition", "evaluate_rule_set", "validate_import_origin", "phase8_schema_summary", "benchmark_phase8",
]
