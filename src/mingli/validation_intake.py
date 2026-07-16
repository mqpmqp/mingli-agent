from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Mapping, Sequence
import uuid

from .contracts.serialization import canonical_json, digest
from .validation_privacy import scan_for_pii


_PERSON_ID = re.compile(r"^person:[a-zA-Z0-9._:-]{3,128}$")


class IntakeError(ValueError):
    pass


@dataclass(frozen=True)
class ImportReport:
    batch_id: str
    validated: int
    imported: int
    duplicates: tuple[str, ...]
    dry_run: bool
    source_ref: str
    canonical_hash: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RollbackReport:
    batch_id: str
    removed: int
    canonical_hash: str


def _require_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise IntakeError(f"{field} must be an object")
    return value


def validate_intake(value: Mapping[str, object]) -> dict[str, object]:
    payload = json.loads(canonical_json(value))
    person_id = str(payload.get("person_case_id", "")).strip()
    if not _PERSON_ID.fullmatch(person_id):
        raise IntakeError("person_case_id is required and must be a pseudonymous identifier")
    if scan_for_pii(payload):
        raise IntakeError("direct PII detected in intake")
    birth = _require_mapping(payload.get("birth_input"), "birth_input")
    for field in ("birth_date", "birth_time", "location_precision", "gender", "calendar", "timezone", "source", "confirmation_status"):
        if birth.get(field) in (None, ""):
            raise IntakeError(f"birth_input.{field} is required")
    if birth.get("confirmation_status") != "confirmed":
        raise IntakeError("birth input must be confirmed")
    consent = _require_mapping(payload.get("consent"), "consent")
    if consent.get("consent_status") != "granted" or consent.get("research_use_allowed") is not True or consent.get("benchmark_use_allowed") is not True:
        raise IntakeError("granted research and benchmark consent is required")
    for field in ("consent_recorded_at", "consent_record_ref", "raw_data_retention_policy"):
        if not str(consent.get(field, "")).strip():
            raise IntakeError(f"consent.{field} is required")
    if consent.get("withdrawal_supported") is not True:
        raise IntakeError("withdrawal support is required")
    metadata = _require_mapping(payload.get("case_metadata"), "case_metadata")
    for field in ("collection_channel", "collector_role", "created_at", "source_provenance", "conflict_status", "completeness_status"):
        if not str(metadata.get(field, "")).strip():
            raise IntakeError(f"case_metadata.{field} is required")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise IntakeError("at least one scenario is required")
    seen: set[str] = set()
    for scenario in scenarios:
        item = _require_mapping(scenario, "scenario")
        scenario_id = str(item.get("scenario_id", "")).strip()
        if not scenario_id or scenario_id in seen:
            raise IntakeError("scenario_id is required and must be unique within a case")
        seen.add(scenario_id)
        for field in ("scenario_type", "target_period", "question_scope"):
            if not str(item.get(field, "")).strip():
                raise IntakeError(f"scenario.{field} is required")
        if item.get("known_at_prediction_time") is not True:
            raise IntakeError("scenario must be registered before prediction")
    payload["intake_canonical_hash"] = digest({"record_type": "RealCaseIntake", "payload": payload})
    return payload


def _safe_name(identifier: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", identifier)


def import_intakes(
    store: Path,
    records: Sequence[Mapping[str, object]],
    *,
    source_ref: str,
    dry_run: bool = False,
) -> ImportReport:
    if not source_ref.startswith("authorized:"):
        raise IntakeError("authorized source_ref is required")
    validated = [validate_intake(item) for item in records]
    ids = [str(item["person_case_id"]) for item in validated]
    if len(ids) != len(set(ids)):
        raise IntakeError("duplicate person_case_id in import batch")
    intake_dir = Path(store) / "intake"
    duplicates = tuple(person_id for person_id in ids if (intake_dir / f"{_safe_name(person_id)}.json").exists())
    if duplicates:
        raise IntakeError(f"duplicate person_case_id already exists: {','.join(duplicates)}")
    batch_id = f"import-{uuid.uuid4().hex}"
    body = {"batch_id": batch_id, "person_case_ids": ids, "source_ref": source_ref}
    report = ImportReport(batch_id, len(validated), 0 if dry_run else len(validated), duplicates, dry_run, source_ref, digest(body))
    if dry_run:
        return report
    intake_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = Path(store) / "imports"
    batch_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for item in validated:
            target = intake_dir / f"{_safe_name(str(item['person_case_id']))}.json"
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(item) + "\n")
            created.append(target)
        manifest = {**body, "created_at": datetime.now(timezone.utc).isoformat(), "files": [f"intake/{_safe_name(item)}.json" for item in ids]}
        with (batch_dir / f"{batch_id}.json").open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(manifest) + "\n")
    except (FileExistsError, OSError) as exc:
        for target in created:
            target.unlink(missing_ok=True)
        raise IntakeError("atomic intake import failed; no partial batch was retained") from exc
    return report


def rollback_import(store: Path, batch_id: str) -> RollbackReport:
    if not re.fullmatch(r"import-[0-9a-f]{32}", batch_id):
        raise IntakeError("invalid batch_id")
    root = Path(store).resolve()
    manifest_path = (root / "imports" / f"{batch_id}.json").resolve()
    if root not in manifest_path.parents or not manifest_path.is_file():
        raise IntakeError("import batch not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    removed = 0
    for relative in manifest.get("files", []):
        target = (root / str(relative)).resolve()
        if root not in target.parents:
            raise IntakeError("rollback path escapes validation store")
        if target.is_file():
            target.unlink()
            removed += 1
    manifest_path.unlink()
    return RollbackReport(batch_id, removed, digest({"batch_id": batch_id, "removed": removed}))
