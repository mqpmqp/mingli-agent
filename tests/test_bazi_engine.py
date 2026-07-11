from __future__ import annotations

import unittest
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from mingli.bazi import (
    CONVENTIONS,
    METHOD_ID,
    DeterministicBaziEngine,
    benchmark_charts,
    solar_term_utc,
    validate_benchmarks,
)
from mingli.errors import ChartCalculationError


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "tests/fixtures/bazi_independent_benchmarks_v0.1.jsonl"


def chart_input(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "gender": "male",
        "calendar": "solar",
        "birth_date": "2000-01-07",
        "birth_time": "12:00",
        "timezone": "Asia/Shanghai",
        "longitude": 121.4737,
        "latitude": 31.2304,
        "true_solar_time": False,
    }
    value.update(overrides)
    return value


class DeterministicBaziEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DeterministicBaziEngine()

    def test_result_has_method_conventions_and_no_prediction_claim(self) -> None:
        result = self.engine.calculate(chart_input())

        self.assertEqual(METHOD_ID, result["method_id"])
        self.assertEqual(CONVENTIONS, result["conventions"])
        self.assertEqual("not_evaluated", result["prediction_validity"])
        self.assertEqual(
            {"year": "己卯", "month": "丁丑", "day": "甲子", "hour": "庚午"},
            result["pillars"],
        )

    def test_midnight_boundary_and_no_early_late_zi_split(self) -> None:
        before = self.engine.calculate(chart_input(birth_time="23:00"))["pillars"]
        after = self.engine.calculate(chart_input(birth_date="2000-01-08", birth_time="00:00"))["pillars"]

        self.assertEqual(("甲子", "甲子"), (before["day"], before["hour"]))
        self.assertEqual(("乙丑", "丙子"), (after["day"], after["hour"]))

    def test_valid_leap_month_converts_and_invalid_leap_month_fails(self) -> None:
        valid = self.engine.calculate(
            chart_input(calendar="lunar", birth_date="2023-02-01", is_leap_month=True)
        )
        self.assertEqual("2023-03-22", valid["calendar"]["solar_date"])

        with self.assertRaises(ChartCalculationError) as raised:
            self.engine.calculate(chart_input(calendar="lunar", birth_date="2024-02-01", is_leap_month=True))
        self.assertEqual("INVALID_LEAP_MONTH", raised.exception.code)

    def test_true_solar_time_requires_longitude_and_can_cross_hour(self) -> None:
        with self.assertRaises(ChartCalculationError) as raised:
            self.engine.calculate(chart_input(longitude=None, true_solar_time=True))
        self.assertEqual("MISSING_LONGITUDE", raised.exception.code)

        result = self.engine.calculate(
            chart_input(
                birth_date="2024-06-18",
                birth_time="01:30",
                longitude=104.0665,
                latitude=30.5728,
                true_solar_time=True,
            )
        )
        self.assertTrue(result["calendar"]["true_solar_time_applied"])
        self.assertLess(result["calendar"]["true_solar_correction_minutes"], -60)
        self.assertEqual("子", result["pillars"]["hour"][1])

    def test_supported_range_and_solar_term_uncertainty_fail_explicitly(self) -> None:
        for year in (1900, 2100):
            with self.subTest(year=year), self.assertRaises(ChartCalculationError) as raised:
                self.engine.calculate(chart_input(birth_date=f"{year}-07-15"))
            self.assertEqual("UNSUPPORTED_YEAR", raised.exception.code)

        local = solar_term_utc(2024, 315).astimezone(ZoneInfo("Asia/Shanghai")) + timedelta(minutes=1)
        with self.assertRaises(ChartCalculationError) as raised:
            self.engine.calculate(
                chart_input(birth_date=local.date().isoformat(), birth_time=local.time().replace(microsecond=0).isoformat())
            )
        self.assertEqual("SOLAR_TERM_UNCERTAIN", raised.exception.code)


class IndependentBenchmarkTests(unittest.TestCase):
    def test_strict_contract_and_independent_results(self) -> None:
        self.assertEqual((), validate_benchmarks(BENCHMARKS, strict=True))

        result = benchmark_charts(BENCHMARKS, independent_only=True)

        self.assertEqual(52, result.total)
        self.assertEqual(52, result.independent)
        self.assertEqual(51, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(1, result.unresolved)
        self.assertEqual(1.0, result.source_agreement)
        self.assertEqual(24, result.categories["solar_term_boundary"]["passed"])
        self.assertEqual(4, result.categories["day_boundary"]["passed"])
        self.assertEqual(3, result.categories["lunar_leap_month"]["passed"])
        self.assertEqual(4, result.categories["true_solar_time"]["passed"])


if __name__ == "__main__":
    unittest.main()
