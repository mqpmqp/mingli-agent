from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from datetime import datetime
from typing import Callable, Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase16 import build_phase16_fixture, evaluate_base_domain_contracts, validate_phase16_rules
from .phase17 import evaluate_special_scenario, validate_phase17_rules
from .phase18 import orchestrate_evidence_fusion
from .phase19 import calculate_chenggu, load_chenggu_table, validate_phase19_table
from .phase20 import DISCLAIMER, SECTION_TITLES, render_yuan_eight_sections
from .phase21 import Phase21InputError, generate_five_year_outlook
from .phase22 import CaseBenchmarkReport, run_case_benchmark
from .phase23 import RUNTIME_STAGES, run_mingli_agent
from .validation_authorization import evaluate_product_release

PHASE24_SCHEMA_VERSION = "release-candidate-assessment@0.6"
PHASE24_METHOD_ID = "dual-product-commercial-release-gate@0.6.0"
PHASE24_CALCULATION_VERSION = "0.6.0"
PHASE24_DECISION_ID = "PHASE_24_PRODUCT_CAPABILITY_COMMERCIAL_VALIDATION_R5"


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
    product_release_status: Literal["PRODUCT_RELEASE_HOLD", "PRODUCT_RELEASE_ALLOWED"]
    product_capability_status: Literal["PRODUCT_CAPABILITY_READY", "PRODUCT_CAPABILITY_BLOCKED"]
    commercial_validation_status: Literal["COMMERCIAL_VALIDATION_PENDING", "COMMERCIAL_VALIDATION_READY"]
    development_runtime_allowed: bool
    production_commercial_allowed: bool
    validation_closure_passed: bool
    product_accuracy_claim_allowed: bool
    phase_gates: tuple[PhaseGate, ...]
    blockers: tuple[Mapping[str, str], ...]
    codex_handoff: tuple[Mapping[str, str], ...]
    provenance: Mapping[str, object]
    warnings: tuple[str, ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE24_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE24_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE24_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated", "evaluated"] = "not_evaluated"

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
    exam = evaluate_special_scenario(source, scenario="career_exam", target_id=target)
    exam_layers = {item.layer: item for item in exam.layers}
    return _result(17, (
        not validate_phase17_rules(),
        tuple(exam_layers) == ("system_fit", "admission_outlook", "exam_outlook", "position_direction", "preparation_strategy"),
        exam_layers["exam_outlook"].label == "unresolved" and exam_layers["exam_outlook"].confidence == "low",
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
        result.conventions["gender_basis"] == "not_used_for_weight_calculation",
        result.prediction_validity == "not_evaluated",
    ))


def _phase20_check() -> PhaseGate:
    result = render_yuan_eight_sections({
        "profile":{"calendar":"solar","birth_date":"1990-03-15","birth_time":"10:30"},
        "chenggu":{"display_weight":"3两7钱","verse_available":False},
        "domains":{"career":"mixed","wealth":"challenging","relationship":"unresolved"},
        "domain_confidence":{"career":"medium","wealth":"medium","relationship":"low"},
        "five_years":[{"year":year,"status":"mixed","confidence":"low"} for year in range(2026,2031)],
    })
    return _result(20, (
        tuple(item.title for item in result.sections) == SECTION_TITLES,
        len(result.sections) == 8,
        result.rendered_text.count(DISCLAIMER) == 1,
        result.rendered_text.endswith(DISCLAIMER),
        "置信度：低" in result.sections[6].content,
        result.prediction_validity == "not_evaluated",
    ))


def _phase21_check() -> PhaseGate:
    result = generate_five_year_outlook({
        "anchor_year":2028,
        "baseline_domains":{"career":"mixed","wealth":"challenging","relationship":"unresolved"},
        "annual_evidence":[{"evidence_id":"r","year":2028,"domain":"career","signal":0,"verified_reality":"support","source_type":"reality","source_id":"confirmed","verified":True}],
    })
    rejected = False
    try:
        generate_five_year_outlook({
            "anchor_year":2028,
            "baseline_domains":{"career":"mixed","wealth":"mixed","relationship":"mixed"},
            "annual_evidence":[{"evidence_id":"forbidden","year":2028,"domain":"career","signal":1,"event":"promotion","source_type":"rule","source_id":"test"}],
        })
    except Phase21InputError:
        rejected = True
    return _result(21, (
        [item.year for item in result.years] == [2026,2027,2028,2029,2030],
        next(item for item in result.years if item.year == 2028).domain_statuses["career"] == "supportive",
        next(item for item in result.years if item.year == 2028).domain_confidence["career"] == "high",
        all(item.confidence in {"high", "medium", "low"} for item in result.years),
        rejected,
        result.prediction_validity == "not_evaluated",
    ))


def _phase22_check() -> PhaseGate:
    empty = run_case_benchmark()
    synthetic = run_case_benchmark({
        "registry_id":"independent-contract",
        "minimum_cases_for_product_claim":30,
        "cases":[{"case_id":"synthetic:1","case_class":"synthetic","predicted_claims":{"c":"mixed"},"observed_claims":{"c":"mixed"}}],
    })
    return _result(22, (
        empty.eligible_real_cases == 0,
        not empty.validation_closure_passed,
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
        result.effective_domain_confidence["wealth"] == result.evidence_fusion["claims"][0]["confidence"],
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


def assess_release_candidate(
    case_report: CaseBenchmarkReport | None = None,
    *,
    frozen_dataset_manifest: Mapping[str, object] | None = None,
    product_release_authorization: Mapping[str, object] | None = None,
    external_gates: Mapping[str, object] | None = None,
    now: datetime | None = None,
) -> ReleaseCandidateAssessment:
    gates = run_independent_release_checks()
    technical_ready = all(gate.status == "passed" for gate in gates)
    resolved_case_report = case_report or run_case_benchmark()
    table = load_chenggu_table()
    blockers: list[Mapping[str, str]] = []
    handoff: list[Mapping[str, str]] = []
    if not resolved_case_report.validation_closure_passed:
        blockers.append({"blocker_id":"P22_VALIDATION_CLOSURE","owner":"authorized-data-process","status":"open","detail":f"当前合格唯一人员 {resolved_case_report.qualified_unique_person_cases}；validation closure failures: {','.join(resolved_case_report.validation_closure_failures)}"})
        handoff.append({"task_id":"DATA_01","action":"collect_tiered_validation_cases","command":"由授权数据流程导入去标识 Gold/Silver 私有案例","acceptance":"validation closure 达到 30 个唯一合格案例，其中 Gold 不少于 10；准确率声明另需 30 个唯一 Gold 人员"})
    formal_release_requested = any(
        value is not None
        for value in (frozen_dataset_manifest, product_release_authorization, external_gates)
    )
    if formal_release_requested:
        release_gate = evaluate_product_release(
            frozen_dataset_manifest,
            product_release_authorization,
            external_gates,
            now=now,
        )
        formal_blockers = set(release_gate["blockers"])
        if not frozen_dataset_manifest or frozen_dataset_manifest.get("phase22_assessment_hash") != resolved_case_report.canonical_hash:
            formal_blockers.add("P22_FROZEN_ASSESSMENT_MISMATCH")
        if frozen_dataset_manifest and frozen_dataset_manifest.get("product_accuracy_claim_allowed") is not resolved_case_report.product_accuracy_claim_allowed:
            formal_blockers.add("P22_ACCURACY_ASSESSMENT_MISMATCH")
        if resolved_case_report.validation_closure_passed:
            formal_blockers.discard("P22_VALIDATION_CLOSURE")
        elif "P22_VALIDATION_CLOSURE" not in formal_blockers:
            formal_blockers.add("P22_VALIDATION_CLOSURE")
        blockers = [item for item in blockers if item["blocker_id"] != "P22_VALIDATION_CLOSURE"]
        blockers.extend(
            {
                "blocker_id": blocker_id,
                "owner": "independent-release-gate",
                "status": "open",
                "detail": "Formal frozen-dataset authorization gate is not satisfied.",
            }
            for blocker_id in sorted(formal_blockers)
        )
        if formal_blockers:
            handoff.append({"task_id":"RELEASE_01","action":"close_formal_release_gates","command":"由独立产品审查者关闭冻结数据集授权和外部门禁","acceptance":"授权引用当前冻结 dataset，未过期且 P1/P2、privacy、package、main CI 全部通过"})
        product_status = str(release_gate["status"])
    else:
        blockers.append({"blocker_id":"PRODUCT_RELEASE_AUTHORIZATION","owner":"product-review","status":"open","detail":"Validation closure 与 product accuracy claim 均不构成产品发布授权；当前仍为 PRODUCT_RELEASE_HOLD。"})
        handoff.append({"task_id":"RELEASE_01","action":"independent_product_release_review","command":"由产品负责人独立审查发布条件","acceptance":"另行明确授权产品发布；不得由 validation closure 自动推导"})
        product_status = "PRODUCT_RELEASE_HOLD"
    if not technical_ready and product_status == "PRODUCT_RELEASE_ALLOWED":
        product_status = "PRODUCT_RELEASE_HOLD"
        blockers.append({"blocker_id":"TECHNICAL_RELEASE_GATE","owner":"engineering","status":"open","detail":"Independent Phase 16-23 checks are not all passing."})
    product_ready = technical_ready and product_status == "PRODUCT_RELEASE_ALLOWED" and not blockers
    capability_status = "PRODUCT_CAPABILITY_READY" if technical_ready else "PRODUCT_CAPABILITY_BLOCKED"
    commercial_status = "COMMERCIAL_VALIDATION_READY" if product_ready else "COMMERCIAL_VALIDATION_PENDING"
    decision = "release" if product_ready else ("technical_rc_only_product_hold" if technical_ready else "technical_hold")
    provenance = {
        "phase_range":"16-24",
        "gate_source":"independent_contract_checks@0.2",
        "benchmark_helpers_invoked":False,
        "chenggu_table_id":table["table_id"],
        "real_case_registry_hash":resolved_case_report.canonical_hash,
        "validation_closure_passed":resolved_case_report.validation_closure_passed,
        "product_accuracy_claim_allowed":resolved_case_report.product_accuracy_claim_allowed,
        "formal_release_gate_evaluated":formal_release_requested,
        "dataset_id":frozen_dataset_manifest.get("dataset_id") if frozen_dataset_manifest else None,
        "authorization_status":product_release_authorization.get("authorization_status") if product_release_authorization else None,
    }
    prediction_validity = "evaluated" if product_ready else "not_evaluated"
    warnings = (
        "technical_rc_does_not_equal_product_validity",
        "external_ci_must_remain_a_separate_merge_gate",
        *(("prediction_validity_not_evaluated",) if not product_ready else ()),
    )
    body = {
        "release_decision":decision,
        "local_technical_rc_ready":technical_ready,
        "product_release_ready":product_ready,
        "product_release_status":product_status,
        "product_capability_status":capability_status,
        "commercial_validation_status":commercial_status,
        "development_runtime_allowed":technical_ready,
        "production_commercial_allowed":product_ready,
        "validation_closure_passed":resolved_case_report.validation_closure_passed,
        "product_accuracy_claim_allowed":resolved_case_report.product_accuracy_claim_allowed,
        "phase_gates":[asdict(gate) for gate in gates],
        "blockers":blockers,
        "codex_handoff":handoff,
        "provenance":provenance,
        "warnings":list(warnings),
        "prediction_validity":prediction_validity,
    }
    return ReleaseCandidateAssessment(
        release_decision=decision,
        local_technical_rc_ready=technical_ready,
        product_release_ready=product_ready,
        product_release_status=product_status,
        product_capability_status=capability_status,
        commercial_validation_status=commercial_status,
        development_runtime_allowed=technical_ready,
        production_commercial_allowed=product_ready,
        validation_closure_passed=resolved_case_report.validation_closure_passed,
        product_accuracy_claim_allowed=resolved_case_report.product_accuracy_claim_allowed,
        phase_gates=gates,
        blockers=tuple(blockers),
        codex_handoff=tuple(handoff),
        provenance=provenance,
        warnings=warnings,
        canonical_hash=digest({"record_type":"ReleaseCandidateAssessment","payload":body}),
        prediction_validity=prediction_validity,
    )


def benchmark_phase24(assessment: ReleaseCandidateAssessment | None = None) -> dict[str, object]:
    result = assessment or assess_release_candidate()
    checks = (
        result.local_technical_rc_ready,
        not result.product_release_ready,
        result.product_release_status == "PRODUCT_RELEASE_HOLD",
        result.product_capability_status == "PRODUCT_CAPABILITY_READY",
        result.commercial_validation_status == "COMMERCIAL_VALIDATION_PENDING",
        result.development_runtime_allowed,
        not result.production_commercial_allowed,
        not result.validation_closure_passed,
        not result.product_accuracy_claim_allowed,
        result.release_decision == "technical_rc_only_product_hold",
        tuple(gate.phase for gate in result.phase_gates) == tuple(range(16,24)),
        all(gate.status == "passed" for gate in result.phase_gates),
        {item["blocker_id"] for item in result.blockers} == {"P22_VALIDATION_CLOSURE","PRODUCT_RELEASE_AUTHORIZATION"},
        result.provenance.get("benchmark_helpers_invoked") is False,
        result.prediction_validity == "not_evaluated",
    )
    failures = [f"phase24_contract_{index}" for index, ok in enumerate(checks,1) if not ok]
    return {"assertions_total":len(checks),"passed":len(checks)-len(failures),"failed":len(failures),"unresolved":0,"failures":failures,"release_decision":result.release_decision}
