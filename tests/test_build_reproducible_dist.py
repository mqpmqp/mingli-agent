from __future__ import annotations

import gzip
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

from scripts.build_reproducible_dist import build_distribution, normalize_sdist


def _write_unstable_sdist(
    path: Path,
    *,
    gzip_mtime: int,
    member_mtime: int,
    reverse: bool,
) -> None:
    members = [
        ("example-1.0/README.md", b"example\n"),
        ("example-1.0/src/example/__init__.py", b"VALUE = 1\n"),
    ]
    if reverse:
        members.reverse()

    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=gzip_mtime) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                for name, payload in members:
                    info = tarfile.TarInfo(name)
                    info.size = len(payload)
                    info.mtime = member_mtime
                    info.uid = 1001
                    info.gid = 1002
                    info.uname = "builder"
                    info.gname = "builders"
                    info.pax_headers = {
                        "mtime": f"{member_mtime}.25",
                        "atime": f"{member_mtime + 1}.5",
                    }
                    archive.addfile(info, io.BytesIO(payload))


class NormalizeSdistTests(unittest.TestCase):
    def test_equivalent_archives_become_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.tar.gz"
            second = root / "second.tar.gz"
            _write_unstable_sdist(
                first,
                gzip_mtime=100,
                member_mtime=200,
                reverse=False,
            )
            _write_unstable_sdist(
                second,
                gzip_mtime=300,
                member_mtime=400,
                reverse=True,
            )

            normalize_sdist(first, source_date_epoch=1_700_000_000)
            normalize_sdist(second, source_date_epoch=1_700_000_000)

            self.assertEqual(
                hashlib.sha256(first.read_bytes()).digest(),
                hashlib.sha256(second.read_bytes()).digest(),
            )

    def test_normalization_preserves_content_and_canonicalizes_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "package.tar.gz"
            epoch = 1_700_000_000
            _write_unstable_sdist(
                archive_path,
                gzip_mtime=123,
                member_mtime=456,
                reverse=True,
            )

            normalize_sdist(archive_path, source_date_epoch=epoch)

            header = archive_path.read_bytes()[:10]
            self.assertEqual(int.from_bytes(header[4:8], "little"), epoch)
            with tarfile.open(archive_path, "r:gz") as archive:
                members = archive.getmembers()
                self.assertEqual([member.name for member in members], sorted(member.name for member in members))
                self.assertTrue(all(member.mtime == epoch for member in members))
                self.assertTrue(all(member.uid == 0 and member.gid == 0 for member in members))
                self.assertTrue(all(not member.uname and not member.gname for member in members))
                self.assertTrue(all("atime" not in member.pax_headers for member in members))
                readme = archive.extractfile("example-1.0/README.md")
                self.assertIsNotNone(readme)
                assert readme is not None
                self.assertEqual(readme.read(), b"example\n")

    def test_rejects_epoch_outside_gzip_range(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "package.tar.gz"
            _write_unstable_sdist(
                archive_path,
                gzip_mtime=1,
                member_mtime=2,
                reverse=False,
            )

            with self.assertRaisesRegex(ValueError, "source_date_epoch"):
                normalize_sdist(archive_path, source_date_epoch=-1)


class BuildDistributionTests(unittest.TestCase):
    def test_build_sets_reproducible_environment_and_normalizes_sdist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            output = root / "dist"
            source.mkdir()
            sdist = output / "example-1.0.tar.gz"

            def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                output.mkdir(parents=True, exist_ok=True)
                _write_unstable_sdist(
                    sdist,
                    gzip_mtime=10,
                    member_mtime=20,
                    reverse=False,
                )
                return subprocess.CompletedProcess(command, 0)

            with mock.patch("scripts.build_reproducible_dist.subprocess.run", side_effect=fake_run) as run:
                artifacts = build_distribution(
                    source,
                    output,
                    source_date_epoch=1_700_000_000,
                    python_executable="python-test",
                    no_isolation=True,
                )

            command = run.call_args.args[0]
            environment = run.call_args.kwargs["env"]
            self.assertEqual(command[:3], ["python-test", "-m", "build"])
            self.assertIn("--no-isolation", command)
            self.assertEqual(environment["SOURCE_DATE_EPOCH"], "1700000000")
            self.assertEqual(environment["PYTHONHASHSEED"], "0")
            self.assertEqual(artifacts, [sdist])
            self.assertEqual(
                int.from_bytes(sdist.read_bytes()[4:8], "little"),
                1_700_000_000,
            )


if __name__ == "__main__":
    unittest.main()
