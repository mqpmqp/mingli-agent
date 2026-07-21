from __future__ import annotations

from mingli.derived.static_engine import BRANCHES, STEMS
from mingli.phase15 import build_phase15_fixture
import mingli.phase15 as phase15


def test_phase15_fixture_cache_reuses_deterministic_input_without_shared_mutation() -> None:
    phase15.clear_phase15_fixture_cache()

    first = build_phase15_fixture(STEMS[0], BRANCHES[0])
    first[0]["nodes"].clear()  # type: ignore[index]
    second = build_phase15_fixture(STEMS[0], BRANCHES[0])

    assert second[0]["nodes"]
    info = phase15.phase15_fixture_cache_info()
    assert info.hits >= 1
    assert info.currsize == 1
