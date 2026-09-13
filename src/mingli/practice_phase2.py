"""Phase 2 synthetic product-quality checks on top of the frozen Phase 1 runs.

Human review and behavioral regression are product engineering evidence only.
Prospective case qualification reuses ``real_case_learning_v2`` and never turns
synthetic fixtures or unreviewed observations into prediction accuracy.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Mapping, Sequence, cast

from .contracts.serialization import digest
from .practice_cycle import _run, _safe, parse_window, render_claims
from .real_case_learning_v2 import (
    COMMERCIAL_RELEASE_HOLD,
    RealCaseLearningV2Error,
    summarize_learning_cases,
)
from .training import TrainingError, TrainingStore
from .validation_privacy import scan_for_pii


VERSION = "practice-to-product-phase2@1"
PHASE2_COMMANDS = {
    "review-create",
    "review-show",
    "review-submit",
    "review-summary",
    "behavior-regression",
    "real-case-qualify",
}
ERROR_FAMILIES = {
    "time_reference_error",
    "given_leakage_or_given_scoring",
    "career_template_reuse",
    "relationship_overclaim",
    "comment_output_vagueness",
    "paid_output_hallucinated_detail",
}
_SOURCE_TYPES = {
    "historical_chat_original",
    "historical_summary_only",
    "synthetic_from_known_failure_pattern",
}
_PREFERENCE_FIELDS = (
    "overall_preference",
    "answers_user_question",
    "specificity_without_overreach",
    "time_window_clarity",
    "human_master_style",
)
_RISK_FIELDS = ("unsupported_detail_risk", "template_or_generic_language")
_RESULT_KEYS = (
    "hit",
    "partial",
    "miss",
    "unverifiable",
    "pending",
    "lost_to_followup",
    "refused",
    "missing",
)
PROSPECTIVE_QUALIFICATION_CONTRACT = {
    "record_source": "real_case_learning_v2",
    "case_schema": "real_case_learning_v2_case.schema.json",
    "prediction_freeze": "validation_freeze.freeze_prediction",
    "feedback_append": "real_case_learning_v2.record_future_outcome",
    "privacy_gate": "validation_privacy.scan_for_pii",
    "dataset_boundary": "real_case_learning_v2 temporal partition dependencies",
    "fact_interpretation_boundary": {
        "fact": "future_outcomes[].evidence_snapshot",
        "interpretation": "adjudications[]",
    },
    "outcome_time_fields": {
        "event_window": "frozen claim window",
        "observed_at": "event observed or received time",
        "collected_at": "evidence recorded time",
    },
    "outcome_statuses": list(_RESULT_KEYS),
    "accuracy_default": {
        "eligible_sample_count": 0,
        "accuracy": None,
        "metrics": None,
        "status": "not_evaluated",
    },
}


def _fail(code: str, message: str) -> None:
    raise TrainingError(code, message)


def _closed(
    value: object,
    required: set[str],
    *,
    label: str,
    optional: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("SCHEMA_INCOMPATIBLE", f"{label} must be an object")
    allowed = required | (optional or set())
    if set(value) - allowed:
        _fail("INPUT_FIELD_NOT_ALLOWED", f"{label} contains fields outside the closed contract")
    missing = required - set(value)
    if missing:
        _fail("SCHEMA_INCOMPATIBLE", f"{label} is missing: {','.join(sorted(missing))}")
    return cast(dict[str, Any], json.loads(json.dumps(value, ensure_ascii=False)))


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 8_000:
        _fail("SCHEMA_INCOMPATIBLE", f"{field} must be non-empty bounded text")
    return value


def _time(value: object, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrainingError("INVALID_TIME", f"{field} must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        _fail("TIMEZONE_REQUIRED", f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _public_packet(packet: Mapping[str, object]) -> dict[str, object]:
    """Return only what a reviewer may see; assignment/provenance stay sealed."""

    return {
        "schema_version": VERSION,
        "review_id": packet["review_id"],
        "comparison_id": packet["comparison_id"],
        "created_at": packet["created_at"],
        "tier": packet["tier"],
        "visible_input": packet["visible_input"],
        "answers": packet["answers"],
        "randomization": {
            "method": "seeded_permutation",
            "identity_disclosed": False,
        },
        "human_review_status": "not_evaluated",
        "accuracy_eligible": False,
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
    }


def create_blind_review(
    payload: Mapping[str, object], store: TrainingStore
) -> dict[str, object]:
    data = _closed(
        payload,
        {
            "review_id",
            "comparison_id",
            "baseline_run_id",
            "candidate_run_id",
            "tier",
            "created_at",
            "randomization_seed",
        },
        label="review-create",
    )
    for field in (
        "review_id",
        "comparison_id",
        "baseline_run_id",
        "candidate_run_id",
        "randomization_seed",
    ):
        _text(data[field], field)
    if data["tier"] not in {"comment", "paid"}:
        _fail("INVALID_TIER", "tier must be comment or paid")
    created = _time(data["created_at"], "created_at")
    baseline = _run(store, data["baseline_run_id"])
    candidate = _run(store, data["candidate_run_id"])
    if baseline["case_id"] != candidate["case_id"]:
        _fail("INCOMPARABLE_INPUT", "blind review requires the same synthetic case")
    baseline_result = baseline["result"]
    candidate_result = candidate["result"]
    if baseline_result["visible_input_hash"] != candidate_result["visible_input_hash"]:
        _fail("INCOMPARABLE_INPUT", "blind review requires the same frozen visible input")
    if any(_time(run["created_at"], "run.created_at") > created for run in (baseline, candidate)):
        _fail("INVALID_CHRONOLOGY", "review packet cannot predate either frozen answer")

    seed_hash = digest(
        {
            "comparison_id": data["comparison_id"],
            "review_id": data["review_id"],
            "randomization_seed": data["randomization_seed"],
        }
    )
    source = {
        "baseline": {
            "run": baseline,
            "answer_id": "answer:" + digest(
                {"review_id": data["review_id"], "run_id": baseline["run_id"], "seed": seed_hash}
            )[7:31],
        },
        "candidate": {
            "run": candidate,
            "answer_id": "answer:" + digest(
                {"review_id": data["review_id"], "run_id": candidate["run_id"], "seed": seed_hash}
            )[7:31],
        },
    }
    roles = ["candidate", "baseline"] if int(seed_hash[7:9], 16) % 2 else ["baseline", "candidate"]
    answers = [
        {
            "label": label,
            "answer_id": source[role]["answer_id"],
            "text": source[role]["run"]["result"]["rendered"][data["tier"]],
        }
        for label, role in zip(("A", "B"), roles, strict=True)
    ]
    generation_input = baseline_result["generation_input"]
    packet = {
        "review_id": data["review_id"],
        "comparison_id": data["comparison_id"],
        "created_at": data["created_at"],
        "tier": data["tier"],
        "visible_input": {
            "question": generation_input["question"],
            "as_of": generation_input["as_of"],
            "given_facts": [item["text"] for item in generation_input["known_facts"]],
            "visible_input_hash": baseline_result["visible_input_hash"],
        },
        "answers": answers,
        "assignment": {
            "baseline_answer_id": source["baseline"]["answer_id"],
            "candidate_answer_id": source["candidate"]["answer_id"],
        },
        "source_snapshots": {
            "baseline_run_id": baseline["run_id"],
            "candidate_run_id": candidate["run_id"],
            "baseline_answer_id": source["baseline"]["answer_id"],
            "candidate_answer_id": source["candidate"]["answer_id"],
            "baseline_prediction_hash": baseline_result["prediction"]["canonical_hash"],
            "candidate_prediction_hash": candidate_result["prediction"]["canonical_hash"],
        },
        "randomization": {
            "method": "sha256_seeded_permutation",
            "seed_hash": seed_hash,
        },
        "synthetic": True,
        "accuracy_eligible": False,
        "human_review_status": "not_evaluated",
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
    }
    return _public_packet(store.create_review_packet(packet))


def show_blind_review(review_id: str, store: TrainingStore) -> dict[str, object]:
    return _public_packet(store.review_packet(_text(review_id, "review_id")))


def submit_blind_review(
    payload: Mapping[str, object], store: TrainingStore
) -> dict[str, object]:
    data = _closed(
        payload,
        {
            "review_submission_id",
            "review_id",
            "reviewer_id",
            "submitted_at",
            "overall_preference",
            "answers_user_question",
            "specificity_without_overreach",
            "time_window_clarity",
            "unsupported_detail_risk",
            "template_or_generic_language",
            "human_master_style",
            "requires_manual_rewrite",
        },
        label="review-submit",
        optional={"note"},
    )
    for field in ("review_submission_id", "review_id", "reviewer_id"):
        _text(data[field], field)
    packet = store.review_packet(data["review_id"])
    if _time(data["submitted_at"], "submitted_at") < _time(packet["created_at"], "packet.created_at"):
        _fail("INVALID_CHRONOLOGY", "review submission cannot predate its packet")
    for field in _PREFERENCE_FIELDS:
        allowed = {"A", "B", "tie", "neither"}
        if field == "time_window_clarity":
            allowed.add("not_applicable")
        if data[field] not in allowed:
            _fail("INVALID_REVIEW_CHOICE", f"invalid {field} choice")
    for field in _RISK_FIELDS:
        if data[field] not in {"A_lower", "B_lower", "tie"}:
            _fail("INVALID_REVIEW_CHOICE", f"invalid {field} choice")
    if data["requires_manual_rewrite"] not in {"A", "B", "both", "neither"}:
        _fail("INVALID_REVIEW_CHOICE", "invalid requires_manual_rewrite choice")
    note = data.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > 2_000):
        _fail("SCHEMA_INCOMPATIBLE", "note must be null or bounded text")
    saved = store.add_human_review(
        {
            **data,
            "note": note,
            "synthetic": True,
            "accuracy_eligible": False,
            "status": "recorded",
            "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
        }
    )
    return {
        "schema_version": VERSION,
        "review_submission_id": saved["review_submission_id"],
        "review_id": saved["review_id"],
        "status": "recorded",
        "accuracy_eligible": False,
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
    }


def _role_for_choice(packet: Mapping[str, object], choice: str) -> str:
    if choice in {"tie", "neither", "not_applicable"}:
        return choice
    label = choice.removesuffix("_lower")
    answer = next(
        item for item in cast(Sequence[Mapping[str, object]], packet["answers"])
        if item["label"] == label
    )
    assignment = cast(Mapping[str, object], packet["assignment"])
    if answer["answer_id"] == assignment["candidate_answer_id"]:
        return "candidate"
    return "baseline"


def _empty_dimension() -> dict[str, int]:
    return {
        "baseline_wins": 0,
        "candidate_wins": 0,
        "ties": 0,
        "neither": 0,
        "not_applicable": 0,
    }


def summarize_blind_reviews(
    store: TrainingStore, *, review_id: str | None = None
) -> dict[str, object]:
    packets = [store._validate("review_packet", item) for item in store._list("review_packet")]
    if review_id is not None:
        packets = [item for item in packets if item["review_id"] == review_id]
    packet_by_id = {str(item["review_id"]): item for item in packets}
    reviews = [
        item
        for item in store.human_reviews(review_id=review_id)
        if str(item["review_id"]) in packet_by_id
    ]
    totals = {"baseline_wins": 0, "candidate_wins": 0, "ties": 0, "neither": 0}
    dimensions = {field: _empty_dimension() for field in (*_PREFERENCE_FIELDS[1:], *_RISK_FIELDS)}
    manual = {
        "candidate_required": 0,
        "baseline_required": 0,
        "both": 0,
        "neither": 0,
        "candidate_rate": None,
        "baseline_rate": None,
    }
    mapped_overall: dict[str, list[str]] = {}
    for review in reviews:
        packet = packet_by_id[str(review["review_id"])]
        overall = _role_for_choice(packet, str(review["overall_preference"]))
        total_key = {
            "candidate": "candidate_wins",
            "baseline": "baseline_wins",
            "tie": "ties",
            "neither": "neither",
        }[overall]
        totals[total_key] += 1
        mapped_overall.setdefault(str(review["review_id"]), []).append(overall)
        for field in dimensions:
            mapped = _role_for_choice(packet, str(review[field]))
            key = f"{mapped}_wins" if mapped in {"candidate", "baseline"} else (
                "ties" if mapped == "tie" else mapped
            )
            dimensions[field][key] += 1
        rewrite = str(review["requires_manual_rewrite"])
        if rewrite == "both":
            manual["both"] += 1
            manual["candidate_required"] += 1
            manual["baseline_required"] += 1
        elif rewrite == "neither":
            manual["neither"] += 1
        else:
            role = _role_for_choice(packet, rewrite)
            manual[f"{role}_required"] += 1
    if reviews:
        manual["candidate_rate"] = manual["candidate_required"] / len(reviews)
        manual["baseline_rate"] = manual["baseline_required"] / len(reviews)

    per_comparison: list[dict[str, object]] = []
    multi_count = 0
    agreed_count = 0
    for packet_id, packet in packet_by_id.items():
        choices = mapped_overall.get(packet_id, [])
        if not choices:
            status = "not_evaluated"
        elif len(choices) == 1:
            status = "single_reviewer"
        else:
            multi_count += 1
            agreed = len(set(choices)) == 1
            agreed_count += int(agreed)
            status = "multi_reviewer_agreement" if agreed else "multi_reviewer_disagreement"
        per_comparison.append(
            {
                "review_id": packet_id,
                "comparison_id": packet["comparison_id"],
                "review_count": len(choices),
                "status": status,
            }
        )
    if not reviews:
        agreement_status = "not_evaluated"
    elif multi_count == 0:
        agreement_status = "single_reviewer"
    elif agreed_count == multi_count:
        agreement_status = "multi_reviewer_agreement"
    else:
        agreement_status = "multi_reviewer_disagreement"
    return {
        "schema_version": VERSION,
        "packet_count": len(packets),
        "review_count": len(reviews),
        "totals": totals,
        "per_dimension": dimensions,
        "manual_rewrite": manual,
        "reviewer_agreement": {
            "status": agreement_status,
            "multi_reviewer_comparison_count": multi_count,
            "agreed_comparison_count": agreed_count,
            "agreement_rate": agreed_count / multi_count if multi_count else None,
            "per_comparison": per_comparison,
        },
        "accuracy_eligible": False,
        "real_results": {
            "eligible_sample_count": 0,
            "accuracy": None,
            "metrics": None,
            "status": "not_evaluated",
        },
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
    }


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("SCHEMA_INCOMPATIBLE", f"{field} must be an object")
    return cast(dict[str, Any], value)


def _evaluate_behavior(family: str, fixture: Mapping[str, object]) -> dict[str, str]:
    if family == "time_reference_error":
        try:
            parse_window(
                _mapping(fixture.get("window"), "fixture.window"),
                as_of=_text(fixture.get("as_of"), "fixture.as_of"),
            )
        except TrainingError as exc:
            return {"gate": "blocked", "code": exc.code}
        return {"gate": "allowed", "code": "TIME_REFERENCE_VALID"}
    if family == "given_leakage_or_given_scoring":
        blocked = (
            fixture.get("origin") == "given"
            and (
                fixture.get("independent_prediction_eligible") is not False
                or fixture.get("rendered_as_prediction") is True
            )
        ) or fixture.get("reality_evidence_visibility") is True
        return {
            "gate": "blocked" if blocked else "allowed",
            "code": "GIVEN_LEAKAGE_BLOCKED" if blocked else "GIVEN_ISOLATED",
        }
    if family == "career_template_reuse":
        answer = _text(fixture.get("answer"), "fixture.answer")
        vague = any(phrase in answer for phrase in ("有机会", "会变化", "压力大", "注意沟通", "慢慢稳定"))
        concrete_event = re.search(r"面谈|录取|岗位|职责|交接|换岗|升职", answer) is not None
        concrete_time = re.search(r"\d{4}年\d{1,2}月|\d{4}-\d{2}-\d{2}", answer) is not None
        blocked = vague and not (concrete_event and concrete_time)
        return {
            "gate": "blocked" if blocked else "allowed",
            "code": "CAREER_TEMPLATE_BLOCKED" if blocked else "CAREER_ANSWER_SPECIFIC",
        }
    if family == "relationship_overclaim":
        answer = _text(fixture.get("answer"), "fixture.answer")
        try:
            _safe(answer)
        except TrainingError as exc:
            return {"gate": "blocked", "code": exc.code}
        return {"gate": "allowed", "code": "RELATIONSHIP_CLAIM_BOUNDED"}
    if family == "comment_output_vagueness":
        answer = _text(fixture.get("answer"), "fixture.answer")
        vague = any(phrase in answer for phrase in ("有机会", "会变化", "压力大", "注意沟通", "慢慢稳定"))
        concrete = (
            re.search(r"\d{4}年\d{1,2}月|\d{4}-\d{2}-\d{2}", answer) is not None
            and re.search(r"面谈|联系|见面|岗位|录取|结果", answer) is not None
        )
        blocked = vague and not concrete
        return {
            "gate": "blocked" if blocked else "allowed",
            "code": "COMMENT_VAGUENESS_BLOCKED" if blocked else "COMMENT_HAS_VERIFIABLE_POINT",
        }
    if family == "paid_output_hallucinated_detail":
        claims = fixture.get("structured_claims")
        if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
            _fail("SCHEMA_INCOMPATIBLE", "fixture.structured_claims must be an array")
        expected = render_claims(cast(Sequence[Mapping[str, Any]], claims), tier="paid")
        blocked = fixture.get("rendered") != expected
        return {
            "gate": "blocked" if blocked else "allowed",
            "code": "PAID_UNSUPPORTED_DETAIL_BLOCKED" if blocked else "PAID_OUTPUT_CLAIM_BOUND",
        }
    _fail("UNKNOWN_ERROR_FAMILY", f"unsupported behavioral family: {family}")
    raise AssertionError("unreachable")


def run_behavioral_regression(payload: Mapping[str, object]) -> dict[str, object]:
    data = _closed(
        payload,
        {"schema_version", "cases", "comparisons"},
        label="behavior-regression",
    )
    if not isinstance(data["cases"], list) or not isinstance(data["comparisons"], list):
        _fail("SCHEMA_INCOMPATIBLE", "cases and comparisons must be arrays")
    rows: list[dict[str, object]] = []
    families: set[str] = set()
    for raw in data["cases"]:
        case = _closed(
            raw,
            {
                "regression_case_id",
                "error_family",
                "source_type",
                "source_date",
                "source_reference",
                "known_bad_behavior",
                "expected_behavior",
                "expected_gate",
                "fixture",
                "accuracy_eligible",
            },
            label="behavior case",
            optional={"original_input"},
        )
        family = _text(case["error_family"], "error_family")
        for field in (
            "regression_case_id",
            "source_date",
            "source_reference",
            "known_bad_behavior",
            "expected_behavior",
        ):
            _text(case[field], field)
        if family not in ERROR_FAMILIES:
            _fail("UNKNOWN_ERROR_FAMILY", f"unsupported behavioral family: {family}")
        if case["source_type"] not in _SOURCE_TYPES:
            _fail("INVALID_SOURCE_TYPE", "behavior case source_type is not allowed")
        if case["source_type"] == "historical_chat_original" and not isinstance(
            case.get("original_input"), Mapping
        ):
            _fail(
                "ORIGINAL_INPUT_REQUIRED",
                "historical_chat_original cases must preserve the original input object",
            )
        if case["accuracy_eligible"] is not False:
            _fail(
                "BEHAVIOR_NOT_ACCURACY_EVIDENCE",
                "behavior regression is never eligible for real prediction accuracy",
            )
        if case["expected_gate"] not in {"blocked", "allowed"}:
            _fail("SCHEMA_INCOMPATIBLE", "expected_gate must be blocked or allowed")
        actual = _evaluate_behavior(family, _mapping(case["fixture"], "fixture"))
        rows.append(
            {
                **{key: case[key] for key in (
                    "regression_case_id",
                    "error_family",
                    "source_type",
                    "source_date",
                    "source_reference",
                    "known_bad_behavior",
                    "expected_behavior",
                )},
                "expected_gate": case["expected_gate"],
                "actual_gate": actual["gate"],
                "code": actual["code"],
                "passed": actual["gate"] == case["expected_gate"],
                "accuracy_eligible": False,
            }
        )
        families.add(family)
    if families != ERROR_FAMILIES:
        _fail("INCOMPLETE_REGRESSION_FAMILIES", "all six Phase 2 error families are required")
    by_family: dict[str, dict[str, int]] = {}
    for family in sorted(ERROR_FAMILIES):
        selected = [row for row in rows if row["error_family"] == family]
        by_family[family] = {
            "total": len(selected),
            "passed": sum(row["passed"] is True for row in selected),
            "failed": sum(row["passed"] is False for row in selected),
            "blocked_cases": sum(row["actual_gate"] == "blocked" for row in selected),
            "allowed_cases": sum(row["actual_gate"] == "allowed" for row in selected),
        }
    if any(values["blocked_cases"] < 1 for values in by_family.values()):
        _fail("MISSING_NEGATIVE_CASE", "every behavior family needs at least one blocked case")
    if sum(values["allowed_cases"] > 0 for values in by_family.values()) < 4:
        _fail("OVER_REFUSAL_REGRESSION_SET", "at least four behavior families need a normal allowed case")

    comparisons: list[dict[str, object]] = []
    for raw in data["comparisons"]:
        comparison = _closed(
            raw,
            {"comparison_id", "error_family", "fixed_input", "baseline", "candidate"},
            label="behavior comparison",
        )
        family = _text(comparison["error_family"], "comparison.error_family")
        if family not in ERROR_FAMILIES:
            _fail("UNKNOWN_ERROR_FAMILY", f"unsupported behavioral family: {family}")
        rendered: dict[str, object] = {}
        for role in ("baseline", "candidate"):
            side = _closed(
                comparison[role], {"output", "fixture"}, label=f"comparison.{role}"
            )
            _text(side["output"], f"comparison.{role}.output")
            verdict = _evaluate_behavior(family, _mapping(side["fixture"], "fixture"))
            rendered[role] = {"output": side["output"], **verdict}
        comparisons.append(
            {
                "comparison_id": comparison["comparison_id"],
                "error_family": family,
                "fixed_input": comparison["fixed_input"],
                **rendered,
                "machine_verdict": (
                    "candidate_improved"
                    if rendered["baseline"]["gate"] == "blocked"
                    and rendered["candidate"]["gate"] == "allowed"
                    else "improvement_not_established"
                ),
                "human_review_status": "not_evaluated",
                "accuracy_eligible": False,
            }
        )
    if len(comparisons) != 3:
        _fail("COMPARISON_SET_INCOMPLETE", "exactly three Phase 2 before/after comparisons are required")
    comparison_families = {str(item["error_family"]) for item in comparisons}
    if not {"time_reference_error", "career_template_reuse"} <= comparison_families or not comparison_families.intersection(
        {"relationship_overclaim", "paid_output_hallucinated_detail"}
    ):
        _fail(
            "COMPARISON_SET_INCOMPLETE",
            "comparisons must cover time, career, and relationship overclaim or paid-detail risk",
        )
    passed = sum(row["passed"] is True for row in rows)
    return {
        "schema_version": VERSION,
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "by_error_family": by_family,
        "cases": rows,
        "comparisons": comparisons,
        "accuracy_eligible": False,
        "real_results": {
            "eligible_sample_count": 0,
            "accuracy": None,
            "metrics": None,
            "status": "not_evaluated",
        },
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
    }


def _try_time(value: object) -> datetime | None:
    try:
        return _time(value, "timestamp")
    except TrainingError:
        return None


def _try_window(value: object) -> tuple[datetime, datetime] | None:
    if not isinstance(value, str) or value.count("/") != 1:
        return None
    start, end = value.split("/", 1)
    parsed = (_try_time(start), _try_time(end))
    if parsed[0] is None or parsed[1] is None or parsed[1] < parsed[0]:
        return None
    return cast(tuple[datetime, datetime], parsed)


def qualify_prospective_case(
    case: Mapping[str, object], *, evaluated_at: str
) -> dict[str, object]:
    now = _time(evaluated_at, "evaluated_at")
    prediction = case.get("prediction_snapshot")
    prediction_map = prediction if isinstance(prediction, Mapping) else {}
    intake = case.get("intake_snapshot")
    intake_map = intake if isinstance(intake, Mapping) else {}
    consent = case.get("consent")
    consent_map = consent if isinstance(consent, Mapping) else {}
    reality = case.get("prediction_time_reality_snapshot")
    reality_map = reality if isinstance(reality, Mapping) else {}
    question = case.get("original_question_snapshot")
    question_map = question if isinstance(question, Mapping) else {}
    claims_value = prediction_map.get("structured_claims")
    claims = [item for item in claims_value if isinstance(item, Mapping)] if isinstance(claims_value, list) else []
    outcomes_value = case.get("future_outcomes")
    outcomes = [item for item in outcomes_value if isinstance(item, Mapping)] if isinstance(outcomes_value, list) else []
    adjudications_value = case.get("adjudications")
    adjudications = [item for item in adjudications_value if isinstance(item, Mapping)] if isinstance(adjudications_value, list) else []
    try:
        summarize_learning_cases([case])
        v2_valid = True
    except (RealCaseLearningV2Error, KeyError, TypeError, ValueError):
        v2_valid = False

    freeze_time = _try_time(prediction_map.get("freeze_timestamp"))
    feedback_times_valid = bool(outcomes) and freeze_time is not None
    if outcomes and freeze_time is not None:
        feedback_times_valid = all(
            _try_time(item.get("observed_at")) is not None
            and _try_time(item.get("collected_at")) is not None
            and cast(datetime, _try_time(item.get("observed_at"))) > freeze_time
            and cast(datetime, _try_time(item.get("collected_at")))
            >= cast(datetime, _try_time(item.get("observed_at")))
            for item in outcomes
        )
    feedback_traceable = bool(outcomes) and all(
        item.get("evidence_id")
        and item.get("claim_id")
        and item.get("observed_at")
        and item.get("collected_at")
        and isinstance(item.get("evidence_snapshot"), Mapping)
        and cast(Mapping[str, object], item["evidence_snapshot"]).get("source_provenance")
        for item in outcomes
    )
    identifiers = [
        case.get("case_id"),
        case.get("person_case_id"),
        case.get("scenario_id"),
        prediction_map.get("prediction_id"),
        *(item.get("claim_id") for item in claims),
    ]
    metadata = intake_map.get("case_metadata")
    metadata_map = metadata if isinstance(metadata, Mapping) else {}
    checks = {
        "existing_v2_contract_valid": v2_valid,
        "consent_granted": consent_map.get("status") == "granted"
        and consent_map.get("research_use_allowed") is True
        and consent_map.get("benchmark_use_allowed") is True
        and consent_map.get("withdrawal_supported") is True,
        "deidentified": re.fullmatch(r"person:[0-9a-f]{64}", str(case.get("person_case_id", "")))
        is not None
        and not scan_for_pii(case),
        "stable_case_person_prediction_claim_ids": bool(claims)
        and all(isinstance(item, str) and item for item in identifiers)
        and len({str(item.get("claim_id")) for item in claims}) == len(claims),
        "verifiable_input_time": _try_time(metadata_map.get("created_at")) is not None
        and _try_time(reality_map.get("known_at")) is not None,
        "original_question_frozen": bool(question_map.get("text"))
        and question_map.get("freeze_status") == "frozen",
        "given_facts_isolated": reality_map.get("freeze_status") == "frozen"
        and prediction_map.get("reality_evidence_visibility") is False,
        "as_of_present": _try_time(reality_map.get("known_at")) is not None,
        "frozen_prediction_present": prediction_map.get("freeze_status") == "frozen"
        and freeze_time is not None,
        "structured_and_rendered_prediction_stored": bool(claims)
        and bool(prediction_map.get("prediction_content")),
        "feedback_timestamped_and_traceable": feedback_traceable,
        "feedback_after_freeze": feedback_times_valid,
        "due_window_or_event_defined": bool(claims)
        and all(_try_window(item.get("time_window")) is not None for item in claims),
        "no_result_backfill": not outcomes or feedback_times_valid,
    }
    outcome_counts = {key: 0 for key in _RESULT_KEYS}
    claim_statuses: list[dict[str, object]] = []
    for claim in claims:
        claim_id = str(claim.get("claim_id", ""))
        matching_outcomes = [item for item in outcomes if item.get("claim_id") == claim_id]
        matching_reviews = [item for item in adjudications if item.get("claim_id") == claim_id]
        window = _try_window(claim.get("time_window"))
        if matching_reviews and matching_reviews[-1].get("status") in {"hit", "partial", "miss", "unverifiable"}:
            status = str(matching_reviews[-1]["status"])
        elif matching_outcomes:
            status = "unverifiable"
        elif window is not None and now <= window[1]:
            status = "pending"
        else:
            status = "missing"
        outcome_counts[status] += 1
        claim_statuses.append(
            {
                "claim_id": claim_id,
                "status": status,
                "observation_count": len(matching_outcomes),
                "adjudication_count": len(matching_reviews),
            }
        )
    structural_checks = [
        value for key, value in checks.items()
        if key not in {"feedback_timestamped_and_traceable", "feedback_after_freeze"}
    ]
    terminal = outcome_counts["hit"] + outcome_counts["partial"] + outcome_counts["miss"]
    accuracy_eligible = (
        case.get("synthetic") is False
        and case.get("accuracy_eligible") is True
        and all(structural_checks)
        and checks["feedback_timestamped_and_traceable"]
        and checks["feedback_after_freeze"]
        and terminal > 0
    )
    qualification_basis = {
        "identity": {
            "case_id": case.get("case_id"),
            "person_case_id": case.get("person_case_id"),
            "scenario_id": case.get("scenario_id"),
        },
        "consent": {
            "status": consent_map.get("status"),
            "research_use_allowed": consent_map.get("research_use_allowed"),
            "benchmark_use_allowed": consent_map.get("benchmark_use_allowed"),
            "withdrawal_supported": consent_map.get("withdrawal_supported"),
        },
        "input": {
            "original_question_stored": bool(question_map.get("text")),
            "original_question_snapshot_hash": question_map.get("canonical_hash"),
            "as_of": reality_map.get("known_at"),
            "given_facts_stored": isinstance(reality_map.get("facts"), Mapping),
            "intake_snapshot_hash": intake_map.get("intake_canonical_hash"),
            "reality_snapshot_hash": reality_map.get("canonical_hash"),
            "input_manifest_hash": prediction_map.get("input_manifest_sha"),
        },
        "prediction": {
            "prediction_id": prediction_map.get("prediction_id"),
            "frozen_at": prediction_map.get("freeze_timestamp"),
            "claim_ids": [item.get("claim_id") for item in claims],
            "structured_claims_stored": bool(claims),
            "rendered_text_stored": bool(prediction_map.get("prediction_content")),
            "prediction_hash": prediction_map.get("canonical_hash"),
        },
        "feedback": [
            {
                "evidence_id": item.get("evidence_id"),
                "claim_id": item.get("claim_id"),
                "event_window": item.get("event_window"),
                "observed_at": item.get("observed_at"),
                "collected_at": item.get("collected_at"),
                "evidence_snapshot_hash": (
                    item.get("evidence_snapshot", {}).get("canonical_hash")
                    if isinstance(item.get("evidence_snapshot"), Mapping)
                    else None
                ),
            }
            for item in outcomes
        ],
    }
    return {
        "schema_version": VERSION,
        "case_id": case.get("case_id"),
        "synthetic": case.get("synthetic"),
        "qualification_basis": qualification_basis,
        "qualification_checks": checks,
        "missing_requirements": sorted(key for key, value in checks.items() if not value),
        "claim_statuses": claim_statuses,
        "outcome_counts": outcome_counts,
        "accuracy_eligible": accuracy_eligible,
        "status": "qualified" if accuracy_eligible else "not_evaluated",
        "prediction_validity": "not_evaluated",
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
    }


def summarize_prospective_cases(payload: Mapping[str, object]) -> dict[str, object]:
    data = _closed(
        payload,
        {"evaluated_at", "cases"},
        label="real-case-qualify",
    )
    _time(data["evaluated_at"], "evaluated_at")
    if not isinstance(data["cases"], list) or any(not isinstance(item, Mapping) for item in data["cases"]):
        _fail("SCHEMA_INCOMPATIBLE", "cases must be an array of V2 case objects")
    qualifications = [
        qualify_prospective_case(item, evaluated_at=data["evaluated_at"])
        for item in cast(Sequence[Mapping[str, object]], data["cases"])
    ]
    real = [
        item for item, case in zip(qualifications, data["cases"], strict=True)
        if case.get("synthetic") is False
    ]
    counts = {key: sum(item["outcome_counts"][key] for item in real) for key in _RESULT_KEYS}
    eligible = sum(item["accuracy_eligible"] is True for item in real)
    return {
        "schema_version": VERSION,
        "qualification_count": len(qualifications),
        "qualifications": qualifications,
        "qualification_contract": PROSPECTIVE_QUALIFICATION_CONTRACT,
        "product_quality": {
            "source": "human_blind_review",
            "included_in_real_accuracy": False,
        },
        "real_results": {
            "eligible_sample_count": eligible,
            **counts,
            "accuracy": None,
            "metrics": None,
            "status": "not_evaluated" if eligible == 0 else "pending_independent_scoring",
        },
        "prediction_validity": "not_evaluated",
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
    }


def dispatch_phase2(
    command: str, payload: Mapping[str, object], *, store: TrainingStore
) -> dict[str, object]:
    if command not in PHASE2_COMMANDS:
        _fail("UNKNOWN_COMMAND", f"unknown Phase 2 command: {command}")
    if not store.synthetic:
        _fail("SYNTHETIC_ONLY", "Phase 2 entry commands require --synthetic")
    if scan_for_pii(payload):
        _fail("PII_DETECTED", "Phase 2 accepts only de-identified synthetic fixtures")
    if command == "review-create":
        return create_blind_review(payload, store)
    if command == "review-show":
        data = _closed(payload, {"review_id"}, label="review-show")
        return show_blind_review(data["review_id"], store)
    if command == "review-submit":
        return submit_blind_review(payload, store)
    if command == "review-summary":
        data = _closed(payload, set(), label="review-summary", optional={"review_id"})
        review_id = data.get("review_id")
        return summarize_blind_reviews(
            store, review_id=_text(review_id, "review_id") if review_id is not None else None
        )
    if command == "behavior-regression":
        return run_behavioral_regression(payload)
    if any(
        isinstance(item, Mapping) and item.get("synthetic") is not True
        for item in payload.get("cases", [])
    ):
        _fail("SYNTHETIC_ONLY", "the Phase 2 CLI cannot ingest real cases")
    return summarize_prospective_cases(payload)


__all__ = [
    "ERROR_FAMILIES",
    "PHASE2_COMMANDS",
    "PROSPECTIVE_QUALIFICATION_CONTRACT",
    "RealCaseLearningV2Error",
    "VERSION",
    "create_blind_review",
    "dispatch_phase2",
    "qualify_prospective_case",
    "run_behavioral_regression",
    "show_blind_review",
    "submit_blind_review",
    "summarize_blind_reviews",
    "summarize_prospective_cases",
]
