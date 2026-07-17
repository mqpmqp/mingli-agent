from __future__ import annotations

import os
from typing import Mapping

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from .capability_surge_v2 import CapabilitySurgeV2Error, run_capability_surge_v2
from .service_app import create_app as create_base_app
from .service_app import create_mcp as create_base_mcp

CAPABILITY_SURGE_SERVICE_VERSION = "mingli-capability-surge-service@2.0.0"


def analyze_capability_surge_v2(payload: dict[str, object]) -> dict[str, object]:
    return run_capability_surge_v2(payload).to_dict()


def get_capability_surge_v2_capabilities() -> dict[str, object]:
    return {
        "schema_version": "mingli-capability-surge-service-capabilities@2.0",
        "service_version": CAPABILITY_SURGE_SERVICE_VERSION,
        "transports": ["http", "streamable-http-mcp"],
        "request_storage": "none",
        "external_network_calls": False,
        "tools": ["analyze_capability_surge_v2"],
        "prediction_validity": "not_evaluated",
        "release_hold": "ACTIVE",
        "accuracy_claim_allowed": False,
    }


async def _capabilities_http(request: Request) -> JSONResponse:
    del request
    return JSONResponse(get_capability_surge_v2_capabilities())


async def _analyze_http(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            {"error": {"code": "invalid_json", "message": "Request body must be JSON"}},
            status_code=400,
        )
    if not isinstance(payload, Mapping):
        return JSONResponse(
            {"error": {"code": "invalid_request", "message": "Request body must be an object"}},
            status_code=400,
        )
    try:
        result = run_capability_surge_v2(payload).to_dict()
    except CapabilitySurgeV2Error as exc:
        return JSONResponse(
            {"error": {"code": "domain_validation_failed", "message": str(exc)[:500]}},
            status_code=422,
        )
    return JSONResponse(result)


def create_capability_surge_mcp(
    *,
    host: str | None = None,
    port: int | None = None,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
) -> FastMCP:
    server = create_base_mcp(
        host=host,
        port=port,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )
    server.tool(
        name="analyze_capability_surge_v2",
        title="Analyze MingLi Core Capability Surge V2",
        description=(
            "Use this when a caller has versioned Bazi Expert V2 input, a complete "
            "Ziwei chart with bounded temporal overlays, and optional review-gated "
            "learning cases. The tool is deterministic, read-only, fail-closed, and "
            "does not establish prediction accuracy."
        ),
        annotations=ToolAnnotations(
            title="Analyze MingLi Core Capability Surge V2",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )(analyze_capability_surge_v2)
    server.custom_route(
        "/v2/capabilities", methods=["GET"], include_in_schema=False
    )(_capabilities_http)
    server.custom_route(
        "/v2/capability-surge/analyze",
        methods=["POST"],
        include_in_schema=False,
    )(_analyze_http)
    return server


def create_capability_surge_app(server: FastMCP | None = None) -> Starlette:
    return create_base_app(server or create_capability_surge_mcp())


mcp = create_capability_surge_mcp()
app = create_capability_surge_app(mcp)


def main() -> None:
    import uvicorn

    host = os.environ.get("MINGLI_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("MINGLI_PORT", "8000")))
    uvicorn.run(
        "mingli.capability_surge_service_v2:app",
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get(
            "MINGLI_FORWARDED_ALLOW_IPS", "127.0.0.1"
        ),
    )


__all__ = [
    "CAPABILITY_SURGE_SERVICE_VERSION",
    "analyze_capability_surge_v2",
    "app",
    "create_capability_surge_app",
    "create_capability_surge_mcp",
    "get_capability_surge_v2_capabilities",
    "main",
    "mcp",
]


if __name__ == "__main__":
    main()
