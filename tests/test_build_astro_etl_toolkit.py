from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_astro_etl_toolkit import build_toolkit


class BuildToolkitTests(unittest.TestCase):
    def test_equivalent_inputs_produce_byte_identical_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_source = root / "first.txt"
            second_source = root / "second.txt"
            first_source.write_bytes(b"first\n")
            second_source.write_bytes(b"second\n")
            first_source.touch()
            first = root / "first.zip"
            second = root / "second.zip"
            entries = [
                ("docs/second.txt", second_source),
                ("first.txt", first_source),
            ]

            build_toolkit(
                first,
                entries,
                source_commit="a" * 40,
                source_date_epoch=1_700_000_000,
            )
            build_toolkit(
                second,
                list(reversed(entries)),
                source_commit="a" * 40,
                source_date_epoch=1_700_000_000,
            )

            self.assertEqual(
                hashlib.sha256(first.read_bytes()).digest(),
                hashlib.sha256(second.read_bytes()).digest(),
            )

    def test_manifest_hashes_every_payload_and_records_release_hold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "payload.bin"
            payload.write_bytes(b"payload")
            output = root / "toolkit.zip"

            manifest = build_toolkit(
                output,
                [("payload.bin", payload)],
                source_commit="b" * 40,
                source_date_epoch=1_700_000_000,
            )

            self.assertEqual(manifest["source_commit"], "b" * 40)
            self.assertEqual(manifest["product_release_status"], "HOLD")
            self.assertEqual(
                manifest["files"],
                [
                    {
                        "path": "payload.bin",
                        "sha256": hashlib.sha256(b"payload").hexdigest(),
                        "size": 7,
                    }
                ],
            )
            with zipfile.ZipFile(output) as archive:
                stored = json.loads(archive.read("MANIFEST.json"))
                self.assertEqual(stored, manifest)
                self.assertIsNone(archive.testzip())
                self.assertEqual(
                    archive.namelist(),
                    ["MANIFEST.json", "payload.bin"],
                )
                self.assertTrue(
                    all(
                        item.compress_type == zipfile.ZIP_STORED
                        for item in archive.infolist()
                    )
                )

    def test_rejects_duplicate_or_unsafe_archive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "payload"
            payload.write_bytes(b"payload")

            invalid_entries = [
                [("same", payload), ("same", payload)],
                [("../outside", payload)],
                [("/absolute", payload)],
                [("MANIFEST.json", payload)],
                [("windows\\path", payload)],
            ]
            for entries in invalid_entries:
                with self.subTest(entries=entries):
                    with self.assertRaises(ValueError):
                        build_toolkit(
                            root / "invalid.zip",
                            entries,
                            source_commit="c" * 40,
                            source_date_epoch=1_700_000_000,
                        )

    def test_rejects_missing_payload_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                build_toolkit(
                    root / "toolkit.zip",
                    [("missing", root / "missing")],
                    source_commit="d" * 40,
                    source_date_epoch=1_700_000_000,
                )


if __name__ == "__main__":
    unittest.main()
