from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import re
import subprocess
from typing import Any

from scripts import build_pwa_runtime


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_lock_pins_browser_dependencies_and_sha256() -> None:
    lock = build_pwa_runtime.load_runtime_lock(ROOT)

    assert lock["python"]["version"] == "3.11.15"
    assert lock["node"]["version"] == "22.18.0"
    assert lock["pyodide"]["version"] == "0.25.1"
    assert lock["pyodide"]["python_version"].startswith("3.11.")
    assert lock["tzdata"]["version"] == "2025.2"
    assert lock["frontend"] == {
        "playwright": "1.55.1",
        "typescript": "5.9.2",
        "vite": "7.3.6",
        "vitest": "3.2.7",
    }
    for dependency in ("pyodide", "tzdata"):
        digest = lock[dependency]["sha256"]
        assert len(digest) == 64
        assert digest == digest.lower()


def test_workflow_defers_runner_temp_until_a_step_is_running() -> None:
    workflow = (ROOT / ".github/workflows/pwa.yml").read_text(encoding="utf-8")
    job_configuration, steps = workflow.split("    steps:\n", maxsplit=1)
    runner_temp = "${{ runner.temp }}"

    assert runner_temp not in job_configuration

    build_step = steps.split(
        "      - name: Build pinned browser runtime and verify downloads\n", maxsplit=1
    )[1].split("      - name:", maxsplit=1)[0]
    assert (
        f"MINGLI_PWA_RUNTIME_CACHE: {runner_temp}/mingli-pwa-runtime-cache"
        in build_step
    )


def test_parity_cases_reuse_all_benchmarks_and_cover_required_boundaries() -> None:
    cases = build_pwa_runtime.collect_parity_cases(ROOT)

    assert len(cases) >= 100
    assert len({case["id"] for case in cases}) == len(cases)
    benchmark_ids = {
        line.split('"id": "', 1)[1].split('"', 1)[0]
        for line in (ROOT / "tests/fixtures/bazi_independent_benchmarks_v0.1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    }
    assert benchmark_ids <= {case["source_id"] for case in cases}
    categories = {case["category"] for case in cases}
    assert {
        "solar",
        "lunar",
        "leap_month",
        "true_solar_hour_crossing",
        "true_solar_day_crossing",
        "lichun_boundary",
        "month_term_boundary",
        "zi_hour",
        "day_boundary",
        "longitude",
        "historical_timezone",
        "error",
    } <= categories


def test_frontend_error_messages_match_every_literal_bazi_fail_code() -> None:
    bazi_source = (ROOT / "src/mingli/bazi.py").read_text(encoding="utf-8")
    tree = ast.parse(bazi_source, filename="src/mingli/bazi.py")
    engine_codes = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_fail"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }

    presentation_source = (ROOT / "web/pwa/src/presentation.ts").read_text(
        encoding="utf-8"
    )
    mapping = re.search(
        r"const\s+ERROR_MESSAGES\b[^=]*=\s*\{(?P<body>.*?)^\};",
        presentation_source,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert mapping is not None, "presentation.ts must define ERROR_MESSAGES"
    frontend_codes = set(
        re.findall(r"^\s{2}([A-Z][A-Z0-9_]+):", mapping.group("body"), re.MULTILINE)
    )

    assert frontend_codes == engine_codes, (
        f"missing frontend mappings: {sorted(engine_codes - frontend_codes)}; "
        f"stale frontend mappings: {sorted(frontend_codes - engine_codes)}"
    )


def test_pwa_png_icons_are_regular_git_blobs_not_lfs_pointers() -> None:
    signature = b"\x89PNG\r\n\x1a\n"
    icon_paths = (
        "web/pwa/public/icons/icon-192.png",
        "web/pwa/public/icons/icon-512.png",
        "web/pwa/public/icons/apple-touch-icon-180.png",
    )

    for icon_path in icon_paths:
        blob = subprocess.run(
            ["git", "show", f":{icon_path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert blob.startswith(signature), (
            f"{icon_path} must be committed as a regular PNG blob; "
            "GitHub Actions checkout does not fetch Git LFS objects by default"
        )

def test_runtime_file_manifest_is_safe_complete_and_byte_exact(tmp_path: Path) -> None:
    files = {
        "packages/mingli_agent-2.0.0-py3-none-any.whl": b"wheel",
        "packages/tzdata.whl": b"timezone",
        "pyodide/pyodide.mjs": b"module",
        "pyodide/pyodide.asm.wasm": b"wasm",
        "parity-reference.json": b"[]",
    }
    for relative, content in files.items():
        target = tmp_path.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    records, total_bytes = build_pwa_runtime._runtime_file_records(tmp_path)

    assert [record["path"] for record in records] == sorted(files)
    assert len({record["path"] for record in records}) == len(records)
    assert total_bytes == sum(map(len, files.values()))
    for record in records:
        path = record["path"]
        assert "\\" not in path
        assert not path.startswith("/")
        assert ".." not in Path(path).parts
        assert record["bytes"] == len(files[path])
        assert record["sha256"] == hashlib.sha256(files[path]).hexdigest()


def test_wheel_build_uses_reproducible_source_date_epoch(
    tmp_path: Path, monkeypatch: Any
) -> None:
    observed: dict[str, object] = {}

    def fake_run(
        command: list[str], *, cwd: Path, check: bool, env: dict[str, str]
    ) -> None:
        observed.update(command=command, cwd=cwd, check=check, env=env)
        outdir = Path(command[command.index("--outdir") + 1])
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "mingli_agent-2.0.0-py3-none-any.whl").write_bytes(b"wheel")

    monkeypatch.setattr(build_pwa_runtime, "_source_date_epoch", lambda _root: 1_700_000_000)
    monkeypatch.setattr(build_pwa_runtime.subprocess, "run", fake_run)

    wheel = build_pwa_runtime._build_wheel(ROOT, tmp_path)

    assert wheel.name == "mingli_agent-2.0.0-py3-none-any.whl"
    assert observed["check"] is True
    assert isinstance(observed["env"], dict)
    assert observed["env"]["SOURCE_DATE_EPOCH"] == "1700000000"  # type: ignore[index]
