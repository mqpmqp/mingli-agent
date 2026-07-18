"""Boundaries for the user-attested, retrospective Luming pilot corpus."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
CASES = ROOT / "research/luming-historical-corpus-v1/cases.jsonl"
RULES = ROOT / "research/luming-historical-corpus-v1/candidate-rules.jsonl"
SOURCE = ROOT / "knowledge/sources/luming-bazi-casebook-v1.json"
SELECTED = {1, 11, 21, 31, 41, 51, 61, 71, 81, 91, 101, 111}
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_source_registration_is_authorized_but_not_validation_evidence():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert source["source_id"] == "luming-bazi-casebook-v1"
    assert source["copyright_authorization_status"] == "AUTHORIZED"
    assert source["authorization_basis"] == "USER_ATTESTED"
    assert source["allowed_use"] == ["INTERNAL_RESEARCH", "COMMERCIAL_TRAINING"]
    assert source["verification_level"] == "unverified_retrospective"
    assert source["prediction_validity"] == "not_evaluated"
    assert source["commercial_validation_eligible"] is False
    assert source["release_hold_evidence"] is False
    assert source["raw_file_in_git"] is False
    assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
    assert source["page_count"] == 240


def test_fixed_sample_has_exactly_twelve_cases_and_traceability():
    cases = read_jsonl(CASES)
    assert {case["source_case_number"] for case in cases} == SELECTED
    assert len(cases) == len(SELECTED)
    assert len({case["case_id"] for case in cases}) == 12
    for case in cases:
        assert case["source_id"] == "luming-bazi-casebook-v1"
        assert case["source_pages"] and all(page >= 1 for page in case["source_pages"])
        assert case["commercial_validation_eligible"] is False
        assert case["release_hold_evidence"] is False
        assert case["verification_level"] == "unverified_retrospective"
        assert case["prediction_validity"] == "not_evaluated"
        assert case["extraction_status"] in {"completed", "uncertain", "blocked"}


def test_claim_types_remain_separate_and_are_not_long_quotations():
    cases = read_jsonl(CASES)
    for case in cases:
        assert set(case) >= {"reported_outcomes", "author_claims", "student_hypotheses", "rule_candidates"}
        assert all(isinstance(case[key], list) for key in ("reported_outcomes", "author_claims", "student_hypotheses"))
        for key in ("reported_outcomes", "author_claims", "student_hypotheses"):
            assert all(len(item) < 100 for item in case[key])


def test_chart_fields_are_legal_or_explicitly_missing_and_uncertain_is_not_high():
    for case in read_jsonl(CASES):
        for pillar, value in case["chart"].items():
            assert value is None or (len(value) == 2 and value[0] in GAN and value[1] in ZHI), (case["case_id"], pillar, value)
            if case["chart_field_confidence"][pillar] == "low":
                assert case["chart_field_confidence"][pillar] != "high"
        assert all(confidence in {"high", "medium", "low"} for confidence in case["chart_field_confidence"].values())


def test_high_risk_cases_are_isolated():
    for case in read_jsonl(CASES):
        if "health" in case["safety_flags"]:
            assert "high_stakes_unverified" in case["safety_flags"]
            assert case["commercial_validation_eligible"] is False
            assert case["release_hold_evidence"] is False


def test_rules_are_draft_low_confidence_and_single_case_only():
    rules = read_jsonl(RULES)
    assert len(rules) == 12
    assert all(rule["status"] == "draft" and rule["confidence"] == "low" for rule in rules)
    assert all(rule["support_count"] == 1 for rule in rules)
    assert all(len(rule["source_case_ids"]) == 1 for rule in rules)
    assert all(rule["safety_class"] in {"ordinary_unverified", "high_stakes_unverified"} for rule in rules)


def test_repository_contains_no_raw_source_or_private_paths():
    forbidden_suffixes = {".pdf", ".png", ".jpg", ".jpeg"}
    forbidden = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/|微信|手机|邮箱|联系(?:方式|电话))", re.IGNORECASE)
    paths = [CASES, RULES, SOURCE]
    for path in paths:
        assert path.suffix.lower() not in forbidden_suffixes, path
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not forbidden.search(text), path
