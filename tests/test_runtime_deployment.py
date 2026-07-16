from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docker_image_contract_is_minimal_non_root_and_health_checked() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.11-slim")
    assert 'python -m pip install --no-cache-dir ".[api]"' in dockerfile
    assert "COPY src ./src" in dockerfile
    assert "COPY . ." not in dockerfile
    assert "USER mingli" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert 'CMD ["mingli-service"]' in dockerfile


def test_container_context_excludes_local_state_and_sensitive_inputs() -> None:
    ignored = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {".git", ".env", ".venv", ".pytest_cache", "validation"} <= ignored


def test_deployment_runbook_covers_runtime_and_chatgpt_connection() -> None:
    runbook = (
        ROOT / "docs" / "deployment" / "runtime-http-mcp.md"
    ).read_text(encoding="utf-8")

    for required in (
        "/healthz",
        "/mcp",
        "MINGLI_ALLOWED_HOSTS",
        "MINGLI_ALLOWED_ORIGINS",
        "MINGLI_FORWARDED_ALLOW_IPS",
        "Settings → Security and login → Developer mode",
        "Settings → Plugins",
        "prediction_validity=not_evaluated",
        "PRODUCT_RELEASE_HOLD",
    ):
        assert required in runbook


def test_ci_installs_api_extra_for_runtime_transport_tests() -> None:
    workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count('python -m pip install -e ".[dev,api]"') == 3
    assert 'python -m pip install -e ".[dev]"' not in workflow
