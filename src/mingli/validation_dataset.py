from __future__ import annotations

import json
from typing import Mapping, Sequence

from .contracts.serialization import canonical_json, digest


def _without_hash(value: Mapping[str, object]) -> dict[str, object]:
    return {key: item for key, item in value.items() if key != "aggregate_canonical_hash"}


def build_dataset_manifest(
    *,
    dataset_id: str,
    dataset_version: str,
    source_commit_sha: str,
    protocol_hash: str,
    cases: Sequence[Mapping[str, object]],
    prediction_hashes: Sequence[str],
    reality_evidence_hashes: Sequence[str],
    review_hashes: Sequence[str],
    comparable_claims_count: int,
    review_coverage_passed: bool,
    privacy_coverage_passed: bool,
    frozen_at: str,
    phase22_assessment_hash: str | None = None,
) -> dict[str, object]:
    entries = [json.loads(canonical_json(item)) for item in cases]
    active = [item for item in entries if item.get("qualified") is True and item.get("withdrawn") is not True]
    eligible = [item for item in active if item.get("evidence_tier") in {"gold", "silver"}]
    bronze_people = {
        str(item.get("person_case_id"))
        for item in active
        if item.get("evidence_tier") == "bronze" and item.get("person_case_id")
    }
    tiers_by_person: dict[str, set[str]] = {}
    scenarios: set[str] = set()
    for item in eligible:
        person_id = str(item.get("person_case_id", "")).strip()
        tier = str(item.get("evidence_tier", "bronze"))
        if not person_id:
            continue
        tiers_by_person.setdefault(person_id, set()).add(tier)
        scenarios.update(str(value) for value in item.get("scenario_ids", []) if value)
    gold = silver = 0
    bronze = len(bronze_people)
    conflicts: list[str] = []
    for person_id, tiers in sorted(tiers_by_person.items()):
        if tiers == {"gold"}:
            gold += 1
        elif tiers == {"silver"}:
            silver += 1
        else:
            conflicts.append(person_id)
            silver += 1
    people = len(tiers_by_person)
    failures: list[str] = []
    if people < 30:
        failures.append("insufficient_qualified_unique_person_cases")
    if gold < 10:
        failures.append("insufficient_qualified_gold_unique_person_cases")
    if silver > 20:
        failures.append("too_many_qualified_silver_unique_person_cases")
    if comparable_claims_count < 100:
        failures.append("insufficient_comparable_claims")
    if len(scenarios) < 3:
        failures.append("scenario_coverage_not_met")
    if not review_coverage_passed:
        failures.append("review_coverage_not_met")
    if not privacy_coverage_passed:
        failures.append("privacy_coverage_not_met")
    if conflicts:
        failures.append("conflicting_person_tiers")
    body: dict[str, object] = {
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "freeze_status": "frozen",
        "frozen_at": frozen_at,
        "source_commit_sha": source_commit_sha,
        "protocol_hash": protocol_hash,
        "phase22_assessment_hash": phase22_assessment_hash,
        "dataset_kind": "authorized_real_case_validation",
        "source_store_class": "controlled_off_git",
        "raw_case_data_in_manifest": False,
        "case_count": len(active),
        "unique_person_count": people,
        "gold_unique_person_count": gold,
        "silver_unique_person_count": silver,
        "bronze_count": bronze,
        "comparable_claims_count": comparable_claims_count,
        "scenario_coverage": sorted(scenarios),
        "review_coverage_passed": review_coverage_passed,
        "privacy_coverage_passed": privacy_coverage_passed,
        "conflicting_person_tiers": conflicts,
        "excluded_cases": sum(item.get("qualified") is not True for item in entries),
        "withdrawn_cases": sum(item.get("withdrawn") is True for item in entries),
        "case_manifest_hashes": sorted(str(item.get("manifest_hash")) for item in entries if item.get("manifest_hash")),
        "prediction_snapshot_hashes": sorted(prediction_hashes),
        "reality_evidence_hashes": sorted(reality_evidence_hashes),
        "review_hashes": sorted(review_hashes),
        "case_entries": entries,
        "validation_closure_passed": not failures,
        "validation_closure_failures": failures,
        "product_accuracy_claim_allowed": gold >= 30 and review_coverage_passed and privacy_coverage_passed and not conflicts,
        "prediction_validity": "evaluated" if not failures else "not_evaluated",
    }
    body["aggregate_canonical_hash"] = digest({"record_type": "ValidationDatasetManifest", "payload": body})
    return body


def verify_dataset_manifest(manifest: Mapping[str, object]) -> bool:
    return (
        manifest.get("freeze_status") == "frozen"
        and isinstance(manifest.get("aggregate_canonical_hash"), str)
        and manifest.get("aggregate_canonical_hash")
        == digest({"record_type": "ValidationDatasetManifest", "payload": _without_hash(manifest)})
    )
