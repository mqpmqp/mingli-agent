from __future__ import annotations

"""Read-only staging store for human-reviewed knowledge references.

This module deliberately has no dependency on the deterministic chart runtime.
GitHub material enters as a pending, reference-only card and therefore cannot be
used as a rule, a prediction conclusion, or runtime input.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any, Mapping, Sequence


ALLOWED_GITHUB_SOURCES: Mapping[str, str] = {
    "jinchenma94/bazi-skill": "bdd7f863d4450bf0e2fac84579ad6b45cfdfa25c",
    "Renhuai123/ziwei-doushu": "88194a404242bfe5c6d5cc512e4117e3e245cdd5",
}
CARD_LIFECYCLES = frozenset({"draft", "reviewed", "verified"})
SOURCE_REVIEW_STATUSES = frozenset({"pending", "reviewed"})
_FULL_GIT_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SAFE_TEXT_SUFFIXES = frozenset({".md", ".txt"})
_REJECTED_PATH_PARTS = frozenset(
    {
        "example",
        "examples",
        "case",
        "cases",
        "medical",
        "health",
        "test",
        "tests",
        "fixtures",
    }
)
_REJECTED_TEXT = re.compile(
    r"(?:\bmedical\b|\bdiagnos(?:is|tic)?\b|\btreatment\b|\bdisease\b|"
    r"\bpatient\b|\bpersonal example\b|\bmodern prediction\b|"
    r"医疗|诊断|治疗|疾病|患者|个人示例|个人案例|现代断语|当代断语)",
    re.IGNORECASE,
)


class KnowledgeStagingError(ValueError):
    """Raised when a staged knowledge artifact violates its isolation contract."""


class SnapshotIntegrityError(KnowledgeStagingError):
    """Raised when a retained snapshot is not byte-identical to its Git blob."""


@dataclass(frozen=True)
class GitHubSourceSnapshot:
    source_id: str
    repository: str
    declared_commit: str
    path: str
    blob_id: str
    sha256: str
    size_bytes: int
    review_status: str = "pending"
    source_kind: str = "github_reference"
    runtime_eligible: bool = False
    prediction_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _safe_relative_path(path: str) -> PurePosixPath:
    candidate = PurePosixPath(path)
    if (
        not path
        or candidate.is_absolute()
        or ".." in candidate.parts
        or "." in candidate.parts
        or "\\" in path
        or candidate.as_posix() != path
    ):
        raise KnowledgeStagingError("GitHub reference path must be safe and repository-relative")
    return candidate


def _validate_declaration(repository: str, declared_commit: str, path: str) -> PurePosixPath:
    if repository not in ALLOWED_GITHUB_SOURCES:
        raise KnowledgeStagingError("GitHub repository is not allowlisted")
    if not _FULL_GIT_OBJECT_ID.fullmatch(declared_commit):
        raise KnowledgeStagingError("GitHub commit must be a complete lowercase 40/64-character ID")
    if declared_commit != ALLOWED_GITHUB_SOURCES[repository]:
        raise KnowledgeStagingError("GitHub commit is not the allowlisted declared commit")
    candidate = _safe_relative_path(path)
    if candidate.suffix.lower() not in _SAFE_TEXT_SUFFIXES:
        raise KnowledgeStagingError("only non-executable .md and .txt reference files are importable")
    if any(part.lower() in _REJECTED_PATH_PARTS for part in candidate.parts):
        raise KnowledgeStagingError("personal examples, medical material, and test fixtures are excluded")
    return candidate


def _run_git(repository_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise KnowledgeStagingError("declared Git commit/tree/blob is unavailable")
    return completed.stdout


def _tree_blob(repository_root: Path, declared_commit: str, path: PurePosixPath) -> tuple[str, bytes]:
    # Verify the exact declared commit before resolving a tree path.  No working-tree
    # file is opened anywhere in this flow.
    resolved = _run_git(repository_root, "rev-parse", "--verify", f"{declared_commit}^{{commit}}")
    if resolved.decode("ascii", "strict").strip() != declared_commit:
        raise KnowledgeStagingError("Git commit did not resolve to the declared full ID")
    tree_record = _run_git(
        repository_root,
        "ls-tree",
        "-z",
        declared_commit,
        "--",
        path.as_posix(),
    )
    records = [item for item in tree_record.split(b"\0") if item]
    if len(records) != 1:
        raise KnowledgeStagingError("declared commit path must resolve to exactly one blob")
    try:
        metadata, resolved_path = records[0].split(b"\t", 1)
        mode, object_type, blob_id = metadata.decode("ascii", "strict").split()
    except (UnicodeDecodeError, ValueError) as exc:
        raise KnowledgeStagingError("declared commit tree record is malformed") from exc
    if mode != "100644" or object_type != "blob" or resolved_path.decode("utf-8", "strict") != path.as_posix():
        raise KnowledgeStagingError("declared commit path is not a regular, exact blob")
    return blob_id, _run_git(repository_root, "cat-file", "blob", blob_id)


def _reject_excluded_reference(text: str) -> None:
    if _REJECTED_TEXT.search(text):
        raise KnowledgeStagingError(
            "medical material, personal examples, and unverified modern claims are excluded"
        )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    values: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise KnowledgeStagingError(f"invalid JSONL at {path}:{number}") from exc
        if not isinstance(value, dict):
            raise KnowledgeStagingError(f"JSONL record at {path}:{number} must be an object")
        values.append(value)
    return values


def _write_jsonl(path: Path, records: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = "".join(
        json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )
    path.write_text(contents, encoding="utf-8")


def _snapshot_name(repository: str, declared_commit: str, blob_id: str) -> str:
    return f"{repository.replace('/', '__')}--{declared_commit}--{blob_id}"


def _verify_existing_snapshot(path: Path, expected_sha256: str) -> None:
    if not path.exists():
        return
    actual = sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise SnapshotIntegrityError("existing snapshot SHA-256 does not match its declared Git blob")


def import_github_reference(
    *,
    repository: str,
    declared_commit: str,
    path: str,
    git_repository_root: Path | str,
    staging_root: Path | str,
) -> GitHubSourceSnapshot:
    """Stage a single Git tree/blob as a pending, non-runtime reference card.

    The caller supplies a local clone solely as an object database.  The content is
    read with ``git ls-tree`` and ``git cat-file`` from the declared commit, never
    from the clone's mutable working tree.
    """

    candidate = _validate_declaration(repository, declared_commit, path)
    git_root = Path(git_repository_root).resolve()
    root = Path(staging_root).resolve()
    if not (git_root / ".git").exists():
        raise KnowledgeStagingError("GitHub source repository must be a local Git checkout")
    blob_id, raw = _tree_blob(git_root, declared_commit, candidate)
    try:
        reference_text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KnowledgeStagingError("only UTF-8 GitHub reference text is importable") from exc
    _reject_excluded_reference(reference_text)

    digest = sha256(raw).hexdigest()
    name = _snapshot_name(repository, declared_commit, blob_id)
    snapshots = root / "snapshots"
    snapshot_path = snapshots / f"{name}.bin"
    metadata_path = snapshots / f"{name}.json"
    _verify_existing_snapshot(snapshot_path, digest)

    source_id = f"github:{repository}@{declared_commit}:{candidate.as_posix()}"
    snapshot = GitHubSourceSnapshot(
        source_id=source_id,
        repository=repository,
        declared_commit=declared_commit,
        path=candidate.as_posix(),
        blob_id=blob_id,
        sha256=digest,
        size_bytes=len(raw),
    )
    metadata = snapshot.to_dict()
    if metadata_path.exists():
        try:
            existing_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SnapshotIntegrityError("existing snapshot metadata is invalid") from exc
        if existing_metadata != metadata:
            raise SnapshotIntegrityError("existing snapshot metadata does not match its Git blob")
    if not snapshot_path.exists():
        snapshots.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(raw)
    if not metadata_path.exists():
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    sources_path = root / "sources.jsonl"
    sources = _jsonl(sources_path)
    existing_source = next((item for item in sources if item.get("source_id") == source_id), None)
    if existing_source is not None and existing_source != metadata:
        raise SnapshotIntegrityError("existing source record does not match its Git blob")
    if existing_source is None:
        _write_jsonl(sources_path, sorted([*sources, metadata], key=lambda item: str(item["source_id"])))

    cards_path = root / "cards.jsonl"
    cards = _jsonl(cards_path)
    card_id = f"github_ref_{digest[:24]}"
    card = {
        "id": card_id,
        "card_type": "reference",
        "title": candidate.name,
        "text": reference_text,
        "lifecycle": "draft",
        "source_id": source_id,
        "source_review_status": "pending",
        "reference_only": True,
        "runtime_eligible": False,
        "prediction_eligible": False,
    }
    existing_card = next((item for item in cards if item.get("id") == card_id), None)
    if existing_card is not None and existing_card != card:
        raise SnapshotIntegrityError("existing reference card does not match its Git blob")
    if existing_card is None:
        _write_jsonl(cards_path, sorted([*cards, card], key=lambda item: str(item["id"])))
    return snapshot


def _validated_source(record: Mapping[str, Any]) -> bool:
    repository = record.get("repository")
    declared_commit = record.get("declared_commit")
    path = record.get("path")
    source_id = record.get("source_id")
    if (
        not isinstance(repository, str)
        or not isinstance(declared_commit, str)
        or not isinstance(path, str)
        or not isinstance(source_id, str)
        or repository not in ALLOWED_GITHUB_SOURCES
        or declared_commit != ALLOWED_GITHUB_SOURCES[repository]
        or not _FULL_GIT_OBJECT_ID.fullmatch(declared_commit)
    ):
        return False
    try:
        candidate = _validate_declaration(repository, declared_commit, path)
    except KnowledgeStagingError:
        return False
    return (
        candidate.suffix.lower() in _SAFE_TEXT_SUFFIXES
        and source_id == f"github:{repository}@{declared_commit}:{candidate.as_posix()}"
        and isinstance(record.get("blob_id"), str)
        and bool(_FULL_GIT_OBJECT_ID.fullmatch(record["blob_id"]))
        and isinstance(record.get("sha256"), str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", record["sha256"]))
        and isinstance(record.get("size_bytes"), int)
        and not isinstance(record.get("size_bytes"), bool)
        and record["size_bytes"] >= 0
        and record.get("source_kind") == "github_reference"
        and record.get("review_status") in SOURCE_REVIEW_STATUSES
        and record.get("runtime_eligible") is False
        and record.get("prediction_eligible") is False
    )


def _validated_card(record: Mapping[str, Any]) -> bool:
    return (
        isinstance(record.get("id"), str)
        and isinstance(record.get("source_id"), str)
        and isinstance(record.get("title"), str)
        and isinstance(record.get("text"), str)
        and record.get("card_type") == "reference"
        and record.get("lifecycle") in CARD_LIFECYCLES
        and record.get("reference_only") is True
        and record.get("runtime_eligible") is False
        and record.get("prediction_eligible") is False
    )


def search_reference_cards(
    query: str,
    *,
    review_mode: bool = False,
    staging_root: Path | str,
    limit: int = 5,
) -> dict[str, object]:
    """Search only staged reference cards; default visibility is reviewed-only."""

    if not isinstance(query, str) or not query.strip():
        raise KnowledgeStagingError("knowledge query must be a non-empty string")
    if not isinstance(review_mode, bool):
        raise KnowledgeStagingError("review_mode must be boolean")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise KnowledgeStagingError("limit must be an integer from 1 to 20")
    root = Path(staging_root).resolve()
    sources = {
        str(item["source_id"]): item
        for item in _jsonl(root / "sources.jsonl")
        if _validated_source(item)
    }
    query_tokens = tuple(token for token in query.casefold().split() if token)
    results: list[tuple[int, dict[str, object]]] = []
    for card in _jsonl(root / "cards.jsonl"):
        if not _validated_card(card):
            continue
        source = sources.get(str(card["source_id"]))
        if source is None:
            continue
        source_status = source["review_status"]
        if not review_mode and not (
            card["lifecycle"] in {"reviewed", "verified"}
            and source_status == "reviewed"
        ):
            continue
        haystack = f"{card['title']}\n{card['text']}".casefold()
        score = sum(token in haystack for token in query_tokens)
        if score:
            results.append(
                (
                    score,
                    {
                        "id": card["id"],
                        "title": card["title"],
                        "text": card["text"],
                        "lifecycle": card["lifecycle"],
                        "source_id": card["source_id"],
                        "source_status": source_status,
                        "reference_only": True,
                        "runtime_eligible": False,
                        "prediction_eligible": False,
                    },
                )
            )
    results.sort(key=lambda item: (-item[0], str(item[1]["id"])))
    return {
        "schema_version": "mingli-knowledge-search@1.0",
        "review_mode": review_mode,
        "references": [item for _, item in results[:limit]],
        "runtime_input": False,
        "prediction_input": False,
    }


__all__ = [
    "ALLOWED_GITHUB_SOURCES",
    "GitHubSourceSnapshot",
    "KnowledgeStagingError",
    "SnapshotIntegrityError",
    "import_github_reference",
    "search_reference_cards",
]
