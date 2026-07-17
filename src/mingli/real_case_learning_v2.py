from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Mapping, Sequence, cast

from jsonschema import Draft202012Validator, ValidationError

from .contracts import get_schema
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
_CASE_ID = re.compile(r"^case:[0-9a-f]{64}$")
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
_PREDICTION_FIELDS = frozenset(
    {
        "prediction_id",
        "person_case_id",
        "scenario_id",
        "engine_version",
        "source_commit_sha",
        "rule_set_version",
        "knowledge_manifest_sha",
        "input_manifest_sha",
        "generated_at",
        "prediction_content",
        "structured_claims",
        "confidence",
        "blocked_fields",
        "reality_evidence_visibility",
        "prediction_validity",
    }
)
_PREDICTION_CLAIM_FIELDS = frozenset(
    {
        "claim_id",
        "scope",
        "domain",
        "time_window",
        "claim_type",
        "predicted_direction",
        "predicted_event_or_state",
        "confidence",
        "specificity_level",
        "exclusion_conditions",
        "rule_ids",
    }
)
_PREDICTION_SNAPSHOT_FIELDS = _PREDICTION_FIELDS | {
    "freeze_status",
    "freeze_timestamp",
    "canonical_hash",
}
_REALITY_EVIDENCE_FIELDS = frozenset(
    {
        "evidence_id",
        "person_case_id",
        "scenario_id",
        "claim_id",
        "scope",
        "event_window",
        "observed_at",
        "collected_at",
        "source_provenance",
        "evidence_quality",
        "direction",
        "verified",
        "synthetic",
    }
)
_REALITY_EVIDENCE_SNAPSHOT_FIELDS = _REALITY_EVIDENCE_FIELDS | {
    "freeze_status",
    "canonical_hash",
}
_PRIOR_EVIDENCE_ENTRY_FIELDS = frozenset(
    {
        "record_type",
        "evidence_id",
        "claim_id",
        "scope",
        "event_window",
        "observed_at",
        "collected_at",
        "evidence_snapshot",
        "canonical_hash",
    }
)
_FUTURE_EVIDENCE_ENTRY_FIELDS = _PRIOR_EVIDENCE_ENTRY_FIELDS | {
    "reality_resolution"
}
_PARTITION_INPUT_FIELDS = frozenset(
    {
        "person_case_id",
        "prediction_id",
        "event_windows",
        "available_at",
        "observed_at",
        "event_window_end",
        "derived_fingerprint",
        "near_duplicate_fingerprint",
        "base_assignment",
    }
)
_PARTITION_MANIFEST_FIELDS = frozenset(
    {
        "record_type",
        "schema_version",
        "cutoff_at",
        "assignment_basis",
        "ingestion_order_used",
        "deduplication_keys",
        "base_train_case_ids",
        "base_test_case_ids",
        "train_case_ids",
        "test_case_ids",
        "forced_test_case_ids",
        "withdrawn_case_refs",
        "synthetic_case_ids",
        "accuracy_eligible_case_ids",
        "case_dependency_hashes",
        "case_partition_inputs",
        "withdrawal_dependency_hashes",
        "dependency_hashes",
        "corpus_hash",
        "leakage_detected",
        "leakage_prevention",
        "product_claim_eligible",
        "commercial_release_hold",
        "prediction_validity",
        "canonical_hash",
    }
)


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


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _bounded_confidence(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value <= 1
    )


def _validate_prediction_contract(payload: Mapping[str, object]) -> None:
    if set(payload) != _PREDICTION_FIELDS:
        raise RealCaseLearningV2Error(
            "PREDICTION_CONTRACT_CLOSED",
            "prediction fields must exactly match the closed V2 prediction contract",
        )
    claims = payload.get("structured_claims")
    if not isinstance(claims, list) or not claims:
        raise RealCaseLearningV2Error(
            "PREDICTION_CONTRACT_CLOSED",
            "structured_claims must be a non-empty list",
        )
    string_fields = (
        "prediction_id",
        "person_case_id",
        "scenario_id",
        "engine_version",
        "source_commit_sha",
        "rule_set_version",
        "knowledge_manifest_sha",
        "input_manifest_sha",
        "generated_at",
        "prediction_content",
    )
    if any(not isinstance(payload.get(field), str) or not payload.get(field) for field in string_fields):
        raise RealCaseLearningV2Error(
            "PREDICTION_CONTRACT_CLOSED",
            "prediction scalar fields must be non-empty strings",
        )
    if (
        not _bounded_confidence(payload.get("confidence"))
        or not _string_list(payload.get("blocked_fields"))
    ):
        raise RealCaseLearningV2Error(
            "PREDICTION_CONTRACT_CLOSED",
            "prediction confidence or blocked fields are invalid",
        )
    for claim in claims:
        if not isinstance(claim, Mapping) or set(claim) != _PREDICTION_CLAIM_FIELDS:
            raise RealCaseLearningV2Error(
                "PREDICTION_CONTRACT_CLOSED",
                "claim fields must exactly match the closed V2 prediction claim contract",
            )
        claim_strings = (
            "claim_id",
            "scope",
            "domain",
            "time_window",
            "claim_type",
            "predicted_direction",
            "predicted_event_or_state",
            "specificity_level",
        )
        if (
            any(not isinstance(claim.get(field), str) or not claim.get(field) for field in claim_strings)
            or claim.get("predicted_direction") not in {"support", "contradict"}
            or not _bounded_confidence(claim.get("confidence"))
            or not _string_list(claim.get("exclusion_conditions"))
            or not _string_list(claim.get("rule_ids"))
        ):
            raise RealCaseLearningV2Error(
                "PREDICTION_CONTRACT_CLOSED",
                "prediction claim scalar and list fields must satisfy the closed V2 contract",
            )


def _validate_reality_evidence_contract(payload: Mapping[str, object]) -> None:
    if set(payload) != _REALITY_EVIDENCE_FIELDS:
        raise RealCaseLearningV2Error(
            "REALITY_EVIDENCE_CONTRACT_CLOSED",
            "Reality Evidence fields must exactly match the closed V2 evidence contract",
        )
    string_fields = (
        "evidence_id",
        "person_case_id",
        "scenario_id",
        "claim_id",
        "scope",
        "event_window",
        "observed_at",
        "collected_at",
        "source_provenance",
        "evidence_quality",
        "direction",
    )
    if (
        any(not isinstance(payload.get(field), str) or not payload.get(field) for field in string_fields)
        or payload.get("direction") not in {"support", "contradict"}
        or not isinstance(payload.get("verified"), bool)
        or not isinstance(payload.get("synthetic"), bool)
    ):
        raise RealCaseLearningV2Error(
            "REALITY_EVIDENCE_CONTRACT_CLOSED",
            "Reality Evidence boundary fields must be scalar and type-safe",
        )


def _validate_v2_prediction_snapshot(snapshot: Mapping[str, object]) -> None:
    if set(snapshot) != _PREDICTION_SNAPSHOT_FIELDS:
        raise RealCaseLearningV2Error(
            "CASE_PREDICTION_CONTRACT_INVALID",
            "frozen prediction fields do not match the closed V2 snapshot contract",
        )
    payload = {key: snapshot[key] for key in _PREDICTION_FIELDS}
    try:
        _validate_prediction_contract(payload)
    except RealCaseLearningV2Error as exc:
        raise RealCaseLearningV2Error(
            "CASE_PREDICTION_CONTRACT_INVALID", exc.message
        ) from exc
    if (
        snapshot.get("freeze_status") != "frozen"
        or not isinstance(snapshot.get("freeze_timestamp"), str)
        or snapshot.get("reality_evidence_visibility") is not False
        or snapshot.get("prediction_validity") != PREDICTION_VALIDITY
        or not verify_prediction_snapshot(snapshot)
    ):
        raise RealCaseLearningV2Error(
            "CASE_PREDICTION_CONTRACT_INVALID",
            "frozen prediction status, timestamp, or canonical hash is invalid",
        )
    _parse_time(
        snapshot.get("freeze_timestamp"),
        code="CASE_PREDICTION_CONTRACT_INVALID",
        field="prediction.freeze_timestamp",
    )


def _validate_v2_reality_evidence_snapshot(snapshot: Mapping[str, object]) -> None:
    if set(snapshot) != _REALITY_EVIDENCE_SNAPSHOT_FIELDS:
        raise RealCaseLearningV2Error(
            "CASE_EVIDENCE_CONTRACT_INVALID",
            "frozen Reality Evidence fields do not match the closed V2 snapshot contract",
        )
    payload = {key: snapshot[key] for key in _REALITY_EVIDENCE_FIELDS}
    try:
        _validate_reality_evidence_contract(payload)
    except RealCaseLearningV2Error as exc:
        raise RealCaseLearningV2Error(
            "CASE_EVIDENCE_CONTRACT_INVALID", exc.message
        ) from exc
    if snapshot.get("freeze_status") != "frozen" or not verify_reality_evidence(
        snapshot
    ):
        raise RealCaseLearningV2Error(
            "CASE_EVIDENCE_CONTRACT_INVALID",
            "frozen Reality Evidence status or canonical hash is invalid",
        )


def _verify_sealed_record(record: Mapping[str, object]) -> bool:
    body = {key: value for key, value in record.items() if key != "canonical_hash"}
    expected = record.get("canonical_hash")
    return isinstance(expected, str) and expected == digest(
        {"record_type": str(body.get("record_type", "")), "payload": body}
    )


def _validate_schema(
    payload: Mapping[str, object], *, schema_name: str, code: str
) -> None:
    try:
        Draft202012Validator(get_schema(schema_name)).validate(payload)
    except ValidationError as exc:
        raise RealCaseLearningV2Error(code, exc.message) from exc


def _privacy_scan_projection(value: object) -> object:
    if isinstance(value, Mapping):
        projected: dict[str, object] = {}
        for key, item in value.items():
            field = str(key)
            valid_person_id = field == "person_case_id" and isinstance(
                item, str
            ) and _PERSON_CASE_ID.fullmatch(item)
            valid_hash = (
                field.endswith("_hash")
                and isinstance(item, str)
                and _SHA256.fullmatch(item)
            )
            valid_hashes = (
                field.endswith("_hashes")
                and isinstance(item, list)
                and all(
                    isinstance(entry, str) and _SHA256.fullmatch(entry)
                    for entry in item
                )
            )
            valid_sha = (
                field.endswith("_sha")
                and isinstance(item, str)
                and (
                    _SHA256.fullmatch(item) is not None
                    or re.fullmatch(r"[0-9a-f]{40}", item) is not None
                )
            )
            if valid_person_id or valid_hash or valid_hashes or valid_sha:
                continue
            projected[field] = _privacy_scan_projection(item)
        return projected
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_privacy_scan_projection(item) for item in value]
    return value


def _validate_v2_case_intake(case: Mapping[str, object]) -> None:
    _require_clean(_privacy_scan_projection(case))
    intake = case.get("intake_snapshot")
    if not isinstance(intake, Mapping):
        raise RealCaseLearningV2Error(
            "CASE_INTAKE_CONTRACT_INVALID", "intake snapshot is missing"
        )
    intake_source = cast(dict[str, object], _plain(intake))
    intake_source.pop("intake_canonical_hash", None)
    try:
        validated_intake = validate_intake(intake_source)
    except IntakeError as exc:
        raise RealCaseLearningV2Error(
            "CASE_INTAKE_CONTRACT_INVALID", str(exc)
        ) from exc
    if validated_intake != intake:
        raise RealCaseLearningV2Error(
            "CASE_INTAKE_CONTRACT_INVALID",
            "intake snapshot canonical hash or semantics changed after intake",
        )
    consent = cast(Mapping[str, object], validated_intake["consent"])
    expected_consent = {
        "status": consent["consent_status"],
        "research_use_allowed": consent["research_use_allowed"],
        "benchmark_use_allowed": consent["benchmark_use_allowed"],
        "withdrawal_supported": consent["withdrawal_supported"],
    }
    if case.get("consent") != expected_consent:
        raise RealCaseLearningV2Error(
            "CASE_CONSENT_CONTRACT_INVALID",
            "case consent projection diverges from the validated intake snapshot",
        )
    scenarios = validated_intake.get("scenarios")
    scenario_ids = {
        str(item.get("scenario_id"))
        for item in cast(list[object], scenarios)
        if isinstance(item, Mapping)
    }
    if (
        case.get("person_case_id") != validated_intake.get("person_case_id")
        or case.get("scenario_id") not in scenario_ids
    ):
        raise RealCaseLearningV2Error(
            "CASE_INTAKE_CONTRACT_INVALID",
            "case identity diverges from the validated intake snapshot",
        )
    metadata = cast(Mapping[str, object], validated_intake["case_metadata"])
    birth = cast(Mapping[str, object], validated_intake["birth_input"])
    provenance = (
        str(metadata.get("collection_channel", "")),
        str(metadata.get("source_provenance", "")),
        str(birth.get("source", "")),
    )
    if any("synthetic" in item.casefold() for item in provenance) and case.get(
        "synthetic"
    ) is not True:
        raise RealCaseLearningV2Error(
            "CASE_SYNTHETIC_CONTRACT_INVALID",
            "synthetic intake provenance cannot be relabelled as a real case",
        )


def _validate_v2_review_records(
    case: Mapping[str, object], dependency_hashes: set[str]
) -> None:
    checks = {
        "adjudications": lambda item: item.get("operator_review_required") is True,
        "revisions": lambda item: item.get("review_state")
        == "pending_operator_review"
        and item.get("applied") is False,
        "benchmark_comparisons": lambda item: item.get("prediction_validity")
        == PREDICTION_VALIDITY,
        "rule_recommendations": lambda item: item.get("review_state")
        == "pending_operator_review"
        and item.get("applied_to_rules") is False,
        "negative_case_archive": lambda item: item.get("review_state")
        == "pending_operator_review"
        and item.get("accuracy_eligible") is False,
    }
    for field, safe in checks.items():
        records = case.get(field)
        if not isinstance(records, list):
            raise RealCaseLearningV2Error(
                "CASE_REVIEW_CONTRACT_INVALID", f"{field} must be an array"
            )
        for item in records:
            if (
                not isinstance(item, Mapping)
                or not _verify_sealed_record(item)
                or item.get("canonical_hash") not in dependency_hashes
                or not safe(item)
            ):
                raise RealCaseLearningV2Error(
                    "CASE_REVIEW_CONTRACT_INVALID",
                    f"{field} contains an unsafe or unbound review record",
                )


def _validate_v2_case_semantics(case: Mapping[str, object]) -> None:
    _validate_v2_case_intake(case)
    prediction = case.get("prediction_snapshot")
    if not isinstance(prediction, Mapping):
        raise RealCaseLearningV2Error(
            "CASE_PREDICTION_CONTRACT_INVALID", "prediction snapshot is missing"
        )
    _validate_v2_prediction_snapshot(prediction)
    generated = _parse_time(
        prediction.get("generated_at"),
        code="CASE_PREDICTION_CONTRACT_INVALID",
        field="prediction.generated_at",
    )
    frozen_at = _parse_time(
        prediction.get("freeze_timestamp"),
        code="CASE_PREDICTION_CONTRACT_INVALID",
        field="prediction.freeze_timestamp",
    )
    dependency_hashes = case.get("dependency_hashes")
    if not isinstance(dependency_hashes, list) or prediction.get(
        "canonical_hash"
    ) not in dependency_hashes:
        raise RealCaseLearningV2Error(
            "CASE_PREDICTION_CONTRACT_INVALID",
            "prediction snapshot hash is not bound into case dependencies",
        )
    dependency_hash_set = {str(item) for item in dependency_hashes}
    intake_snapshot = cast(Mapping[str, object], case["intake_snapshot"])
    if intake_snapshot.get("intake_canonical_hash") not in dependency_hash_set:
        raise RealCaseLearningV2Error(
            "CASE_INTAKE_CONTRACT_INVALID",
            "intake snapshot hash is not bound into case dependencies",
        )
    for field, record_type in (
        ("chart_snapshot", "RealCaseChartSnapshotV2"),
        ("original_question_snapshot", "OriginalQuestionSnapshotV2"),
        ("prediction_time_reality_snapshot", "PredictionTimeRealitySnapshotV2"),
    ):
        snapshot = case.get(field)
        if (
            not isinstance(snapshot, Mapping)
            or snapshot.get("record_type") != record_type
            or snapshot.get("freeze_status") != "frozen"
            or not _verify_sealed_record(snapshot)
            or snapshot.get("canonical_hash") not in dependency_hash_set
        ):
            raise RealCaseLearningV2Error(
                "CASE_SNAPSHOT_CONTRACT_INVALID",
                f"{field} is not a frozen dependency-bound V2 snapshot",
            )
    reality_snapshot = cast(
        Mapping[str, object], case["prediction_time_reality_snapshot"]
    )
    if _parse_time(
        reality_snapshot.get("known_at"),
        code="CASE_SNAPSHOT_CONTRACT_INVALID",
        field="prediction_time_reality_snapshot.known_at",
    ) > generated:
        raise RealCaseLearningV2Error(
            "CASE_SNAPSHOT_CONTRACT_INVALID",
            "prediction-time reality snapshot contains future information",
        )
    expected_case_seed = digest(
        {
            "person_case_id": case.get("person_case_id"),
            "scenario_id": case.get("scenario_id"),
            "prediction_id": prediction.get("prediction_id"),
        }
    )
    if case.get("case_id") != f"case:{expected_case_seed[7:]}":
        raise RealCaseLearningV2Error(
            "CASE_IDENTITY_CONTRACT_INVALID", "case_id diverges from frozen identity"
        )
    chart = cast(Mapping[str, object], case["chart_snapshot"])
    question = cast(Mapping[str, object], case["original_question_snapshot"])
    claims = prediction.get("structured_claims")
    assert isinstance(claims, list)
    expected_fingerprint = digest(
        {
            "person_case_id": case.get("person_case_id"),
            "prediction_id": prediction.get("prediction_id"),
            "chart_snapshot_hash": chart.get("canonical_hash"),
            "question_snapshot_hash": question.get("canonical_hash"),
            "claim_windows": sorted(
                (
                    str(item["claim_id"]),
                    str(item["scope"]),
                    str(item.get("time_window", "")),
                )
                for item in claims
                if isinstance(item, Mapping)
            ),
        }
    )
    if case.get("derived_fingerprint") != expected_fingerprint:
        raise RealCaseLearningV2Error(
            "CASE_IDENTITY_CONTRACT_INVALID",
            "derived fingerprint diverges from frozen case dependencies",
        )
    _validate_v2_review_records(case, dependency_hash_set)
    for relation, field, expected_fields in (
        ("prior", "prior_event_validations", _PRIOR_EVIDENCE_ENTRY_FIELDS),
        ("future", "future_outcomes", _FUTURE_EVIDENCE_ENTRY_FIELDS),
    ):
        entries = case.get(field)
        if not isinstance(entries, list):
            raise RealCaseLearningV2Error(
                "CASE_EVIDENCE_CONTRACT_INVALID", f"{field} must be an array"
            )
        for entry in entries:
            if (
                not isinstance(entry, Mapping)
                or set(entry) != expected_fields
                or entry.get("record_type")
                != (
                    "PriorEventValidationV2"
                    if relation == "prior"
                    else "FutureOutcomeV2"
                )
                or not _verify_sealed_record(entry)
            ):
                raise RealCaseLearningV2Error(
                    "CASE_EVIDENCE_CONTRACT_INVALID",
                    f"{relation} evidence entry is not a closed hash-valid V2 record",
                )
            snapshot = entry.get("evidence_snapshot")
            if not isinstance(snapshot, Mapping):
                raise RealCaseLearningV2Error(
                    "CASE_EVIDENCE_CONTRACT_INVALID",
                    f"{relation} evidence snapshot is missing",
                )
            _validate_v2_reality_evidence_snapshot(snapshot)
            matching_fields = (
                "evidence_id",
                "claim_id",
                "scope",
                "event_window",
                "observed_at",
                "collected_at",
            )
            if (
                any(entry.get(key) != snapshot.get(key) for key in matching_fields)
                or snapshot.get("person_case_id") != case.get("person_case_id")
                or snapshot.get("scenario_id") != case.get("scenario_id")
                or snapshot.get("synthetic") is not case.get("synthetic")
                or entry.get("canonical_hash") not in dependency_hashes
            ):
                raise RealCaseLearningV2Error(
                    "CASE_EVIDENCE_CONTRACT_INVALID",
                    f"{relation} evidence top-level and frozen boundaries diverge",
                )
            observed = _parse_time(
                snapshot.get("observed_at"),
                code="CASE_EVIDENCE_CONTRACT_INVALID",
                field=f"{relation}.observed_at",
            )
            collected = _parse_time(
                snapshot.get("collected_at"),
                code="CASE_EVIDENCE_CONTRACT_INVALID",
                field=f"{relation}.collected_at",
            )
            window_start, window_end = _parse_event_window(
                snapshot.get("event_window"),
                code="CASE_EVIDENCE_CONTRACT_INVALID",
            )
            if collected < observed:
                raise RealCaseLearningV2Error(
                    "CASE_EVIDENCE_CONTRACT_INVALID",
                    f"{relation} evidence collection precedes observation",
                )
            if relation == "prior" and (
                observed < window_start
                or observed > generated
                or collected > generated
                or window_end > generated
            ):
                raise RealCaseLearningV2Error(
                    "CASE_EVIDENCE_CONTRACT_INVALID",
                    "prior evidence escapes the prediction-time boundary",
                )
            if relation == "future" and (
                observed <= frozen_at
                or window_start <= frozen_at
                or observed < window_start
            ):
                raise RealCaseLearningV2Error(
                    "CASE_EVIDENCE_CONTRACT_INVALID",
                    "future evidence escapes its frozen temporal boundary",
                )
            if relation == "future":
                resolution = entry.get("reality_resolution")
                if not isinstance(resolution, Mapping) or any(
                    resolution.get(key) != entry.get(key)
                    for key in ("claim_id", "scope")
                ) or (
                    snapshot.get("verified") is True
                    and resolution.get("hard_override_direction")
                    != snapshot.get("direction")
                ):
                    raise RealCaseLearningV2Error(
                        "CASE_EVIDENCE_CONTRACT_INVALID",
                        "future evidence resolution diverges from claim and scope",
                    )
    _validate_schema(
        case,
        schema_name="real_case_learning_v2_case.schema.json",
        code="CASE_SCHEMA_INVALID",
    )
    has_review = any(
        cast(list[object], case[field])
        for field in (
            "adjudications",
            "revisions",
            "benchmark_comparisons",
            "rule_recommendations",
            "negative_case_archive",
        )
    )
    if has_review and case.get("lifecycle_status") != "pending_operator_review":
        raise RealCaseLearningV2Error(
            "CASE_LIFECYCLE_CONTRACT_INVALID",
            "case lifecycle diverges from its frozen evidence and review records",
        )


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
    _validate_v2_case_semantics(payload)
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
    _validate_prediction_contract(prediction_payload)
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
        prediction_frozen = freeze_prediction(
            prediction_payload, frozen_at=frozen_at
        )
    except FreezeError as exc:
        raise RealCaseLearningV2Error("PREDICTION_REJECTED", str(exc)) from exc
    try:
        _validate_v2_prediction_snapshot(prediction_frozen)
    except RealCaseLearningV2Error as exc:
        raise RealCaseLearningV2Error(
            "PREDICTION_FREEZE_INVALID", exc.message
        ) from exc

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
    _validate_reality_evidence_contract(payload)
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
    try:
        _validate_v2_reality_evidence_snapshot(frozen)
    except RealCaseLearningV2Error as exc:
        raise RealCaseLearningV2Error(
            "REALITY_EVIDENCE_HASH_INVALID", exc.message
        ) from exc
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
    window_start, window_end = event_window
    if window_end > generated:
        raise RealCaseLearningV2Error(
            "PRIOR_EVENT_WINDOW_NOT_PRIOR",
            "prior-event window must end before prediction generation",
        )
    if observed < window_start:
        raise RealCaseLearningV2Error(
            "PRIOR_EVENT_BEFORE_WINDOW",
            "prior-event observation cannot precede its frozen event window",
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
    outcomes = cast(list[object], result["future_outcomes"])
    if any(
        isinstance(item, Mapping)
        and item.get("evidence_id") == entry["evidence_id"]
        for item in outcomes
    ):
        raise RealCaseLearningV2Error(
            "DUPLICATE_EVIDENCE", "future outcome evidence_id already exists"
        )
    for item in outcomes:
        if not isinstance(item, Mapping):
            continue
        existing = item.get("evidence_snapshot")
        if (
            isinstance(existing, Mapping)
            and existing.get("claim_id") == payload.get("claim_id")
            and existing.get("scope") == payload.get("scope")
            and existing.get("verified") is True
            and payload.get("verified") is True
            and existing.get("direction") != payload.get("direction")
        ):
            raise RealCaseLearningV2Error(
                "CONFLICTING_REALITY_EVIDENCE",
                "opposite verified outcomes for one claim and scope require operator reconciliation",
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
        or not verify_temporal_partition_manifest(partition_manifest)
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
    case_dependencies = partition_manifest.get("case_dependency_hashes")
    case_inputs = partition_manifest.get("case_partition_inputs")
    case_id = str(result["case_id"])
    cutoff = _parse_time(
        partition_manifest.get("cutoff_at"),
        code="PARTITION_CASE_STALE",
        field="partition.cutoff_at",
    )
    if (
        not isinstance(case_dependencies, Mapping)
        or not isinstance(case_inputs, Mapping)
        or case_dependencies.get(case_id) != case.get("canonical_hash")
        or case_inputs.get(case_id) != _partition_input(case, cutoff=cutoff)
    ):
        raise RealCaseLearningV2Error(
            "PARTITION_CASE_STALE",
            "partition provenance does not match the current adjudicated case",
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


def _event_window_bounds(value: object) -> tuple[datetime, datetime]:
    if not isinstance(value, str) or value.count("/") != 1:
        raise RealCaseLearningV2Error(
            "TEMPORAL_BOUNDARY_MISSING", "event_window must have start/end"
        )
    start_raw, end_raw = value.split("/", 1)
    start = _parse_time(
        start_raw, code="TEMPORAL_BOUNDARY_MISSING", field="event_window.start"
    )
    end = _parse_time(
        end_raw, code="TEMPORAL_BOUNDARY_MISSING", field="event_window.end"
    )
    if end < start:
        raise RealCaseLearningV2Error(
            "TEMPORAL_BOUNDARY_MISSING", "event_window end precedes start"
        )
    return start, end


def _event_window_end(value: object) -> datetime:
    return _event_window_bounds(value)[1]


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _collect_hashes(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return {
            str(item)
            for key, item in value.items()
            if key == "canonical_hash"
            and isinstance(item, str)
            and _SHA256.fullmatch(item)
        } | set().union(*(_collect_hashes(item) for item in value.values()))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return set().union(*(_collect_hashes(item) for item in value))
    return set()


def _validate_v2_withdrawal_tombstone(payload: Mapping[str, object]) -> None:
    _validate_schema(
        payload,
        schema_name="real_case_learning_v2_withdrawal.schema.json",
        code="WITHDRAWAL_CONTRACT_INVALID",
    )
    _parse_time(
        payload.get("withdrawn_at"),
        code="WITHDRAWAL_CONTRACT_INVALID",
        field="withdrawn_at",
    )
    invalidated = payload.get("invalidated_dependency_hashes")
    if (
        not isinstance(invalidated, list)
        or invalidated != sorted(set(str(item) for item in invalidated))
        or any(_SHA256.fullmatch(str(item)) is None for item in invalidated)
    ):
        raise RealCaseLearningV2Error(
            "WITHDRAWAL_CONTRACT_INVALID",
            "invalidated dependency hashes must be non-empty, unique, and canonical",
        )


def _verified_for_partition(case: Mapping[str, object]) -> dict[str, object]:
    payload = cast(dict[str, object], _plain(case))
    ingested_at = payload.pop("ingested_at", None)
    if ingested_at is not None and not verify_learning_record(payload):
        raise RealCaseLearningV2Error("CASE_HASH_INVALID", "case changed outside ignored ingestion metadata")
    if ingested_at is None and not verify_learning_record(payload):
        raise RealCaseLearningV2Error("CASE_HASH_INVALID", "case hash is invalid")
    if payload.get("record_type") == "RealCaseLearningV2Case":
        _validate_v2_case_semantics(payload)
    elif payload.get("record_type") == "RealCaseLearningV2Withdrawal":
        _validate_v2_withdrawal_tombstone(payload)
    return payload


def _partition_input(
    case: Mapping[str, object], *, cutoff: datetime
) -> dict[str, object]:
    outcomes = [
        item
        for item in cast(list[object], case.get("future_outcomes", []))
        if isinstance(item, Mapping)
    ]
    if not outcomes:
        raise RealCaseLearningV2Error(
            "TEMPORAL_BOUNDARY_MISSING",
            "partitioning requires at least one future outcome",
        )
    available_at = max(
        _parse_time(
            item.get("collected_at"),
            code="TEMPORAL_BOUNDARY_MISSING",
            field="collected_at",
        )
        for item in outcomes
    )
    observed_at = max(
        _parse_time(
            item.get("observed_at"),
            code="TEMPORAL_BOUNDARY_MISSING",
            field="observed_at",
        )
        for item in outcomes
    )
    event_end = max(
        _event_window_end(item.get("event_window")) for item in outcomes
    )
    return {
        "person_case_id": str(case["person_case_id"]),
        "prediction_id": str(
            cast(Mapping[str, object], case["prediction_snapshot"])[
                "prediction_id"
            ]
        ),
        "event_windows": sorted(
            set(str(item["event_window"]) for item in outcomes)
        ),
        "available_at": _utc_iso(available_at),
        "observed_at": _utc_iso(observed_at),
        "event_window_end": _utc_iso(event_end),
        "derived_fingerprint": str(case["derived_fingerprint"]),
        "near_duplicate_fingerprint": str(case["near_duplicate_fingerprint"]),
        "base_assignment": (
            "train"
            if max(available_at, observed_at, event_end) < cutoff
            else "test"
        ),
    }


def _partition_assignments(
    metadata: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    base = {
        case_id: str(value["base_assignment"])
        for case_id, value in metadata.items()
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
                or left_meta["derived_fingerprint"]
                == right_meta["derived_fingerprint"]
                or left_meta["near_duplicate_fingerprint"]
                == right_meta["near_duplicate_fingerprint"]
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
    return base, assignment, sorted(forced_test)


def _partition_corpus_hash(
    *,
    case_dependency_hashes: Mapping[str, object],
    case_partition_inputs: Mapping[str, object],
    withdrawn_case_refs: Sequence[object],
    withdrawal_dependency_hashes: Sequence[object],
) -> str:
    return digest(
        {
            "case_dependency_hashes": dict(case_dependency_hashes),
            "case_partition_inputs": dict(case_partition_inputs),
            "withdrawn_case_refs": sorted(str(item) for item in withdrawn_case_refs),
            "withdrawal_dependency_hashes": sorted(
                str(item) for item in withdrawal_dependency_hashes
            ),
        }
    )


def verify_temporal_partition_manifest(manifest: Mapping[str, object]) -> bool:
    try:
        if (
            set(manifest) != _PARTITION_MANIFEST_FIELDS
            or manifest.get("record_type") != "RealCaseLearningV2PartitionManifest"
            or manifest.get("schema_version") != PARTITION_SCHEMA_VERSION
            or manifest.get("assignment_basis") != "event_and_observation_time"
            or manifest.get("ingestion_order_used") is not False
            or manifest.get("leakage_detected") is not False
            or manifest.get("leakage_prevention")
            != "duplicate_components_use_test_partition"
            or not verify_learning_record(manifest)
        ):
            return False
        list_fields = (
            "base_train_case_ids",
            "base_test_case_ids",
            "train_case_ids",
            "test_case_ids",
            "forced_test_case_ids",
            "withdrawn_case_refs",
            "synthetic_case_ids",
            "accuracy_eligible_case_ids",
            "withdrawal_dependency_hashes",
            "dependency_hashes",
        )
        if any(not _string_list(manifest.get(field)) for field in list_fields):
            return False
        if any(
            cast(list[str], manifest[field])
            != sorted(set(cast(list[str], manifest[field])))
            for field in list_fields
        ):
            return False
        if manifest.get("deduplication_keys") != [
            "person_case_id",
            "prediction_id",
            "derived_fingerprint",
            "near_duplicate_fingerprint",
        ]:
            return False
        cutoff = _parse_time(
            manifest.get("cutoff_at"),
            code="TEMPORAL_BOUNDARY_MISSING",
            field="cutoff_at",
        )
        base_train = set(cast(list[str], manifest["base_train_case_ids"]))
        base_test = set(cast(list[str], manifest["base_test_case_ids"]))
        train = set(cast(list[str], manifest["train_case_ids"]))
        test = set(cast(list[str], manifest["test_case_ids"]))
        forced = set(cast(list[str], manifest["forced_test_case_ids"]))
        synthetic = set(cast(list[str], manifest["synthetic_case_ids"]))
        withdrawn = set(cast(list[str], manifest["withdrawn_case_refs"]))
        case_dependencies = manifest.get("case_dependency_hashes")
        case_inputs = manifest.get("case_partition_inputs")
        if not isinstance(case_dependencies, Mapping) or not isinstance(
            case_inputs, Mapping
        ):
            return False
        dependency_cases = set(str(key) for key in case_dependencies)
        if set(str(key) for key in case_inputs) != dependency_cases:
            return False
        normalized_inputs: dict[str, Mapping[str, object]] = {}
        for case_id, value in case_inputs.items():
            if not isinstance(value, Mapping) or set(value) != _PARTITION_INPUT_FIELDS:
                return False
            event_windows = value.get("event_windows")
            if (
                not _string_list(event_windows)
                or cast(list[str], event_windows)
                != sorted(set(cast(list[str], event_windows)))
                or not cast(list[str], event_windows)
                or not isinstance(value.get("person_case_id"), str)
                or _PERSON_CASE_ID.fullmatch(str(value["person_case_id"])) is None
                or not isinstance(value.get("prediction_id"), str)
                or not value.get("prediction_id")
                or value.get("base_assignment") not in {"train", "test"}
                or any(
                    not isinstance(value.get(field), str)
                    or _SHA256.fullmatch(str(value[field])) is None
                    for field in (
                        "derived_fingerprint",
                        "near_duplicate_fingerprint",
                    )
                )
            ):
                return False
            available_at = _parse_time(
                value.get("available_at"),
                code="TEMPORAL_BOUNDARY_MISSING",
                field="available_at",
            )
            observed_at = _parse_time(
                value.get("observed_at"),
                code="TEMPORAL_BOUNDARY_MISSING",
                field="observed_at",
            )
            event_end = _parse_time(
                value.get("event_window_end"),
                code="TEMPORAL_BOUNDARY_MISSING",
                field="event_window_end",
            )
            declared_windows = [
                _event_window_bounds(item)
                for item in cast(list[str], event_windows)
            ]
            if (
                event_end != max(end for _, end in declared_windows)
                or available_at < observed_at
                or observed_at < min(start for start, _ in declared_windows)
            ):
                return False
            expected_base = (
                "train"
                if max(available_at, observed_at, event_end) < cutoff
                else "test"
            )
            if value.get("base_assignment") != expected_base:
                return False
            normalized_inputs[str(case_id)] = value
        recomputed_base, recomputed_assignment, recomputed_forced = (
            _partition_assignments(normalized_inputs)
        )
        expected_base_train = sorted(
            key for key, value in recomputed_base.items() if value == "train"
        )
        expected_base_test = sorted(
            key for key, value in recomputed_base.items() if value == "test"
        )
        expected_train = sorted(
            key for key, value in recomputed_assignment.items() if value == "train"
        )
        expected_test = sorted(
            key for key, value in recomputed_assignment.items() if value == "test"
        )
        if (
            any(_CASE_ID.fullmatch(case_id) is None for case_id in dependency_cases)
            or any(
                not isinstance(value, str) or _SHA256.fullmatch(value) is None
                for value in case_dependencies.values()
            )
            or base_train & base_test
            or train & test
            or cast(list[str], manifest["base_train_case_ids"])
            != expected_base_train
            or cast(list[str], manifest["base_test_case_ids"])
            != expected_base_test
            or cast(list[str], manifest["train_case_ids"]) != expected_train
            or cast(list[str], manifest["test_case_ids"]) != expected_test
            or cast(list[str], manifest["forced_test_case_ids"])
            != recomputed_forced
            or base_train | base_test != dependency_cases
            or train | test != dependency_cases
            or not forced <= base_train
            or train != base_train - forced
            or test != base_test | forced
            or not synthetic <= dependency_cases
            or any(
                digest({"case_id": case_id}) in withdrawn
                for case_id in dependency_cases
            )
            or cast(list[object], manifest["accuracy_eligible_case_ids"])
            or any(
                _SHA256.fullmatch(value) is None
                for value in cast(list[str], manifest["withdrawn_case_refs"])
            )
            or len(cast(list[str], manifest["withdrawn_case_refs"]))
            != len(cast(list[str], manifest["withdrawal_dependency_hashes"]))
        ):
            return False
        withdrawal_dependencies = cast(
            list[str], manifest["withdrawal_dependency_hashes"]
        )
        dependency_hashes = cast(list[str], manifest["dependency_hashes"])
        expected_dependencies = sorted(
            set(str(value) for value in case_dependencies.values())
            | set(withdrawal_dependencies)
        )
        if (
            any(_SHA256.fullmatch(value) is None for value in withdrawal_dependencies)
            or dependency_hashes != expected_dependencies
            or manifest.get("corpus_hash")
            != _partition_corpus_hash(
                case_dependency_hashes=case_dependencies,
                case_partition_inputs=case_inputs,
                withdrawn_case_refs=cast(list[object], manifest["withdrawn_case_refs"]),
                withdrawal_dependency_hashes=withdrawal_dependencies,
            )
        ):
            return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def build_temporal_partitions(
    cases: Sequence[Mapping[str, object]],
    *,
    cutoff_at: str,
    trusted_withdrawal_hashes: Sequence[str] = (),
) -> dict[str, object]:
    cutoff = _parse_time(cutoff_at, code="TEMPORAL_BOUNDARY_MISSING", field="cutoff_at")
    if isinstance(trusted_withdrawal_hashes, (str, bytes)) or any(
        not isinstance(item, str) or _SHA256.fullmatch(item) is None
        for item in trusted_withdrawal_hashes
    ):
        raise RealCaseLearningV2Error(
            "WITHDRAWAL_TRUST_INVALID",
            "trusted withdrawal registry must contain canonical tombstone hashes",
        )
    trusted_withdrawals = set(trusted_withdrawal_hashes)
    if len(trusted_withdrawals) != len(trusted_withdrawal_hashes):
        raise RealCaseLearningV2Error(
            "WITHDRAWAL_TRUST_INVALID",
            "trusted withdrawal registry cannot contain duplicates",
        )
    candidates: list[dict[str, object]] = []
    tombstones: dict[str, dict[str, object]] = {}
    for case in cases:
        payload = _verified_for_partition(case)
        if payload.get("record_type") == "RealCaseLearningV2Withdrawal":
            case_ref = str(payload["case_ref_hash"])
            if case_ref in tombstones:
                raise RealCaseLearningV2Error(
                    "DUPLICATE_WITHDRAWAL",
                    "only one withdrawal tombstone is accepted per case reference",
                )
            tombstones[case_ref] = payload
            continue
        if payload.get("record_type") != "RealCaseLearningV2Case":
            raise RealCaseLearningV2Error("UNSUPPORTED_CASE_SCHEMA", "partition input is not a V2 case")
        candidates.append(payload)

    candidate_ids = [str(item["case_id"]) for item in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise RealCaseLearningV2Error(
            "DUPLICATE_CASE", "partition input contains a duplicate case_id"
        )
    active: list[dict[str, object]] = []
    matched_withdrawal_refs: set[str] = set()
    for payload in candidates:
        case_ref = digest({"case_id": payload["case_id"]})
        tombstone = tombstones.get(case_ref)
        if tombstone is None:
            active.append(payload)
            continue
        matched_withdrawal_refs.add(case_ref)
        expected_invalidated = sorted(
            set(_dependency_hashes(payload, payload.get("canonical_hash")))
            | _collect_hashes(payload)
        )
        prediction = cast(Mapping[str, object], payload["prediction_snapshot"])
        if (
            tombstone.get("person_ref_hash")
            != digest({"person_case_id": payload["person_case_id"]})
            or tombstone.get("synthetic") is not payload.get("synthetic")
            or tombstone.get("invalidated_dependency_hashes")
            != expected_invalidated
            or _parse_time(
                tombstone.get("withdrawn_at"),
                code="WITHDRAWAL_CONTRACT_INVALID",
                field="withdrawn_at",
            )
            < _parse_time(
                prediction.get("freeze_timestamp"),
                code="WITHDRAWAL_CONTRACT_INVALID",
                field="prediction.freeze_timestamp",
            )
        ):
            raise RealCaseLearningV2Error(
                "WITHDRAWAL_CONTRACT_INVALID",
                "withdrawal tombstone does not bind the matching case and dependencies",
            )
    unbound_tombstones = [
        item
        for case_ref, item in tombstones.items()
        if case_ref not in matched_withdrawal_refs
        and item.get("canonical_hash") not in trusted_withdrawals
    ]
    if unbound_tombstones:
        raise RealCaseLearningV2Error(
            "WITHDRAWAL_TRUST_REQUIRED",
            "standalone withdrawal tombstones require an explicit trusted registry proof",
        )

    withdrawn_refs = sorted(tombstones)
    withdrawal_dependency_hashes = sorted(
        str(item["canonical_hash"]) for item in tombstones.values()
    )

    metadata: dict[str, dict[str, object]] = {}
    for case in active:
        case_id = str(case["case_id"])
        metadata[case_id] = _partition_input(case, cutoff=cutoff)

    base, assignment, forced_test = _partition_assignments(metadata)
    train_ids = sorted(item for item, partition in assignment.items() if partition == "train")
    test_ids = sorted(item for item, partition in assignment.items() if partition == "test")
    synthetic_ids = sorted(str(item["case_id"]) for item in active if item.get("synthetic") is True)
    base_train_ids = sorted(item for item, partition in base.items() if partition == "train")
    base_test_ids = sorted(item for item, partition in base.items() if partition == "test")
    case_dependency_hashes = {
        str(item["case_id"]): str(item["canonical_hash"])
        for item in sorted(active, key=lambda value: str(value["case_id"]))
    }
    dependency_hashes = sorted(
        set(case_dependency_hashes.values()) | set(withdrawal_dependency_hashes)
    )
    body = {
        "record_type": "RealCaseLearningV2PartitionManifest",
        "schema_version": PARTITION_SCHEMA_VERSION,
        "cutoff_at": cutoff_at,
        "assignment_basis": "event_and_observation_time",
        "ingestion_order_used": False,
        "deduplication_keys": [
            "person_case_id",
            "prediction_id",
            "derived_fingerprint",
            "near_duplicate_fingerprint",
        ],
        "base_train_case_ids": base_train_ids,
        "base_test_case_ids": base_test_ids,
        "train_case_ids": train_ids,
        "test_case_ids": test_ids,
        "forced_test_case_ids": sorted(forced_test),
        "withdrawn_case_refs": withdrawn_refs,
        "synthetic_case_ids": synthetic_ids,
        "accuracy_eligible_case_ids": [],
        "case_dependency_hashes": case_dependency_hashes,
        "case_partition_inputs": metadata,
        "withdrawal_dependency_hashes": withdrawal_dependency_hashes,
        "dependency_hashes": dependency_hashes,
        "corpus_hash": _partition_corpus_hash(
            case_dependency_hashes=case_dependency_hashes,
            case_partition_inputs=metadata,
            withdrawn_case_refs=withdrawn_refs,
            withdrawal_dependency_hashes=withdrawal_dependency_hashes,
        ),
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
    withdrawal_time = _parse_time(
        withdrawn_at, code="WITHDRAWAL_TIME_INVALID", field="withdrawn_at"
    )
    prediction = cast(Mapping[str, object], payload["prediction_snapshot"])
    if withdrawal_time < _parse_time(
        prediction.get("freeze_timestamp"),
        code="WITHDRAWAL_TIME_INVALID",
        field="prediction.freeze_timestamp",
    ):
        raise RealCaseLearningV2Error(
            "WITHDRAWAL_TIME_INVALID",
            "withdrawal cannot precede the frozen case it invalidates",
        )

    dependencies = sorted(
        set(_dependency_hashes(payload, case.get("canonical_hash")))
        | _collect_hashes(case)
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
    "verify_temporal_partition_manifest",
    "record_future_outcome",
    "record_prior_event_validation",
    "summarize_learning_cases",
    "verify_learning_record",
    "withdraw_case",
]
