from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "src/mingli/derived/data/real_case_candidate_freeze_v1.json"
DOC_PATH = ROOT / "docs/validation/REAL_CASE_CANDIDATE_FREEZE_V1.md"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_candidate_identity_is_frozen_without_release_authority() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == "real-case-candidate-freeze@1.0"
    assert manifest["candidate_sha"] == "a41f6d6da78124f0eb76918ebfbb1f8a843b2798"
    assert manifest["base_sha"] == "b03af9f1a7ee5199f64cdd627dd47f348c761d6e"
    assert manifest["release_hold"] == "ACTIVE"
    assert manifest["pr"] == {"number": 36, "draft": True}
    assert manifest["ci"] == {
        "run_id": 29636958835,
        "fast_tests": "success",
        "real_case_tests": "success",
        "benchmark_tests": "success",
    }


def test_manifest_is_sorted_relative_and_hashes_original_bytes() -> None:
    entries = _manifest()["files"]
    assert isinstance(entries, list)
    paths = [entry["path"] for entry in entries]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    assert all("\\" not in path and not Path(path).is_absolute() for path in paths)
    assert "src/mingli/derived/data/real_case_candidate_freeze_v1.json" not in paths
    forbidden = (".git/", "__pycache__/", ".pytest", "dist/", "build/", ".egg-info/")
    assert not any(path.startswith(forbidden) or ".egg-info/" in path for path in paths)
    for entry in entries:
        path = ROOT / entry["path"]
        assert path.is_file(), entry["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert entry["sha256"] == actual, entry["path"]


def test_manifest_contains_required_contract_and_case_os_surfaces() -> None:
    paths = {entry["path"] for entry in _manifest()["files"]}
    assert "pyproject.toml" in paths
    assert ".github/workflows/test.yml" in paths
    assert "src/mingli/contracts/frozen/mingli_core_capability_surge_v2.json" in paths
    assert "src/mingli/derived/data/release_hold_attack_v1_protocol.json" in paths
    assert "src/mingli/contracts/schemas/outcome_observation.schema.json" in paths
    assert "src/mingli/contracts/schemas/outcome_observation_v2.schema.json" in paths
    assert "src/mingli/real_case_learning_v2.py" in paths
    assert "src/mingli/validation_cli.py" in paths
    assert "src/mingli/release_hold_attack_v1.py" in paths


def test_freeze_document_matches_candidate_and_has_external_boundary() -> None:
    document = DOC_PATH.read_text(encoding="utf-8")
    assert "a41f6d6da78124f0eb76918ebfbb1f8a843b2798" in document
    assert "Release Hold: `ACTIVE`" in document
    assert "No real-case data was imported" in document
    assert "candidate freeze is not commercial validation" in document.lower()
    assert "D:\\" not in document
    assert "CI artifact" in document
    assert re.search(r"Freeze timestamp: `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z`", document)
