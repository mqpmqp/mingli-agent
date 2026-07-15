from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from mingli.validation_astro_etl import (
    AstroTransformError,
    local_mean_solar_time,
    transform_astro_record,
)
from mingli.validation_intake import validate_intake
from mingli.validation_privacy import scan_for_pii
from mingli.validation_cli import main as validation_main


def authorized_record() -> dict[str, object]:
    return {
        "source_record_id": "astro-databank:synthetic-001",
        "name": "Synthetic Example",
        "gender": "female",
        "birth_datetime_utc": "1990-03-15T02:30:00Z",
        "birth_timezone": "Asia/Taipei",
        "birth_longitude": 121.5654,
        "birth_location_precision": "city",
        "birth_source": "participant_confirmed",
        "birth_confirmation_status": "confirmed",
        "consent": {
            "consent_status": "granted",
            "consent_scope": ["research", "benchmark"],
            "consent_recorded_at": "2026-01-01T00:00:00Z",
            "consent_record_ref": "consent:irreversible:synthetic-001",
            "withdrawal_supported": True,
            "research_use_allowed": True,
            "benchmark_use_allowed": True,
            "publication_use_allowed": False,
            "raw_data_retention_policy": "controlled_off_git",
        },
        "case_metadata": {
            "collection_channel": "authorized_private_intake",
            "collector_role": "case-coordinator",
            "created_at": "2026-01-01T00:00:00Z",
            "source_provenance": "participant_direct",
            "conflict_status": "none",
            "completeness_status": "complete",
        },
        "scenarios": [
            {
                "scenario_id": "scenario:career:synthetic-001",
                "scenario_type": "career_exam",
                "target_period": "2026",
                "question_scope": "exam_stage_trend",
                "known_at_prediction_time": True,
                "excluded_future_information": [],
            }
        ],
    }


class AstroEtlTests(unittest.TestCase):
    def test_authorized_record_becomes_valid_pseudonymous_intake(self):
        raw = authorized_record()

        transformed = transform_astro_record(
            raw,
            project_salt="test-only-project-salt",
        )

        self.assertEqual("1990-03-15", transformed["birth_input"]["birth_date"])
        self.assertEqual("10:30", transformed["birth_input"]["birth_time"])
        self.assertFalse(transformed["birth_input"]["true_solar_time"])
        self.assertEqual(
            "1990-03-15T10:36:15.696000+08:06:15.696000",
            transformed["birth_input"]["local_mean_solar_time"],
        )
        self.assertTrue(str(transformed["person_case_id"]).startswith("person:"))
        self.assertNotIn(raw["name"], json.dumps(transformed, ensure_ascii=False))
        self.assertNotIn(raw["source_record_id"], json.dumps(transformed, ensure_ascii=False))
        self.assertFalse(scan_for_pii(transformed))
        self.assertNotIn("intake_canonical_hash", transformed)
        self.assertIn("intake_canonical_hash", validate_intake(transformed))

    def test_public_biography_without_explicit_consent_fails_closed(self):
        raw = authorized_record()
        raw.pop("consent")
        raw["consent_type"] = "public_domain_historical"

        with self.assertRaisesRegex(AstroTransformError, "explicit consent"):
            transform_astro_record(raw, project_salt="test-only-project-salt")

    def test_retrospective_events_are_never_registered_as_scenarios(self):
        raw = authorized_record()
        raw["events"] = [
            {"year": 2020, "type": "Promotion", "description": "known outcome"}
        ]

        with self.assertRaisesRegex(AstroTransformError, "retrospective events"):
            transform_astro_record(raw, project_salt="test-only-project-salt")

    def test_local_mean_solar_time_rejects_invalid_inputs(self):
        with self.assertRaisesRegex(AstroTransformError, "longitude"):
            local_mean_solar_time("1990-03-15T02:30:00Z", 181)
        with self.assertRaisesRegex(AstroTransformError, "UTC"):
            local_mean_solar_time("1990-03-15T02:30:00+08:00", 121.5)

    def test_salt_never_appears_in_serialized_output(self):
        salt = "test-only-project-salt"
        transformed = transform_astro_record(authorized_record(), project_salt=salt)
        self.assertNotIn(salt, json.dumps(transformed, ensure_ascii=False))

    def test_cli_dry_run_validates_without_writing_to_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "authorized-record.json"
            salt_path = root / "project-salt.txt"
            store = root / "controlled-store"
            raw_path.write_text(
                json.dumps(authorized_record(), ensure_ascii=False),
                encoding="utf-8",
            )
            salt_path.write_text("test-only-project-salt\n", encoding="utf-8")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = validation_main(
                    [
                        "astro-intake",
                        "--file",
                        str(raw_path),
                        "--store",
                        str(store),
                        "--source-ref",
                        "authorized:test",
                        "--project-salt-file",
                        str(salt_path),
                        "--dry-run",
                    ]
                )

            self.assertEqual(0, exit_code)
            report = json.loads(stdout.getvalue())
            self.assertEqual(1, report["validated"])
            self.assertEqual(0, report["imported"])
            self.assertFalse(store.exists())


if __name__ == "__main__":
    unittest.main()
