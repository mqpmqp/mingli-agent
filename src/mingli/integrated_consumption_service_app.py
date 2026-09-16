from __future__ import annotations

"""Integrated Runtime plus Consumption V1 tools on the existing service endpoint."""

import os
from collections.abc import Callable

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import Context, FastMCP
from starlette.applications import Starlette

from . import integrated_service_app as base
from .training_collector import TrainingReportCollector


INTEGRATED_CONSUMPTION_VERSION = "mingli-integrated-runtime-consumption@1.0"


def create_mcp(
    *,
    collector: TrainingReportCollector | None = None,
    bearer_token: str | None = None,
    host: str | None = None,
    port: int | None = None,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    token_verifier: TokenVerifier | None = None,
    auth_settings: AuthSettings | None = None,
) -> FastMCP:
    if (token_verifier is None) != (auth_settings is None):
        raise ValueError("token_verifier 与 auth_settings 必须同时配置")
    if token_verifier is None:
        oauth_components = base._oauth_from_environment()
        if oauth_components is not None:
            token_verifier, auth_settings = oauth_components
    oauth_enabled = token_verifier is not None

    server = base.create_mcp(
        collector=collector,
        bearer_token=bearer_token,
        host=host,
        port=port,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
        token_verifier=token_verifier,
        auth_settings=auth_settings,
    )
    provider: Callable[[], TrainingReportCollector] = (
        (lambda: collector) if collector is not None else base.default_training_collector
    )

    def _auth(ctx: Context, scope: str) -> None:
        base._require_mcp_auth(
            ctx,
            bearer_token=bearer_token,
            oauth_enabled=oauth_enabled,
            required_scope=scope,
        )

    def stage_consumption_review_asset(
        asset: dict[str, object], ctx: Context
    ) -> dict[str, object]:
        _auth(ctx, "training:write")
        return provider().consumption.stage_review_asset(asset)

    def decide_consumption_review(
        decision: dict[str, object], ctx: Context
    ) -> dict[str, object]:
        _auth(ctx, "training:write")
        return provider().consumption.decide_review(decision)

    def publish_consumption_asset(
        publication: dict[str, object], ctx: Context
    ) -> dict[str, object]:
        _auth(ctx, "training:write")
        return provider().consumption.publish_approved_asset(publication)

    def retrieve_training_context(
        domain: str,
        scenario: str,
        topic: str,
        query_id: str,
        consumed_at: str,
        ctx: Context,
        mode: str = "SHADOW",
    ) -> dict[str, object]:
        _auth(ctx, "training:read")
        return provider().consumption.retrieve(
            domain=domain,
            scenario=scenario,
            topic=topic,
            query_id=query_id,
            consumed_at=consumed_at,
            mode=mode,
        )

    def get_consumption_status(ctx: Context) -> dict[str, object]:
        _auth(ctx, "training:read")
        return provider().consumption.status()

    write_meta = (
        {"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read", "training:write"]}]}
        if oauth_enabled
        else None
    )
    read_meta = (
        {"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read", "training:read"]}]}
        if oauth_enabled
        else None
    )
    server.tool(
        name="stage_consumption_review_asset",
        title="Stage Consumption REVIEW asset",
        description="把结构化训练资产放入 REVIEW；不会自动批准或发布。",
        annotations=base._annotations("Stage Consumption REVIEW asset", read_only=False),
        meta=write_meta,
    )(stage_consumption_review_asset)
    server.tool(
        name="decide_consumption_review",
        title="Decide Consumption review",
        description="记录明确人工 approved/rejected 决定；不得代表用户自动批准。",
        annotations=base._annotations("Decide Consumption review", read_only=False),
        meta=write_meta,
    )(decide_consumption_review)
    server.tool(
        name="publish_consumption_asset",
        title="Publish approved Consumption asset",
        description="仅发布当前最新人工决定仍为 approved 的 REVIEW。",
        annotations=base._annotations("Publish approved Consumption asset", read_only=False),
        meta=write_meta,
    )(publish_consumption_asset)
    server.tool(
        name="retrieve_training_context",
        title="Retrieve training context",
        description="按 domain/scenario/topic 精确检索并写审计；默认 SHADOW。",
        annotations=base._annotations("Retrieve training context", read_only=False),
        meta=read_meta,
    )(retrieve_training_context)
    server.tool(
        name="get_consumption_status",
        title="Get Consumption status",
        description="读取 Consumption V1 当前 REVIEW、批准、发布和可检索状态。",
        annotations=base._annotations("Get Consumption status", read_only=True),
        meta=read_meta,
    )(get_consumption_status)
    return server


def create_app(server: FastMCP | None = None, **kwargs: object) -> Starlette:
    application = (server or create_mcp(**kwargs)).streamable_http_app()
    application.add_middleware(base.RequestPolicyMiddleware)
    return application


mcp = create_mcp()
app = create_app(mcp)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "mingli.integrated_consumption_service_app:app",
        host=base._runtime_host(),
        port=base._runtime_port(),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get(
            "MINGLI_FORWARDED_ALLOW_IPS", "127.0.0.1"
        ),
    )


__all__ = [
    "INTEGRATED_CONSUMPTION_VERSION",
    "app",
    "create_app",
    "create_mcp",
    "main",
    "mcp",
]


if __name__ == "__main__":
    main()
