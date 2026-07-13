from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Callable, Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase16 import build_phase16_fixture, evaluate_base_domain_contracts, validate_phase16_rules
from .phase17 import evaluate_special_scenario, validate_phase17_rules
from .phase18 import orchestrate_evidence_fusion
from .phase19 import calculate_chenggu, load_chenggu_table, validate_phase19_table
from .phase20 import DISCLAIMER, SECTION_TITLES, render_yuan_eight_sections
from .phase21 import Phase21InputError, generate_five_year_outlook
from .phase22 import run_case_benchmark
from .phase23 import RUNTIME_STAGES, run_mingli_agent

PHASE24_SCHEMA_VERSION = "release-candidate-assessment@0.2"
PHASE24_METHOD_ID = "independent-local-rc-product-gate@0.2.0"
PHASE24_CALCULATION_VERSION = "0.2.0"
PHASE24_DECISION_ID = "PHASE_24_RELEASE_CANDIDATE_PRODUCT_VALIDATION_R2_HOLD"


@dataclass(frozen=True)
class PhaseGate:
    phase: int
    assertions_total: int
    passed: int
    failed: int
    status: str


@dataclass(frozen=True)
class ReleaseCandidateAssessment:
    release_decision: str
    local_technical_rc_ready: bool
    product_release_ready: bool
    phase_gates: tuple[PhaseGate, ...]
    blockers: tuple[Mapping[str, str], ...]
    codex_handoff: tuple[Mapping[str, str], ...]
    provenance: Mapping[str, object]
    warnings: tuple[str, ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE24_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE24_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE24_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return json.loads(canonical_json(asdict(self)))


def _result(phase: int, checks: tuple[bool, ...]) -> PhaseGate:
    passed = sum(checks)
    return PhaseGate(phase, len(checks), passed, len(checks) - passed, "passed" if passed == len(checks) else "failed")


def _phase16_check() -> PhaseGate:
    result = evaluate_base_domain_contracts(build_phase16_fixture("甲", "寅"))
    return _result(16, (
        not validate_phase16_rules(),
        len(result.domain_contracts) > 0,
        {item.domain for item in result.domain_contracts} == {"career", "wealth", "relationship"},
        result.prediction_validity == "not_evaluated",
    ))


def _phase17_check() -> PhaseGate:
    source = evaluate_base_domain_contracts(build_phase16_fixture("甲", "寅")).to_dict()
    target = str(source["domain_contracts"][0]["target_id"])
    result = evaluate_special_scenario(
        source,
        scenario="relationship_reunion",
        target_id=target,
        reality_context={"legal_contact_restriction": True, "root_cause_resolved": True},
    )
    layers = {item.layer: item for item in result.layers}
    return _result(17, (
        not validate_phase17_rules(),
        layers["recontact"].reality_override,
        layers["reunion"].label == "conflict",
        layers["stability"].label == "conflict",
        result.prediction_validity == "not_evaluated",
    ))


def _phase18_check() -> PhaseGate:
    result = orchestrate_evidence_fusion({}, (
        {"evidence_id":"rule","claim_id":"career","scope":"independent","source_type":"rule","source_id":"p16","direction":"support","weight":8,"priority":60},
        {"evidence_id":"reality","claim_id":"career","scope":"independent","source_type":"reality","source_id":"confirmed","direction":"contradict","weight":0,"priority":100,"verified":True},
    ))
    claim = result.claims[0]
    return _result(18, (
        claim.status == "resolved_by_reality_override",
        claim.hard_override_direction == "contradict",
        claim.contradiction_penalty > 0,
        "rule" in claim.conflicting_evidence_ids,
        result.prediction_validity == "not_evaluated",
    ))


def _phase19_check() -> PhaseGate:
    result = calculate_chenggu({"calendar":"solar","birth_date":"1990-03-15","birth_time":"10:30"})
    table = validate_phase19_table()
    return _result(19, (
        table["valid"] is True and not table["failures"],
        result.total_qian == 37,
        result.display_weight == "3两7钱",
        result.verse_available is False,
        result.prediction_validity == "not_evaluated",
    ))


def _phase20_check() -> PhaseGate:
    result = render_yuan_eight_sections({
        "profile":{"calendar":"solar","birth_date":"1990-03-15","birth_time":"10:30"},
        "chenggu":{"display_weight":"3两7钱","verse_available":False},
        "domains":{"career":"mixed","wealth":"challenging","relationship":"unresolved"},
        "overall_status":"mixed",
        "five_years":[{"year":year,"status":"mixed"} for year in range(2026,2031)],
    })
    return _result(20, (
        tuple(item.title for item in result.sections) == SECTION_TITLES,
        len(result.sections) == 8,
        result.rendered_text.count(DISCLAIMER) == 1,
        result.rendered_text.endswith(DISCLAIMER),
        result.prediction_validity == "not_evaluated",
    ))


def _phase21_check() -> PhaseGate:
    result = generate_five_year_outlook({
        "anchor_year":2028,
        "baseline_domains":{"career":"mixed","wealth":"challenging","relationship":"unresolved"},
        "annual_evidence":[{"evidence_id":"r","year":2028,"domain":"career","signal":0,"verified_reality":"support"}],
    })
    rejected = False
    try:
        generate_five_year_outlook({
            "anchor_year":2028,
            "baseline_domains":{"career":"mixed","wealth":"mixed","relationship":"mixed"},
            "annual_evidence":[{"year":2028,"domain":"career","signal":1,"event":"promotion"}],
        })
    except Phase21InputError:
        rejected = True
    return _result(21, (
        [item.year for item in result.years] == [2026,2027,2028,2029,2030],
        next(item for item in result.years if item.year == 2028).domain_statuses["career"] == "supportive",
        rejected,
        result.prediction_validity == "not_evaluated",
    ))


def _phase22_check() -> PhaseGate:
    empty = run_case_benchmark()
    synthetic = run_case_benchmark({
        "registry_id":"independent-contract",
        "minimum_cases_for_product_claim":1,
        "cases":[{"case_id":"synthetic:1","case_class":"synthetic","predicted_claims":{"c":"mixed"},"observed_claims":{"c":"mixed"}}],
    })
    return _result(22, (
        empty.eligible_real_cases == 0,
        empty.exact_match_rate is None,
        not empty.product_accuracy_claim_allowed,
        synthetic.synthetic_contract_cases == 1,
        synthetic.eligible_real_cases == 0,
        synthetic.exact_match_rate is None,
    ))


def _phase23_check() -> PhaseGate:
    result = run_mingli_agent({
        "chart_input":{"gender":"male","calendar":"solar","birth_date":"1990-03-15","birth_time":"10:30","timezone":"Asia/Shanghai","birth_location":{"longitude":121.47,"latitude":31.23},"true_solar_time":False},
        "anchor_year":2028,
        "reality":{"cash_runway_months":2},
        "fusion_evidence":[{"evidence_id":"wealth-reality","claim_id":"wealth","scope":"runtime:baseline","source_type":"reality","source_id":"confirmed","direction":"contradict","weight":0,"priority":100,"verified":True}],
    })
    return _result(23, (
        tuple(item.stage for item in result.stages) == RUNTIME_STAGES,
        all(item.status == "completed" for item in result.stages),
        result.artifacts["domain_contracts"]["phase15_result_hash"] == result.artifacts["domain_rules"]["canonical_hash"],
        result.effective_domain_statuses["wealth"] == "challenging",
        len(result.renderer["sections"]) == 8,
        result.final_answer.endswith(DISCLAIMER),
        result.prediction_validity == "not_evaluated",
    ))


INDEPENDENT_CHECKS: tuple[tuple[int, Callable[[], PhaseGate]], ...] = (
    (16,_phase16_check),(17,_phase17_check),(18,_phase18_check),(19,_phase19_check),
    (20,_phase20_check),(21,_phase21_check),(22,_phase22_check),(23,_phase23_check),
)


def run_independent_release_checks() -> tuple[PhaseGate, ...]:
    """Run fixed expected-output checks that do not call phase benchmark helpers."""
    return tuple(check() for _, check in INDEPENDENT_CHECKS)


def assess_release_candidate() -> ReleaseCandidateAssessment:
    gates = run_independent_release_checks()
    technical_ready = all(gate.status == "passed" for gate in gates)
    case_report = run_case_benchmark()
    table = load_chenggu_table()
    blockers = (
        {"blocker_id":"P19_VERSE_SOURCE","owner":"content-review","status":"open","detail":"完整称骨歌诀尚无通过来源审核的版本；Renderer 只展示骨重。"},
        {"blocker_id":"P22_REAL_CASE_THRESHOLD","owner":"authorized-data-process","status":"open","detail":f"合格真实案例 {case_report.eligible_real_cases}/{case_report.minimum_real_cases}，不得宣称产品准确率。"},
    )
    handoff = (
        {"task_id":"CONTENT_01","action":"review_chenggu_verses","command":"由内容审核流程核对完整歌诀及授权","acceptance":"逐条来源可追溯且完成授权审核"},
        {"task_id":"DATA_01","action":"collect_consented_cases","command":"由授权数据流程导入去标识真实案例","acceptance":f"不少于 {case_report.minimum_real_cases} 个合格案例"},
    )
    product_ready = technical_ready and not blockers
    decision = "release" if product_ready else ("technical_rc_only_product_hold" if technical_ready else "technical_hold")
    provenance = {
        "phase_range":"16-24",
        "gate_source":"independent_contract_checks@0.1",
        "benchmark_helpers_invoked":False,
        "chenggu_table_id":table["table_id"],
        "real_case_registry_hash":case_report.canonical_hash,
    }
    warnings = ("technical_rc_does_not_equal_product_validity","prediction_validity_not_evaluated","external_ci_must_remain_a_separate_merge_gate")
    body = {
        "release_decision":decision,
        "local_technical_rc_ready":technical_ready,
        "product_release_ready":product_ready,
        "phase_gates":[asdict(gate) for gate in gates],
        "blockers":list(blockers),
        "codex_handoff":list(handoff),
        "provenance":provenance,
        "warnings":list(warnings),
    }
    return ReleaseCandidateAssessment(decision,technical_ready,product_ready,gates,blockers,handoff,provenance,warnings,digest({"record_type":"ReleaseCandidateAssessment","payload":body}))


def benchmark_phase24(assessment: ReleaseCandidateAssessment | None = None) -> dict[str, object]:
    result = assessment or assess_release_candidate()
    checks = (
        result.local_technical_rc_ready,
        not result.product_release_ready,
        result.release_decision == "technical_rc_only_product_hold",
        tuple(gate.phase for gate in result.phase_gates) == tuple(range(16,24)),
        all(gate.status == "passed" for gate in result.phase_gates),
        {item["blocker_id"] for item in result.blockers} == {"P19_VERSE_SOURCE","P22_REAL_CASE_THRESHOLD"},
        result.provenance.get("benchmark_helpers_invoked") is False,
        result.prediction_validity == "not_evaluated",
    )
    failures = [f"phase24_contract_{index}" for index, ok in enumerate(checks,1) if not ok]
    return {"assertions_total":len(checks),"passed":len(checks)-len(failures),"failed":len(failures),"unresolved":0,"failures":failures,"release_decision":result.release_decision}
