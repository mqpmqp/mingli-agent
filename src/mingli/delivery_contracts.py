from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from .contracts.serialization import digest


QUESTION_DOMAINS = (
    "finance",
    "relationship",
    "exam_education",
    "civil_service_and_public_institution",
    "career",
    "health",
    "fengshui",
    "migration",
    "art_and_skill",
)
RENDER_INTENTS = ("focused_question", "follow_up", "comment", "full_reading")
CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})

_DOMAIN_ALIASES = {
    "wealth": "finance",
    "career_exam": "civil_service_and_public_institution",
    "relationship_reunion": "relationship",
}
_STEMS = "甲乙丙丁戊己庚辛壬癸"
_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
_SEXAGENARY = frozenset(
    _STEMS[index % 10] + _BRANCHES[index % 12] for index in range(60)
)

REALITY_FIELDS = frozenset(
    {
        "relationship_status",
        "contact_status",
        "other_party_status",
        "user_marital_status",
        "other_party_marital_status",
        "other_party_new_relationship",
        "new_partner_present",
        "no_contact_months",
        "both_willing",
        "breakup_reason",
        "explicit_rejection",
        "legal_contact_restriction",
        "safety_risk",
        "root_cause_resolved",
        "family_opposition",
        "distance_plan_confirmed",
        "communication_quality",
        "career_status",
        "education",
        "major",
        "major_eligible",
        "age_eligible",
        "degree_eligible",
        "hukou_eligible",
        "fresh_graduate_eligible",
        "job_requirements_met",
        "exam_stage",
        "exam_scores",
        "mock_score",
        "mock_rank",
        "attempt_count",
        "preparation_months",
        "target_positions",
        "recruitment_target",
        "target_job_competition",
        "income_stability",
        "capital_level",
        "cash_runway_months",
        "cashflow_status",
        "customer_validation",
        "contract_leverage",
        "financial_risk",
        "borrowing_for_ritual",
        "symptoms",
        "medical_assessment",
        "floor_plan_confirmed",
        "compass_measurement_confirmed",
        "property_location_confirmed",
        "residence_type",
        "migration_destination",
        "visa_status",
        "language_readiness",
        "portfolio_status",
        "practice_hours",
        "skill_level",
        "explicit_metaphysical_request",
        "ritual_interest",
        "requested_advice",
    }
)


class InputContractError(ValueError):
    """Raised when a payload is structurally unsafe to normalize."""


class PaidTier(str, Enum):
    COMMENT = "comment"
    PRIVATE = "private"
    PAID_699 = "paid_699"


class EvidenceQuality(str, Enum):
    UNKNOWN = "unknown"
    SELF_REPORTED = "self_reported"
    DOCUMENTED = "documented"
    VERIFIED_REALITY = "verified_reality"


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputContractError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, field_name)


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise InputContractError(f"{field_name} must be an array of strings")
    result = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise InputContractError(f"{field_name} must contain non-empty strings")
    return tuple(item.strip() for item in result)


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InputContractError(f"{field_name} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise InputContractError(f"{field_name} keys must be strings")
    return value


def _enum_value(enum_type: type[Enum], value: object, field_name: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        choices = ", ".join(item.value for item in enum_type)
        raise InputContractError(f"{field_name} must be one of: {choices}") from exc


@dataclass(frozen=True, slots=True)
class BirthInput:
    gender: str | None = None
    calendar: str | None = None
    birth_date: str | None = None
    birth_time: str | None = None
    timezone: str | None = None
    birth_location: Mapping[str, object] | None = None
    true_solar_time: bool = False
    source: str = "user"
    confirmation_status: str = "not_required"
    pillars: Mapping[str, str] | None = None
    is_leap_month: bool = False
    fold: int = 0

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "BirthInput":
        value = dict(_mapping(raw, "birth"))
        allowed = {
            "gender",
            "calendar",
            "birth_date",
            "birth_time",
            "timezone",
            "birth_location",
            "true_solar_time",
            "solar_time_adjustment",
            "source",
            "confirmation_status",
            "pillars",
            "is_leap_month",
            "fold",
        }
        unknown = set(value) - allowed
        if unknown:
            raise InputContractError(
                "birth contains unknown fields: " + ", ".join(sorted(unknown))
            )

        source = str(value.get("source", "user"))
        if source not in {
            "user",
            "image_confirmed",
            "text_confirmed",
            "external_calculator",
        }:
            raise InputContractError("birth.source is unsupported")
        default_confirmation = (
            "pending" if source in {"image_confirmed", "text_confirmed"} else "not_required"
        )
        confirmation_status = str(
            value.get("confirmation_status", default_confirmation)
        )
        if confirmation_status not in {"not_required", "pending", "confirmed", "rejected"}:
            raise InputContractError("birth.confirmation_status is unsupported")

        location: Mapping[str, object] | None = None
        if value.get("birth_location") is not None:
            location = MappingProxyType(
                dict(_mapping(value["birth_location"], "birth.birth_location"))
            )

        pillars: Mapping[str, str] | None = None
        if value.get("pillars") is not None:
            raw_pillars = _mapping(value["pillars"], "birth.pillars")
            normalized: dict[str, str] = {}
            for position in ("year", "month", "day", "hour"):
                if position in raw_pillars:
                    normalized[position] = _non_empty_string(
                        raw_pillars[position], f"birth.pillars.{position}"
                    )
            unknown_pillars = set(raw_pillars) - {"year", "month", "day", "hour"}
            if unknown_pillars:
                raise InputContractError(
                    "birth.pillars contains unknown fields: "
                    + ", ".join(sorted(unknown_pillars))
                )
            pillars = MappingProxyType(normalized)

        true_solar_time = value.get(
            "true_solar_time", value.get("solar_time_adjustment", False)
        )
        if not isinstance(true_solar_time, bool):
            raise InputContractError("birth.true_solar_time must be boolean")
        is_leap_month = value.get("is_leap_month", False)
        if not isinstance(is_leap_month, bool):
            raise InputContractError("birth.is_leap_month must be boolean")
        fold = value.get("fold", 0)
        if fold not in {0, 1}:
            raise InputContractError("birth.fold must be 0 or 1")

        return cls(
            gender=_optional_string(value.get("gender"), "birth.gender"),
            calendar=_optional_string(value.get("calendar"), "birth.calendar"),
            birth_date=_optional_string(value.get("birth_date"), "birth.birth_date"),
            birth_time=_optional_string(value.get("birth_time"), "birth.birth_time"),
            timezone=_optional_string(value.get("timezone"), "birth.timezone"),
            birth_location=location,
            true_solar_time=true_solar_time,
            source=source,
            confirmation_status=confirmation_status,
            pillars=pillars,
            is_leap_month=is_leap_month,
            fold=int(fold),
        )

    @property
    def has_confirmed_pillars(self) -> bool:
        return (
            self.source in {"image_confirmed", "text_confirmed"}
            and self.confirmation_status == "confirmed"
            and self.pillars is not None
            and tuple(self.pillars) == ("year", "month", "day", "hour")
            and all(value in _SEXAGENARY for value in self.pillars.values())
        )

    def to_runtime_mapping(self) -> dict[str, object]:
        value: dict[str, object] = {
            "gender": self.gender,
            "calendar": self.calendar,
            "birth_date": self.birth_date,
            "birth_time": self.birth_time,
            "timezone": self.timezone,
            "birth_location": dict(self.birth_location or {}),
            "true_solar_time": self.true_solar_time,
            "is_leap_month": self.is_leap_month,
            "fold": self.fold,
            "source": self.source,
            "confirmation_status": self.confirmation_status,
        }
        if self.pillars is not None:
            value["pillars"] = dict(self.pillars)
        return value

    def to_dict(self) -> dict[str, object]:
        return self.to_runtime_mapping()


@dataclass(frozen=True, slots=True)
class DivinationInput:
    line_results: tuple[int, ...] = ()
    cast_at: str | None = None
    location: str | None = None
    target_event: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "DivinationInput":
        value = dict(_mapping(raw, "divination"))
        allowed = {"line_results", "cast_at", "location", "target_event"}
        unknown = set(value) - allowed
        if unknown:
            raise InputContractError(
                "divination contains unknown fields: " + ", ".join(sorted(unknown))
            )
        raw_lines = value.get("line_results", ())
        if isinstance(raw_lines, str) or not isinstance(raw_lines, Sequence):
            raise InputContractError("divination.line_results must be an array")
        lines = tuple(raw_lines)
        if any(isinstance(item, bool) or not isinstance(item, int) for item in lines):
            raise InputContractError("divination.line_results must contain integers")
        return cls(
            line_results=lines,
            cast_at=_optional_string(value.get("cast_at"), "divination.cast_at"),
            location=_optional_string(value.get("location"), "divination.location"),
            target_event=_optional_string(
                value.get("target_event"), "divination.target_event"
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "line_results": list(self.line_results),
            "cast_at": self.cast_at,
            "location": self.location,
            "target_event": self.target_event,
        }


@dataclass(frozen=True, slots=True)
class QuestionIntent:
    question: str
    domain: str
    render_intent: str = "focused_question"
    bone_weight_requested: bool = False

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "QuestionIntent":
        value = dict(_mapping(raw, "question_intent"))
        allowed = {"question", "domain", "render_intent", "bone_weight_requested"}
        unknown = set(value) - allowed
        if unknown:
            raise InputContractError(
                "question_intent contains unknown fields: "
                + ", ".join(sorted(unknown))
            )
        domain = _non_empty_string(value.get("domain"), "question_intent.domain")
        domain = _DOMAIN_ALIASES.get(domain, domain)
        if domain not in QUESTION_DOMAINS:
            raise InputContractError("question_intent.domain is unsupported")
        render_intent = str(value.get("render_intent", "focused_question"))
        if render_intent not in RENDER_INTENTS:
            raise InputContractError("question_intent.render_intent is unsupported")
        bone_weight_requested = value.get("bone_weight_requested", False)
        if not isinstance(bone_weight_requested, bool):
            raise InputContractError(
                "question_intent.bone_weight_requested must be boolean"
            )
        return cls(
            question=_non_empty_string(
                value.get("question"), "question_intent.question"
            ),
            domain=domain,
            render_intent=render_intent,
            bone_weight_requested=bone_weight_requested,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "domain": self.domain,
            "render_intent": self.render_intent,
            "bone_weight_requested": self.bone_weight_requested,
        }


@dataclass(frozen=True, slots=True)
class RealityConstraints:
    facts: Mapping[str, object]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object] | None) -> "RealityConstraints":
        if raw is None:
            return cls(MappingProxyType({}))
        value = dict(_mapping(raw, "reality_constraints"))
        return cls(MappingProxyType({key: value[key] for key in sorted(value)}))

    def to_dict(self) -> dict[str, object]:
        return dict(self.facts)


@dataclass(frozen=True, slots=True)
class ConfidenceProfile:
    chart_confidence: str
    interpretation_confidence: str
    event_confidence: str
    action_confidence: str
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "chart_confidence",
            "interpretation_confidence",
            "event_confidence",
            "action_confidence",
        ):
            if getattr(self, field_name) not in CONFIDENCE_LEVELS:
                raise InputContractError(f"{field_name} must be high, medium, or low")
        if any(not isinstance(item, str) or not item for item in self.reasons):
            raise InputContractError("confidence reasons must be non-empty strings")

    def to_dict(self) -> dict[str, object]:
        return {
            "chart_confidence": self.chart_confidence,
            "interpretation_confidence": self.interpretation_confidence,
            "event_confidence": self.event_confidence,
            "action_confidence": self.action_confidence,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ReviewCheckpoint:
    checkpoint_id: str
    review_at: str
    criteria: tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ReviewCheckpoint":
        value = dict(_mapping(raw, "review_checkpoint"))
        allowed = {"checkpoint_id", "review_at", "criteria"}
        unknown = set(value) - allowed
        if unknown:
            raise InputContractError(
                "review_checkpoint contains unknown fields: "
                + ", ".join(sorted(unknown))
            )
        return cls(
            checkpoint_id=_non_empty_string(
                value.get("checkpoint_id"), "review_checkpoint.checkpoint_id"
            ),
            review_at=_non_empty_string(
                value.get("review_at"), "review_checkpoint.review_at"
            ),
            criteria=_string_tuple(
                value.get("criteria", ()), "review_checkpoint.criteria"
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "review_at": self.review_at,
            "criteria": list(self.criteria),
        }


@dataclass(frozen=True, slots=True)
class CaseInput:
    case_id: str
    created_at: str
    anchor_year: int
    paid_tier: PaidTier
    question_intent: QuestionIntent
    birth: BirthInput | None
    divination: DivinationInput | None
    reality: RealityConstraints
    evidence_quality: EvidenceQuality
    review_checkpoint: ReviewCheckpoint | None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "CaseInput":
        value = dict(_mapping(raw, "case_input"))
        allowed = {
            "case_id",
            "created_at",
            "anchor_year",
            "paid_tier",
            "question_intent",
            "birth",
            "divination",
            "reality_constraints",
            "evidence_quality",
            "review_checkpoint",
        }
        unknown = set(value) - allowed
        if unknown:
            raise InputContractError(
                "case_input contains unknown fields: " + ", ".join(sorted(unknown))
            )
        anchor_year = value.get("anchor_year")
        if isinstance(anchor_year, bool) or not isinstance(anchor_year, int):
            raise InputContractError("anchor_year must be an integer")
        question_raw = _mapping(value.get("question_intent"), "question_intent")
        birth_raw = value.get("birth")
        divination_raw = value.get("divination")
        review_raw = value.get("review_checkpoint")
        return cls(
            case_id=_non_empty_string(value.get("case_id"), "case_id"),
            created_at=_non_empty_string(value.get("created_at"), "created_at"),
            anchor_year=anchor_year,
            paid_tier=_enum_value(
                PaidTier, value.get("paid_tier", "private"), "paid_tier"
            ),
            question_intent=QuestionIntent.from_mapping(question_raw),
            birth=(
                BirthInput.from_mapping(_mapping(birth_raw, "birth"))
                if birth_raw is not None
                else None
            ),
            divination=(
                DivinationInput.from_mapping(
                    _mapping(divination_raw, "divination")
                )
                if divination_raw is not None
                else None
            ),
            reality=RealityConstraints.from_mapping(
                _mapping(value.get("reality_constraints", {}), "reality_constraints")
            ),
            evidence_quality=_enum_value(
                EvidenceQuality,
                value.get("evidence_quality", "self_reported"),
                "evidence_quality",
            ),
            review_checkpoint=(
                ReviewCheckpoint.from_mapping(
                    _mapping(review_raw, "review_checkpoint")
                )
                if review_raw is not None
                else None
            ),
        )

    @property
    def canonical_hash(self) -> str:
        return digest({"record_type": "CaseInput", "payload": self.to_dict()})

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "created_at": self.created_at,
            "anchor_year": self.anchor_year,
            "paid_tier": self.paid_tier.value,
            "question_intent": self.question_intent.to_dict(),
            "birth": self.birth.to_dict() if self.birth is not None else None,
            "divination": (
                self.divination.to_dict() if self.divination is not None else None
            ),
            "reality_constraints": self.reality.to_dict(),
            "evidence_quality": self.evidence_quality.value,
            "review_checkpoint": (
                self.review_checkpoint.to_dict()
                if self.review_checkpoint is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class InputValidation:
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    degradation_reasons: tuple[str, ...] = ()

    @property
    def degraded(self) -> bool:
        return bool(self.errors or self.missing_fields or self.degradation_reasons)

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "degraded": self.degraded,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "missing_fields": list(self.missing_fields),
            "degradation_reasons": list(self.degradation_reasons),
        }


def _append_once(values: list[str], item: str) -> None:
    if item not in values:
        values.append(item)


def _aware_iso_datetime(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def validate_case_input(case: CaseInput) -> InputValidation:
    errors: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []
    reasons: list[str] = []

    if not _aware_iso_datetime(case.created_at):
        errors.append("created_at_must_be_timezone_aware_iso8601")
    if not 1901 <= case.anchor_year <= 2200:
        errors.append("anchor_year_out_of_supported_range")
    unknown_reality = set(case.reality.facts) - REALITY_FIELDS
    for field_name in sorted(unknown_reality):
        errors.append(f"unknown_reality_field:{field_name}")

    birth = case.birth
    if birth is None:
        missing.append("birth")
        reasons.append("birth_input_missing")
    elif birth.source in {"image_confirmed", "text_confirmed"}:
        if birth.confirmation_status != "confirmed":
            reasons.append("image_chart_unconfirmed")
        if birth.pillars is None:
            missing.append("birth.pillars")
            reasons.append("confirmed_pillars_missing")
        else:
            for position in ("year", "month", "day", "hour"):
                pillar = birth.pillars.get(position)
                if pillar is None:
                    missing.append(f"birth.pillars.{position}")
                elif pillar not in _SEXAGENARY:
                    errors.append(f"invalid_birth_pillar:{position}")
            if birth.confirmation_status == "confirmed":
                reasons.append("confirmed_pillars_static_only")
    else:
        required = {
            "birth.gender": birth.gender,
            "birth.calendar": birth.calendar,
            "birth.birth_date": birth.birth_date,
            "birth.birth_time": birth.birth_time,
            "birth.timezone": birth.timezone,
            "birth.birth_location": birth.birth_location,
        }
        for field_name, field_value in required.items():
            if field_value is None:
                missing.append(field_name)
        location = dict(birth.birth_location or {})
        for name in ("country", "city"):
            if not isinstance(location.get(name), str) or not str(location[name]).strip():
                missing.append(f"birth.birth_location.{name}")
        if missing:
            reasons.append("birth_metadata_incomplete")
        if birth.gender is not None and birth.gender not in {"male", "female"}:
            errors.append("invalid_birth_gender")
        if birth.calendar is not None and birth.calendar not in {"solar", "lunar"}:
            errors.append("invalid_birth_calendar")
        if birth.birth_date is not None:
            try:
                date.fromisoformat(birth.birth_date)
            except ValueError:
                errors.append("invalid_birth_date")
        if birth.birth_time is not None and re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", birth.birth_time
        ) is None:
            errors.append("invalid_birth_time")
        if birth.calendar == "solar" and birth.is_leap_month:
            errors.append("leap_month_requires_lunar_calendar")
        if birth.true_solar_time and not isinstance(location.get("longitude"), (int, float)):
            missing.append("birth.birth_location.longitude")
            reasons.append("true_solar_time_longitude_missing")

    divination = case.divination
    if divination is not None:
        if len(divination.line_results) != 6:
            errors.append("divination_requires_six_line_results")
        elif any(value not in {6, 7, 8, 9} for value in divination.line_results):
            errors.append("invalid_divination_line_result")
        for field_name, field_value in (
            ("divination.cast_at", divination.cast_at),
            ("divination.location", divination.location),
            ("divination.target_event", divination.target_event),
        ):
            if field_value is None:
                missing.append(field_name)
        if divination.cast_at is not None and not _aware_iso_datetime(divination.cast_at):
            errors.append("divination_cast_at_must_be_timezone_aware")
        reasons.append("liuyao_engine_unavailable")

    if case.review_checkpoint is None:
        warnings.append("review_checkpoint_missing")
    else:
        if not _aware_iso_datetime(case.review_checkpoint.review_at):
            errors.append("review_checkpoint_review_at_must_be_timezone_aware")
        if not case.review_checkpoint.criteria:
            errors.append("review_checkpoint_criteria_required")

    for collection in (errors, warnings, missing, reasons):
        deduplicated: list[str] = []
        for item in collection:
            _append_once(deduplicated, item)
        collection[:] = deduplicated
    return InputValidation(
        errors=tuple(errors),
        warnings=tuple(warnings),
        missing_fields=tuple(missing),
        degradation_reasons=tuple(reasons),
    )
