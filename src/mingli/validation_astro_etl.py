from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .validation_intake import IntakeError, validate_intake
from .validation_privacy import irreversible_person_case_id


class AstroTransformError(ValueError):
    """Raised when an Astro source record cannot safely enter intake."""


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AstroTransformError(f"{field} must be an object")
    return value


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AstroTransformError(f"{field} is required")
    return text


def _utc_datetime(value: object) -> datetime:
    text = _required_text(value, "birth_datetime_utc")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AstroTransformError("birth_datetime_utc must be valid ISO 8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise AstroTransformError("birth_datetime_utc must use UTC")
    return parsed


def local_mean_solar_time(utc_time: object, longitude: object) -> str:
    """Return longitude-derived local mean solar time.

    This deliberately does not claim true solar time because it does not apply
    the equation of time.
    """

    parsed = _utc_datetime(utc_time)
    if isinstance(longitude, bool) or not isinstance(longitude, (int, float, str)):
        raise AstroTransformError("birth_longitude must be numeric")
    try:
        longitude_value = float(longitude)
    except (TypeError, ValueError) as exc:
        raise AstroTransformError("birth_longitude must be numeric") from exc
    if not -180 <= longitude_value <= 180:
        raise AstroTransformError("birth_longitude must be between -180 and 180")
    longitude_offset = timedelta(minutes=longitude_value * 4)
    return parsed.astimezone(timezone(longitude_offset)).isoformat()


def transform_astro_record(
    raw_record: Mapping[str, object],
    *,
    project_salt: str,
) -> dict[str, object]:
    """Transform one authorized source record into validated intake data.

    Raw identifiers, names, source record IDs, and retrospective events are not
    copied into the returned object. The project salt must be controlled outside
    Git and is used only to derive the stable pseudonymous person identifier.
    """

    raw = _mapping(raw_record, "raw_record")
    consent = raw.get("consent")
    if not isinstance(consent, Mapping):
        raise AstroTransformError(
            "explicit consent is required; public-domain status is not consent"
        )
    if raw.get("events"):
        raise AstroTransformError(
            "retrospective events cannot become pre-registered scenarios"
        )

    source_record_id = _required_text(raw.get("source_record_id"), "source_record_id")
    birth_utc = _utc_datetime(raw.get("birth_datetime_utc"))
    timezone_name = _required_text(raw.get("birth_timezone"), "birth_timezone")
    try:
        local_birth = birth_utc.astimezone(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError as exc:
        raise AstroTransformError("birth_timezone must be a valid IANA timezone") from exc

    scenarios = raw.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise AstroTransformError("at least one pre-registered scenario is required")

    intake = {
        "person_case_id": irreversible_person_case_id(
            source_record_id,
            project_salt=project_salt,
        ),
        "birth_input": {
            "birth_date": local_birth.date().isoformat(),
            "birth_time": local_birth.strftime("%H:%M"),
            "location_precision": _required_text(
                raw.get("birth_location_precision"),
                "birth_location_precision",
            ),
            "gender": _required_text(raw.get("gender"), "gender"),
            "calendar": _required_text(raw.get("calendar", "solar"), "calendar"),
            "timezone": timezone_name,
            "true_solar_time": False,
            "local_mean_solar_time": local_mean_solar_time(
                raw.get("birth_datetime_utc"),
                raw.get("birth_longitude"),
            ),
            "source": _required_text(raw.get("birth_source"), "birth_source"),
            "confirmation_status": _required_text(
                raw.get("birth_confirmation_status"),
                "birth_confirmation_status",
            ),
        },
        "consent": dict(consent),
        "case_metadata": dict(_mapping(raw.get("case_metadata"), "case_metadata")),
        "scenarios": [dict(_mapping(item, "scenario")) for item in scenarios],
    }
    try:
        validated = validate_intake(intake)
    except (IntakeError, ValueError) as exc:
        raise AstroTransformError(str(exc)) from exc
    validated.pop("intake_canonical_hash", None)
    return validated
