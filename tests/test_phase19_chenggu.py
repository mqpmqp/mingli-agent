from __future__ import annotations
from importlib.resources import files
import unittest
from mingli.phase19 import Phase19InputError, benchmark_phase19, calculate_chenggu, load_chenggu_table, solar_to_lunar

class Phase19Tests(unittest.TestCase):
    def test_benchmark(self):
        result = benchmark_phase19(); self.assertEqual(result["assertions_total"], result["passed"]); self.assertEqual(0, result["failed"])

    def test_integer_qian_and_components(self):
        result = calculate_chenggu({"calendar": "lunar", "birth_date": "1984-01-01", "birth_time": "00:00"})
        self.assertEqual(39, result.total_qian); self.assertEqual(39, sum(result.components_qian.values())); self.assertFalse(result.verse_available)

    def test_roundtrip_and_leap_convention(self):
        lunar = solar_to_lunar(__import__("datetime").date(1990, 3, 15)); self.assertEqual((1990, 2, 19, False), (lunar.year, lunar.month, lunar.day, lunar.is_leap_month))
        leap = calculate_chenggu({"calendar": "lunar", "birth_date": "2020-04-01", "birth_time": "12:00", "is_leap_month": True})
        regular = calculate_chenggu({"calendar": "lunar", "birth_date": "2020-04-01", "birth_time": "12:00"})
        self.assertEqual(regular.components_qian["month"], leap.components_qian["month"]); self.assertIn("leap_month_uses_same_numeric_month_weight", leap.warnings)

    def test_invalid_input(self):
        with self.assertRaises(Phase19InputError): calculate_chenggu({"calendar": "solar", "birth_date": "2020-01-01", "birth_time": "24:00"})
        with self.assertRaises(Phase19InputError): calculate_chenggu({"calendar": "solar", "birth_date": "2020-01-01", "birth_time": "12:00", "is_leap_month": True})

    def test_core_package_contains_no_verse_pack(self):
        table = load_chenggu_table()
        self.assertEqual(
            {"schema_version", "table_id", "unit", "year_weights", "month_weights", "day_weights", "hour_weights", "source"},
            set(table),
        )
        resource_names = {entry.name.lower() for entry in files("mingli.derived.data").iterdir() if entry.is_file()}
        self.assertFalse(any("verse" in name or "歌诀" in name for name in resource_names))

if __name__ == "__main__": unittest.main()
