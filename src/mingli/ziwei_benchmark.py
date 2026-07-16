from __future__ import annotations

from importlib import resources
import json
from pathlib import Path
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator

from .contracts import get_schema
from .contracts.serialization import digest
from .ziwei import ZIWEI_ALGORITHM_VERSION, build_ziwei_chart

CLASSIFICATIONS = ("hit", "partial_hit", "unverifiable", "wrong")
ZIWEI_ENGINE_BENCHMARK_RESOURCE = "ziwei_engine_benchmarks_v1.json"
ZIWEI_ENGINE_BENCHMARK_SCHEMA_VERSION = "ziwei-engine-benchmarks@1.0"
ZIWEI_ENGINE_EXPECTED_FIELDS = frozenset(
    {
        "life_palace_branch",
        "body_palace_branch",
        "bureau",
        "ziwei_branch",
        "tianfu_branch",
    }
)


def _validate_engine_benchmark_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("Ziwei engine benchmark payload must be an object")
    if payload.get("schema_version") != ZIWEI_ENGINE_BENCHMARK_SCHEMA_VERSION:
        raise ValueError("Ziwei engine benchmark schema_version is unsupported")
    if payload.get("algorithm_version") != ZIWEI_ALGORITHM_VERSION:
        raise ValueError("Ziwei engine benchmark algorithm_version does not match the runtime")
    sources = payload.get("source_provenance")
    if (
        not isinstance(sources, list)
        or not sources
        or any(not isinstance(source, str) or not source for source in sources)
        or len(set(sources)) != len(sources)
    ):
        raise ValueError("Ziwei engine benchmark source_provenance must be non-empty and unique")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Ziwei engine benchmark requires at least one case")
    case_ids: set[str] = set()
    for raw_case in cases:
        if not isinstance(raw_case, Mapping):
            raise ValueError("Ziwei engine benchmark case must be an object")
        case_id = raw_case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise ValueError("Ziwei engine benchmark case_id must be non-empty and unique")
        case_ids.add(case_id)
        chart_input = raw_case.get("input")
        expected = raw_case.get("expected")
        if not isinstance(chart_input, Mapping):
            raise ValueError("Ziwei engine benchmark case input must be an object")
        if not isinstance(expected, Mapping) or set(expected) != ZIWEI_ENGINE_EXPECTED_FIELDS:
            raise ValueError("Ziwei engine benchmark case has invalid expected fields")
        if any(not isinstance(value, str) or not value for value in expected.values()):
            raise ValueError("Ziwei engine benchmark expected values must be non-empty strings")
    return payload


def _load_engine_benchmark_payload(path: Path | None = None) -> dict[str, object]:
    if path is None:
        text = (
            resources.files("mingli.derived.data")
            .joinpath(ZIWEI_ENGINE_BENCHMARK_RESOURCE)
            .read_text(encoding="utf-8")
        )
    else:
        text = path.read_text(encoding="utf-8")
    return _validate_engine_benchmark_payload(json.loads(text))


def _star_branch(chart: Mapping[str, object], star_id: str) -> str | None:
    palaces = chart.get("palaces")
    if not isinstance(palaces, Sequence) or isinstance(palaces, (str, bytes)):
        return None
    for palace in palaces:
        if not isinstance(palace, Mapping):
            continue
        for field in ("primary_stars", "supporting_stars", "malefic_stars"):
            stars = palace.get(field)
            if not isinstance(stars, Sequence) or isinstance(stars, (str, bytes)):
                continue
            if any(isinstance(star, Mapping) and star.get("star_id") == star_id for star in stars):
                branch = palace.get("earthly_branch")
                return str(branch) if isinstance(branch, str) else None
    return None


def run_ziwei_engine_benchmarks(path: Path | None = None) -> dict[str, object]:
    payload = _load_engine_benchmark_payload(path)
    cases = payload["cases"]
    assert isinstance(cases, list)
    results: list[dict[str, object]] = []
    covered_bureaus: set[str] = set()
    for raw_case in cases:
        if not isinstance(raw_case, Mapping):
            raise ValueError("Ziwei engine benchmark case must be an object")
        chart_input = raw_case.get("input")
        expected = raw_case.get("expected")
        if not isinstance(chart_input, Mapping) or not isinstance(expected, Mapping):
            raise ValueError("Ziwei engine benchmark case requires input and expected objects")
        chart = build_ziwei_chart(chart_input)
        life_index = chart.get("life_palace")
        body_index = chart.get("body_palace")
        palaces = chart.get("palaces")
        if not isinstance(life_index, int) or not isinstance(body_index, int) or not isinstance(palaces, list):
            raise ValueError("Ziwei engine benchmark requires a complete chart")
        bureau = chart.get("bureau")
        if not isinstance(bureau, Mapping):
            raise ValueError("Ziwei engine benchmark requires a bureau")
        actual = {
            "life_palace_branch": palaces[life_index]["earthly_branch"],
            "body_palace_branch": palaces[body_index]["earthly_branch"],
            "bureau": bureau.get("label"),
            "ziwei_branch": _star_branch(chart, "ziwei"),
            "tianfu_branch": _star_branch(chart, "tianfu"),
        }
        failures = [key for key, value in expected.items() if actual.get(str(key)) != value]
        if isinstance(actual["bureau"], str):
            covered_bureaus.add(actual["bureau"])
        results.append(
            {
                "case_id": raw_case.get("case_id"),
                "passed": not failures,
                "failed_fields": failures,
                "chart_fingerprint": chart["chart_fingerprint"],
                "canonical_hash": chart["canonical_hash"],
            }
        )
    report: dict[str, object] = {
        "schema_version": "ziwei-engine-benchmark-report@1.0",
        "algorithm_version": payload.get("algorithm_version"),
        "total_cases": len(results),
        "passed_cases": sum(bool(item["passed"]) for item in results),
        "failed_cases": sum(not bool(item["passed"]) for item in results),
        "covered_bureaus": sorted(covered_bureaus),
        "cases": results,
        "source_provenance": payload.get("source_provenance", []),
        "prediction_validity": "not_evaluated",
    }
    report["canonical_hash"] = digest(
        {"record_type": "ZiweiEngineBenchmarkReport", "payload": report}
    )
    return report


def summarize_ziwei_cases(cases: Sequence[Mapping[str, object]]) -> dict[str, object]:
    validator = Draft202012Validator(get_schema("ziwei_anonymous_case.schema.json"))
    counts = {name: 0 for name in CLASSIFICATIONS}
    eligible = 0
    excluded = 0
    for case in cases:
        validator.validate(case)
        consent = case["consent"]
        assert isinstance(consent, Mapping)
        allowed = (
            consent["consent_for_storage"] is True
            and consent["anonymization_status"] == "anonymized"
            and consent["withdrawal_status"] == "not_requested"
        )
        if not allowed:
            excluded += 1
            continue
        eligible += 1
        assessments = case["assessments"]
        assert isinstance(assessments, Sequence)
        for assessment in assessments:
            assert isinstance(assessment, Mapping)
            classification = assessment.get("classification")
            if classification in counts:
                counts[str(classification)] += 1
    denominator = counts["hit"] + counts["partial_hit"] + counts["wrong"]
    return {
        "total_cases": len(cases),
        "eligible_cases": eligible,
        "excluded_withdrawn_or_unconsented": excluded,
        "classifications": counts,
        "verifiable_assessments": denominator,
        "accuracy_rate": None if denominator == 0 else counts["hit"] / denominator,
        "accuracy_definition": "strict_hit/(hit+partial_hit+wrong); unverifiable excluded",
        "prediction_validity": "not_evaluated",
        "release_gate": "NO-GO" if eligible == 0 else "REQUIRES_REVIEW",
    }


__all__ = ["run_ziwei_engine_benchmarks", "summarize_ziwei_cases"]
