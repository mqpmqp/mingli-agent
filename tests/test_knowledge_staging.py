from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess

import pytest
from starlette.testclient import TestClient

from mingli import knowledge_staging
from mingli.knowledge_staging import (
    KnowledgeStagingError,
    SnapshotIntegrityError,
    import_github_reference,
    search_reference_cards,
)
from mingli.knowledge_service_app import create_app


MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
}


_SOURCE_REPOSITORY = "jinchenma94/bazi-skill"
_SOURCE_COMMIT = "bdd7f863d4450bf0e2fac84579ad6b45cfdfa25c"


def _source_id(path: str) -> str:
    return f"github:{_SOURCE_REPOSITORY}@{_SOURCE_COMMIT}:{path}"


def _source(path: str, status: str) -> dict[str, object]:
    return {
        "source_id": _source_id(path),
        "repository": _SOURCE_REPOSITORY,
        "declared_commit": _SOURCE_COMMIT,
        "path": path,
        "blob_id": "a" * 40,
        "sha256": "b" * 64,
        "size_bytes": 1,
        "source_kind": "github_reference",
        "review_status": status,
        "runtime_eligible": False,
        "prediction_eligible": False,
    }


def _card(card_id: str, source_id: str, lifecycle: str, text: str) -> dict[str, object]:
    return {
        "id": card_id,
        "card_type": "reference",
        "title": card_id,
        "text": text,
        "lifecycle": lifecycle,
        "source_id": source_id,
        "reference_only": True,
        "runtime_eligible": False,
        "prediction_eligible": False,
    }


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


@pytest.fixture
def staging_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge-staging"
    _write_jsonl(
        root / "sources.jsonl",
        [
            _source("reviewed.md", "reviewed"),
            _source("pending.md", "pending"),
        ],
    )
    _write_jsonl(
        root / "cards.jsonl",
        [
            _card("reviewed-card", _source_id("reviewed.md"), "reviewed", "五行传统参考"),
            _card("verified-card", _source_id("reviewed.md"), "verified", "五行已核验参考"),
            _card("draft-card", _source_id("pending.md"), "draft", "五行待审参考"),
            _card("wrong-source-card", _source_id("pending.md"), "reviewed", "五行来源未审"),
        ],
    )
    return root


def _mcp_request(client: TestClient, params: dict[str, object], call_id: int, **headers: str):
    return client.post(
        "/mcp",
        headers={**MCP_HEADERS, **headers},
        json={"jsonrpc": "2.0", "id": call_id, "method": "tools/call", "params": params},
    )


def test_default_search_only_returns_reviewed_source_reviewed_or_verified_cards(
    staging_root: Path,
) -> None:
    default = search_reference_cards("五行", staging_root=staging_root)
    review = search_reference_cards("五行", review_mode=True, staging_root=staging_root)

    assert [item["id"] for item in default["references"]] == [
        "reviewed-card",
        "verified-card",
    ]
    assert [item["source_status"] for item in default["references"]] == [
        "reviewed",
        "reviewed",
    ]
    assert [item["id"] for item in review["references"]] == [
        "draft-card",
        "reviewed-card",
        "verified-card",
        "wrong-source-card",
    ]
    assert default["runtime_input"] is False
    assert default["prediction_input"] is False


def test_http_review_mode_requires_configured_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
    staging_root: Path,
) -> None:
    monkeypatch.setenv("MINGLI_KNOWLEDGE_STAGING_ROOT", str(staging_root))
    monkeypatch.delenv("MINGLI_KNOWLEDGE_REVIEW_TOKEN", raising=False)
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        default = client.post("/v1/knowledge/search", json={"query": "五行"})
        missing = client.post(
            "/v1/knowledge/search", json={"query": "五行", "review_mode": True}
        )
        monkeypatch.setenv("MINGLI_KNOWLEDGE_REVIEW_TOKEN", "test-review-token")
        wrong = client.post(
            "/v1/knowledge/search",
            json={"query": "五行", "review_mode": True},
            headers={"authorization": "Bearer wrong-token"},
        )
        valid = client.post(
            "/v1/knowledge/search",
            json={"query": "五行", "review_mode": True},
            headers={"authorization": "Bearer test-review-token"},
        )

    assert default.status_code == 200
    assert [item["id"] for item in default.json()["references"]] == [
        "reviewed-card",
        "verified-card",
    ]
    for response in (missing, wrong):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "review_mode_forbidden"
    assert valid.status_code == 200
    assert {item["id"] for item in valid.json()["references"]} == {
        "draft-card",
        "reviewed-card",
        "verified-card",
        "wrong-source-card",
    }


def test_mcp_review_mode_requires_the_same_authorization_header(
    monkeypatch: pytest.MonkeyPatch,
    staging_root: Path,
) -> None:
    monkeypatch.setenv("MINGLI_KNOWLEDGE_STAGING_ROOT", str(staging_root))
    monkeypatch.delenv("MINGLI_KNOWLEDGE_REVIEW_TOKEN", raising=False)
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        unconfigured = _mcp_request(
            client,
            {"name": "search_knowledge", "arguments": {"query": "五行", "review_mode": True}},
            1,
            authorization="Bearer any-token",
        )
    monkeypatch.setenv("MINGLI_KNOWLEDGE_REVIEW_TOKEN", "test-review-token")
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        missing = _mcp_request(
            client,
            {"name": "search_knowledge", "arguments": {"query": "五行", "review_mode": True}},
            2,
        )
        wrong = _mcp_request(
            client,
            {"name": "search_knowledge", "arguments": {"query": "五行", "review_mode": True}},
            3,
            authorization="Bearer wrong-token",
        )
        valid = _mcp_request(
            client,
            {"name": "search_knowledge", "arguments": {"query": "五行", "review_mode": True}},
            4,
            authorization="Bearer test-review-token",
        )
        default = _mcp_request(
            client,
            {"name": "search_knowledge", "arguments": {"query": "五行", "review_mode": False}},
            5,
        )

    for response in (unconfigured, missing, wrong):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "review_mode_forbidden"
    assert valid.status_code == 200
    assert valid.json()["result"]["isError"] is False
    assert len(valid.json()["result"]["structuredContent"]["references"]) == 4
    assert default.status_code == 200
    assert [item["id"] for item in default.json()["result"]["structuredContent"]["references"]] == [
        "reviewed-card",
        "verified-card",
    ]


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def test_github_import_reads_declared_tree_blob_not_mutable_worktree_and_rejects_tampering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository = tmp_path / "source"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.email", "tests@example.invalid")
    _git(repository, "config", "user.name", "MingLi tests")
    reference = repository / "traditional.md"
    committed_text = "传统资料，仅供人工复核。\n"
    reference.write_text(committed_text, encoding="utf-8")
    _git(repository, "add", "traditional.md")
    _git(repository, "commit", "-m", "add traditional reference")
    commit = _git(repository, "rev-parse", "HEAD")
    monkeypatch.setattr(
        knowledge_staging,
        "ALLOWED_GITHUB_SOURCES",
        {"jinchenma94/bazi-skill": commit},
    )
    reference.write_text("working tree content must not be imported\n", encoding="utf-8")
    staging = tmp_path / "knowledge-staging"

    snapshot = import_github_reference(
        repository="jinchenma94/bazi-skill",
        declared_commit=commit,
        path="traditional.md",
        git_repository_root=repository,
        staging_root=staging,
    )

    snapshot_file = next((staging / "snapshots").glob("*.bin"))
    assert snapshot_file.read_bytes() == committed_text.encode("utf-8")
    assert snapshot.sha256 == hashlib.sha256(snapshot_file.read_bytes()).hexdigest()
    card = json.loads((staging / "cards.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert card["lifecycle"] == "draft"
    assert card["source_review_status"] == "pending"
    assert card["reference_only"] is True
    assert card["runtime_eligible"] is False
    assert card["prediction_eligible"] is False

    snapshot_file.write_bytes(b"tampered")
    with pytest.raises(SnapshotIntegrityError):
        import_github_reference(
            repository="jinchenma94/bazi-skill",
            declared_commit=commit,
            path="traditional.md",
            git_repository_root=repository,
            staging_root=staging,
        )


@pytest.mark.parametrize(
    ("repository", "commit", "path"),
    [
        ("not-allowed/repository", "a" * 40, "traditional.md"),
        ("jinchenma94/bazi-skill", "A" * 40, "traditional.md"),
        ("jinchenma94/bazi-skill", "a" * 40, "rules.json"),
        ("jinchenma94/bazi-skill", "a" * 40, "examples/traditional.md"),
        ("jinchenma94/bazi-skill", "a" * 40, "reference.pdf"),
    ],
)
def test_github_import_rejects_unallowlisted_or_excluded_inputs(
    repository: str,
    commit: str,
    path: str,
    tmp_path: Path,
) -> None:
    with pytest.raises(KnowledgeStagingError):
        import_github_reference(
            repository=repository,
            declared_commit=commit,
            path=path,
            git_repository_root=tmp_path,
            staging_root=tmp_path / "knowledge-staging",
        )
