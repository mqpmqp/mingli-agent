#!/usr/bin/env python3
"""Build Python distributions and canonicalize sdist archive metadata."""

from __future__ import annotations

import argparse
import copy
import gzip
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid


_MAX_GZIP_MTIME = (1 << 32) - 1


def _validated_epoch(source_date_epoch: int) -> int:
    if isinstance(source_date_epoch, bool) or not 0 <= source_date_epoch <= _MAX_GZIP_MTIME:
        raise ValueError(
            f"source_date_epoch must be between 0 and {_MAX_GZIP_MTIME}"
        )
    return source_date_epoch


def _canonical_member(member: tarfile.TarInfo, epoch: int) -> tarfile.TarInfo:
    canonical = copy.copy(member)
    canonical.mtime = epoch
    canonical.uid = 0
    canonical.gid = 0
    canonical.uname = ""
    canonical.gname = ""
    canonical.pax_headers = {}
    if canonical.isdir():
        canonical.mode = 0o755
    elif canonical.isfile():
        canonical.mode = 0o755 if member.mode & 0o111 else 0o644
    elif canonical.issym() or canonical.islnk():
        canonical.mode = 0o777
    return canonical


def normalize_sdist(path: Path, *, source_date_epoch: int) -> None:
    """Rewrite a ``.tar.gz`` sdist with deterministic order and metadata."""

    epoch = _validated_epoch(source_date_epoch)
    archive_path = Path(path)
    temporary_path = archive_path.with_name(
        f".{archive_path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        with tarfile.open(archive_path, "r:gz") as source:
            members = sorted(source.getmembers(), key=lambda item: item.name)
            with temporary_path.open("wb") as raw_output:
                with gzip.GzipFile(
                    filename="",
                    mode="wb",
                    compresslevel=9,
                    fileobj=raw_output,
                    mtime=epoch,
                ) as compressed_output:
                    with tarfile.open(
                        fileobj=compressed_output,
                        mode="w",
                        format=tarfile.PAX_FORMAT,
                    ) as target:
                        for member in members:
                            canonical = _canonical_member(member, epoch)
                            payload = source.extractfile(member) if member.isfile() else None
                            try:
                                target.addfile(canonical, payload)
                            finally:
                                if payload is not None:
                                    payload.close()
        os.replace(temporary_path, archive_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def build_distribution(
    source: Path,
    output: Path,
    *,
    source_date_epoch: int,
    python_executable: str = sys.executable,
    no_isolation: bool = False,
) -> list[Path]:
    """Build wheel/sdist artifacts and normalize every generated sdist."""

    epoch = _validated_epoch(source_date_epoch)
    source_path = Path(source).resolve()
    output_path = Path(output).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    existing = sorted(
        path
        for path in output_path.iterdir()
        if path.is_file()
        and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    )
    if existing:
        names = ", ".join(path.name for path in existing)
        raise FileExistsError(f"output directory already contains artifacts: {names}")

    command = [python_executable, "-m", "build"]
    if no_isolation:
        command.append("--no-isolation")
    command.extend(["--outdir", str(output_path), str(source_path)])
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = str(epoch)
    environment["PYTHONHASHSEED"] = "0"
    subprocess.run(command, check=True, env=environment)

    artifacts = sorted(
        path
        for path in output_path.iterdir()
        if path.is_file()
        and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    )
    if not artifacts:
        raise RuntimeError("build produced no wheel or sdist artifacts")
    for artifact in artifacts:
        if artifact.name.endswith(".tar.gz"):
            normalize_sdist(artifact, source_date_epoch=epoch)
    return artifacts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build deterministic wheel and sdist artifacts."
    )
    parser.add_argument("source", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--outdir", type=Path, default=Path("dist-reproducible"))
    parser.add_argument(
        "--source-date-epoch",
        type=int,
        default=os.environ.get("SOURCE_DATE_EPOCH"),
        required="SOURCE_DATE_EPOCH" not in os.environ,
        help="canonical Unix timestamp; defaults to SOURCE_DATE_EPOCH",
    )
    parser.add_argument(
        "--no-isolation",
        action="store_true",
        help="reuse the current environment instead of creating a build environment",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    artifacts = build_distribution(
        arguments.source,
        arguments.outdir,
        source_date_epoch=arguments.source_date_epoch,
        no_isolation=arguments.no_isolation,
    )
    for artifact in artifacts:
        print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
