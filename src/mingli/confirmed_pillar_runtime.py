"""Deterministic static analysis for an explicitly confirmed four-pillar chart.

This runtime deliberately does not synthesize birth metadata.  It reuses the
reviewed Phase 9-12 engines for natal structure, strength, pattern, regulation,
and XiJi classification, while leaving timeline-dependent outputs unsupported.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal, Mapping

from .contracts.serialization import canonical_json, digest
from .derived.static_engine import SEXAGENARY, map_hidden_stems, map_ten_god
from .phase9_engine import calculate_day_master_strength
from .phase10_engine import evaluate_bazi_pattern
from .phase11_engine import evaluate_bazi_regulation
from .phase12 import evaluate_bazi_xiji_roles


CONFIRMED_PILLAR_SCHEMA_VERSION = "confirmed-pillar-runtime-result@1.0"
CONFIRMED_PILLAR_METHOD_ID = "confirmed-pillar-static-runtime@1.0.0"
CONFIRMED_PILLAR_CALCULATION_VERSION = "1.0.0"
PILLAR_ORDER = ("year", "month", "day", "hour")
CONFIRMED_SOURCES = frozenset({"image_confirmed", "text_confirmed"})
UNSUPPORTED_OUTPUTS = (
    "birth_date",
    "birth_time",
    "birth_location",
    "timezone",
    "true_solar_time",
    "luck_start_age",
    "dayun_timeline",
    "chenggu",
)

_ELEMENT_LABELS = {
    "wood": "木",
    "fire": "火",
    "earth": "土",
    "metal": "金",
    "water": "水",
}
_STRENGTH_LABELS = {
    "very_weak": "极弱",
    "weak": "偏弱",
    "balanced": "相对平衡",
    "strong": "偏强",
    "very_strong": "极强",
}
_PATTERN_LABELS = {
    "zheng_guan": "正官格",
    "qi_sha": "七杀格",
    "zheng_yin": "正印格",
    "pian_yin": "偏印格",
    "shi_shen": "食神格",
    "shang_guan": "伤官格",
    "zheng_cai": "正财格",
    "pian_cai": "偏财格",
    "cong_cai_candidate": "从财候选",
    "cong_er_candidate": "从儿候选",
    "cong_guan_sha_candidate": "从官杀候选",
    "cong_weak_candidate": "从弱候选",
}


class ConfirmedPillarInputError(ValueError):
    """Raised when confirmed image metadata cannot enter the static runtime."""


@dataclass(frozen=True)
class ConfirmedPillarRuntimeResult:
    chart: Mapping[str, object]
    artifacts: Mapping[str, Mapping[str, object]]
    unsupported: tuple[str, ...]
    warnings: tuple[str, ...]
    final_answer: str
    canonical_hash: str
    schema_version: str = field(
        default=CONFIRMED_PILLAR_SCHEMA_VERSION,
        init=False,
    )
    method_id: str = field(default=CONFIRMED_PILLAR_METHOD_ID, init=False)
    calculation_version: str = field(
        default=CONFIRMED_PILLAR_CALCULATION_VERSION,
        init=False,
    )
    prediction_validity: Literal["not_evaluated"] = field(
        default="not_evaluated",
        init=False,
    )

    def to_dict(self) -> dict[str, object]:
        return json.loads(canonical_json(asdict(self)))


def _validated_input(
    raw: Mapping[str, object],
) -> tuple[dict[str, str], str, str, str]:
    if not isinstance(raw, Mapping):
        raise ConfirmedPillarInputError("confirmed pillar input must be an object")
    if raw.get("confirmation_status") != "confirmed":
        raise ConfirmedPillarInputError("confirmed status is required")
    source = raw.get("source")
    if source not in CONFIRMED_SOURCES:
        raise ConfirmedPillarInputError(
            "source must be image_confirmed or text_confirmed"
        )
    if source == "text_confirmed":
        confirmation_id = raw.get("text_confirmation_id")
        if not isinstance(confirmation_id, str) or not confirmation_id.strip():
            raise ConfirmedPillarInputError(
                "text_confirmed requires text_confirmation_id"
            )
        if any(
            key in raw
            for key in (
                "image_hash",
                "vision_provider",
                "vision_request_id",
                "image_chart_confirmation",
            )
        ):
            raise ConfirmedPillarInputError(
                "text_confirmed must not contain image provenance"
            )
    elif "text_confirmation_id" in raw:
        raise ConfirmedPillarInputError(
            "image_confirmed must not contain text provenance"
        )
    trace_id = raw.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ConfirmedPillarInputError("trace_id is required")
    idempotency_key = raw.get("idempotency_key")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ConfirmedPillarInputError("idempotency_key is required")
    gender = raw.get("gender")
    if gender not in {"male", "female"}:
        raise ConfirmedPillarInputError("gender must be male or female")
    pillars = raw.get("pillars")
    if not isinstance(pillars, Mapping) or tuple(pillars) != PILLAR_ORDER:
        raise ConfirmedPillarInputError(
            "pillars must be ordered as year, month, day, hour"
        )
    normalized = {position: str(pillars[position]) for position in PILLAR_ORDER}
    if any(value not in SEXAGENARY for value in normalized.values()):
        raise ConfirmedPillarInputError(
            "pillar values must be legal sexagenary pairs"
        )
    day_master = raw.get("day_master")
    if day_master != normalized["day"][0]:
        raise ConfirmedPillarInputError(
            "day master must match the day pillar stem"
        )
    return normalized, str(day_master), str(gender), str(source)


def _graph_item(record_type: str, payload: dict[str, object]) -> dict[str, object]:
    result = dict(payload)
    result["canonical_digest"] = digest(
        {"record_type": record_type, "payload": payload}
    )
    return result


def _build_static_fact_graph(
    pillars: Mapping[str, str],
    day_master: str,
    gender: str,
    source: str,
) -> dict[str, object]:
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    for position in PILLAR_ORDER:
        value = pillars[position]
        stem, branch = value
        pillar_id = f"pillar:{position}"
        stem_id = f"stem:{position}:{stem}"
        branch_id = f"branch:{position}:{branch}"
        nodes.extend(
            (
                _graph_item(
                    "GraphNode",
                    {
                        "node_id": pillar_id,
                        "node_type": "Pillar",
                        "position": position,
                        "stem": stem,
                        "branch": branch,
                    },
                ),
                _graph_item(
                    "GraphNode",
                    {
                        "node_id": stem_id,
                        "node_type": "Stem",
                        "value": stem,
                        "position": position,
                    },
                ),
                _graph_item(
                    "GraphNode",
                    {
                        "node_id": branch_id,
                        "node_type": "Branch",
                        "value": branch,
                        "position": position,
                    },
                ),
            )
        )
        edges.extend(
            (
                _graph_item(
                    "GraphEdge",
                    {
                        "edge_id": f"contains:{pillar_id}->{stem_id}",
                        "edge_type": "contains",
                        "source": pillar_id,
                        "target": stem_id,
                    },
                ),
                _graph_item(
                    "GraphEdge",
                    {
                        "edge_id": f"contains:{pillar_id}->{branch_id}",
                        "edge_type": "contains",
                        "source": pillar_id,
                        "target": branch_id,
                    },
                ),
            )
        )
        ten_god = map_ten_god(day_master, stem)
        ten_god_id = f"ten-god:{position}:{ten_god.code}"
        nodes.append(
            _graph_item(
                "GraphNode",
                {
                    "node_id": ten_god_id,
                    "node_type": "TenGod",
                    "code": ten_god.code,
                    "label": ten_god.label,
                    "position": position,
                },
            )
        )
        edges.append(
            _graph_item(
                "GraphEdge",
                {
                    "edge_id": f"relative-to:{stem_id}->{ten_god_id}",
                    "edge_type": "relative_to_day_master",
                    "source": stem_id,
                    "target": ten_god_id,
                },
            )
        )
        for hidden in map_hidden_stems(branch, day_master=day_master):
            hidden_id = (
                f"hidden-stem:{position}:{branch}:{hidden.ordinal}:{hidden.stem}"
            )
            nodes.append(
                _graph_item(
                    "GraphNode",
                    {
                        "node_id": hidden_id,
                        "node_type": "HiddenStem",
                        "stem": hidden.stem,
                        "ordinal": hidden.ordinal,
                        "ten_god": (
                            hidden.ten_god.code
                            if hidden.ten_god is not None
                            else None
                        ),
                    },
                )
            )
            edges.append(
                _graph_item(
                    "GraphEdge",
                    {
                        "edge_id": f"contains:{branch_id}->{hidden_id}",
                        "edge_type": "contains",
                        "source": branch_id,
                        "target": hidden_id,
                    },
                )
            )
    payload: dict[str, object] = {
        "base_chart_ref": {
            "source": source,
            "pillar_fingerprint": digest(dict(pillars)),
        },
        "derived_structure_ref": {
            "source": "reviewed_static_mappings",
        },
        "profiles": [],
        "nodes": sorted(nodes, key=lambda item: str(item["node_id"])),
        "edges": sorted(edges, key=lambda item: str(item["edge_id"])),
        "timeline": {
            "status": "unsupported_without_birth_metadata",
            "dayun_periods": [],
            "liunian_periods": [],
        },
        "relations": [],
        "growth_stages": [],
        "provenance_index": {
            "input_source": source,
            "gender": gender,
        },
        "warnings": ["birth_metadata_not_inferred"],
        "unresolved": [
            {
                "code": "timeline_requires_birth_metadata",
                "fields": list(UNSUPPORTED_OUTPUTS),
            }
        ],
        "schema_version": "confirmed-pillar-static-fact-graph@1.0",
        "method_id": "confirmed-pillar-static-fact-graph@1.0.0",
        "calculation_version": "1.0.0",
        "prediction_validity": "not_evaluated",
    }
    payload["canonical_hash"] = digest(payload)
    return payload


def _element_list(values: object) -> str:
    if not isinstance(values, list) or not values:
        return "未决"
    return "、".join(_ELEMENT_LABELS.get(str(value), str(value)) for value in values)


def _pattern_label(pattern: Mapping[str, object]) -> str:
    primary = pattern.get("primary_candidates")
    candidates = pattern.get("candidates")
    if not isinstance(primary, list) or not isinstance(candidates, list):
        return "未决"
    primary_ids = {str(value) for value in primary}
    labels: list[str] = []
    for candidate in candidates:
        if (
            isinstance(candidate, Mapping)
            and str(candidate.get("candidate_id")) in primary_ids
        ):
            pattern_type = str(candidate.get("pattern_type"))
            labels.append(_PATTERN_LABELS.get(pattern_type, pattern_type))
    return "、".join(labels) if labels else "未决"


def _render(
    chart: Mapping[str, object],
    strength: Mapping[str, object],
    pattern: Mapping[str, object],
    xiji: Mapping[str, object],
) -> str:
    pillars = chart["pillars"]
    assert isinstance(pillars, Mapping)
    gender_label = "女命" if chart["gender"] == "female" else "男命"
    ordered = " ".join(str(pillars[position]) for position in PILLAR_ORDER)
    day_master = str(chart["day_master"])
    day_element = _ELEMENT_LABELS.get(
        str(strength.get("day_master_element")),
        str(strength.get("day_master_element")),
    )
    strength_label = _STRENGTH_LABELS.get(
        str(strength.get("classification")),
        str(strength.get("classification")),
    )
    return (
        "【图片命盘已确认】\n"
        f"{gender_label}：{ordered}\n"
        f"日主：{day_master}{day_element}\n\n"
        "【命局结构】\n"
        f"日主强弱：{strength_label}\n"
        f"主格局：{_pattern_label(pattern)}\n\n"
        "【喜忌分类】\n"
        f"用神：{_element_list(xiji.get('yongshen_elements'))}\n"
        f"喜神：{_element_list(xiji.get('xishen_elements'))}\n"
        f"忌神：{_element_list(xiji.get('jishen_elements'))}\n"
        f"未决元素：{_element_list(xiji.get('unresolved_elements'))}\n\n"
        "【计算边界】\n"
        "本次直接按已确认四柱进行静态命局计算。精确起运年龄、"
        "当前大运定位、称骨和真太阳时需要出生元数据，本次未计算，"
        "也未使用任何推测值。\n\n"
        "仅供文化研究与娱乐参考。"
    )


def run_confirmed_pillar_agent(
    raw: Mapping[str, object],
) -> ConfirmedPillarRuntimeResult:
    """Run the public static runtime for a user-confirmed chart provenance."""
    pillars, day_master, gender, source = _validated_input(raw)
    graph = _build_static_fact_graph(pillars, day_master, gender, source)
    strength = calculate_day_master_strength(graph).to_dict()
    pattern = evaluate_bazi_pattern(graph, strength).to_dict()
    regulation = evaluate_bazi_regulation(graph, strength, pattern).to_dict()
    xiji = evaluate_bazi_xiji_roles(regulation).to_dict()
    chart: dict[str, object] = {
        "pillars": pillars,
        "day_master": day_master,
        "gender": gender,
        "source": source,
    }
    artifacts: dict[str, Mapping[str, object]] = {
        "fact_graph": graph,
        "strength": strength,
        "pattern": pattern,
        "regulation": regulation,
        "xiji": xiji,
    }
    warnings = (
        "confirmed_pillar_static_mode",
        "birth_metadata_not_inferred",
        "timeline_dependent_outputs_unsupported",
        "prediction_validity_not_evaluated",
    )
    final_answer = _render(chart, strength, pattern, xiji)
    body = {
        "chart": chart,
        "artifacts": artifacts,
        "unsupported": list(UNSUPPORTED_OUTPUTS),
        "warnings": list(warnings),
        "final_answer": final_answer,
    }
    return ConfirmedPillarRuntimeResult(
        chart=chart,
        artifacts=artifacts,
        unsupported=UNSUPPORTED_OUTPUTS,
        warnings=warnings,
        final_answer=final_answer,
        canonical_hash=digest(
            {
                "record_type": "ConfirmedPillarRuntimeResult",
                "payload": body,
            }
        ),
    )
