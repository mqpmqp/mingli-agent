from __future__ import annotations

from pathlib import Path

from scripts.build_pwa_runtime import collect_parity_cases, load_runtime_lock


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_lock_pins_browser_dependencies_and_sha256() -> None:
    lock = load_runtime_lock(ROOT)

    assert lock["pyodide"]["version"] == "0.25.1"
    assert lock["pyodide"]["python_version"].startswith("3.11.")
    assert lock["tzdata"]["version"] == "2025.2"
    for dependency in ("pyodide", "tzdata"):
        digest = lock[dependency]["sha256"]
        assert len(digest) == 64
        assert digest == digest.lower()


def test_parity_cases_reuse_all_benchmarks_and_cover_required_boundaries() -> None:
    cases = collect_parity_cases(ROOT)

    assert len(cases) >= 100
    assert len({case["id"] for case in cases}) == len(cases)
    benchmark_ids = {
        line.split('"id": "', 1)[1].split('"', 1)[0]
        for line in (ROOT / "tests/fixtures/bazi_independent_benchmarks_v0.1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    }
    assert benchmark_ids <= {case["source_id"] for case in cases}
    categories = {case["category"] for case in cases}
    assert {
        "solar",
        "lunar",
        "leap_month",
        "true_solar_hour_crossing",
        "true_solar_day_crossing",
        "lichun_boundary",
        "month_term_boundary",
        "zi_hour",
        "day_boundary",
        "longitude",
        "historical_timezone",
        "error",
    } <= categories
