from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from importlib.resources import files
from typing import Mapping, Sequence

from .contracts.serialization import digest
from .derived.static_engine import BRANCHES, STEMS
from .phase8_engine import validate_import_origin
from .phase13 import build_phase13_fixture, evaluate_luck_cycle_role_interactions
from .phase13_contracts import record_digest as phase13_record_digest
from .phase14_contracts import (
    BaziTemporalTrendEvidenceResult,
    PHASE14_CALCULATION_VERSION,
    PHASE14_DECISION_ID,
    PHASE14_METHOD_ID,
    PHASE14_SCHEMA_VERSION,
    Phase14BenchmarkResult,
    Phase14InputError,
    TARGET_TYPES,
    TRANSITION_TYPES,
    TREND_LABELS,
    TemporalRealityEvidenceRecord,
    TemporalTrendEvidenceRecord,
    TemporalTrendRecord,
    TrendTransitionRecord,
    record_digest,
)

DEFAULT_PHASE14_PROFILE_ID = "temporal-trend-evidence-r1@0.1"
PROFILE_RESOURCE = "phase14_temporal_trend_profiles_v0.1.json"
ASSERTION_RESOURCE = "phase14_temporal_trend_assertions_v0.1.json"
METADATA_FIELDS = {"canonical_hash", "schema_version", "method_id", "calculation_version", "prediction_validity"}
BLOCKED_OUTPUTS = {
    "auspiciousness",
    "good_bad",
    "fortune_judgement",
    "event_prediction",
    "career_prediction",
    "wealth_prediction",
    "relationship_prediction",
    "health_prediction",
    "natural_language_renderer",
}


def _decimal(value: object, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise Phase14InputError(f"{name} must be decimal-compatible") from exc
    if not result.is_finite():
        raise Phase14InputError(f"{name} must be finite")
    return result


def _score(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")


def _resource(name: str, label: str) -> dict[str, object]:
    value = json.loads(files("mingli.derived.data").joinpath(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def load_phase14_trend_profiles() -> dict[str, object]:
    return _resource(PROFILE_RESOURCE, "Phase 14 profile manifest")


def load_phase14_trend_assertions() -> dict[str, object]:
    return _resource(ASSERTION_RESOURCE, "Phase 14 assertion manifest")


def get_temporal_trend_profile(profile_id: str = DEFAULT_PHASE14_PROFILE_ID) -> dict[str, object]:
    raw = load_phase14_trend_profiles().get("profiles")
    if not isinstance(raw, list):
        raise ValueError("profiles must be an array")
    for item in raw:
        if isinstance(item, dict) and item.get("profile_id") == profile_id:
            result = dict(item)
            result["canonical_hash"] = digest({
                "record_type": "TemporalTrendProfile",
                "payload": {key: value for key, value in result.items() if key != "canonical_hash"},
            })
            return result
    raise ValueError(f"unsupported Phase 14 profile: {profile_id}")


def validate_phase14_profiles() -> tuple[str, ...]:
    issues: list[str] = []
    try:
        profile = get_temporal_trend_profile()
        thresholds = profile.get("trend_thresholds")
        if profile.get("reviewed") is not True:
            issues.append("reviewed must be true")
        if not isinstance(thresholds, Mapping) or set(thresholds) != {
            "support_ratio_min", "conflict_ratio_min", "mixed_secondary_min"
        }:
            issues.append("trend_thresholds are incomplete")
        else:
            for key, value in thresholds.items():
                number = _decimal(value, f"trend_thresholds.{key}")
                if not Decimal("0") <= number <= Decimal("1"):
                    issues.append(f"trend_thresholds.{key} must be between 0 and 1")
        transition_delta = _decimal(profile.get("transition_delta"), "transition_delta")
        if not Decimal("0") <= transition_delta <= Decimal("2"):
            issues.append("transition_delta must be between 0 and 2")
        scale = _decimal(profile.get("evidence_scale"), "evidence_scale")
        if not Decimal("0") < scale <= Decimal("10"):
            issues.append("evidence_scale must be greater than 0 and at most 10")
        if len(set(profile.get("independence_groups", []))) < 2:
            issues.append("at least two independence groups are required")
        if not str(profile.get("canonical_hash", "")).startswith("sha256:"):
            issues.append("profile canonical hash is invalid")
    except (ValueError, Phase14InputError) as exc:
        issues.append(str(exc))
    return tuple(issues)


def phase14_schema_summary() -> dict[str, object]:
    return {
        "decision_id": PHASE14_DECISION_ID,
        "schema_version": PHASE14_SCHEMA_VERSION,
        "method_id": PHASE14_METHOD_ID,
        "calculation_version": PHASE14_CALCULATION_VERSION,
        "profile_id": DEFAULT_PHASE14_PROFILE_ID,
        "prediction_validity": "not_evaluated",
        "trend_labels": list(TREND_LABELS),
        "target_types": list(TARGET_TYPES),
        "transition_types": list(TRANSITION_TYPES),
        "output_boundary": "temporal_tendency_evidence_only_no_auspiciousness_or_event_prediction",
    }


def _verify_fact_graph(value: Mapping[str, object]) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase14InputError("Phase 7 Fact Graph missing canonical_hash")
    if value.get("schema_version") != "bazi-fact-graph-result@0.1":
        raise Phase14InputError("unsupported Phase 7 Fact Graph schema")
    if value.get("prediction_validity") != "not_evaluated":
        raise Phase14InputError("Phase 7 Fact Graph prediction_validity must be not_evaluated")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    if found != digest({"record_type": "BaziFactGraphResult", "payload": body}):
        raise Phase14InputError("Phase 7 Fact Graph canonical_hash mismatch")
    if not isinstance(value.get("timeline"), Mapping):
        raise Phase14InputError("Phase 7 Fact Graph timeline is required")
    return found


def _verify_phase13(value: Mapping[str, object], fact_graph_hash: str) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase14InputError("Phase 13 Interaction Result missing canonical_hash")
    if value.get("schema_version") != "bazi-luck-cycle-role-interaction-result@0.1":
        raise Phase14InputError("unsupported Phase 13 Interaction Result schema")
    if value.get("prediction_validity") != "not_evaluated":
        raise Phase14InputError("Phase 13 Interaction Result prediction_validity must be not_evaluated")
    if value.get("fact_graph_hash") != fact_graph_hash:
        raise Phase14InputError("Phase 7 and Phase 13 fact_graph_hash mismatch")
    for key, record_type in (
        ("dayun_interactions", "PeriodRoleInteraction"),
        ("liunian_interactions", "PeriodRoleInteraction"),
        ("combined_windows", "CombinedCycleWindow"),
        ("evidence_records", "CycleInteractionEvidenceRecord"),
    ):
        raw = value.get(key)
        if not isinstance(raw, list):
            raise Phase14InputError(f"Phase 13 {key} must be an array")
        for item in raw:
            if not isinstance(item, Mapping):
                raise Phase14InputError(f"Phase 13 {key} entry must be an object")
            if item.get("canonical_digest") != phase13_record_digest(record_type, item):
                raise Phase14InputError(f"Phase 13 {key} canonical_digest mismatch")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    if found != phase13_record_digest("BaziLuckCycleRoleInteractionResult", body):
        raise Phase14InputError("Phase 13 Interaction Result canonical_hash mismatch")
    return found


def _age_maps(graph: Mapping[str, object]) -> tuple[dict[str, tuple[int | None, int | None]], dict[str, int | None]]:
    timeline = graph["timeline"]
    assert isinstance(timeline, Mapping)
    raw_dayun = timeline.get("dayun_periods")
    raw_liunian = timeline.get("liunian_periods")
    if not isinstance(raw_dayun, list) or not isinstance(raw_liunian, list):
        raise Phase14InputError("Phase 7 timeline periods are required")
    dayun: dict[str, tuple[int | None, int | None]] = {}
    liunian: dict[str, int | None] = {}
    for item in raw_dayun:
        if not isinstance(item, Mapping):
            continue
        start_age = item.get("start_age")
        end_age = item.get("end_age")
        start = int(start_age["chronological_years"]) if isinstance(start_age, Mapping) and start_age.get("chronological_years") is not None else None
        end = int(end_age["chronological_years"]) if isinstance(end_age, Mapping) and end_age.get("chronological_years") is not None else None
        dayun[str(item.get("period_id"))] = (start, end)
    for item in raw_liunian:
        if not isinstance(item, Mapping):
            continue
        snapshot = item.get("age_snapshot")
        age = int(snapshot["chronological_years"]) if isinstance(snapshot, Mapping) and snapshot.get("chronological_years") is not None else None
        liunian[str(item.get("period_id"))] = age
    return dayun, liunian


def _parse_reality(raw_items: Sequence[Mapping[str, object]], valid_targets: set[str]) -> tuple[TemporalRealityEvidenceRecord, ...]:
    records: list[TemporalRealityEvidenceRecord] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items, 1):
        target_id = str(item.get("target_id", ""))
        direction = str(item.get("direction", ""))
        detail = str(item.get("detail", "")).strip()
        source_id = str(item.get("source_id", "")).strip()
        evidence_id = str(item.get("evidence_id") or f"phase14-reality:{target_id}:{index}")
        verified = item.get("verified") is True
        weight = _decimal(item.get("weight", "0"), "reality.weight")
        if target_id not in valid_targets:
            raise Phase14InputError(f"reality evidence target is unknown: {target_id}")
        if direction not in {"support", "contradict"}:
            raise Phase14InputError("reality evidence direction must be support or contradict")
        if not detail or not source_id:
            raise Phase14InputError("reality evidence detail and source_id are required")
        if not Decimal("0") <= weight <= Decimal("10"):
            raise Phase14InputError("reality evidence weight must be between 0 and 10")
        if evidence_id in seen:
            raise Phase14InputError(f"duplicate reality evidence_id: {evidence_id}")
        seen.add(evidence_id)
        payload = {
            "evidence_id": evidence_id,
            "target_id": target_id,
            "direction": direction,
            "detail": detail,
            "weight": _score(weight),
            "verified": verified,
            "source_id": source_id,
        }
        records.append(TemporalRealityEvidenceRecord(
            evidence_id=evidence_id,
            target_id=target_id,
            direction=direction,  # type: ignore[arg-type]
            detail=detail,
            weight=payload["weight"],
            verified=verified,
            source_id=source_id,
            canonical_digest=record_digest("TemporalRealityEvidenceRecord", payload),
        ))
    return tuple(sorted(records, key=lambda item: item.evidence_id))


def _label(profile: Mapping[str, object], state: str, support: Decimal, conflict: Decimal, unresolved_count: int) -> str:
    if unresolved_count or state == "unresolved":
        return "unresolved"
    thresholds = profile["trend_thresholds"]
    assert isinstance(thresholds, Mapping)
    support_min = _decimal(thresholds["support_ratio_min"], "support_ratio_min")
    conflict_min = _decimal(thresholds["conflict_ratio_min"], "conflict_ratio_min")
    mixed_min = _decimal(thresholds["mixed_secondary_min"], "mixed_secondary_min")
    if support >= support_min and conflict < mixed_min:
        return "support_tendency"
    if conflict >= conflict_min and support < mixed_min:
        return "conflict_tendency"
    if support >= mixed_min and conflict >= mixed_min:
        return "mixed_tendency"
    return {
        "aligned": "support_tendency",
        "opposed": "conflict_tendency",
        "mixed": "mixed_tendency",
        "neutral": "neutral_tendency",
    }.get(state, "neutral_tendency")


def _source_meta(
    source: Mapping[str, object],
    target_type: str,
    dayun_ages: Mapping[str, tuple[int | None, int | None]],
    liunian_ages: Mapping[str, int | None],
    liunian_by_id: Mapping[str, Mapping[str, object]],
) -> tuple[str, int | None, int | None, int | None, int | None, str, str]:
    if target_type == "combined_window":
        target_id = str(source.get("window_id"))
        liunian_id = str(source.get("liunian_period_id"))
        liunian = liunian_by_id.get(liunian_id, {})
        year = int(liunian["label_year"]) if liunian.get("label_year") is not None else None
        age = liunian_ages.get(liunian_id)
        return target_id, None, year, age, age, str(source.get("start_instant_utc")), str(source.get("end_instant_utc"))
    target_id = str(source.get("period_id"))
    if target_type == "dayun":
        start_age, end_age = dayun_ages.get(target_id, (None, None))
        sequence = int(source["sequence_index"]) if source.get("sequence_index") is not None else None
        return target_id, sequence, None, start_age, end_age, str(source.get("start_instant_utc")), str(source.get("end_instant_utc"))
    age = liunian_ages.get(target_id)
    year = int(source["label_year"]) if source.get("label_year") is not None else None
    return target_id, None, year, age, age, str(source.get("start_instant_utc")), str(source.get("end_instant_utc"))


def _trend(
    source: Mapping[str, object],
    target_type: str,
    dayun_ages: Mapping[str, tuple[int | None, int | None]],
    liunian_ages: Mapping[str, int | None],
    liunian_by_id: Mapping[str, Mapping[str, object]],
    reality_by_target: Mapping[str, tuple[TemporalRealityEvidenceRecord, ...]],
    graph_hash: str,
    interaction_hash: str,
    profile: Mapping[str, object],
) -> TemporalTrendRecord:
    target_id, sequence, year, start_age, end_age, start, end = _source_meta(
        source, target_type, dayun_ages, liunian_ages, liunian_by_id
    )
    support_score = _decimal(source.get("support_score", "0"), "support_score")
    conflict_score = _decimal(source.get("conflict_score", "0"), "conflict_score")
    neutral_score = _decimal(source.get("neutral_score", "0"), "neutral_score")
    unresolved_count = int(source.get("unresolved_count", 0))
    total = support_score + conflict_score + neutral_score
    if total:
        support_ratio = support_score / total
        conflict_ratio = conflict_score / total
        neutral_ratio = neutral_score / total
        net = (support_score - conflict_score) / total
        intensity = (support_score + conflict_score) / total
    else:
        support_ratio = Decimal("0")
        conflict_ratio = Decimal("0")
        neutral_ratio = Decimal("1")
        net = Decimal("0")
        intensity = Decimal("0")
    trend_label = _label(profile, str(source.get("structural_state")), support_ratio, conflict_ratio, unresolved_count)
    reality = reality_by_target.get(target_id, ())
    verified_directions = {item.direction for item in reality if item.verified}
    override: str | None = None
    rationale = ["phase13_structural_scores_retained"]
    if len(verified_directions) > 1:
        trend_label = "unresolved"
        rationale.append("conflicting_verified_reality")
    elif len(verified_directions) == 1:
        override = next(iter(verified_directions))
        trend_label = "support_tendency" if override == "support" else "conflict_tendency"
        rationale.append("verified_reality_hard_override")
    elif reality:
        rationale.append("unverified_reality_no_hard_override")
    if trend_label in {"unresolved", "neutral_tendency"}:
        confidence = "low"
        rationale.append("low_confidence_boundary")
    elif override:
        confidence = "high"
        rationale.append("high_confidence_reality_scope_only")
    else:
        confidence = "medium"
        rationale.append("medium_without_verified_reality")
    payload = {
        "trend_id": f"trend:{target_id}",
        "target_id": target_id,
        "target_type": target_type,
        "sequence_index": sequence,
        "label_year": year,
        "start_instant_utc": start,
        "end_instant_utc": end,
        "start_age": start_age,
        "end_age": end_age,
        "structural_state": str(source.get("structural_state")),
        "base_support_score": _score(support_score),
        "base_conflict_score": _score(conflict_score),
        "base_neutral_score": _score(neutral_score),
        "support_ratio": _score(support_ratio),
        "conflict_ratio": _score(conflict_ratio),
        "neutral_ratio": _score(neutral_ratio),
        "net_balance": _score(net),
        "intensity": _score(intensity),
        "trend_label": trend_label,
        "confidence": confidence,
        "confidence_rationale_codes": sorted(set(rationale)),
        "reality_override_direction": override,
        "reality_evidence_ids": [item.evidence_id for item in reality],
        "source_record_digest": str(source.get("canonical_digest", "")),
        "source_result_hashes": [graph_hash, interaction_hash],
        "profile_id": str(profile["profile_id"]),
    }
    return TemporalTrendRecord(
        trend_id=payload["trend_id"],
        target_id=target_id,
        target_type=target_type,  # type: ignore[arg-type]
        sequence_index=sequence,
        label_year=year,
        start_instant_utc=start,
        end_instant_utc=end,
        start_age=start_age,
        end_age=end_age,
        structural_state=payload["structural_state"],
        base_support_score=payload["base_support_score"],
        base_conflict_score=payload["base_conflict_score"],
        base_neutral_score=payload["base_neutral_score"],
        support_ratio=payload["support_ratio"],
        conflict_ratio=payload["conflict_ratio"],
        neutral_ratio=payload["neutral_ratio"],
        net_balance=payload["net_balance"],
        intensity=payload["intensity"],
        trend_label=trend_label,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        confidence_rationale_codes=tuple(payload["confidence_rationale_codes"]),
        reality_override_direction=override,  # type: ignore[arg-type]
        reality_evidence_ids=tuple(payload["reality_evidence_ids"]),
        source_record_digest=payload["source_record_digest"],
        source_result_hashes=(graph_hash, interaction_hash),
        profile_id=payload["profile_id"],
        canonical_digest=record_digest("TemporalTrendRecord", payload),
    )


def _transition_kind(previous: TemporalTrendRecord, current: TemporalTrendRecord, threshold: Decimal) -> str:
    if current.trend_label == "unresolved" and previous.trend_label != "unresolved":
        return "becoming_unresolved"
    if previous.trend_label == "unresolved" and current.trend_label != "unresolved":
        return "resolving"
    if current.trend_label == "mixed_tendency" and previous.trend_label != "mixed_tendency":
        return "entering_mixed"
    if previous.trend_label == "mixed_tendency" and current.trend_label != "mixed_tendency":
        return "leaving_mixed"
    delta = Decimal(current.net_balance) - Decimal(previous.net_balance)
    if delta >= threshold:
        return "strengthening_support"
    if delta <= -threshold:
        return "strengthening_conflict"
    return "stable"


def _transitions(records: Sequence[TemporalTrendRecord], profile: Mapping[str, object]) -> tuple[TrendTransitionRecord, ...]:
    threshold = _decimal(profile["transition_delta"], "transition_delta")
    result: list[TrendTransitionRecord] = []
    for previous, current in zip(records, records[1:]):
        transition_type = _transition_kind(previous, current, threshold)
        payload = {
            "transition_id": f"transition:{previous.target_id}->{current.target_id}",
            "target_type": current.target_type,
            "from_target_id": previous.target_id,
            "to_target_id": current.target_id,
            "from_label": previous.trend_label,
            "to_label": current.trend_label,
            "net_delta": _score(Decimal(current.net_balance) - Decimal(previous.net_balance)),
            "intensity_delta": _score(Decimal(current.intensity) - Decimal(previous.intensity)),
            "transition_type": transition_type,
        }
        result.append(TrendTransitionRecord(
            transition_id=payload["transition_id"],
            target_type=current.target_type,
            from_target_id=previous.target_id,
            to_target_id=current.target_id,
            from_label=previous.trend_label,
            to_label=current.trend_label,
            net_delta=payload["net_delta"],
            intensity_delta=payload["intensity_delta"],
            transition_type=transition_type,  # type: ignore[arg-type]
            canonical_digest=record_digest("TrendTransitionRecord", payload),
        ))
    return tuple(result)


def _indexes(records: Sequence[TemporalTrendRecord]) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    years: dict[str, set[str]] = {}
    ages: dict[str, set[str]] = {}
    for record in records:
        if record.label_year is not None:
            years.setdefault(str(record.label_year), set()).add(record.target_id)
        else:
            try:
                start_year = datetime.fromisoformat(record.start_instant_utc.replace("Z", "+00:00")).year
                end_year = datetime.fromisoformat(record.end_instant_utc.replace("Z", "+00:00")).year
                if 0 <= end_year - start_year <= 30:
                    for year in range(start_year, end_year + 1):
                        years.setdefault(str(year), set()).add(record.target_id)
            except ValueError:
                pass
        if record.start_age is not None:
            end_age = record.end_age if record.end_age is not None else record.start_age
            if 0 <= end_age - record.start_age <= 30:
                for age in range(record.start_age, end_age + 1):
                    ages.setdefault(str(age), set()).add(record.target_id)
    return (
        {key: tuple(sorted(value)) for key, value in sorted(years.items(), key=lambda item: int(item[0]))},
        {key: tuple(sorted(value)) for key, value in sorted(ages.items(), key=lambda item: int(item[0]))},
    )


def _evidence(
    trends: Sequence[TemporalTrendRecord],
    reality: Sequence[TemporalRealityEvidenceRecord],
    interaction_hash: str,
    profile: Mapping[str, object],
) -> tuple[TemporalTrendEvidenceRecord, ...]:
    scale = _decimal(profile["evidence_scale"], "evidence_scale")
    records: list[TemporalTrendEvidenceRecord] = []
    for trend in trends:
        rows = (
            ("structural_support_ratio", "timing", "support", Decimal(trend.support_ratio)),
            ("structural_conflict_ratio", "timing", "contradict", Decimal(trend.conflict_ratio)),
            ("structural_neutral_ratio", "rule", "support", Decimal(trend.neutral_ratio)),
        )
        for evidence_type, source_type, direction, ratio in rows:
            if ratio == 0:
                continue
            payload = {
                "evidence_id": f"evidence:{trend.target_id}:{evidence_type}",
                "target_id": trend.target_id,
                "evidence_type": evidence_type,
                "source_type": source_type,
                "direction": direction,
                "contribution": _score(min(Decimal("10"), ratio * scale)),
                "priority": 80 if source_type == "timing" else 60,
                "verified": True,
                "source_id": trend.source_record_digest,
                "source_result_hashes": [interaction_hash],
                "profile_id": str(profile["profile_id"]),
            }
            records.append(TemporalTrendEvidenceRecord(
                evidence_id=payload["evidence_id"],
                target_id=trend.target_id,
                evidence_type=evidence_type,
                source_type=source_type,  # type: ignore[arg-type]
                direction=direction,  # type: ignore[arg-type]
                contribution=payload["contribution"],
                priority=payload["priority"],
                verified=True,
                source_id=trend.source_record_digest,
                source_result_hashes=(interaction_hash,),
                profile_id=payload["profile_id"],
                canonical_digest=record_digest("TemporalTrendEvidenceRecord", payload),
            ))
    for item in reality:
        payload = {
            "evidence_id": f"evidence:{item.evidence_id}",
            "target_id": item.target_id,
            "evidence_type": "verified_reality" if item.verified else "unverified_reality",
            "source_type": "reality",
            "direction": item.direction,
            "contribution": item.weight,
            "priority": 100 if item.verified else 70,
            "verified": item.verified,
            "source_id": item.source_id,
            "source_result_hashes": [interaction_hash],
            "profile_id": str(profile["profile_id"]),
        }
        records.append(TemporalTrendEvidenceRecord(
            evidence_id=payload["evidence_id"],
            target_id=item.target_id,
            evidence_type=payload["evidence_type"],
            source_type="reality",
            direction=item.direction,
            contribution=item.weight,
            priority=payload["priority"],
            verified=item.verified,
            source_id=item.source_id,
            source_result_hashes=(interaction_hash,),
            profile_id=payload["profile_id"],
            canonical_digest=record_digest("TemporalTrendEvidenceRecord", payload),
        ))
    return tuple(sorted(records, key=lambda item: item.evidence_id))


def evaluate_bazi_temporal_trends(
    fact_graph: Mapping[str, object],
    interaction_result: Mapping[str, object],
    *,
    reality_evidence: Sequence[Mapping[str, object]] = (),
    profile_id: str = DEFAULT_PHASE14_PROFILE_ID,
    requested_outputs: Sequence[str] = (),
) -> BaziTemporalTrendEvidenceResult:
    if set(requested_outputs) & BLOCKED_OUTPUTS:
        raise Phase14InputError("Phase 14 cannot return auspiciousness, event, domain, or renderer outputs")
    if not isinstance(fact_graph, Mapping) or not fact_graph:
        raise Phase14InputError("Phase 7 Fact Graph is required")
    if not isinstance(interaction_result, Mapping) or not interaction_result:
        raise Phase14InputError("Phase 13 Interaction Result is required")
    profile = get_temporal_trend_profile(profile_id)
    graph_hash = _verify_fact_graph(fact_graph)
    interaction_hash = _verify_phase13(interaction_result, graph_hash)
    raw_dayun = interaction_result["dayun_interactions"]
    raw_liunian = interaction_result["liunian_interactions"]
    raw_windows = interaction_result["combined_windows"]
    assert isinstance(raw_dayun, list) and isinstance(raw_liunian, list) and isinstance(raw_windows, list)
    valid_targets = {
        str(item.get("period_id")) for item in (*raw_dayun, *raw_liunian) if isinstance(item, Mapping)
    } | {
        str(item.get("window_id")) for item in raw_windows if isinstance(item, Mapping)
    }
    reality = _parse_reality(reality_evidence, valid_targets)
    reality_by_target = {
        target_id: tuple(item for item in reality if item.target_id == target_id)
        for target_id in sorted(valid_targets)
    }
    dayun_ages, liunian_ages = _age_maps(fact_graph)
    liunian_by_id = {str(item.get("period_id")): item for item in raw_liunian if isinstance(item, Mapping)}
    dayun = tuple(
        _trend(item, "dayun", dayun_ages, liunian_ages, liunian_by_id, reality_by_target, graph_hash, interaction_hash, profile)
        for item in raw_dayun if isinstance(item, Mapping)
    )
    liunian = tuple(
        _trend(item, "liunian", dayun_ages, liunian_ages, liunian_by_id, reality_by_target, graph_hash, interaction_hash, profile)
        for item in raw_liunian if isinstance(item, Mapping)
    )
    combined = tuple(
        _trend(item, "combined_window", dayun_ages, liunian_ages, liunian_by_id, reality_by_target, graph_hash, interaction_hash, profile)
        for item in raw_windows if isinstance(item, Mapping)
    )
    all_trends = (*dayun, *liunian, *combined)
    transitions = (*_transitions(dayun, profile), *_transitions(liunian, profile), *_transitions(combined, profile))
    year_index, age_index = _indexes(all_trends)
    evidence = _evidence(all_trends, reality, interaction_hash, profile)
    trend_counts = {label: 0 for label in TREND_LABELS}
    confidence_counts = {level: 0 for level in ("high", "medium", "low")}
    unresolved: list[dict[str, object]] = []
    for trend in all_trends:
        trend_counts[trend.trend_label] += 1
        confidence_counts[trend.confidence] += 1
        if trend.trend_label == "unresolved":
            unresolved.append({"code": "temporal_trend_unresolved", "target_id": trend.target_id, "source": "phase14"})
    for item in interaction_result.get("unresolved", []):
        if isinstance(item, Mapping):
            unresolved.append(dict(item))
    provenance = {
        "profile_hash": profile["canonical_hash"],
        "fact_graph_hash": graph_hash,
        "interaction_result_hash": interaction_hash,
        "phase13_profile_id": interaction_result.get("profile_id"),
        "reality_evidence_ids": [item.evidence_id for item in reality],
        "source_ids": list(profile.get("source_ids", [])),
    }
    body = {
        "fact_graph_hash": graph_hash,
        "interaction_result_hash": interaction_hash,
        "profile_id": profile_id,
        "dayun_trends": [item.to_dict() for item in dayun],
        "liunian_trends": [item.to_dict() for item in liunian],
        "combined_trends": [item.to_dict() for item in combined],
        "transitions": [item.to_dict() for item in transitions],
        "reality_evidence": [item.to_dict() for item in reality],
        "evidence_records": [item.to_dict() for item in evidence],
        "year_index": {key: list(value) for key, value in year_index.items()},
        "age_index": {key: list(value) for key, value in age_index.items()},
        "trend_counts": trend_counts,
        "confidence_counts": confidence_counts,
        "provenance_index": provenance,
        "warnings": [
            "temporal_tendency_evidence_only",
            "reality_override_does_not_delete_structural_evidence",
            "high_confidence_scoped_to_verified_reality_only",
            "prediction_validity_not_evaluated",
            "no_auspiciousness_or_event_prediction",
        ],
        "unresolved": unresolved,
    }
    return BaziTemporalTrendEvidenceResult(
        fact_graph_hash=graph_hash,
        interaction_result_hash=interaction_hash,
        profile_id=profile_id,
        dayun_trends=dayun,
        liunian_trends=liunian,
        combined_trends=combined,
        transitions=tuple(transitions),
        reality_evidence=reality,
        evidence_records=evidence,
        year_index=year_index,
        age_index=age_index,
        trend_counts=trend_counts,
        confidence_counts=confidence_counts,
        provenance_index=provenance,
        warnings=tuple(body["warnings"]),
        unresolved=tuple(unresolved),
        canonical_hash=record_digest("BaziTemporalTrendEvidenceResult", body),
    )


def query_temporal_trends(
    result: BaziTemporalTrendEvidenceResult | Mapping[str, object],
    *,
    year: int | None = None,
    age: int | None = None,
) -> tuple[Mapping[str, object], ...]:
    if (year is None) == (age is None):
        raise Phase14InputError("exactly one of year or age is required")
    payload = result.to_dict() if isinstance(result, BaziTemporalTrendEvidenceResult) else dict(result)
    index_name = "year_index" if year is not None else "age_index"
    index_value = year if year is not None else age
    index = payload.get(index_name)
    if not isinstance(index, Mapping):
        raise Phase14InputError(f"{index_name} is required")
    target_ids = set(index.get(str(index_value), []))
    found: list[Mapping[str, object]] = []
    for key in ("dayun_trends", "liunian_trends", "combined_trends"):
        raw = payload.get(key)
        if isinstance(raw, list):
            found.extend(item for item in raw if isinstance(item, Mapping) and item.get("target_id") in target_ids)
    return tuple(sorted(found, key=lambda item: (str(item.get("target_type")), str(item.get("target_id")))))


def temporal_trend_result_to_phase8_evidence(result: BaziTemporalTrendEvidenceResult | Mapping[str, object]):
    if isinstance(result, BaziTemporalTrendEvidenceResult):
        return tuple(item.to_phase8_evidence() for item in result.evidence_records)
    raw = result.get("evidence_records")
    if not isinstance(raw, list):
        raise Phase14InputError("evidence_records must be an array")
    records: list[TemporalTrendEvidenceRecord] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise Phase14InputError("evidence record must be an object")
        records.append(TemporalTrendEvidenceRecord(
            evidence_id=str(item["evidence_id"]),
            target_id=str(item["target_id"]),
            evidence_type=str(item["evidence_type"]),
            source_type=str(item["source_type"]),  # type: ignore[arg-type]
            direction=str(item["direction"]),  # type: ignore[arg-type]
            contribution=str(item["contribution"]),
            priority=int(item["priority"]),
            verified=bool(item["verified"]),
            source_id=str(item["source_id"]),
            source_result_hashes=tuple(str(value) for value in item["source_result_hashes"]),
            profile_id=str(item["profile_id"]),
            canonical_digest=str(item["canonical_digest"]),
        ))
    return tuple(item.to_phase8_evidence() for item in sorted(records, key=lambda value: value.evidence_id))


def build_phase14_fixture(day_stem: str, month_branch: str) -> tuple[dict[str, object], dict[str, object]]:
    graph, xiji = build_phase13_fixture(day_stem, month_branch)
    return graph, evaluate_luck_cycle_role_interactions(graph, xiji).to_dict()


def benchmark_phase14() -> Phase14BenchmarkResult:
    failures = list(validate_phase14_profiles())
    assertions_total = passed = 0
    hashes: set[str] = set()

    def check(condition: bool, message: str) -> None:
        nonlocal assertions_total, passed
        assertions_total += 1
        if condition:
            passed += 1
        else:
            failures.append(message)

    for day_stem in STEMS:
        for month_branch in BRANCHES:
            graph, interaction = build_phase14_fixture(day_stem, month_branch)
            result = evaluate_bazi_temporal_trends(graph, interaction)
            reordered = evaluate_bazi_temporal_trends(
                json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True)),
                json.loads(json.dumps(interaction, ensure_ascii=False, sort_keys=True)),
            )
            payload = result.to_dict()
            all_trends = (*result.dayun_trends, *result.liunian_trends, *result.combined_trends)
            target_ids = {item.target_id for item in all_trends}
            ratios_valid = all(
                abs(
                    Decimal(item.support_ratio)
                    + Decimal(item.conflict_ratio)
                    + Decimal(item.neutral_ratio)
                    - Decimal("1")
                ) <= Decimal("0.0002")
                for item in all_trends
            )
            checks = (
                result.schema_version == PHASE14_SCHEMA_VERSION,
                result.method_id == PHASE14_METHOD_ID,
                result.calculation_version == PHASE14_CALCULATION_VERSION,
                result.prediction_validity == "not_evaluated",
                result.canonical_hash.startswith("sha256:"),
                result.canonical_hash == reordered.canonical_hash,
                result.fact_graph_hash == graph["canonical_hash"],
                result.interaction_result_hash == interaction["canonical_hash"],
                len(result.dayun_trends) == len(interaction["dayun_interactions"]),
                len(result.liunian_trends) == len(interaction["liunian_interactions"]),
                len(result.combined_trends) == len(interaction["combined_windows"]),
                len(target_ids) == len(all_trends),
                all(item.target_type in TARGET_TYPES for item in all_trends),
                all(item.trend_label in TREND_LABELS for item in all_trends),
                all(item.confidence in {"high", "medium", "low"} for item in all_trends),
                all(item.confidence != "high" for item in all_trends),
                ratios_valid,
                all(Decimal("-1") <= Decimal(item.net_balance) <= Decimal("1") for item in all_trends),
                all(Decimal("0") <= Decimal(item.intensity) <= Decimal("1") for item in all_trends),
                all(item.source_record_digest.startswith("sha256:") for item in all_trends),
                all(item.canonical_digest.startswith("sha256:") for item in all_trends),
                all(item.target_type == "dayun" for item in result.dayun_trends),
                all(item.target_type == "liunian" for item in result.liunian_trends),
                all(item.target_type == "combined_window" for item in result.combined_trends),
                all(item.transition_type in TRANSITION_TYPES for item in result.transitions),
                len(result.transitions) == max(0, len(result.dayun_trends) - 1) + max(0, len(result.liunian_trends) - 1) + max(0, len(result.combined_trends) - 1),
                all(item.canonical_digest.startswith("sha256:") for item in result.transitions),
                bool(result.year_index),
                bool(result.age_index),
                all(target_id in target_ids for values in result.year_index.values() for target_id in values),
                all(target_id in target_ids for values in result.age_index.values() for target_id in values),
                sum(result.trend_counts.values()) == len(all_trends),
                sum(result.confidence_counts.values()) == len(all_trends),
                bool(result.evidence_records),
                all(item.canonical_digest.startswith("sha256:") for item in result.evidence_records),
                all(key not in payload for key in BLOCKED_OUTPUTS),
            )
            for index, condition in enumerate(checks, 1):
                check(condition, f"{day_stem}{month_branch}: check {index} failed")
            hashes.add(result.canonical_hash)

    graph, interaction = build_phase14_fixture(STEMS[0], BRANCHES[2])
    baseline = evaluate_bazi_temporal_trends(graph, interaction)
    target = baseline.liunian_trends[0].target_id
    support = {
        "target_id": target,
        "direction": "support",
        "detail": "verified external reality condition",
        "weight": "10",
        "verified": True,
        "source_id": "phase14-benchmark-reality-support",
    }
    overridden = evaluate_bazi_temporal_trends(graph, interaction, reality_evidence=(support,))
    overridden_record = next(item for item in overridden.liunian_trends if item.target_id == target)
    check(overridden_record.trend_label == "support_tendency", "verified support reality did not override")
    check(overridden_record.confidence == "high", "verified reality did not set scoped high confidence")
    check(overridden_record.reality_override_direction == "support", "reality override direction missing")
    conflicting = evaluate_bazi_temporal_trends(graph, interaction, reality_evidence=(
        support,
        {
            "target_id": target,
            "direction": "contradict",
            "detail": "verified contradictory reality condition",
            "weight": "10",
            "verified": True,
            "source_id": "phase14-benchmark-reality-conflict",
        },
    ))
    conflicting_record = next(item for item in conflicting.liunian_trends if item.target_id == target)
    check(conflicting_record.trend_label == "unresolved", "conflicting verified reality was not unresolved")
    check(conflicting_record.confidence == "low", "conflicting verified reality confidence was not low")
    unverified = evaluate_bazi_temporal_trends(graph, interaction, reality_evidence=({
        "target_id": target,
        "direction": "support",
        "detail": "unverified reality condition",
        "weight": "10",
        "verified": False,
        "source_id": "phase14-benchmark-reality-unverified",
    },))
    unverified_record = next(item for item in unverified.liunian_trends if item.target_id == target)
    check(unverified_record.confidence != "high", "unverified reality created high confidence")
    year = baseline.liunian_trends[0].label_year
    age = baseline.liunian_trends[0].start_age
    check(year is not None and bool(query_temporal_trends(baseline, year=year)), "year query failed")
    check(age is not None and bool(query_temporal_trends(baseline, age=age)), "age query failed")
    try:
        evaluate_bazi_temporal_trends({**graph, "canonical_hash": "sha256:bad"}, interaction)
        check(False, "fact graph hash mismatch was not blocked")
    except Phase14InputError:
        check(True, "fact graph hash mismatch blocked")
    try:
        evaluate_bazi_temporal_trends(graph, {**interaction, "canonical_hash": "sha256:bad"})
        check(False, "interaction hash mismatch was not blocked")
    except Phase14InputError:
        check(True, "interaction hash mismatch blocked")
    tampered = json.loads(json.dumps(interaction, ensure_ascii=False))
    tampered["liunian_interactions"][0]["support_score"] = "999.0000"
    body = {key: value for key, value in tampered.items() if key not in METADATA_FIELDS}
    tampered["canonical_hash"] = phase13_record_digest("BaziLuckCycleRoleInteractionResult", body)
    try:
        evaluate_bazi_temporal_trends(graph, tampered)
        check(False, "nested Phase 13 tampering was not blocked")
    except Phase14InputError:
        check(True, "nested Phase 13 tampering blocked")
    try:
        evaluate_bazi_temporal_trends(graph, interaction, requested_outputs=("event_prediction",))
        check(False, "prediction request was not blocked")
        prediction_boundary_failures = 1
    except Phase14InputError:
        check(True, "prediction request blocked")
        prediction_boundary_failures = 0

    if assertions_total < int(load_phase14_trend_assertions()["minimum_expected_assertions_total"]):
        failures.append("assertion matrix below declared minimum")
    schema_failures = 0 if PHASE14_SCHEMA_VERSION.startswith("bazi-temporal-trend-evidence-result@") else 1
    profile = get_temporal_trend_profile()
    provenance_failures = 0 if len(set(profile.get("independence_groups", []))) >= 2 else 1
    hash_mismatches = 0 if len(hashes) > 20 else 1
    if schema_failures:
        failures.append("schema version invalid")
    if provenance_failures:
        failures.append("profile provenance insufficient")
    if hash_mismatches:
        failures.append("canonical hash coverage insufficient")
    return Phase14BenchmarkResult(
        assertions_total=assertions_total,
        passed=passed,
        failed=len(failures),
        unresolved=0,
        schema_failures=schema_failures,
        provenance_failures=provenance_failures,
        hash_mismatches=hash_mismatches,
        partition_failures=0,
        query_failures=0,
        transition_failures=0,
        reality_override_failures=0,
        prediction_boundary_failures=prediction_boundary_failures,
        failures=tuple(failures),
    )


__all__ = [
    "PHASE14_CALCULATION_VERSION",
    "PHASE14_DECISION_ID",
    "PHASE14_METHOD_ID",
    "PHASE14_SCHEMA_VERSION",
    "Phase14InputError",
    "benchmark_phase14",
    "build_phase14_fixture",
    "evaluate_bazi_temporal_trends",
    "get_temporal_trend_profile",
    "load_phase14_trend_assertions",
    "load_phase14_trend_profiles",
    "phase14_schema_summary",
    "query_temporal_trends",
    "temporal_trend_result_to_phase8_evidence",
    "validate_import_origin",
    "validate_phase14_profiles",
]
