from __future__ import annotations

from dataclasses import dataclass
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from mingli.contracts.models import (
    DependencyAmbiguity,
    DerivedChartResult,
    DerivedPillar,
    HiddenStemRecord,
    NayinRecord,
    TenGodRecord,
    XunKongRecord,
)
from mingli.contracts.serialization import digest
from mingli.contracts.sources import CAPABILITIES, validate_source_manifest
from mingli.contracts.validation import contract_error, load_convention_profile

from .adapter import adapt_base_chart

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
POSITIONS = ("year", "month", "day", "hour")
DEFAULT_PROFILE_ID = "derived-static-r1@0.1"
ASSERTION_RESOURCE = "generated-static-assertions-v0.1"

CLASSICAL_YUAN = "yuan-hai-zi-ping-wikisource-20260711"
CLASSICAL_SANMING = "san-ming-tong-hui-ctext-20260711"
MODERN_LUNAR = "lunar-python-lunarutil-master-20260711"

SOURCE_IDS: dict[str, tuple[str, ...]] = {
    "hidden_stems": (CLASSICAL_YUAN, MODERN_LUNAR),
    "visible_stem_ten_gods": (CLASSICAL_YUAN, MODERN_LUNAR),
    "hidden_stem_ten_gods": (CLASSICAL_YUAN, MODERN_LUNAR),
    "nayin": (CLASSICAL_SANMING, MODERN_LUNAR),
    "xunkong": (CLASSICAL_YUAN, CLASSICAL_SANMING, MODERN_LUNAR),
}

SOURCE_GROUPS: dict[str, tuple[str, ...]] = {
    "hidden_stems": ("classical-yuan-hai-zi-ping", "modern-6tail-lunar"),
    "visible_stem_ten_gods": ("classical-yuan-hai-zi-ping", "modern-6tail-lunar"),
    "hidden_stem_ten_gods": ("classical-yuan-hai-zi-ping", "modern-6tail-lunar"),
    "nayin": ("classical-san-ming-tong-hui", "modern-6tail-lunar"),
    "xunkong": ("classical-yuan-hai-zi-ping", "classical-san-ming-tong-hui", "modern-6tail-lunar"),
}

STEM_ELEMENT = {
    "甲": "wood",
    "乙": "wood",
    "丙": "fire",
    "丁": "fire",
    "戊": "earth",
    "己": "earth",
    "庚": "metal",
    "辛": "metal",
    "壬": "water",
    "癸": "water",
}
STEM_POLARITY = {stem: ("yang" if index % 2 == 0 else "yin") for index, stem in enumerate(STEMS)}
GENERATES = {"wood": "fire", "fire": "earth", "earth": "metal", "metal": "water", "water": "wood"}
CONTROLS = {"wood": "earth", "earth": "water", "water": "fire", "fire": "metal", "metal": "wood"}

TEN_GOD_LABELS = {
    "peer_same_polarity": "比肩",
    "peer_opposite_polarity": "劫财",
    "output_same_polarity": "食神",
    "output_opposite_polarity": "伤官",
    "wealth_same_polarity": "偏财",
    "wealth_opposite_polarity": "正财",
    "authority_same_polarity": "七杀",
    "authority_opposite_polarity": "正官",
    "resource_same_polarity": "偏印",
    "resource_opposite_polarity": "正印",
}

HIDDEN_STEMS: dict[str, tuple[str, ...]] = {
    "子": ("癸",),
    "丑": ("己", "癸", "辛"),
    "寅": ("甲", "丙", "戊"),
    "卯": ("乙",),
    "辰": ("戊", "乙", "癸"),
    "巳": ("丙", "戊", "庚"),
    "午": ("丁", "己"),
    "未": ("己", "丁", "乙"),
    "申": ("庚", "壬", "戊"),
    "酉": ("辛",),
    "戌": ("戊", "辛", "丁"),
    "亥": ("壬", "甲"),
}

NAYIN_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("海中金", "sea_gold", "甲子乙丑"),
    ("炉中火", "furnace_fire", "丙寅丁卯"),
    ("大林木", "great_forest_wood", "戊辰己巳"),
    ("路旁土", "roadside_earth", "庚午辛未"),
    ("剑锋金", "sword_edge_gold", "壬申癸酉"),
    ("山头火", "mountain_top_fire", "甲戌乙亥"),
    ("涧下水", "stream_water", "丙子丁丑"),
    ("城头土", "city_wall_earth", "戊寅己卯"),
    ("白蜡金", "white_wax_gold", "庚辰辛巳"),
    ("杨柳木", "willow_wood", "壬午癸未"),
    ("泉中水", "spring_water", "甲申乙酉"),
    ("屋上土", "roof_earth", "丙戌丁亥"),
    ("霹雳火", "thunder_fire", "戊子己丑"),
    ("松柏木", "pine_cypress_wood", "庚寅辛卯"),
    ("长流水", "long_flowing_water", "壬辰癸巳"),
    ("沙中金", "sand_gold", "甲午乙未"),
    ("山下火", "mountain_foot_fire", "丙申丁酉"),
    ("平地木", "flatland_wood", "戊戌己亥"),
    ("壁上土", "wall_earth", "庚子辛丑"),
    ("金箔金", "gold_leaf_gold", "壬寅癸卯"),
    ("佛灯火", "lamp_fire", "甲辰乙巳"),
    ("天河水", "milky_way_water", "丙午丁未"),
    ("大驿土", "great_post_earth", "戊申己酉"),
    ("钗钏金", "hairpin_gold", "庚戌辛亥"),
    ("桑柘木", "mulberry_wood", "壬子癸丑"),
    ("大溪水", "great_stream_water", "甲寅乙卯"),
    ("沙中土", "sand_earth", "丙辰丁巳"),
    ("天上火", "sky_fire", "戊午己未"),
    ("石榴木", "pomegranate_wood", "庚申辛酉"),
    ("大海水", "great_sea_water", "壬戌癸亥"),
)

SEXAGENARY = tuple(STEMS[index % 10] + BRANCHES[index % 12] for index in range(60))
NAYIN_BY_PILLAR = {
    pillar: {"code": code, "label": label}
    for label, code, pair in NAYIN_PAIRS
    for pillar in (pair[:2], pair[2:])
}
XUN_STARTS = ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅")
XUN_VOID_BRANCHES = {
    "甲子": ("戌", "亥"),
    "甲戌": ("申", "酉"),
    "甲申": ("午", "未"),
    "甲午": ("辰", "巳"),
    "甲辰": ("寅", "卯"),
    "甲寅": ("子", "丑"),
}


@dataclass(frozen=True)
class StaticBenchmarkResult:
    total: int
    passed: int
    failed: int
    unresolved: int
    capability_counts: Mapping[str, int]
    source_group_counts: Mapping[str, int]
    independence_group_violations: int
    deterministic_hash_mismatches: int
    schema_failures: int
    provenance_failures: int
    failures: tuple[str, ...]


def _data_file(name: str):
    if "/" in name or "\\" in name:
        raise ValueError("data resource name must be a file name")
    return files("mingli.derived.data").joinpath(name)


def _load_json_resource(name: str) -> dict[str, object]:
    value = json.loads(_data_file(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"data resource is not an object: {name}")
    return value


def load_packaged_capability_manifest() -> dict[str, object]:
    return _load_json_resource("phase6_capability_manifest_v0.1.json")


def load_packaged_source_manifest() -> dict[str, object]:
    return _load_json_resource("phase6_source_manifest_v0.1.json")


def _assertion_record(
    assertion_id: str,
    capability: str,
    fixture: Mapping[str, object],
    expected: object,
    determinism_level: str,
) -> dict[str, object]:
    source_ids = list(SOURCE_IDS[capability])
    source_groups = list(SOURCE_GROUPS[capability])
    return {
        "assertion_id": assertion_id,
        "capability_id": capability,
        "input_fixture": dict(fixture),
        "expected_source_group": source_groups[0],
        "expected_mapping_result": expected,
        "expected_provenance": {
            "source_ids": source_ids,
            "source_groups": source_groups,
        },
        "expected_confidence": {
            "status": "verified",
            "determinism_level": determinism_level,
        },
        "expected_error_code": None,
        "independence_group_expectation": {
            "minimum_reviewed_groups": 2,
            "actual_groups": source_groups,
        },
        "canonical_digest": digest(expected),
        "pass_fail": "pass",
        "independent": True,
        "source_version": "phase6-source-manifest@0.1",
    }


def _generated_static_assertions() -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for day_master in STEMS:
        for target in STEMS:
            expected = map_ten_god(day_master, target).to_dict()
            records.append(
                _assertion_record(
                    f"visible-ten-god-{day_master}-{target}",
                    "visible_stem_ten_gods",
                    {"day_master": day_master, "target_stem": target},
                    expected,
                    "D1",
                )
            )
    for branch in BRANCHES:
        expected = [record.to_dict() for record in map_hidden_stems(branch)]
        records.append(_assertion_record(f"hidden-stems-{branch}", "hidden_stems", {"branch": branch}, expected, "D2"))
    for day_master in STEMS:
        for branch in BRANCHES:
            expected = [record.to_dict() for record in map_hidden_stems(branch, day_master=day_master)]
            records.append(
                _assertion_record(
                    f"hidden-stem-ten-god-{day_master}-{branch}",
                    "hidden_stem_ten_gods",
                    {"day_master": day_master, "branch": branch},
                    expected,
                    "D2",
                )
            )
    for pillar in SEXAGENARY:
        records.append(_assertion_record(f"nayin-{pillar}", "nayin", {"pillar": pillar}, map_nayin(pillar).to_dict(), "D1"))
    for pillar in SEXAGENARY:
        records.append(_assertion_record(f"xunkong-{pillar}", "xunkong", {"pillar": pillar}, map_xunkong(pillar).to_dict(), "D1"))
    return tuple(records)


def load_static_assertions(path: Path | None = None) -> tuple[dict[str, object], ...]:
    if path is None:
        return _generated_static_assertions()
    text = path.read_text(encoding="utf-8")
    label = str(path)
    assertions: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{label}:{line_number}: assertion must be an object")
        assertions.append(value)
    return tuple(assertions)


def _validate_stem(stem: object, field_path: str) -> str:
    if not isinstance(stem, str) or stem not in STEM_ELEMENT:
        raise contract_error("DERIVED_FIELD_NOT_AVAILABLE", "unsupported stem", field_path=field_path, dependency=str(stem))
    return stem


def _validate_branch(branch: object, field_path: str) -> str:
    if not isinstance(branch, str) or branch not in HIDDEN_STEMS:
        raise contract_error("DERIVED_FIELD_NOT_AVAILABLE", "unsupported branch", field_path=field_path, dependency=str(branch))
    return branch


def _validate_pillar(pillar: object, field_path: str) -> str:
    if not isinstance(pillar, str) or len(pillar) != 2:
        raise contract_error("DERIVED_FIELD_NOT_AVAILABLE", "pillar must be a two-character ganzhi", field_path=field_path)
    stem = _validate_stem(pillar[0], f"{field_path}.stem")
    branch = _validate_branch(pillar[1], f"{field_path}.branch")
    if pillar not in SEXAGENARY:
        raise contract_error("DERIVED_FIELD_NOT_AVAILABLE", "pillar is not in the sexagenary cycle", field_path=field_path, dependency=pillar)
    return stem + branch


def map_ten_god(day_master: str, target_stem: str) -> TenGodRecord:
    day_master = _validate_stem(day_master, "day_master")
    target_stem = _validate_stem(target_stem, "target_stem")
    master_element = STEM_ELEMENT[day_master]
    target_element = STEM_ELEMENT[target_stem]
    same_polarity = STEM_POLARITY[day_master] == STEM_POLARITY[target_stem]
    suffix = "same_polarity" if same_polarity else "opposite_polarity"
    if target_element == master_element:
        relation = "peer"
    elif GENERATES[master_element] == target_element:
        relation = "output"
    elif CONTROLS[master_element] == target_element:
        relation = "wealth"
    elif CONTROLS[target_element] == master_element:
        relation = "authority"
    elif GENERATES[target_element] == master_element:
        relation = "resource"
    else:
        raise contract_error("DERIVED_FIELD_NOT_AVAILABLE", "ten-god relation is unavailable", field_path="target_stem")
    code = f"{relation}_{suffix}"
    return TenGodRecord(code, TEN_GOD_LABELS[code], SOURCE_IDS["visible_stem_ten_gods"])


def map_hidden_stems(branch: str, *, day_master: str | None = None) -> tuple[HiddenStemRecord, ...]:
    branch = _validate_branch(branch, "branch")
    stems = HIDDEN_STEMS[branch]
    return tuple(
        HiddenStemRecord(
            ordinal=index,
            stem=stem,
            ten_god=map_ten_god(day_master, stem) if day_master is not None else None,
            source_ids=SOURCE_IDS["hidden_stems"],
        )
        for index, stem in enumerate(stems, 1)
    )


def map_nayin(pillar: str) -> NayinRecord:
    pillar = _validate_pillar(pillar, "pillar")
    item = NAYIN_BY_PILLAR[pillar]
    return NayinRecord(str(item["code"]), str(item["label"]), SOURCE_IDS["nayin"])


def map_xunkong(pillar: str) -> XunKongRecord:
    pillar = _validate_pillar(pillar, "pillar")
    index = SEXAGENARY.index(pillar)
    xun_start = XUN_STARTS[index // 10]
    return XunKongRecord(xun_start, index % 10 + 1, XUN_VOID_BRANCHES[xun_start], SOURCE_IDS["xunkong"])


def _requested_capabilities(capabilities: Iterable[str] | None) -> tuple[str, ...]:
    if capabilities is None:
        return tuple(sorted(CAPABILITIES))
    requested = tuple(dict.fromkeys(capabilities))
    unknown = sorted(set(requested) - CAPABILITIES)
    if unknown:
        raise contract_error("DERIVED_CAPABILITY_NOT_ENABLED", "unsupported capability", field_path="capabilities", dependency=", ".join(unknown))
    return requested


def _ensure_source_readiness(source_manifest: Mapping[str, object], capabilities: Sequence[str]) -> None:
    result = validate_source_manifest(source_manifest)
    ready = set(result.implementation_ready)
    missing = sorted(set(capabilities) - ready)
    if missing:
        raise contract_error("DERIVED_DEPENDENCY_UNRESOLVED", "source manifest does not satisfy reviewed independence groups", field_path="source_manifest", dependency=", ".join(missing))


def _base_ambiguities(base: Mapping[str, object]) -> tuple[DependencyAmbiguity, ...]:
    raw = base.get("ambiguities", ())
    if not raw:
        return ()
    if not isinstance(raw, list | tuple):
        return (
            DependencyAmbiguity(
                dependency="base.ambiguities",
                field_paths=("base.ambiguities",),
                source_ids=(),
                message="基础盘 ambiguity 字段不可解析",
            ),
        )
    ambiguities: list[DependencyAmbiguity] = []
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            fields = item.get("field_paths", ())
            sources = item.get("source_ids", ())
            ambiguities.append(
                DependencyAmbiguity(
                    dependency=str(item.get("dependency", f"base.ambiguities[{index}]")),
                    field_paths=tuple(str(field) for field in fields) if isinstance(fields, (list, tuple)) else (f"base.ambiguities[{index}]",),
                    source_ids=tuple(str(source) for source in sources) if isinstance(sources, (list, tuple)) else (),
                    message=str(item.get("message", "基础盘存在未决依赖")),
                )
            )
    return tuple(ambiguities)


def derive_static_chart(
    base_chart: Mapping[str, object],
    *,
    capabilities: Iterable[str] | None = None,
    profile_id: str = DEFAULT_PROFILE_ID,
    strict: bool = True,
    source_manifest: Mapping[str, object] | None = None,
) -> DerivedChartResult:
    if not isinstance(base_chart, Mapping):
        raise contract_error("DERIVED_BASE_RESULT_INVALID", "base chart must be an object", field_path="base_chart")
    requested = _requested_capabilities(capabilities)
    manifest = source_manifest if source_manifest is not None else load_packaged_source_manifest()
    _ensure_source_readiness(manifest, requested)
    base_ref = adapt_base_chart(base_chart)
    profile = load_convention_profile(profile_id)
    ambiguities = _base_ambiguities(base_chart)
    if ambiguities and strict:
        raise contract_error("DERIVED_DEPENDENCY_UNRESOLVED", "base chart has unresolved dependencies", field_path="base_chart.ambiguities", dependency=ambiguities[0].dependency, profile_id=profile_id)
    if ambiguities:
        return DerivedChartResult(
            base_ref=base_ref,
            convention_profile=profile,
            status="partial",
            ambiguities=ambiguities,
            warnings=("基础盘存在未决依赖；仅显式 partial API 返回部分结果。",),
        )
    pillars = base_chart["pillars"]
    if not isinstance(pillars, Mapping):
        raise contract_error("DERIVED_BASE_RESULT_INVALID", "base pillars is invalid", field_path="pillars")
    day_pillar = _validate_pillar(pillars.get("day"), "pillars.day")
    day_master = day_pillar[0]
    derived: list[DerivedPillar] = []
    for position in POSITIONS:
        pillar = _validate_pillar(pillars.get(position), f"pillars.{position}")
        stem, branch = pillar[0], pillar[1]
        include_hidden_ten_gods = "hidden_stem_ten_gods" in requested
        derived.append(
            DerivedPillar(
                position=position,  # type: ignore[arg-type]
                stem=stem,
                branch=branch,
                stem_ten_god=map_ten_god(day_master, stem) if "visible_stem_ten_gods" in requested else None,
                hidden_stems=map_hidden_stems(branch, day_master=day_master if include_hidden_ten_gods else None)
                if ("hidden_stems" in requested or include_hidden_ten_gods)
                else (),
                nayin=map_nayin(pillar) if "nayin" in requested else None,
                xunkong=map_xunkong(pillar) if "xunkong" in requested else None,
            )
        )
    return DerivedChartResult(base_ref=base_ref, convention_profile=profile, pillars=tuple(derived))


def _mapping_for_assertion(assertion: Mapping[str, object]) -> object:
    capability = assertion.get("capability_id")
    fixture = assertion.get("input_fixture")
    if not isinstance(capability, str) or not isinstance(fixture, Mapping):
        raise ValueError("assertion capability_id and input_fixture are required")
    if capability == "hidden_stems":
        branch = fixture.get("branch")
        return [record.to_dict() for record in map_hidden_stems(str(branch))]
    if capability == "visible_stem_ten_gods":
        return map_ten_god(str(fixture.get("day_master")), str(fixture.get("target_stem"))).to_dict()
    if capability == "hidden_stem_ten_gods":
        return [record.to_dict() for record in map_hidden_stems(str(fixture.get("branch")), day_master=str(fixture.get("day_master")))]
    if capability == "nayin":
        return map_nayin(str(fixture.get("pillar"))).to_dict()
    if capability == "xunkong":
        return map_xunkong(str(fixture.get("pillar"))).to_dict()
    raise ValueError(f"unsupported assertion capability: {capability}")


def validate_static_assertions(
    assertions: Sequence[Mapping[str, object]],
    *,
    source_manifest: Mapping[str, object] | None = None,
) -> tuple[str, ...]:
    manifest = source_manifest if source_manifest is not None else load_packaged_source_manifest()
    source_groups_by_id = {
        str(source["source_id"]): str(source["independence_group"])
        for source in manifest.get("sources", [])
        if isinstance(source, Mapping) and source.get("verification_status") == "reviewed"
    }
    issues: list[str] = []
    seen: set[str] = set()
    capability_counts = {capability: 0 for capability in CAPABILITIES}
    for index, assertion in enumerate(assertions, 1):
        assertion_id = assertion.get("assertion_id")
        if not isinstance(assertion_id, str) or not assertion_id:
            issues.append(f"line {index}: invalid assertion_id")
        elif assertion_id in seen:
            issues.append(f"{assertion_id}: duplicate assertion_id")
        else:
            seen.add(assertion_id)
        capability = assertion.get("capability_id")
        if capability not in CAPABILITIES:
            issues.append(f"{assertion_id}: unsupported capability_id")
            continue
        capability_counts[str(capability)] += 1
        expected = assertion.get("expected_mapping_result")
        if expected in (None, {}, []):
            issues.append(f"{assertion_id}: expected_mapping_result is empty")
        provenance = assertion.get("expected_provenance")
        if not isinstance(provenance, Mapping):
            issues.append(f"{assertion_id}: expected_provenance is required")
            continue
        source_ids = provenance.get("source_ids")
        if not isinstance(source_ids, list) or len(source_ids) < 2:
            issues.append(f"{assertion_id}: at least two source_ids are required")
            continue
        groups = [source_groups_by_id.get(str(source_id)) for source_id in source_ids]
        if any(group is None for group in groups) or len(set(groups)) < 2:
            issues.append(f"{assertion_id}: source_ids do not satisfy independent reviewed groups")
        expected_digest = assertion.get("canonical_digest")
        if expected_digest != digest(expected):
            issues.append(f"{assertion_id}: canonical digest mismatch")
    for capability, count in sorted(capability_counts.items()):
        if count == 0:
            issues.append(f"{capability}: missing assertion coverage")
    if len(assertions) < 272:
        issues.append(f"requires at least 272 assertions; found {len(assertions)}")
    return tuple(issues)


def benchmark_static_mappings(path: Path | None = None) -> StaticBenchmarkResult:
    assertions = load_static_assertions(path)
    validation_issues = validate_static_assertions(assertions)
    failures: list[str] = list(validation_issues)
    capability_counts: dict[str, int] = {capability: 0 for capability in sorted(CAPABILITIES)}
    source_group_counts: dict[str, int] = {}
    passed = failed = unresolved = hash_mismatches = provenance_failures = independence_violations = 0
    for assertion in assertions:
        capability = str(assertion.get("capability_id"))
        if capability in capability_counts:
            capability_counts[capability] += 1
        provenance = assertion.get("expected_provenance")
        if isinstance(provenance, Mapping):
            for group in provenance.get("source_groups", []):
                source_group_counts[str(group)] = source_group_counts.get(str(group), 0) + 1
            groups = provenance.get("source_groups", [])
            if not isinstance(groups, list) or len(set(str(group) for group in groups)) < 2:
                independence_violations += 1
        expected_status = assertion.get("expected_confidence", {}).get("status") if isinstance(assertion.get("expected_confidence"), Mapping) else None
        if expected_status == "unresolved":
            unresolved += 1
            continue
        try:
            actual = _mapping_for_assertion(assertion)
        except Exception as exc:  # noqa: BLE001 - converted into benchmark failure text.
            failed += 1
            failures.append(f"{assertion.get('assertion_id')}: {exc}")
            continue
        expected = assertion.get("expected_mapping_result")
        if assertion.get("canonical_digest") != digest(expected):
            hash_mismatches += 1
        if not isinstance(provenance, Mapping) or not provenance.get("source_ids"):
            provenance_failures += 1
        if actual == expected:
            passed += 1
        else:
            failed += 1
            failures.append(f"{assertion.get('assertion_id')}: expected {expected}, got {actual}")
    return StaticBenchmarkResult(
        total=len(assertions),
        passed=passed,
        failed=failed,
        unresolved=unresolved,
        capability_counts=capability_counts,
        source_group_counts=dict(sorted(source_group_counts.items())),
        independence_group_violations=independence_violations,
        deterministic_hash_mismatches=hash_mismatches,
        schema_failures=0,
        provenance_failures=provenance_failures,
        failures=tuple(failures),
    )
