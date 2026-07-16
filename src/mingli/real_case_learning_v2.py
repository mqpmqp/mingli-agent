from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Mapping, Sequence, cast

from .contracts.serialization import canonical_json, digest
from .phase18 import Phase18InputError, normalize_reality_context, orchestrate_evidence_fusion
from .training import TRAINING_SCHEMA_VERSION
from .validation_claims import validate_comparable_claim
from .validation_dataset import verify_dataset_manifest
from .validation_freeze import FreezeError, freeze_prediction, verify_prediction_snapshot
from .validation_intake import IntakeError, validate_intake
from .validation_privacy import irreversible_person_case_id, scan_for_pii
from .validation_reality import freeze_reality_evidence, verify_reality_evidence
from .validation_review import assess_review_coverage


SCHEMA_VERSION = "real-case-learning-os@2.0"
PARTITION_SCHEMA_VERSION = "real-case-learning-partition@2.0"
WITHDRAWAL_SCHEMA_VERSION = "real-case-learning-withdrawal@2.0"
PREDICTION_VALIDITY = "not_evaluated"
COMMERCIAL_RELEASE_HOLD = "ACTIVE"
STORAGE_BOUNDARY = "controlled_off_git"

_PERSON_CASE_ID = re.compile(r"^person:[0-9a-f]{64}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_SUPPORTED_CHART_PREFIXES = (
    "synthetic-chart-snapshot@2.",
    "mingli-chart-snapshot@2.",
    "derived-chart-result@",
    "ziwei-chart@",
    "bazi-chart@",
)
_OUTCOME_STATUSES = frozenset({"hit", "partial", "miss", "unverifiable"})
_ERROR_TAXONOMY = frozenset(
    {
        "wrong_direction",
        "wrong_timing",
        "over_specific",
        "missing_context",
        "rule_conflict",
        "unsupported_input",
        "insufficient_evidence",
        "data_quality",
    }
)
_RECOMMENDATIONS = frozenset({"promote", "demote", "retain", "investigate"})
_COMPARISON_STATUS = {
    "hit": "supported",
    "partial": "partially_supported",
    "miss": "contradicted",
    "unverifiable": "insufficient_evidence",
}


class RealCaseLearningV2Error(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _plain(value: object) -> object:
    return json.loads(canonical_json(value))


def _mapping(value: object, *, code: str, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise RealCaseLearningV2Error(code, f"{field} must be an object")
    return cast(dict[str, object], _plain(value))


def _parse_time(value: object, *, code: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RealCaseLearningV2Error(code, f"{field} must be an ISO-8601 date-time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RealCaseLearningV2Error(code, f"{field} must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise RealCaseLearningV2Error(code, f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _parse_event_window(
    value: object, *, code: str
) -> tuple[datetime, datetime]:
    if not isinstance(value, str) or value.count("/") != 1:
        raise RealCaseLearningV2Error(
            code, "event_window must contain bounded ISO-8601 start/end instants"
        )
    start_value, end_value = value.split("/", 1)
    start = _parse_time(start_value, code=code, field="event_window.start")
    end = _parse_time(end_value, code=code, field="event_window.end")
    if end < start:
        raise RealCaseLearningV2Error(
            code, "event_window end cannot precede its start"
        )
    return start, end


def _seal(body: Mapping[str, object]) -> dict[str, object]:
    payload = {key: value for key, value in body.items() if key != "canonical_hash"}
    result = cast(dict[str, object], _plain(payload))
    result["canonical_hash"] = digest(
        {"record_type": str(result.get("record_type", "")), "payload": result}
    )
    return result


def verify_learning_record(record: Mapping[str, object]) -> bool:
    try:
        body = {key: value for key, value in record.items() if key != "canonical_hash"}
        expected = record.get("canonical_hash")
        if not isinstance(expected, str) or expected != digest(
            {"record_type": str(body.get("record_type", "")), "payload": body}
        ):
            return False
        if record.get("prediction_validity") != PREDICTION_VALIDITY:
            return False
        if record.get("commercial_release_hold") != COMMERCIAL_RELEASE_HOLD:
            return False
        return record.get("product_claim_eligible", False) is False
    except (TypeError, ValueError):
        return False


def anonymize_person_case(raw_identifier: str, *, project_salt: str) -> str:
    """Return the existing irreversible HMAC pseudonym without retaining raw identity."""

    return irreversible_person_case_id(raw_identifier, project_salt=project_salt)


def _require_clean(value: object) -> None:
    findings = scan_for_pii(value)
    if findings:
        raise RealCaseLearningV2Error(
            "PII_DETECTED",
            f"forbidden direct identifier at {findings[0].field_path}",
        )


def _snapshot(record_type: str, body: Mapping[str, object]) -> dict[str, object]:
    return _seal({"record_type": record_type, **body})


def _claim(snapshot: Mapping[str, object], claim_id: str, scope: str) -> dict[str, object]:
    claims = snapshot.get("structured_claims")
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
        raise RealCaseLearningV2Error("PREDICTION_CLAIMS_MISSING", "prediction claims are unavailable")
    for value in claims:
        if isinstance(value, Mapping) and value.get("claim_id") == claim_id:
            if value.get("scope") != scope:
                raise RealCaseLearningV2Error(
                    "CLAIM_SCOPE_MISMATCH",
                    "Reality Evidence may override only the registered claim and scope",
                )
            comparable = {
                **value,
                "prediction_id": snapshot.get("prediction_id"),
                "person_case_id": snapshot.get("person_case_id"),
                "scenario_id": snapshot.get("scenario_id"),
            }
            try:
                validate_comparable_claim(comparable, snapshot)
            except ValueError as exc:
                raise RealCaseLearningV2Error("CLAIM_CONTRACT_INVALID", str(exc)) from exc
            return cast(dict[str, object], _plain(value))
    raise RealCaseLearningV2Error("CLAIM_SCOPE_MISMATCH", "claim and scope were not frozen in the prediction")


def _case_copy(case: Mapping[str, object]) -> dict[str, object]:
    payload = cast(dict[str, object], _plain(case))
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("record_type") != "RealCaseLearningV2Case":
        raise RealCaseLearningV2Error("UNSUPPORTED_CASE_SCHEMA", "unsupported V2 learning case schema")
    if not verify_learning_record(payload):
        raise RealCaseLearningV2Error("CASE_HASH_INVALID", "learning case hash or boundary fields are invalid")
    payload.pop("canonical_hash", None)
    return payload


def _dependency_hashes(case: Mapping[str, object], *new_hashes: object) -> list[str]:
    existing = case.get("dependency_hashes", [])
    values = [str(item) for item in existing] if isinstance(existing, list) else []
    values.extend(str(item) for item in new_hashes if isinstance(item, str) and _SHA256.fullmatch(item))
    return sorted(set(values))


def build_learning_case(
    intake: Mapping[str, object],
    *,
    chart_snapshot: Mapping[str, object],
    original_question: str,
    prediction_time_reality_context: Mapping[str, object],
    prediction: Mapping[str, object],
    frozen_at: str,
    synthetic: bool,
    near_duplicate_fingerprint: str | None = None,
) -> dict[str, object]:
    if not isinstance(synthetic, bool):
        raise RealCaseLearningV2Error("SYNTHETIC_MARKER_REQUIRED", "synthetic must be explicitly true or false")
    _require_clean(
        {
            "intake": intake,
            "chart_snapshot": chart_snapshot,
            "original_question": original_question,
            "prediction_time_reality_context": prediction_time_reality_context,
            "prediction": prediction,
        }
    )
    try:
        validated_intake = validate_intake(intake)
    except IntakeError as exc:
        raise RealCaseLearningV2Error("INTAKE_REJECTED", str(exc)) from exc
    person_case_id = str(validated_intake["person_case_id"])
    if _PERSON_CASE_ID.fullmatch(person_case_id) is None:
        raise RealCaseLearningV2Error(
            "ANONYMIZATION_REQUIRED",
            "person_case_id must be an irreversible HMAC-SHA256 pseudonym",
        )
    prediction_payload = _mapping(prediction, code="PREDICTION_REJECTED", field="prediction")
    scenario_id = str(prediction_payload.get("scenario_id", ""))
    scenarios = validated_intake.get("scenarios")
    registered_scenarios = {
        str(item.get("scenario_id"))
        for item in cast(list[object], scenarios)
        if isinstance(item, Mapping)
    }
    if (
        prediction_payload.get("person_case_id") != person_case_id
        or not scenario_id
        or scenario_id not in registered_scenarios
    ):
        raise RealCaseLearningV2Error("PREDICTION_CASE_MISMATCH", "prediction identity does not match intake")
    metadata = cast(Mapping[str, object], validated_intake["case_metadata"])
    birth = cast(Mapping[str, object], validated_intake["birth_input"])
    synthetic_sources = (
        str(metadata.get("collection_channel", "")),
        str(metadata.get("source_provenance", "")),
        str(birth.get("source", "")),
    )
    if not synthetic and any("synthetic" in item.casefold() for item in synthetic_sources):
        raise RealCaseLearningV2Error(
            "SYNTHETIC_MARKER_REQUIRED",
            "synthetic provenance cannot be represented as a real case",
        )
    if prediction_payload.get("prediction_validity") != PREDICTION_VALIDITY:
        raise RealCaseLearningV2Error("PREDICTION_VALIDITY_CHANGED", "prediction_validity must remain not_evaluated")
    if prediction_payload.get("reality_evidence_visibility") is not False:
        raise RealCaseLearningV2Error(
            "REALITY_VISIBLE_AT_PREDICTION",
            "future Reality Evidence must be invisible when the initial prediction is generated",
        )
    generated = _parse_time(
        prediction_payload.get("generated_at"), code="PREDICTION_TIME_INVALID", field="prediction.generated_at"
    )
    frozen = _parse_time(frozen_at, code="PREDICTION_TIME_INVALID", field="frozen_at")
    if frozen < generated:
        raise RealCaseLearningV2Error("PREDICTION_TIME_INVALID", "frozen_at cannot precede generated_at")

    chart = _mapping(chart_snapshot, code="UNSUPPORTED_CHART_SNAPSHOT", field="chart_snapshot")
    chart_version = str(chart.get("schema_version", ""))
    if not any(chart_version.startswith(prefix) for prefix in _SUPPORTED_CHART_PREFIXES):
        raise RealCaseLearningV2Error("UNSUPPORTED_CHART_SNAPSHOT", "chart snapshot schema is unsupported")
    if chart.get("prediction_validity") != PREDICTION_VALIDITY:
        raise RealCaseLearningV2Error("PREDICTION_VALIDITY_CHANGED", "chart prediction_validity must remain not_evaluated")
    chart_frozen = _snapshot(
        "RealCaseChartSnapshotV2",
        {**chart, "freeze_status": "frozen", "frozen_at": frozen_at},
    )
    if not isinstance(original_question, str) or not original_question.strip():
        raise RealCaseLearningV2Error("ORIGINAL_QUESTION_REQUIRED", "original question must be frozen verbatim")
    question_frozen = _snapshot(
        "OriginalQuestionSnapshotV2",
        {
            "text": original_question.strip(),
            "freeze_status": "frozen",
            "frozen_at": frozen_at,
        },
    )
    reality_context = _mapping(
        prediction_time_reality_context,
        code="PREDICTION_CONTEXT_REJECTED",
        field="prediction_time_reality_context",
    )
    known_at = _parse_time(
        reality_context.get("known_at"),
        code="PREDICTION_CONTEXT_REJECTED",
        field="prediction_time_reality_context.known_at",
    )
    if known_at > generated:
        raise RealCaseLearningV2Error(
            "PREDICTION_CONTEXT_LEAKAGE",
            "prediction-time reality context contains information known after generation",
        )
    facts = _mapping(reality_context.get("facts", {}), code="PREDICTION_CONTEXT_REJECTED", field="facts")
    try:
        normalized_reality = normalize_reality_context(facts).to_dict()
    except Phase18InputError as exc:
        raise RealCaseLearningV2Error("PREDICTION_CONTEXT_REJECTED", str(exc)) from exc
    reality_frozen = _snapshot(
        "PredictionTimeRealitySnapshotV2",
        {
            "known_at": str(reality_context["known_at"]),
            "facts": normalized_reality["facts"],
            "excluded_future_information": list(reality_context.get("excluded_future_information", [])),
            "freeze_status": "frozen",
            "frozen_at": frozen_at,
        },
    )
    claims = prediction_payload.get("structured_claims")
    if not isinstance(claims, list) or not claims:
        raise RealCaseLearningV2Error("PREDICTION_CLAIMS_MISSING", "at least one structured claim is required")
    for claim in claims:
        if not isinstance(claim, Mapping) or not claim.get("scope") or claim.get("predicted_direction") not in {
            "support",
            "contradict",
        }:
            raise RealCaseLearningV2Error(
                "UNSUPPORTED_PREDICTION_CLAIM",
                "each claim requires a scope and support/contradict direction",
            )
    try:
        prediction_frozen = freeze_prediction(prediction_payload, frozen_at=frozen_at)
    except FreezeError as exc:
        raise RealCaseLearningV2Error("PREDICTION_REJECTED", str(exc)) from exc
    if not verify_prediction_snapshot(prediction_frozen):
        raise RealCaseLearningV2Error("PREDICTION_FREEZE_INVALID", "prediction snapshot failed hash verification")

    if near_duplicate_fingerprint is None:
        near_duplicate_fingerprint = digest(
            {
                "person_case_id": person_case_id,
                "chart": chart_frozen["canonical_hash"],
                "question": " ".join(original_question.casefold().split()),
            }
        )
    if _SHA256.fullmatch(near_duplicate_fingerprint) is None:
        raise RealCaseLearningV2Error(
            "NEAR_DUPLICATE_FINGERPRINT_INVALID",
            "near_duplicate_fingerprint must be a canonical SHA-256 digest",
        )
    derived_fingerprint = digest(
        {
            "person_case_id": person_case_id,
            "prediction_id": prediction_frozen["prediction_id"],
            "chart_snapshot_hash": chart_frozen["canonical_hash"],
            "question_snapshot_hash": question_frozen["canonical_hash"],
            "claim_windows": sorted(
                (str(item["claim_id"]), str(item["scope"]), str(item.get("time_window", "")))
                for item in claims
            ),
        }
    )
    intake_hash = str(validated_intake["intake_canonical_hash"])
    case_seed = digest(
        {
            "person_case_id": person_case_id,
            "scenario_id": scenario_id,
            "prediction_id": prediction_frozen["prediction_id"],
        }
    )
    consent = cast(Mapping[str, object], validated_intake["consent"])
    body: dict[str, object] = {
        "record_type": "RealCaseLearningV2Case",
        "schema_version": SCHEMA_VERSION,
        "case_id": f"case:{case_seed[7:]}",
        "person_case_id": person_case_id,
        "scenario_id": scenario_id,
        "lifecycle_status": "prediction_frozen",
        "storage_boundary": STORAGE_BOUNDARY,
        "training_boundary_version": TRAINING_SCHEMA_VERSION,
        "consent": {
            "status": consent["consent_status"],
            "research_use_allowed": consent["research_use_allowed"],
            "benchmark_use_allowed": consent["benchmark_use_allowed"],
            "withdrawal_supported": consent["withdrawal_supported"],
        },
        "synthetic": synthetic,
        "accuracy_eligible": False,
        "product_claim_eligible": False,
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
        "prediction_validity": PREDICTION_VALIDITY,
        "intake_snapshot": validated_intake,
        "chart_snapshot": chart_frozen,
        "original_question_snapshot": question_frozen,
        "prediction_time_reality_snapshot": reality_frozen,
        "prediction_snapshot": prediction_frozen,
        "prior_event_validations": [],
        "future_outcomes": [],
        "adjudications": [],
        "error_taxonomy": [],
        "rule_attributions": [],
        "revisions": [],
        "benchmark_comparisons": [],
        "rule_recommendations": [],
        "negative_case_archive": [],
        "derived_fingerprint": derived_fingerprint,
        "near_duplicate_fingerprint": near_duplicate_fingerprint,
        "dependency_hashes": sorted(
            {
                intake_hash,
                str(chart_frozen["canonical_hash"]),
                str(question_frozen["canonical_hash"]),
                str(reality_frozen["canonical_hash"]),
                str(prediction_frozen["canonical_hash"]),
            }
        ),
    }
    return _seal(body)


def _freeze_case_evidence(
    case: Mapping[str, object],
    evidence: Mapping[str, object],
    *,
    relation: str,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    tuple[datetime, datetime],
]:
    payload = _mapping(evidence, code="REALITY_EVIDENCE_REJECTED", field="evidence")
    _require_clean(payload)
    if payload.get("person_case_id") != case.get("person_case_id") or payload.get("scenario_id") != case.get(
        "scenario_id"
    ):
        raise RealCaseLearningV2Error("EVIDENCE_CASE_MISMATCH", "evidence identity does not match case")
    if payload.get("synthetic") is not case.get("synthetic"):
        raise RealCaseLearningV2Error("SYNTHETIC_MARKER_MISMATCH", "evidence and case synthetic markers must match")
    if case.get("synthetic") is False and "synthetic" in str(payload.get("source_provenance", "")).casefold():
        raise RealCaseLearningV2Error(
            "SYNTHETIC_MARKER_REQUIRED",
            "synthetic evidence provenance cannot enter a real case",
        )
    claim_id = str(payload.get("claim_id", ""))
    scope = str(payload.get("scope", ""))
    claim = _claim(cast(Mapping[str, object], case["prediction_snapshot"]), claim_id, scope)
    event_window = payload.get("event_window")
    if event_window != claim.get("time_window"):
        raise RealCaseLearningV2Error(
            "EVENT_WINDOW_MISMATCH",
            "Reality Evidence event window must match the frozen claim window",
        )
    parsed_window = _parse_event_window(
        event_window, code="EVENT_WINDOW_INVALID"
    )
    try:
        frozen = freeze_reality_evidence(payload)
    except ValueError as exc:
        raise RealCaseLearningV2Error("REALITY_EVIDENCE_REJECTED", str(exc)) from exc
    if not verify_reality_evidence(frozen):
        raise RealCaseLearningV2Error("REALITY_EVIDENCE_HASH_INVALID", "Reality Evidence failed hash verification")
    entry = {
        "record_type": "PriorEventValidationV2" if relation == "prior" else "FutureOutcomeV2",
        "evidence_id": frozen["evidence_id"],
        "claim_id": claim_id,
        "scope": scope,
        "event_window": str(event_window),
        "observed_at": frozen["observed_at"],
        "collected_at": frozen["collected_at"],
        "evidence_snapshot": frozen,
    }
    return payload, claim, entry, parsed_window


def record_prior_event_validation(
    case: Mapping[str, object], evidence: Mapping[str, object]
) -> dict[str, object]:
    result = _case_copy(case)
    payload, _claim_record, entry, event_window = _freeze_case_evidence(
        result, evidence, relation="prior"
    )
    generated = _parse_time(
        cast(Mapping[str, object], result["prediction_snapshot"]).get("generated_at"),
        code="PREDICTION_TIME_INVALID",
        field="prediction.generated_at",
    )
    observed = _parse_time(payload.get("observed_at"), code="PRIOR_EVENT_TIME_INVALID", field="observed_at")
    collected = _parse_time(payload.get("collected_at"), code="PRIOR_EVENT_TIME_INVALID", field="collected_at")
    if observed > generated or collected > generated:
        raise RealCaseLearningV2Error(
            "PRIOR_EVENT_AFTER_PREDICTION",
            "prior-event validation must be observed and collected before prediction generation",
        )
    if collected < observed:
        raise RealCaseLearningV2Error("PRIOR_EVENT_TIME_INVALID", "collected_at cannot precede observed_at")
    _window_start, window_end = event_window
    if window_end > generated:
        raise RealCaseLearningV2Error(
            "PRIOR_EVENT_WINDOW_NOT_PRIOR",
            "prior-event window must end before prediction generation",
        )
    sealed_entry = _seal(entry)
    validations = cast(list[object], result["prior_event_validations"])
    if any(isinstance(item, Mapping) and item.get("evidence_id") == entry["evidence_id"] for item in validations):
        raise RealCaseLearningV2Error("DUPLICATE_EVIDENCE", "prior evidence_id already exists")
    validations.append(sealed_entry)
    result["lifecycle_status"] = "prior_event_validated"
    result["dependency_hashes"] = _dependency_hashes(result, sealed_entry["canonical_hash"])
    return _seal(result)


def record_future_outcome(
    case: Mapping[str, object], evidence: Mapping[str, object]
) -> dict[str, object]:
    result = _case_copy(case)
    payload, claim, entry, event_window = _freeze_case_evidence(
        result, evidence, relation="future"
    )
    frozen_at = _parse_time(
        cast(Mapping[str, object], result["prediction_snapshot"]).get("freeze_timestamp"),
        code="PREDICTION_TIME_INVALID",
        field="prediction.freeze_timestamp",
    )
    observed = _parse_time(payload.get("observed_at"), code="FUTURE_OUTCOME_TIME_INVALID", field="observed_at")
    collected = _parse_time(payload.get("collected_at"), code="FUTURE_OUTCOME_TIME_INVALID", field="collected_at")
    if observed <= frozen_at:
        raise RealCaseLearningV2Error(
            "FUTURE_OUTCOME_NOT_FUTURE",
            "future outcome must be observed after the initial prediction is frozen",
        )
    if collected < observed:
        raise RealCaseLearningV2Error("FUTURE_OUTCOME_TIME_INVALID", "collected_at cannot precede observed_at")
    window_start, _window_end = event_window
    if window_start <= frozen_at:
        raise RealCaseLearningV2Error(
            "FUTURE_OUTCOME_WINDOW_NOT_FUTURE",
            "future outcome window must start after the initial prediction is frozen",
        )
    if observed < window_start:
        raise RealCaseLearningV2Error(
            "FUTURE_OUTCOME_BEFORE_WINDOW",
            "future outcome cannot be observed before its frozen event window starts",
        )
    chart_evidence = {
        "evidence_id": f"prediction:{result['case_id']}:{claim['claim_id']}",
        "claim_id": claim["claim_id"],
        "scope": claim["scope"],
        "source_type": "chart",
        "source_id": str(cast(Mapping[str, object], result["prediction_snapshot"])["prediction_id"]),
        "direction": claim["predicted_direction"],
        "weight": 1,
        "priority": 50,
        "verified": False,
        "detail_code": "frozen_initial_prediction",
    }
    reality_evidence = {
        "evidence_id": str(payload["evidence_id"]),
        "claim_id": claim["claim_id"],
        "scope": claim["scope"],
        "source_type": "reality",
        "source_id": str(payload["source_provenance"]),
        "direction": payload["direction"],
        "weight": 0,
        "priority": 100,
        "verified": payload.get("verified") is True,
        "detail_code": "future_outcome_observation",
    }
    try:
        fusion = orchestrate_evidence_fusion({}, [chart_evidence, reality_evidence])
    except Phase18InputError as exc:
        raise RealCaseLearningV2Error("REALITY_EVIDENCE_REJECTED", str(exc)) from exc
    entry["reality_resolution"] = fusion.claims[0].to_dict()
    sealed_entry = _seal(entry)
    outcomes = cast(list[object], result["future_outcomes"])
    if any(isinstance(item, Mapping) and item.get("evidence_id") == entry["evidence_id"] for item in outcomes):
        raise RealCaseLearningV2Error("DUPLICATE_EVIDENCE", "future outcome evidence_id already exists")
    outcomes.append(sealed_entry)
    result["lifecycle_status"] = "future_outcome_observed"
    result["dependency_hashes"] = _dependency_hashes(result, sealed_entry["canonical_hash"])
    return _seal(result)


def adjudicate_outcome(
    case: Mapping[str, object],
    *,
    adjudication_id: str,
    claim_id: str,
    scope: str,
    outcome_evidence_ids: Sequence[str],
    status: str,
    error_taxonomy: Sequence[str],
    rule_attributions: Sequence[Mapping[str, object]],
    revision: Mapping[str, object],
    benchmark_comparison: Mapping[str, object],
    recommendation: str,
    adjudicated_at: str,
) -> dict[str, object]:
    result = _case_copy(case)
    if status not in _OUTCOME_STATUSES:
        raise RealCaseLearningV2Error("UNSUPPORTED_ADJUDICATION_STATUS", f"unsupported status: {status}")
    _parse_time(adjudicated_at, code="ADJUDICATION_TIME_INVALID", field="adjudicated_at")
    _claim(cast(Mapping[str, object], result["prediction_snapshot"]), claim_id, scope)
    outcomes = [item for item in cast(list[object], result["future_outcomes"]) if isinstance(item, Mapping)]
    available = {
        str(item.get("evidence_id")): item
        for item in outcomes
        if item.get("claim_id") == claim_id and item.get("scope") == scope
    }
    requested = [str(item) for item in outcome_evidence_ids]
    if not requested or any(item not in available for item in requested):
        raise RealCaseLearningV2Error(
            "OUTCOME_EVIDENCE_NOT_FOUND",
            "adjudication evidence must exist and match the frozen claim and scope",
        )
    taxonomy = [str(item) for item in error_taxonomy]
    if any(item not in _ERROR_TAXONOMY for item in taxonomy):
        raise RealCaseLearningV2Error("UNSUPPORTED_ERROR_TAXONOMY", "unsupported error taxonomy code")
    if status != "hit" and not taxonomy:
        raise RealCaseLearningV2Error("ERROR_TAXONOMY_REQUIRED", "non-hit adjudications require an error taxonomy")
    attributions = [
        _mapping(item, code="RULE_ATTRIBUTION_REQUIRED", field="rule_attribution")
        for item in rule_attributions
    ]
    if not attributions or any(not item.get("rule_id") or not item.get("attribution") for item in attributions):
        raise RealCaseLearningV2Error("RULE_ATTRIBUTION_REQUIRED", "rule id and attribution are required")
    revision_payload = _mapping(revision, code="REVISION_REQUIRED", field="revision")
    if not revision_payload.get("revision_id") or not revision_payload.get("proposal"):
        raise RealCaseLearningV2Error("REVISION_REQUIRED", "revision id and proposal are required")
    comparison = _mapping(
        benchmark_comparison,
        code="BENCHMARK_COMPARISON_REQUIRED",
        field="benchmark_comparison",
    )
    _require_clean(
        {
            "error_taxonomy": taxonomy,
            "rule_attributions": attributions,
            "revision": revision_payload,
            "benchmark_comparison": comparison,
        }
    )
    required_comparison = (
        "baseline_version",
        "candidate_version",
        "baseline_status",
        "candidate_status",
        "partition",
    )
    if any(not comparison.get(field) for field in required_comparison):
        raise RealCaseLearningV2Error(
            "BENCHMARK_COMPARISON_REQUIRED",
            "versioned baseline and candidate comparison is required",
        )
    if comparison.get("leakage_clean") is not True or comparison.get("partition") != "test":
        raise RealCaseLearningV2Error(
            "LEAKAGE_RISK",
            "rule recommendations require a leakage-clean temporal test comparison",
        )
    partition_manifest = comparison.get("partition_manifest")
    if not isinstance(partition_manifest, Mapping):
        raise RealCaseLearningV2Error(
            "PARTITION_MANIFEST_REQUIRED",
            "rule recommendations require a frozen V2 temporal partition manifest",
        )
    if (
        partition_manifest.get("record_type")
        != "RealCaseLearningV2PartitionManifest"
        or partition_manifest.get("schema_version") != PARTITION_SCHEMA_VERSION
        or partition_manifest.get("leakage_detected") is not False
        or not verify_learning_record(partition_manifest)
    ):
        raise RealCaseLearningV2Error(
            "PARTITION_MANIFEST_INVALID",
            "temporal partition manifest failed its frozen hash or leakage boundary",
        )
    test_case_ids = partition_manifest.get("test_case_ids")
    if not isinstance(test_case_ids, list) or result.get("case_id") not in test_case_ids:
        raise RealCaseLearningV2Error(
            "PARTITION_CASE_MISMATCH",
            "adjudicated case must belong to the manifest's leakage-clean test partition",
        )
    dataset_manifest = comparison.get("dataset_manifest")
    if dataset_manifest is not None and (
        not isinstance(dataset_manifest, Mapping) or not verify_dataset_manifest(dataset_manifest)
    ):
        raise RealCaseLearningV2Error(
            "DATASET_MANIFEST_INVALID",
            "referenced legacy validation dataset manifest failed its frozen hash boundary",
        )
    if recommendation not in _RECOMMENDATIONS:
        raise RealCaseLearningV2Error("UNSUPPORTED_RULE_RECOMMENDATION", "unsupported recommendation")
    revision_record = _seal(
        {
            "record_type": "RealCaseRevisionV2",
            **revision_payload,
            "review_state": "pending_operator_review",
            "applied": False,
        }
    )
    comparison_record = _seal(
        {
            "record_type": "BenchmarkVersionComparisonV2",
            **comparison,
            "prediction_validity": PREDICTION_VALIDITY,
        }
    )
    adjudication = _seal(
        {
            "record_type": "OutcomeAdjudicationV2",
            "adjudication_id": adjudication_id,
            "claim_id": claim_id,
            "scope": scope,
            "outcome_evidence_ids": sorted(requested),
            "status": status,
            "comparison_status": _COMPARISON_STATUS[status],
            "error_taxonomy": sorted(set(taxonomy)),
            "rule_attributions": attributions,
            "adjudicated_at": adjudicated_at,
            "operator_review_required": True,
        }
    )
    recommendation_record = _seal(
        {
            "record_type": "RuleReviewRecommendationV2",
            "recommendation_id": digest(
                {
                    "case_id": result["case_id"],
                    "adjudication_id": adjudication_id,
                    "recommendation": recommendation,
                }
            ),
            "adjudication_id": adjudication_id,
            "rule_ids": sorted(str(item["rule_id"]) for item in attributions),
            "recommendation": recommendation,
            "review_state": "pending_operator_review",
            "applied_to_rules": False,
            "benchmark_comparison_hash": comparison_record["canonical_hash"],
        }
    )
    cast(list[object], result["adjudications"]).append(adjudication)
    result["error_taxonomy"] = sorted(
        set(str(item) for item in cast(list[object], result["error_taxonomy"])) | set(taxonomy)
    )
    cast(list[object], result["rule_attributions"]).extend(attributions)
    cast(list[object], result["revisions"]).append(revision_record)
    cast(list[object], result["benchmark_comparisons"]).append(comparison_record)
    cast(list[object], result["rule_recommendations"]).append(recommendation_record)
    archive_hash: object = None
    if status in {"partial", "miss", "unverifiable"}:
        archive = _seal(
            {
                "record_type": "NegativeCaseArchiveV2",
                "adjudication_id": adjudication_id,
                "status": status,
                "error_taxonomy": sorted(set(taxonomy)),
                "review_state": "pending_operator_review",
                "accuracy_eligible": False,
            }
        )
        cast(list[object], result["negative_case_archive"]).append(archive)
        archive_hash = archive["canonical_hash"]
    result["lifecycle_status"] = "pending_operator_review"
    result["accuracy_eligible"] = False
    result["product_claim_eligible"] = False
    result["dependency_hashes"] = _dependency_hashes(
        result,
        adjudication["canonical_hash"],
        revision_record["canonical_hash"],
        comparison_record["canonical_hash"],
        recommendation_record["canonical_hash"],
        archive_hash,
    )
    return _seal(result)


def _event_window_end(value: object) -> datetime:
    if not isinstance(value, str) or "/" not in value:
        raise RealCaseLearningV2Error("TEMPORAL_BOUNDARY_MISSING", "event_window must have start/end")
    return _parse_time(value.split("/", 1)[1], code="TEMPORAL_BOUNDARY_MISSING", field="event_window.end")


def _verified_for_partition(case: Mapping[str, object]) -> dict[str, object]:
    payload = cast(dict[str, object], _plain(case))
    ingested_at = payload.pop("ingested_at", None)
    if ingested_at is not None and not verify_learning_record(payload):
        raise RealCaseLearningV2Error("CASE_HASH_INVALID", "case changed outside ignored ingestion metadata")
    if ingested_at is None and not verify_learning_record(payload):
        raise RealCaseLearningV2Error("CASE_HASH_INVALID", "case hash is invalid")
    return payload


def build_temporal_partitions(
    cases: Sequence[Mapping[str, object]], *, cutoff_at: str
) -> dict[str, object]:
    cutoff = _parse_time(cutoff_at, code="TEMPORAL_BOUNDARY_MISSING", field="cutoff_at")
    active: list[dict[str, object]] = []
    withdrawn_refs: list[str] = []
    for case in cases:
        payload = _verified_for_partition(case)
        if payload.get("record_type") == "RealCaseLearningV2Withdrawal":
            withdrawn_refs.append(str(payload["case_ref_hash"]))
            continue
        if payload.get("record_type") != "RealCaseLearningV2Case":
            raise RealCaseLearningV2Error("UNSUPPORTED_CASE_SCHEMA", "partition input is not a V2 case")
        active.append(payload)

    base: dict[str, str] = {}
    metadata: dict[str, dict[str, object]] = {}
    for case in active:
        outcomes = [item for item in cast(list[object], case.get("future_outcomes", [])) if isinstance(item, Mapping)]
        if not outcomes:
            raise RealCaseLearningV2Error(
                "TEMPORAL_BOUNDARY_MISSING",
                "partitioning requires at least one future outcome",
            )
        case_id = str(case["case_id"])
        available_at = max(
            _parse_time(item.get("collected_at"), code="TEMPORAL_BOUNDARY_MISSING", field="collected_at")
            for item in outcomes
        )
        observed_at = max(
            _parse_time(item.get("observed_at"), code="TEMPORAL_BOUNDARY_MISSING", field="observed_at")
            for item in outcomes
        )
        event_end = max(_event_window_end(item.get("event_window")) for item in outcomes)
        base[case_id] = "train" if max(available_at, observed_at, event_end) < cutoff else "test"
        metadata[case_id] = {
            "person_case_id": case["person_case_id"],
            "prediction_id": cast(Mapping[str, object], case["prediction_snapshot"])["prediction_id"],
            "event_window": sorted(str(item["event_window"]) for item in outcomes),
            "derived_fingerprint": case["derived_fingerprint"],
            "near_duplicate_fingerprint": case["near_duplicate_fingerprint"],
        }

    parent = {case_id: case_id for case_id in metadata}

    def find(case_id: str) -> str:
        while parent[case_id] != case_id:
            parent[case_id] = parent[parent[case_id]]
            case_id = parent[case_id]
        return case_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    case_ids = sorted(metadata)
    for index, left in enumerate(case_ids):
        for right in case_ids[index + 1 :]:
            left_meta, right_meta = metadata[left], metadata[right]
            duplicate = (
                left_meta["person_case_id"] == right_meta["person_case_id"]
                or left_meta["prediction_id"] == right_meta["prediction_id"]
                or left_meta["derived_fingerprint"] == right_meta["derived_fingerprint"]
                or left_meta["near_duplicate_fingerprint"] == right_meta["near_duplicate_fingerprint"]
                or (
                    left_meta["person_case_id"] == right_meta["person_case_id"]
                    and left_meta["event_window"] == right_meta["event_window"]
                )
            )
            if duplicate:
                union(left, right)

    groups: dict[str, list[str]] = {}
    for case_id in case_ids:
        groups.setdefault(find(case_id), []).append(case_id)
    assignment = dict(base)
    forced_test: list[str] = []
    for group in groups.values():
        if any(base[item] == "test" for item in group):
            for item in group:
                if base[item] == "train":
                    forced_test.append(item)
                assignment[item] = "test"
    train_ids = sorted(item for item, partition in assignment.items() if partition == "train")
    test_ids = sorted(item for item, partition in assignment.items() if partition == "test")
    synthetic_ids = sorted(str(item["case_id"]) for item in active if item.get("synthetic") is True)
    body = {
        "record_type": "RealCaseLearningV2PartitionManifest",
        "schema_version": PARTITION_SCHEMA_VERSION,
        "cutoff_at": cutoff_at,
        "assignment_basis": "event_and_observation_time",
        "ingestion_order_used": False,
        "deduplication_keys": [
            "person_case_id",
            "prediction_id",
            "event_window",
            "derived_fingerprint",
            "near_duplicate_fingerprint",
        ],
        "train_case_ids": train_ids,
        "test_case_ids": test_ids,
        "forced_test_case_ids": sorted(forced_test),
        "withdrawn_case_refs": sorted(withdrawn_refs),
        "synthetic_case_ids": synthetic_ids,
        "accuracy_eligible_case_ids": [],
        "leakage_detected": False,
        "leakage_prevention": "duplicate_components_use_test_partition",
        "product_claim_eligible": False,
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
        "prediction_validity": PREDICTION_VALIDITY,
    }
    return _seal(body)


def build_operator_review_queue(cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for case in cases:
        payload = _case_copy(case)
        case_ref_hash = digest({"case_id": payload["case_id"]})
        for recommendation in cast(list[object], payload["rule_recommendations"]):
            if not isinstance(recommendation, Mapping):
                continue
            entries.append(
                {
                    "case_ref_hash": case_ref_hash,
                    "recommendation_id": recommendation["recommendation_id"],
                    "adjudication_id": recommendation["adjudication_id"],
                    "rule_ids": list(cast(Sequence[object], recommendation["rule_ids"])),
                    "recommendation": recommendation["recommendation"],
                    "review_state": "pending_operator_review",
                    "applied_to_rules": False,
                }
            )
    entries.sort(key=lambda item: (str(item["recommendation_id"]), str(item["case_ref_hash"])))
    review_boundary = assess_review_coverage([], required_reviewers=1)
    return _seal(
        {
            "record_type": "RealCaseLearningV2OperatorReviewQueue",
            "schema_version": "real-case-learning-review-queue@2.0",
            "entries": entries,
            "automatic_actions_applied": 0,
            "review_boundary": review_boundary,
            "product_claim_eligible": False,
            "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
            "prediction_validity": PREDICTION_VALIDITY,
        }
    )


def withdraw_case(case: Mapping[str, object], *, withdrawn_at: str) -> dict[str, object]:
    payload = _case_copy(case)
    _parse_time(withdrawn_at, code="WITHDRAWAL_TIME_INVALID", field="withdrawn_at")

    def collect_hashes(value: object) -> set[str]:
        if isinstance(value, Mapping):
            return {
                str(item)
                for key, item in value.items()
                if key == "canonical_hash" and isinstance(item, str) and _SHA256.fullmatch(item)
            } | set().union(*(collect_hashes(item) for item in value.values()))
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return set().union(*(collect_hashes(item) for item in value))
        return set()

    dependencies = sorted(
        set(_dependency_hashes(payload, case.get("canonical_hash"))) | collect_hashes(case)
    )
    body = {
        "record_type": "RealCaseLearningV2Withdrawal",
        "schema_version": WITHDRAWAL_SCHEMA_VERSION,
        "case_ref_hash": digest({"case_id": payload["case_id"]}),
        "person_ref_hash": digest({"person_case_id": payload["person_case_id"]}),
        "lifecycle_status": "withdrawn",
        "withdrawn_at": withdrawn_at,
        "dependencies_valid": False,
        "dependent_records_retained": False,
        "invalidated_dependency_hashes": dependencies,
        "synthetic": payload["synthetic"],
        "accuracy_eligible": False,
        "product_claim_eligible": False,
        "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
        "prediction_validity": PREDICTION_VALIDITY,
    }
    return _seal(body)


def summarize_learning_cases(cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    active = [_case_copy(case) for case in cases]
    synthetic_count = sum(item.get("synthetic") is True for item in active)
    return _seal(
        {
            "record_type": "RealCaseLearningV2Summary",
            "schema_version": "real-case-learning-summary@2.0",
            "total_cases": len(active),
            "synthetic_contract_cases": synthetic_count,
            "real_cases_pending_independent_review": len(active) - synthetic_count,
            "accuracy_eligible_cases": 0,
            "accuracy_metrics": None,
            "product_accuracy_claim_allowed": False,
            "product_claim_eligible": False,
            "commercial_release_hold": COMMERCIAL_RELEASE_HOLD,
            "prediction_validity": PREDICTION_VALIDITY,
            "limitations": [
                "synthetic_cases_are_contract_tests_only",
                "no_case_is_accuracy_evidence_before_independent_operator_review",
                "rule_promotion_and_demotion_are_never_automatic",
            ],
        }
    )


__all__ = [
    "COMMERCIAL_RELEASE_HOLD",
    "PARTITION_SCHEMA_VERSION",
    "PREDICTION_VALIDITY",
    "RealCaseLearningV2Error",
    "SCHEMA_VERSION",
    "STORAGE_BOUNDARY",
    "WITHDRAWAL_SCHEMA_VERSION",
    "adjudicate_outcome",
    "anonymize_person_case",
    "build_learning_case",
    "build_operator_review_queue",
    "build_temporal_partitions",
    "record_future_outcome",
    "record_prior_event_validation",
    "summarize_learning_cases",
    "verify_learning_record",
    "withdraw_case",
]
