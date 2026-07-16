from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from typing import Mapping, Sequence

MANIFEST_NAME = "mingli_core_capability_surge_v2.json"
MANIFEST_SCHEMA_VERSION = "mingli-contract-freeze-manifest@2.0"
REQUIRED_GROUPS = (
    "benchmark",
    "case",
    "chart",
    "evidence",
    "renderer",
    "rule",
    "runtime",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class ContractFreezeManifestError(ValueError):
    """Raised when a freeze manifest is malformed or unsafe."""


@dataclass(frozen=True)
class ContractViolation:
    group: str
    path: str
    reason: str
    expected_sha256: str | None = None
    actual_sha256: str | None = None


@dataclass(frozen=True)
class ContractFreezeReport:
    baseline_sha: str
    checked_count: int
    groups: tuple[str, ...]
    violations: tuple[ContractViolation, ...]

    @property
    def ok(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "mingli-contract-freeze-report@2.0",
            "baseline_sha": self.baseline_sha,
            "checked_count": self.checked_count,
            "groups": list(self.groups),
            "violations": [asdict(item) for item in self.violations],
            "ok": self.ok,
        }

    def raise_for_violations(self) -> None:
        if self.violations:
            details = ", ".join(
                f"{item.group}:{item.path}:{item.reason}"
                for item in self.violations
            )
            raise RuntimeError(f"frozen contract verification failed: {details}")


def default_manifest_path() -> Path:
    return Path(__file__).with_name("frozen") / MANIFEST_NAME


def _validate_entry(group: str, value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ContractFreezeManifestError(f"{group} entry must be an object")
    path = value.get("path")
    digest = value.get("sha256")
    if not isinstance(path, str) or not path:
        raise ContractFreezeManifestError(f"{group} entry path is required")
    pure = PurePosixPath(path)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or "." in pure.parts
        or "\\" in path
        or pure.as_posix() != path
    ):
        raise ContractFreezeManifestError(
            f"{group} path must be a safe repository-relative POSIX path: {path}"
        )
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ContractFreezeManifestError(
            f"{group}:{path} sha256 must be 64 lowercase hex characters"
        )
    return {"path": path, "sha256": digest}


def load_contract_manifest(path: Path | str | None = None) -> dict[str, object]:
    source = Path(path) if path is not None else default_manifest_path()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractFreezeManifestError(
            f"cannot read contract freeze manifest: {source}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise ContractFreezeManifestError("contract freeze manifest must be an object")
    if raw.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ContractFreezeManifestError("unsupported contract freeze schema_version")
    baseline = raw.get("baseline_sha")
    if not isinstance(baseline, str) or not _GIT_SHA.fullmatch(baseline):
        raise ContractFreezeManifestError("baseline_sha must be a full lowercase Git SHA")
    groups = raw.get("groups")
    if not isinstance(groups, Mapping) or set(groups) != set(REQUIRED_GROUPS):
        raise ContractFreezeManifestError(
            "contract freeze groups must exactly match the seven public groups"
        )

    normalized_groups: dict[str, list[dict[str, str]]] = {}
    seen: set[str] = set()
    for group in REQUIRED_GROUPS:
        entries = groups[group]
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            raise ContractFreezeManifestError(f"{group} entries must be an array")
        if not entries:
            raise ContractFreezeManifestError(f"{group} entries must not be empty")
        normalized: list[dict[str, str]] = []
        for item in entries:
            entry = _validate_entry(group, item)
            if entry["path"] in seen:
                raise ContractFreezeManifestError(
                    f"frozen contract path is duplicated: {entry['path']}"
                )
            seen.add(entry["path"])
            normalized.append(entry)
        normalized_groups[group] = normalized

    result = dict(raw)
    result["groups"] = normalized_groups
    return result


def verify_frozen_contracts(
    repository_root: Path | str,
    manifest_path: Path | str | None = None,
) -> ContractFreezeReport:
    root = Path(repository_root).resolve()
    manifest = load_contract_manifest(manifest_path)
    groups = manifest["groups"]
    assert isinstance(groups, Mapping)

    violations: list[ContractViolation] = []
    checked = 0
    for group in REQUIRED_GROUPS:
        entries = groups[group]
        assert isinstance(entries, Sequence)
        for raw in entries:
            assert isinstance(raw, Mapping)
            relative = PurePosixPath(str(raw["path"]))
            expected = str(raw["sha256"])
            checked += 1
            target = root.joinpath(*relative.parts)
            if not target.is_file():
                violations.append(
                    ContractViolation(group, relative.as_posix(), "missing", expected)
                )
                continue
            actual = sha256(target.read_bytes()).hexdigest()
            if actual != expected:
                violations.append(
                    ContractViolation(
                        group,
                        relative.as_posix(),
                        "sha256_mismatch",
                        expected,
                        actual,
                    )
                )

    return ContractFreezeReport(
        baseline_sha=str(manifest["baseline_sha"]),
        checked_count=checked,
        groups=tuple(sorted(groups)),
        violations=tuple(violations),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mingli-contract-freeze")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    report = verify_frozen_contracts(args.root, args.manifest)
    print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
