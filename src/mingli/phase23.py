from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal, Mapping, Sequence

from .bazi import DeterministicBaziEngine
from .contracts.serialization import canonical_json, digest
from .phase18 import normalize_reality_context, orchestrate_evidence_fusion
from .phase19 import calculate_chenggu
from .phase20 import render_yuan_eight_sections
from .phase21 import generate_five_year_outlook, renderer_years

PHASE23_SCHEMA_VERSION = "mingli-agent-runtime-result@0.1"
PHASE23_METHOD_ID = "deterministic-mingli-agent-runtime@0.1.0"
PHASE23_CALCULATION_VERSION = "0.1.0"
PHASE23_DECISION_ID = "PHASE_23_END_TO_END_RUNTIME_R1_APPROVED"
RUNTIME_STAGES = ("chart", "chenggu", "reality_fusion", "five_year", "renderer")


class Phase23InputError(ValueError):
    pass


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
    chenggu: Mapping[str, object]
    evidence_fusion: Mapping[str, object]
    five_year: Mapping[str, object]
    renderer: Mapping[str, object]
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


def run_mingli_agent(raw: Mapping[str, object]) -> MingLiRuntimeResult:
    if not isinstance(raw, Mapping):
        raise Phase23InputError("runtime input must be an object")
    chart_input = raw.get("chart_input")
    baseline = raw.get("baseline_domains")
    anchor = raw.get("anchor_year")
    if not isinstance(chart_input, Mapping) or not isinstance(baseline, Mapping):
        raise Phase23InputError("chart_input and baseline_domains are required objects")
    if isinstance(anchor, bool) or not isinstance(anchor, int):
        raise Phase23InputError("anchor_year is required")
    chart = dict(DeterministicBaziEngine().calculate(chart_input))
    chenggu = calculate_chenggu({key: chart_input[key] for key in ("calendar", "birth_date", "birth_time") if key in chart_input} | ({"is_leap_month": chart_input["is_leap_month"]} if "is_leap_month" in chart_input else {})).to_dict()
    reality_raw = raw.get("reality", {})
    evidence_raw = raw.get("fusion_evidence", [])
    if not isinstance(reality_raw, Mapping) or not isinstance(evidence_raw, Sequence) or isinstance(evidence_raw, (str, bytes)):
        raise Phase23InputError("reality must be an object and fusion_evidence an array")
    context = normalize_reality_context(reality_raw)
    fusion = orchestrate_evidence_fusion(context, evidence_raw).to_dict()
    effective = {domain: str(baseline.get(domain, "unresolved")) for domain in ("career", "wealth", "relationship")}
    for claim in fusion["claims"]:
        if not isinstance(claim, Mapping):
            continue
        domain = str(claim.get("claim_id"))
        if domain in effective and claim.get("scope") == "runtime:baseline" and claim.get("hard_override_direction") in {"support", "contradict"}:
            effective[domain] = "supportive" if claim["hard_override_direction"] == "support" else "challenging"
    five_year = generate_five_year_outlook({"anchor_year": anchor, "baseline_domains": effective, "annual_evidence": raw.get("annual_evidence", [])})
    renderer = render_yuan_eight_sections({
        "profile": {key: chart_input.get(key) for key in ("calendar", "birth_date", "birth_time")},
        "chenggu": chenggu,
        "domains": effective,
        "overall_status": raw.get("overall_status", "unresolved"),
        "five_years": renderer_years(five_year),
        "advice_codes": raw.get("advice_codes", []),
    }).to_dict()
    stage_artifacts = {"chart": chart, "chenggu": chenggu, "reality_fusion": fusion, "five_year": five_year.to_dict(), "renderer": renderer}
    stages = tuple(RuntimeStage(stage, "completed", _artifact_hash(f"Runtime:{stage}", stage_artifacts[stage])) for stage in RUNTIME_STAGES)
    run_id = str(raw.get("run_id") or digest({"record_type": "RuntimeInput", "payload": raw})[:24])
    warnings = ("no_external_llm_or_network", "domain_baseline_must_come_from_approved_upstream", "traditional_culture_not_decision_advice")
    body = {"run_id": run_id, "stages": [asdict(stage) for stage in stages], "chart": chart, "chenggu": chenggu, "evidence_fusion": fusion, "five_year": five_year.to_dict(), "renderer": renderer, "effective_domain_statuses": effective, "warnings": list(warnings)}
    return MingLiRuntimeResult(run_id, stages, chart, chenggu, fusion, five_year.to_dict(), renderer, effective, warnings, digest({"record_type": "MingLiRuntimeResult", "payload": body}))


def benchmark_phase23() -> dict[str, object]:
    payload = {"run_id": "runtime-fixture", "chart_input": {"gender": "male", "calendar": "solar", "birth_date": "1990-03-15", "birth_time": "10:30", "timezone": "Asia/Shanghai", "birth_location": {"longitude": 121.47, "latitude": 31.23}, "true_solar_time": False}, "anchor_year": 2028, "baseline_domains": {"career": "mixed", "wealth": "challenging", "relationship": "unresolved"}, "reality": {"cash_runway_months": 2}, "fusion_evidence": [{"evidence_id": "rw", "claim_id": "wealth", "scope": "runtime:baseline", "source_type": "reality", "source_id": "user", "direction": "contradict", "weight": 0, "priority": 100, "verified": True}], "annual_evidence": [{"evidence_id": "c28", "year": 2028, "domain": "career", "signal": 2}], "overall_status": "mixed", "advice_codes": ["verify_reality"]}
    result = run_mingli_agent(payload)
    checks = [(tuple(stage.stage for stage in result.stages) == RUNTIME_STAGES, "stage_order"), (all(stage.status == "completed" for stage in result.stages), "stage_status"), (result.chart["prediction_validity"] == "not_evaluated", "chart_boundary"), (result.chenggu["total_qian"] == 37, "chenggu"), (result.effective_domain_statuses["wealth"] == "challenging", "reality_override"), (len(result.five_year["years"]) == 5, "five_year"), (len(result.renderer["sections"]) == 8, "renderer"), (result.prediction_validity == "not_evaluated", "runtime_boundary"), (result.canonical_hash == run_mingli_agent(json.loads(json.dumps(payload))).canonical_hash, "determinism")]
    failures = [name for ok, name in checks if not ok]
    return {"assertions_total": len(checks), "passed": len(checks) - len(failures), "failed": len(failures), "unresolved": 0, "failures": failures}
