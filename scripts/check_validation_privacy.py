from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tarfile
import zipfile

from mingli.validation_privacy import scan_for_pii


FORBIDDEN_ARCHIVE_TOKENS = (
    "validation/intake/", "validation/predictions/", "validation/reality_evidence/",
    "validation/reviews/", "validation/adjudications/", "consent_document", "raw_case",
)


def scan_json(path: Path) -> list[str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"{path}: unreadable JSON: {exc}"]
    return [f"{path}:{item.field_path}:{item.code}" for item in scan_for_pii(value)]


def scan_archive(path: Path) -> list[str]:
    failures: list[str] = []
    if path.suffix == ".whl" or path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                normalized = member.replace("\\", "/").lower()
                if any(token in normalized for token in FORBIDDEN_ARCHIVE_TOKENS):
                    failures.append(f"{path}: forbidden packaged member: {member}")
                if "verse" in normalized or "歌诀" in normalized:
                    failures.append(f"{path}: chenggu verse asset forbidden: {member}")
                if normalized.endswith(".json"):
                    try:
                        value = json.loads(archive.read(member).decode("utf-8"))
                        failures.extend(f"{path}:{member}:{item.field_path}:{item.code}" for item in scan_for_pii(value))
                    except (UnicodeError, json.JSONDecodeError) as exc:
                        failures.append(f"{path}:{member}: unreadable JSON: {exc}")
    if path.name.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        with tarfile.open(path) as archive:
            for item in archive.getmembers():
                normalized = item.name.replace("\\", "/").lower()
                if any(token in normalized for token in FORBIDDEN_ARCHIVE_TOKENS):
                    failures.append(f"{path}: forbidden packaged member: {item.name}")
                if "verse" in normalized or "歌诀" in normalized:
                    failures.append(f"{path}: chenggu verse asset forbidden: {item.name}")
                if normalized.endswith(".json") and item.isfile():
                    stream = archive.extractfile(item)
                    try:
                        value = json.loads(stream.read().decode("utf-8") if stream else "")
                        failures.extend(f"{path}:{item.name}:{finding.field_path}:{finding.code}" for finding in scan_for_pii(value))
                    except (UnicodeError, json.JSONDecodeError) as exc:
                        failures.append(f"{path}:{item.name}: unreadable JSON: {exc}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("validation"), Path("validation_dataset_manifest.json"), Path("product_release_authorization.json")])
    parser.add_argument("--archives", type=Path)
    args = parser.parse_args()
    failures: list[str] = []
    for root in args.paths:
        candidates = sorted(root.rglob("*.json")) if root.is_dir() else ([root] if root.suffix == ".json" else [])
        for candidate in candidates:
            failures.extend(scan_json(candidate))
    if args.archives and args.archives.exists():
        for archive in sorted(args.archives.iterdir()):
            if not archive.is_file():
                continue
            failures.extend(scan_archive(archive))
    print(json.dumps({"passed": not failures, "failures": failures}, ensure_ascii=False, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
