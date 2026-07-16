from __future__ import annotations

from typing import Mapping

from .phase23 import run_mingli_agent
from .ziwei import build_ziwei_chart
from .ziwei_rules import (
    ZIWEI_RULE_CONTENT_VERSION,
    build_rule_coverage,
    evaluate_ziwei_chart_rules,
    load_ziwei_rule_content,
)

MINGLI_SERVICE_VERSION = "mingli-runtime-service@1.0.0"

_TOOLS = (
    (
        "analyze_mingli",
        "运行完整、确定性的 MingLi Runtime，并返回结构化结果与一次性免责声明。",
    ),
    (
        "create_ziwei_chart",
        "根据结构化出生资料生成版本化紫微命盘；未知时辰不会默认子时。",
    ),
    (
        "evaluate_ziwei_chart",
        "对完整且版本兼容的紫微命盘执行 draft 传统规则求值。",
    ),
    (
        "get_ziwei_rule_coverage",
        "返回规则内容的行为覆盖、重复项与 Release Hold 状态。",
    ),
)


def _object_payload(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def get_service_capabilities() -> dict[str, object]:
    return {
        "schema_version": "mingli-service-capabilities@1.0",
        "service_version": MINGLI_SERVICE_VERSION,
        "archetype": "tool-only",
        "transports": ["http", "streamable-http-mcp"],
        "request_storage": "none",
        "external_network_calls": False,
        "prediction_validity": "not_evaluated",
        "commercial_release_hold": "ACTIVE",
        "tools": [
            {
                "name": name,
                "description": description,
                "read_only": True,
                "destructive": False,
                "open_world": False,
                "idempotent": True,
            }
            for name, description in _TOOLS
        ],
    }


def analyze_mingli_payload(payload: object) -> dict[str, object]:
    value = _object_payload(payload, "runtime input")
    return run_mingli_agent(value).to_dict()


def build_ziwei_chart_payload(payload: object) -> dict[str, object]:
    value = _object_payload(payload, "Ziwei birth input")
    return build_ziwei_chart(value)


def evaluate_ziwei_chart_payload(payload: object) -> dict[str, object]:
    chart = _object_payload(payload, "Ziwei chart")
    rules = load_ziwei_rule_content()
    matches = evaluate_ziwei_chart_rules(chart, rules)
    effective = [
        item.to_dict()
        for item in matches
        if item.resolution != "suppressed_by_higher_priority"
    ]
    return {
        "schema_version": "ziwei-rule-evaluation@1.0",
        "algorithm_version": chart.get("algorithm_version"),
        "content_version": ZIWEI_RULE_CONTENT_VERSION,
        "evaluated_rules": len(rules),
        "matched_rules": len(matches),
        "effective_match_count": len(effective),
        "effective_matches": effective,
        "suppressed_matches": sum(
            item.resolution == "suppressed_by_higher_priority" for item in matches
        ),
        "prediction_validity": "not_evaluated",
        "rule_content_hold": "ACTIVE",
    }


def get_ziwei_coverage() -> dict[str, object]:
    return build_rule_coverage()


__all__ = [
    "MINGLI_SERVICE_VERSION",
    "analyze_mingli_payload",
    "build_ziwei_chart_payload",
    "evaluate_ziwei_chart_payload",
    "get_service_capabilities",
    "get_ziwei_coverage",
]
