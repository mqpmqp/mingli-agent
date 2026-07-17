from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator, ValidationError

from .contracts import get_schema
from .contracts.serialization import digest
from .ziwei_engine import AUXILIARY_STAR_IDS, PRIMARY_STAR_IDS
from .ziwei_rules import ZIWEI_CHART_ALGORITHM, ZiweiRuleError, extract_ziwei_rule_facts

ZIWEI_TEMPORAL_V2_SCHEMA_VERSION = "ziwei-temporal-combination-result@2.0"
ZIWEI_TEMPORAL_V2_METHOD_ID = "ziwei-temporal-combination@2.0.0"
ZIWEI_TEMPORAL_V2_RULESET_VERSION = "ziwei-temporal-combination-rules@2.0.0"
ZIWEI_TEMPORAL_V2_RULE_PACK_SCHEMA = "ziwei-temporal-combination-rule-pack@2.0"
SYNTHETIC_FIXTURE_CLASSIFICATION = "synthetic_contract_only"
PREDICTION_VALIDITY = "not_evaluated"
RELEASE_HOLD = "ACTIVE"

_HASH_PATTERN_PREFIX = "sha256:"
_TRANSFORMATIONS = frozenset({"lu", "quan", "ke", "ji"})
_TEMPORAL_LEVELS = frozenset({"natal", "decade", "year", "month"})
_DIRECTIONS = frozenset({"support", "contradict"})
_CONFIDENCE = frozenset({"low", "medium"})
_CATEGORIES = frozenset(
    {
        "four_transformation_combination",
        "primary_supporting_combination",
        "three_directions_four_orthogonals",
        "sandwich",
        "arch",
        "convergence",
        "aspect",
        "life_body_relationship",
        "brightness_state_combination",
        "temporal_overlay",
    }
)
_TOPICS = frozenset(
    {"career", "wealth", "relationship", "study", "family", "migration"}
)
_REQUIRED_EXCLUSIONS = (
    "chart:not_complete",
    "chart:unsupported",
    "overlay:unsupported",
)
_CONFLICT_POLICY = "higher_priority_then_unresolved"
_RULE_RECORD_TYPE = "ZiweiTemporalCombinationRuleV2"
_PACK_RECORD_TYPE = "ZiweiTemporalCombinationRulePackV2"
_RESULT_RECORD_TYPE = "ZiweiTemporalCombinationResultV2"


class ZiweiTemporalV2Error(ValueError):
    """Raised when v2 cannot evaluate a complete compatible Ziwei chart."""


def _rule(
    rule_id: str,
    *,
    category: str,
    topics: Sequence[str],
    temporal_level: str,
    claim_id: str,
    direction: str,
    priority: int,
    confidence: str,
    tokens: Sequence[str],
) -> dict[str, object]:
    trigger = {"all": list(tokens)}
    return {
        "rule_id": rule_id,
        "content_version": ZIWEI_TEMPORAL_V2_RULESET_VERSION,
        "category": category,
        "topics": list(topics),
        "temporal_level": temporal_level,
        "claim_id": claim_id,
        "conflict_group": claim_id,
        "direction": direction,
        "priority": priority,
        "canonical_priority": priority,
        "confidence": confidence,
        "trigger": trigger,
        "canonical_trigger": deepcopy(trigger),
        "exclusions": list(_REQUIRED_EXCLUSIONS),
        "conflict_policy": _CONFLICT_POLICY,
        "compatibility": {
            "chart_algorithm": ZIWEI_CHART_ALGORITHM,
            "rule_content": ZIWEI_TEMPORAL_V2_RULESET_VERSION,
        },
        "source_id": "traditional:ziwei-combination-structure-v2",
        "lifecycle": "draft",
        "synthetic_contract_fixture": {
            "classification": SYNTHETIC_FIXTURE_CLASSIFICATION,
            "tokens": list(tokens),
        },
    }


_RULE_TEMPLATES = (
    _rule(
        "ziwei-temporal-v2:four-transformations:lu-quan-colocated",
        category="four_transformation_combination",
        topics=("family",),
        temporal_level="natal",
        claim_id="family:four-transformations",
        direction="support",
        priority=72,
        confidence="medium",
        tokens=(
            "temporal:natal",
            "palace:父母宫:transformation:lu",
            "palace:父母宫:transformation:quan",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:primary-supporting:wealth-study-assist",
        category="primary_supporting_combination",
        topics=("wealth", "study"),
        temporal_level="natal",
        claim_id="wealth-study:primary-supporting",
        direction="support",
        priority=70,
        confidence="medium",
        tokens=(
            "temporal:natal",
            "palace:财帛宫:primary:tianji",
            "palace:财帛宫:primary:tianliang",
            "palace:财帛宫:supporting:youbi",
            "palace:财帛宫:supporting:wenchang",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:geometry:life-four-orthogonals",
        category="three_directions_four_orthogonals",
        topics=("career", "wealth", "migration"),
        temporal_level="natal",
        claim_id="career-wealth-migration:four-orthogonals",
        direction="support",
        priority=68,
        confidence="medium",
        tokens=(
            "temporal:natal",
            "geometry:命宫:four_orthogonals:star:taiyin",
            "geometry:命宫:four_orthogonals:star:tianji",
            "geometry:命宫:four_orthogonals:star:taiyang",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:geometry:life-sandwich",
        category="sandwich",
        topics=("family",),
        temporal_level="natal",
        claim_id="family:life-sandwich",
        direction="contradict",
        priority=58,
        confidence="low",
        tokens=(
            "temporal:natal",
            "geometry:命宫:sandwich:star:tiankui",
            "geometry:命宫:sandwich:star:lianzhen",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:geometry:life-arch",
        category="arch",
        topics=("career", "study"),
        temporal_level="natal",
        claim_id="career-study:life-arch",
        direction="support",
        priority=64,
        confidence="medium",
        tokens=(
            "temporal:natal",
            "geometry:命宫:arch:star:taiyin",
            "geometry:命宫:arch:star:tianji",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:geometry:life-convergence",
        category="convergence",
        topics=("career", "wealth", "migration"),
        temporal_level="natal",
        claim_id="career-wealth-migration:life-convergence",
        direction="contradict",
        priority=62,
        confidence="low",
        tokens=(
            "temporal:natal",
            "geometry:命宫:convergence:star:taiyang",
            "geometry:命宫:convergence:star:tianji",
            "geometry:命宫:convergence:transformation:ji",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:geometry:life-migration-aspect",
        category="aspect",
        topics=("migration", "relationship"),
        temporal_level="natal",
        claim_id="migration-relationship:life-aspect",
        direction="contradict",
        priority=60,
        confidence="low",
        tokens=(
            "temporal:natal",
            "geometry:命宫:aspect:star:taiyang",
            "geometry:命宫:aspect:star:jumen",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:life-body:same-palace",
        category="life_body_relationship",
        topics=("family", "relationship"),
        temporal_level="natal",
        claim_id="family-relationship:life-body",
        direction="support",
        priority=66,
        confidence="medium",
        tokens=("temporal:natal", "life_body:same_palace"),
    ),
    _rule(
        "ziwei-temporal-v2:brightness:wealth-mixed-state",
        category="brightness_state_combination",
        topics=("wealth", "study"),
        temporal_level="natal",
        claim_id="wealth-study:brightness-state",
        direction="support",
        priority=56,
        confidence="low",
        tokens=(
            "temporal:natal",
            "palace:财帛宫:brightness:tianliang:temple",
            "palace:财帛宫:brightness:tianji:neutral",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:overlay:decade-career",
        category="temporal_overlay",
        topics=("career",),
        temporal_level="decade",
        claim_id="career:decade-overlay",
        direction="support",
        priority=75,
        confidence="medium",
        tokens=(
            "temporal:decade",
            "overlay:target:官禄宫",
            "overlay:star:wuqu",
            "overlay:transformation:quan",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:overlay:year-wealth-study",
        category="temporal_overlay",
        topics=("wealth", "study"),
        temporal_level="year",
        claim_id="wealth-study:year-overlay",
        direction="support",
        priority=74,
        confidence="medium",
        tokens=(
            "temporal:year",
            "overlay:target:财帛宫",
            "overlay:star:wuqu",
            "overlay:transformation:lu",
        ),
    ),
    _rule(
        "ziwei-temporal-v2:overlay:month-relationship-family",
        category="temporal_overlay",
        topics=("relationship", "family"),
        temporal_level="month",
        claim_id="relationship-family:month-overlay",
        direction="support",
        priority=73,
        confidence="medium",
        tokens=(
            "temporal:month",
            "overlay:target:夫妻宫",
            "overlay:star:taiyin",
            "overlay:transformation:ke",
        ),
    ),
)


def _record_hash(record_type: str, value: Mapping[str, object]) -> str:
    body = {key: item for key, item in value.items() if key != "canonical_hash"}
    return digest({"record_type": record_type, "payload": body})


def _with_hash(record_type: str, value: Mapping[str, object]) -> dict[str, object]:
    result = deepcopy(dict(value))
    result["canonical_hash"] = _record_hash(record_type, result)
    return result


def load_ziwei_temporal_v2_rule_pack() -> dict[str, object]:
    """Load a fresh deterministic copy of the built-in additive v2 rule pack."""
    rules = [_with_hash(_RULE_RECORD_TYPE, rule) for rule in _RULE_TEMPLATES]
    pack = {
        "schema_version": ZIWEI_TEMPORAL_V2_RULE_PACK_SCHEMA,
        "content_version": ZIWEI_TEMPORAL_V2_RULESET_VERSION,
        "method_id": ZIWEI_TEMPORAL_V2_METHOD_ID,
        "chart_algorithm": ZIWEI_CHART_ALGORITHM,
        "sources": [
            {
                "source_id": "traditional:ziwei-combination-structure-v2",
                "evidence_level": "traditional_paraphrase",
                "prediction_validation": "not_evaluated",
            }
        ],
        "fixture_classification": SYNTHETIC_FIXTURE_CLASSIFICATION,
        "accuracy_assessment": "not_assessed",
        "prediction_validity": PREDICTION_VALIDITY,
        "release_hold": RELEASE_HOLD,
        "rules": rules,
    }
    return _with_hash(_PACK_RECORD_TYPE, pack)


def _strings(value: object, name: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ZiweiTemporalV2Error(f"{name} must be an array")
    result = list(value)
    if (not allow_empty and not result) or any(
        not isinstance(item, str) or not item for item in result
    ):
        raise ZiweiTemporalV2Error(f"{name} must contain non-empty strings")
    if len(set(result)) != len(result):
        raise ZiweiTemporalV2Error(f"{name} must be unique")
    return result


def _validate_rule(rule: Mapping[str, object]) -> None:
    rule_id = rule.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id:
        raise ZiweiTemporalV2Error("rule_id must be non-empty")
    if rule.get("content_version") != ZIWEI_TEMPORAL_V2_RULESET_VERSION:
        raise ZiweiTemporalV2Error(f"{rule_id} has incompatible content_version")
    if rule.get("category") not in _CATEGORIES:
        raise ZiweiTemporalV2Error(f"{rule_id} category is unsupported")
    topics = _strings(rule.get("topics"), f"{rule_id}.topics")
    if not set(topics).issubset(_TOPICS):
        raise ZiweiTemporalV2Error(f"{rule_id} topics are unsupported")
    if rule.get("temporal_level") not in _TEMPORAL_LEVELS:
        raise ZiweiTemporalV2Error(f"{rule_id} temporal_level is unsupported")
    for field in ("claim_id", "conflict_group", "source_id"):
        if not isinstance(rule.get(field), str) or not rule[field]:
            raise ZiweiTemporalV2Error(f"{rule_id}.{field} must be non-empty")
    if rule.get("direction") not in _DIRECTIONS:
        raise ZiweiTemporalV2Error(f"{rule_id} direction is unsupported")
    priority = rule.get("priority")
    canonical_priority = rule.get("canonical_priority")
    if (
        isinstance(priority, bool)
        or not isinstance(priority, int)
        or not 1 <= priority <= 100
    ):
        raise ZiweiTemporalV2Error(f"{rule_id}.priority must be from 1 to 100")
    if canonical_priority != priority:
        raise ZiweiTemporalV2Error(f"{rule_id} priority differs from canonical_priority")
    if rule.get("confidence") not in _CONFIDENCE:
        raise ZiweiTemporalV2Error(f"{rule_id} confidence is unsupported")
    trigger = rule.get("trigger")
    canonical_trigger = rule.get("canonical_trigger")
    if not isinstance(trigger, Mapping) or set(trigger) != {"all"}:
        raise ZiweiTemporalV2Error(f"{rule_id}.trigger must contain all")
    trigger_tokens = _strings(trigger["all"], f"{rule_id}.trigger.all")
    if trigger != canonical_trigger:
        raise ZiweiTemporalV2Error(f"{rule_id} trigger differs from canonical_trigger")
    exclusions = _strings(rule.get("exclusions"), f"{rule_id}.exclusions")
    if not set(_REQUIRED_EXCLUSIONS).issubset(exclusions):
        raise ZiweiTemporalV2Error(f"{rule_id} exclusions are incomplete")
    if rule.get("conflict_policy") != _CONFLICT_POLICY:
        raise ZiweiTemporalV2Error(f"{rule_id} conflict_policy is unsupported")
    compatibility = rule.get("compatibility")
    if not isinstance(compatibility, Mapping) or compatibility != {
        "chart_algorithm": ZIWEI_CHART_ALGORITHM,
        "rule_content": ZIWEI_TEMPORAL_V2_RULESET_VERSION,
    }:
        raise ZiweiTemporalV2Error(f"{rule_id} compatibility is unsupported")
    if rule.get("lifecycle") != "draft":
        raise ZiweiTemporalV2Error(f"{rule_id} lifecycle must remain draft")
    fixture = rule.get("synthetic_contract_fixture")
    if (
        not isinstance(fixture, Mapping)
        or fixture.get("classification") != SYNTHETIC_FIXTURE_CLASSIFICATION
    ):
        raise ZiweiTemporalV2Error(
            f"{rule_id} synthetic fixture classification is required"
        )
    _strings(fixture.get("tokens"), f"{rule_id}.synthetic_contract_fixture.tokens")
    if set(fixture["tokens"]) != set(trigger_tokens):
        raise ZiweiTemporalV2Error(f"{rule_id} fixture does not exercise its trigger")
    expected_hash = _record_hash(_RULE_RECORD_TYPE, rule)
    if rule.get("canonical_hash") != expected_hash:
        raise ZiweiTemporalV2Error(f"{rule_id} canonical_hash mismatch")


def _validate_pack(pack: Mapping[str, object]) -> list[Mapping[str, object]]:
    if pack.get("schema_version") != ZIWEI_TEMPORAL_V2_RULE_PACK_SCHEMA:
        raise ZiweiTemporalV2Error("rule pack schema_version is unsupported")
    if pack.get("content_version") != ZIWEI_TEMPORAL_V2_RULESET_VERSION:
        raise ZiweiTemporalV2Error("rule pack content_version is incompatible")
    if pack.get("method_id") != ZIWEI_TEMPORAL_V2_METHOD_ID:
        raise ZiweiTemporalV2Error("rule pack method_id is incompatible")
    if pack.get("chart_algorithm") != ZIWEI_CHART_ALGORITHM:
        raise ZiweiTemporalV2Error("rule pack chart_algorithm is incompatible")
    raw_rules = pack.get("rules")
    if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, (str, bytes)):
        raise ZiweiTemporalV2Error("rule pack rules must be an array")
    rules: list[Mapping[str, object]] = []
    for item in raw_rules:
        if not isinstance(item, Mapping):
            raise ZiweiTemporalV2Error("rule pack contains a non-object rule")
        _validate_rule(item)
        rules.append(item)
    ids = [str(item["rule_id"]) for item in rules]
    if not rules or len(ids) != len(set(ids)):
        raise ZiweiTemporalV2Error("rule pack rule_id values must be non-empty and unique")
    expected_hash = _record_hash(_PACK_RECORD_TYPE, pack)
    if pack.get("canonical_hash") != expected_hash:
        raise ZiweiTemporalV2Error("rule pack canonical_hash mismatch")
    try:
        Draft202012Validator(
            get_schema("ziwei_temporal_v2_rule_pack.schema.json")
        ).validate(pack)
    except ValidationError as exc:
        raise ZiweiTemporalV2Error(
            f"rule pack schema validation failed: {exc.message}"
        ) from exc
    return rules


def _validate_chart(chart: Mapping[str, object]) -> None:
    if chart.get("calculation_status") != "complete":
        raise ZiweiTemporalV2Error("v2 requires a complete Ziwei chart")
    unsupported = chart.get("unsupported_fields")
    if not isinstance(unsupported, Sequence) or isinstance(unsupported, (str, bytes)):
        raise ZiweiTemporalV2Error("chart unsupported_fields must be an array")
    if unsupported:
        raise ZiweiTemporalV2Error("v2 rejects charts with unsupported fields")
    if chart.get("algorithm_version") != ZIWEI_CHART_ALGORITHM:
        raise ZiweiTemporalV2Error("chart algorithm_version is incompatible")
    if chart.get("prediction_validity") != PREDICTION_VALIDITY:
        raise ZiweiTemporalV2Error("chart prediction_validity must be not_evaluated")
    if chart.get("canonical_hash") != _record_hash("ZiweiChart", chart):
        raise ZiweiTemporalV2Error("chart canonical_hash mismatch")
    try:
        Draft202012Validator(get_schema("ziwei_chart.schema.json")).validate(chart)
        extract_ziwei_rule_facts(chart)
    except (ValidationError, ZiweiRuleError) as exc:
        raise ZiweiTemporalV2Error(f"complete chart validation failed: {exc}") from exc


def _palace_stars(palace: Mapping[str, object]) -> set[str]:
    stars: set[str] = set()
    for field in ("primary_stars", "supporting_stars", "malefic_stars"):
        values = palace[field]
        assert isinstance(values, Sequence)
        for item in values:
            assert isinstance(item, Mapping)
            stars.add(str(item["star_id"]))
    return stars


def _palace_transformations(palace: Mapping[str, object]) -> set[str]:
    values = palace["transformations"]
    assert isinstance(values, Sequence)
    return {
        str(item["transformation"])
        for item in values
        if isinstance(item, Mapping)
    }


def _chart_tokens(chart: Mapping[str, object]) -> set[str]:
    raw_palaces = chart["palaces"]
    assert isinstance(raw_palaces, Sequence)
    palaces = {
        int(item["palace_index"]): item
        for item in raw_palaces
        if isinstance(item, Mapping)
    }
    tokens = {"chart:complete"}
    field_categories = {
        "primary_stars": "primary",
        "supporting_stars": "supporting",
        "malefic_stars": "malefic",
    }
    for palace in palaces.values():
        name = str(palace["palace_name"])
        for field, category in field_categories.items():
            values = palace[field]
            assert isinstance(values, Sequence)
            for item in values:
                assert isinstance(item, Mapping)
                star_id = str(item["star_id"])
                tokens.add(f"palace:{name}:star:{star_id}")
                tokens.add(f"palace:{name}:{category}:{star_id}")
        transformations = palace["transformations"]
        assert isinstance(transformations, Sequence)
        for item in transformations:
            assert isinstance(item, Mapping)
            tokens.add(
                f"palace:{name}:transformation:{item['transformation']}"
            )
        brightness = palace["brightness_state"]
        assert isinstance(brightness, Sequence)
        for item in brightness:
            assert isinstance(item, Mapping)
            tokens.add(
                f"palace:{name}:brightness:{item['star_id']}:{item['state']}"
            )

    for index, anchor in palaces.items():
        anchor_name = str(anchor["palace_name"])
        geometry = {
            "three_directions": (index, (index + 4) % 12, (index + 8) % 12),
            "four_orthogonals": (
                index,
                (index + 4) % 12,
                (index + 8) % 12,
                (index + 6) % 12,
            ),
            "sandwich": ((index - 1) % 12, (index + 1) % 12),
            "arch": ((index + 4) % 12, (index + 8) % 12),
            "aspect": ((index + 6) % 12,),
            "convergence": (
                index,
                (index + 4) % 12,
                (index + 8) % 12,
                (index + 6) % 12,
            ),
        }
        for relation, indexes in geometry.items():
            related = [palaces[item] for item in indexes]
            for star_id in sorted(set().union(*(_palace_stars(item) for item in related))):
                tokens.add(f"geometry:{anchor_name}:{relation}:star:{star_id}")
            for transformation in sorted(
                set().union(*(_palace_transformations(item) for item in related))
            ):
                tokens.add(
                    f"geometry:{anchor_name}:{relation}:transformation:{transformation}"
                )

    life = int(chart["life_palace"])
    body = int(chart["body_palace"])
    distance = (body - life) % 12
    if distance == 0:
        relationship = "same_palace"
    elif distance == 6:
        relationship = "opposite"
    elif distance in {4, 8}:
        relationship = "three_direction"
    else:
        relationship = "other"
    tokens.add(f"life_body:{relationship}")
    return tokens


def _normalize_overlay(
    value: Mapping[str, object], palace_names: set[str]
) -> tuple[dict[str, object], set[str], dict[str, object]]:
    common = {
        "overlay_id",
        "level",
        "target_palaces",
        "star_ids",
        "transformations",
        "calculation_status",
        "unsupported_fields",
    }
    level = value.get("level")
    level_fields = {
        "decade": {"start_year", "end_year"},
        "year": {"year"},
        "month": {"year", "month"},
    }
    if level not in level_fields:
        raise ZiweiTemporalV2Error("overlay level must be decade, year, or month")
    expected = common | level_fields[str(level)]
    if set(value) != expected:
        raise ZiweiTemporalV2Error("overlay contains missing or unsupported fields")
    overlay_id = value.get("overlay_id")
    if not isinstance(overlay_id, str) or not overlay_id:
        raise ZiweiTemporalV2Error("overlay_id must be non-empty")
    if value.get("calculation_status") != "complete":
        raise ZiweiTemporalV2Error("overlay calculation_status must be complete")
    unsupported = _strings(
        value.get("unsupported_fields"), "overlay unsupported_fields", allow_empty=True
    )
    if unsupported:
        raise ZiweiTemporalV2Error("v2 rejects overlays with unsupported fields")
    targets = _strings(value.get("target_palaces"), "overlay target_palaces")
    if not set(targets).issubset(palace_names):
        raise ZiweiTemporalV2Error("overlay target_palaces are incompatible")
    stars = _strings(value.get("star_ids"), "overlay star_ids")
    if not set(stars).issubset({*PRIMARY_STAR_IDS, *AUXILIARY_STAR_IDS}):
        raise ZiweiTemporalV2Error("overlay star_ids are unsupported")
    transformations = _strings(
        value.get("transformations"), "overlay transformations"
    )
    if not set(transformations).issubset(_TRANSFORMATIONS):
        raise ZiweiTemporalV2Error("overlay transformations are unsupported")

    normalized = dict(value)
    normalized["target_palaces"] = sorted(targets)
    normalized["star_ids"] = sorted(stars)
    normalized["transformations"] = sorted(transformations)
    if level == "decade":
        start = value.get("start_year")
        end = value.get("end_year")
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or end < start
            or end - start > 9
        ):
            raise ZiweiTemporalV2Error("decade overlay must span at most ten years")
        window = {
            "scope": overlay_id,
            "level": level,
            "start": f"{start:04d}-01",
            "end": f"{end:04d}-12",
            "bounded": True,
            "precision": "month",
        }
    elif level == "year":
        year = value.get("year")
        if isinstance(year, bool) or not isinstance(year, int):
            raise ZiweiTemporalV2Error("year overlay requires an integer year")
        window = {
            "scope": overlay_id,
            "level": level,
            "start": f"{year:04d}-01",
            "end": f"{year:04d}-12",
            "bounded": True,
            "precision": "month",
        }
    else:
        year = value.get("year")
        month = value.get("month")
        if (
            isinstance(year, bool)
            or not isinstance(year, int)
            or isinstance(month, bool)
            or not isinstance(month, int)
            or not 1 <= month <= 12
        ):
            raise ZiweiTemporalV2Error("month overlay requires a valid year and month")
        window = {
            "scope": overlay_id,
            "level": level,
            "start": f"{year:04d}-{month:02d}",
            "end": f"{year:04d}-{month:02d}",
            "bounded": True,
            "precision": "month",
        }
    tokens = {f"temporal:{level}"}
    tokens.update(f"overlay:target:{item}" for item in targets)
    tokens.update(f"overlay:star:{item}" for item in stars)
    tokens.update(f"overlay:transformation:{item}" for item in transformations)
    return normalized, tokens, window


def _validate_overlay_containment(overlays: Sequence[Mapping[str, object]]) -> None:
    decades: list[tuple[int, int]] = []
    years: list[int] = []
    months: list[int] = []
    for overlay in overlays:
        level = overlay.get("level")
        if level == "decade":
            start = overlay.get("start_year")
            end = overlay.get("end_year")
            if not isinstance(start, int) or isinstance(start, bool):
                raise ZiweiTemporalV2Error("normalized decade start_year is invalid")
            if not isinstance(end, int) or isinstance(end, bool):
                raise ZiweiTemporalV2Error("normalized decade end_year is invalid")
            decades.append((start, end))
        elif level == "year":
            year = overlay.get("year")
            if not isinstance(year, int) or isinstance(year, bool):
                raise ZiweiTemporalV2Error("normalized year overlay is invalid")
            years.append(year)
        elif level == "month":
            year = overlay.get("year")
            if not isinstance(year, int) or isinstance(year, bool):
                raise ZiweiTemporalV2Error("normalized month overlay year is invalid")
            months.append(year)

    if (years or months) and not decades:
        raise ZiweiTemporalV2Error(
            "year and month overlays require a supplied decade overlay"
        )
    if months and not years:
        raise ZiweiTemporalV2Error(
            "month overlays require a supplied year overlay"
        )
    if decades:
        for child_year in sorted(set(years) | set(months)):
            parent_count = sum(
                start <= child_year <= end for start, end in decades
            )
            if parent_count != 1:
                raise ZiweiTemporalV2Error(
                    "year and month overlays must be contained by exactly one supplied decade overlay"
                )
    if years:
        for month_year in months:
            if years.count(month_year) != 1:
                raise ZiweiTemporalV2Error(
                    "month overlays must be contained by exactly one supplied year overlay"
                )


def _rule_matches(rule: Mapping[str, object], tokens: set[str]) -> bool:
    trigger = rule["trigger"]
    assert isinstance(trigger, Mapping)
    required = trigger["all"]
    assert isinstance(required, Sequence)
    exclusions = rule["exclusions"]
    assert isinstance(exclusions, Sequence)
    return set(required).issubset(tokens) and not set(exclusions).intersection(tokens)


def _resolve_candidates(
    candidates: Sequence[Mapping[str, object]],
    *,
    scope: str,
    window: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for rule in candidates:
        grouped[(str(rule["claim_id"]), str(rule["conflict_group"]))].append(rule)
    findings: list[dict[str, object]] = []
    for group_rules in grouped.values():
        highest = max(int(rule["priority"]) for rule in group_rules)
        top_directions = {
            str(rule["direction"])
            for rule in group_rules
            if int(rule["priority"]) == highest
        }
        for rule in group_rules:
            demotions: list[str] = []
            confidence = str(rule["confidence"])
            if int(rule["priority"]) < highest:
                resolution = "suppressed_by_higher_priority"
                confidence = "low"
                demotions.append("higher_priority_conflict")
            elif len(top_directions) > 1:
                resolution = "unresolved_conflict"
                confidence = "low"
                demotions.append("equal_priority_direction_conflict")
            else:
                resolution = "matched"
            findings.append(
                {
                    "rule_id": rule["rule_id"],
                    "category": rule["category"],
                    "topics": list(rule["topics"]),
                    "claim_id": rule["claim_id"],
                    "scope": scope,
                    "temporal_level": rule["temporal_level"],
                    "direction": rule["direction"],
                    "priority": rule["priority"],
                    "confidence": confidence,
                    "resolution": resolution,
                    "confidence_demotion_reasons": demotions,
                    "reality_evidence_ids": [],
                    "event_time_window": dict(window) if window is not None else None,
                    "prediction_validity": PREDICTION_VALIDITY,
                }
            )
    return findings


def _apply_reality_evidence(
    findings: list[dict[str, object]],
    evidence: Sequence[Mapping[str, object]],
) -> list[str]:
    valid_targets = {
        (str(item["claim_id"]), str(item["scope"])) for item in findings
    }
    seen_ids: set[str] = set()
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    allowed = {
        "evidence_id",
        "claim_id",
        "scope",
        "direction",
        "verified",
        "source_id",
    }
    for item in evidence:
        if not isinstance(item, Mapping) or set(item) != allowed:
            raise ZiweiTemporalV2Error("Reality Evidence record is unsupported")
        evidence_id = item.get("evidence_id")
        source_id = item.get("source_id")
        if not isinstance(evidence_id, str) or not evidence_id:
            raise ZiweiTemporalV2Error("Reality Evidence evidence_id is required")
        if evidence_id in seen_ids:
            raise ZiweiTemporalV2Error("Reality Evidence evidence_id must be unique")
        if not isinstance(source_id, str) or not source_id:
            raise ZiweiTemporalV2Error("Reality Evidence source_id is required")
        if item.get("verified") is not True:
            raise ZiweiTemporalV2Error("Reality Evidence hard override requires verified=true")
        if item.get("direction") not in _DIRECTIONS:
            raise ZiweiTemporalV2Error("Reality Evidence direction is unsupported")
        target = (str(item.get("claim_id")), str(item.get("scope")))
        if target not in valid_targets:
            raise ZiweiTemporalV2Error(
                "Reality Evidence claim and scope do not match a finding"
            )
        seen_ids.add(evidence_id)
        grouped[target].append(item)
    for finding in findings:
        target = (str(finding["claim_id"]), str(finding["scope"]))
        records = sorted(
            grouped.get(target, []), key=lambda item: str(item["evidence_id"])
        )
        if not records:
            continue
        directions = {str(item["direction"]) for item in records}
        finding["reality_evidence_ids"] = [
            str(item["evidence_id"]) for item in records
        ]
        if len(directions) == 1:
            finding["direction"] = next(iter(directions))
            finding["resolution"] = "reality_override"
            finding["confidence"] = "high"
            finding["confidence_demotion_reasons"] = []
        else:
            finding["resolution"] = "unresolved_reality_conflict"
            finding["confidence"] = "low"
            finding["confidence_demotion_reasons"] = [
                "conflicting_verified_reality_evidence"
            ]
    return sorted(seen_ids)


def evaluate_ziwei_temporal_v2(
    chart: Mapping[str, object],
    *,
    overlays: Sequence[Mapping[str, object]] = (),
    reality_evidence: Sequence[Mapping[str, object]] = (),
    rule_pack: Mapping[str, object] | None = None,
    requested_outputs: Sequence[str] = ("findings", "event_time_windows"),
) -> dict[str, object]:
    """Evaluate additive v2 structural and temporal rules without accuracy claims."""
    if not isinstance(chart, Mapping):
        raise ZiweiTemporalV2Error("chart must be an object")
    _validate_chart(chart)
    pack = (
        load_ziwei_temporal_v2_rule_pack()
        if rule_pack is None
        else deepcopy(dict(rule_pack))
    )
    rules = _validate_pack(pack)
    outputs = _strings(requested_outputs, "requested_outputs", allow_empty=True)
    unsupported_outputs = sorted(
        set(outputs).difference({"findings", "event_time_windows"})
    )
    if unsupported_outputs:
        raise ZiweiTemporalV2Error(
            "v2 cannot return requested output: " + ", ".join(unsupported_outputs)
        )
    if not isinstance(overlays, Sequence) or isinstance(overlays, (str, bytes)):
        raise ZiweiTemporalV2Error("overlays must be an array")
    if not isinstance(reality_evidence, Sequence) or isinstance(
        reality_evidence, (str, bytes)
    ):
        raise ZiweiTemporalV2Error("reality_evidence must be an array")

    base_tokens = _chart_tokens(chart)
    raw_palaces = chart["palaces"]
    assert isinstance(raw_palaces, Sequence)
    palace_names = {
        str(item["palace_name"])
        for item in raw_palaces
        if isinstance(item, Mapping)
    }
    contexts: list[tuple[str, str, set[str], Mapping[str, object] | None]] = [
        ("natal", "natal", base_tokens | {"temporal:natal"}, None)
    ]
    normalized_overlays: list[dict[str, object]] = []
    windows: list[dict[str, object]] = []
    for overlay in overlays:
        if not isinstance(overlay, Mapping):
            raise ZiweiTemporalV2Error("overlay must be an object")
        normalized, overlay_tokens, window = _normalize_overlay(
            overlay, palace_names
        )
        normalized_overlays.append(normalized)
        windows.append(window)
        contexts.append(
            (
                str(normalized["level"]),
                str(normalized["overlay_id"]),
                base_tokens | overlay_tokens,
                window,
            )
        )
    overlay_ids = [str(item["overlay_id"]) for item in normalized_overlays]
    if len(overlay_ids) != len(set(overlay_ids)):
        raise ZiweiTemporalV2Error("overlay_id values must be unique")
    _validate_overlay_containment(normalized_overlays)

    findings: list[dict[str, object]] = []
    for level, scope, tokens, window in contexts:
        candidates = [
            rule
            for rule in rules
            if rule["temporal_level"] == level and _rule_matches(rule, tokens)
        ]
        findings.extend(
            _resolve_candidates(candidates, scope=scope, window=window)
        )
    findings.sort(
        key=lambda item: (
            str(item["scope"]),
            str(item["claim_id"]),
            -int(item["priority"]),
            str(item["rule_id"]),
        )
    )
    applied_evidence = _apply_reality_evidence(findings, reality_evidence)
    windows.sort(key=lambda item: str(item["scope"]))
    body: dict[str, object] = {
        "schema_version": ZIWEI_TEMPORAL_V2_SCHEMA_VERSION,
        "method_id": ZIWEI_TEMPORAL_V2_METHOD_ID,
        "ruleset_version": ZIWEI_TEMPORAL_V2_RULESET_VERSION,
        "ruleset_hash": pack["canonical_hash"],
        "chart_fingerprint": chart["chart_fingerprint"],
        "findings": findings,
        "event_time_windows": windows,
        "reality_evidence_applied": applied_evidence,
        "fixture_classification": SYNTHETIC_FIXTURE_CLASSIFICATION,
        "accuracy_assessment": "not_assessed",
        "warnings": [
            "bounded_windows_are_not_event_predictions",
            "synthetic_contract_fixtures_do_not_establish_accuracy",
        ],
        "release_hold": RELEASE_HOLD,
        "prediction_validity": PREDICTION_VALIDITY,
    }
    body["canonical_hash"] = _record_hash(_RESULT_RECORD_TYPE, body)
    try:
        Draft202012Validator(
            get_schema("ziwei_temporal_v2_result.schema.json")
        ).validate(body)
    except ValidationError as exc:  # pragma: no cover - internal invariant guard
        raise ZiweiTemporalV2Error(
            f"result schema validation failed: {exc.message}"
        ) from exc
    return body


def _coverage_item(rule: Mapping[str, object]) -> dict[str, object]:
    rule_id = str(rule.get("rule_id", "<invalid-rule>"))
    paths = {
        "canonical_trigger": False,
        "exclusion": False,
        "priority_conflict": False,
        "unsupported": False,
    }
    errors: list[str] = []
    try:
        _validate_rule(rule)
        fixture = rule["synthetic_contract_fixture"]
        assert isinstance(fixture, Mapping)
        fixture_tokens = set(_strings(fixture["tokens"], "fixture.tokens"))
        canonical_match = _rule_matches(rule, fixture_tokens)
        trigger = rule["trigger"]
        assert isinstance(trigger, Mapping)
        trigger_tokens = _strings(trigger["all"], "trigger.all")
        false_passes = any(
            _rule_matches(rule, fixture_tokens - {token})
            for token in trigger_tokens
        )
        paths["canonical_trigger"] = canonical_match and not false_passes

        exclusions = _strings(rule["exclusions"], "exclusions")
        paths["exclusion"] = set(_REQUIRED_EXCLUSIONS).issubset(exclusions) and all(
            not _rule_matches(rule, fixture_tokens | {exclusion})
            for exclusion in exclusions
        )
        paths["unsupported"] = all(
            not _rule_matches(rule, fixture_tokens | {token})
            for token in ("chart:unsupported", "overlay:unsupported")
        )

        lower_peer = deepcopy(dict(rule))
        lower_peer["rule_id"] = f"{rule_id}:coverage-lower-peer"
        lower_peer["direction"] = (
            "contradict" if rule["direction"] == "support" else "support"
        )
        lower_peer["priority"] = max(0, int(rule["priority"]) - 1)
        lower_findings = _resolve_candidates(
            [rule, lower_peer], scope="synthetic-coverage", window=None
        )
        lower_by_id = {str(item["rule_id"]): item for item in lower_findings}
        equal_peer = deepcopy(lower_peer)
        equal_peer["rule_id"] = f"{rule_id}:coverage-equal-peer"
        equal_peer["priority"] = rule["priority"]
        equal_findings = _resolve_candidates(
            [rule, equal_peer], scope="synthetic-coverage", window=None
        )
        paths["priority_conflict"] = (
            int(rule["priority"]) == int(rule["canonical_priority"])
            and rule["conflict_policy"] == _CONFLICT_POLICY
            and lower_by_id[rule_id]["resolution"] == "matched"
            and lower_by_id[str(lower_peer["rule_id"])]["resolution"]
            == "suppressed_by_higher_priority"
            and lower_by_id[str(lower_peer["rule_id"])]["confidence"] == "low"
            and all(
                item["resolution"] == "unresolved_conflict"
                and item["confidence"] == "low"
                for item in equal_findings
            )
        )
    except (AssertionError, KeyError, TypeError, ZiweiTemporalV2Error) as exc:
        errors.append(str(exc) or type(exc).__name__)
    return {
        "rule_id": rule_id,
        "paths": paths,
        "covered": all(paths.values()),
        "errors": errors,
    }


def build_ziwei_temporal_v2_coverage(
    rule_pack: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Behaviorally exercise rule paths; this is not an accuracy metric."""
    pack = (
        load_ziwei_temporal_v2_rule_pack()
        if rule_pack is None
        else deepcopy(dict(rule_pack))
    )
    raw_rules = pack.get("rules")
    rules = (
        list(raw_rules)
        if isinstance(raw_rules, Sequence) and not isinstance(raw_rules, (str, bytes))
        else []
    )
    items = [
        _coverage_item(rule if isinstance(rule, Mapping) else {}) for rule in rules
    ]
    ids = [item["rule_id"] for item in items]
    pack_hash_valid = pack.get("canonical_hash") == _record_hash(
        _PACK_RECORD_TYPE, pack
    )
    metadata_valid = (
        pack.get("schema_version") == ZIWEI_TEMPORAL_V2_RULE_PACK_SCHEMA
        and pack.get("content_version") == ZIWEI_TEMPORAL_V2_RULESET_VERSION
        and pack.get("prediction_validity") == PREDICTION_VALIDITY
        and pack.get("release_hold") == RELEASE_HOLD
        and pack.get("accuracy_assessment") == "not_assessed"
    )
    complete = (
        bool(items)
        and all(bool(item["covered"]) for item in items)
        and len(ids) == len(set(ids))
        and pack_hash_valid
        and metadata_valid
    )
    result: dict[str, object] = {
        "schema_version": "ziwei-temporal-combination-coverage@2.0",
        "ruleset_version": ZIWEI_TEMPORAL_V2_RULESET_VERSION,
        "ruleset_hash": pack.get("canonical_hash"),
        "rule_count": len(items),
        "covered_count": sum(bool(item["covered"]) for item in items),
        "required_paths": [
            "canonical_trigger",
            "exclusion",
            "priority_conflict",
            "unsupported",
        ],
        "rules": items,
        "complete": complete,
        "fixture_classification": SYNTHETIC_FIXTURE_CLASSIFICATION,
        "accuracy_assessment": "not_assessed",
        "prediction_validity": PREDICTION_VALIDITY,
        "release_hold": RELEASE_HOLD,
    }
    result["canonical_hash"] = _record_hash(
        "ZiweiTemporalCombinationCoverageV2", result
    )
    return result


__all__ = [
    "ZIWEI_TEMPORAL_V2_METHOD_ID",
    "ZIWEI_TEMPORAL_V2_RULESET_VERSION",
    "ZIWEI_TEMPORAL_V2_SCHEMA_VERSION",
    "ZiweiTemporalV2Error",
    "build_ziwei_temporal_v2_coverage",
    "evaluate_ziwei_temporal_v2",
    "load_ziwei_temporal_v2_rule_pack",
]
