from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from importlib import resources
import json
from itertools import combinations
from pathlib import Path
from typing import Mapping, Sequence, TypedDict, cast

from jsonschema import Draft202012Validator, ValidationError

from .contracts import get_schema
from .ziwei_engine import (
    AUXILIARY_STAR_IDS,
    MALEFIC_STAR_NAMES,
    PALACE_BRANCHES,
    SUPPORTING_STAR_NAMES,
)

ZIWEI_RULE_CONTENT_VERSION = "ziwei-traditional-rule-content@1.0.0"
ZIWEI_CHART_ALGORITHM = "ziwei-traditional-natal@1.0.0"
ZIWEI_RULE_RESOURCE = "ziwei_traditional_rules_v1.json"

PRIMARY_STAR_NAMES = {
    "ziwei": "紫微",
    "tianji": "天机",
    "taiyang": "太阳",
    "wuqu": "武曲",
    "tiantong": "天同",
    "lianzhen": "廉贞",
    "tianfu": "天府",
    "taiyin": "太阴",
    "tanlang": "贪狼",
    "jumen": "巨门",
    "tianxiang": "天相",
    "tianliang": "天梁",
    "qisha": "七杀",
    "pojun": "破军",
}
PRIMARY_STAR_IDS = tuple(PRIMARY_STAR_NAMES)
PALACES = (
    "命宫",
    "兄弟宫",
    "夫妻宫",
    "子女宫",
    "财帛宫",
    "疾厄宫",
    "迁移宫",
    "交友宫",
    "官禄宫",
    "田宅宫",
    "福德宫",
    "父母宫",
)
TRANSFORMATIONS = ("lu", "quan", "ke", "ji")
BRIGHTNESS_STATES = (
    "temple",
    "prosperous",
    "beneficial",
    "neutral",
    "weak",
    "unfavorable",
    "fallen",
)
COMBINATION_FACTS = {
    "ziwei:v1:combination:ziwei-tianfu": "ziwei+tianfu",
    "ziwei:v1:combination:ziwei-qisha": "ziwei+qisha",
    "ziwei:v1:combination:wuqu-tanlang": "wuqu+tanlang",
    "ziwei:v1:combination:taiyang-taiyin": "taiyang+taiyin",
    "ziwei:v1:combination:lianzhen-qisha": "lianzhen+qisha",
}
SUBJECTS = ("primary_star_palace", "transformation", "brightness", "combination")
DOMAINS = ("career", "wealth", "relationship")
THEMES = ("career", "wealth", "relationship", "study")
RULE_FIELDS = frozenset(
    {
        "rule_id",
        "content_version",
        "subject",
        "star",
        "palace",
        "transformation",
        "state",
        "domain",
        "themes",
        "trigger",
        "exclusions",
        "priority",
        "confidence",
        "evidence_level",
        "source_id",
        "plain_language",
        "lifecycle",
        "compatibility",
        "conflict_policy",
        "output_constraints",
        "direction",
    }
)
FORBIDDEN_ABSOLUTES = (
    "一定",
    "必然",
    "注定",
    "没救",
    "百分之百",
    "百分百",
    "保证",
    "必死",
    "必离婚",
    "必发财",
)
FORBIDDEN_PLATFORM_TEXT = ("metis",)
REQUIRED_CHART_EXCLUSIONS = (
    {"fact": "calculation_status", "operator": "not_equals", "value": "complete"},
    {"fact": "unsupported_fields", "operator": "not_equals", "value": []},
)
_MISSING = object()


class ZiweiRuleError(ValueError):
    pass


class RuleCard(TypedDict):
    rule_id: str
    content_version: str
    subject: str
    star: str | None
    palace: str | None
    transformation: str | None
    state: str | None
    domain: str
    themes: Sequence[str]
    trigger: Mapping[str, object]
    exclusions: Sequence[Mapping[str, object]]
    priority: int
    confidence: str
    evidence_level: str
    source_id: str
    plain_language: str
    lifecycle: str
    compatibility: Mapping[str, object]
    conflict_policy: str
    output_constraints: Sequence[str]
    direction: str


@dataclass(frozen=True)
class ZiweiRuleMatch:
    rule_id: str
    subject: str
    star: str | None
    palace: str | None
    transformation: str | None
    state: str | None
    domain: str
    themes: tuple[str, ...]
    direction: str
    priority: int
    confidence: str
    plain_language: str
    source_id: str
    resolution: str

    def to_evidence(self) -> dict[str, object]:
        return {
            "evidence_id": f"ziwei-rule:{self.rule_id}",
            "claim_id": self.rule_id,
            "scope": self.domain,
            "source_type": "rule",
            "source_id": self.source_id,
            "direction": self.direction,
            "weight": {"low": 2, "medium": 5, "high": 8}[self.confidence],
            "priority": self.priority,
            "verified": False,
            "detail_code": "ziwei_traditional_rule_match",
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "subject": self.subject,
            "star": self.star,
            "palace": self.palace,
            "transformation": self.transformation,
            "state": self.state,
            "domain": self.domain,
            "themes": list(self.themes),
            "direction": self.direction,
            "priority": self.priority,
            "confidence": self.confidence,
            "plain_language": self.plain_language,
            "source_id": self.source_id,
            "resolution": self.resolution,
        }


def _condition(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ZiweiRuleError(f"{name} must be an object")
    keys = set(value)
    if keys in ({"all"}, {"any"}):
        operator = next(iter(keys))
        children = value[operator]
        if (
            not isinstance(children, Sequence)
            or isinstance(children, (str, bytes))
            or not children
        ):
            raise ZiweiRuleError(f"{name}.{operator} must be a non-empty array")
        for index, child in enumerate(children):
            _condition(child, f"{name}.{operator}[{index}]")
        return value
    if keys != {"fact", "operator", "value"}:
        raise ZiweiRuleError(
            f"{name} must contain fact/operator/value or one all/any group"
        )
    fact = value["fact"]
    if not isinstance(fact, str) or not fact:
        raise ZiweiRuleError(f"{name}.fact must be non-empty")
    if value["operator"] not in {"equals", "not_equals", "contains", "not_contains"}:
        raise ZiweiRuleError(f"{name}.operator is invalid")
    return value


def _non_empty_strings(value: object, name: str) -> tuple[str, ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ZiweiRuleError(f"{name} must contain non-empty strings")
    result = tuple(str(item) for item in value)
    if len(set(result)) != len(result):
        raise ZiweiRuleError(f"{name} must be unique")
    return result


def validate_rule_card(raw: Mapping[str, object]) -> RuleCard:
    if not isinstance(raw, Mapping):
        raise ZiweiRuleError("rule card must be an object")
    missing = sorted(RULE_FIELDS.difference(raw))
    if missing:
        raise ZiweiRuleError(f"missing rule fields: {', '.join(missing)}")
    unexpected = sorted(set(raw).difference(RULE_FIELDS))
    if unexpected:
        raise ZiweiRuleError(f"unexpected rule fields: {', '.join(unexpected)}")
    source_id = raw["source_id"]
    if not isinstance(source_id, str) or not source_id:
        raise ZiweiRuleError("source_id must be non-empty")
    text = raw["plain_language"]
    if not isinstance(text, str) or not text.strip():
        raise ZiweiRuleError("plain_language must be non-empty")
    if any(token in text for token in FORBIDDEN_ABSOLUTES):
        raise ZiweiRuleError("plain_language contains forbidden absolute language")
    if any(token in text.casefold() for token in FORBIDDEN_PLATFORM_TEXT):
        raise ZiweiRuleError("plain_language contains forbidden platform content")
    try:
        Draft202012Validator(get_schema("ziwei_rule_card.schema.json")).validate(raw)
    except ValidationError as exc:
        raise ZiweiRuleError(f"rule schema validation failed: {exc.message}") from exc

    rule_id = raw["rule_id"]
    if not isinstance(rule_id, str) or not rule_id:
        raise ZiweiRuleError("rule_id must be non-empty")
    if raw["content_version"] != ZIWEI_RULE_CONTENT_VERSION:
        raise ZiweiRuleError("content_version is incompatible")
    subject = raw["subject"]
    if subject not in SUBJECTS:
        raise ZiweiRuleError("subject is invalid")
    star = raw["star"]
    palace = raw["palace"]
    transformation = raw["transformation"]
    state = raw["state"]
    if subject == "primary_star_palace":
        if star not in PRIMARY_STAR_IDS or palace not in PALACES:
            raise ZiweiRuleError("primary_star_palace requires a supported star and palace")
        if transformation is not None or state is not None:
            raise ZiweiRuleError("primary_star_palace cannot set transformation or state")
    elif subject == "transformation":
        if transformation not in TRANSFORMATIONS or any(
            item is not None for item in (star, palace, state)
        ):
            raise ZiweiRuleError("transformation subject fields are inconsistent")
    elif subject == "brightness":
        if state not in BRIGHTNESS_STATES or any(
            item is not None for item in (star, palace, transformation)
        ):
            raise ZiweiRuleError("brightness subject fields are inconsistent")
    elif any(item is not None for item in (star, palace, transformation, state)):
        raise ZiweiRuleError("combination subject fields must be null")

    if raw["domain"] not in DOMAINS:
        raise ZiweiRuleError("domain is invalid")
    themes = _non_empty_strings(raw["themes"], "themes")
    if not set(themes).issubset(THEMES):
        raise ZiweiRuleError("themes contains an unsupported theme")
    _condition(raw["trigger"], "trigger")
    exclusions = raw["exclusions"]
    if (
        not isinstance(exclusions, Sequence)
        or isinstance(exclusions, (str, bytes))
        or not exclusions
    ):
        raise ZiweiRuleError("exclusions must be a non-empty array")
    for index, exclusion in enumerate(exclusions):
        _condition(exclusion, f"exclusions[{index}]")
    priority = raw["priority"]
    if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 100:
        raise ZiweiRuleError("priority must be an integer from 0 to 100")
    if raw["confidence"] not in {"low", "medium", "high"}:
        raise ZiweiRuleError("confidence is invalid")
    if raw["evidence_level"] not in {
        "traditional_paraphrase",
        "cross_checked_traditional",
    }:
        raise ZiweiRuleError("evidence_level is invalid")
    if raw["lifecycle"] not in {"draft", "reviewed", "deprecated"}:
        raise ZiweiRuleError("lifecycle is invalid")
    compatibility = raw["compatibility"]
    if not isinstance(compatibility, Mapping):
        raise ZiweiRuleError("compatibility must be an object")
    if compatibility.get("chart_algorithm") != ZIWEI_CHART_ALGORITHM:
        raise ZiweiRuleError("compatibility chart_algorithm is incompatible")
    if compatibility.get("rule_content") != ZIWEI_RULE_CONTENT_VERSION:
        raise ZiweiRuleError("compatibility rule_content is incompatible")
    if raw["conflict_policy"] != "higher_priority_then_unresolved":
        raise ZiweiRuleError("conflict_policy is invalid")
    constraints = _non_empty_strings(raw["output_constraints"], "output_constraints")
    if not {"no_absolute_claims", "reality_override"}.issubset(constraints):
        raise ZiweiRuleError(
            "output_constraints must require no_absolute_claims and reality_override"
        )
    if raw["direction"] not in {"support", "contradict"}:
        raise ZiweiRuleError("direction is invalid")
    return cast(RuleCard, dict(raw))


def load_ziwei_rule_payload(path: Path | None = None) -> dict[str, object]:
    if path is None:
        text = (
            resources.files("mingli.derived.data")
            .joinpath(ZIWEI_RULE_RESOURCE)
            .read_text(encoding="utf-8")
        )
    else:
        text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ZiweiRuleError("Ziwei rule payload must be an object")
    return payload


def load_ziwei_rule_content(
    path: Path | None = None,
    *,
    payload: Mapping[str, object] | None = None,
) -> tuple[RuleCard, ...]:
    if path is not None and payload is not None:
        raise ZiweiRuleError("provide path or payload, not both")
    document = dict(payload) if payload is not None else load_ziwei_rule_payload(path)
    if document.get("schema_version") != "ziwei-traditional-rules@1.0":
        raise ZiweiRuleError("Ziwei rule payload schema_version is unsupported")
    if document.get("content_version") != ZIWEI_RULE_CONTENT_VERSION:
        raise ZiweiRuleError("Ziwei rule payload content_version is incompatible")
    sources = document.get("sources")
    if (
        not isinstance(sources, Sequence)
        or isinstance(sources, (str, bytes))
        or not sources
    ):
        raise ZiweiRuleError("Ziwei rule payload sources must be non-empty")
    source_ids: list[str] = []
    for source in sources:
        if not isinstance(source, Mapping):
            raise ZiweiRuleError("Ziwei source record must be an object")
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ZiweiRuleError("Ziwei source_id must be non-empty")
        source_ids.append(source_id)
    if len(set(source_ids)) != len(source_ids):
        raise ZiweiRuleError("Ziwei source_id values must be unique")
    rules = document.get("rules")
    if (
        not isinstance(rules, Sequence)
        or isinstance(rules, (str, bytes))
        or not rules
    ):
        raise ZiweiRuleError("Ziwei rule payload rules must be non-empty")
    cards = tuple(validate_rule_card(rule) for rule in rules if isinstance(rule, Mapping))
    if len(cards) != len(rules):
        raise ZiweiRuleError("Ziwei rule payload contains a non-object rule")
    rule_ids = [str(card["rule_id"]) for card in cards]
    if len(set(rule_ids)) != len(rule_ids):
        raise ZiweiRuleError("Ziwei rule_id values must be unique")
    unknown_sources = sorted(
        {str(card["source_id"]) for card in cards}.difference(source_ids)
    )
    if unknown_sources:
        raise ZiweiRuleError(
            f"Ziwei rule references unknown source: {', '.join(unknown_sources)}"
        )
    return cards


def _contains(actual: object, expected: object) -> bool:
    if isinstance(actual, Mapping):
        if not isinstance(expected, Mapping):
            return expected in actual
        return all(actual.get(key, _MISSING) == value for key, value in expected.items())
    if isinstance(actual, Sequence) and not isinstance(actual, (str, bytes)):
        if isinstance(expected, Mapping):
            return any(
                isinstance(item, Mapping)
                and all(item.get(key, _MISSING) == value for key, value in expected.items())
                for item in actual
            )
        return expected in actual
    return False


def _matches(condition: Mapping[str, object], facts: Mapping[str, object]) -> bool:
    all_conditions = condition.get("all")
    if isinstance(all_conditions, Sequence) and not isinstance(
        all_conditions, (str, bytes)
    ):
        return all(
            isinstance(item, Mapping) and _matches(item, facts)
            for item in all_conditions
        )
    any_conditions = condition.get("any")
    if isinstance(any_conditions, Sequence) and not isinstance(
        any_conditions, (str, bytes)
    ):
        return any(
            isinstance(item, Mapping) and _matches(item, facts)
            for item in any_conditions
        )
    actual = facts.get(str(condition["fact"]), _MISSING)
    expected = condition["value"]
    operator = condition["operator"]
    if operator == "equals":
        return actual is not _MISSING and actual == expected
    if operator == "not_equals":
        return actual is _MISSING or actual != expected
    if operator == "contains":
        return actual is not _MISSING and _contains(actual, expected)
    return actual is _MISSING or not _contains(actual, expected)


def _rule_conflict_key(card: Mapping[str, object]) -> tuple[str, str, str]:
    target = json.dumps(
        card["trigger"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return str(card["domain"]), str(card["subject"]), target


def evaluate_ziwei_rules(
    facts: Mapping[str, object], rules: Sequence[Mapping[str, object]]
) -> tuple[ZiweiRuleMatch, ...]:
    cards = [validate_rule_card(raw) for raw in rules]
    if cards and facts.get("algorithm_version") != ZIWEI_CHART_ALGORITHM:
        raise ZiweiRuleError("facts algorithm_version is incompatible with rule content")
    candidates = [
        card
        for card in cards
        if _matches(card["trigger"], facts)
        and not any(_matches(item, facts) for item in card["exclusions"])
    ]
    candidates.sort(key=lambda card: (-int(card["priority"]), str(card["rule_id"])))
    highest_priority = {
        key: max(
            int(card["priority"])
            for card in candidates
            if _rule_conflict_key(card) == key
        )
        for key in {_rule_conflict_key(card) for card in candidates}
    }
    top_directions = {
        key: {
            str(card["direction"])
            for card in candidates
            if _rule_conflict_key(card) == key
            and int(card["priority"]) == highest_priority[key]
        }
        for key in highest_priority
    }
    matches: list[ZiweiRuleMatch] = []
    for card in candidates:
        domain = str(card["domain"])
        conflict_key = _rule_conflict_key(card)
        if int(card["priority"]) < highest_priority[conflict_key]:
            resolution = "suppressed_by_higher_priority"
        elif len(top_directions[conflict_key]) > 1:
            resolution = "unresolved_conflict"
        else:
            resolution = "matched"
        matches.append(
            ZiweiRuleMatch(
                rule_id=str(card["rule_id"]),
                subject=str(card["subject"]),
                star=str(card["star"]) if card["star"] is not None else None,
                palace=str(card["palace"]) if card["palace"] is not None else None,
                transformation=(
                    str(card["transformation"])
                    if card["transformation"] is not None
                    else None
                ),
                state=str(card["state"]) if card["state"] is not None else None,
                domain=domain,
                themes=tuple(str(item) for item in card["themes"]),
                direction=str(card["direction"]),
                priority=int(card["priority"]),
                confidence=str(card["confidence"]),
                plain_language=str(card["plain_language"]),
                source_id=str(card["source_id"]),
                resolution=resolution,
            )
        )
    return tuple(matches)


def _require_sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ZiweiRuleError(f"chart.{name} must be an array")
    return value


def extract_ziwei_rule_facts(chart: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(chart, Mapping):
        raise ZiweiRuleError("Ziwei chart must be an object")
    try:
        Draft202012Validator(get_schema("ziwei_chart.schema.json")).validate(chart)
    except ValidationError as exc:
        raise ZiweiRuleError(f"Ziwei chart schema validation failed: {exc.message}") from exc
    if chart.get("calculation_status") != "complete":
        raise ZiweiRuleError("Ziwei traditional rules require a complete chart")
    if chart.get("algorithm_version") != ZIWEI_CHART_ALGORITHM:
        raise ZiweiRuleError("Ziwei chart algorithm_version is incompatible")
    unsupported = _require_sequence(chart.get("unsupported_fields"), "unsupported_fields")
    if unsupported:
        raise ZiweiRuleError("Ziwei traditional rules reject unsupported chart fields")
    palaces = _require_sequence(chart.get("palaces"), "palaces")
    if len(palaces) != 12:
        raise ZiweiRuleError("Ziwei chart must contain twelve palaces")

    star_palace_pairs: list[dict[str, str]] = []
    transformations: list[dict[str, str]] = []
    brightness_states: list[dict[str, str]] = []
    co_locations: list[str] = []
    seen_stars: list[str] = []
    seen_all_stars: list[str] = []
    seen_palaces: list[str] = []
    seen_palace_indexes: list[int] = []
    seen_branches: list[str] = []
    seen_transformations: list[str] = []
    seen_brightness_stars: list[str] = []
    body_palace_count = 0
    star_order = {star_id: index for index, star_id in enumerate(PRIMARY_STAR_IDS)}
    for palace in palaces:
        if not isinstance(palace, Mapping):
            raise ZiweiRuleError("Ziwei palace must be an object")
        palace_name = palace.get("palace_name")
        if palace_name not in PALACES:
            raise ZiweiRuleError("Ziwei palace_name is unsupported")
        palace_index = palace.get("palace_index")
        branch = palace.get("earthly_branch")
        if isinstance(palace_index, bool) or not isinstance(palace_index, int):
            raise ZiweiRuleError("Ziwei palace_index is invalid")
        if branch not in PALACE_BRANCHES:
            raise ZiweiRuleError("Ziwei earthly_branch is unsupported")
        seen_palaces.append(str(palace_name))
        seen_palace_indexes.append(palace_index)
        seen_branches.append(str(branch))
        body_palace_count += palace.get("is_body_palace") is True
        primary = _require_sequence(palace.get("primary_stars"), "primary_stars")
        palace_star_ids: list[str] = []
        for star in primary:
            if (
                not isinstance(star, Mapping)
                or star.get("star_id") not in PRIMARY_STAR_IDS
                or star.get("field_status") != "supported"
            ):
                raise ZiweiRuleError("Ziwei primary star is unsupported")
            star_id = str(star["star_id"])
            seen_stars.append(star_id)
            seen_all_stars.append(star_id)
            palace_star_ids.append(star_id)
            star_palace_pairs.append({"star": star_id, "palace": str(palace_name)})
        for field, supported_ids in (
            ("supporting_stars", SUPPORTING_STAR_NAMES),
            ("malefic_stars", MALEFIC_STAR_NAMES),
        ):
            for star in _require_sequence(palace.get(field), field):
                if (
                    not isinstance(star, Mapping)
                    or star.get("star_id") not in supported_ids
                    or star.get("field_status") != "supported"
                ):
                    raise ZiweiRuleError(f"Ziwei {field} contains an unsupported star")
                star_id = str(star["star_id"])
                seen_all_stars.append(star_id)
                palace_star_ids.append(star_id)
        if len(set(palace_star_ids)) != len(palace_star_ids):
            raise ZiweiRuleError("Ziwei palace contains duplicate stars")
        for first, second in combinations(
            sorted(
                (star_id for star_id in palace_star_ids if star_id in star_order),
                key=star_order.__getitem__,
            ),
            2,
        ):
            co_locations.append(f"{first}+{second}")
        for item in _require_sequence(palace.get("transformations"), "transformations"):
            if not isinstance(item, Mapping):
                raise ZiweiRuleError("Ziwei transformation must be an object")
            transformation = item.get("transformation")
            star_id = item.get("star_id")
            if (
                transformation not in TRANSFORMATIONS
                or not isinstance(star_id, str)
                or not star_id
                or star_id not in palace_star_ids
                or item.get("field_status") != "supported"
            ):
                raise ZiweiRuleError("Ziwei transformation is unsupported")
            seen_transformations.append(str(transformation))
            transformations.append(
                {
                    "star": str(star_id),
                    "transformation": str(transformation),
                    "palace": str(palace_name),
                }
            )
        for item in _require_sequence(palace.get("brightness_state"), "brightness_state"):
            if not isinstance(item, Mapping):
                raise ZiweiRuleError("Ziwei brightness state must be an object")
            state = item.get("state")
            star_id = item.get("star_id")
            if (
                state not in BRIGHTNESS_STATES
                or not isinstance(star_id, str)
                or not star_id
                or star_id not in palace_star_ids
                or item.get("field_status") != "supported"
            ):
                raise ZiweiRuleError("Ziwei brightness state is unsupported")
            seen_brightness_stars.append(star_id)
            brightness_states.append(
                {"star": star_id, "state": str(state), "palace": str(palace_name)}
            )
    if Counter(seen_palaces) != Counter({palace: 1 for palace in PALACES}):
        raise ZiweiRuleError("Ziwei complete chart must contain each palace exactly once")
    if Counter(seen_palace_indexes) != Counter({index: 1 for index in range(12)}):
        raise ZiweiRuleError("Ziwei complete chart must contain each palace_index exactly once")
    if Counter(seen_branches) != Counter({branch: 1 for branch in PALACE_BRANCHES}):
        raise ZiweiRuleError("Ziwei complete chart must contain each earthly branch exactly once")
    if body_palace_count != 1:
        raise ZiweiRuleError("Ziwei complete chart must identify one body palace")
    if Counter(seen_stars) != Counter({star_id: 1 for star_id in PRIMARY_STAR_IDS}):
        raise ZiweiRuleError("Ziwei complete chart must contain each primary star exactly once")
    supported_star_ids = (*PRIMARY_STAR_IDS, *AUXILIARY_STAR_IDS)
    if Counter(seen_all_stars) != Counter({star_id: 1 for star_id in supported_star_ids}):
        raise ZiweiRuleError("Ziwei complete chart must contain each supported star exactly once")
    if Counter(seen_transformations) != Counter(
        {transformation: 1 for transformation in TRANSFORMATIONS}
    ):
        raise ZiweiRuleError("Ziwei complete chart must contain each transformation exactly once")
    if len(set(seen_brightness_stars)) != len(seen_brightness_stars):
        raise ZiweiRuleError("Ziwei complete chart contains duplicate brightness states")
    return {
        "algorithm_version": ZIWEI_CHART_ALGORITHM,
        "calculation_status": "complete",
        "unsupported_fields": [],
        "star_palace_pairs": star_palace_pairs,
        "transformations": transformations,
        "brightness_states": brightness_states,
        "co_locations": sorted(co_locations),
    }


def evaluate_ziwei_chart_rules(
    chart: Mapping[str, object],
    rules: Sequence[Mapping[str, object]] | None = None,
) -> tuple[ZiweiRuleMatch, ...]:
    cards = load_ziwei_rule_content() if rules is None else tuple(rules)
    return evaluate_ziwei_rules(extract_ziwei_rule_facts(chart), cards)


def _empty_rule_facts() -> dict[str, object]:
    return {
        "algorithm_version": ZIWEI_CHART_ALGORITHM,
        "calculation_status": "complete",
        "unsupported_fields": [],
        "star_palace_pairs": [],
        "transformations": [],
        "brightness_states": [],
        "co_locations": [],
    }


def _synthetic_pair_facts(star: str, palace: str) -> dict[str, object]:
    facts = _empty_rule_facts()
    facts["star_palace_pairs"] = [{"star": star, "palace": palace}]
    return facts


def _canonical_rule_trigger(card: Mapping[str, object]) -> dict[str, object] | None:
    subject = card["subject"]
    if subject == "primary_star_palace":
        value: object = {"star": str(card["star"]), "palace": str(card["palace"])}
        fact = "star_palace_pairs"
    elif subject == "transformation":
        value = {"transformation": str(card["transformation"])}
        fact = "transformations"
    elif subject == "brightness":
        value = {"state": str(card["state"])}
        fact = "brightness_states"
    else:
        value = COMBINATION_FACTS.get(str(card["rule_id"]))
        if value is None:
            return None
        fact = "co_locations"
    return {"fact": fact, "operator": "contains", "value": value}


def _synthetic_rule_facts(card: Mapping[str, object]) -> dict[str, object] | None:
    canonical_trigger = _canonical_rule_trigger(card)
    if canonical_trigger is None or card["trigger"] != canonical_trigger:
        return None
    facts = _empty_rule_facts()
    subject = card["subject"]
    if subject == "primary_star_palace":
        facts["star_palace_pairs"] = [
            {"star": str(card["star"]), "palace": str(card["palace"])}
        ]
    elif subject == "transformation":
        facts["transformations"] = [
            {
                "star": "ziwei",
                "transformation": str(card["transformation"]),
                "palace": "命宫",
            }
        ]
    elif subject == "brightness":
        facts["brightness_states"] = [
            {"star": "ziwei", "state": str(card["state"]), "palace": "命宫"}
        ]
    else:
        combination = COMBINATION_FACTS.get(str(card["rule_id"]))
        assert combination is not None
        facts["co_locations"] = [combination]
    return facts


def build_rule_coverage(
    rules: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    cards = list(load_ziwei_rule_content() if rules is None else rules)
    validated = [validate_rule_card(rule) for rule in cards]
    rule_ids = [str(card["rule_id"]) for card in validated]
    duplicate_rule_ids = len(rule_ids) - len(set(rule_ids))
    base_cards = [
        card for card in validated if card["subject"] == "primary_star_palace"
    ]
    pairs = [(str(card["star"]), str(card["palace"])) for card in base_cards]
    pair_counts = Counter(pairs)
    duplicate_pairs = sum(count - 1 for count in pair_counts.values() if count > 1)
    behavior_rule_ids: set[str] = set()
    for card in validated:
        facts = _synthetic_rule_facts(card)
        if facts is None:
            continue
        if not all(
            exclusion in card["exclusions"]
            for exclusion in REQUIRED_CHART_EXCLUSIONS
        ):
            continue
        matches = evaluate_ziwei_rules(facts, [card])
        negative_matches = evaluate_ziwei_rules(_empty_rule_facts(), [card])
        degraded_matches = evaluate_ziwei_rules(
            {**facts, "calculation_status": "degraded"}, [card]
        )
        unsupported_matches = evaluate_ziwei_rules(
            {**facts, "unsupported_fields": ["rule_facts"]}, [card]
        )
        if (
            len(matches) == 1
            and matches[0].rule_id == card["rule_id"]
            and matches[0].resolution == "matched"
            and not negative_matches
            and not degraded_matches
            and not unsupported_matches
        ):
            behavior_rule_ids.add(str(card["rule_id"]))
    behavior_pairs: set[tuple[str, str]] = set()
    for card in base_cards:
        pair = (str(card["star"]), str(card["palace"]))
        if (
            pair_counts[pair] == 1
            and str(card["rule_id"]) in behavior_rule_ids
        ):
            behavior_pairs.add(pair)
    expected_pairs = {(star, palace) for star in PRIMARY_STAR_IDS for palace in PALACES}
    transformation_cards = [
        card for card in validated if card["subject"] == "transformation"
    ]
    transformation_rules = {
        str(card["transformation"])
        for card in transformation_cards
        if str(card["rule_id"]) in behavior_rule_ids
    }
    brightness_cards = [card for card in validated if card["subject"] == "brightness"]
    brightness_rules = {
        str(card["state"])
        for card in brightness_cards
        if str(card["rule_id"]) in behavior_rule_ids
    }
    combination_cards = [card for card in validated if card["subject"] == "combination"]
    combination_rules = {
        str(card["rule_id"])
        for card in combination_cards
        if str(card["rule_id"]) in behavior_rule_ids
    }
    transformations_complete = (
        len(transformation_cards) == len(TRANSFORMATIONS)
        and transformation_rules == set(TRANSFORMATIONS)
    )
    brightness_complete = (
        len(brightness_cards) == len(BRIGHTNESS_STATES)
        and brightness_rules == set(BRIGHTNESS_STATES)
    )
    combinations_complete = (
        len(combination_cards) == len(COMBINATION_FACTS)
        and combination_rules == set(COMBINATION_FACTS)
    )
    complete = (
        len(validated) == 184
        and behavior_pairs == expected_pairs
        and duplicate_pairs == 0
        and duplicate_rule_ids == 0
        and transformations_complete
        and brightness_complete
        and combinations_complete
    )
    return {
        "content_version": ZIWEI_RULE_CONTENT_VERSION,
        "rule_count": len(validated),
        "primary_stars": {
            star: (
                "implemented"
                if all((star, palace) in behavior_pairs for palace in PALACES)
                else "incomplete"
            )
            for star in PRIMARY_STAR_IDS
        },
        "palaces": {
            palace: (
                "implemented"
                if all((star, palace) in behavior_pairs for star in PRIMARY_STAR_IDS)
                else "incomplete"
            )
            for palace in PALACES
        },
        "star_palace_total": len(expected_pairs),
        "star_palace_records": len(base_cards),
        "star_palace_behaviorally_evaluated": len(behavior_pairs),
        "star_palace_implemented": len(behavior_pairs),
        "duplicate_rule_ids": duplicate_rule_ids,
        "duplicate_pairs": duplicate_pairs,
        "transformation_records": len(transformation_cards),
        "transformation_behaviorally_evaluated": len(transformation_rules),
        "brightness_records": len(brightness_cards),
        "brightness_behaviorally_evaluated": len(brightness_rules),
        "combination_records": len(combination_cards),
        "combination_behaviorally_evaluated": len(combination_rules),
        "contracts": {
            "dual_star": "implemented" if combinations_complete else "incomplete",
            "three_directions_four_orthogonals": "contract_only",
            "opposite_palace": "contract_only",
            "four_transformations": (
                "implemented" if transformations_complete else "incomplete"
            ),
            "supporting_and_malefic": "contract_only",
            "brightness": (
                "implemented" if brightness_complete else "incomplete"
            ),
            "pattern_recognition": "contract_only",
            "temporal_overlay": "contract_only",
            "reality_override": (
                "implemented"
                if validated
                and all(
                    "reality_override" in card["output_constraints"]
                    for card in validated
                )
                else "incomplete"
            ),
        },
        "release_gate": "REVIEW_REQUIRED" if complete else "NO-GO",
        "rule_content_hold": "ACTIVE",
        "prediction_validity": "not_evaluated",
    }


__all__ = [
    "PALACES",
    "PRIMARY_STAR_IDS",
    "PRIMARY_STAR_NAMES",
    "ZIWEI_RULE_CONTENT_VERSION",
    "ZiweiRuleError",
    "ZiweiRuleMatch",
    "build_rule_coverage",
    "evaluate_ziwei_chart_rules",
    "evaluate_ziwei_rules",
    "extract_ziwei_rule_facts",
    "load_ziwei_rule_content",
    "load_ziwei_rule_payload",
    "validate_rule_card",
]
