from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .contracts.serialization import digest


@dataclass(frozen=True)
class ZiweiScope:
    user_scope: str
    case_scope: str
    cache_namespace: str

    def __post_init__(self) -> None:
        for name in ("user_scope", "case_scope", "cache_namespace"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty opaque identifier")


def context_hash(context: Mapping[str, object]) -> str:
    return digest({"record_type": "ZiweiTemporalContext", "payload": context})


def make_cache_key(
    scope: ZiweiScope, chart_fingerprint: str, context: Mapping[str, object]
) -> str:
    return digest(
        {
            "record_type": "ZiweiScopedCacheKey",
            "payload": {
                "cache_namespace": scope.cache_namespace,
                "user_scope": scope.user_scope,
                "case_scope": scope.case_scope,
                "chart_fingerprint": chart_fingerprint,
                "context_hash": context_hash(context),
            },
        }
    )


class ScopedZiweiCache:
    def __init__(self) -> None:
        self._values: dict[str, tuple[ZiweiScope, str, object]] = {}

    def put(
        self,
        scope: ZiweiScope,
        chart_fingerprint: str,
        context: Mapping[str, object],
        value: object,
    ) -> None:
        self._values[make_cache_key(scope, chart_fingerprint, context)] = (
            scope,
            chart_fingerprint,
            value,
        )

    def get(
        self, scope: ZiweiScope, chart_fingerprint: str, context: Mapping[str, object]
    ) -> object | None:
        record = self._values.get(make_cache_key(scope, chart_fingerprint, context))
        return None if record is None else record[2]

    def invalidate_chart(self, scope: ZiweiScope, chart_fingerprint: str) -> None:
        stale = [
            key
            for key, (stored_scope, stored_fingerprint, _) in self._values.items()
            if stored_scope == scope and stored_fingerprint == chart_fingerprint
        ]
        for key in stale:
            del self._values[key]


@dataclass(frozen=True)
class ZiweiRequestToken:
    chart_fingerprint: str
    chart_revision: int
    request_revision: int
    context_hash: str


class ZiweiResultGate:
    def __init__(self) -> None:
        self._fingerprint = ""
        self._chart_revision = 0
        self._request_revision = 0
        self._context_hash = ""

    def switch_chart(self, chart_fingerprint: str) -> int:
        if not isinstance(chart_fingerprint, str) or not chart_fingerprint.startswith("sha256:"):
            raise ValueError("chart_fingerprint must be a sha256 digest")
        if chart_fingerprint != self._fingerprint:
            self._fingerprint = chart_fingerprint
            self._chart_revision += 1
            self._request_revision = 0
            self._context_hash = ""
        return self._chart_revision

    def issue_request(self, context: Mapping[str, object]) -> ZiweiRequestToken:
        if not self._fingerprint:
            raise ValueError("switch_chart must be called before issue_request")
        self._request_revision += 1
        self._context_hash = context_hash(context)
        return ZiweiRequestToken(
            self._fingerprint,
            self._chart_revision,
            self._request_revision,
            self._context_hash,
        )

    def accepts(self, token: ZiweiRequestToken) -> bool:
        return token == ZiweiRequestToken(
            self._fingerprint,
            self._chart_revision,
            self._request_revision,
            self._context_hash,
        )


def make_pair_context_hash(first_chart_fingerprint: str, second_chart_fingerprint: str) -> str:
    if first_chart_fingerprint == second_chart_fingerprint:
        raise ValueError("pair analysis requires two distinct chart identities")
    return digest(
        {
            "record_type": "ZiweiOrderedPairContext",
            "payload": {
                "first_role_chart": first_chart_fingerprint,
                "second_role_chart": second_chart_fingerprint,
            },
        }
    )


__all__ = [
    "ScopedZiweiCache", "ZiweiRequestToken", "ZiweiResultGate", "ZiweiScope",
    "context_hash", "make_cache_key", "make_pair_context_hash",
]
