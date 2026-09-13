"""Run five explicitly synthetic acceptance cases through actual CLI processes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 五组 synthetic CLI 验收")
    parser.add_argument("--store", type=Path, required=True, help="不存在的工作区内临时目录")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    target = args.store.resolve()
    if target.exists() or root not in target.parents:
        parser.error("store 必须是工作区内尚不存在的专用临时目录")
    results = []
    for name in ("l2_hit", "l2_miss", "l3_pending", "given_leakage", "expired_window"):
        sample = json.loads(Path(__file__).with_name(name + ".json").read_text(encoding="utf-8"))
        if sample["synthetic"] is not True:
            raise ValueError("只允许明确标记 synthetic 的验收样例")
        codes, summary, pilot = [], None, None
        for step in sample["steps"]:
            completed = subprocess.run(
                [sys.executable, "-X", "utf8", "-m", "mingli.training_cli", step["command"], "--input", "-",
                 "--store", str(target / name), "--repository-root", str(root), "--synthetic", "--json"],
                input=json.dumps(step["input"], ensure_ascii=True), text=True, capture_output=True,
                encoding="utf-8", errors="replace", cwd=root, timeout=30, check=False,
            )
            codes.append(completed.returncode)
            if completed.returncode != step["expected_exit"]:
                raise AssertionError(f"{name}/{step['command']}: exit={completed.returncode}; {completed.stdout}; {completed.stderr}")
            envelope = json.loads(completed.stdout)
            if step.get("expected_error"):
                assert envelope["error"]["code"] == step["expected_error"]
            if step["command"] == "validation-summary":
                summary = envelope["data"]
            if step["command"] == "pilot-show":
                pilot = envelope["data"]
        assert summary is not None and pilot is not None
        counts = summary["pools"][sample["expected_pool"]]["synthetic_claim_counts"]
        if sample["expected_result"] == "blocked":
            assert sum(counts.values()) == 0
        else:
            assert counts[sample["expected_result"]] == 1
        assert summary["eligible_sample_count"] == pilot["registered_cases"] == pilot["eligible_sample_count"] == 0
        assert summary["accuracy"] is summary["metrics"] is pilot["accuracy"] is pilot["metrics"] is None
        assert pilot["commercial_release_hold"] == "ACTIVE"
        assert summary["l0_synthetic_count"] == summary["cases"]["l0_synthetic"] == 1
        for metric in ("l1_historical_count", "l2_retrospective_count", "l3_prospective_count", "prospective_pending_count"):
            assert summary[metric] == 0
        assert summary["public_accuracy_claim_allowed"] is False
        assert summary["cases"]["total"] == 1 and summary["cases"]["real_registered_cases"] == 0
        assert summary["retrospective_validation"]["total_cases"] == summary["prospective_validation"]["total_cases"] == 0
        assert "overall_accuracy" not in summary
        results.append({"example_id": name, "synthetic": True, "step_exit_codes": codes,
                        "result": sample["expected_result"], "passed": True})
    print(json.dumps({"examples": results, "passed": len(results), "registered_cases": 0,
                      "l0_synthetic_count": len(results), "l1_historical_count": 0, "l2_retrospective_count": 0,
                      "l3_prospective_count": 0, "prospective_pending_count": 0,
                      "eligible_sample_count": 0, "accuracy": None, "metrics": None, "public_accuracy_claim_allowed": False,
                      "status": "not_evaluated", "commercial_release_hold": "ACTIVE"}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
