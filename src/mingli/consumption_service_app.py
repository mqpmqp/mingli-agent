from __future__ import annotations

import hmac
import os
from pathlib import Path
from threading import RLock
from typing import Callable

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from starlette.applications import Starlette

from .consumption_v1 import ConsumptionV1
from .oauth_resource import OIDCJWTVerifier
from .training import TrainingError, TrainingStore


CONSUMPTION_SERVICE_VERSION = "mingli-consumption-service@1.1"
TOKEN_ENV = "MINGLI_TRAINING_COLLECTOR_TOKEN"
APPROVAL_TOKEN_ENV = "MINGLI_CONSUMPTION_APPROVAL_TOKEN"
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
            "MINGLI_TRAINING_STORE 必须指向受控的仓库外训练目录",
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
    return bool(token and authorization and hmac.compare_digest(authorization, f"Bearer {token}"))


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
        configured = bearer_token or os.environ.get(TOKEN_ENV, "").strip()
        ok = _authorized(_request_authorization(ctx), configured)
    if not ok:
        raise TrainingError("CONSUMPTION_AUTH_REQUIRED", f"需要有效的 {required_scope} 授权")


def _require_approval_auth(
    ctx: Context,
    *,
    approval_token: str | None,
    oauth_enabled: bool,
) -> None:
    if oauth_enabled:
        access_token = get_access_token()
        ok = access_token is not None and "training:approve" in access_token.scopes
    else:
        configured = approval_token or os.environ.get(APPROVAL_TOKEN_ENV, "").strip()
        ok = _authorized(_request_authorization(ctx), configured)
    if not ok:
        raise TrainingError(
            "HUMAN_APPROVAL_AUTH_REQUIRED",
            "人工批准和发布必须使用独立 training:approve 授权",
        )


def _oauth_from_environment() -> tuple[TokenVerifier, AuthSettings] | None:
    issuer = os.environ.get(OAUTH_ISSUER_ENV, "").strip()
    jwks_url = os.environ.get(OAUTH_JWKS_URL_ENV, "").strip()
    resource_url = os.environ.get(OAUTH_RESOURCE_URL_ENV, "").strip()
    configured = [bool(issuer), bool(jwks_url), bool(resource_url)]
    if not any(configured):
        return None
    if not all(configured):
        raise RuntimeError("MingLi OAuth 必须同时配置 issuer、JWKS URL 和 resource URL")
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
    approval_token: str | None = None,
    token_verifier: TokenVerifier | None = None,
    auth_settings: AuthSettings | None = None,
    host: str = "127.0.0.1",
    port: int = 8010,
) -> FastMCP:
    provider: Callable[[], ConsumptionV1] = (
        (lambda: manager) if manager is not None else default_consumption_manager
    )
    if (token_verifier is None) != (auth_settings is None):
        raise ValueError("token_verifier 与 auth_settings 必须同时配置")
    if token_verifier is None:
        oauth = _oauth_from_environment()
        if oauth is not None:
            token_verifier, auth_settings = oauth
    oauth_enabled = token_verifier is not None
    server = FastMCP(
        "MingLi Consumption V1",
        instructions=(
            "只消费人工审核训练资产。不得代表用户批准。"
            "检索严格按 domain/scenario/topic，有限额、有审计，默认 SHADOW。"
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
        _require_approval_auth(ctx, approval_token=approval_token, oauth_enabled=oauth_enabled)
        return provider().decide_review(decision)

    def publish_consumption_asset(publication: dict[str, object], ctx: Context) -> dict[str, object]:
        _require_approval_auth(ctx, approval_token=approval_token, oauth_enabled=oauth_enabled)
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
    approve_meta = {"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read", "training:approve"]}]} if oauth_enabled else None
    read_meta = {"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read", "training:read"]}]} if oauth_enabled else None
    server.tool(
        name="stage_consumption_review_asset",
        description="把结构化训练资产放入 REVIEW；不会自动批准或发布。",
        annotations=_annotations("Stage Consumption REVIEW asset", read_only=False, idempotent=False),
        meta=write_meta,
    )(stage_consumption_review_asset)
    server.tool(
        name="decide_consumption_review",
        description="记录明确人工 approved/rejected 决定；必须使用独立 training:approve 授权。",
        annotations=_annotations("Decide Consumption review", read_only=False, idempotent=False),
        meta=approve_meta,
    )(decide_consumption_review)
    server.tool(
        name="publish_consumption_asset",
        description="仅发布当前最新人工决定仍为 approved 的 REVIEW；必须使用独立 training:approve 授权。",
        annotations=_annotations("Publish approved Consumption asset", read_only=False, idempotent=False),
        meta=approve_meta,
    )(publish_consumption_asset)
    server.tool(
        name="retrieve_training_context",
        description="按 domain/scenario/topic 精确检索并写审计；默认 SHADOW。",
        annotations=_annotations("Retrieve training context", read_only=False, idempotent=False),
        meta=read_meta,
    )(retrieve_training_context)
    server.tool(
        name="get_consumption_status",
        description="读取 Consumption V1 当前状态。",
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
    "APPROVAL_TOKEN_ENV",
    "CONSUMPTION_SERVICE_VERSION",
    "create_app",
    "create_mcp",
    "default_consumption_manager",
    "main",
]


if __name__ == "__main__":
    main()
