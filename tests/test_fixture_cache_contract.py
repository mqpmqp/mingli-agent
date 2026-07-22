from __future__ import annotations

from mingli.derived.static_engine import BRANCHES, STEMS
from mingli.phase16 import (
    build_phase16_fixture,
    clear_phase16_evaluation_cache,
    evaluate_base_domain_contracts,
    phase16_evaluation_cache_info,
)
from mingli.phase15 import build_phase15_fixture
import mingli.phase15 as phase15
import mingli.phase16 as phase16
from concurrent.futures import ThreadPoolExecutor

import pytest


def test_phase15_fixture_cache_reuses_deterministic_input_without_shared_mutation() -> None:
    phase15.clear_phase15_fixture_cache()

    first = build_phase15_fixture(STEMS[0], BRANCHES[0])
    first[0]["nodes"].clear()  # type: ignore[index]
    second = build_phase15_fixture(STEMS[0], BRANCHES[0])

    assert second[0]["nodes"]
    info = phase15.phase15_fixture_cache_info()
    assert info.hits >= 1
    assert info.currsize == 1


def test_phase16_evaluator_cache_returns_isolated_deterministic_results() -> None:
    clear_phase16_evaluation_cache()
    source = build_phase16_fixture(STEMS[0], BRANCHES[0])
    first = evaluate_base_domain_contracts(source)
    first.domain_index["mutated"] = ()  # type: ignore[index]
    second = evaluate_base_domain_contracts(source)

    assert "mutated" not in second.domain_index
    assert first.canonical_hash == second.canonical_hash


def test_phase16_evaluation_cache_is_bounded_and_does_not_cache_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(phase16, "_EVALUATION_CACHE_LIMIT", 2)
    clear_phase16_evaluation_cache()

    for day_stem in STEMS[:3]:
        evaluate_base_domain_contracts(build_phase16_fixture(day_stem, BRANCHES[0]))

    info = phase16_evaluation_cache_info()
    assert info["size"] == 2
    assert info["limit"] == 2
    with pytest.raises(Exception, match="cannot return concrete events"):
        evaluate_base_domain_contracts(
            build_phase16_fixture(STEMS[0], BRANCHES[0]),
            requested_outputs=("event_prediction",),
        )
    assert phase16_evaluation_cache_info()["size"] == 2


def test_phase16_evaluation_cache_is_concurrency_safe_and_keys_requested_outputs() -> None:
    clear_phase16_evaluation_cache()
    source = build_phase16_fixture(STEMS[0], BRANCHES[0])

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: evaluate_base_domain_contracts(source), range(24)))

    assert {result.canonical_hash for result in results} == {results[0].canonical_hash}
    assert phase16_evaluation_cache_info()["size"] == 1
    evaluate_base_domain_contracts(source, requested_outputs=("domain_contracts",))
    assert phase16_evaluation_cache_info()["size"] == 2
