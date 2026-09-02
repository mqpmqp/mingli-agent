from __future__ import annotations

import unittest

from mingli.bazi import DeterministicBaziEngine
from mingli.derived.static_engine import map_hidden_stems, map_ten_god
from mingli.phase7 import build_bazi_fact_graph
from mingli.phase9_engine import calculate_day_master_strength
from mingli.phase10_engine import evaluate_bazi_pattern


def _base_chart() -> dict[str, object]:
    return DeterministicBaziEngine().calculate(
        {
            "birth_date": "2000-01-07",
            "birth_time": "12:00",
            "timezone": "Asia/Shanghai",
            "gender": "male",
            "calendar": "solar",
            "longitude": 121.4737,
            "latitude": 31.2304,
            "true_solar_time": False,
        }
    )


def _derived_chart_with_list_pillars() -> dict[str, object]:
    return {
        "method_id": "phase7-day-master-regression-fixture",
        "calculation_version": "1",
        "pillars": [
            {"position": "year", "stem": "甲", "branch": "子"},
            {"position": "month", "stem": "丙", "branch": "寅"},
            {"position": "day", "stem": "辛", "branch": "酉"},
            {"position": "hour", "stem": "壬", "branch": "辰"},
        ],
    }


class Phase7DayMasterRegressionTests(unittest.TestCase):
    def _graph(self) -> dict[str, object]:
        return build_bazi_fact_graph(
            _base_chart(),
            derived_chart=_derived_chart_with_list_pillars(),
            dayun_count=1,
            liunian_start_year=2006,
            liunian_end_year=2006,
        ).to_dict()

    def test_visible_and_hidden_ten_gods_use_day_position(self) -> None:
        graph = self._graph()
        nodes = list(graph["nodes"])
        day_master = "辛"
        pillars = (
            ("year", "甲", "子"),
            ("month", "丙", "寅"),
            ("day", "辛", "酉"),
            ("hour", "壬", "辰"),
        )

        for position, stem, branch in pillars:
            with self.subTest(position=position, kind="visible"):
                visible = [
                    node
                    for node in nodes
                    if node.get("node_type") == "TenGod"
                    and str(node.get("node_id", "")).startswith(f"ten-god:{position}:")
                ]
                self.assertEqual(1, len(visible))
                self.assertEqual(map_ten_god(day_master, stem).code, visible[0]["code"])

            with self.subTest(position=position, kind="hidden"):
                actual = sorted(
                    (
                        node
                        for node in nodes
                        if node.get("node_type") == "HiddenStem"
                        and str(node.get("node_id", "")).startswith(f"hidden-stem:{position}:{branch}:")
                    ),
                    key=lambda node: int(node["ordinal"]),
                )
                expected = map_hidden_stems(branch, day_master=day_master)
                self.assertEqual(
                    [(item.stem, item.ordinal, item.ten_god.code) for item in expected],
                    [(item["stem"], item["ordinal"], item["ten_god"]) for item in actual],
                )

    def test_real_phase7_graph_passes_phase9_and_phase10_contracts(self) -> None:
        graph = self._graph()
        strength = calculate_day_master_strength(graph).to_dict()
        pattern = evaluate_bazi_pattern(graph, strength)

        self.assertEqual("辛", strength["day_master"])
        self.assertTrue(pattern.candidates)
        self.assertEqual(graph["canonical_hash"], pattern.fact_graph_hash)


if __name__ == "__main__":
    unittest.main()
