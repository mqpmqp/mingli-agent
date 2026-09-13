"""Run the five Phase 4 synthetic acceptance paths through real CLI processes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def _run(root: Path, store: Path, command: str, payload: dict[str, object]) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "mingli.training_cli",
            command,
            "--input",
            "-",
            "--store",
            str(store),
            "--repository-root",
            str(root),
            "--synthetic",
            "--json",
        ],
        input=json.dumps(payload, ensure_ascii=True),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        cwd=root,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(f"{command}: exit={completed.returncode}; {completed.stdout}; {completed.stderr}")
    return json.loads(completed.stdout)["data"]


def _phase3_steps(root: Path, name: str) -> list[dict[str, object]]:
    path = root / "examples" / "practice_phase3" / f"{name}.json"
    sample = json.loads(path.read_text(encoding="utf-8"))
    if sample["synthetic"] is not True:
        raise AssertionError("Phase 4 只能复用明确标记 synthetic 的工程样例")
    return [step for step in sample["steps"] if step["command"] not in {"validation-summary", "pilot-show"}]


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 五组 synthetic CLI 验收")
    parser.add_argument("--store", type=Path, required=True, help="工作区内尚不存在的专用临时目录")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    target = args.store.resolve()
    if target.exists() or root not in target.parents:
        parser.error("store 必须是工作区内尚不存在的专用临时目录")
    base = Path(__file__).parent
    start = json.loads((base / "pilot_start.json").read_text(encoding="utf-8"))
    candidate = json.loads((base / "candidate_intake.json").read_text(encoding="utf-8"))
    screen = json.loads((base / "screen_eligible.json").read_text(encoding="utf-8"))
    scenarios = []
    for scenario, phase3_name in (
        ("case_a_l2_hit", "l2_hit"),
        ("case_b_l2_miss", "l2_miss"),
        ("case_c_l3_pending", "l3_pending"),
        ("case_d_l3_matured_feedback", "l3_pending"),
        ("case_e_l3_matured_no_feedback", "l3_pending"),
    ):
        store = target / scenario
        _run(root, store, "pilot-start", start)
        intake = _run(root, store, "pilot-candidate-intake", candidate)
        screen["candidate_id"] = intake["candidate_id"]
        _run(root, store, "pilot-screen", screen)
        for step in _phase3_steps(root, phase3_name):
            _run(root, store, step["command"], step["input"])
        as_of = "2026-11-08T13:00:00+08:00"
        if scenario == "case_c_l3_pending":
            as_of = "2026-11-05T12:00:00+08:00"
            maturity = _run(
                root,
                store,
                "pilot-mature",
                {
                    "batch_id": "phase4-pilot-001",
                    "maturity_id": "maturity-pending",
                    "prediction_id": "prediction-l3_pending",
                    "claim_id": "interview",
                    "as_of": as_of,
                    "resolution": "pending",
                    "synthetic": True,
                },
            )
            assert maturity["maturity_status"] == "pending"
        elif scenario == "case_d_l3_matured_feedback":
            _run(
                root,
                store,
                "outcome-append",
                {
                    "prediction_id": "prediction-l3_pending",
                    "evidence_id": "future-evidence",
                    "claim_id": "interview",
                    "event_window": "2026-10-01T00:00:00+08:00/2026-10-31T23:59:59+08:00",
                    "observed_at": "2026-10-20T12:00:00+08:00",
                    "collected_at": "2026-11-08T10:00:00+08:00",
                    "source_provenance": "synthetic_fixture",
                    "evidence_quality": "synthetic",
                    "fact": "离线样例记录包含一份面谈通知",
                    "synthetic": True,
                },
            )
            _run(
                root,
                store,
                "pilot-mature",
                {
                    "batch_id": "phase4-pilot-001",
                    "maturity_id": "maturity-feedback",
                    "prediction_id": "prediction-l3_pending",
                    "claim_id": "interview",
                    "as_of": as_of,
                    "resolution": "with_feedback",
                    "synthetic": True,
                },
            )
            _run(
                root,
                store,
                "claim-adjudicate",
                {
                    "prediction_id": "prediction-l3_pending",
                    "adjudication_id": "decision-l3-matured",
                    "claim_id": "interview",
                    "outcome_evidence_ids": ["future-evidence"],
                    "status": "hit",
                    "reason": "仅核对离线事实与冻结结果变量",
                    "adjudicated_at": as_of,
                    "verdict": "hit",
                    "timing_verdict": "in_window",
                    "direction_verdict": "support",
                    "adjudicator": "synthetic-reviewer-one",
                    "adjudication_status": "single_reviewer",
                },
            )
            _run(
                root,
                store,
                "pilot-quality-append",
                {
                    "batch_id": "phase4-pilot-001",
                    "quality_feedback_id": "quality-one",
                    "prediction_id": "prediction-l3_pending",
                    "collected_at": as_of,
                    "labels": ["GOOD_STYLE"],
                    "raw_feedback_excerpt": "表达自然。",
                    "synthetic": True,
                },
            )
        elif scenario == "case_e_l3_matured_no_feedback":
            maturity = _run(
                root,
                store,
                "pilot-mature",
                {
                    "batch_id": "phase4-pilot-001",
                    "maturity_id": "maturity-lost",
                    "prediction_id": "prediction-l3_pending",
                    "claim_id": "interview",
                    "as_of": as_of,
                    "resolution": "lost_to_followup",
                    "synthetic": True,
                },
            )
            assert maturity["maturity_status"] == "lost_to_followup"
        summary = _run(root, store, "pilot-summary", {"batch_id": "phase4-pilot-001", "as_of": as_of})
        assert summary["registered_real_cases"] == summary["eligible_real_cases"] == 0
        assert summary["candidate_intake"]["candidate_human_total"] == 0
        assert summary["candidate_intake"]["candidate_synthetic_total"] == 1
        assert summary["candidate_intake_integrity"] == "pass"
        assert summary["pilot_screen_integrity"] == "pass"
        assert summary["pilot_slot_integrity"] == "pass"
        assert summary["no_selective_enrollment"] is True
        assert summary["synthetic_real_mix"] is False
        assert summary["commercial_release_hold"] == "ACTIVE"
        assert all(slot["case_id"] is None for slot in summary["real_slots"])
        scenarios.append(
            {
                "scenario": scenario,
                "synthetic": True,
                "registered_real_cases": 0,
                "eligible_real_cases": 0,
                "synthetic_candidate_receipts": 1,
                "candidate_intake_integrity": "pass",
                "status": "passed",
            }
        )
    print(
        json.dumps(
            {
                "scenarios": scenarios,
                "passed": len(scenarios),
                "pilot_target": 10,
                "registered_real_cases": 0,
                "eligible_real_cases": 0,
                "human_candidate_receipts": 0,
                "synthetic_candidate_receipts": len(scenarios),
                "candidate_intake_integrity": "pass",
                "accuracy": None,
                "product_accuracy_claim_allowed": False,
                "commercial_release_hold": "ACTIVE",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
