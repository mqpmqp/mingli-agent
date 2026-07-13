from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Callable, Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .phase16 import benchmark_phase16
from .phase17 import benchmark_phase17
from .phase18 import benchmark_phase18
from .phase19 import benchmark_phase19, load_chenggu_table
from .phase20 import benchmark_phase20
from .phase21 import benchmark_phase21
from .phase22 import benchmark_phase22, run_case_benchmark
from .phase23 import benchmark_phase23

PHASE24_SCHEMA_VERSION = "release-candidate-assessment@0.1"
PHASE24_METHOD_ID = "local-rc-product-gate@0.1.0"
PHASE24_CALCULATION_VERSION = "0.1.0"
PHASE24_DECISION_ID = "PHASE_24_RELEASE_CANDIDATE_PRODUCT_VALIDATION_R1_HOLD"


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


def _plain_benchmark(value: object) -> Mapping[str, object]:
    if hasattr(value, "to_dict"):
        return value.to_dict()  # type: ignore[no-any-return]
    if isinstance(value, Mapping):
        return value
    return asdict(value)  # type: ignore[arg-type]


def assess_release_candidate() -> ReleaseCandidateAssessment:
    runners: tuple[tuple[int, Callable[[], object]], ...] = ((16, benchmark_phase16), (17, benchmark_phase17), (18, benchmark_phase18), (19, benchmark_phase19), (20, benchmark_phase20), (21, benchmark_phase21), (22, benchmark_phase22), (23, benchmark_phase23))
    gates: list[PhaseGate] = []
    for phase, runner in runners:
        result = _plain_benchmark(runner())
        total, passed, failed = int(result.get("assertions_total", 0)), int(result.get("passed", 0)), int(result.get("failed", 0))
        gates.append(PhaseGate(phase, total, passed, failed, "passed" if total > 0 and failed == 0 and passed == total else "failed"))
    technical_ready = all(gate.status == "passed" for gate in gates)
    case_report = run_case_benchmark()
    table = load_chenggu_table()
    blockers: list[dict[str, str]] = []
    blockers.append({"blocker_id": "P19_VERSE_SOURCE", "owner": "content-review", "status": "open", "detail": "完整称骨歌诀尚无通过核验的版本，Renderer 仅展示骨重。"})
    blockers.append({"blocker_id": "P22_REAL_CASE_THRESHOLD", "owner": "authorized-data-process", "status": "open", "detail": f"合格真实案例 {case_report.eligible_real_cases}/{case_report.minimum_real_cases}，不得宣称产品准确率。"})
    blockers.append({"blocker_id": "CLOUD_CI", "owner": "codex", "status": "deferred", "detail": "需要在具备完整依赖的环境运行全仓测试、构建与安装后验。"})
    handoff = (
        {"task_id": "CODEX_01", "action": "run_full_ci", "command": "python -m pytest && python -m build", "acceptance": "全仓测试通过且 sdist/wheel 构建成功"},
        {"task_id": "CODEX_02", "action": "isolated_wheel_readback", "command": "在隔离环境安装 wheel，运行 P16-P24 benchmark，并比对源树/安装包 canonical hash", "acceptance": "所有 benchmark 通过且哈希一致"},
        {"task_id": "CODEX_03", "action": "publish_branch", "command": "git push -u origin agent/phase16-domain-contracts-base-rules-v1", "acceptance": "远端分支存在"},
        {"task_id": "CODEX_04", "action": "open_pull_request", "command": "创建覆盖 P16-P24 的 draft PR，并附各阶段报告和产品阻塞项", "acceptance": "PR 创建且 CI 状态可见"},
    )
    product_ready = technical_ready and not blockers
    decision = "release" if product_ready else ("technical_rc_only_product_hold" if technical_ready else "technical_hold")
    provenance = {"phase_range": "16-24", "chenggu_table_id": table["table_id"], "real_case_registry_hash": case_report.canonical_hash, "local_validation_scope": "deterministic benchmarks only"}
    warnings = ("local_pass_does_not_equal_product_validity", "prediction_validity_not_evaluated", "external_tasks_deferred_to_codex")
    body = {"release_decision": decision, "local_technical_rc_ready": technical_ready, "product_release_ready": product_ready, "phase_gates": [asdict(gate) for gate in gates], "blockers": blockers, "codex_handoff": list(handoff), "provenance": provenance, "warnings": list(warnings)}
    return ReleaseCandidateAssessment(decision, technical_ready, product_ready, tuple(gates), tuple(blockers), handoff, provenance, warnings, digest({"record_type": "ReleaseCandidateAssessment", "payload": body}))


def benchmark_phase24(assessment: ReleaseCandidateAssessment | None = None) -> dict[str, object]:
    result = assessment or assess_release_candidate()
    checks = [(result.local_technical_rc_ready, "technical_rc"), (not result.product_release_ready, "product_hold"), (result.release_decision == "technical_rc_only_product_hold", "decision"), (tuple(gate.phase for gate in result.phase_gates) == tuple(range(16, 24)), "phase_order"), (all(gate.status == "passed" for gate in result.phase_gates), "phase_gates"), ({item["blocker_id"] for item in result.blockers} == {"P19_VERSE_SOURCE", "P22_REAL_CASE_THRESHOLD", "CLOUD_CI"}, "blockers"), (len(result.codex_handoff) == 4, "handoff"), (result.prediction_validity == "not_evaluated", "prediction_boundary")]
    failures = [name for ok, name in checks if not ok]
    return {"assertions_total": len(checks), "passed": len(checks) - len(failures), "failed": len(failures), "unresolved": 0, "failures": failures, "release_decision": result.release_decision}
