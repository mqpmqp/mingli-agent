from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_FLOOR, getcontext
import itertools
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

from .bazi import DeterministicBaziEngine, solar_term_utc
from .contracts.serialization import canonical_json, digest
from .derived.adapter import adapt_base_chart
from .derived.static_engine import (
    BRANCHES,
    SEXAGENARY,
    STEMS,
    derive_static_chart,
    map_hidden_stems,
    map_nayin,
    map_ten_god,
    map_xunkong,
)

getcontext().prec = 28

PHASE7_SCHEMA_VERSION = "bazi-fact-graph-result@0.1"
PHASE7_METHOD_ID = "bazi-deterministic-fact-graph@0.1.0"
PHASE7_CALCULATION_VERSION = "0.1.0"
DEFAULT_PROFILE_SET_ID = "phase7-fact-graph-r1@0.1"
DEFAULT_DAYUN_COUNT = 10
DEFAULT_LIUNIAN_SPAN = 10
TROPICAL_YEAR_DAYS = Decimal("365.2425")
SECONDS_PER_DAY = Decimal("86400")
MICROSECONDS_PER_SECOND = Decimal("1000000")

SOURCE_IDS = (
    "hko-stems-branches-1901-2100-20260711",
    "yuan-hai-zi-ping-wikisource-20260711",
    "san-ming-tong-hui-ctext-20260711",
    "lunar-python-lunarutil-master-20260711",
)
SOURCE_GROUPS = ("calendar-authority", "classical-yuan-hai-zi-ping", "classical-san-ming-tong-hui", "modern-6tail-lunar")
STAGE_CODES = (
    "chang_sheng",
    "mu_yu",
    "guan_dai",
    "lin_guan",
    "di_wang",
    "shuai",
    "bing",
    "si",
    "mu",
    "jue",
    "tai",
    "yang",
)
STAGE_LABELS = {
    "chang_sheng": "Chang Sheng",
    "mu_yu": "Mu Yu",
    "guan_dai": "Guan Dai",
    "lin_guan": "Lin Guan",
    "di_wang": "Di Wang",
    "shuai": "Shuai",
    "bing": "Bing",
    "si": "Si",
    "mu": "Mu",
    "jue": "Jue",
    "tai": "Tai",
    "yang": "Yang",
}
GROWTH_START_BRANCH_INDEX = {
    0: 11,
    1: 6,
    2: 2,
    3: 9,
    4: 2,
    5: 9,
    6: 5,
    7: 0,
    8: 8,
    9: 3,
}
STEM_FIVE_COMBINE = {frozenset(pair) for pair in ((0, 5), (1, 6), (2, 7), (3, 8), (4, 9))}
STEM_CLASH = {frozenset(pair) for pair in ((0, 6), (1, 7), (2, 8), (3, 9))}
BRANCH_LIUHE = {frozenset(pair) for pair in ((0, 1), (2, 11), (3, 10), (4, 9), (5, 8), (6, 7))}
BRANCH_LIUCHONG = {frozenset(pair) for pair in ((0, 6), (1, 7), (2, 8), (3, 9), (4, 10), (5, 11))}
BRANCH_LIUHAI = {frozenset(pair) for pair in ((0, 7), (1, 6), (2, 5), (3, 4), (8, 11), (9, 10))}
BRANCH_LIUPO = {frozenset(pair) for pair in ((0, 9), (1, 4), (2, 11), (3, 6), (5, 8), (7, 10))}
BRANCH_SANHE = {frozenset(group) for group in ((8, 0, 4), (11, 3, 7), (2, 6, 10), (5, 9, 1))}
BRANCH_SANHUI = {frozenset(group) for group in ((11, 0, 1), (2, 3, 4), (5, 6, 7), (8, 9, 10))}
BRANCH_SANXING = {frozenset(group) for group in ((2, 5, 8), (1, 7, 10))}
BRANCH_PAIR_XING = {frozenset(pair) for pair in ((0, 3),)}
BRANCH_SELF_XING = {4, 6, 9, 11}


def _plain_dataclass(value: object) -> dict[str, object]:
    return json.loads(canonical_json(asdict(value)))


def _record_digest(record_type: str, payload: Mapping[str, object]) -> str:
    body = {key: value for key, value in payload.items() if key not in {"canonical_digest", "canonical_hash"}}
    return digest({"record_type": record_type, "payload": body})


def _data_file(name: str):
    if "/" in name or "\\" in name:
        raise ValueError("data resource name must be a file name")
    return files("mingli.derived.data").joinpath(name)


def _load_json_resource(name: str) -> dict[str, object]:
    value = json.loads(_data_file(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"data resource is not an object: {name}")
    return value


def load_phase7_profiles() -> dict[str, object]:
    return _load_json_resource("phase7_profiles_v0.1.json")


def load_phase7_source_manifest() -> dict[str, object]:
    return _load_json_resource("phase7_source_manifest_v0.1.json")


@dataclass(frozen=True)
class Phase7Profile:
    profile_id: str
    version: str
    convention_summary: str
    source_ids: tuple[str, ...]
    independence_groups: tuple[str, ...]
    reviewed: bool
    applicable_inputs: tuple[str, ...]
    explicit_exclusions: tuple[str, ...]
    unresolved_conditions: tuple[str, ...]
    compatibility_version: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class BoundaryReference:
    boundary_id: str
    term_name: str
    instant_utc: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class ExactDuration:
    source_seconds: int
    source_microseconds: int
    conversion_rule: str
    display_start_age_years: str
    exact_offset_microseconds: int
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class LuckAnchorResult:
    birth_instant_utc: str
    boundary: BoundaryReference
    direction: Literal["forward", "reverse"]
    duration: ExactDuration
    exact_start_instant_utc: str
    calculation_precision: str
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class AgeSnapshot:
    snapshot_id: str
    target_instant_utc: str
    chronological_years: int
    nominal_years: int | None
    nominal_status: Literal["resolved", "omitted", "unresolved"]
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class DaYunPeriod:
    period_id: str
    sequence_index: int
    ganzhi: str
    cycle_index: int
    direction: Literal["forward", "reverse"]
    start_instant_utc: str
    end_instant_utc: str
    interval_rule: str
    start_age: AgeSnapshot
    end_age: AgeSnapshot
    base_month_pillar: str
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class LiuNianPeriod:
    period_id: str
    label_year: int
    ganzhi: str
    cycle_index: int
    start_instant_utc: str
    end_instant_utc: str
    boundary_profile_id: str
    dayun_period_id: str | None
    age_snapshot: AgeSnapshot
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class LuckTimelineResult:
    luck_anchor: LuckAnchorResult
    dayun_periods: tuple[DaYunPeriod, ...]
    liunian_periods: tuple[LiuNianPeriod, ...]
    interval_gaps: int
    interval_overlaps: int

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class GrowthStageFact:
    fact_id: str
    target_stem: str
    target_branch: str
    stage_code: str
    stage_label: str
    direction_convention: str
    profile_id: str
    source_ids: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class RelationFact:
    relation_id: str
    relation_type: str
    participants: tuple[str, ...]
    arity: int
    profile_id: str
    source_ids: tuple[str, ...]
    independence_groups: tuple[str, ...]
    conditions: tuple[str, ...]
    status: tuple[str, ...]
    canonical_digest: str

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


@dataclass(frozen=True)
class BaziFactGraphResult:
    base_chart_ref: Mapping[str, object]
    derived_structure_ref: Mapping[str, object]
    profiles: tuple[Mapping[str, object], ...]
    nodes: tuple[Mapping[str, object], ...]
    edges: tuple[Mapping[str, object], ...]
    timeline: Mapping[str, object]
    relations: tuple[Mapping[str, object], ...]
    growth_stages: tuple[Mapping[str, object], ...]
    provenance_index: Mapping[str, object]
    warnings: tuple[str, ...]
    unresolved: tuple[Mapping[str, object], ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE7_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE7_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE7_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "base_chart_ref": dict(self.base_chart_ref),
            "derived_structure_ref": dict(self.derived_structure_ref),
            "profiles": list(self.profiles),
            "nodes": list(self.nodes),
            "edges": list(self.edges),
            "timeline": dict(self.timeline),
            "relations": list(self.relations),
            "growth_stages": list(self.growth_stages),
            "provenance_index": dict(self.provenance_index),
            "warnings": list(self.warnings),
            "unresolved": list(self.unresolved),
            "canonical_hash": self.canonical_hash,
            "schema_version": self.schema_version,
            "method_id": self.method_id,
            "calculation_version": self.calculation_version,
            "prediction_validity": self.prediction_validity,
        }


@dataclass(frozen=True)
class Phase7BenchmarkResult:
    assertions_total: int
    timeline_assertions: int
    growth_assertions: int
    stem_relation_assertions: int
    branch_relation_assertions: int
    graph_assertions: int
    passed: int
    failed: int
    unresolved: int
    schema_failures: int
    provenance_failures: int
    hash_mismatches: int
    interval_gaps: int
    interval_overlaps: int
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _plain_dataclass(self)


def _profiles() -> tuple[Phase7Profile, ...]:
    manifest = load_phase7_profiles()
    raw_profiles = manifest.get("profiles")
    if not isinstance(raw_profiles, list):
        raise ValueError("phase7 profile manifest requires profiles list")
    profiles: list[Phase7Profile] = []
    required = {
        "profile_id",
        "version",
        "convention_summary",
        "source_ids",
        "independence_groups",
        "reviewed",
        "applicable_inputs",
        "explicit_exclusions",
        "unresolved_conditions",
        "compatibility_version",
    }
    for item in raw_profiles:
        if not isinstance(item, Mapping):
            raise ValueError("phase7 profile entry must be an object")
        missing = sorted(required - set(item))
        if missing:
            raise ValueError(f"phase7 profile missing: {', '.join(missing)}")
        profiles.append(
            Phase7Profile(
                profile_id=str(item["profile_id"]),
                version=str(item["version"]),
                convention_summary=str(item["convention_summary"]),
                source_ids=tuple(str(value) for value in item["source_ids"]),  # type: ignore[index]
                independence_groups=tuple(str(value) for value in item["independence_groups"]),  # type: ignore[index]
                reviewed=bool(item["reviewed"]),
                applicable_inputs=tuple(str(value) for value in item["applicable_inputs"]),  # type: ignore[index]
                explicit_exclusions=tuple(str(value) for value in item["explicit_exclusions"]),  # type: ignore[index]
                unresolved_conditions=tuple(str(value) for value in item["unresolved_conditions"]),  # type: ignore[index]
                compatibility_version=str(item["compatibility_version"]),
            )
        )
    return tuple(sorted(profiles, key=lambda profile: profile.profile_id))


def _profile(profile_id: str) -> Phase7Profile:
    for profile in _profiles():
        if profile.profile_id == profile_id:
            if not profile.reviewed:
                raise ValueError(f"phase7 profile is not reviewed: {profile_id}")
            return profile
    raise ValueError(f"unsupported phase7 profile: {profile_id}")


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"instant must include timezone offset: {value}")
    return parsed.astimezone(UTC)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=value.microsecond).isoformat().replace("+00:00", "Z")


def _sexagenary_index(pillar: str) -> int:
    if pillar not in SEXAGENARY:
        raise ValueError(f"unsupported sexagenary pillar: {pillar}")
    return SEXAGENARY.index(pillar)


def dayun_ganzhi_at(base_month_pillar: str, direction: Literal["forward", "reverse"], sequence_index: int) -> tuple[str, int]:
    if sequence_index < 1:
        raise ValueError("sequence_index must be positive")
    month_index = _sexagenary_index(base_month_pillar)
    step = 1 if direction == "forward" else -1
    cycle_index = (month_index + step * sequence_index) % 60
    return SEXAGENARY[cycle_index], cycle_index


def _stem_index(stem: str) -> int:
    index = STEMS.find(stem)
    if index < 0:
        raise ValueError(f"unsupported stem: {stem}")
    return index


def _branch_index(branch: str) -> int:
    index = BRANCHES.find(branch)
    if index < 0:
        raise ValueError(f"unsupported branch: {branch}")
    return index


def _add_microseconds(moment: datetime, microseconds: int) -> datetime:
    return moment + timedelta(microseconds=microseconds)


def _converted_offset_microseconds(source_microseconds: int) -> int:
    value = Decimal(source_microseconds) * TROPICAL_YEAR_DAYS / Decimal(3)
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def _display_start_age_years(source_microseconds: int) -> str:
    years = Decimal(source_microseconds) / MICROSECONDS_PER_SECOND / SECONDS_PER_DAY / Decimal(3)
    return str(years.quantize(Decimal("0.000001")))


def _make_boundary(term_name: str, instant: datetime) -> BoundaryReference:
    payload = {
        "boundary_id": f"jie:{term_name}:{_iso_utc(instant)}",
        "term_name": term_name,
        "instant_utc": _iso_utc(instant),
        "source_ids": list(SOURCE_IDS),
    }
    return BoundaryReference(
        boundary_id=str(payload["boundary_id"]),
        term_name=term_name,
        instant_utc=str(payload["instant_utc"]),
        source_ids=SOURCE_IDS,
        canonical_digest=_record_digest("BoundaryReference", payload),
    )


def build_luck_anchor(base_chart: Mapping[str, object]) -> LuckAnchorResult:
    _profile("luck-anchor-profile@0.1")
    calendar = base_chart.get("calendar")
    luck = base_chart.get("luck")
    if not isinstance(calendar, Mapping) or not isinstance(luck, Mapping):
        raise ValueError("base chart calendar and luck objects are required")
    birth = _dt(str(calendar.get("input_datetime")))
    boundary = _dt(str(luck.get("adjacent_jie_utc")))
    direction = str(luck.get("direction"))
    if direction not in {"forward", "reverse"}:
        raise ValueError("luck.direction must be forward or reverse")
    delta = abs(boundary - birth)
    source_microseconds = delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
    source_seconds = source_microseconds // 1_000_000
    offset_microseconds = _converted_offset_microseconds(source_microseconds)
    start = _add_microseconds(birth, offset_microseconds)
    duration_payload = {
        "source_seconds": source_seconds,
        "source_microseconds": source_microseconds,
        "conversion_rule": "adjacent_jie_seconds / 86400 / 3 years; exact start offset uses 365.2425-day tropical year",
        "display_start_age_years": _display_start_age_years(source_microseconds),
        "exact_offset_microseconds": offset_microseconds,
    }
    duration = ExactDuration(
        source_seconds=source_seconds,
        source_microseconds=source_microseconds,
        conversion_rule=str(duration_payload["conversion_rule"]),
        display_start_age_years=str(duration_payload["display_start_age_years"]),
        exact_offset_microseconds=offset_microseconds,
        canonical_digest=_record_digest("ExactDuration", duration_payload),
    )
    boundary_ref = _make_boundary(str(luck.get("adjacent_jie")), boundary)
    payload = {
        "birth_instant_utc": _iso_utc(birth),
        "boundary": boundary_ref.to_dict(),
        "direction": direction,
        "duration": duration.to_dict(),
        "exact_start_instant_utc": _iso_utc(start),
        "calculation_precision": "integer microseconds from UTC instants; no binary float public result",
        "profile_id": "luck-anchor-profile@0.1",
        "source_ids": list(SOURCE_IDS),
    }
    return LuckAnchorResult(
        birth_instant_utc=str(payload["birth_instant_utc"]),
        boundary=boundary_ref,
        direction=direction,  # type: ignore[arg-type]
        duration=duration,
        exact_start_instant_utc=str(payload["exact_start_instant_utc"]),
        calculation_precision=str(payload["calculation_precision"]),
        profile_id="luck-anchor-profile@0.1",
        source_ids=SOURCE_IDS,
        canonical_digest=_record_digest("LuckAnchorResult", payload),
    )


def _chronological_years(birth: datetime, target: datetime) -> int:
    birth_local = birth
    target_local = target.astimezone(birth.tzinfo)
    years = target_local.year - birth_local.year
    if (target_local.month, target_local.day, target_local.timetz()) < (birth_local.month, birth_local.day, birth_local.timetz()):
        years -= 1
    return max(years, 0)


def _nominal_age_lunar_new_year(birth: datetime, target: datetime) -> int:
    birth_year = birth.astimezone(UTC).year
    target_year = target.astimezone(UTC).year
    return max(target_year - birth_year + 1, 1)


def _age_snapshot(snapshot_id: str, birth: datetime, target: datetime, *, nominal: bool = True) -> AgeSnapshot:
    nominal_years = _nominal_age_lunar_new_year(birth, target) if nominal else None
    status: Literal["resolved", "omitted", "unresolved"] = "resolved" if nominal else "omitted"
    payload = {
        "snapshot_id": snapshot_id,
        "target_instant_utc": _iso_utc(target),
        "chronological_years": _chronological_years(birth, target),
        "nominal_years": nominal_years,
        "nominal_status": status,
        "profile_id": "age-profile@0.1",
        "source_ids": list(SOURCE_IDS),
    }
    return AgeSnapshot(
        snapshot_id=snapshot_id,
        target_instant_utc=str(payload["target_instant_utc"]),
        chronological_years=int(payload["chronological_years"]),
        nominal_years=nominal_years,
        nominal_status=status,
        profile_id="age-profile@0.1",
        source_ids=SOURCE_IDS,
        canonical_digest=_record_digest("AgeSnapshot", payload),
    )


def build_luck_timeline(
    base_chart: Mapping[str, object],
    *,
    dayun_count: int = DEFAULT_DAYUN_COUNT,
    liunian_start_year: int | None = None,
    liunian_end_year: int | None = None,
) -> LuckTimelineResult:
    for profile_id in ("luck-direction-profile@0.1", "luck-anchor-profile@0.1", "dayun-sequence-profile@0.1", "liunian-boundary-profile@0.1", "age-profile@0.1"):
        _profile(profile_id)
    if dayun_count < 1 or dayun_count > 24:
        raise ValueError("dayun_count must be between 1 and 24")
    pillars = base_chart.get("pillars")
    if not isinstance(pillars, Mapping):
        raise ValueError("base chart pillars object is required")
    month_pillar = str(pillars.get("month"))
    anchor = build_luck_anchor(base_chart)
    birth = _dt(anchor.birth_instant_utc)
    start = _dt(anchor.exact_start_instant_utc)
    decade_microseconds = int((TROPICAL_YEAR_DAYS * Decimal(10) * SECONDS_PER_DAY * MICROSECONDS_PER_SECOND).to_integral_value(rounding=ROUND_FLOOR))
    dayun_periods: list[DaYunPeriod] = []
    for sequence_index in range(1, dayun_count + 1):
        period_start = _add_microseconds(start, decade_microseconds * (sequence_index - 1))
        period_end = _add_microseconds(start, decade_microseconds * sequence_index)
        ganzhi, cycle_index = dayun_ganzhi_at(month_pillar, anchor.direction, sequence_index)
        payload = {
            "period_id": f"dayun:{sequence_index}:{ganzhi}",
            "sequence_index": sequence_index,
            "ganzhi": ganzhi,
            "cycle_index": cycle_index,
            "direction": anchor.direction,
            "start_instant_utc": _iso_utc(period_start),
            "end_instant_utc": _iso_utc(period_end),
            "interval_rule": "[start,end)",
            "start_age": _age_snapshot(f"age:dayun:{sequence_index}:start", birth, period_start).to_dict(),
            "end_age": _age_snapshot(f"age:dayun:{sequence_index}:end", birth, period_end).to_dict(),
            "base_month_pillar": month_pillar,
            "profile_id": "dayun-sequence-profile@0.1",
            "source_ids": list(SOURCE_IDS),
        }
        dayun_periods.append(
            DaYunPeriod(
                period_id=str(payload["period_id"]),
                sequence_index=sequence_index,
                ganzhi=ganzhi,
                cycle_index=cycle_index,
                direction=anchor.direction,
                start_instant_utc=str(payload["start_instant_utc"]),
                end_instant_utc=str(payload["end_instant_utc"]),
                interval_rule="[start,end)",
                start_age=_age_snapshot(f"age:dayun:{sequence_index}:start", birth, period_start),
                end_age=_age_snapshot(f"age:dayun:{sequence_index}:end", birth, period_end),
                base_month_pillar=month_pillar,
                profile_id="dayun-sequence-profile@0.1",
                source_ids=SOURCE_IDS,
                canonical_digest=_record_digest("DaYunPeriod", payload),
            )
        )
    if liunian_start_year is None:
        liunian_start_year = start.year
    if liunian_end_year is None:
        liunian_end_year = liunian_start_year + DEFAULT_LIUNIAN_SPAN - 1
    if liunian_start_year < 1901 or liunian_end_year > 2099 or liunian_start_year > liunian_end_year:
        raise ValueError("liunian year range must be within 1901-2099 and non-empty")
    liunian_periods: list[LiuNianPeriod] = []
    for year in range(liunian_start_year, liunian_end_year + 1):
        period_start = solar_term_utc(year, 315)
        period_end = solar_term_utc(year + 1, 315) if year < 2099 else datetime(2100, 2, 4, tzinfo=UTC)
        cycle_index = (year - 4) % 60
        dayun_id = _find_active_dayun_id(dayun_periods, period_start)
        age = _age_snapshot(f"age:liunian:{year}:start", birth, period_start)
        payload = {
            "period_id": f"liunian:{year}:{SEXAGENARY[cycle_index]}",
            "label_year": year,
            "ganzhi": SEXAGENARY[cycle_index],
            "cycle_index": cycle_index,
            "start_instant_utc": _iso_utc(period_start),
            "end_instant_utc": _iso_utc(period_end),
            "boundary_profile_id": "liunian-boundary-profile@0.1",
            "dayun_period_id": dayun_id,
            "age_snapshot": age.to_dict(),
            "source_ids": list(SOURCE_IDS),
        }
        liunian_periods.append(
            LiuNianPeriod(
                period_id=str(payload["period_id"]),
                label_year=year,
                ganzhi=SEXAGENARY[cycle_index],
                cycle_index=cycle_index,
                start_instant_utc=str(payload["start_instant_utc"]),
                end_instant_utc=str(payload["end_instant_utc"]),
                boundary_profile_id="liunian-boundary-profile@0.1",
                dayun_period_id=dayun_id,
                age_snapshot=age,
                source_ids=SOURCE_IDS,
                canonical_digest=_record_digest("LiuNianPeriod", payload),
            )
        )
    gaps, overlaps = _interval_issues([(period.start_instant_utc, period.end_instant_utc) for period in dayun_periods])
    return LuckTimelineResult(anchor, tuple(dayun_periods), tuple(liunian_periods), gaps, overlaps)


def _find_active_dayun_id(periods: Sequence[DaYunPeriod], instant: datetime) -> str | None:
    for period in periods:
        if _dt(period.start_instant_utc) <= instant < _dt(period.end_instant_utc):
            return period.period_id
    return None


def _interval_issues(intervals: Iterable[tuple[str, str]]) -> tuple[int, int]:
    parsed = sorted((_dt(start), _dt(end)) for start, end in intervals)
    gaps = overlaps = 0
    for previous, current in zip(parsed, parsed[1:]):
        if previous[1] < current[0]:
            gaps += 1
        if previous[1] > current[0]:
            overlaps += 1
    return gaps, overlaps


def growth_stage_for(stem: str, branch: str, *, profile_id: str = "twelve-growth-profile@0.1") -> GrowthStageFact:
    _profile(profile_id)
    stem_index = _stem_index(stem)
    branch_index = _branch_index(branch)
    start = GROWTH_START_BRANCH_INDEX[stem_index]
    direction = 1 if stem_index % 2 == 0 else -1
    stage_index = ((branch_index - start) * direction) % 12
    stage_code = STAGE_CODES[stage_index]
    payload = {
        "fact_id": f"growth:{stem}:{branch}:{profile_id}",
        "target_stem": stem,
        "target_branch": branch,
        "stage_code": stage_code,
        "stage_label": STAGE_LABELS[stage_code],
        "direction_convention": "yang stems advance through branch order; yin stems reverse; earth follows fire storage convention",
        "profile_id": profile_id,
        "source_ids": list(SOURCE_IDS),
    }
    return GrowthStageFact(
        fact_id=str(payload["fact_id"]),
        target_stem=stem,
        target_branch=branch,
        stage_code=stage_code,
        stage_label=STAGE_LABELS[stage_code],
        direction_convention=str(payload["direction_convention"]),
        profile_id=profile_id,
        source_ids=SOURCE_IDS,
        canonical_digest=_record_digest("GrowthStageFact", payload),
    )


def calculate_growth_stages(
    targets: Iterable[tuple[str, str]] | None = None,
    *,
    profile_id: str = "twelve-growth-profile@0.1",
) -> tuple[GrowthStageFact, ...]:
    if targets is None:
        targets = ((stem, branch) for stem in STEMS for branch in BRANCHES)
    return tuple(growth_stage_for(stem, branch, profile_id=profile_id) for stem, branch in targets)


def _relation_payload(relation_type: str, participants: Sequence[str], profile_id: str, conditions: Sequence[str]) -> dict[str, object]:
    ordered = tuple(sorted(participants))
    return {
        "relation_id": f"{relation_type}:{'|'.join(ordered)}:{profile_id}",
        "relation_type": relation_type,
        "participants": list(ordered),
        "arity": len(ordered),
        "profile_id": profile_id,
        "source_ids": list(SOURCE_IDS),
        "independence_groups": list(SOURCE_GROUPS),
        "conditions": list(conditions),
        "status": [
            "relation_detected",
            "combination_complete" if len(ordered) >= 3 else "combination_not_applicable",
            "transformation_not_evaluated",
            "strength_not_evaluated",
            "auspiciousness_not_evaluated",
        ],
    }


def _relation_fact(relation_type: str, participants: Sequence[str], profile_id: str, conditions: Sequence[str]) -> RelationFact:
    payload = _relation_payload(relation_type, participants, profile_id, conditions)
    return RelationFact(
        relation_id=str(payload["relation_id"]),
        relation_type=relation_type,
        participants=tuple(payload["participants"]),  # type: ignore[arg-type]
        arity=int(payload["arity"]),
        profile_id=profile_id,
        source_ids=SOURCE_IDS,
        independence_groups=SOURCE_GROUPS,
        conditions=tuple(payload["conditions"]),  # type: ignore[arg-type]
        status=tuple(payload["status"]),  # type: ignore[arg-type]
        canonical_digest=_record_digest("RelationFact", payload),
    )


def stem_pair_relation(stem_a: str, stem_b: str, *, profile_id: str = "stem-relation-profile@0.1") -> tuple[RelationFact, ...]:
    _profile(profile_id)
    a, b = _stem_index(stem_a), _stem_index(stem_b)
    if a == b:
        return (_relation_fact("same_stem", (stem_a, stem_b), profile_id, ("same visible stem",)),)
    pair = frozenset((a, b))
    facts: list[RelationFact] = []
    if pair in STEM_FIVE_COMBINE:
        facts.append(_relation_fact("stem_five_combine", (stem_a, stem_b), profile_id, ("five-combine pair only; transformation not evaluated",)))
    if pair in STEM_CLASH:
        facts.append(_relation_fact("stem_clash", (stem_a, stem_b), profile_id, ("stem clash pair only; strength not evaluated",)))
    return tuple(facts)


def branch_pair_relation(branch_a: str, branch_b: str, *, profile_id: str = "branch-relation-profile@0.1") -> tuple[RelationFact, ...]:
    _profile(profile_id)
    a, b = _branch_index(branch_a), _branch_index(branch_b)
    if a == b:
        relation_type = "self_punishment" if a in BRANCH_SELF_XING else "same_branch"
        return (_relation_fact(relation_type, (branch_a, branch_b), profile_id, ("same branch structural relation",)),)
    pair = frozenset((a, b))
    facts: list[RelationFact] = []
    if pair in BRANCH_LIUHE:
        facts.append(_relation_fact("branch_six_combine", (branch_a, branch_b), profile_id, ("six-combine pair; transformation not evaluated",)))
    if pair in BRANCH_LIUCHONG:
        facts.append(_relation_fact("branch_six_clash", (branch_a, branch_b), profile_id, ("six-clash pair; effect not evaluated",)))
    if pair in BRANCH_LIUHAI:
        facts.append(_relation_fact("branch_six_harm", (branch_a, branch_b), profile_id, ("six-harm pair; effect not evaluated",)))
    if pair in BRANCH_LIUPO:
        facts.append(_relation_fact("branch_six_break", (branch_a, branch_b), profile_id, ("six-break pair; effect not evaluated",)))
    if pair in BRANCH_PAIR_XING:
        facts.append(_relation_fact("branch_punishment", (branch_a, branch_b), profile_id, ("pair punishment relation; effect not evaluated",)))
    for group in BRANCH_SANHE:
        if pair < group:
            facts.append(_relation_fact("branch_half_combine", (branch_a, branch_b), profile_id, ("two members of a sanhe set; complete combination not claimed",)))
            break
    return tuple(facts)


def branch_triple_relation(branches: Sequence[str], *, profile_id: str = "branch-relation-profile@0.1") -> tuple[RelationFact, ...]:
    _profile(profile_id)
    if len(branches) != 3:
        raise ValueError("branch_triple_relation requires exactly three branches")
    indexes = frozenset(_branch_index(branch) for branch in branches)
    facts: list[RelationFact] = []
    if indexes in BRANCH_SANHE:
        facts.append(_relation_fact("branch_three_combine", branches, profile_id, ("all three sanhe members present; transformation not evaluated",)))
    if indexes in BRANCH_SANHUI:
        facts.append(_relation_fact("branch_three_meeting", branches, profile_id, ("all three sanhui members present; transformation not evaluated",)))
    if indexes in BRANCH_SANXING:
        facts.append(_relation_fact("branch_three_punishment", branches, profile_id, ("all three punishment members present; effect not evaluated",)))
    return tuple(facts)


def _pillars_from_value(value: Mapping[str, object]) -> tuple[tuple[str, str, str], ...]:
    if isinstance(value.get("pillars"), Mapping):
        pillars = value["pillars"]  # type: ignore[index]
        return tuple((position, str(pillars[position])[0], str(pillars[position])[1]) for position in ("year", "month", "day", "hour"))  # type: ignore[index]
    raw_pillars = value.get("pillars")
    if isinstance(raw_pillars, list):
        records: list[tuple[str, str, str]] = []
        for item in raw_pillars:
            if not isinstance(item, Mapping):
                raise ValueError("derived pillar entries must be objects")
            records.append((str(item["position"]), str(item["stem"]), str(item["branch"])))
        return tuple(sorted(records))
    raise ValueError("relations input must contain base or derived pillars")


def detect_structural_relations(value: Mapping[str, object]) -> tuple[RelationFact, ...]:
    pillars = _pillars_from_value(value)
    facts: list[RelationFact] = []
    for left, right in itertools.combinations(pillars, 2):
        left_position, left_stem, left_branch = left
        right_position, right_stem, right_branch = right
        for fact in stem_pair_relation(left_stem, right_stem):
            facts.append(_relation_fact(fact.relation_type, (f"stem:{left_position}:{left_stem}", f"stem:{right_position}:{right_stem}"), fact.profile_id, fact.conditions))
        for fact in branch_pair_relation(left_branch, right_branch):
            facts.append(_relation_fact(fact.relation_type, (f"branch:{left_position}:{left_branch}", f"branch:{right_position}:{right_branch}"), fact.profile_id, fact.conditions))
    for triple in itertools.combinations(pillars, 3):
        branches = tuple(item[2] for item in triple)
        participants = tuple(f"branch:{item[0]}:{item[2]}" for item in triple)
        for fact in branch_triple_relation(branches):
            facts.append(_relation_fact(fact.relation_type, participants, fact.profile_id, fact.conditions))
    return tuple(sorted(facts, key=lambda fact: fact.relation_id))


def _node(node_type: str, node_id: str, **attrs: object) -> dict[str, object]:
    payload = {"node_id": node_id, "node_type": node_type, **attrs}
    payload["canonical_digest"] = _record_digest("GraphNode", payload)
    return payload


def _edge(edge_type: str, source: str, target: str, **attrs: object) -> dict[str, object]:
    payload = {"edge_id": f"{edge_type}:{source}->{target}", "edge_type": edge_type, "source": source, "target": target, **attrs}
    payload["canonical_digest"] = _record_digest("GraphEdge", payload)
    return payload


def _graph_refs(base_chart: Mapping[str, object], derived_chart: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    base_ref = adapt_base_chart(base_chart).to_dict()
    derived_ref = {
        "method_id": str(derived_chart.get("method_id")),
        "calculation_version": str(derived_chart.get("calculation_version")),
        "result_sha256": digest(derived_chart),
        "base_result_sha256": base_ref["base_result_sha256"],
    }
    return base_ref, derived_ref


def build_bazi_fact_graph(
    base_chart: Mapping[str, object],
    *,
    derived_chart: Mapping[str, object] | None = None,
    dayun_count: int = DEFAULT_DAYUN_COUNT,
    liunian_start_year: int | None = None,
    liunian_end_year: int | None = None,
) -> BaziFactGraphResult:
    if derived_chart is None:
        derived_chart = derive_static_chart(base_chart).to_dict()
    timeline = build_luck_timeline(base_chart, dayun_count=dayun_count, liunian_start_year=liunian_start_year, liunian_end_year=liunian_end_year)
    relations = tuple(fact.to_dict() for fact in detect_structural_relations(derived_chart))
    pillars = _pillars_from_value(derived_chart)
    growth_targets = tuple((stem, branch) for _, stem, branch in pillars)
    growth = tuple(fact.to_dict() for fact in calculate_growth_stages(growth_targets))
    base_ref, derived_ref = _graph_refs(base_chart, derived_chart)
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    for position, stem, branch in pillars:
        pillar_id = f"pillar:{position}"
        stem_id = f"stem:{position}:{stem}"
        branch_id = f"branch:{position}:{branch}"
        nodes.extend(
            [
                _node("Pillar", pillar_id, position=position, stem=stem, branch=branch),
                _node("Stem", stem_id, value=stem, position=position),
                _node("Branch", branch_id, value=branch, position=position),
            ]
        )
        edges.extend([_edge("contains", pillar_id, stem_id), _edge("contains", pillar_id, branch_id)])
        hidden = map_hidden_stems(branch, day_master=pillars[2][1])
        for record in hidden:
            hidden_id = f"hidden-stem:{position}:{branch}:{record.ordinal}:{record.stem}"
            ten_god_code = record.ten_god.code if record.ten_god else None
            nodes.append(_node("HiddenStem", hidden_id, stem=record.stem, ordinal=record.ordinal, ten_god=ten_god_code))
            edges.append(_edge("contains", branch_id, hidden_id))
        ten_god = map_ten_god(pillars[2][1], stem)
        ten_god_id = f"ten-god:{position}:{ten_god.code}"
        nodes.append(_node("TenGod", ten_god_id, code=ten_god.code, label=ten_god.label))
        edges.append(_edge("relative_to_day_master", stem_id, ten_god_id))
        pillar_value = stem + branch
        nayin = map_nayin(pillar_value)
        xunkong = map_xunkong(pillar_value)
        nayin_id = f"nayin:{position}:{nayin.code}"
        xunkong_id = f"xunkong:{position}:{xunkong.xun_start}:{'-'.join(xunkong.void_branches)}"
        nodes.append(_node("NaYin", nayin_id, code=nayin.code, label=nayin.label))
        nodes.append(_node("XunKong", xunkong_id, xun_start=xunkong.xun_start, void_branches=list(xunkong.void_branches)))
        edges.extend([_edge("derived_from", pillar_id, nayin_id), _edge("derived_from", pillar_id, xunkong_id)])
    anchor_id = "luck-anchor:primary"
    nodes.append(_node("LuckAnchor", anchor_id, **timeline.luck_anchor.to_dict()))
    for period in timeline.dayun_periods:
        node_id = f"dayun-period:{period.sequence_index}"
        nodes.append(_node("DaYunPeriod", node_id, **period.to_dict()))
        edges.append(_edge("derived_from", anchor_id, node_id))
        for age in (period.start_age, period.end_age):
            age_node_id = f"age-snapshot:{age.snapshot_id}"
            nodes.append(_node("AgeSnapshot", age_node_id, **age.to_dict()))
            edges.append(_edge("active_during", age_node_id, node_id))
        if period.sequence_index > 1:
            edges.append(_edge("follows", f"dayun-period:{period.sequence_index - 1}", node_id))
    for period in timeline.liunian_periods:
        node_id = f"liunian-period:{period.label_year}"
        nodes.append(_node("LiuNianPeriod", node_id, **period.to_dict()))
        age_node_id = f"age-snapshot:{period.age_snapshot.snapshot_id}"
        nodes.append(_node("AgeSnapshot", age_node_id, **period.age_snapshot.to_dict()))
        edges.append(_edge("active_during", age_node_id, node_id))
        if period.dayun_period_id:
            edges.append(_edge("active_during", node_id, f"dayun-period:{period.dayun_period_id.split(':')[1]}"))
    for item in growth:
        node_id = f"growth-stage:{item['target_stem']}:{item['target_branch']}"
        nodes.append(_node("GrowthStage", node_id, **item))
        edges.append(_edge("governed_by_profile", node_id, "profile:twelve-growth-profile@0.1"))
    for item in relations:
        node_id = f"relation:{item['relation_id']}"
        nodes.append(_node("Relation", node_id, **item))
        for participant in item["participants"]:  # type: ignore[index]
            edges.append(_edge("participates_in_relation", str(participant), node_id))
    for profile in _profiles():
        nodes.append(_node("Profile", f"profile:{profile.profile_id}", **profile.to_dict()))
    provenance_index = {
        "source_manifest": load_phase7_source_manifest()["manifest_version"],
        "source_ids": list(SOURCE_IDS),
        "independence_groups": list(SOURCE_GROUPS),
    }
    timeline_payload = timeline.to_dict()
    payload = {
        "base_chart_ref": base_ref,
        "derived_structure_ref": derived_ref,
        "profiles": [profile.to_dict() for profile in _profiles()],
        "nodes": sorted(nodes, key=lambda item: str(item["node_id"])),
        "edges": sorted(edges, key=lambda item: str(item["edge_id"])),
        "timeline": timeline_payload,
        "relations": list(relations),
        "growth_stages": list(growth),
        "provenance_index": provenance_index,
        "warnings": list(base_chart.get("warnings", [])) if isinstance(base_chart.get("warnings", []), list) else [],
        "unresolved": [],
    }
    canonical_hash = _record_digest("BaziFactGraphResult", payload)
    return BaziFactGraphResult(
        base_chart_ref=base_ref,
        derived_structure_ref=derived_ref,
        profiles=tuple(payload["profiles"]),  # type: ignore[arg-type]
        nodes=tuple(payload["nodes"]),  # type: ignore[arg-type]
        edges=tuple(payload["edges"]),  # type: ignore[arg-type]
        timeline=timeline_payload,
        relations=tuple(relations),
        growth_stages=tuple(growth),
        provenance_index=provenance_index,
        warnings=tuple(payload["warnings"]),  # type: ignore[arg-type]
        unresolved=(),
        canonical_hash=canonical_hash,
    )


def _sample_base_input(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "birth_date": "2000-01-07",
        "birth_time": "12:00",
        "timezone": "+08:00",
        "gender": "male",
        "calendar": "solar",
        "longitude": 121.4737,
        "latitude": 31.2304,
        "true_solar_time": False,
    }
    value.update(overrides)
    return value


def _direction_fixtures() -> tuple[dict[str, object], ...]:
    return (
        _sample_base_input(birth_date="2024-07-15", gender="male"),
        _sample_base_input(birth_date="2024-07-15", gender="female"),
        _sample_base_input(birth_date="2023-07-15", gender="male"),
        _sample_base_input(birth_date="2023-07-15", gender="female"),
    )


def _assert(condition: bool, failures: list[str], message: str) -> int:
    if condition:
        return 1
    failures.append(message)
    return 0


def validate_phase7_profiles() -> tuple[str, ...]:
    issues: list[str] = []
    required_ids = {
        "luck-direction-profile@0.1",
        "luck-anchor-profile@0.1",
        "dayun-sequence-profile@0.1",
        "liunian-boundary-profile@0.1",
        "age-profile@0.1",
        "twelve-growth-profile@0.1",
        "stem-relation-profile@0.1",
        "branch-relation-profile@0.1",
    }
    profiles = _profiles()
    seen = {profile.profile_id for profile in profiles}
    for profile_id in sorted(required_ids - seen):
        issues.append(f"missing profile: {profile_id}")
    for profile in profiles:
        if len(set(profile.independence_groups)) < 2:
            issues.append(f"{profile.profile_id}: requires at least two independence groups")
        if not profile.reviewed:
            issues.append(f"{profile.profile_id}: profile is not reviewed")
        if not profile.explicit_exclusions:
            issues.append(f"{profile.profile_id}: explicit exclusions are required")
    return tuple(issues)


def benchmark_phase7() -> Phase7BenchmarkResult:
    failures: list[str] = []
    passed = timeline_assertions = growth_assertions = stem_relation_assertions = branch_relation_assertions = graph_assertions = 0
    schema_failures = provenance_failures = hash_mismatches = interval_gaps = interval_overlaps = unresolved = 0
    profile_issues = validate_phase7_profiles()
    if profile_issues:
        failures.extend(profile_issues)
        schema_failures += len(profile_issues)
    engine = DeterministicBaziEngine()
    for fixture in _direction_fixtures():
        base = engine.calculate(fixture)
        expected_forward = (base["pillars"]["year"][0] in (STEMS[0], STEMS[2], STEMS[4], STEMS[6], STEMS[8]) and fixture["gender"] == "male") or (
            base["pillars"]["year"][0] in (STEMS[1], STEMS[3], STEMS[5], STEMS[7], STEMS[9]) and fixture["gender"] == "female"
        )
        expected = "forward" if expected_forward else "reverse"
        timeline_assertions += 1
        passed += _assert(base["luck"]["direction"] == expected, failures, f"luck direction mismatch for {fixture}")
        timeline = build_luck_timeline(base)
        timeline_assertions += 2
        interval_gaps += timeline.interval_gaps
        interval_overlaps += timeline.interval_overlaps
        passed += _assert(timeline.interval_gaps == 0, failures, "dayun interval gap")
        passed += _assert(timeline.interval_overlaps == 0, failures, "dayun interval overlap")
        display = Decimal(timeline.luck_anchor.duration.display_start_age_years)
        phase5_display = Decimal(str(base["luck"]["start_age_years"])).quantize(Decimal("0.000001"))
        timeline_assertions += 1
        passed += _assert(abs(display - phase5_display) <= Decimal("0.000001"), failures, "phase5 start_age display mismatch")
    for month_index, month_pillar in enumerate(SEXAGENARY):
        forward, forward_index = dayun_ganzhi_at(month_pillar, "forward", 1)
        reverse, reverse_index = dayun_ganzhi_at(month_pillar, "reverse", 1)
        timeline_assertions += 2
        passed += _assert(forward == SEXAGENARY[(month_index + 1) % 60] and forward_index == (month_index + 1) % 60, failures, f"forward dayun mismatch for {month_pillar}")
        passed += _assert(reverse == SEXAGENARY[(month_index - 1) % 60] and reverse_index == (month_index - 1) % 60, failures, f"reverse dayun mismatch for {month_pillar}")
    for stem in STEMS:
        for branch in BRANCHES:
            fact = growth_stage_for(stem, branch)
            growth_assertions += 1
            passed += _assert(fact.stage_code in STAGE_CODES and bool(fact.source_ids), failures, f"growth invalid {stem}{branch}")
    for left in STEMS:
        for right in STEMS:
            facts = stem_pair_relation(left, right)
            stem_relation_assertions += 1
            passed += _assert(all("auspiciousness_not_evaluated" in fact.status for fact in facts), failures, f"stem relation status invalid {left}{right}")
    for left in BRANCHES:
        for right in BRANCHES:
            facts = branch_pair_relation(left, right)
            branch_relation_assertions += 1
            passed += _assert(all("auspiciousness_not_evaluated" in fact.status for fact in facts), failures, f"branch relation status invalid {left}{right}")
    for triple in itertools.combinations(BRANCHES, 3):
        facts = branch_triple_relation(triple)
        branch_relation_assertions += 1
        passed += _assert(all("combination_complete" in fact.status and "transformation_not_evaluated" in fact.status for fact in facts), failures, f"branch triple status invalid {triple}")
    base = engine.calculate(_sample_base_input())
    graph = build_bazi_fact_graph(base)
    payload = graph.to_dict()
    required_node_types = {
        "Pillar",
        "Stem",
        "Branch",
        "HiddenStem",
        "TenGod",
        "NaYin",
        "XunKong",
        "LuckAnchor",
        "DaYunPeriod",
        "LiuNianPeriod",
        "AgeSnapshot",
        "GrowthStage",
        "Relation",
    }
    present = {str(node["node_type"]) for node in payload["nodes"]}  # type: ignore[index]
    graph_assertions += len(required_node_types) + 3
    for node_type in required_node_types:
        passed += _assert(node_type in present, failures, f"missing graph node type {node_type}")
    repeated = build_bazi_fact_graph(json.loads(json.dumps(base, ensure_ascii=False, sort_keys=True))).canonical_hash
    passed += _assert(repeated == graph.canonical_hash, failures, "graph hash changed after key reorder")
    passed += _assert(payload["prediction_validity"] == "not_evaluated", failures, "prediction validity changed")
    passed += _assert(all("source_ids" in item and item["source_ids"] for item in payload["relations"]), failures, "relation provenance missing")
    provenance_failures += 0 if all("source_ids" in item and item["source_ids"] for item in payload["relations"]) else 1
    hash_mismatches += 0 if repeated == graph.canonical_hash else 1
    assertions_total = timeline_assertions + growth_assertions + stem_relation_assertions + branch_relation_assertions + graph_assertions
    failed = len(failures)
    return Phase7BenchmarkResult(
        assertions_total=assertions_total,
        timeline_assertions=timeline_assertions,
        growth_assertions=growth_assertions,
        stem_relation_assertions=stem_relation_assertions,
        branch_relation_assertions=branch_relation_assertions,
        graph_assertions=graph_assertions,
        passed=passed,
        failed=failed,
        unresolved=unresolved,
        schema_failures=schema_failures,
        provenance_failures=provenance_failures,
        hash_mismatches=hash_mismatches,
        interval_gaps=interval_gaps,
        interval_overlaps=interval_overlaps,
        failures=tuple(failures),
    )


def load_phase7_assertion_summary() -> dict[str, object]:
    return benchmark_phase7().to_dict()


def phase7_schema_summary() -> dict[str, object]:
    return {
        "schemas": {
            "BaziFactGraphResult": PHASE7_SCHEMA_VERSION,
            "LuckAnchorResult": "phase7-luck-anchor-result@0.1",
            "LuckTimelineResult": "phase7-luck-timeline-result@0.1",
            "GrowthStageFact": "phase7-growth-stage-fact@0.1",
            "RelationFact": "phase7-relation-fact@0.1",
        },
        "profile_manifest": load_phase7_profiles()["manifest_version"],
        "source_manifest": load_phase7_source_manifest()["manifest_version"],
    }


def build_base_chart_from_input(chart_input: Mapping[str, object]) -> Mapping[str, object]:
    return DeterministicBaziEngine().calculate(chart_input)


def read_json_file(path: Path | str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))
