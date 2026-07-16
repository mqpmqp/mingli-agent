from __future__ import annotations

from collections.abc import Awaitable, Callable
import json
import logging
import os
import re
from time import perf_counter
from typing import Literal
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .service import (
    MINGLI_SERVICE_VERSION,
    analyze_mingli_payload,
    build_ziwei_chart_payload,
    evaluate_ziwei_chart_payload,
    get_service_capabilities,
    get_ziwei_coverage,
)

MAX_REQUEST_BYTES = 1_000_000
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_LOGGER = logging.getLogger("mingli.service")
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})

MCP_NAME = "MingLi Agent Runtime"
MCP_INSTRUCTIONS = (
    "All tools are read-only, deterministic, and do not store request data or call "
    "external services. Never present results as verified predictions or decision advice. "
    "For Ziwei rules, call create_ziwei_chart first and evaluate_ziwei_chart only when "
    "the chart is complete. Preserve prediction_validity and Release Hold fields."
)

_ANALYZE_DESCRIPTION = (
    "Use this when the user explicitly asks for a structured MingLi analysis from "
    "birth data and optional present-day reality constraints. Returns deterministic "
    "low-confidence output with prediction validity and safety warnings."
)
_CREATE_ZIWEI_DESCRIPTION = (
    "Use this when the user provides structured birth data and asks for the versioned "
    "deterministic Ziwei chart. Unknown birth time remains degraded and is never "
    "silently replaced with midnight."
)
_EVALUATE_ZIWEI_DESCRIPTION = (
    "Use this when a complete chart returned by create_ziwei_chart needs draft "
    "traditional rule evaluation. Rejects degraded, unsupported, tampered, or "
    "algorithm-incompatible charts."
)
_COVERAGE_DESCRIPTION = (
    "Use this when the user asks whether packaged Ziwei rule content is complete, "
    "behaviorally evaluated, duplicated, or release-ready. Returns Hold status and "
    "never converts engineering coverage into prediction accuracy."
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
    return os.environ.get("MINGLI_HOST", "127.0.0.1")


def _runtime_port() -> int:
    return int(os.environ.get("PORT", os.environ.get("MINGLI_PORT", "8000")))


def analyze_mingli(
    calendar: Literal["solar", "lunar"],
    birth_date: str,
    birth_time: str,
    timezone: str,
    gender: Literal["male", "female", "unspecified"],
    longitude: float,
    latitude: float,
    anchor_year: int,
    true_solar_time: bool = False,
    is_leap_month: bool = False,
    scenario: Literal["career_exam", "relationship_reunion"] | None = None,
    reality: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "chart_input": {
            "gender": gender,
            "calendar": calendar,
            "birth_date": birth_date,
            "birth_time": birth_time,
            "timezone": timezone,
            "birth_location": {"longitude": longitude, "latitude": latitude},
            "true_solar_time": true_solar_time,
            "is_leap_month": is_leap_month,
        },
        "anchor_year": anchor_year,
        "reality": reality or {},
        "fusion_evidence": [],
    }
    if scenario is not None:
        payload["scenario"] = scenario
    result = analyze_mingli_payload(payload)
    return {
        "schema_version": result["schema_version"],
        "method_id": result["method_id"],
        "calculation_version": result["calculation_version"],
        "run_id": result["run_id"],
        "chart": result["chart"],
        "scenario_assessment": result["scenario_assessment"],
        "chenggu": result["chenggu"],
        "final_answer": result["final_answer"],
        "effective_domain_statuses": result["effective_domain_statuses"],
        "effective_domain_confidence": result["effective_domain_confidence"],
        "warnings": result["warnings"],
        "canonical_hash": result["canonical_hash"],
        "prediction_validity": result["prediction_validity"],
    }


def create_ziwei_chart(
    calendar_type: Literal["solar", "lunar"],
    birth_date: str,
    birth_time: str | None,
    timezone: str,
    longitude: float,
    latitude: float,
    gender: Literal["male", "female", "unspecified"],
    solar_time_mode: Literal["civil", "local_mean_solar", "true_solar"] = "civil",
    late_zi_policy: Literal["midnight", "late_zi_next_day"] = "midnight",
    birth_time_known: bool = True,
    leap_month: bool = False,
) -> dict[str, object]:
    return build_ziwei_chart_payload(
        {
            "calendar_type": calendar_type,
            "birth_date": birth_date,
            "birth_time": birth_time,
            "birth_time_known": birth_time_known,
            "timezone": timezone,
            "longitude": longitude,
            "latitude": latitude,
            "solar_time_mode": solar_time_mode,
            "late_zi_policy": late_zi_policy,
            "leap_month": leap_month,
            "gender": gender,
        }
    )


def evaluate_ziwei_chart(chart: dict[str, object]) -> dict[str, object]:
    return evaluate_ziwei_chart_payload(chart)


def get_ziwei_rule_coverage() -> dict[str, object]:
    return get_ziwei_coverage()


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
        {"error": {"code": code, "message": message[:500]}},
        status_code=status_code,
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
                response = _apply_response_headers(
                    _error_response("invalid_content_length", "Invalid Content-Length", 400),
                    request_id,
                )
                self._log_response(request, response, request_id, started)
                return response
            if too_large:
                response = _apply_response_headers(
                    _error_response(
                        "request_too_large",
                        f"Request body exceeds {MAX_REQUEST_BYTES} bytes",
                        413,
                    ),
                    request_id,
                )
                self._log_response(request, response, request_id, started)
                return response
        if request.method in _BODY_METHODS and not await self._buffer_body(request):
            response = _apply_response_headers(
                _error_response(
                    "request_too_large",
                    f"Request body exceeds {MAX_REQUEST_BYTES} bytes",
                    413,
                ),
                request_id,
            )
            self._log_response(request, response, request_id, started)
            return response
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
        response = _apply_response_headers(response, request_id)
        self._log_response(request, response, request_id, started)
        return response

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
    def _log_response(
        request: Request,
        response: Response,
        request_id: str,
        started: float,
    ) -> None:
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


async def _execute_json(
    request: Request,
    handler: Callable[[object], dict[str, object]],
) -> JSONResponse:
    try:
        payload = await _json_object(request)
        return JSONResponse(handler(payload))
    except OverflowError:
        return _error_response(
            "request_too_large",
            f"Request body exceeds {MAX_REQUEST_BYTES} bytes",
            413,
        )
    except json.JSONDecodeError:
        return _error_response("invalid_json", "Request body must be valid JSON", 400)
    except TypeError as exc:
        return _error_response("invalid_request", str(exc), 400)
    except ValueError as exc:
        return _error_response("domain_validation_failed", str(exc), 422)
    except Exception:
        _LOGGER.exception("Unhandled service error")
        return _error_response("internal_error", "Internal service error", 500)


async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": MINGLI_SERVICE_VERSION})


async def capabilities(request: Request) -> JSONResponse:
    return JSONResponse(get_service_capabilities())


async def analyze_http(request: Request) -> JSONResponse:
    return await _execute_json(request, analyze_mingli_payload)


async def ziwei_chart_http(request: Request) -> JSONResponse:
    return await _execute_json(request, build_ziwei_chart_payload)


async def ziwei_rules_http(request: Request) -> JSONResponse:
    return await _execute_json(request, evaluate_ziwei_chart_payload)


async def ziwei_coverage_http(request: Request) -> JSONResponse:
    return JSONResponse(get_ziwei_coverage())


def create_mcp(
    *,
    host: str | None = None,
    port: int | None = None,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
) -> FastMCP:
    resolved_host = host or _runtime_host()
    resolved_port = port if port is not None else _runtime_port()
    resolved_allowed_hosts = (
        _csv_setting("MINGLI_ALLOWED_HOSTS")
        if allowed_hosts is None
        else allowed_hosts
    )
    resolved_allowed_origins = (
        _csv_setting("MINGLI_ALLOWED_ORIGINS")
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
        host=resolved_host,
        port=resolved_port,
        json_response=True,
        stateless_http=True,
        streamable_http_path="/mcp",
        transport_security=transport_security,
    )
    server.tool(
        name="analyze_mingli",
        title="Analyze MingLi runtime",
        description=_ANALYZE_DESCRIPTION,
        annotations=_annotations("Analyze MingLi runtime"),
    )(analyze_mingli)
    server.tool(
        name="create_ziwei_chart",
        title="Create Ziwei chart",
        description=_CREATE_ZIWEI_DESCRIPTION,
        annotations=_annotations("Create Ziwei chart"),
    )(create_ziwei_chart)
    server.tool(
        name="evaluate_ziwei_chart",
        title="Evaluate Ziwei chart rules",
        description=_EVALUATE_ZIWEI_DESCRIPTION,
        annotations=_annotations("Evaluate Ziwei chart rules"),
    )(evaluate_ziwei_chart)
    server.tool(
        name="get_ziwei_rule_coverage",
        title="Get Ziwei rule coverage",
        description=_COVERAGE_DESCRIPTION,
        annotations=_annotations("Get Ziwei rule coverage"),
    )(get_ziwei_rule_coverage)
    server.custom_route("/healthz", methods=["GET"], include_in_schema=False)(
        healthz
    )
    server.custom_route(
        "/v1/capabilities", methods=["GET"], include_in_schema=False
    )(capabilities)
    server.custom_route(
        "/v1/mingli/analyze", methods=["POST"], include_in_schema=False
    )(analyze_http)
    server.custom_route(
        "/v1/ziwei/chart", methods=["POST"], include_in_schema=False
    )(ziwei_chart_http)
    server.custom_route(
        "/v1/ziwei/rules/evaluate", methods=["POST"], include_in_schema=False
    )(ziwei_rules_http)
    server.custom_route(
        "/v1/ziwei/coverage", methods=["GET"], include_in_schema=False
    )(ziwei_coverage_http)
    return server


def create_app(server: FastMCP | None = None) -> Starlette:
    runtime = server or create_mcp()
    application = runtime.streamable_http_app()
    application.add_middleware(RequestPolicyMiddleware)
    return application


mcp = create_mcp()
app = create_app(mcp)


def main() -> None:
    import uvicorn

    host = _runtime_host()
    port = _runtime_port()
    uvicorn.run(
        "mingli.service_app:app",
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("MINGLI_FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


__all__ = [
    "MAX_REQUEST_BYTES",
    "app",
    "create_app",
    "create_mcp",
    "main",
    "mcp",
]


if __name__ == "__main__":
    main()
