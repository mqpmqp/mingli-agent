from __future__ import annotations

from typing import Mapping, Sequence

from jsonschema import Draft202012Validator

from .contracts import get_schema

CLASSIFICATIONS = ("hit", "partial_hit", "unverifiable", "wrong")


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


__all__ = ["summarize_ziwei_cases"]
