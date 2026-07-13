from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Literal, Mapping, Sequence

from .contracts.serialization import canonical_json, digest

PHASE21_SCHEMA_VERSION = "five-year-bounded-outlook@0.1"
PHASE21_METHOD_ID = "five-year-evidence-bounded-generator@0.1.0"
PHASE21_CALCULATION_VERSION = "0.1.0"
PHASE21_DECISION_ID = "PHASE_21_FIVE_YEAR_GENERATION_BOUNDARY_GATE_R1_APPROVED"
DOMAINS = ("career", "wealth", "relationship")
STATUSES = ("supportive", "mixed", "challenging", "unresolved")
FORBIDDEN_EVENT_FIELDS = frozenset({"event", "event_date", "guarantee", "income_amount", "admission_result", "reunion_result", "marriage_date"})


class Phase21InputError(ValueError):
    pass


@dataclass(frozen=True)
class YearOutlook:
    year: int
    status: str
    domain_statuses: Mapping[str, str]
    evidence_ids: tuple[str, ...]
    unresolved_domains: tuple[str, ...]
    boundary_code: str = field(default="trend_only_no_concrete_event", init=False)


@dataclass(frozen=True)
class FiveYearOutlookResult:
    anchor_year: int
    range_start: int
    range_end: int
    years: tuple[YearOutlook, ...]
    evidence_index: tuple[Mapping[str, object], ...]
    warnings: tuple[str, ...]
    canonical_hash: str
    schema_version: str = field(default=PHASE21_SCHEMA_VERSION, init=False)
    method_id: str = field(default=PHASE21_METHOD_ID, init=False)
    calculation_version: str = field(default=PHASE21_CALCULATION_VERSION, init=False)
    prediction_validity: Literal["not_evaluated"] = field(default="not_evaluated", init=False)

    def to_dict(self) -> dict[str, object]:
        return json.loads(canonical_json(asdict(self)))


def _controlled_status(value: object) -> str:
    status = str(value or "unresolved")
    if status not in STATUSES:
        raise Phase21InputError(f"unsupported status: {status}")
    return status


def _score_to_status(score: int | None) -> str:
    if score is None:
        return "unresolved"
    if score >= 2:
        return "supportive"
    if score <= -2:
        return "challenging"
    return "mixed"


def generate_five_year_outlook(raw: Mapping[str, object]) -> FiveYearOutlookResult:
    if not isinstance(raw, Mapping):
        raise Phase21InputError("input must be an object")
    anchor = raw.get("anchor_year")
    if isinstance(anchor, bool) or not isinstance(anchor, int) or not 1901 <= anchor <= 2097:
        raise Phase21InputError("anchor_year must be an integer between 1901 and 2097")
    baseline = raw.get("baseline_domains")
    evidence = raw.get("annual_evidence", [])
    if not isinstance(baseline, Mapping) or not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)):
        raise Phase21InputError("baseline_domains object and annual_evidence array are required")
    baseline_status = {domain: _controlled_status(baseline.get(domain)) for domain in DOMAINS}
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    allowed_years = set(range(anchor - 2, anchor + 3))
    for index, item in enumerate(evidence, 1):
        if not isinstance(item, Mapping):
            raise Phase21InputError("annual evidence must contain objects")
        forbidden = FORBIDDEN_EVENT_FIELDS.intersection(item)
        if forbidden:
            raise Phase21InputError(f"concrete event fields are forbidden: {sorted(forbidden)}")
        evidence_id = str(item.get("evidence_id", ""))
        if not evidence_id:
            raise Phase21InputError("annual evidence_id is required")
        if evidence_id in seen:
            raise Phase21InputError(f"duplicate evidence_id: {evidence_id}")
        seen.add(evidence_id)
        year, domain = item.get("year"), str(item.get("domain"))
        if isinstance(year, bool) or not isinstance(year, int) or year not in allowed_years or domain not in DOMAINS:
            raise Phase21InputError("annual evidence year/domain is outside the five-year contract")
        signal = item.get("signal")
        if isinstance(signal, bool) or not isinstance(signal, int) or not -2 <= signal <= 2:
            raise Phase21InputError("signal must be an integer from -2 to 2")
        reality = item.get("verified_reality")
        if reality not in {None, "support", "contradict"}:
            raise Phase21InputError("verified_reality must be support, contradict or null")
        source_type = str(item.get("source_type", ""))
        source_id = str(item.get("source_id", ""))
        verified = item.get("verified") is True
        if source_type not in {"rule", "timing", "reality"} or not source_id:
            raise Phase21InputError("annual evidence source_type and source_id are required")
        if reality is not None and (source_type != "reality" or not verified):
            raise Phase21InputError("verified_reality requires a verified reality source")
        record = {"evidence_id": evidence_id, "year": year, "domain": domain, "signal": signal, "verified_reality": reality, "source_type": source_type, "source_id": source_id, "verified": verified}
        record["canonical_digest"] = digest({"record_type":"AnnualEvidence","payload":record})
        records.append(record)
    base_score = {"supportive": 1, "mixed": 0, "challenging": -1, "unresolved": None}
    years: list[YearOutlook] = []
    for year in sorted(allowed_years):
        statuses: dict[str, str] = {}
        evidence_ids: list[str] = []
        for domain in DOMAINS:
            group = [record for record in records if record["year"] == year and record["domain"] == domain]
            evidence_ids.extend(str(record["evidence_id"]) for record in group)
            reality = {str(record["verified_reality"]) for record in group if record["verified_reality"] is not None}
            if len(reality) > 1:
                statuses[domain] = "unresolved"
            elif reality == {"support"}:
                statuses[domain] = "supportive"
            elif reality == {"contradict"}:
                statuses[domain] = "challenging"
            else:
                base = base_score[baseline_status[domain]]
                statuses[domain] = _score_to_status(None if base is None and not group else (base or 0) + sum(int(record["signal"]) for record in group))
        resolved_scores = [{"supportive": 1, "mixed": 0, "challenging": -1}[status] for status in statuses.values() if status != "unresolved"]
        overall = _score_to_status(None if not resolved_scores else sum(resolved_scores))
        years.append(YearOutlook(year, overall, statuses, tuple(sorted(evidence_ids)), tuple(domain for domain in DOMAINS if statuses[domain] == "unresolved")))
    body = {"anchor_year": anchor, "range_start": anchor - 2, "range_end": anchor + 2, "years": [asdict(item) for item in years], "evidence_index":records, "warnings": ["trend_only_no_concrete_event", "verified_reality_override_is_year_and_domain_scoped", "not_a_guarantee"]}
    return FiveYearOutlookResult(anchor, anchor - 2, anchor + 2, tuple(years), tuple(records), tuple(body["warnings"]), digest({"record_type": "FiveYearOutlookResult", "payload": body}))


def renderer_years(result: FiveYearOutlookResult) -> list[dict[str, object]]:
    return [{"year": item.year, "status": item.status} for item in result.years]


def benchmark_phase21() -> dict[str, object]:
    payload = {"anchor_year": 2028, "baseline_domains": {"career": "mixed", "wealth": "challenging", "relationship": "unresolved"}, "annual_evidence": [{"evidence_id": "c26", "year": 2026, "domain": "career", "signal": 2,"source_type":"timing","source_id":"phase14"}, {"evidence_id": "r27", "year": 2027, "domain": "relationship", "signal": 0, "verified_reality": "contradict","source_type":"reality","source_id":"confirmed","verified":True}, {"evidence_id": "w30", "year": 2030, "domain": "wealth", "signal": 2,"source_type":"rule","source_id":"phase16"}]}
    result = generate_five_year_outlook(payload)
    by_year = {item.year: item for item in result.years}
    checks = [(len(result.years) == 5, "five_years"), ([item.year for item in result.years] == [2026, 2027, 2028, 2029, 2030], "range"), (by_year[2026].domain_statuses["career"] == "supportive", "signal"), (by_year[2027].domain_statuses["relationship"] == "challenging", "reality_override"), (by_year[2030].domain_statuses["wealth"] == "mixed", "baseline_plus_signal"), (all(item.boundary_code == "trend_only_no_concrete_event" for item in result.years), "boundary"), (result.canonical_hash == generate_five_year_outlook(json.loads(json.dumps(payload))).canonical_hash, "determinism"), (result.prediction_validity == "not_evaluated", "prediction_validity")]
    failures = [name for ok, name in checks if not ok]
    return {"assertions_total": len(checks), "passed": len(checks) - len(failures), "failed": len(failures), "unresolved": 0, "failures": failures}
