from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from copy import deepcopy
from functools import lru_cache
import json
from importlib.resources import files
from typing import Mapping, Sequence

from .contracts.serialization import digest
from .derived.static_engine import (
    BRANCHES,
    HIDDEN_STEMS,
    STEMS,
    TEN_GOD_LABELS,
    map_ten_god,
)
from .phase8_engine import validate_import_origin
from .phase13_contracts import record_digest as phase13_record_digest
from .phase14 import _build_phase14_fixture_cached, evaluate_bazi_temporal_trends
from .phase14_contracts import record_digest as phase14_record_digest
from .phase15_contracts import (
    BaziTenGodDomainJudgementResult,
    CONFLICT_STATUSES,
    DOMAINS,
    DOMAIN_LABELS,
    PHASE15_CALCULATION_VERSION,
    PHASE15_DECISION_ID,
    PHASE15_METHOD_ID,
    PHASE15_SCHEMA_VERSION,
    TARGET_TYPES,
    CrossDomainConflictRecord,
    DomainContribution,
    DomainJudgementCandidate,
    DomainJudgementEvidenceRecord,
    DomainRealityEvidenceRecord,
    DynamicTenGodHit,
    NatalTenGodContext,
    Phase15BenchmarkResult,
    Phase15InputError,
    record_digest,
)

DEFAULT_PHASE15_PROFILE_ID = "tengod-domain-judgement-r1@0.1"
PROFILE_RESOURCE = "phase15_tengod_domain_profiles_v0.1.json"
ASSERTION_RESOURCE = "phase15_tengod_domain_assertions_v0.1.json"
METADATA_FIELDS = {
    "canonical_hash",
    "schema_version",
    "method_id",
    "calculation_version",
    "prediction_validity",
    "domain_judgement_validity",
}
BLOCKED_OUTPUTS = {
    "auspiciousness",
    "good_bad",
    "fortune_judgement",
    "event_prediction",
    "promotion_prediction",
    "dismissal_prediction",
    "profit_prediction",
    "loss_prediction",
    "marriage_prediction",
    "reunion_prediction",
    "exam_admission_prediction",
    "career_prediction",
    "wealth_prediction",
    "relationship_prediction",
    "health_prediction",
    "natural_language_renderer",
}
TEN_GOD_CODES = tuple(sorted(TEN_GOD_LABELS))
TEN_GOD_FAMILIES = ("peer", "output", "wealth", "authority", "resource")
POSITIONS = ("year", "month", "day", "hour")


def _decimal(value: object, name: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise Phase15InputError(f"{name} must be decimal-compatible") from exc
    if not number.is_finite():
        raise Phase15InputError(f"{name} must be finite")
    return number


def _score(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")


def _resource(name: str, label: str) -> dict[str, object]:
    value = json.loads(files("mingli.derived.data").joinpath(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


@lru_cache(maxsize=1)
def _load_phase15_domain_profiles_cached() -> dict[str, object]:
    return _resource(PROFILE_RESOURCE, "Phase 15 profile manifest")


def load_phase15_domain_profiles() -> dict[str, object]:
    return deepcopy(_load_phase15_domain_profiles_cached())


@lru_cache(maxsize=1)
def _load_phase15_domain_assertions_cached() -> dict[str, object]:
    return _resource(ASSERTION_RESOURCE, "Phase 15 assertion manifest")


def load_phase15_domain_assertions() -> dict[str, object]:
    return deepcopy(_load_phase15_domain_assertions_cached())


@lru_cache(maxsize=8)
def _get_tengod_domain_profile_cached(profile_id: str) -> dict[str, object]:
    raw = _load_phase15_domain_profiles_cached().get("profiles")
    if not isinstance(raw, list):
        raise ValueError("profiles must be an array")
    for item in raw:
        if isinstance(item, dict) and item.get("profile_id") == profile_id:
            result = dict(item)
            result["canonical_hash"] = digest({
                "record_type": "TenGodDomainProfile",
                "payload": {key: value for key, value in result.items() if key != "canonical_hash"},
            })
            return result
    raise ValueError(f"unsupported Phase 15 profile: {profile_id}")


def get_tengod_domain_profile(profile_id: str = DEFAULT_PHASE15_PROFILE_ID) -> dict[str, object]:
    return deepcopy(_get_tengod_domain_profile_cached(profile_id))


def validate_phase15_profiles() -> tuple[str, ...]:
    issues: list[str] = []
    try:
        profile = get_tengod_domain_profile()
        if profile.get("reviewed") is not True:
            issues.append("reviewed must be true")
        if tuple(profile.get("domains", ())) != DOMAINS:
            issues.append("domains must exactly match Phase 15 domains")
        weights = profile.get("ten_god_domain_weights")
        if not isinstance(weights, Mapping) or set(weights) != set(TEN_GOD_CODES):
            issues.append("ten_god_domain_weights must cover all exact TenGod codes")
        else:
            for code, domain_weights in weights.items():
                if not isinstance(domain_weights, Mapping) or set(domain_weights) != set(DOMAINS):
                    issues.append(f"{code} domain weights are incomplete")
                    continue
                for domain, value in domain_weights.items():
                    number = _decimal(value, f"{code}.{domain}")
                    if not Decimal("0") <= number <= Decimal("1"):
                        issues.append(f"{code}.{domain} must be between 0 and 1")
        themes = profile.get("family_theme_codes")
        if not isinstance(themes, Mapping) or set(themes) != set(TEN_GOD_FAMILIES):
            issues.append("family_theme_codes must cover all TenGod families")
        else:
            for family, domain_themes in themes.items():
                if not isinstance(domain_themes, Mapping) or set(domain_themes) != set(DOMAINS):
                    issues.append(f"{family} theme map is incomplete")
                elif any(not isinstance(value, list) or not value for value in domain_themes.values()):
                    issues.append(f"{family} theme codes must be non-empty arrays")
        required_maps = {
            "component_weights": {"dayun", "liunian"},
            "natal_visible_weights": set(POSITIONS),
            "natal_hidden_position_weights": set(POSITIONS),
            "hidden_ordinal_weights": {"1", "2", "3"},
            "context_weights": {"temporal_trend", "natal_context"},
            "thresholds": {"activation_min", "support_ratio_min", "conflict_ratio_min", "mixed_secondary_min"},
        }
        for field_name, required in required_maps.items():
            value = profile.get(field_name)
            if not isinstance(value, Mapping) or set(value) != required:
                issues.append(f"{field_name} is incomplete")
                continue
            for key, raw_value in value.items():
                number = _decimal(raw_value, f"{field_name}.{key}")
                if number < 0:
                    issues.append(f"{field_name}.{key} must be non-negative")
        component = profile.get("component_weights")
        if isinstance(component, Mapping):
            total = sum((_decimal(value, "component_weight") for value in component.values()), Decimal("0"))
            if total != Decimal("1"):
                issues.append("component_weights must sum to 1")
        if len(set(profile.get("independence_groups", []))) < 3:
            issues.append("at least three independence groups are required")
        if not profile.get("explicit_exclusions"):
            issues.append("explicit_exclusions are required")
        if not profile.get("claim_boundary_codes"):
            issues.append("claim_boundary_codes are required")
        if not str(profile.get("canonical_hash", "")).startswith("sha256:"):
            issues.append("profile canonical hash is invalid")
    except (ValueError, Phase15InputError) as exc:
        issues.append(str(exc))
    return tuple(issues)


def phase15_schema_summary() -> dict[str, object]:
    return {
        "decision_id": PHASE15_DECISION_ID,
        "schema_version": PHASE15_SCHEMA_VERSION,
        "method_id": PHASE15_METHOD_ID,
        "calculation_version": PHASE15_CALCULATION_VERSION,
        "profile_id": DEFAULT_PHASE15_PROFILE_ID,
        "prediction_validity": "not_evaluated",
        "domain_judgement_validity": "candidate_only",
        "domains": list(DOMAINS),
        "domain_labels": list(DOMAIN_LABELS),
        "target_types": list(TARGET_TYPES),
        "output_boundary": "tengod_domain_tendency_candidate_only_no_concrete_event_prediction",
    }


def _verify_fact_graph(value: Mapping[str, object]) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase15InputError("Phase 7 Fact Graph missing canonical_hash")
    if value.get("schema_version") != "bazi-fact-graph-result@0.1":
        raise Phase15InputError("unsupported Phase 7 Fact Graph schema")
    if value.get("prediction_validity") != "not_evaluated":
        raise Phase15InputError("Phase 7 Fact Graph prediction_validity must be not_evaluated")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    if found != digest({"record_type": "BaziFactGraphResult", "payload": body}):
        raise Phase15InputError("Phase 7 Fact Graph canonical_hash mismatch")
    if not isinstance(value.get("timeline"), Mapping):
        raise Phase15InputError("Phase 7 Fact Graph timeline is required")
    return found


def _verify_phase13(value: Mapping[str, object], fact_graph_hash: str) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase15InputError("Phase 13 Interaction Result missing canonical_hash")
    if value.get("schema_version") != "bazi-luck-cycle-role-interaction-result@0.1":
        raise Phase15InputError("unsupported Phase 13 Interaction Result schema")
    if value.get("prediction_validity") != "not_evaluated":
        raise Phase15InputError("Phase 13 Interaction Result prediction_validity must be not_evaluated")
    if value.get("fact_graph_hash") != fact_graph_hash:
        raise Phase15InputError("Phase 7 and Phase 13 fact_graph_hash mismatch")
    for key, record_type in (
        ("dayun_interactions", "PeriodRoleInteraction"),
        ("liunian_interactions", "PeriodRoleInteraction"),
        ("combined_windows", "CombinedCycleWindow"),
        ("evidence_records", "CycleInteractionEvidenceRecord"),
    ):
        raw = value.get(key)
        if not isinstance(raw, list):
            raise Phase15InputError(f"Phase 13 {key} must be an array")
        for item in raw:
            if not isinstance(item, Mapping):
                raise Phase15InputError(f"Phase 13 {key} entry must be an object")
            if item.get("canonical_digest") != phase13_record_digest(record_type, item):
                raise Phase15InputError(f"Phase 13 {key} canonical_digest mismatch")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    if found != phase13_record_digest("BaziLuckCycleRoleInteractionResult", body):
        raise Phase15InputError("Phase 13 Interaction Result canonical_hash mismatch")
    return found


def _verify_phase14(
    value: Mapping[str, object],
    fact_graph_hash: str,
    interaction_result_hash: str,
) -> str:
    found = value.get("canonical_hash")
    if not isinstance(found, str) or not found.startswith("sha256:"):
        raise Phase15InputError("Phase 14 Temporal Trend Result missing canonical_hash")
    if value.get("schema_version") != "bazi-temporal-trend-evidence-result@0.1":
        raise Phase15InputError("unsupported Phase 14 Temporal Trend Result schema")
    if value.get("prediction_validity") != "not_evaluated":
        raise Phase15InputError("Phase 14 Temporal Trend Result prediction_validity must be not_evaluated")
    if value.get("fact_graph_hash") != fact_graph_hash:
        raise Phase15InputError("Phase 7 and Phase 14 fact_graph_hash mismatch")
    if value.get("interaction_result_hash") != interaction_result_hash:
        raise Phase15InputError("Phase 13 and Phase 14 interaction_result_hash mismatch")
    for key, record_type in (
        ("dayun_trends", "TemporalTrendRecord"),
        ("liunian_trends", "TemporalTrendRecord"),
        ("combined_trends", "TemporalTrendRecord"),
        ("transitions", "TrendTransitionRecord"),
        ("reality_evidence", "TemporalRealityEvidenceRecord"),
        ("evidence_records", "TemporalTrendEvidenceRecord"),
    ):
        raw = value.get(key)
        if not isinstance(raw, list):
            raise Phase15InputError(f"Phase 14 {key} must be an array")
        for item in raw:
            if not isinstance(item, Mapping):
                raise Phase15InputError(f"Phase 14 {key} entry must be an object")
            if item.get("canonical_digest") != phase14_record_digest(record_type, item):
                raise Phase15InputError(f"Phase 14 {key} canonical_digest mismatch")
    body = {key: child for key, child in value.items() if key not in METADATA_FIELDS}
    if found != phase14_record_digest("BaziTemporalTrendEvidenceResult", body):
        raise Phase15InputError("Phase 14 Temporal Trend Result canonical_hash mismatch")
    return found


def _pillar_nodes(graph: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    raw = graph.get("nodes")
    if not isinstance(raw, list):
        raise Phase15InputError("Phase 7 Fact Graph nodes are required")
    records: dict[str, Mapping[str, object]] = {}
    for item in raw:
        if isinstance(item, Mapping) and item.get("node_type") == "Pillar":
            position = str(item.get("position"))
            stem = str(item.get("stem"))
            branch = str(item.get("branch"))
            if position in POSITIONS and stem in STEMS and branch in BRANCHES:
                records[position] = item
    if set(records) != set(POSITIONS):
        raise Phase15InputError("Phase 7 Fact Graph must contain four natal pillars")
    return tuple(records[position] for position in POSITIONS)


def _natal_context(graph: Mapping[str, object], profile: Mapping[str, object]) -> NatalTenGodContext:
    pillars = _pillar_nodes(graph)
    day_master = str(pillars[2]["stem"])
    visible = {code: Decimal("0") for code in TEN_GOD_CODES}
    hidden = {code: Decimal("0") for code in TEN_GOD_CODES}
    source_ids: list[str] = []
    visible_weights = profile["natal_visible_weights"]
    hidden_position_weights = profile["natal_hidden_position_weights"]
    ordinal_weights = profile["hidden_ordinal_weights"]
    assert isinstance(visible_weights, Mapping)
    assert isinstance(hidden_position_weights, Mapping)
    assert isinstance(ordinal_weights, Mapping)
    for pillar in pillars:
        position = str(pillar["position"])
        stem = str(pillar["stem"])
        branch = str(pillar["branch"])
        visible_record = map_ten_god(day_master, stem)
        visible[visible_record.code] += _decimal(visible_weights[position], f"visible.{position}")
        source_ids.append(f"stem:{position}:{stem}")
        for ordinal, hidden_stem in enumerate(HIDDEN_STEMS[branch], 1):
            hidden_record = map_ten_god(day_master, hidden_stem)
            hidden[hidden_record.code] += (
                _decimal(hidden_position_weights[position], f"hidden.{position}")
                * _decimal(ordinal_weights[str(ordinal)], f"hidden.ordinal.{ordinal}")
            )
            source_ids.append(f"hidden-stem:{position}:{branch}:{ordinal}:{hidden_stem}")
    total = {code: visible[code] + hidden[code] for code in TEN_GOD_CODES}
    domain_weights = profile["ten_god_domain_weights"]
    assert isinstance(domain_weights, Mapping)
    domain_scores: dict[str, Decimal] = {domain: Decimal("0") for domain in DOMAINS}
    for code, score in total.items():
        code_weights = domain_weights[code]
        assert isinstance(code_weights, Mapping)
        for domain in DOMAINS:
            domain_scores[domain] += score * _decimal(code_weights[domain], f"domain_weight.{code}.{domain}")
    payload = {
        "day_master": day_master,
        "visible_scores": {code: _score(visible[code]) for code in TEN_GOD_CODES},
        "hidden_scores": {code: _score(hidden[code]) for code in TEN_GOD_CODES},
        "total_scores": {code: _score(total[code]) for code in TEN_GOD_CODES},
        "domain_activation_scores": {domain: _score(domain_scores[domain]) for domain in DOMAINS},
        "source_node_ids": sorted(set(source_ids)),
        "profile_id": str(profile["profile_id"]),
    }
    return NatalTenGodContext(
        day_master=day_master,
        visible_scores=payload["visible_scores"],
        hidden_scores=payload["hidden_scores"],
        total_scores=payload["total_scores"],
        domain_activation_scores=payload["domain_activation_scores"],
        source_node_ids=tuple(payload["source_node_ids"]),
        profile_id=payload["profile_id"],
        canonical_digest=record_digest("NatalTenGodContext", payload),
    )


def _interaction_maps(interaction: Mapping[str, object]) -> tuple[
    dict[str, Mapping[str, object]],
    dict[str, Mapping[str, object]],
    dict[str, Mapping[str, object]],
]:
    result: list[dict[str, Mapping[str, object]]] = []
    for key, id_field in (
        ("dayun_interactions", "period_id"),
        ("liunian_interactions", "period_id"),
        ("combined_windows", "window_id"),
    ):
        raw = interaction[key]
        assert isinstance(raw, list)
        result.append({str(item[id_field]): item for item in raw if isinstance(item, Mapping)})
    return result[0], result[1], result[2]


def _trend_map(trend_result: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for key in ("dayun_trends", "liunian_trends", "combined_trends"):
        raw = trend_result[key]
        assert isinstance(raw, list)
        for item in raw:
            if isinstance(item, Mapping):
                target_id = str(item.get("target_id"))
                if target_id in result:
                    raise Phase15InputError(f"duplicate Phase 14 target_id: {target_id}")
                result[target_id] = item
    return result


def _dynamic_hit(
    *,
    target_id: str,
    target_type: str,
    component_period_id: str,
    component_type: str,
    role_hit: Mapping[str, object],
    component_weight: Decimal,
    day_master: str,
    graph_hash: str,
    interaction_hash: str,
    trend_hash: str,
    profile: Mapping[str, object],
) -> DynamicTenGodHit:
    source_symbol = str(role_hit.get("source_symbol"))
    if source_symbol not in STEMS:
        raise Phase15InputError(f"Phase 13 role hit source symbol is not a stem: {source_symbol}")
    ten_god = map_ten_god(day_master, source_symbol)
    family, polarity = ten_god.code.rsplit("_", 2)[0], "same_polarity" if ten_god.code.endswith("same_polarity") else "opposite_polarity"
    raw_score = _decimal(role_hit.get("weighted_score", "0"), "role_hit.weighted_score")
    effective = raw_score * component_weight
    payload = {
        "hit_id": f"tengod:{target_id}:{component_type}:{role_hit.get('hit_id')}",
        "target_id": target_id,
        "target_type": target_type,
        "component_period_id": component_period_id,
        "component_type": component_type,
        "source_type": str(role_hit.get("source_type")),
        "source_symbol": source_symbol,
        "ordinal": int(role_hit.get("ordinal", 0)),
        "ten_god_code": ten_god.code,
        "ten_god_label": ten_god.label,
        "ten_god_family": family,
        "polarity_relation": polarity,
        "element": str(role_hit.get("element")),
        "xiji_role": str(role_hit.get("role")),
        "role_direction": str(role_hit.get("direction")),
        "raw_score": _score(raw_score),
        "component_weight": _score(component_weight),
        "effective_score": _score(effective),
        "source_hit_digest": str(role_hit.get("canonical_digest")),
        "source_result_hashes": [graph_hash, interaction_hash, trend_hash],
        "profile_id": str(profile["profile_id"]),
    }
    if payload["source_type"] not in {"stem", "branch_hidden"}:
        raise Phase15InputError("Phase 13 role hit source_type is unsupported")
    if payload["role_direction"] not in {"support", "conflict", "neutral", "unresolved"}:
        raise Phase15InputError("Phase 13 role direction is unsupported")
    return DynamicTenGodHit(
        hit_id=payload["hit_id"],
        target_id=target_id,
        target_type=target_type,  # type: ignore[arg-type]
        component_period_id=component_period_id,
        component_type=component_type,  # type: ignore[arg-type]
        source_type=payload["source_type"],  # type: ignore[arg-type]
        source_symbol=source_symbol,
        ordinal=payload["ordinal"],
        ten_god_code=ten_god.code,
        ten_god_label=ten_god.label,
        ten_god_family=family,
        polarity_relation=polarity,  # type: ignore[arg-type]
        element=payload["element"],
        xiji_role=payload["xiji_role"],
        role_direction=payload["role_direction"],  # type: ignore[arg-type]
        raw_score=payload["raw_score"],
        component_weight=payload["component_weight"],
        effective_score=payload["effective_score"],
        source_hit_digest=payload["source_hit_digest"],
        source_result_hashes=(graph_hash, interaction_hash, trend_hash),
        profile_id=payload["profile_id"],
        canonical_digest=record_digest("DynamicTenGodHit", payload),
    )


def _hits_for_period(
    target_id: str,
    target_type: str,
    interaction_record: Mapping[str, object],
    component_type: str,
    component_weight: Decimal,
    day_master: str,
    graph_hash: str,
    interaction_hash: str,
    trend_hash: str,
    profile: Mapping[str, object],
) -> tuple[DynamicTenGodHit, ...]:
    raw_hits = interaction_record.get("role_hits")
    if not isinstance(raw_hits, list) or not raw_hits:
        raise Phase15InputError(f"Phase 13 interaction has no role_hits: {target_id}")
    component_period_id = str(interaction_record.get("period_id"))
    return tuple(
        _dynamic_hit(
            target_id=target_id,
            target_type=target_type,
            component_period_id=component_period_id,
            component_type=component_type,
            role_hit=item,
            component_weight=component_weight,
            day_master=day_master,
            graph_hash=graph_hash,
            interaction_hash=interaction_hash,
            trend_hash=trend_hash,
            profile=profile,
        )
        for item in raw_hits
        if isinstance(item, Mapping)
    )


def _all_dynamic_hits(
    interaction: Mapping[str, object],
    trend_result: Mapping[str, object],
    day_master: str,
    graph_hash: str,
    interaction_hash: str,
    trend_hash: str,
    profile: Mapping[str, object],
) -> tuple[DynamicTenGodHit, ...]:
    dayun, liunian, windows = _interaction_maps(interaction)
    trends = _trend_map(trend_result)
    component_weights = profile["component_weights"]
    assert isinstance(component_weights, Mapping)
    records: list[DynamicTenGodHit] = []
    for target_id, trend in sorted(trends.items()):
        target_type = str(trend.get("target_type"))
        if target_type == "dayun":
            source = dayun.get(target_id)
            if source is None:
                raise Phase15InputError(f"Phase 14 dayun target missing from Phase 13: {target_id}")
            records.extend(_hits_for_period(
                target_id, target_type, source, "dayun", Decimal("1"), day_master,
                graph_hash, interaction_hash, trend_hash, profile,
            ))
        elif target_type == "liunian":
            source = liunian.get(target_id)
            if source is None:
                raise Phase15InputError(f"Phase 14 liunian target missing from Phase 13: {target_id}")
            records.extend(_hits_for_period(
                target_id, target_type, source, "liunian", Decimal("1"), day_master,
                graph_hash, interaction_hash, trend_hash, profile,
            ))
        elif target_type == "combined_window":
            window = windows.get(target_id)
            if window is None:
                raise Phase15InputError(f"Phase 14 combined target missing from Phase 13: {target_id}")
            dayun_id = str(window.get("dayun_period_id"))
            liunian_id = str(window.get("liunian_period_id"))
            if dayun_id not in dayun or liunian_id not in liunian:
                raise Phase15InputError(f"combined window component is missing: {target_id}")
            records.extend(_hits_for_period(
                target_id, target_type, dayun[dayun_id], "dayun",
                _decimal(component_weights["dayun"], "component.dayun"), day_master,
                graph_hash, interaction_hash, trend_hash, profile,
            ))
            records.extend(_hits_for_period(
                target_id, target_type, liunian[liunian_id], "liunian",
                _decimal(component_weights["liunian"], "component.liunian"), day_master,
                graph_hash, interaction_hash, trend_hash, profile,
            ))
        else:
            raise Phase15InputError(f"unsupported Phase 14 target_type: {target_type}")
    return tuple(sorted(records, key=lambda item: item.hit_id))


def _domain_contributions(
    hits: Sequence[DynamicTenGodHit],
    graph_hash: str,
    interaction_hash: str,
    trend_hash: str,
    profile: Mapping[str, object],
) -> tuple[DomainContribution, ...]:
    weights = profile["ten_god_domain_weights"]
    themes = profile["family_theme_codes"]
    assert isinstance(weights, Mapping) and isinstance(themes, Mapping)
    records: list[DomainContribution] = []
    for hit in hits:
        code_weights = weights[hit.ten_god_code]
        family_themes = themes[hit.ten_god_family]
        assert isinstance(code_weights, Mapping) and isinstance(family_themes, Mapping)
        for domain in DOMAINS:
            theme_weight = _decimal(code_weights[domain], f"theme_weight.{hit.ten_god_code}.{domain}")
            contribution = _decimal(hit.effective_score, "effective_score") * theme_weight
            payload = {
                "contribution_id": f"domain-contribution:{hit.hit_id}:{domain}",
                "target_id": hit.target_id,
                "domain": domain,
                "ten_god_code": hit.ten_god_code,
                "theme_codes": sorted(set(str(value) for value in family_themes[domain])),
                "direction": hit.role_direction,
                "theme_weight": _score(theme_weight),
                "effective_score": hit.effective_score,
                "contribution_score": _score(contribution),
                "source_hit_id": hit.hit_id,
                "source_result_hashes": [graph_hash, interaction_hash, trend_hash],
                "profile_id": str(profile["profile_id"]),
            }
            records.append(DomainContribution(
                contribution_id=payload["contribution_id"],
                target_id=hit.target_id,
                domain=domain,
                ten_god_code=hit.ten_god_code,
                theme_codes=tuple(payload["theme_codes"]),
                direction=hit.role_direction,
                theme_weight=payload["theme_weight"],
                effective_score=hit.effective_score,
                contribution_score=payload["contribution_score"],
                source_hit_id=hit.hit_id,
                source_result_hashes=(graph_hash, interaction_hash, trend_hash),
                profile_id=payload["profile_id"],
                canonical_digest=record_digest("DomainContribution", payload),
            ))
    return tuple(sorted(records, key=lambda item: item.contribution_id))


def _parse_reality(
    raw_items: Sequence[Mapping[str, object]],
    valid_targets: set[str],
) -> tuple[DomainRealityEvidenceRecord, ...]:
    records: list[DomainRealityEvidenceRecord] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items, 1):
        target_id = str(item.get("target_id", ""))
        domain = str(item.get("domain", ""))
        direction = str(item.get("direction", ""))
        detail = str(item.get("detail", "")).strip()
        source_id = str(item.get("source_id", "")).strip()
        evidence_id = str(item.get("evidence_id") or f"phase15-reality:{target_id}:{domain}:{index}")
        verified = item.get("verified") is True
        weight = _decimal(item.get("weight", "0"), "reality.weight")
        if target_id not in valid_targets:
            raise Phase15InputError(f"reality evidence target is unknown: {target_id}")
        if domain not in DOMAINS:
            raise Phase15InputError(f"reality evidence domain is unknown: {domain}")
        if direction not in {"support", "contradict"}:
            raise Phase15InputError("reality evidence direction must be support or contradict")
        if not detail or not source_id:
            raise Phase15InputError("reality evidence detail and source_id are required")
        if not Decimal("0") <= weight <= Decimal("10"):
            raise Phase15InputError("reality evidence weight must be between 0 and 10")
        if evidence_id in seen:
            raise Phase15InputError(f"duplicate reality evidence_id: {evidence_id}")
        seen.add(evidence_id)
        payload = {
            "evidence_id": evidence_id,
            "target_id": target_id,
            "domain": domain,
            "direction": direction,
            "detail": detail,
            "weight": _score(weight),
            "verified": verified,
            "source_id": source_id,
        }
        records.append(DomainRealityEvidenceRecord(
            evidence_id=evidence_id,
            target_id=target_id,
            domain=domain,
            direction=direction,  # type: ignore[arg-type]
            detail=detail,
            weight=payload["weight"],
            verified=verified,
            source_id=source_id,
            canonical_digest=record_digest("DomainRealityEvidenceRecord", payload),
        ))
    return tuple(sorted(records, key=lambda item: item.evidence_id))


def _domain_label(
    profile: Mapping[str, object],
    activation: Decimal,
    support_ratio: Decimal,
    conflict_ratio: Decimal,
    unresolved_count: int,
) -> str:
    thresholds = profile["thresholds"]
    assert isinstance(thresholds, Mapping)
    if unresolved_count:
        return "unresolved"
    if activation < _decimal(thresholds["activation_min"], "activation_min"):
        return "neutral_tendency"
    support_min = _decimal(thresholds["support_ratio_min"], "support_ratio_min")
    conflict_min = _decimal(thresholds["conflict_ratio_min"], "conflict_ratio_min")
    mixed_min = _decimal(thresholds["mixed_secondary_min"], "mixed_secondary_min")
    if support_ratio >= support_min and conflict_ratio < mixed_min:
        return "support_tendency"
    if conflict_ratio >= conflict_min and support_ratio < mixed_min:
        return "conflict_tendency"
    if support_ratio >= mixed_min and conflict_ratio >= mixed_min:
        return "mixed_tendency"
    return "neutral_tendency"


def _judgement(
    *,
    trend: Mapping[str, object],
    domain: str,
    contributions: Sequence[DomainContribution],
    natal_context: NatalTenGodContext,
    reality: Sequence[DomainRealityEvidenceRecord],
    graph_hash: str,
    interaction_hash: str,
    trend_hash: str,
    profile: Mapping[str, object],
) -> DomainJudgementCandidate:
    target_id = str(trend.get("target_id"))
    context_weights = profile["context_weights"]
    assert isinstance(context_weights, Mapping)
    activation = sum((_decimal(item.contribution_score, "contribution_score") for item in contributions), Decimal("0"))
    support = sum((_decimal(item.contribution_score, "support") for item in contributions if item.direction == "support"), Decimal("0"))
    conflict = sum((_decimal(item.contribution_score, "conflict") for item in contributions if item.direction == "conflict"), Decimal("0"))
    neutral = sum((_decimal(item.contribution_score, "neutral") for item in contributions if item.direction == "neutral"), Decimal("0"))
    unresolved_count = sum(1 for item in contributions if item.direction == "unresolved")
    temporal_scale = _decimal(context_weights["temporal_trend"], "context.temporal") * min(Decimal("1"), activation)
    support += _decimal(trend.get("support_ratio", "0"), "trend.support_ratio") * temporal_scale
    conflict += _decimal(trend.get("conflict_ratio", "0"), "trend.conflict_ratio") * temporal_scale
    neutral += _decimal(trend.get("neutral_ratio", "0"), "trend.neutral_ratio") * temporal_scale
    if trend.get("trend_label") == "unresolved":
        unresolved_count += 1
    natal_score = (
        _decimal(natal_context.domain_activation_scores[domain], f"natal.{domain}")
        * _decimal(context_weights["natal_context"], "context.natal")
    )
    total = support + conflict + neutral
    if total:
        support_ratio = support / total
        conflict_ratio = conflict / total
        neutral_ratio = neutral / total
        net = (support - conflict) / total
    else:
        support_ratio = conflict_ratio = Decimal("0")
        neutral_ratio = Decimal("1")
        net = Decimal("0")
    label = _domain_label(profile, activation + natal_score, support_ratio, conflict_ratio, unresolved_count)
    verified_directions = {item.direction for item in reality if item.verified}
    override: str | None = None
    rationale = ["ten_god_domain_activation", "phase14_temporal_context"]
    if len(verified_directions) > 1:
        label = "unresolved"
        rationale.append("conflicting_verified_reality")
    elif len(verified_directions) == 1:
        override = next(iter(verified_directions))
        label = "support_tendency" if override == "support" else "conflict_tendency"
        rationale.append("verified_reality_hard_override")
    elif reality:
        rationale.append("unverified_reality_no_hard_override")
    if label in {"neutral_tendency", "unresolved"}:
        confidence = "low"
        rationale.append("low_confidence_boundary")
    elif override:
        confidence = "high"
        rationale.append("high_confidence_reality_scope_only")
    else:
        confidence = "medium"
        rationale.append("structural_only_medium_ceiling")
    code_scores: dict[str, Decimal] = {}
    theme_scores: dict[str, Decimal] = {}
    for item in contributions:
        score = _decimal(item.contribution_score, "contribution_score")
        code_scores[item.ten_god_code] = code_scores.get(item.ten_god_code, Decimal("0")) + score
        for theme in item.theme_codes:
            theme_scores[theme] = theme_scores.get(theme, Decimal("0")) + score
    top_codes = tuple(code for code, _ in sorted(code_scores.items(), key=lambda item: (-item[1], item[0]))[:3])
    top_themes = tuple(theme for theme, _ in sorted(theme_scores.items(), key=lambda item: (-item[1], item[0]))[:6])
    payload = {
        "judgement_id": f"domain-judgement:{target_id}:{domain}",
        "target_id": target_id,
        "target_type": str(trend.get("target_type")),
        "domain": domain,
        "sequence_index": int(trend["sequence_index"]) if trend.get("sequence_index") is not None else None,
        "label_year": int(trend["label_year"]) if trend.get("label_year") is not None else None,
        "start_age": int(trend["start_age"]) if trend.get("start_age") is not None else None,
        "end_age": int(trend["end_age"]) if trend.get("end_age") is not None else None,
        "start_instant_utc": str(trend.get("start_instant_utc")),
        "end_instant_utc": str(trend.get("end_instant_utc")),
        "temporal_trend_label": str(trend.get("trend_label")),
        "temporal_trend_confidence": str(trend.get("confidence")),
        "activation_score": _score(activation + natal_score),
        "natal_context_score": _score(natal_score),
        "support_score": _score(support),
        "conflict_score": _score(conflict),
        "neutral_score": _score(neutral),
        "unresolved_count": unresolved_count,
        "support_ratio": _score(support_ratio),
        "conflict_ratio": _score(conflict_ratio),
        "neutral_ratio": _score(neutral_ratio),
        "net_balance": _score(net),
        "judgement_label": label,
        "confidence": confidence,
        "top_ten_gods": list(top_codes),
        "active_theme_codes": list(top_themes),
        "confidence_rationale_codes": sorted(set(rationale)),
        "reality_override_direction": override,
        "reality_evidence_ids": [item.evidence_id for item in reality],
        "claim_boundary_codes": list(profile["claim_boundary_codes"]),
        "source_contribution_ids": [item.contribution_id for item in contributions],
        "source_result_hashes": [graph_hash, interaction_hash, trend_hash],
        "profile_id": str(profile["profile_id"]),
    }
    return DomainJudgementCandidate(
        judgement_id=payload["judgement_id"],
        target_id=target_id,
        target_type=payload["target_type"],  # type: ignore[arg-type]
        domain=domain,
        sequence_index=payload["sequence_index"],
        label_year=payload["label_year"],
        start_age=payload["start_age"],
        end_age=payload["end_age"],
        start_instant_utc=payload["start_instant_utc"],
        end_instant_utc=payload["end_instant_utc"],
        temporal_trend_label=payload["temporal_trend_label"],
        temporal_trend_confidence=payload["temporal_trend_confidence"],
        activation_score=payload["activation_score"],
        natal_context_score=payload["natal_context_score"],
        support_score=payload["support_score"],
        conflict_score=payload["conflict_score"],
        neutral_score=payload["neutral_score"],
        unresolved_count=unresolved_count,
        support_ratio=payload["support_ratio"],
        conflict_ratio=payload["conflict_ratio"],
        neutral_ratio=payload["neutral_ratio"],
        net_balance=payload["net_balance"],
        judgement_label=label,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        top_ten_gods=top_codes,
        active_theme_codes=top_themes,
        confidence_rationale_codes=tuple(payload["confidence_rationale_codes"]),
        reality_override_direction=override,  # type: ignore[arg-type]
        reality_evidence_ids=tuple(payload["reality_evidence_ids"]),
        claim_boundary_codes=tuple(payload["claim_boundary_codes"]),
        source_contribution_ids=tuple(payload["source_contribution_ids"]),
        source_result_hashes=(graph_hash, interaction_hash, trend_hash),
        profile_id=payload["profile_id"],
        canonical_digest=record_digest("DomainJudgementCandidate", payload),
    )


def _cross_domain_conflicts(judgements: Sequence[DomainJudgementCandidate]) -> tuple[CrossDomainConflictRecord, ...]:
    targets = sorted({item.target_id for item in judgements})
    records: list[CrossDomainConflictRecord] = []
    for target_id in targets:
        target = [item for item in judgements if item.target_id == target_id]
        support = tuple(sorted(item.domain for item in target if item.judgement_label == "support_tendency"))
        conflict = tuple(sorted(item.domain for item in target if item.judgement_label == "conflict_tendency"))
        mixed = tuple(sorted(item.domain for item in target if item.judgement_label == "mixed_tendency"))
        unresolved = tuple(sorted(item.domain for item in target if item.judgement_label == "unresolved"))
        status = "unresolved" if unresolved else "cross_domain_conflict" if support and conflict else "no_conflict"
        payload = {
            "conflict_id": f"cross-domain:{target_id}",
            "target_id": target_id,
            "support_domains": list(support),
            "conflict_domains": list(conflict),
            "mixed_domains": list(mixed),
            "unresolved_domains": list(unresolved),
            "status": status,
        }
        records.append(CrossDomainConflictRecord(
            conflict_id=payload["conflict_id"],
            target_id=target_id,
            support_domains=support,
            conflict_domains=conflict,
            mixed_domains=mixed,
            unresolved_domains=unresolved,
            status=status,  # type: ignore[arg-type]
            canonical_digest=record_digest("CrossDomainConflictRecord", payload),
        ))
    return tuple(records)


def _evidence_records(
    judgements: Sequence[DomainJudgementCandidate],
    reality: Sequence[DomainRealityEvidenceRecord],
    trend_hash: str,
    profile: Mapping[str, object],
) -> tuple[DomainJudgementEvidenceRecord, ...]:
    records: list[DomainJudgementEvidenceRecord] = []
    for item in judgements:
        rows = (
            ("domain_support_ratio", "timing", "support", Decimal(item.support_ratio), 85),
            ("domain_conflict_ratio", "timing", "contradict", Decimal(item.conflict_ratio), 85),
            ("natal_domain_activation", "rule", "support", min(Decimal("1"), Decimal(item.natal_context_score)), 65),
        )
        for evidence_type, source_type, direction, ratio, priority in rows:
            if ratio == 0:
                continue
            contribution = min(Decimal("10"), ratio * Decimal("10"))
            payload = {
                "evidence_id": f"evidence:{item.target_id}:{item.domain}:{evidence_type}",
                "target_id": item.target_id,
                "domain": item.domain,
                "evidence_type": evidence_type,
                "source_type": source_type,
                "direction": direction,
                "contribution": _score(contribution),
                "priority": priority,
                "verified": True,
                "source_id": item.judgement_id,
                "source_result_hashes": [trend_hash],
                "profile_id": str(profile["profile_id"]),
            }
            records.append(DomainJudgementEvidenceRecord(
                evidence_id=payload["evidence_id"],
                target_id=item.target_id,
                domain=item.domain,
                evidence_type=evidence_type,
                source_type=source_type,  # type: ignore[arg-type]
                direction=direction,  # type: ignore[arg-type]
                contribution=payload["contribution"],
                priority=priority,
                verified=True,
                source_id=item.judgement_id,
                source_result_hashes=(trend_hash,),
                profile_id=payload["profile_id"],
                canonical_digest=record_digest("DomainJudgementEvidenceRecord", payload),
            ))
    for item in reality:
        payload = {
            "evidence_id": f"evidence:{item.evidence_id}",
            "target_id": item.target_id,
            "domain": item.domain,
            "evidence_type": "verified_reality" if item.verified else "unverified_reality",
            "source_type": "reality",
            "direction": item.direction,
            "contribution": item.weight,
            "priority": 100 if item.verified else 70,
            "verified": item.verified,
            "source_id": item.source_id,
            "source_result_hashes": [trend_hash],
            "profile_id": str(profile["profile_id"]),
        }
        records.append(DomainJudgementEvidenceRecord(
            evidence_id=payload["evidence_id"],
            target_id=item.target_id,
            domain=item.domain,
            evidence_type=payload["evidence_type"],
            source_type="reality",
            direction=item.direction,
            contribution=item.weight,
            priority=payload["priority"],
            verified=item.verified,
            source_id=item.source_id,
            source_result_hashes=(trend_hash,),
            profile_id=payload["profile_id"],
            canonical_digest=record_digest("DomainJudgementEvidenceRecord", payload),
        ))
    return tuple(sorted(records, key=lambda item: item.evidence_id))


def _indexes(
    judgements: Sequence[DomainJudgementCandidate],
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    years: dict[str, set[str]] = {}
    ages: dict[str, set[str]] = {}
    domains: dict[str, set[str]] = {domain: set() for domain in DOMAINS}
    for item in judgements:
        domains[item.domain].add(item.judgement_id)
        if item.label_year is not None:
            years.setdefault(str(item.label_year), set()).add(item.judgement_id)
        else:
            try:
                start_year = datetime.fromisoformat(item.start_instant_utc.replace("Z", "+00:00")).year
                end_year = datetime.fromisoformat(item.end_instant_utc.replace("Z", "+00:00")).year
                if 0 <= end_year - start_year <= 30:
                    for year in range(start_year, end_year + 1):
                        years.setdefault(str(year), set()).add(item.judgement_id)
            except ValueError:
                pass
        if item.start_age is not None:
            end_age = item.end_age if item.end_age is not None else item.start_age
            if 0 <= end_age - item.start_age <= 30:
                for age in range(item.start_age, end_age + 1):
                    ages.setdefault(str(age), set()).add(item.judgement_id)
    return (
        {key: tuple(sorted(value)) for key, value in sorted(years.items(), key=lambda row: int(row[0]))},
        {key: tuple(sorted(value)) for key, value in sorted(ages.items(), key=lambda row: int(row[0]))},
        {key: tuple(sorted(value)) for key, value in sorted(domains.items())},
    )


def evaluate_bazi_tengod_domains(
    fact_graph: Mapping[str, object],
    interaction_result: Mapping[str, object],
    temporal_trend_result: Mapping[str, object],
    *,
    reality_evidence: Sequence[Mapping[str, object]] = (),
    profile_id: str = DEFAULT_PHASE15_PROFILE_ID,
    requested_outputs: Sequence[str] = (),
) -> BaziTenGodDomainJudgementResult:
    if set(requested_outputs) & BLOCKED_OUTPUTS:
        raise Phase15InputError("Phase 15 cannot return concrete events, auspiciousness, domain predictions, or renderer outputs")
    if not isinstance(fact_graph, Mapping) or not fact_graph:
        raise Phase15InputError("Phase 7 Fact Graph is required")
    if not isinstance(interaction_result, Mapping) or not interaction_result:
        raise Phase15InputError("Phase 13 Interaction Result is required")
    if not isinstance(temporal_trend_result, Mapping) or not temporal_trend_result:
        raise Phase15InputError("Phase 14 Temporal Trend Result is required")
    profile = get_tengod_domain_profile(profile_id)
    graph_hash = _verify_fact_graph(fact_graph)
    interaction_hash = _verify_phase13(interaction_result, graph_hash)
    trend_hash = _verify_phase14(temporal_trend_result, graph_hash, interaction_hash)
    natal = _natal_context(fact_graph, profile)
    trends = _trend_map(temporal_trend_result)
    hits = _all_dynamic_hits(
        interaction_result, temporal_trend_result, natal.day_master,
        graph_hash, interaction_hash, trend_hash, profile,
    )
    contributions = _domain_contributions(hits, graph_hash, interaction_hash, trend_hash, profile)
    reality = _parse_reality(reality_evidence, set(trends))
    contribution_groups: dict[tuple[str, str], tuple[DomainContribution, ...]] = {}
    for target_id in sorted(trends):
        for domain in DOMAINS:
            contribution_groups[(target_id, domain)] = tuple(
                item for item in contributions if item.target_id == target_id and item.domain == domain
            )
    reality_groups: dict[tuple[str, str], tuple[DomainRealityEvidenceRecord, ...]] = {}
    for target_id in sorted(trends):
        for domain in DOMAINS:
            reality_groups[(target_id, domain)] = tuple(
                item for item in reality if item.target_id == target_id and item.domain == domain
            )
    judgements = tuple(
        _judgement(
            trend=trends[target_id],
            domain=domain,
            contributions=contribution_groups[(target_id, domain)],
            natal_context=natal,
            reality=reality_groups[(target_id, domain)],
            graph_hash=graph_hash,
            interaction_hash=interaction_hash,
            trend_hash=trend_hash,
            profile=profile,
        )
        for target_id in sorted(trends)
        for domain in DOMAINS
    )
    conflicts = _cross_domain_conflicts(judgements)
    evidence = _evidence_records(judgements, reality, trend_hash, profile)
    year_index, age_index, domain_index = _indexes(judgements)
    judgement_counts = {label: 0 for label in DOMAIN_LABELS}
    confidence_counts = {level: 0 for level in ("high", "medium", "low")}
    unresolved: list[dict[str, object]] = []
    for item in judgements:
        judgement_counts[item.judgement_label] += 1
        confidence_counts[item.confidence] += 1
        if item.judgement_label == "unresolved":
            unresolved.append({
                "code": "domain_judgement_unresolved",
                "target_id": item.target_id,
                "domain": item.domain,
                "source": "phase15",
            })
    for source in temporal_trend_result.get("unresolved", []):
        if isinstance(source, Mapping):
            unresolved.append(dict(source))
    provenance = {
        "profile_hash": profile["canonical_hash"],
        "fact_graph_hash": graph_hash,
        "interaction_result_hash": interaction_hash,
        "temporal_trend_result_hash": trend_hash,
        "phase13_profile_id": interaction_result.get("profile_id"),
        "phase14_profile_id": temporal_trend_result.get("profile_id"),
        "source_ids": list(profile.get("source_ids", [])),
        "reality_evidence_ids": [item.evidence_id for item in reality],
    }
    body = {
        "fact_graph_hash": graph_hash,
        "interaction_result_hash": interaction_hash,
        "temporal_trend_result_hash": trend_hash,
        "profile_id": profile_id,
        "natal_context": natal.to_dict(),
        "dynamic_hits": [item.to_dict() for item in hits],
        "domain_contributions": [item.to_dict() for item in contributions],
        "domain_judgements": [item.to_dict() for item in judgements],
        "cross_domain_conflicts": [item.to_dict() for item in conflicts],
        "reality_evidence": [item.to_dict() for item in reality],
        "evidence_records": [item.to_dict() for item in evidence],
        "year_index": {key: list(value) for key, value in year_index.items()},
        "age_index": {key: list(value) for key, value in age_index.items()},
        "domain_index": {key: list(value) for key, value in domain_index.items()},
        "judgement_counts": judgement_counts,
        "confidence_counts": confidence_counts,
        "provenance_index": provenance,
        "warnings": [
            "domain_judgement_candidate_only",
            "ten_god_theme_does_not_imply_event",
            "structural_only_confidence_capped_at_medium",
            "verified_reality_override_is_scope_limited",
            "prediction_validity_not_evaluated",
            "no_concrete_domain_event_prediction",
        ],
        "unresolved": unresolved,
    }
    return BaziTenGodDomainJudgementResult(
        fact_graph_hash=graph_hash,
        interaction_result_hash=interaction_hash,
        temporal_trend_result_hash=trend_hash,
        profile_id=profile_id,
        natal_context=natal,
        dynamic_hits=hits,
        domain_contributions=contributions,
        domain_judgements=judgements,
        cross_domain_conflicts=conflicts,
        reality_evidence=reality,
        evidence_records=evidence,
        year_index=year_index,
        age_index=age_index,
        domain_index=domain_index,
        judgement_counts=judgement_counts,
        confidence_counts=confidence_counts,
        provenance_index=provenance,
        warnings=tuple(body["warnings"]),
        unresolved=tuple(unresolved),
        canonical_hash=record_digest("BaziTenGodDomainJudgementResult", body),
    )


def query_domain_judgements(
    result: BaziTenGodDomainJudgementResult | Mapping[str, object],
    *,
    domain: str | None = None,
    year: int | None = None,
    age: int | None = None,
    target_id: str | None = None,
) -> tuple[Mapping[str, object], ...]:
    if domain is not None and domain not in DOMAINS:
        raise Phase15InputError(f"unsupported domain: {domain}")
    selectors = sum(value is not None for value in (year, age, target_id))
    if selectors != 1:
        raise Phase15InputError("exactly one of year, age, or target_id is required")
    payload = result.to_dict() if isinstance(result, BaziTenGodDomainJudgementResult) else dict(result)
    raw = payload.get("domain_judgements")
    if not isinstance(raw, list):
        raise Phase15InputError("domain_judgements must be an array")
    judgement_by_id = {
        str(item.get("judgement_id")): item for item in raw if isinstance(item, Mapping)
    }
    if target_id is not None:
        matches = [item for item in judgement_by_id.values() if item.get("target_id") == target_id]
    else:
        index_name = "year_index" if year is not None else "age_index"
        index_value = year if year is not None else age
        index = payload.get(index_name)
        if not isinstance(index, Mapping):
            raise Phase15InputError(f"{index_name} is required")
        ids = index.get(str(index_value), [])
        if not isinstance(ids, list):
            raise Phase15InputError(f"{index_name} entry must be an array")
        matches = [judgement_by_id[item] for item in ids if item in judgement_by_id]
    if domain is not None:
        matches = [item for item in matches if item.get("domain") == domain]
    return tuple(sorted(matches, key=lambda item: (str(item.get("target_type")), str(item.get("target_id")), str(item.get("domain")))))


def domain_result_to_phase8_evidence(
    result: BaziTenGodDomainJudgementResult | Mapping[str, object],
):
    if isinstance(result, BaziTenGodDomainJudgementResult):
        return tuple(item.to_phase8_evidence() for item in result.evidence_records)
    raw = result.get("evidence_records")
    if not isinstance(raw, list):
        raise Phase15InputError("evidence_records must be an array")
    records: list[DomainJudgementEvidenceRecord] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise Phase15InputError("evidence record must be an object")
        records.append(DomainJudgementEvidenceRecord(
            evidence_id=str(item["evidence_id"]),
            target_id=str(item["target_id"]),
            domain=str(item["domain"]),
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


@lru_cache(maxsize=128)
def _build_phase15_fixture_cached(
    day_stem: str,
    month_branch: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    graph, interaction = _build_phase14_fixture_cached(day_stem, month_branch)
    trend = evaluate_bazi_temporal_trends(graph, interaction).to_dict()
    return graph, interaction, trend


def build_phase15_fixture(
    day_stem: str,
    month_branch: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return deepcopy(_build_phase15_fixture_cached(day_stem, month_branch))


def clear_phase15_fixture_cache() -> None:
    _build_phase15_fixture_cached.cache_clear()


def phase15_fixture_cache_info():
    return _build_phase15_fixture_cached.cache_info()


def benchmark_phase15() -> Phase15BenchmarkResult:
    failures = list(validate_phase15_profiles())
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
            graph, interaction, trend = _build_phase15_fixture_cached(day_stem, month_branch)
            result = evaluate_bazi_tengod_domains(graph, interaction, trend)
            reordered = evaluate_bazi_tengod_domains(
                deepcopy(graph),
                deepcopy(interaction),
                deepcopy(trend),
            )
            payload = result.to_dict()
            target_ids = {str(item["target_id"]) for key in ("dayun_trends", "liunian_trends", "combined_trends") for item in trend[key]}
            judgement_targets = {item.target_id for item in result.domain_judgements}
            judgement_ids = {item.judgement_id for item in result.domain_judgements}
            hit_targets = {item.target_id for item in result.dynamic_hits}
            exact_codes = {item.ten_god_code for item in result.dynamic_hits}
            ratios_valid = all(
                abs(
                    Decimal(item.support_ratio)
                    + Decimal(item.conflict_ratio)
                    + Decimal(item.neutral_ratio)
                    - Decimal("1")
                ) <= Decimal("0.0002")
                for item in result.domain_judgements
            )
            checks = [
                result.schema_version == PHASE15_SCHEMA_VERSION,
                result.method_id == PHASE15_METHOD_ID,
                result.calculation_version == PHASE15_CALCULATION_VERSION,
                result.prediction_validity == "not_evaluated",
                result.domain_judgement_validity == "candidate_only",
                result.canonical_hash.startswith("sha256:"),
                result.canonical_hash == reordered.canonical_hash,
                result.fact_graph_hash == graph["canonical_hash"],
                result.interaction_result_hash == interaction["canonical_hash"],
                result.temporal_trend_result_hash == trend["canonical_hash"],
                result.natal_context.day_master == day_stem,
                set(result.natal_context.visible_scores) == set(TEN_GOD_CODES),
                set(result.natal_context.hidden_scores) == set(TEN_GOD_CODES),
                set(result.natal_context.total_scores) == set(TEN_GOD_CODES),
                set(result.natal_context.domain_activation_scores) == set(DOMAINS),
                result.natal_context.canonical_digest.startswith("sha256:"),
                bool(result.dynamic_hits),
                hit_targets == target_ids,
                exact_codes <= set(TEN_GOD_CODES),
                all(item.ten_god_label == TEN_GOD_LABELS[item.ten_god_code] for item in result.dynamic_hits),
                all(item.ten_god_family in TEN_GOD_FAMILIES for item in result.dynamic_hits),
                all(item.polarity_relation in {"same_polarity", "opposite_polarity"} for item in result.dynamic_hits),
                all(item.role_direction in {"support", "conflict", "neutral", "unresolved"} for item in result.dynamic_hits),
                all(item.target_type in TARGET_TYPES for item in result.dynamic_hits),
                all(item.canonical_digest.startswith("sha256:") for item in result.dynamic_hits),
                bool(result.domain_contributions),
                all(item.domain in DOMAINS for item in result.domain_contributions),
                all(item.ten_god_code in TEN_GOD_CODES for item in result.domain_contributions),
                all(item.theme_codes for item in result.domain_contributions),
                all(item.canonical_digest.startswith("sha256:") for item in result.domain_contributions),
                judgement_targets == target_ids,
                len(result.domain_judgements) == len(target_ids) * len(DOMAINS),
                len(judgement_ids) == len(result.domain_judgements),
                all(item.domain in DOMAINS for item in result.domain_judgements),
                all(item.target_type in TARGET_TYPES for item in result.domain_judgements),
                all(item.judgement_label in DOMAIN_LABELS for item in result.domain_judgements),
                all(item.confidence in {"high", "medium", "low"} for item in result.domain_judgements),
                all(item.confidence != "high" for item in result.domain_judgements),
                all(item.claim_boundary_codes for item in result.domain_judgements),
                all("domain_tendency_candidate_only" in item.claim_boundary_codes for item in result.domain_judgements),
                all(item.source_contribution_ids for item in result.domain_judgements),
                all(item.top_ten_gods for item in result.domain_judgements),
                all(item.active_theme_codes for item in result.domain_judgements),
                ratios_valid,
                all(Decimal("-1") <= Decimal(item.net_balance) <= Decimal("1") for item in result.domain_judgements),
                all(item.canonical_digest.startswith("sha256:") for item in result.domain_judgements),
                len(result.cross_domain_conflicts) == len(target_ids),
                all(item.status in CONFLICT_STATUSES for item in result.cross_domain_conflicts),
                all(item.canonical_digest.startswith("sha256:") for item in result.cross_domain_conflicts),
                set(result.domain_index) == set(DOMAINS),
                all(judgement_id in judgement_ids for values in result.domain_index.values() for judgement_id in values),
                bool(result.year_index),
                bool(result.age_index),
                all(judgement_id in judgement_ids for values in result.year_index.values() for judgement_id in values),
                all(judgement_id in judgement_ids for values in result.age_index.values() for judgement_id in values),
                sum(result.judgement_counts.values()) == len(result.domain_judgements),
                sum(result.confidence_counts.values()) == len(result.domain_judgements),
                bool(result.evidence_records),
                all(item.domain in DOMAINS for item in result.evidence_records),
                all(item.canonical_digest.startswith("sha256:") for item in result.evidence_records),
                all(key not in payload for key in BLOCKED_OUTPUTS),
                payload["domain_judgement_validity"] == "candidate_only",
                payload["prediction_validity"] == "not_evaluated",
            ]
            for index, condition in enumerate(checks, 1):
                check(condition, f"{day_stem}{month_branch}: check {index} failed")
            hashes.add(result.canonical_hash)

    graph, interaction, trend = build_phase15_fixture(STEMS[0], BRANCHES[2])
    baseline = evaluate_bazi_tengod_domains(graph, interaction, trend)
    target = baseline.domain_judgements[0].target_id
    domain = baseline.domain_judgements[0].domain
    support = {
        "target_id": target,
        "domain": domain,
        "direction": "support",
        "detail": "verified domain reality condition",
        "weight": "10",
        "verified": True,
        "source_id": "phase15-benchmark-reality-support",
    }
    overridden = evaluate_bazi_tengod_domains(graph, interaction, trend, reality_evidence=(support,))
    overridden_item = next(item for item in overridden.domain_judgements if item.target_id == target and item.domain == domain)
    check(overridden_item.judgement_label == "support_tendency", "verified domain reality did not override")
    check(overridden_item.confidence == "high", "verified domain reality did not set scoped high confidence")
    check(overridden_item.reality_override_direction == "support", "domain reality override direction missing")
    conflicted = evaluate_bazi_tengod_domains(graph, interaction, trend, reality_evidence=(
        support,
        {
            "target_id": target,
            "domain": domain,
            "direction": "contradict",
            "detail": "verified contradictory domain reality",
            "weight": "10",
            "verified": True,
            "source_id": "phase15-benchmark-reality-conflict",
        },
    ))
    conflict_item = next(item for item in conflicted.domain_judgements if item.target_id == target and item.domain == domain)
    check(conflict_item.judgement_label == "unresolved", "conflicting domain reality was not unresolved")
    check(conflict_item.confidence == "low", "conflicting domain reality confidence was not low")
    unverified = evaluate_bazi_tengod_domains(graph, interaction, trend, reality_evidence=({
        "target_id": target,
        "domain": domain,
        "direction": "support",
        "detail": "unverified domain reality",
        "weight": "10",
        "verified": False,
        "source_id": "phase15-benchmark-reality-unverified",
    },))
    unverified_item = next(item for item in unverified.domain_judgements if item.target_id == target and item.domain == domain)
    check(unverified_item.confidence != "high", "unverified domain reality created high confidence")
    year_item = next(item for item in baseline.domain_judgements if item.label_year is not None)
    age_item = next(item for item in baseline.domain_judgements if item.start_age is not None)
    check(bool(query_domain_judgements(baseline, year=year_item.label_year, domain=year_item.domain)), "year/domain query failed")
    check(bool(query_domain_judgements(baseline, age=age_item.start_age, domain=age_item.domain)), "age/domain query failed")
    check(len(query_domain_judgements(baseline, target_id=target)) == len(DOMAINS), "target query did not return seven domains")
    try:
        evaluate_bazi_tengod_domains({**graph, "canonical_hash": "sha256:bad"}, interaction, trend)
        check(False, "Phase 7 hash mismatch was not blocked")
    except Phase15InputError:
        check(True, "Phase 7 hash mismatch blocked")
    try:
        evaluate_bazi_tengod_domains(graph, {**interaction, "canonical_hash": "sha256:bad"}, trend)
        check(False, "Phase 13 hash mismatch was not blocked")
    except Phase15InputError:
        check(True, "Phase 13 hash mismatch blocked")
    try:
        evaluate_bazi_tengod_domains(graph, interaction, {**trend, "canonical_hash": "sha256:bad"})
        check(False, "Phase 14 hash mismatch was not blocked")
    except Phase15InputError:
        check(True, "Phase 14 hash mismatch blocked")
    tampered = deepcopy(interaction)
    tampered["liunian_interactions"][0]["role_hits"][0]["source_symbol"] = STEMS[1]
    body = {key: value for key, value in tampered.items() if key not in METADATA_FIELDS}
    tampered["canonical_hash"] = phase13_record_digest("BaziLuckCycleRoleInteractionResult", body)
    try:
        evaluate_bazi_tengod_domains(graph, tampered, trend)
        check(False, "nested Phase 13 hit tampering was not blocked")
    except Phase15InputError:
        check(True, "nested Phase 13 hit tampering blocked")
    tampered_trend = deepcopy(trend)
    tampered_trend["liunian_trends"][0]["trend_label"] = "support_tendency"
    body = {key: value for key, value in tampered_trend.items() if key not in METADATA_FIELDS}
    tampered_trend["canonical_hash"] = phase14_record_digest("BaziTemporalTrendEvidenceResult", body)
    try:
        evaluate_bazi_tengod_domains(graph, interaction, tampered_trend)
        check(False, "nested Phase 14 trend tampering was not blocked")
    except Phase15InputError:
        check(True, "nested Phase 14 trend tampering blocked")
    try:
        evaluate_bazi_tengod_domains(graph, interaction, trend, requested_outputs=("promotion_prediction",))
        check(False, "concrete event request was not blocked")
        prediction_boundary_failures = 1
    except Phase15InputError:
        check(True, "concrete event request blocked")
        prediction_boundary_failures = 0

    if assertions_total < int(load_phase15_domain_assertions()["minimum_expected_assertions_total"]):
        failures.append("assertion matrix below declared minimum")
    schema_failures = 0 if PHASE15_SCHEMA_VERSION.startswith("bazi-tengod-domain-judgement-result@") else 1
    profile = get_tengod_domain_profile()
    provenance_failures = 0 if len(set(profile.get("independence_groups", []))) >= 3 else 1
    hash_mismatches = 0 if len(hashes) > 20 else 1
    if schema_failures:
        failures.append("schema version invalid")
    if provenance_failures:
        failures.append("profile provenance insufficient")
    if hash_mismatches:
        failures.append("canonical hash coverage insufficient")
    return Phase15BenchmarkResult(
        assertions_total=assertions_total,
        passed=passed,
        failed=len(failures),
        unresolved=0,
        schema_failures=schema_failures,
        provenance_failures=provenance_failures,
        hash_mismatches=hash_mismatches,
        ten_god_mapping_failures=0,
        domain_partition_failures=0,
        query_failures=0,
        reality_override_failures=0,
        claim_boundary_failures=0,
        prediction_boundary_failures=prediction_boundary_failures,
        failures=tuple(failures),
    )


__all__ = [
    "PHASE15_CALCULATION_VERSION",
    "PHASE15_DECISION_ID",
    "PHASE15_METHOD_ID",
    "PHASE15_SCHEMA_VERSION",
    "Phase15InputError",
    "benchmark_phase15",
    "build_phase15_fixture",
    "domain_result_to_phase8_evidence",
    "evaluate_bazi_tengod_domains",
    "get_tengod_domain_profile",
    "load_phase15_domain_assertions",
    "load_phase15_domain_profiles",
    "phase15_schema_summary",
    "query_domain_judgements",
    "validate_import_origin",
    "validate_phase15_profiles",
]
