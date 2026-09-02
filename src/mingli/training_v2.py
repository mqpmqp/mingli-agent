from __future__ import annotations

import json
from typing import Any, Mapping, cast

from jsonschema import Draft202012Validator, FormatChecker

from .contracts import canonical_json, get_schema
from .training import TrainingError, TrainingStore
from .validation_privacy import scan_for_pii


OUTCOME_SCHEMA_V2 = "outcome_observation_v2.schema.json"


class TrainingStoreV2(TrainingStore):
    """V2 outcome path with an immutable non-commercial eligibility boundary."""

    def _validate(self, kind: str, value: Mapping[str, object]) -> dict[str, object]:
        if kind != "outcome":
            return super()._validate(kind, value)
        payload = cast(dict[str, object], json.loads(canonical_json(value)))
        findings = scan_for_pii(payload)
        if findings:
            raise TrainingError(
                "PII_DETECTED",
                "record contains a forbidden direct identifier or identifier-like value",
                field_path=findings[0].field_path,
            )
        validator = Draft202012Validator(
            get_schema(OUTCOME_SCHEMA_V2), format_checker=FormatChecker()
        )
        errors = sorted(
            validator.iter_errors(cast(Any, payload)),
            key=lambda item: list(item.absolute_path),
        )
        if errors:
            error = errors[0]
            path = "$" + "".join(
                f"[{part}]" if isinstance(part, int) else f".{part}"
                for part in error.absolute_path
            )
            raise TrainingError("SCHEMA_INCOMPATIBLE", error.message, field_path=path)
        return payload

    def add_outcome(self, value: Mapping[str, object]) -> dict[str, object]:
        payload = {
            **value,
            "commercial_validation_eligible": False,
            "eligibility_reason": "REAL_CASE_V2_ADJUDICATION_REQUIRED",
            "valid": True,
        }
        case_id = str(payload.get("case_id", ""))
        self.show_case(case_id)
        run = self._read("run", str(payload.get("run_id", "")))
        if run.get("case_id") != case_id:
            raise TrainingError("RUN_CASE_MISMATCH", "outcome run_id does not belong to case_id")
        result = self._write("outcome", str(payload.get("outcome_id", "")), payload)
        case = self._read("case", case_id)
        case["outcome_status"] = "observed"
        self._replace("case", case_id, case)
        self._audit("OUTCOME_ADDED", case_id, occurred_at=str(result["observed_at"]))
        return result


__all__ = ["OUTCOME_SCHEMA_V2", "TrainingStoreV2"]
