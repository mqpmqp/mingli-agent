from __future__ import annotations

import hmac
import os
from pathlib import Path
from threading import RLock
from typing import Callable

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.types import ToolAnnotations
from starlette.applications import Starlette

from .consumption_v1 import ConsumptionV1
from .oauth_resource import OIDCJWTVerifier
from .training import TrainingError, TrainingStore


CONSUMPTION_SERVICE_VERSION = "mingli-consumption-service@1.0"
TOKEN_ENV = "MINGLI_TRAINING_COLLECTOR_TOKEN"
OAUTH_ISSUER_ENV = "MINGLI_OAUTH_ISSUER"
OAUTH_JWKS_URL_ENV = "MINGLI_OAUTH_JWKS_URL"
OAUTH_RESOURCE_URL_ENV = "MINGLI_OAUTH_RESOURCE_URL"
_DEFAULT_LOCK = RLock()
_DEFAULT_MANAGER: ConsumptionV1 | None = None
_DEFAULT_CONFIG: tuple[str, str] | None = None


def _repository_root() -> Path:
    return Path(os.environ.get("MINGLI_REPOSITORY_ROOT", Path.cwd())).resolve()


def default_consumption_manager() -> ConsumptionV1:
    store_value = os.environ.get("MINGLI_TRAINING_STORE", "").strip()
    if not store_value:
        raise TrainingError(
            "CONSUMPTION_NOT_CONFIGURED",
            "MINGLI_TRAINING_STORE must point to the controlled off-Git training store",
        )
    repository_root = _repository_root()
    config = (str(Path(store_value).expanduser().resolve()), str(repository_root))
    global _DEFAULT_MANAGER, _DEFAULT_CONFIG
    with _DEFAULT_LOCK:
        if _DEFAULT_MANAGER is None or _DEFAULT_CONFIG != config:
            _DEFAULT_MANAGER = ConsumptionV1(
                TrainingStore(config[0], repository_root=config[1])
            )
            _DEFAULT_CONFIG = config
        return _DEFAULT_MANAGER


def _authorized(authorization: str | None, token: str | None) -> bool:
    configured = token if token is not None else os.environ.get(TOKEN_ENV)
    return bool(configured and authorization and hmac.compare_digest(authorization, f"Bearer {configured}"))


def _request_authorization(ctx: Context) -> str | None:
    try:
        request = ctx.request_context.request
    except ValueError:
        return None
    headers = getattr(request, "headers", None)
    return headers.get("authorization") if headers is not None else None


def _require_auth(
    ctx: Context,
    *,
    bearer_token: str | None,
    oauth_enabled: bool,
    required_scope: str,
) -> None:
    if oauth_enabled:
        access_token = get_access_token()
        ok = access_token is not None and required_scope in access_token.scopes
    else:
        ok = _authorized(_request_authorization(ctx), bearer_token)
    if not ok:
        raise TrainingError("CONSUMPTION_AUTH_REQUIRED", f"authorization with {required_scope} is required")


def _oauth_from_environment() -> tuple[TokenVerifier, AuthSettings] | None:
    issuer = os.environ.get(OAUTH_ISSUER_ENV, "").strip()
    jwks_url = os.environ.get(OAUTH_JWKS_URL_ENV, "").strip()
    resource_url = os.environ.get(OAUTH_RESOURCE_URL_ENV, "").strip()
    configured = [bool(issuer), bool(jwks_url), bool(resource_url)]
    if not any(configured):
        return None
    if not all(configured):
        raise RuntimeError("MingLi OAuth requires issuer, JWKS URL, and resource URL together")
    verifier = OIDCJWTVerifier(issuer=issuer, audience=resource_url, jwks_url=jwks_url)
    settings = AuthSettings(
        issuer_url=issuer,
        resource_server_url=resource_url,
        required_scopes=["runtime:read"],
        validate_token_resource=True,
        service_documentation_url=resource_url,
    )
    return verifier, settings


def _annotations(title: str, *, read_only: bool, idempotent: bool) -> ToolAnnotations:
    return ToolAnnotations(
        title=title,
        readOnlyHint=read_only,
        destructiveHint=False,
        idempotentHint=idempotent,
        openWorldHint=False,
    )


def create_mcp(
    *,
    manager: ConsumptionV1 | None = None,
    bearer_token: str | None = None,
    token_verifier: TokenVerifier | None = None,
    auth_settings: AuthSettings | None = None,
    host: str = "127.0.0.1",
    port: int = 8010,
) -> FastMCP:
    provider: Callable[[], ConsumptionV1] = (lambda: manager) if manager is not None else default_consumption_manager
    if (token_verifier is None) != (auth_settings is None):
        raise ValueError("token_verifier and auth_settings must be configured together")
    if token_verifier is None:
        oauth = _oauth_from_environment()
        if oauth is not None:
            token_verifier, auth_settings = oauth
    oauth_enabled = token_verifier is not None
    server = FastMCP(
        "MingLi Consumption V1",
        instructions=(
            "Human-reviewed training assets only. Never approve on behalf of the user. "
            "Retrieval is exact domain/scenario/topic, bounded, audited, and SHADOW by default."
        ),
        host=host,
        port=port,
        json_response=True,
        stateless_http=True,
        streamable_http_path="/mcp",
        token_verifier=token_verifier,
        auth=auth_settings,
    )

    def stage_consumption_review_asset(asset: dict[str, object], ctx: Context) -> dict[str, object]:
        _require_auth(ctx, bearer_token=bearer_token, oauth_enabled=oauth_enabled, required_scope="training:write")
        return provider().stage_review_asset(asset)

    def decide_consumption_review(decision: dict[str, object], ctx: Context) -> dict[str, object]:
        _require_auth(ctx, bearer_token=bearer_token, oauth_enabled=oauth_enabled, required_scope="training:write")
        return provider().decide_review(decision)

    def publish_consumption_asset(publication: dict[str, object], ctx: Context) -> dict[str, object]:
        _require_auth(ctx, bearer_token=bearer_token, oauth_enabled=oauth_enabled, required_scope="training:write")
        return provider().publish_approved_asset(publication)

    def retrieve_training_context(
        domain: str,
        scenario: str,
        topic: str,
        query_id: str,
        consumed_at: str,
        ctx: Context,
        mode: str = "SHADOW",
    ) -> dict[str, object]:
        _require_auth(ctx, bearer_token=bearer_token, oauth_enabled=oauth_enabled, required_scope="training:read")
        return provider().retrieve(
            domain=domain,
            scenario=scenario,
            topic=topic,
            query_id=query_id,
            consumed_at=consumed_at,
            mode=mode,
        )

    def get_consumption_status(ctx: Context) -> dict[str, object]:
        _require_auth(ctx, bearer_token=bearer_token, oauth_enabled=oauth_enabled, required_scope="training:read")
        return provider().status()

    write_meta = {"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read", "training:write"]}]} if oauth_enabled else None
    read_meta = {"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read", "training:read"]}]} if oauth_enabled else None
    server.tool(
        name="stage_consumption_review_asset",
        description="Stage a structured asset in REVIEW. This does not approve or publish it.",
        annotations=_annotations("Stage Consumption REVIEW asset", read_only=False, idempotent=False),
        meta=write_meta,
    )(stage_consumption_review_asset)
    server.tool(
        name="decide_consumption_review",
        description="Record an explicit human approved/rejected decision. Invoke only after the user has explicitly decided.",
        annotations=_annotations("Decide Consumption review", read_only=False, idempotent=False),
        meta=write_meta,
    )(decide_consumption_review)
    server.tool(
        name="publish_consumption_asset",
        description="Publish only when the exact REVIEW hash has a latest approved human receipt.",
        annotations=_annotations("Publish approved Consumption asset", read_only=False, idempotent=False),
        meta=write_meta,
    )(publish_consumption_asset)
    server.tool(
        name="retrieve_training_context",
        description="Retrieve an audited bounded same-domain/scenario/topic context pack; defaults to SHADOW.",
        annotations=_annotations("Retrieve training context", read_only=False, idempotent=False),
        meta=read_meta,
    )(retrieve_training_context)
    server.tool(
        name="get_consumption_status",
        description="Read Consumption V1 asset and retrieval policy status.",
        annotations=_annotations("Get Consumption status", read_only=True, idempotent=True),
        meta=read_meta,
    )(get_consumption_status)
    return server


def create_app(server: FastMCP | None = None, **kwargs: object) -> Starlette:
    return (server or create_mcp(**kwargs)).streamable_http_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("MINGLI_CONSUMPTION_HOST", "127.0.0.1")
    port = int(os.environ.get("MINGLI_CONSUMPTION_PORT", "8010"))
    uvicorn.run(create_app(create_mcp(host=host, port=port)), host=host, port=port)


__all__ = [
    "CONSUMPTION_SERVICE_VERSION",
    "create_app",
    "create_mcp",
    "default_consumption_manager",
    "main",
]


if __name__ == "__main__":
    main()
