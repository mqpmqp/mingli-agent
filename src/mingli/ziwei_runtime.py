from __future__ import annotations

from typing import Mapping, Sequence

from .phase18 import orchestrate_evidence_fusion
from .phase20 import render_yuan_eight_sections
from .ziwei_rules import evaluate_ziwei_rules


def run_ziwei_runtime(
    chart: Mapping[str, object],
    *,
    facts: Mapping[str, object],
    rules: Sequence[Mapping[str, object]],
    reality: Mapping[str, object],
    reality_evidence: Sequence[Mapping[str, object]],
    start_year: int,
) -> dict[str, object]:
    if chart.get("calculation_status") not in {"partial", "degraded", "complete"}:
        raise ValueError("chart must be a structured Ziwei result")
    if isinstance(start_year, bool) or not isinstance(start_year, int):
        raise ValueError("start_year must be an integer")
    matches = evaluate_ziwei_rules(facts, rules)
    rule_evidence = [item.to_evidence() for item in matches]
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
            "warnings": [
                "ziwei_chart_placement_is_partial",
                "only_source_backed_rule_cards_are_evaluated",
                "reality_evidence_has_claim_scoped_hard_override",
            ],
        },
        "evidence_fusion": fusion.to_dict(),
        "yuan": yuan.to_dict(),
        "prediction_validity": "not_evaluated",
    }


__all__ = ["run_ziwei_runtime"]
