from __future__ import annotations

"""Independent HTTP/MCP service for staged knowledge references only.

The module intentionally has no import path to the deterministic chart Runtime or
its rule loaders.  It can therefore expose the same HTTP and MCP transport shape
without modifying frozen Runtime contracts.
"""

from collections.abc import Awaitable, Callable
import hmac
import json
import logging
import os
from pathlib import Path
import re
from time import perf_counter
from uuid import uuid4

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .knowledge_staging import KnowledgeStagingError, search_reference_cards


KNOWLEDGE_SERVICE_VERSION = "mingli-knowledge-staging-service@1.0.0"
KNOWLEDGE_REVIEW_TOKEN_ENV = "MINGLI_KNOWLEDGE_REVIEW_TOKEN"
MAX_REQUEST_BYTES = 1_000_000
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_LOGGER = logging.getLogger("mingli.knowledge_service")

MCP_NAME = "MingLi Knowledge Staging"
MCP_INSTRUCTIONS = (
    "This service exposes human-reviewed, reference-only knowledge cards. "
    "It has no chart-runtime, rule-loading, or prediction-input capability. "
    "Default retrieval is reviewed-source only; review_mode requires review authorization."
)
_SEARCH_DESCRIPTION = (
    "Use this only for optional reference context after a text response is already "
    "routed to MingLi. Default search returns reviewed/verified cards from reviewed "
    "sources. review_mode requires an Authorization Bearer header and is never runtime input."
)


def _annotations(title: str) -> ToolAnnotations:
    return ToolAnnotations(
        title=title,
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )


def _csv_setting(name: str) -> list[str]:
    return [
        item
        for value in os.environ.get(name, "").split(",")
        if (item := value.strip())
    ]


def _runtime_host() -> str:
    return os.environ.get("MINGLI_KNOWLEDGE_HOST", "127.0.0.1")


def _runtime_port() -> int:
    return int(os.environ.get("MINGLI_KNOWLEDGE_PORT", "8010"))


def default_knowledge_staging_root() -> Path:
    configured = os.environ.get("MINGLI_KNOWLEDGE_STAGING_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "knowledge-staging"


def review_mode_authorized(authorization: str | None) -> bool:
    """Validate the review credential without ever returning or logging it."""

    configured = os.environ.get(KNOWLEDGE_REVIEW_TOKEN_ENV)
    if not configured or not authorization:
        return False
    return hmac.compare_digest(authorization, f"Bearer {configured}")


def search_knowledge_payload(
    payload: object,
    *,
    staging_root: Path | None = None,
) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise TypeError("knowledge search input must be an object")
    query = payload.get("query")
    if not isinstance(query, str):
        raise KnowledgeStagingError("knowledge query must be a non-empty string")
    return search_reference_cards(
        query,
        review_mode=payload.get("review_mode", False),
        limit=payload.get("limit", 5),
        staging_root=staging_root or default_knowledge_staging_root(),
    )


def _mcp_authorization(ctx: Context) -> str | None:
    try:
        request = ctx.request_context.request
    except ValueError:
        return None
    headers = getattr(request, "headers", None)
    return headers.get("authorization") if headers is not None else None


def search_knowledge(
    query: str,
    ctx: Context,
    review_mode: bool = False,
    limit: int = 5,
) -> dict[str, object]:
    if review_mode and not review_mode_authorized(_mcp_authorization(ctx)):
        raise KnowledgeStagingError("review_mode_forbidden")
    return search_knowledge_payload(
        {"query": query, "review_mode": review_mode, "limit": limit}
    )


def get_service_capabilities() -> dict[str, object]:
    return {
        "schema_version": "mingli-knowledge-service-capabilities@1.0",
        "service_version": KNOWLEDGE_SERVICE_VERSION,
        "archetype": "tool-only",
        "transports": ["http", "streamable-http-mcp"],
        "request_storage": "none",
        "external_network_calls": False,
        "runtime_input": False,
        "prediction_input": False,
        "default_source_review_status": "reviewed",
        "default_card_lifecycles": ["reviewed", "verified"],
        "tools": [
            {
                "name": "search_knowledge",
                "description": _SEARCH_DESCRIPTION,
                "read_only": True,
                "destructive": False,
                "idempotent": True,
                "open_world": False,
            }
        ],
    }


def _request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id", "")
    return supplied if _REQUEST_ID.fullmatch(supplied) else uuid4().hex


def _apply_response_headers(response: Response, request_id: str) -> Response:
    response.headers["cache-control"] = "no-store"
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "no-referrer"
    response.headers["x-request-id"] = request_id
    return response


def _error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message[:500]}}, status_code=status_code
    )


class RequestPolicyMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _request_id(request)
        started = perf_counter()
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > MAX_REQUEST_BYTES
            except ValueError:
                response = _error_response("invalid_content_length", "Invalid Content-Length", 400)
                return self._complete(request, response, request_id, started)
            if too_large:
                response = _error_response(
                    "request_too_large", f"Request body exceeds {MAX_REQUEST_BYTES} bytes", 413
                )
                return self._complete(request, response, request_id, started)
        if request.method in _BODY_METHODS and not await self._buffer_body(request):
            response = _error_response(
                "request_too_large", f"Request body exceeds {MAX_REQUEST_BYTES} bytes", 413
            )
            return self._complete(request, response, request_id, started)
        if await self._mcp_review_mode_forbidden(request):
            response = _error_response(
                "review_mode_forbidden",
                "review_mode requires a valid review authorization token",
                403,
            )
            return self._complete(request, response, request_id, started)
        try:
            response = await call_next(request)
        except Exception:
            _LOGGER.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                },
            )
            raise
        return self._complete(request, response, request_id, started)

    @staticmethod
    async def _buffer_body(request: Request) -> bool:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_REQUEST_BYTES:
                return False
            chunks.append(chunk)
        setattr(request, "_body", b"".join(chunks))
        return True

    @staticmethod
    async def _mcp_review_mode_forbidden(request: Request) -> bool:
        if request.method != "POST" or request.url.path != "/mcp":
            return False
        try:
            value = json.loads(await request.body())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not isinstance(value, dict) or value.get("method") != "tools/call":
            return False
        params = value.get("params")
        if not isinstance(params, dict) or params.get("name") != "search_knowledge":
            return False
        arguments = params.get("arguments")
        if not isinstance(arguments, dict) or arguments.get("review_mode") is not True:
            return False
        return not review_mode_authorized(request.headers.get("authorization"))

    @staticmethod
    def _complete(
        request: Request, response: Response, request_id: str, started: float
    ) -> Response:
        response = _apply_response_headers(response, request_id)
        _LOGGER.info(
            "request_complete",
            extra={
                "request_id": request_id,
                "http_method": request.method,
                "http_path": request.url.path,
                "http_status": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            },
        )
        return response


async def _json_object(request: Request) -> dict[str, object]:
    raw = await request.body()
    if len(raw) > MAX_REQUEST_BYTES:
        raise OverflowError
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise json.JSONDecodeError("invalid JSON", "", 0) from exc
    if not isinstance(value, dict):
        raise TypeError("Request JSON must be an object")
    return value


async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": KNOWLEDGE_SERVICE_VERSION})


async def capabilities(request: Request) -> JSONResponse:
    return JSONResponse(get_service_capabilities())


async def knowledge_search_http(request: Request) -> JSONResponse:
    try:
        payload = await _json_object(request)
        if payload.get("review_mode", False) is True and not review_mode_authorized(
            request.headers.get("authorization")
        ):
            return _error_response(
                "review_mode_forbidden",
                "review_mode requires a valid review authorization token",
                403,
            )
        return JSONResponse(search_knowledge_payload(payload))
    except OverflowError:
        return _error_response(
            "request_too_large", f"Request body exceeds {MAX_REQUEST_BYTES} bytes", 413
        )
    except json.JSONDecodeError:
        return _error_response("invalid_json", "Request body must be valid JSON", 400)
    except (TypeError, KnowledgeStagingError) as exc:
        return _error_response("invalid_request", str(exc), 400)
    except ValueError as exc:
        return _error_response("domain_validation_failed", str(exc), 422)
    except Exception:
        _LOGGER.exception("Unhandled knowledge service error")
        return _error_response("internal_error", "Internal service error", 500)


def create_mcp(
    *,
    host: str | None = None,
    port: int | None = None,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
) -> FastMCP:
    resolved_allowed_hosts = (
        _csv_setting("MINGLI_KNOWLEDGE_ALLOWED_HOSTS")
        if allowed_hosts is None
        else allowed_hosts
    )
    resolved_allowed_origins = (
        _csv_setting("MINGLI_KNOWLEDGE_ALLOWED_ORIGINS")
        if allowed_origins is None
        else allowed_origins
    )
    transport_security = None
    if resolved_allowed_hosts:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=resolved_allowed_hosts,
            allowed_origins=resolved_allowed_origins,
        )
    server = FastMCP(
        MCP_NAME,
        instructions=MCP_INSTRUCTIONS,
        host=host or _runtime_host(),
        port=port if port is not None else _runtime_port(),
        json_response=True,
        stateless_http=True,
        streamable_http_path="/mcp",
        transport_security=transport_security,
    )
    server.tool(
        name="search_knowledge",
        title="Search staged knowledge references",
        description=_SEARCH_DESCRIPTION,
        annotations=_annotations("Search staged knowledge references"),
    )(search_knowledge)
    server.custom_route("/healthz", methods=["GET"], include_in_schema=False)(healthz)
    server.custom_route(
        "/v1/capabilities", methods=["GET"], include_in_schema=False
    )(capabilities)
    server.custom_route(
        "/v1/knowledge/search", methods=["POST"], include_in_schema=False
    )(knowledge_search_http)
    return server


def create_app(server: FastMCP | None = None) -> Starlette:
    application = (server or create_mcp()).streamable_http_app()
    application.add_middleware(RequestPolicyMiddleware)
    return application


mcp = create_mcp()
app = create_app(mcp)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "mingli.knowledge_service_app:app",
        host=_runtime_host(),
        port=_runtime_port(),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("MINGLI_KNOWLEDGE_FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


__all__ = [
    "KNOWLEDGE_REVIEW_TOKEN_ENV",
    "KNOWLEDGE_SERVICE_VERSION",
    "MAX_REQUEST_BYTES",
    "app",
    "create_app",
    "create_mcp",
    "default_knowledge_staging_root",
    "get_service_capabilities",
    "main",
    "mcp",
    "review_mode_authorized",
    "search_knowledge",
    "search_knowledge_payload",
]


if __name__ == "__main__":
    main()
