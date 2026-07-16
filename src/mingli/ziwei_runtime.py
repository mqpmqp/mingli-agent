from __future__ import annotations

from typing import Mapping, Sequence

from .phase18 import orchestrate_evidence_fusion
from .phase20 import render_yuan_eight_sections
from .ziwei_rules import (
    evaluate_ziwei_rules,
    extract_ziwei_rule_facts,
    load_ziwei_rule_content,
)


def run_ziwei_runtime(
    chart: Mapping[str, object],
    *,
    facts: Mapping[str, object],
    rules: Sequence[Mapping[str, object]] | None,
    reality: Mapping[str, object],
    reality_evidence: Sequence[Mapping[str, object]],
    start_year: int,
) -> dict[str, object]:
    calculation_status = chart.get("calculation_status")
    if calculation_status not in {"complete", "partial", "degraded"}:
        raise ValueError("Ziwei runtime accepts complete, partial, or degraded charts only")
    if isinstance(start_year, bool) or not isinstance(start_year, int):
        raise ValueError("start_year must be an integer")
    unsupported_raw = chart.get("unsupported_fields")
    if not isinstance(unsupported_raw, Sequence) or isinstance(unsupported_raw, (str, bytes)):
        raise ValueError("chart.unsupported_fields must be an array")
    unsupported = {str(name) for name in unsupported_raw}
    injected = sorted(unsupported.intersection(facts))
    if injected:
        raise ValueError(f"unsupported Ziwei facts cannot enter rule evaluation: {', '.join(injected)}")
    cards = load_ziwei_rule_content() if rules is None else tuple(rules)
    if cards:
        derived_facts = extract_ziwei_rule_facts(chart)
        protected = set(derived_facts).intersection(facts)
        mismatched = sorted(
            name for name in protected if facts[name] != derived_facts[name]
        )
        if mismatched:
            raise ValueError(
                "derived Ziwei facts cannot be overridden: " + ", ".join(mismatched)
            )
        merged_facts = {**derived_facts, **facts}
    else:
        merged_facts = dict(facts)
    matches = evaluate_ziwei_rules(merged_facts, cards)
    effective_matches = [
        item
        for item in matches
        if item.resolution != "suppressed_by_higher_priority"
    ]
    rule_evidence = [item.to_evidence() for item in effective_matches]
    fusion = orchestrate_evidence_fusion(reality, [*rule_evidence, *reality_evidence])

    domain_status = {"career": "unresolved", "wealth": "unresolved", "relationship": "unresolved"}
    domain_confidence = {"career": "low", "wealth": "low", "relationship": "low"}
    for claim in fusion.claims:
        if claim.scope not in domain_status:
            continue
        if claim.status == "unresolved_conflict":
            domain_status[claim.scope] = "unresolved"
        elif claim.hard_override_direction == "contradict":
            domain_status[claim.scope] = "challenging"
        elif claim.hard_override_direction == "support":
            domain_status[claim.scope] = "supportive"
        else:
            domain_status[claim.scope] = "mixed"

    correction = chart.get("time_correction")
    if not isinstance(correction, Mapping):
        raise ValueError("chart.time_correction must be structured")
    yuan = render_yuan_eight_sections(
        {
            "profile": {
                "calendar": correction.get("calendar_type", "unknown"),
                "birth_date": correction.get("input_birth_date", "unknown"),
                "birth_time": (
                    str(correction.get("input_datetime", "unknown")).split("T", 1)[-1]
                    if correction.get("birth_time_known")
                    else "unknown"
                ),
                "canonical_hash": chart.get("chart_fingerprint"),
            },
            "chenggu": {
                "display_weight": "not_calculated_by_ziwei_adapter",
                "verse_available": False,
            },
            "domains": domain_status,
            "domain_confidence": domain_confidence,
            "five_years": [
                {"year": year, "status": "unresolved", "confidence": "low"}
                for year in range(start_year, start_year + 5)
            ],
            "advice_codes": ["verify_reality", "build_plan", "seek_professional_help"],
        }
    )
    return {
        "deterministic": dict(chart),
        "inference": {
            "matches": [
                {
                    "rule_id": item.rule_id,
                    "domain": item.domain,
                    "direction": item.direction,
                    "confidence": item.confidence,
                    "plain_language": item.plain_language,
                    "resolution": item.resolution,
                }
                for item in matches
            ],
            "confidence_gate": "low_only",
            "rule_content_version": (
                str(cards[0]["content_version"]) if cards else None
            ),
            "effective_match_count": len(effective_matches),
            "warnings": [
                f"ziwei_chart_placement_is_{calculation_status}",
                "only_source_backed_rule_cards_are_evaluated",
                "reality_evidence_has_claim_scoped_hard_override",
            ],
        },
        "evidence_fusion": fusion.to_dict(),
        "yuan": yuan.to_dict(),
        "prediction_validity": "not_evaluated",
    }


__all__ = ["run_ziwei_runtime"]
