from __future__ import annotations

from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence

from .contracts.serialization import digest
from .phase8_contracts import (
    PHASE8_DECISION_ID,
    ClaimResolution,
    ConfidenceInputRecord,
    ConflictRecord,
    EvaluationRule,
    EvidenceRecord,
    ImportOriginResult,
    RuleEvaluationResult,
    RuleMatch,
    _record_digest,
)
from .phase8_rules import validate_phase8_rules, evaluate_condition, load_phase8_rules, parse_rule_set, _match_rule
from .phase8_resolution import _reality_override_records, _resolve_claim


def evaluate_rule_set(
    fact_graph: Mapping[str, object],
    rules: Iterable[EvaluationRule | Mapping[str, object]],
    *,
    intent: str = "unspecified",
    reality: Mapping[str, object] | None = None,
    chart_signals: Sequence[str] = (),
    missing_information: bool = False,
    image_unconfirmed: bool = False,
    single_symbol: bool = False,
    high_stakes: str | None = None,
) -> RuleEvaluationResult:
    if not isinstance(fact_graph, Mapping):
        raise TypeError("fact_graph must be an object")
    required_collections = ("nodes", "edges", "relations", "growth_stages", "profiles")
    missing_collections = [name for name in required_collections if name not in fact_graph]
    if missing_collections:
        raise ValueError(f"fact_graph missing collections: {', '.join(missing_collections)}")
    if fact_graph.get("prediction_validity") != "not_evaluated":
        raise ValueError("fact_graph prediction_validity must remain not_evaluated")
    if reality is None:
        reality = {}
    if not isinstance(reality, Mapping):
        raise TypeError("reality must be an object")
    parsed_rules = tuple(item if isinstance(item, EvaluationRule) else EvaluationRule.from_mapping(item) for item in rules)
    issues = validate_phase8_rules(parsed_rules)
    if issues:
        raise ValueError("; ".join(issues))
    parsed_rules = tuple(sorted(parsed_rules, key=lambda item: (-item.priority, item.rule_id)))
    matches: list[RuleMatch] = []
    evidence: list[EvidenceRecord] = []
    for rule in parsed_rules:
        match, emitted = _match_rule(rule, fact_graph, reality)
        matches.append(match)
        if emitted is not None:
            evidence.append(emitted)
    active_claim_ids = frozenset(item.claim_id for item in evidence)
    override_records, override_evidence = _reality_override_records(intent, reality, chart_signals, parsed_rules, active_claim_ids)
    evidence.extend(override_evidence)
    evidence.sort(key=lambda item: (item.claim_id, -item.priority, item.evidence_id))
    claims: list[ClaimResolution] = []
    conflicts: list[ConflictRecord] = []
    confidence_inputs: list[ConfidenceInputRecord] = []
    claim_texts = {rule.claim_id: rule.claim_text for rule in parsed_rules}
    for claim_id in sorted({item.claim_id for item in evidence}):
        claim_records = tuple(item for item in evidence if item.claim_id == claim_id)
        resolution, conflict, confidence = _resolve_claim(
            claim_id,
            claim_texts[claim_id],
            claim_records,
            missing_information=missing_information,
            image_unconfirmed=image_unconfirmed,
            single_symbol=single_symbol,
            high_stakes=high_stakes,
        )
        claims.append(resolution)
        confidence_inputs.append(confidence)
        if conflict is not None:
            conflicts.append(conflict)
    unresolved = tuple(
        {
            "claim_id": claim.claim_id,
            "reason": "equal-priority opposing evidence without verified reality override",
        }
        for claim in claims
        if claim.resolution_status == "unresolved_conflict"
    )
    fact_graph_hash = str(fact_graph.get("canonical_hash") or digest(fact_graph))
    rule_set_hash = digest([rule.to_dict() for rule in parsed_rules])
    provenance_index = {
        "fact_graph_hash": fact_graph_hash,
        "rule_set_hash": rule_set_hash,
        "rule_source_ids": sorted({source_id for rule in parsed_rules for source_id in rule.source_ids}),
        "reality_override_codes": [record.code for record in override_records],
        "confidence_inputs": [record.to_dict() for record in confidence_inputs],
        "decision_id": PHASE8_DECISION_ID,
    }
    warnings: list[str] = []
    if not reality:
        warnings.append("reality_context_not_supplied")
    payload = {
        "fact_graph_hash": fact_graph_hash,
        "rule_set_hash": rule_set_hash,
        "intent": intent,
        "rule_matches": [item.to_dict() for item in sorted(matches, key=lambda item: (-item.priority, item.rule_id))],
        "evidence_records": [item.to_dict() for item in evidence],
        "reality_overrides": [item.to_dict() for item in override_records],
        "conflicts": [item.to_dict() for item in sorted(conflicts, key=lambda item: item.conflict_id)],
        "claim_resolutions": [item.to_dict() for item in sorted(claims, key=lambda item: item.claim_id)],
        "provenance_index": provenance_index,
        "warnings": warnings,
        "unresolved": list(unresolved),
    }
    canonical_hash = _record_digest("RuleEvaluationResult", payload)
    return RuleEvaluationResult(
        fact_graph_hash=fact_graph_hash,
        rule_set_hash=rule_set_hash,
        intent=intent,
        rule_matches=tuple(payload["rule_matches"]),  # type: ignore[arg-type]
        evidence_records=tuple(payload["evidence_records"]),  # type: ignore[arg-type]
        reality_overrides=tuple(payload["reality_overrides"]),  # type: ignore[arg-type]
        conflicts=tuple(payload["conflicts"]),  # type: ignore[arg-type]
        claim_resolutions=tuple(payload["claim_resolutions"]),  # type: ignore[arg-type]
        provenance_index=provenance_index,
        warnings=tuple(warnings),
        unresolved=unresolved,
        canonical_hash=canonical_hash,
    )


def validate_import_origin(expected_root: Path | str | None = None) -> ImportOriginResult:
    import mingli

    if not getattr(mingli, "__file__", None):
        return ImportOriginResult("", str(expected_root) if expected_root is not None else None, "invalid", False, "mingli.__file__ is unavailable")
    module_path = Path(str(mingli.__file__)).resolve()
    if expected_root is not None:
        root = Path(expected_root).resolve()
        candidates = (root, root / "src", root / "src" / "mingli")
        valid = any(module_path == candidate or module_path.is_relative_to(candidate) for candidate in candidates)
        return ImportOriginResult(
            str(module_path),
            str(root),
            "checkout" if valid else "invalid",
            valid,
            "import belongs to expected checkout" if valid else "import does not belong to expected checkout",
        )
    prefix = Path(sys.prefix).resolve()
    isolated = sys.prefix != sys.base_prefix and module_path.is_relative_to(prefix)
    return ImportOriginResult(
        str(module_path),
        None,
        "isolated_venv" if isolated else "invalid",
        isolated,
        "import belongs to isolated venv" if isolated else "expected_root is required outside an isolated venv",
    )
