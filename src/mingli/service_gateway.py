from __future__ import annotations

import json
import logging
import os

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .service_app import create_app

_LOGGER = logging.getLogger("mingli.service")
_INTERNAL_ERROR_MESSAGE = "Internal service error"


class _ExceptionPrivacyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info is not None:
            record.exc_info = None
            record.exc_text = None
        return True


def _install_exception_privacy_filter() -> None:
    if not any(isinstance(item, _ExceptionPrivacyFilter) for item in _LOGGER.filters):
        _LOGGER.addFilter(_ExceptionPrivacyFilter())


def _sanitize_mcp_error_body(body: bytes) -> bytes:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body
    if not isinstance(payload, dict):
        return body

    changed = False
    error = payload.get("error")
    if isinstance(error, dict):
        payload["error"] = {
            "code": error.get("code", -32603),
            "message": _INTERNAL_ERROR_MESSAGE,
        }
        changed = True

    result = payload.get("result")
    if isinstance(result, dict) and result.get("isError") is True:
        result["content"] = [{"type": "text", "text": _INTERNAL_ERROR_MESSAGE}]
        result.pop("structuredContent", None)
        changed = True

    if not changed:
        return body
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


class MCPErrorPrivacyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if request.url.path != "/mcp" or not content_type.startswith(
            "application/json"
        ):
            return response

        chunks = [
            chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
            async for chunk in response.body_iterator
        ]
        body = b"".join(chunks)
        sanitized = _sanitize_mcp_error_body(body)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=sanitized,
            status_code=response.status_code,
            headers=headers,
            background=response.background,
        )


def create_gateway_app(server: FastMCP | None = None) -> Starlette:
    _install_exception_privacy_filter()
    application = create_app(server)
    application.add_middleware(MCPErrorPrivacyMiddleware)
    return application


app = create_gateway_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("MINGLI_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("MINGLI_PORT", "8000")))
    uvicorn.run(
        "mingli.service_gateway:app",
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get(
            "MINGLI_FORWARDED_ALLOW_IPS",
            "127.0.0.1",
        ),
    )


__all__ = [
    "MCPErrorPrivacyMiddleware",
    "app",
    "create_gateway_app",
    "main",
]


if __name__ == "__main__":
    main()
