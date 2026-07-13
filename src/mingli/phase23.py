from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal, Mapping, Sequence

from .bazi import DeterministicBaziEngine
from .contracts.serialization import canonical_json, digest
from .phase7 import build_bazi_fact_graph
from .phase9_engine import calculate_day_master_strength
from .phase10_engine import evaluate_bazi_pattern
from .phase11_engine import evaluate_bazi_regulation
from .phase12 import evaluate_bazi_xiji_roles
from .phase13 import evaluate_luck_cycle_role_interactions
from .phase14 import evaluate_bazi_temporal_trends
from .phase15 import evaluate_bazi_tengod_domains
from .phase16 import evaluate_base_domain_contracts
from .phase17 import evaluate_special_scenario
from .phase18 import normalize_reality_context, orchestrate_evidence_fusion
from .phase19 import calculate_chenggu
from .phase20 import render_yuan_eight_sections
from .phase21 import generate_five_year_outlook, renderer_years

PHASE23_SCHEMA_VERSION = "mingli-agent-runtime-result@0.2"
PHASE23_METHOD_ID = "deterministic-mingli-agent-runtime@0.2.0"
PHASE23_CALCULATION_VERSION = "0.2.0"
PHASE23_DECISION_ID = "PHASE_23_END_TO_END_RUNTIME_R2_APPROVED"
RUNTIME_STAGES = (
    "intake_validation",
    "scenario_router",
    "deterministic_chart",
    "fact_graph",
    "strength",
    "pattern",
    "regulation",
    "xiji",
    "luck_interactions",
    "temporal_trends",
    "domain_rules",
    "domain_contracts",
    "reality_context",
    "evidence_fusion",
    "confidence_gate",
    "chenggu",
    "five_year",
    "yuan_renderer",
    "final_answer",
)
DOMAINS = ("career", "wealth", "relationship")
LABEL_TO_STATUS = {
    "support_tendency": "supportive",
    "conflict_tendency": "challenging",
    "mixed_tendency": "mixed",
    "neutral_tendency": "mixed",
    "unresolved": "unresolved",
}


class Phase23InputError(ValueError):
    """Raised when the end-to-end runtime cannot preserve its contracts."""


@dataclass(frozen=True)
class RuntimeStage:
    stage: str
    status: str
    artifact_hash: str


@dataclass(frozen=True)
class MingLiRuntimeResult:
    run_id: str
    stages: tuple[RuntimeStage, ...]
    chart: Mapping[str, object]
    artifacts: Mapping[str, Mapping[str, object]]
    scenario_assessment: Mapping[str, object] | None
    chenggu: Mapping[str, object]
    evidence_fusion: Mapping[str, object]
    five_year: Mapping[str, object]
    renderer: Mapping[str, object]
    final_answer: str
    effective_domain_statuses: Mapping[str, str]
    warnings: tuple[str, ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE23_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE23_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE23_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return json.loads(canonical_json(asdict(self)))


def _artifact_hash(kind: str, value: object) -> str:
    if isinstance(value, Mapping) and isinstance(value.get("canonical_hash"), str):
        return str(value["canonical_hash"])
    return digest({"record_type": kind, "payload": value})


def _validated_input(raw: Mapping[str, object]) -> tuple[Mapping[str, object], int, Mapping[str, object], Sequence[Mapping[str, object]]]:
    if not isinstance(raw, Mapping):
        raise Phase23InputError("runtime input must be an object")
    if "baseline_domains" in raw:
        raise Phase23InputError("baseline_domains is no longer accepted; Phase 16 domain contracts are authoritative")
    chart_input = raw.get("chart_input")
    anchor = raw.get("anchor_year")
    reality = raw.get("reality", {})
    evidence = raw.get("fusion_evidence", [])
    if not isinstance(chart_input, Mapping):
        raise Phase23InputError("chart_input is required")
    if isinstance(anchor, bool) or not isinstance(anchor, int):
        raise Phase23InputError("anchor_year is required")
    if not isinstance(reality, Mapping):
        raise Phase23InputError("reality must be an object")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)) or not all(isinstance(item, Mapping) for item in evidence):
        raise Phase23InputError("fusion_evidence must be an array of objects")
    return chart_input, anchor, reality, evidence  # type: ignore[return-value]


def _target_contracts(contracts: Mapping[str, object], anchor: int) -> tuple[str, dict[str, Mapping[str, object]]]:
    identifiers = set(contracts.get("year_index", {}).get(str(anchor), []))  # type: ignore[union-attr]
    rows = [
        item for item in contracts.get("domain_contracts", [])
        if isinstance(item, Mapping) and item.get("contract_id") in identifiers
    ]
    if not rows:
        raise Phase23InputError(f"Phase 16 has no domain contracts for anchor_year {anchor}")
    targets = sorted({str(item["target_id"]) for item in rows})
    target_id = next((value for value in targets if value.startswith("window:")), None)
    target_id = target_id or next((value for value in targets if value.startswith("liunian:")), None) or targets[0]
    by_domain = {str(item["domain"]): item for item in rows if item.get("target_id") == target_id}
    if set(by_domain) != set(DOMAINS):
        raise Phase23InputError("Phase 16 anchor target does not contain all domain contracts")
    return target_id, by_domain


def _domain_evidence(by_domain: Mapping[str, Mapping[str, object]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for domain in DOMAINS:
        item = by_domain[domain]
        label = str(item.get("judgement_label"))
        direction = {"support_tendency": "support", "conflict_tendency": "contradict"}.get(label)
        if direction is None:
            continue
        records.append({
            "evidence_id": f"phase16:{item['contract_id']}",
            "claim_id": domain,
            "scope": "runtime:baseline",
            "source_type": "rule",
            "source_id": str(item["contract_id"]),
            "direction": direction,
            "weight": 1,
            "priority": 60,
            "verified": False,
            "detail_code": label,
        })
    return records


def _effective_statuses(
    by_domain: Mapping[str, Mapping[str, object]],
    fusion: Mapping[str, object],
) -> dict[str, str]:
    statuses = {domain: LABEL_TO_STATUS[str(by_domain[domain]["judgement_label"])] for domain in DOMAINS}
    for claim in fusion.get("claims", []):
        if not isinstance(claim, Mapping) or claim.get("scope") != "runtime:baseline":
            continue
        domain = str(claim.get("claim_id"))
        if domain not in statuses:
            continue
        if claim.get("status") == "unresolved_conflict" or claim.get("confidence") == "low":
            statuses[domain] = "unresolved"
        elif claim.get("hard_override_direction") == "support":
            statuses[domain] = "supportive"
        elif claim.get("hard_override_direction") == "contradict":
            statuses[domain] = "challenging"
        elif claim.get("status") == "resolved_by_priority":
            winning = set(claim.get("winning_evidence_ids", []))
            evidence = [item for item in fusion.get("evidence", []) if isinstance(item, Mapping) and item.get("evidence_id") in winning]
            if evidence:
                statuses[domain] = "supportive" if evidence[0].get("direction") == "support" else "challenging"
    return statuses


def run_mingli_agent(raw: Mapping[str, object]) -> MingLiRuntimeResult:
    chart_input, anchor, reality_raw, evidence_raw = _validated_input(raw)
    scenario = raw.get("scenario")
    if scenario not in {None, "career_exam", "relationship_reunion"}:
        raise Phase23InputError(f"unsupported scenario: {scenario}")

    chart = dict(DeterministicBaziEngine().calculate(chart_input))
    fact_graph = build_bazi_fact_graph(
        chart,
        liunian_start_year=anchor - 2,
        liunian_end_year=anchor + 2,
    ).to_dict()
    strength = calculate_day_master_strength(fact_graph).to_dict()
    pattern = evaluate_bazi_pattern(fact_graph, strength).to_dict()
    regulation = evaluate_bazi_regulation(fact_graph, strength, pattern).to_dict()
    xiji = evaluate_bazi_xiji_roles(regulation).to_dict()
    interactions = evaluate_luck_cycle_role_interactions(fact_graph, xiji).to_dict()
    trends = evaluate_bazi_temporal_trends(fact_graph, interactions).to_dict()
    domain_rules = evaluate_bazi_tengod_domains(fact_graph, interactions, trends).to_dict()
    domain_contracts = evaluate_base_domain_contracts(domain_rules).to_dict()
    target_id, by_domain = _target_contracts(domain_contracts, anchor)

    context = normalize_reality_context(reality_raw)
    fusion_items = _domain_evidence(by_domain) + [dict(item) for item in evidence_raw]
    fusion = orchestrate_evidence_fusion(context, fusion_items).to_dict()
    effective = _effective_statuses(by_domain, fusion)
    scenario_result = None
    if scenario is not None:
        scenario_result = evaluate_special_scenario(
            domain_contracts,
            scenario=scenario,
            target_id=target_id,
            reality_context=context.facts,
        ).to_dict()

    chenggu_input = {key: chart_input[key] for key in ("calendar", "birth_date", "birth_time") if key in chart_input}
    if "is_leap_month" in chart_input:
        chenggu_input["is_leap_month"] = chart_input["is_leap_month"]
    chenggu = calculate_chenggu(chenggu_input).to_dict()
    five_year = generate_five_year_outlook({
        "anchor_year": anchor,
        "baseline_domains": effective,
        "annual_evidence": raw.get("annual_evidence", []),
    })
    renderer = render_yuan_eight_sections({
        "profile": {key: chart_input.get(key) for key in ("calendar", "birth_date", "birth_time")},
        "chenggu": chenggu,
        "domains": effective,
        "overall_status": raw.get("overall_status", "unresolved"),
        "five_years": renderer_years(five_year),
        "advice_codes": raw.get("advice_codes", []),
    }).to_dict()

    artifacts = {
        "fact_graph": fact_graph,
        "strength": strength,
        "pattern": pattern,
        "regulation": regulation,
        "xiji": xiji,
        "luck_interactions": interactions,
        "temporal_trends": trends,
        "domain_rules": domain_rules,
        "domain_contracts": domain_contracts,
    }
    stage_artifacts: dict[str, object] = {
        "intake_validation": {"chart_input": chart_input, "anchor_year": anchor},
        "scenario_router": {"scenario": scenario or "base_domains"},
        "deterministic_chart": chart,
        **artifacts,
        "reality_context": context.to_dict(),
        "evidence_fusion": fusion,
        "confidence_gate": effective,
        "chenggu": chenggu,
        "five_year": five_year.to_dict(),
        "yuan_renderer": renderer,
        "final_answer": renderer["rendered_text"],
    }
    stages = tuple(
        RuntimeStage(stage, "completed", _artifact_hash(f"Runtime:{stage}", stage_artifacts[stage]))
        for stage in RUNTIME_STAGES
    )
    run_id = str(raw.get("run_id") or digest({"record_type": "RuntimeInput", "payload": raw})[:24])
    warnings = (
        "no_external_llm_or_network",
        "phase16_contracts_are_authoritative_domain_baseline",
        "reality_override_is_claim_and_scope_specific",
        "traditional_culture_not_decision_advice",
    )
    body = {
        "run_id": run_id,
        "stages": [asdict(stage) for stage in stages],
        "chart": chart,
        "artifacts": artifacts,
        "scenario_assessment": scenario_result,
        "chenggu": chenggu,
        "evidence_fusion": fusion,
        "five_year": five_year.to_dict(),
        "renderer": renderer,
        "final_answer": renderer["rendered_text"],
        "effective_domain_statuses": effective,
        "warnings": list(warnings),
    }
    return MingLiRuntimeResult(
        run_id,
        stages,
        chart,
        artifacts,
        scenario_result,
        chenggu,
        fusion,
        five_year.to_dict(),
        renderer,
        str(renderer["rendered_text"]),
        effective,
        warnings,
        digest({"record_type": "MingLiRuntimeResult", "payload": body}),
    )


def benchmark_phase23() -> dict[str, object]:
    payload = {
        "run_id": "runtime-fixture",
        "chart_input": {
            "gender": "male", "calendar": "solar", "birth_date": "1990-03-15",
            "birth_time": "10:30", "timezone": "Asia/Shanghai",
            "birth_location": {"longitude": 121.47, "latitude": 31.23}, "true_solar_time": False,
        },
        "anchor_year": 2028,
        "reality": {"cash_runway_months": 2},
        "fusion_evidence": [{
            "evidence_id": "rw", "claim_id": "wealth", "scope": "runtime:baseline",
            "source_type": "reality", "source_id": "user", "direction": "contradict",
            "weight": 0, "priority": 100, "verified": True,
        }],
        "annual_evidence": [{"evidence_id": "c28", "year": 2028, "domain": "career", "signal": 2}],
        "overall_status": "mixed",
        "advice_codes": ["verify_reality"],
    }
    result = run_mingli_agent(payload)
    checks = [
        (tuple(stage.stage for stage in result.stages) == RUNTIME_STAGES, "stage_order"),
        (all(stage.status == "completed" for stage in result.stages), "stage_status"),
        (result.chart["prediction_validity"] == "not_evaluated", "chart_boundary"),
        (result.chenggu["total_qian"] == 37, "chenggu"),
        (result.effective_domain_statuses["wealth"] == "challenging", "reality_override"),
        (result.artifacts["domain_contracts"]["phase15_result_hash"] == result.artifacts["domain_rules"]["canonical_hash"], "phase15_to_16"),
        (len(result.five_year["years"]) == 5, "five_year"),
        (len(result.renderer["sections"]) == 8, "renderer"),
        (result.final_answer.endswith("仅供文化研究与娱乐参考。"), "final_disclaimer"),
        (result.prediction_validity == "not_evaluated", "runtime_boundary"),
        (result.canonical_hash == run_mingli_agent(json.loads(json.dumps(payload))).canonical_hash, "determinism"),
    ]
    failures = [name for ok, name in checks if not ok]
    return {
        "assertions_total": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "unresolved": 0,
        "failures": failures,
    }
