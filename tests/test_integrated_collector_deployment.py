from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_integrated_container_has_persistent_off_git_store_and_new_entrypoint() -> None:
    dockerfile = (ROOT / "Dockerfile.integrated").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.11-slim")
    assert "MINGLI_TRAINING_STORE=/var/lib/mingli/training" in dockerfile
    assert 'VOLUME ["/var/lib/mingli"]' in dockerfile
    assert "USER mingli" in dockerfile
    assert 'CMD ["mingli-integrated-service"]' in dockerfile
    assert "MINGLI_TRAINING_COLLECTOR_TOKEN=" not in dockerfile


def test_deployment_runbook_requires_oauth_and_real_three_task_receipts() -> None:
    runbook = (
        ROOT / "docs" / "deployment" / "hourly-training-collector.md"
    ).read_text(encoding="utf-8")

    for required in (
        "submit_hourly_training_report",
        "MINGLI_OAUTH_ISSUER",
        "MINGLI_OAUTH_JWKS_URL",
        "MINGLI_OAUTH_RESOURCE_URL",
        "runtime:read training:write",
        "COLLECTOR_WRITE=OK",
        "list_rule_review_queue",
        "auto_approved",
        "commercial_release_hold=ACTIVE",
        "bind_phase4_1_prediction",
    ):
        assert required in runbook


def test_systemd_unit_runs_single_integrated_process_with_controlled_state() -> None:
    unit = (
        ROOT / "deploy" / "systemd" / "mingli-integrated-service.service.example"
    ).read_text(encoding="utf-8")

    assert "ExecStart=/opt/mingli-agent/.venv/bin/mingli-integrated-service" in unit
    assert "ReadWritePaths=/var/lib/mingli" in unit
    assert "StateDirectory=mingli" in unit
    assert "--workers" not in unit
