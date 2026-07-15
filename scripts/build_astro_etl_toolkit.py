#!/usr/bin/env python3
"""Assemble a deterministic Astro ETL delivery bundle with a hash manifest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Sequence
import uuid
import zipfile


_COMMIT_PATTERN = re.compile(r"[0-9a-fA-F]{40}\Z")
_MANIFEST_NAME = "MANIFEST.json"


def _validated_archive_name(name: str, seen: set[str]) -> str:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or path.as_posix() != name
        or any(part in {"", ".", ".."} for part in path.parts)
        or name == _MANIFEST_NAME
        or name in seen
    ):
        raise ValueError(f"unsafe or duplicate archive path: {name!r}")
    seen.add(name)
    return name


def _zip_datetime(source_date_epoch: int) -> tuple[int, int, int, int, int, int]:
    if isinstance(source_date_epoch, bool) or source_date_epoch < 0:
        raise ValueError("source_date_epoch must be a non-negative integer")
    instant = datetime.fromtimestamp(source_date_epoch, timezone.utc)
    if not 1980 <= instant.year <= 2107:
        raise ValueError("source_date_epoch is outside the ZIP timestamp range")
    return instant.timetuple()[:6]


def _zip_info(name: str, timestamp: tuple[int, int, int, int, int, int]) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=timestamp)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    return info


def build_toolkit(
    output: Path,
    entries: Sequence[tuple[str, Path]],
    *,
    source_commit: str,
    source_date_epoch: int,
) -> dict[str, object]:
    """Write a byte-stable ZIP and return the embedded manifest."""

    if not _COMMIT_PATTERN.fullmatch(source_commit):
        raise ValueError("source_commit must be a full 40-character hexadecimal hash")
    timestamp = _zip_datetime(source_date_epoch)
    seen: set[str] = set()
    payloads: list[tuple[str, bytes]] = []
    for archive_name, source in entries:
        name = _validated_archive_name(archive_name, seen)
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        payloads.append((name, source_path.read_bytes()))
    payloads.sort(key=lambda item: item[0])

    manifest: dict[str, object] = {
        "manifest_version": 1,
        "product_release_status": "HOLD",
        "source_commit": source_commit.lower(),
        "source_date_epoch": source_date_epoch,
        "files": [
            {
                "path": name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
            for name, payload in payloads
        ],
    }
    manifest_payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    all_payloads = [(_MANIFEST_NAME, manifest_payload), *payloads]
    all_payloads.sort(key=lambda item: item[0])

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f".{output_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with zipfile.ZipFile(temporary_path, mode="w") as archive:
            for name, payload in all_payloads:
                archive.writestr(_zip_info(name, timestamp), payload)
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return manifest


def _entry(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("entry must use ARCHIVE_PATH=SOURCE_PATH")
    archive_name, source = value.split("=", 1)
    return archive_name, Path(source)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic Astro ETL toolkit ZIP."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    parser.add_argument(
        "--entry",
        type=_entry,
        action="append",
        required=True,
        help="repeatable ARCHIVE_PATH=SOURCE_PATH mapping",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    build_toolkit(
        arguments.output,
        arguments.entry,
        source_commit=arguments.source_commit,
        source_date_epoch=arguments.source_date_epoch,
    )
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
