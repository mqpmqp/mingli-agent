"""Offline synthetic acceptance checks through the existing application CLI."""
from __future__ import annotations

from copy import deepcopy
import io
import json
from unittest.mock import patch

import pytest

from mingli.cli import main
from mingli.training import TrainingStore


AS_OF = "2026-09-13T12:00:00+08:00"
CASE_ID = "person:" + "b" * 64
TEXT = "你在2026年10月可能收到一次岗位面谈安排，结果以正式通知为准。"


def sample():
    claim = {
        "claim_id": "career-interview", "text": TEXT,
        "window": {"text": "2026年10月", "intent": "future"},
        "confidence": 0.5, "basis_id": "fixture-career", "known_fact_ids": [],
    }
    return {
        "synthetic": True, "case_id": CASE_ID, "run_id": "practice-v1",
        "as_of": AS_OF, "recorded_at": AS_OF, "question": "看工作",
        "rule_version": "synthetic-career@1", "known_facts": [],
        "bases": [{
            "basis_id": "fixture-career", "kind": "synthetic_rule_fixture",
            "available_at": AS_OF,
            "supported_claims": [{
                "text": TEXT, "window": deepcopy(claim["window"]),
                "confidence": 0.5, "required_fact_ids": [],
            }],
        }],
        "claims": [claim],
    }


def invoke(tmp_path, capsys, command, payload, *, synthetic=True):
    args = ["training", command, "--input", "-", "--store", str(tmp_path / "store")]
    if synthetic:
        args.append("--synthetic")
    with patch("sys.stdin", io.StringIO(json.dumps(payload, ensure_ascii=False))):
        code = main(args)
    return code, json.loads(capsys.readouterr().out)


def changed_claim(payload, text, window, intent="future"):
    payload["claims"][0]["text"] = text
    payload["claims"][0]["window"] = {"text": window, "intent": intent}
    support = payload["bases"][0]["supported_claims"][0]
    support["text"] = text
    support["window"] = deepcopy(payload["claims"][0]["window"])
    return payload


def feedback(run_id="practice-v1", claim_id="career-interview", record_id="result-1"):
    return {
        "run_id": run_id, "feedback_id": record_id, "claim_id": claim_id,
        "submitted_at": "2026-11-01T12:00:00+08:00", "outcome": "hit",
        "text": "synthetic outcome: 已收到岗位面谈安排",
        "experience": {
            "overall_rating": 4,
            "useful_sections": ["事业"],
            "inaccurate_sections": [],
            "missing_context": [],
            "user_correction": None,
            "clarity_rating": 4,
            "actionability_rating": 4,
            "feedback_kind": "subjective",
        },
    }


def test_entry_rejects_expired_future_window_without_rolling_year(tmp_path, capsys):
    payload = changed_claim(sample(), "你现在到今年五月可能换岗。", "现在到今年五月")
    code, result = invoke(tmp_path, capsys, "practice-run", payload)
    assert code == 2
    assert result["error"]["code"] == "EXPIRED_FUTURE_WINDOW"
    assert "2026-05" in result["error"]["message"]
    assert "2027" not in result["error"]["message"]
    assert not (tmp_path / "store" / "runs").exists()


def test_entry_allows_explicit_history_and_normal_substantive_output(tmp_path, capsys):
    payload = changed_claim(sample(), "回顾2026年5月，你可能经历过一次职责交接。", "回顾2026年5月", "historical")
    code, result = invoke(tmp_path, capsys, "practice-run", payload)
    assert code == 0
    claim = result["data"]["prediction"]["structured_claims"][0]
    assert claim["time_window"]["relation"] == "past"
    assert claim["time_window"]["historical"] is True
    assert claim["time_window"]["start"].startswith("2026-05-01")
    assert claim["time_window"]["end"].startswith("2026-05-31")
    assert claim["visible_cutoff"] == AS_OF
    assert claim["rule_version"] == "synthetic-career@1"
    assert claim["original_text"] == payload["claims"][0]["text"]
    assert "职责交接" in result["data"]["rendered"]["paid"]


@pytest.mark.parametrize("mutation,error", [
    ("no_timezone", "TIMEZONE_REQUIRED"),
    ("no_basis", "MISSING_BASIS"),
    ("post_cutoff_basis", "POST_CUTOFF_INPUT"),
    ("post_cutoff_fact", "POST_CUTOFF_INPUT"),
    ("title", "INPUT_FIELD_NOT_ALLOWED"),
    ("guarantee", "UNSAFE_CLAIM"),
    ("assumed_unemployment", "UNSUPPORTED_EMPLOYMENT_STATE"),
    ("text_window_mismatch", "EXPIRED_FUTURE_WINDOW"),
])
def test_entry_guards(tmp_path, capsys, mutation, error):
    payload = sample()
    if mutation == "no_timezone":
        payload["as_of"] = "2026-09-13T12:00:00"
    elif mutation == "no_basis":
        payload["claims"][0]["basis_id"] = "missing"
    elif mutation == "post_cutoff_basis":
        payload["bases"][0]["available_at"] = "2026-11-01T00:00:00+08:00"
    elif mutation == "post_cutoff_fact":
        payload["known_facts"] = [{"source_id": "late", "text": "已换岗", "available_at": "2026-11-01T00:00:00+08:00"}]
    elif mutation == "title":
        payload["title"] = "结果提示：已换岗"
    elif mutation == "guarantee":
        changed_claim(payload, "你在2026年10月一定升职。", "2026年10月")
    elif mutation == "assumed_unemployment":
        changed_claim(payload, "你失业后在2026年10月可能收到岗位面谈安排。", "2026年10月")
    else:
        payload["claims"][0]["text"] = "你现在到今年五月可能换岗。"
        payload["bases"][0]["supported_claims"][0]["text"] = payload["claims"][0]["text"]
    code, result = invoke(tmp_path, capsys, "practice-run", payload)
    assert code == 2
    assert result["error"]["code"] == error


def test_given_is_context_and_never_independent_hit(tmp_path, capsys):
    payload = sample()
    payload["known_facts"] = [
        {"source_id": "marital", "text": "你已婚", "available_at": AS_OF},
        {"source_id": "employment", "text": "你在职", "available_at": AS_OF},
    ]
    code, result = invoke(tmp_path, capsys, "practice-run", payload)
    assert code == 0
    claims = result["data"]["prediction"]["structured_claims"]
    given = [claim for claim in claims if claim["origin"] == "given"]
    assert len(given) == 2
    assert all(claim["known_fact_ids"] for claim in given)
    code, scored = invoke(tmp_path, capsys, "practice-feedback", feedback(claim_id=given[0]["claim_id"]))
    assert code == 0
    assert scored["data"]["adjudication"]["independent_hit"] is False
    assert scored["data"]["adjudication"]["exclusion_reason"] == "given"


def test_full_entry_loop_preserves_original_and_replay_cannot_read_results(tmp_path, capsys):
    code, original = invoke(tmp_path, capsys, "practice-run", sample())
    assert code == 0
    before = {p.name: p.read_bytes() for p in (tmp_path / "store" / "runs").glob("*.json")}
    code, scored = invoke(tmp_path, capsys, "practice-feedback", feedback())
    assert code == 0
    assert scored["data"]["adjudication"]["independent_hit"] is True
    replay = {"source_run_id": "practice-v1", "run_id": "practice-v2", "rule_version": "synthetic-career@2", "recorded_at": "2026-11-02T12:00:00+08:00"}
    with patch.object(TrainingStore, "show_case", side_effect=AssertionError("replay read feedback")), patch.object(TrainingStore, "_list", side_effect=AssertionError("replay listed results")):
        code, candidate = invoke(tmp_path, capsys, "practice-replay", replay)
    assert code == 0
    assert candidate["data"]["generation_input"]["as_of"] == AS_OF
    assert "synthetic outcome" not in json.dumps(candidate)
    for name, content in before.items():
        assert (tmp_path / "store" / "runs" / name).read_bytes() == content
    assert original["data"]["prediction"]["canonical_hash"] != candidate["data"]["prediction"]["canonical_hash"]
    assert original["data"]["rendered"] == candidate["data"]["rendered"]
    code, comparison = invoke(tmp_path, capsys, "practice-compare", {"baseline_run_id": "practice-v1", "candidate_run_id": "practice-v2", "as_of": "2026-11-03T12:00:00+08:00"})
    assert code == 0
    report = comparison["data"]
    assert report["engineering"]["same_visible_input"] is True
    for field in ("time_consistency", "given_not_scored", "original_snapshot_not_overwritten", "feedback_hidden_from_replay", "normal_flow_completed"):
        assert report["engineering"][field] is True
    assert report["product"]["candidate"]["substantive_claim_count"] == 1
    for version in ("baseline", "candidate"):
        quality = report["product"][version]
        assert quality["answered_current_question"] is True
        assert quality["unsupported_detail_count"] == 0
        assert quality["template_or_vague_phrase_count"] == 0
        assert quality["over_refusal"] is False
        assert quality["manual_rewrite_amount"] is None
    assert report["real_results"]["eligible_sample_count"] == 0
    assert report["real_results"]["accuracy"] is None
    assert report["real_results"]["status"] == "not_evaluated"
    assert report["real_results"]["data_source"] == "none"
    for field in ("due_with_feedback", "not_due", "lost_to_followup", "unverifiable", "refused", "missing"):
        assert report["real_results"][field] == 0
    assert report["synthetic_results"]["baseline"]["independent_hits"] == 1
    assert report["synthetic_results"]["candidate"]["independent_hits"] == 0
    assert report["comparison"]["baseline_prediction_hash"] == original["data"]["prediction"]["canonical_hash"]
    assert report["comparison"]["candidate_prediction_hash"] == candidate["data"]["prediction"]["canonical_hash"]
    assert report["release_hold"] == "ACTIVE"
    assert report["commercial_release_hold"] == "ACTIVE"
    assert report["prediction_validity"] == "not_evaluated"


def test_practice_feedback_appends_existing_feedback_and_outcome_records(tmp_path, capsys):
    invoke(tmp_path, capsys, "practice-run", sample())
    code, result = invoke(tmp_path, capsys, "practice-feedback", feedback())
    assert code == 0
    assert result["data"]["feedback_id"] == "result-1"
    assert result["data"]["outcome_id"] == "result-1"
    feedback_records = list((tmp_path / "store" / "feedback").glob("*.json"))
    outcome_records = list((tmp_path / "store" / "outcomes").glob("*.json"))
    assert len(feedback_records) == 1
    assert len(outcome_records) == 1
    stored = json.loads(feedback_records[0].read_text(encoding="utf-8"))
    assert stored["counts_toward_accuracy"] is False
    assert stored["free_text"] == feedback()["text"]


def test_replay_can_improve_output_without_changing_visible_input_or_reading_feedback(tmp_path, capsys):
    baseline_payload = changed_claim(sample(), "你在2026年10月可能有机会收到岗位面谈安排。", "2026年10月")
    code, baseline = invoke(tmp_path, capsys, "practice-run", baseline_payload)
    assert code == 0
    assert invoke(tmp_path, capsys, "practice-feedback", feedback())[0] == 0

    candidate_payload = sample()
    replay = {
        "source_run_id": "practice-v1",
        "run_id": "practice-v2",
        "rule_version": "synthetic-career@2",
        "recorded_at": "2026-11-02T12:00:00+08:00",
        "bases": candidate_payload["bases"],
        "claims": candidate_payload["claims"],
    }
    code, candidate = invoke(tmp_path, capsys, "practice-replay", replay)
    assert code == 0
    assert candidate["data"]["rendered"] != baseline["data"]["rendered"]
    assert TEXT in candidate["data"]["rendered"]["paid"]
    assert "synthetic outcome" not in json.dumps(candidate)

    code, comparison = invoke(
        tmp_path,
        capsys,
        "practice-compare",
        {
            "baseline_run_id": "practice-v1",
            "candidate_run_id": "practice-v2",
            "as_of": "2026-11-03T12:00:00+08:00",
        },
    )
    assert code == 0
    report = comparison["data"]
    assert report["engineering"]["same_visible_input"] is True
    assert report["engineering"]["feedback_hidden_from_replay"] is True
    assert report["product"]["same_rendered_output"] is False
    improvement = report["product"]["improvement"]
    assert improvement["status"] == "machine_checks_improved"
    assert "template_or_vague_phrase_count" in improvement["improved_checks"]
    assert improvement["regressed_checks"] == []
    assert improvement["human_quality_review"] == "not_evaluated"


def test_replay_rejects_overwrite_same_rule_and_injected_feedback(tmp_path, capsys):
    invoke(tmp_path, capsys, "practice-run", sample())
    replay = {"source_run_id": "practice-v1", "run_id": "practice-v1", "rule_version": "synthetic-career@2", "recorded_at": "2026-11-02T12:00:00+08:00"}
    code, result = invoke(tmp_path, capsys, "practice-replay", replay)
    assert code == 2 and result["error"]["code"] == "DUPLICATE_RECORD"
    replay["run_id"] = "practice-v2"
    replay["rule_version"] = "synthetic-career@1"
    code, result = invoke(tmp_path, capsys, "practice-replay", replay)
    assert code == 2 and result["error"]["code"] == "NEW_RULE_VERSION_REQUIRED"
    replay["feedback"] = "实际上已换岗"
    code, result = invoke(tmp_path, capsys, "practice-replay", replay)
    assert code == 2 and result["error"]["code"] == "INPUT_FIELD_NOT_ALLOWED"


def test_tiers_share_claims_and_never_expand_certainty(tmp_path, capsys):
    code, result = invoke(tmp_path, capsys, "practice-run", sample())
    assert code == 0
    for text in result["data"]["rendered"].values():
        assert TEXT in text
        assert "失业" not in text
        assert text.count("仅供文化研究与娱乐参考。") == 1
        assert text.endswith("仅供文化研究与娱乐参考。")
    # Renderer is the same contract used by the CLI; this isn't a relationship feature.
    from mingli.practice_cycle import render_claims
    claims = [{"claim_id": "contact", "original_text": "存在联系可能", "origin": "inference"}]
    assert "存在联系可能" in render_claims(claims, tier="paid")
    assert "一定" not in render_claims(claims, tier="paid")


def test_synthetic_is_mandatory_and_early_outcome_is_not_a_hit(tmp_path, capsys):
    code, result = invoke(tmp_path, capsys, "practice-run", sample(), synthetic=False)
    assert code == 2 and result["error"]["code"] == "SYNTHETIC_ONLY"
    invoke(tmp_path, capsys, "practice-run", sample())
    event = feedback()
    event["submitted_at"] = "2026-09-14T00:00:00+08:00"
    code, result = invoke(tmp_path, capsys, "practice-feedback", event)
    assert code == 0
    assert result["data"]["adjudication"]["independent_hit"] is False
    assert result["data"]["adjudication"]["exclusion_reason"] == "not_due"


def test_given_paraphrase_cannot_be_scored_as_an_independent_claim(tmp_path, capsys):
    payload = changed_claim(sample(), "你可能已经在职。", "2026-09-13", "present")
    payload["known_facts"] = [{"source_id": "employment", "text": "我在职", "available_at": AS_OF}]
    payload["claims"][0]["known_fact_ids"] = ["employment"]
    code, result = invoke(tmp_path, capsys, "practice-run", payload)
    assert code == 2 and result["error"]["code"] == "NO_SUPPORTED_CLAIMS"


@pytest.mark.parametrize("expression", ["明年五月", "明年5月", "五月", "下个月"])
def test_unparsed_time_in_original_is_rejected(tmp_path, capsys, expression):
    payload = changed_claim(sample(), f"你在{expression}可能换岗。", "2026年10月")
    code, result = invoke(tmp_path, capsys, "practice-run", payload)
    assert code == 2 and result["error"]["code"] == "UNSUPPORTED_TIME_EXPRESSION"


def test_conflicting_feedback_is_not_cherry_picked_or_double_counted(tmp_path, capsys):
    invoke(tmp_path, capsys, "practice-run", sample())
    invoke(tmp_path, capsys, "practice-feedback", feedback())
    second = feedback(record_id="result-2")
    second["outcome"] = "miss"
    invoke(tmp_path, capsys, "practice-feedback", second)
    code, report = invoke(tmp_path, capsys, "practice-compare", {"baseline_run_id": "practice-v1", "candidate_run_id": "practice-v1", "as_of": "2026-11-03T12:00:00+08:00"})
    assert code == 0
    score = report["data"]["synthetic_results"]["baseline"]
    assert score["conflicting_feedback"] == 1
    assert score["independent_hits"] == 0
    assert score["evaluated"] == 0


def test_existing_case_cannot_replace_visible_sources_by_starting_another_run(tmp_path, capsys):
    invoke(tmp_path, capsys, "practice-run", sample())
    invoke(tmp_path, capsys, "practice-feedback", feedback())
    payload = sample()
    payload["run_id"] = "practice-v2"
    payload["rule_version"] = "synthetic-career@2"
    payload["known_facts"] = [{"source_id": "backdated-result", "text": "已换岗", "available_at": AS_OF}]
    code, result = invoke(tmp_path, capsys, "practice-run", payload)
    assert code == 2 and result["error"]["code"] == "FROZEN_CASE_INPUT"


def test_feedback_is_append_only_and_original_adjudication_survives_replay(tmp_path, capsys):
    invoke(tmp_path, capsys, "practice-run", sample())
    invoke(tmp_path, capsys, "practice-feedback", feedback())
    before = {p.name: p.read_bytes() for p in (tmp_path / "store" / "outcomes").glob("*.json")}
    changed = feedback()
    changed["outcome"] = "miss"
    code, result = invoke(tmp_path, capsys, "practice-feedback", changed)
    assert code == 2 and result["error"]["code"] == "DUPLICATE_RECORD"
    invoke(tmp_path, capsys, "practice-replay", {"source_run_id": "practice-v1", "run_id": "practice-v2", "rule_version": "synthetic-career@2", "recorded_at": "2026-11-02T12:00:00+08:00"})
    assert before == {p.name: p.read_bytes() for p in (tmp_path / "store" / "outcomes").glob("*.json")}


@pytest.mark.parametrize("qualification", [
    "但并不一定录取。", "这不能保证上岸。", "不要把“你一定升职”当作承诺。",
])
def test_negated_or_rejected_quoted_promise_is_not_a_promise(tmp_path, capsys, qualification):
    payload = changed_claim(sample(), "你在2026年10月可能收到岗位面谈安排，" + qualification, "2026年10月")
    code, result = invoke(tmp_path, capsys, "practice-run", payload)
    assert code == 0
    assert qualification in result["data"]["rendered"]["paid"]
    assert result["data"]["prediction"]["source_commit_sha"] == "0" * 40
    assert result["data"]["provenance"]["source_commit_attested"] is False


def test_negated_clause_does_not_hide_a_separate_positive_promise(tmp_path, capsys):
    payload = changed_claim(sample(), "你在2026年10月可能收到面谈安排，不一定落选，你一定升职。", "2026年10月")
    code, result = invoke(tmp_path, capsys, "practice-run", payload)
    assert code == 2 and result["error"]["code"] == "UNSAFE_CLAIM"
