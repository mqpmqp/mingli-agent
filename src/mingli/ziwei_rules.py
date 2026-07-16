from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

PRIMARY_STARS = (
    "紫微", "天机", "太阳", "武曲", "天同", "廉贞", "天府",
    "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军",
)
PALACES = (
    "命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
    "迁移宫", "交友宫", "官禄宫", "田宅宫", "福德宫", "父母宫",
)
REQUIRED_FIELDS = (
    "rule_id", "domain", "trigger", "required_facts", "exclusions", "priority",
    "confidence", "deterministic_or_inferential", "traditional_claim", "plain_language",
    "evidence_refs", "source_level", "lifecycle", "conflict_policy", "output_constraints",
)
FORBIDDEN_ABSOLUTES = ("一定", "必然", "注定", "没救", "百分之百", "保证")


class ZiweiRuleError(ValueError):
    pass


@dataclass(frozen=True)
class ZiweiRuleMatch:
    rule_id: str
    domain: str
    direction: str
    priority: int
    confidence: str
    plain_language: str
    evidence_refs: tuple[str, ...]
    resolution: str

    def to_evidence(self) -> dict[str, object]:
        return {
            "evidence_id": f"ziwei-rule:{self.rule_id}",
            "claim_id": self.rule_id,
            "scope": self.domain,
            "source_type": "rule",
            "source_id": self.evidence_refs[0],
            "direction": self.direction,
            "weight": {"low": 2, "medium": 5, "high": 8}[self.confidence],
            "priority": self.priority,
            "verified": False,
            "detail_code": "ziwei_rule_match",
        }


def _condition(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != {"fact", "equals"}:
        raise ZiweiRuleError(f"{name} must contain fact and equals")
    if not isinstance(value["fact"], str) or not value["fact"]:
        raise ZiweiRuleError(f"{name}.fact must be non-empty")
    return value


def validate_rule_card(raw: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise ZiweiRuleError("rule card must be an object")
    missing = [field for field in REQUIRED_FIELDS if field not in raw]
    if missing:
        raise ZiweiRuleError(f"missing rule fields: {', '.join(missing)}")
    rule_id = raw["rule_id"]
    if not isinstance(rule_id, str) or not rule_id:
        raise ZiweiRuleError("rule_id must be non-empty")
    _condition(raw["trigger"], "trigger")
    required = raw["required_facts"]
    exclusions = raw["exclusions"]
    refs = raw["evidence_refs"]
    constraints = raw["output_constraints"]
    if not isinstance(required, Sequence) or isinstance(required, (str, bytes)) or not all(isinstance(item, str) and item for item in required):
        raise ZiweiRuleError("required_facts must contain strings")
    if not isinstance(exclusions, Sequence) or isinstance(exclusions, (str, bytes)):
        raise ZiweiRuleError("exclusions must be an array")
    for item in exclusions:
        _condition(item, "exclusion")
    if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or not refs or not all(isinstance(item, str) and item for item in refs):
        raise ZiweiRuleError("evidence_refs must contain at least one source_id")
    if not isinstance(constraints, Sequence) or isinstance(constraints, (str, bytes)) or "no_absolute_claims" not in constraints or "reality_override" not in constraints:
        raise ZiweiRuleError("output_constraints must require no_absolute_claims and reality_override")
    priority = raw["priority"]
    if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 100:
        raise ZiweiRuleError("priority must be an integer from 0 to 100")
    if raw["confidence"] not in {"low", "medium", "high"}:
        raise ZiweiRuleError("confidence is invalid")
    if raw["deterministic_or_inferential"] not in {"deterministic", "inferential"}:
        raise ZiweiRuleError("deterministic_or_inferential is invalid")
    if raw.get("direction", "support") not in {"support", "contradict"}:
        raise ZiweiRuleError("direction is invalid")
    for field in ("traditional_claim", "plain_language"):
        text = raw[field]
        if not isinstance(text, str) or not text.strip():
            raise ZiweiRuleError(f"{field} must be non-empty")
        if any(token in text for token in FORBIDDEN_ABSOLUTES):
            raise ZiweiRuleError(f"{field} contains forbidden absolute language")
    if raw["source_level"] not in {"reviewed_repository_source", "research_required"}:
        raise ZiweiRuleError("source_level is invalid")
    if raw["lifecycle"] not in {"draft", "active", "deprecated"}:
        raise ZiweiRuleError("lifecycle is invalid")
    if raw["conflict_policy"] != "higher_priority_then_unresolved":
        raise ZiweiRuleError("conflict_policy is invalid")
    return dict(raw)


def _matches(condition: Mapping[str, object], facts: Mapping[str, object]) -> bool:
    return condition["fact"] in facts and facts[condition["fact"]] == condition["equals"]


def evaluate_ziwei_rules(
    facts: Mapping[str, object], rules: Sequence[Mapping[str, object]]
) -> tuple[ZiweiRuleMatch, ...]:
    candidates: list[dict[str, object]] = []
    for raw in rules:
        card = validate_rule_card(raw)
        if any(name not in facts for name in card["required_facts"]):
            continue
        if not _matches(card["trigger"], facts):
            continue
        if any(_matches(item, facts) for item in card["exclusions"]):
            continue
        candidates.append(card)
    candidates.sort(key=lambda card: (-int(card["priority"]), str(card["rule_id"])))
    conflicts: set[str] = set()
    for card in candidates:
        for other in candidates:
            if (
                card is not other
                and card["domain"] == other["domain"]
                and card["priority"] == other["priority"]
                and card.get("direction", "support") != other.get("direction", "support")
            ):
                conflicts.update((str(card["rule_id"]), str(other["rule_id"])))
    return tuple(
        ZiweiRuleMatch(
            rule_id=str(card["rule_id"]),
            domain=str(card["domain"]),
            direction=str(card.get("direction", "support")),
            priority=int(card["priority"]),
            confidence=str(card["confidence"]),
            plain_language=str(card["plain_language"]),
            evidence_refs=tuple(str(item) for item in card["evidence_refs"]),
            resolution="unresolved_conflict" if card["rule_id"] in conflicts else "matched",
        )
        for card in candidates
    )


def build_rule_coverage(rules: Sequence[Mapping[str, object]]) -> dict[str, object]:
    cards = [validate_rule_card(rule) for rule in rules]
    implemented_pairs = {
        (str(card.get("primary_star")), str(card.get("palace")))
        for card in cards
        if card.get("primary_star") in PRIMARY_STARS and card.get("palace") in PALACES
    }
    return {
        "primary_stars": {name: "research_required" for name in PRIMARY_STARS},
        "palaces": {name: "contract_only" for name in PALACES},
        "star_palace_total": len(PRIMARY_STARS) * len(PALACES),
        "star_palace_implemented": len(implemented_pairs),
        "contracts": {
            name: "contract_only"
            for name in (
                "dual_star", "three_directions_four_orthogonals", "opposite_palace",
                "four_transformations", "supporting_and_malefic", "brightness",
                "pattern_recognition", "temporal_overlay", "reality_override",
            )
        },
        "release_gate": "GO" if len(implemented_pairs) == 168 else "NO-GO",
    }


__all__ = [
    "ZiweiRuleError", "ZiweiRuleMatch", "build_rule_coverage",
    "evaluate_ziwei_rules", "validate_rule_card",
]
