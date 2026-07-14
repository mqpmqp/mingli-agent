from __future__ import annotations

import base64
import gzip
import unittest
from pathlib import Path


class Phase7PatchExportTests(unittest.TestCase):
    def test_export_surgically_patched_phase7_source(self) -> None:
        path = Path(__file__).resolve().parents[1] / "src" / "mingli" / "phase7.py"
        source = path.read_text(encoding="utf-8")
        anchor = (
            "    pillars = _pillars_from_value(derived_chart)\n"
            "    growth_targets = tuple((stem, branch) for _, stem, branch in pillars)\n"
        )
        replacement = (
            "    pillars = _pillars_from_value(derived_chart)\n"
            "    day_masters = [stem for position, stem, _branch in pillars if position == \"day\"]\n"
            "    if len(day_masters) != 1:\n"
            "        raise ValueError(\"derived pillars must contain exactly one day pillar\")\n"
            "    day_master = day_masters[0]\n"
            "    growth_targets = tuple((stem, branch) for _, stem, branch in pillars)\n"
        )
        self.assertEqual(1, source.count(anchor))
        source = source.replace(anchor, replacement)
        replacements = {
            "map_hidden_stems(branch, day_master=pillars[2][1])": "map_hidden_stems(branch, day_master=day_master)",
            "map_ten_god(pillars[2][1], stem)": "map_ten_god(day_master, stem)",
        }
        for old, new in replacements.items():
            self.assertEqual(1, source.count(old), old)
            source = source.replace(old, new)
        self.assertNotIn("pillars[2][1]", source)
        encoded = base64.b64encode(gzip.compress(source.encode("utf-8"), compresslevel=9)).decode("ascii")
        print(f"PHASE7_PATCH_GZIP_B64={encoded}", flush=True)
        self.fail("PHASE7_PATCH_EXPORT_COMPLETE")


if __name__ == "__main__":
    unittest.main()
