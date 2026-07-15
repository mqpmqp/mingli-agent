from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, asdict
from typing import Mapping, Sequence


_DIRECT_IDENTIFIER_KEYS = frozenset(
    {
        "name", "full_name", "phone", "mobile", "email", "id_card", "identity_number",
        "address", "home_address", "contact", "wechat", "qq", "passport",
    }
)
_PHONE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_CN_ID = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


@dataclass(frozen=True)
class PrivacyFinding:
    code: str
    field_path: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def irreversible_person_case_id(raw_identifier: str, *, project_salt: str) -> str:
    """Create a stable pseudonym; callers must keep raw identifiers and salt outside Git."""
    if not raw_identifier.strip() or len(project_salt) < 16:
        raise ValueError("raw identifier and a project salt of at least 16 characters are required")
    value = hmac.new(project_salt.encode("utf-8"), raw_identifier.strip().encode("utf-8"), hashlib.sha256).hexdigest()
    return f"person:{value}"


def scan_for_pii(value: object, *, path: str = "$") -> tuple[PrivacyFinding, ...]:
    findings: list[PrivacyFinding] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            field = str(key)
            child = f"{path}.{field}"
            if field.lower() in _DIRECT_IDENTIFIER_KEYS and item not in (None, "", [], {}):
                findings.append(PrivacyFinding("DIRECT_IDENTIFIER_FIELD", child, "direct identifier field is forbidden"))
            findings.extend(scan_for_pii(item, path=child))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            findings.extend(scan_for_pii(item, path=f"{path}[{index}]"))
    elif isinstance(value, str):
        if _PHONE.search(value):
            findings.append(PrivacyFinding("PHONE_PATTERN", path, "phone-like value detected"))
        if _EMAIL.search(value):
            findings.append(PrivacyFinding("EMAIL_PATTERN", path, "email-like value detected"))
        if _CN_ID.search(value):
            findings.append(PrivacyFinding("IDENTITY_NUMBER_PATTERN", path, "identity-number-like value detected"))
    return tuple(findings)


def public_case_manifest(case: Mapping[str, object]) -> dict[str, object]:
    consent = case.get("consent")
    allowed = bool(isinstance(consent, Mapping) and consent.get("publication_use_allowed") is True)
    scenarios = case.get("scenarios", [])
    return {
        "person_case_id_hash": hashlib.sha256(str(case.get("person_case_id", "")).encode("utf-8")).hexdigest(),
        "publication_eligible": allowed,
        "scenario_types": sorted(
            {str(item.get("scenario_type")) for item in scenarios if isinstance(item, Mapping) and item.get("scenario_type")}
        ),
        "manifest_kind": "non_reidentifying_case_summary",
    }
