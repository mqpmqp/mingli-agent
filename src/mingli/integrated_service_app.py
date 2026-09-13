from __future__ import annotations

"""Runtime plus authenticated hourly-training collection.

This is an additive service entrypoint.  The frozen ``mingli-service`` module and
its public contracts remain unchanged.
"""

from collections.abc import Callable
import hmac
import json
import logging
import os
from pathlib import Path
from threading import RLock
from typing import Literal, Mapping

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from .rule_runtime_v1 import RuleAwareRuntime, configured_rule_runtime
from .oauth_resource import OIDCJWTVerifier
from .service import (
    analyze_mingli_payload,
    build_ziwei_chart_payload,
    evaluate_ziwei_chart_payload,
    get_service_capabilities as get_base_capabilities,
    get_ziwei_coverage,
)
from .service_app import RequestPolicyMiddleware
from .training import TrainingError, TrainingStore
from .training_collector import TRAINING_COLLECTOR_VERSION, TrainingReportCollector


INTEGRATED_SERVICE_VERSION = "mingli-integrated-runtime@1.0"
COLLECTOR_TOKEN_ENV = "MINGLI_TRAINING_COLLECTOR_TOKEN"
OAUTH_ISSUER_ENV = "MINGLI_OAUTH_ISSUER"
OAUTH_JWKS_URL_ENV = "MINGLI_OAUTH_JWKS_URL"
OAUTH_RESOURCE_URL_ENV = "MINGLI_OAUTH_RESOURCE_URL"
MAX_REQUEST_BYTES = 1_000_000
_PROTECTED_TOOLS = frozenset(
    {
        "submit_hourly_training_report",
        "get_rule_promotion_status",
        "list_rule_review_queue",
    }
)
_LOGGER = logging.getLogger("mingli.integrated_service")
_DEFAULT_COLLECTOR_LOCK = RLock()
_DEFAULT_COLLECTOR: TrainingReportCollector | None = None
_DEFAULT_COLLECTOR_CONFIG: tuple[str, str] | None = None

MCP_NAME = "MingLi Agent Runtime"
MCP_INSTRUCTIONS = (
    "Runtime analysis is deterministic and keeps prediction_validity=not_evaluated "
    "and commercial Release Hold. submit_hourly_training_report is only for the "
    "three registered hourly-training automations. It stores a schema-valid report, "
    "deduplicates candidates, and runs source and contract-regression gates. It never "
    "approves or publishes a rule."
)


def _annotations(title: str, *, read_only: bool) -> ToolAnnotations:
    return ToolAnnotations(
        title=title,
        readOnlyHint=read_only,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )


def _csv_setting(name: str) -> list[str]:
    return [item for value in os.environ.get(name, "").split(",") if (item := value.strip())]


def _runtime_host() -> str:
    return os.environ.get("MINGLI_HOST", "127.0.0.1")


def _runtime_port() -> int:
    return int(os.environ.get("PORT", os.environ.get("MINGLI_PORT", "8000")))


def _repository_root() -> Path:
    return Path(os.environ.get("MINGLI_REPOSITORY_ROOT", Path.cwd())).resolve()


def default_training_collector() -> TrainingReportCollector:
    store_value = os.environ.get("MINGLI_TRAINING_STORE", "").strip()
    if not store_value:
        raise TrainingError(
            "COLLECTOR_NOT_CONFIGURED",
            "MINGLI_TRAINING_STORE must point to a controlled off-Git directory",
        )
    repository_root = _repository_root()
    config = (str(Path(store_value).expanduser().resolve()), str(repository_root))
    global _DEFAULT_COLLECTOR, _DEFAULT_COLLECTOR_CONFIG
    with _DEFAULT_COLLECTOR_LOCK:
        if _DEFAULT_COLLECTOR is None or _DEFAULT_COLLECTOR_CONFIG != config:
            _DEFAULT_COLLECTOR = TrainingReportCollector(
                TrainingStore(config[0], repository_root=config[1])
            )
            _DEFAULT_COLLECTOR_CONFIG = config
        return _DEFAULT_COLLECTOR


def collector_authorized(
    authorization: str | None, *, bearer_token: str | None = None
) -> bool:
    configured = bearer_token if bearer_token is not None else os.environ.get(COLLECTOR_TOKEN_ENV)
    if not configured or not authorization:
        return False
    return hmac.compare_digest(authorization, f"Bearer {configured}")


def _mcp_authorization(ctx: Context) -> str | None:
    try:
        request = ctx.request_context.request
    except ValueError:
        return None
    headers = getattr(request, "headers", None)
    return headers.get("authorization") if headers is not None else None


def _require_mcp_auth(
    ctx: Context,
    *,
    bearer_token: str | None,
    oauth_enabled: bool,
    required_scope: str,
) -> None:
    if oauth_enabled:
        access_token = get_access_token()
        authorized = access_token is not None and required_scope in access_token.scopes
    else:
        authorized = collector_authorized(
            _mcp_authorization(ctx), bearer_token=bearer_token
        )
    if not authorized:
        raise TrainingError(
            "COLLECTOR_AUTH_REQUIRED",
            f"a valid authorization with {required_scope} is required",
        )


def _configured_runtime() -> RuleAwareRuntime | None:
    settings = dict(os.environ)
    if not settings.get("MINGLI_RULE_RELEASE_STORE", "").strip():
        training_store = settings.get("MINGLI_TRAINING_STORE", "").strip()
        if training_store:
            settings["MINGLI_RULE_RELEASE_STORE"] = training_store
    try:
        return configured_rule_runtime(
            repository_root=_repository_root(), environ=settings
        )
    except TrainingError as exc:
        if (
            exc.code == "RULE_RELEASE_NOT_FOUND"
            and not os.environ.get("MINGLI_RULE_RELEASE_VERSION", "").strip()
        ):
            return None
        raise


def _oauth_from_environment() -> tuple[TokenVerifier, AuthSettings] | None:
    issuer = os.environ.get(OAUTH_ISSUER_ENV, "").strip()
    jwks_url = os.environ.get(OAUTH_JWKS_URL_ENV, "").strip()
    resource_url = os.environ.get(OAUTH_RESOURCE_URL_ENV, "").strip()
    configured = [bool(issuer), bool(jwks_url), bool(resource_url)]
    if not any(configured):
        return None
    if not all(configured):
        raise RuntimeError(
            "MINGLI OAuth requires issuer, JWKS URL, and resource URL together"
        )
    verifier = OIDCJWTVerifier(issuer=issuer, audience=resource_url, jwks_url=jwks_url)
    settings = AuthSettings(
        issuer_url=issuer,
        resource_server_url=resource_url,
        required_scopes=["runtime:read"],
        validate_token_resource=True,
        service_documentation_url=f"{resource_url.rstrip('/')}/v1/capabilities",
    )
    return verifier, settings


def _apply_active_release(result: Mapping[str, object], *, domain: str) -> dict[str, object]:
    runtime = _configured_runtime()
    return dict(result) if runtime is None else runtime.apply(result, domain=domain)


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
    return _apply_active_release(analyze_mingli_payload(payload), domain="bazi")


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


def get_integrated_capabilities() -> dict[str, object]:
    capabilities = get_base_capabilities()
    runtime = _configured_runtime()
    capabilities["integrated_service_version"] = INTEGRATED_SERVICE_VERSION
    capabilities["training_collector"] = {
        "version": TRAINING_COLLECTOR_VERSION,
        "write_auth": "bearer_required",
        "allowed_automations": 3,
        "automatic_steps": [
            "report_ingest",
            "content_deduplication",
            "source_gate_evaluation",
            "contract_regression",
        ],
        "auto_approval": False,
        "auto_publish": False,
    }
    capabilities["rule_release"] = (
        {
            "status": "loaded",
            "version": runtime.release["version"],
            "manifest_hash": runtime.release["manifest_hash"],
            "phase4_1_validation": runtime.release["phase4_1_validation"],
        }
        if runtime is not None
        else {
            "status": "not_published",
            "commercial_release_hold": "ACTIVE",
            "prediction_validity": "not_evaluated",
        }
    )
    return capabilities


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


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message[:500]}}, status_code=status_code
    )


def _collector_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, TrainingError):
        status_code = 503 if exc.code == "COLLECTOR_NOT_CONFIGURED" else 422
        return _error(exc.code, exc.message, status_code)
    if isinstance(exc, OverflowError):
        return _error("request_too_large", "Request body is too large", 413)
    if isinstance(exc, json.JSONDecodeError):
        return _error("invalid_json", "Request body must be valid JSON", 400)
    if isinstance(exc, (TypeError, OSError, UnicodeError)):
        return _error("invalid_request", str(exc), 400)
    if isinstance(exc, ValueError):
        return _error("domain_validation_failed", str(exc), 422)
    _LOGGER.exception("Unhandled integrated service error")
    return _error("internal_error", "Internal service error", 500)


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
    collector_provider: Callable[[], TrainingReportCollector] = (
        (lambda: collector) if collector is not None else default_training_collector
    )

    if (token_verifier is None) != (auth_settings is None):
        raise ValueError("token_verifier and auth_settings must be configured together")
    if token_verifier is None:
        oauth_components = _oauth_from_environment()
        if oauth_components is not None:
            token_verifier, auth_settings = oauth_components
    oauth_enabled = token_verifier is not None

    def submit_hourly_training_report(
        report: dict[str, object], ctx: Context
    ) -> dict[str, object]:
        _require_mcp_auth(
            ctx,
            bearer_token=bearer_token,
            oauth_enabled=oauth_enabled,
            required_scope="training:write",
        )
        return collector_provider().collect(report)

    def get_rule_promotion_status(ctx: Context) -> dict[str, object]:
        _require_mcp_auth(
            ctx,
            bearer_token=bearer_token,
            oauth_enabled=oauth_enabled,
            required_scope="training:read",
        )
        return collector_provider().status()

    def list_rule_review_queue(ctx: Context) -> dict[str, object]:
        _require_mcp_auth(
            ctx,
            bearer_token=bearer_token,
            oauth_enabled=oauth_enabled,
            required_scope="training:read",
        )
        return collector_provider().review_queue()

    resolved_hosts = (
        _csv_setting("MINGLI_ALLOWED_HOSTS")
        if allowed_hosts is None
        else allowed_hosts
    )
    resolved_origins = (
        _csv_setting("MINGLI_ALLOWED_ORIGINS")
        if allowed_origins is None
        else allowed_origins
    )
    transport_security = None
    if resolved_hosts:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=resolved_hosts,
            allowed_origins=resolved_origins,
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
        token_verifier=token_verifier,
        auth=auth_settings,
    )
    server.tool(
        name="analyze_mingli",
        title="Analyze MingLi runtime",
        description="Run the deterministic MingLi runtime and apply an active human-approved rule release.",
        annotations=_annotations("Analyze MingLi runtime", read_only=True),
        meta={"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read"]}]}
        if oauth_enabled
        else None,
    )(analyze_mingli)
    server.tool(
        name="create_ziwei_chart",
        title="Create Ziwei chart",
        description="Create a versioned deterministic Ziwei chart.",
        annotations=_annotations("Create Ziwei chart", read_only=True),
        meta={"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read"]}]}
        if oauth_enabled
        else None,
    )(create_ziwei_chart)
    server.tool(
        name="evaluate_ziwei_chart",
        title="Evaluate Ziwei chart rules",
        description="Evaluate draft traditional Ziwei rules for a complete supported chart.",
        annotations=_annotations("Evaluate Ziwei chart rules", read_only=True),
        meta={"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read"]}]}
        if oauth_enabled
        else None,
    )(evaluate_ziwei_chart)
    server.tool(
        name="get_ziwei_rule_coverage",
        title="Get Ziwei rule coverage",
        description="Return engineering coverage and Release Hold state for Ziwei rules.",
        annotations=_annotations("Get Ziwei rule coverage", read_only=True),
        meta={"securitySchemes": [{"type": "oauth2", "scopes": ["runtime:read"]}]}
        if oauth_enabled
        else None,
    )(get_ziwei_rule_coverage)
    server.tool(
        name="submit_hourly_training_report",
        title="Submit hourly training report",
        description=(
            "Use only after one registered hourly-training automation has generated a complete "
            "HOURLY_TRAINING_REPORT_JSON object. The service stores it off Git, deduplicates "
            "candidate rules, and runs source and regression gates. It never approves or publishes."
        ),
        annotations=_annotations("Submit hourly training report", read_only=False),
        meta={
            "securitySchemes": [
                {"type": "oauth2", "scopes": ["runtime:read", "training:write"]}
            ]
        }
        if oauth_enabled
        else None,
    )(submit_hourly_training_report)
    server.tool(
        name="get_rule_promotion_status",
        title="Get rule promotion status",
        description="Read private collector counts, gate states, active release, and Phase 4.1 Hold state.",
        annotations=_annotations("Get rule promotion status", read_only=True),
        meta={
            "securitySchemes": [
                {"type": "oauth2", "scopes": ["runtime:read", "training:read"]}
            ]
        }
        if oauth_enabled
        else None,
    )(get_rule_promotion_status)
    server.tool(
        name="list_rule_review_queue",
        title="List rule review queue",
        description="List gate receipts and candidates awaiting an explicit human decision.",
        annotations=_annotations("List rule review queue", read_only=True),
        meta={
            "securitySchemes": [
                {"type": "oauth2", "scopes": ["runtime:read", "training:read"]}
            ]
        }
        if oauth_enabled
        else None,
    )(list_rule_review_queue)

    async def healthz(request: Request) -> JSONResponse:
        fallback_token = (
            bearer_token
            if bearer_token is not None
            else os.environ.get(COLLECTOR_TOKEN_ENV)
        )
        return JSONResponse(
            {
                "status": "ok",
                "service": INTEGRATED_SERVICE_VERSION,
                "collector_configured": collector is not None
                or bool(os.environ.get("MINGLI_TRAINING_STORE", "").strip()),
                "collector_auth_configured": oauth_enabled or bool(fallback_token),
                "oauth_resource_server": oauth_enabled,
            }
        )

    async def capabilities(request: Request) -> JSONResponse:
        try:
            return JSONResponse(get_integrated_capabilities())
        except Exception as exc:
            return _collector_error(exc)

    async def analyze_http(request: Request) -> JSONResponse:
        try:
            return JSONResponse(
                _apply_active_release(
                    analyze_mingli_payload(await _json_object(request)), domain="bazi"
                )
            )
        except Exception as exc:
            return _collector_error(exc)

    async def ziwei_chart_http(request: Request) -> JSONResponse:
        try:
            return JSONResponse(build_ziwei_chart_payload(await _json_object(request)))
        except Exception as exc:
            return _collector_error(exc)

    async def ziwei_rules_http(request: Request) -> JSONResponse:
        try:
            return JSONResponse(evaluate_ziwei_chart_payload(await _json_object(request)))
        except Exception as exc:
            return _collector_error(exc)

    async def submit_http(request: Request) -> JSONResponse:
        if oauth_enabled:
            authorized = "training:write" in request.auth.scopes
        else:
            authorized = collector_authorized(
                request.headers.get("authorization"), bearer_token=bearer_token
            )
        if not authorized:
            return _error("collector_auth_required", "Valid Bearer authorization required", 401)
        try:
            return JSONResponse(collector_provider().collect(await _json_object(request)))
        except Exception as exc:
            return _collector_error(exc)

    async def status_http(request: Request) -> JSONResponse:
        if oauth_enabled:
            authorized = "training:read" in request.auth.scopes
        else:
            authorized = collector_authorized(
                request.headers.get("authorization"), bearer_token=bearer_token
            )
        if not authorized:
            return _error("collector_auth_required", "Valid Bearer authorization required", 401)
        try:
            return JSONResponse(collector_provider().status())
        except Exception as exc:
            return _collector_error(exc)

    async def review_queue_http(request: Request) -> JSONResponse:
        if oauth_enabled:
            authorized = "training:read" in request.auth.scopes
        else:
            authorized = collector_authorized(
                request.headers.get("authorization"), bearer_token=bearer_token
            )
        if not authorized:
            return _error("collector_auth_required", "Valid Bearer authorization required", 401)
        try:
            return JSONResponse(collector_provider().review_queue())
        except Exception as exc:
            return _collector_error(exc)

    async def ziwei_coverage_http(request: Request) -> JSONResponse:
        return JSONResponse(get_ziwei_coverage())

    server.custom_route("/healthz", methods=["GET"], include_in_schema=False)(healthz)
    server.custom_route("/v1/capabilities", methods=["GET"], include_in_schema=False)(capabilities)
    server.custom_route("/v1/mingli/analyze", methods=["POST"], include_in_schema=False)(analyze_http)
    server.custom_route("/v1/ziwei/chart", methods=["POST"], include_in_schema=False)(ziwei_chart_http)
    server.custom_route("/v1/ziwei/rules/evaluate", methods=["POST"], include_in_schema=False)(ziwei_rules_http)
    server.custom_route("/v1/ziwei/coverage", methods=["GET"], include_in_schema=False)(
        ziwei_coverage_http
    )
    server.custom_route(
        "/v1/training/hourly-reports", methods=["POST"], include_in_schema=False
    )(submit_http)
    server.custom_route("/v1/training/status", methods=["GET"], include_in_schema=False)(status_http)
    server.custom_route(
        "/v1/training/review-queue", methods=["GET"], include_in_schema=False
    )(review_queue_http)
    return server


def create_app(server: FastMCP | None = None, **kwargs: object) -> Starlette:
    application = (server or create_mcp(**kwargs)).streamable_http_app()
    application.add_middleware(RequestPolicyMiddleware)
    return application


mcp = create_mcp()
app = create_app(mcp)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "mingli.integrated_service_app:app",
        host=_runtime_host(),
        port=_runtime_port(),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get(
            "MINGLI_FORWARDED_ALLOW_IPS", "127.0.0.1"
        ),
    )


__all__ = [
    "COLLECTOR_TOKEN_ENV",
    "INTEGRATED_SERVICE_VERSION",
    "OAUTH_ISSUER_ENV",
    "OAUTH_JWKS_URL_ENV",
    "OAUTH_RESOURCE_URL_ENV",
    "app",
    "collector_authorized",
    "create_app",
    "create_mcp",
    "default_training_collector",
    "get_integrated_capabilities",
    "main",
    "mcp",
]


if __name__ == "__main__":
    main()
