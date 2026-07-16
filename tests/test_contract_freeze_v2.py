from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import shutil

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    REPO_ROOT
    / "src"
    / "mingli"
    / "contracts"
    / "frozen"
    / "mingli_core_capability_surge_v2.json"
)
BASELINE_SHA = "00eeaad66a2a36684ae2ad0b5b0074fcdf700640"
GROUPS = {
    "chart",
    "rule",
    "evidence",
    "case",
    "benchmark",
    "runtime",
    "renderer",
}


def _copy_frozen_tree(target: Path) -> dict[str, object]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for entries in manifest["groups"].values():
        for entry in entries:
            relative = PurePosixPath(entry["path"])
            destination = target.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT.joinpath(*relative.parts), destination)
    return manifest


def test_contract_freeze_verifies_merged_main_baseline() -> None:
    from mingli.contracts.freeze import verify_frozen_contracts

    report = verify_frozen_contracts(REPO_ROOT)

    assert report.ok, report.to_dict()
    assert report.baseline_sha == BASELINE_SHA
    assert report.checked_count >= 70
    assert report.groups == tuple(sorted(GROUPS))


def test_contract_freeze_detects_raw_byte_tampering(tmp_path: Path) -> None:
    from mingli.contracts.freeze import verify_frozen_contracts

    manifest = _copy_frozen_tree(tmp_path)
    first = next(iter(manifest["groups"]["chart"]))
    target = tmp_path.joinpath(*PurePosixPath(first["path"]).parts)
    target.write_bytes(target.read_bytes() + b"\n# tampered\n")

    report = verify_frozen_contracts(tmp_path, MANIFEST_PATH)

    assert not report.ok
    assert any(
        item.path == first["path"] and item.reason == "sha256_mismatch"
        for item in report.violations
    )


def test_contract_freeze_allows_additive_versioned_files(tmp_path: Path) -> None:
    from mingli.contracts.freeze import verify_frozen_contracts

    _copy_frozen_tree(tmp_path)
    addition = tmp_path / "src" / "mingli" / "additive_v2_contract.py"
    addition.parent.mkdir(parents=True, exist_ok=True)
    addition.write_text("SCHEMA_VERSION = 'additive@2.0'\n", encoding="utf-8")

    assert verify_frozen_contracts(tmp_path, MANIFEST_PATH).ok


def test_contract_freeze_rejects_path_traversal(tmp_path: Path) -> None:
    from mingli.contracts.freeze import ContractFreezeManifestError, load_contract_manifest

    malicious = {
        "schema_version": "mingli-contract-freeze-manifest@2.0",
        "baseline_sha": BASELINE_SHA,
        "groups": {
            name: (
                [{"path": "../escape", "sha256": "0" * 64}]
                if name == "chart"
                else [{"path": f"{name}.json", "sha256": "0" * 64}]
            )
            for name in GROUPS
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(malicious), encoding="utf-8")

    with pytest.raises(ContractFreezeManifestError, match="repository-relative"):
        load_contract_manifest(path)


def test_architecture_records_non_negotiable_boundaries() -> None:
    document = (
        REPO_ROOT / "MINGLI_CORE_CAPABILITY_SURGE_V2_ARCHITECTURE.md"
    ).read_text(encoding="utf-8")

    for term in (
        BASELINE_SHA,
        "chart",
        "rule",
        "evidence",
        "case",
        "benchmark",
        "runtime",
        "renderer",
        "Reality Evidence",
        "fail closed",
        "Synthetic",
        "Release Hold: **ACTIVE**",
        "integration/mingli-core-capability-surge-v2",
    ):
        assert term in document

