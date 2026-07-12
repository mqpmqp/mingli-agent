from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from .contracts.serialization import canonical_json
from .phase8_contracts import (
    EXECUTABLE_RULE_STATUSES,
    ConditionResult,
    ConditionSpec,
    EvaluationRule,
    EvidenceRecord,
    RuleMatch,
    _lookup,
    _record_digest,
    _source_ref,
)


def _collection_records(graph: Mapping[str, object], collection: str) -> tuple[Mapping[str, object], ...]:
    if collection == "root":
        return (graph,)
    raw = graph.get(collection, [])
    if not isinstance(raw, list):
        raise ValueError(f"fact graph collection {collection} must be an array")
    if any(not isinstance(item, Mapping) for item in raw):
        raise ValueError(f"fact graph collection {collection} must contain objects")
    return tuple(raw)  # type: ignore[return-value]


def _record_matches(record: Mapping[str, object], where: Mapping[str, object]) -> bool:
    for path, expected in where.items():
        if not isinstance(path, str) or not path:
            raise ValueError("condition.where keys must be non-empty strings")
        exists, actual = _lookup(record, path)
        if not exists or canonical_json(actual) != canonical_json(expected):
            return False
    return True


def _evaluate_fact_condition(condition: ConditionSpec, graph: Mapping[str, object]) -> ConditionResult:
    assert condition.collection is not None
    records = _collection_records(graph, condition.collection)
    matched_records = [(index, record) for index, record in enumerate(records) if _record_matches(record, condition.where)]
    matched_count = len(matched_records)
    if condition.quantifier == "any":
        matched = matched_count > 0
    elif condition.quantifier == "none":
        matched = matched_count == 0
    elif condition.quantifier == "all":
        matched = bool(records) and matched_count == len(records)
    else:
        matched = matched_count >= condition.threshold
    refs = tuple(_source_ref(record, condition.collection, index) for index, record in matched_records)
    detail = f"{condition.collection}:{condition.quantifier}:{matched_count}/{len(records)}"
    payload = {
        "condition_id": condition.condition_id,
        "matched": matched,
        "matched_count": matched_count,
        "source_refs": list(refs),
        "detail": detail,
    }
    return ConditionResult(condition.condition_id, matched, matched_count, refs, detail, _record_digest("ConditionResult", payload))


def _evaluate_reality_condition(condition: ConditionSpec, reality: Mapping[str, object]) -> ConditionResult:
    assert condition.path is not None and condition.operator is not None
    exists, actual = _lookup(reality, condition.path)
    operator = condition.operator
    if operator == "exists":
        matched = exists
    elif operator == "equals":
        matched = exists and canonical_json(actual) == canonical_json(condition.value)
    elif operator == "not_equals":
        matched = exists and canonical_json(actual) != canonical_json(condition.value)
    elif operator == "in":
        expected = condition.value
        matched = exists and isinstance(expected, (list, tuple)) and actual in expected
    elif operator == "contains":
        matched = exists and (
            (isinstance(actual, str) and isinstance(condition.value, str) and condition.value in actual)
            or (isinstance(actual, (list, tuple, set)) and condition.value in actual)
        )
    elif operator in {"gte", "lte"}:
        expected = condition.value
        comparable = (
            exists
            and not isinstance(actual, bool)
            and not isinstance(expected, bool)
            and isinstance(actual, (int, float))
            and isinstance(expected, (int, float))
        )
        matched = comparable and (actual >= expected if operator == "gte" else actual <= expected)  # type: ignore[operator]
    else:
        raise ValueError(f"unsupported reality operator: {operator}")
    refs = (f"reality:{condition.path}",) if exists else ()
    detail = f"reality:{condition.path}:{operator}:{'matched' if matched else 'not_matched'}"
    payload = {
        "condition_id": condition.condition_id,
        "matched": matched,
        "matched_count": 1 if matched else 0,
        "source_refs": list(refs),
        "detail": detail,
    }
    return ConditionResult(condition.condition_id, matched, 1 if matched else 0, refs, detail, _record_digest("ConditionResult", payload))


def evaluate_condition(condition: ConditionSpec, graph: Mapping[str, object], reality: Mapping[str, object]) -> ConditionResult:
    return _evaluate_fact_condition(condition, graph) if condition.source == "fact_graph" else _evaluate_reality_condition(condition, reality)


def parse_rule_set(value: object) -> tuple[EvaluationRule, ...]:
    raw_rules: object
    if isinstance(value, Mapping):
        unknown = set(value) - {"rules", "rule_set_id", "version"}
        if unknown:
            raise ValueError(f"rule set contains unknown fields: {', '.join(sorted(unknown))}")
        raw_rules = value.get("rules")
    else:
        raw_rules = value
    if not isinstance(raw_rules, list):
        raise ValueError("rule set must be an array or an object containing rules")
    if not raw_rules:
        raise ValueError("rule set must not be empty")
    parsed: list[EvaluationRule] = []
    for item in raw_rules:
        if not isinstance(item, Mapping):
            raise ValueError("rule must be an object")
        parsed.append(EvaluationRule.from_mapping(item))
    rules = tuple(parsed)
    issues = validate_phase8_rules(rules)
    if issues:
        raise ValueError("; ".join(issues))
    return tuple(sorted(rules, key=lambda item: (-item.priority, item.rule_id)))


def load_phase8_rules(path: Path | str) -> tuple[EvaluationRule, ...]:
    target = Path(path)
    if target.is_dir():
        values: list[object] = []
        for file in sorted((*target.rglob("*.json"), *target.rglob("*.jsonl"))):
            loaded = load_phase8_rules(file)
            values.extend(rule.to_dict() for rule in loaded)
        return parse_rule_set(values)
    text = target.read_text(encoding="utf-8")
    if target.suffix == ".jsonl":
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
        return parse_rule_set(records)
    return parse_rule_set(json.loads(text))


def validate_phase8_rules(rules: Iterable[EvaluationRule | Mapping[str, object]]) -> tuple[str, ...]:
    issues: list[str] = []
    parsed: list[EvaluationRule] = []
    for index, item in enumerate(rules):
        try:
            parsed.append(item if isinstance(item, EvaluationRule) else EvaluationRule.from_mapping(item))
        except (TypeError, ValueError) as exc:
            issues.append(f"rule[{index}]: {exc}")
    ids = [item.rule_id for item in parsed]
    for rule_id in sorted({item for item in ids if ids.count(item) > 1}):
        issues.append(f"duplicate rule_id: {rule_id}")
    claim_texts: dict[str, set[str]] = {}
    for item in parsed:
        claim_texts.setdefault(item.claim_id, set()).add(item.claim_text)
        if item.status in EXECUTABLE_RULE_STATUSES and not item.source_ids:
            issues.append(f"{item.rule_id}: executable rule requires source_ids")
    for claim_id, texts in sorted(claim_texts.items()):
        if len(texts) > 1:
            issues.append(f"{claim_id}: claim_text must be consistent across rules")
    return tuple(issues)


def _rule_evidence(rule: EvaluationRule) -> EvidenceRecord:
    evidence_id = f"rule-evidence:{rule.rule_id}:{rule.claim_id}:{rule.direction}"
    payload = {
        "evidence_id": evidence_id,
        "claim_id": rule.claim_id,
        "source_type": "rule",
        "source_id": rule.rule_id,
        "detail": rule.evidence_detail,
        "direction": rule.direction,
        "weight": rule.weight,
        "priority": rule.priority,
        "verified": rule.status == "verified",
    }
    return EvidenceRecord(
        evidence_id=evidence_id,
        claim_id=rule.claim_id,
        source_type="rule",
        source_id=rule.rule_id,
        detail=rule.evidence_detail,
        direction=rule.direction,
        weight=rule.weight,
        priority=rule.priority,
        verified=rule.status == "verified",
        canonical_digest=_record_digest("EvidenceRecord", payload),
    )


def _match_rule(rule: EvaluationRule, graph: Mapping[str, object], reality: Mapping[str, object]) -> tuple[RuleMatch, EvidenceRecord | None]:
    if rule.status not in EXECUTABLE_RULE_STATUSES:
        payload = {
            "rule_id": rule.rule_id,
            "claim_id": rule.claim_id,
            "priority": rule.priority,
            "status": "skipped",
            "required_results": [],
            "blocking_results": [],
            "reason": f"status_not_executable:{rule.status}",
            "emitted_evidence_ids": [],
        }
        return RuleMatch(
            rule.rule_id,
            rule.claim_id,
            rule.priority,
            "skipped",
            (),
            (),
            str(payload["reason"]),
            (),
            _record_digest("RuleMatch", payload),
        ), None
    required = tuple(evaluate_condition(condition, graph, reality) for condition in rule.required_conditions)
    blocking = tuple(evaluate_condition(condition, graph, reality) for condition in rule.blocking_conditions)
    if any(item.matched for item in blocking):
        status = "blocked"
        reason = "blocking_condition_matched"
        evidence = None
    elif all(item.matched for item in required):
        status = "matched"
        reason = "all_required_conditions_matched"
        evidence = _rule_evidence(rule)
    else:
        status = "not_matched"
        reason = "required_condition_not_matched"
        evidence = None
    emitted = (evidence.evidence_id,) if evidence else ()
    payload = {
        "rule_id": rule.rule_id,
        "claim_id": rule.claim_id,
        "priority": rule.priority,
        "status": status,
        "required_results": [item.to_dict() for item in required],
        "blocking_results": [item.to_dict() for item in blocking],
        "reason": reason,
        "emitted_evidence_ids": list(emitted),
    }
    return RuleMatch(
        rule.rule_id,
        rule.claim_id,
        rule.priority,
        status,
        tuple(item.to_dict() for item in required),
        tuple(item.to_dict() for item in blocking),
        reason,
        emitted,
        _record_digest("RuleMatch", payload),
    ), evidence
