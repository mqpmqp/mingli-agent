from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Mapping
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from mingli.bazi import DeterministicBaziEngine, solar_term_utc
from mingli.errors import ChartCalculationError


RUNTIME_LOCK = Path("web/pwa/runtime-lock.json")
BENCHMARKS = Path("tests/fixtures/bazi_independent_benchmarks_v0.1.jsonl")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_runtime_lock(root: Path) -> dict[str, Any]:
    lock_path = root / RUNTIME_LOCK
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != "mingli-pwa-runtime-lock@1.0":
        raise ValueError("unsupported PWA runtime lock schema")
    for name in ("pyodide", "tzdata"):
        record = lock.get(name)
        if not isinstance(record, dict):
            raise ValueError(f"runtime lock is missing {name}")
        digest = record.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or digest != digest.lower():
            raise ValueError(f"runtime lock has invalid {name} SHA256")
        url = record.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(f"runtime lock has invalid {name} URL")
    return lock


def _benchmark_category(record: Mapping[str, Any]) -> str:
    case_id = str(record["id"])
    category = str(record["category"])
    if category == "solar_term_boundary":
        return "lichun_boundary" if "lichun" in case_id else "month_term_boundary"
    if category in {"invalid_lunar_input", "true_solar_time_contract", "unsupported_year"}:
        return "error"
    if category == "lunar_leap_month":
        return "leap_month"
    if category == "true_solar_time":
        return "true_solar_hour_crossing"
    if category in {"day_boundary", "external_source_conflict"}:
        return "zi_hour" if str(record["input"].get("birth_time", "")).startswith("23:") else "day_boundary"
    if category == "timezone":
        return "historical_timezone"
    return "solar"


def _case(
    case_id: str,
    category: str,
    chart_input: Mapping[str, object],
    *,
    source_id: str | None = None,
    expected_error: str | None = None,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "source_id": source_id or case_id,
        "category": category,
        "input": dict(chart_input),
        "expected_error": expected_error,
    }


def _solar_input(
    birth_date: str,
    birth_time: str,
    *,
    timezone: str = "Asia/Shanghai",
    longitude: float = 116.4074,
    latitude: float = 39.9042,
    true_solar_time: bool = False,
) -> dict[str, object]:
    return {
        "gender": "male",
        "calendar": "solar",
        "birth_date": birth_date,
        "birth_time": birth_time,
        "timezone": timezone,
        "longitude": longitude,
        "latitude": latitude,
        "true_solar_time": true_solar_time,
        "fold": 0,
    }


def collect_parity_cases(root: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line in (root / BENCHMARKS).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        cases.append(
            _case(
                f"benchmark:{record['id']}",
                _benchmark_category(record),
                record["input"],
                source_id=str(record["id"]),
                expected_error=record.get("expected_error"),
            )
        )

    years = (1901, 1912, 1936, 1950, 1968, 1988, 2000, 2012, 2024, 2050, 2077, 2099)
    months = (1, 3, 5, 7, 9, 11)
    locations = (
        (121.4737, 31.2304),
        (104.0665, 30.5728),
        (87.6168, 43.8256),
        (113.2644, 23.1291),
    )
    times = ("06:15", "12:34", "18:45")
    for index, (year, month) in enumerate((item for year in years for item in ((year, month) for month in months))):
        longitude, latitude = locations[index % len(locations)]
        cases.append(
            _case(
                f"synthetic:solar:{year}-{month:02d}",
                "longitude" if index % 4 == 0 else "solar",
                _solar_input(
                    f"{year}-{month:02d}-15",
                    times[index % len(times)],
                    longitude=longitude,
                    latitude=latitude,
                ),
            )
        )

    for index, year in enumerate((1901, 1933, 1966, 1999, 2023, 2050, 2099)):
        for month in (1, 8):
            lunar = _solar_input(f"{year}-{month:02d}-01", "09:20")
            lunar.update({"calendar": "lunar", "is_leap_month": False})
            cases.append(_case(f"synthetic:lunar:{year}-{month:02d}", "lunar", lunar))

    cases.extend(
        (
            _case(
                "synthetic:true-solar-day-crossing-west",
                "true_solar_day_crossing",
                _solar_input("2024-06-18", "00:30", longitude=73.0, latitude=39.5, true_solar_time=True),
            ),
            _case(
                "synthetic:true-solar-hour-crossing-east",
                "true_solar_hour_crossing",
                _solar_input("2024-11-15", "00:20", longitude=134.3, latitude=48.3, true_solar_time=True),
            ),
            _case(
                "synthetic:historical-new-york",
                "historical_timezone",
                _solar_input("1945-08-15", "12:00", timezone="America/New_York", longitude=-74.006, latitude=40.7128),
            ),
            _case(
                "synthetic:historical-london",
                "historical_timezone",
                _solar_input("1970-06-15", "12:00", timezone="Europe/London", longitude=-0.1276, latitude=51.5072),
            ),
        )
    )

    uncertain = solar_term_utc(2024, 315).astimezone(ZoneInfo("Asia/Shanghai"))
    error_cases = (
        ("invalid-date", {**_solar_input("2024-02-30", "12:00")}, "INVALID_DATE"),
        ("invalid-time", {**_solar_input("2024-02-20", "25:00")}, "INVALID_TIME"),
        ("invalid-calendar", {**_solar_input("2024-02-20", "12:00"), "calendar": "stellar"}, "INVALID_CALENDAR"),
        ("invalid-gender", {**_solar_input("2024-02-20", "12:00"), "gender": "unknown"}, "INVALID_GENDER"),
        ("missing-longitude", {**_solar_input("2024-02-20", "12:00", true_solar_time=True), "longitude": None}, "MISSING_LONGITUDE"),
        ("invalid-coordinate", {**_solar_input("2024-02-20", "12:00"), "longitude": 181}, "INVALID_COORDINATE"),
        ("invalid-timezone", {**_solar_input("2024-02-20", "12:00"), "timezone": "Invalid/Timezone"}, "INVALID_TIMEZONE"),
        ("nonexistent-local-time", _solar_input("2024-03-10", "02:30", timezone="America/New_York", longitude=-74.006, latitude=40.7128), "NONEXISTENT_LOCAL_TIME"),
        ("unsupported-year", _solar_input("2100-07-15", "12:00"), "UNSUPPORTED_YEAR"),
        ("invalid-leap-month", {**_solar_input("2024-02-01", "12:00"), "calendar": "lunar", "is_leap_month": True}, "INVALID_LEAP_MONTH"),
        ("invalid-fold", {**_solar_input("2024-02-20", "12:00"), "fold": 2}, "INVALID_FOLD"),
        (
            "solar-term-uncertain",
            _solar_input(uncertain.date().isoformat(), uncertain.time().replace(microsecond=0).isoformat()),
            "SOLAR_TERM_UNCERTAIN",
        ),
    )
    for case_id, chart_input, code in error_cases:
        cases.append(_case(f"synthetic:error:{case_id}", "error", chart_input, expected_error=code))

    ids = [str(item["id"]) for item in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("parity case IDs must be unique")
    return cases


def canonical_result_hash(result: Mapping[str, object]) -> str:
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_parity_reference(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    engine = DeterministicBaziEngine()
    records: list[dict[str, Any]] = []
    for case in cases:
        try:
            result = dict(engine.calculate(case["input"]))
        except ChartCalculationError as exc:
            records.append({**case, "outcome": {"ok": False, "error": {"code": exc.code}}})
            continue
        records.append(
            {
                **case,
                "outcome": {
                    "ok": True,
                    "result": result,
                    "canonical_hash": canonical_result_hash(result),
                },
            }
        )
    return records


def _download_verified(url: str, destination: Path, expected_sha256: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and _sha256(destination) == expected_sha256:
        return destination
    partial = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": "mingli-pwa-runtime-builder/1.0"})
    with urlopen(request, timeout=120) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output)
    actual = _sha256(partial)
    if actual != expected_sha256:
        partial.unlink(missing_ok=True)
        raise ValueError(f"download SHA256 mismatch for {url}: expected {expected_sha256}, got {actual}")
    partial.replace(destination)
    return destination


def _extract_pyodide(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            path = PurePosixPath(member.name)
            if not member.isfile() or not path.parts or path.parts[0] != "package":
                continue
            relative = PurePosixPath(*path.parts[1:])
            if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
                raise ValueError(f"unsafe Pyodide archive member: {member.name}")
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise ValueError(f"could not read Pyodide archive member: {member.name}")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def _build_wheel(root: Path, destination: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(destination)],
        cwd=root,
        check=True,
    )
    wheels = sorted(destination.glob("mingli_agent-*.whl"))
    if len(wheels) != 1:
        raise ValueError(f"expected one mingli-agent wheel, found {len(wheels)}")
    return wheels[0]


def _git_sha(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def build_runtime(root: Path, output: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    lock = load_runtime_lock(root)
    public_root = (root / "web/pwa/public").resolve()
    public_root.mkdir(parents=True, exist_ok=True)
    target = (output or public_root / "runtime").resolve()
    if target.parent != public_root:
        raise ValueError("PWA runtime output must be web/pwa/public/runtime")

    cache_override = os.environ.get("MINGLI_PWA_RUNTIME_CACHE")
    cache = Path(cache_override).resolve() if cache_override else Path(tempfile.gettempdir()) / "mingli-pwa-runtime-cache"
    cache.mkdir(parents=True, exist_ok=True)
    pyodide_archive = _download_verified(
        str(lock["pyodide"]["url"]),
        cache / f"pyodide-{lock['pyodide']['version']}.tgz",
        str(lock["pyodide"]["sha256"]),
    )
    tzdata_wheel = _download_verified(
        str(lock["tzdata"]["url"]),
        cache / str(lock["tzdata"]["filename"]),
        str(lock["tzdata"]["sha256"]),
    )

    with tempfile.TemporaryDirectory(prefix="mingli-pwa-build-") as temporary:
        temporary_path = Path(temporary)
        wheel = _build_wheel(root, temporary_path / "wheel")
        staging = temporary_path / "runtime"
        pyodide_target = staging / "pyodide"
        packages_target = staging / "packages"
        packages_target.mkdir(parents=True, exist_ok=True)
        _extract_pyodide(pyodide_archive, pyodide_target)
        wheel_target = packages_target / wheel.name
        tzdata_target = packages_target / tzdata_wheel.name
        shutil.copy2(wheel, wheel_target)
        shutil.copy2(tzdata_wheel, tzdata_target)

        cases = collect_parity_cases(root)
        reference = build_parity_reference(cases)
        (staging / "parity-reference.json").write_text(
            json.dumps(reference, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        git_sha = _git_sha(root)
        wheel_sha256 = _sha256(wheel_target)
        build_material = json.dumps(
            {
                "git_sha": git_sha,
                "wheel_sha256": wheel_sha256,
                "pyodide_version": lock["pyodide"]["version"],
                "tzdata_version": lock["tzdata"]["version"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        build_id = hashlib.sha256(build_material).hexdigest()[:20]
        first_load_bytes = sum(path.stat().st_size for path in staging.rglob("*") if path.is_file())
        manifest = {
            "schema_version": "mingli-pwa-runtime-manifest@1.0",
            "app_build_id": build_id,
            "git_sha": git_sha,
            "wheel": {"filename": f"packages/{wheel.name}", "sha256": wheel_sha256},
            "pyodide": {
                "version": lock["pyodide"]["version"],
                "python_version": lock["pyodide"]["python_version"],
                "archive_sha256": lock["pyodide"]["sha256"],
                "module": "pyodide/pyodide.mjs",
                "index": "pyodide/",
            },
            "tzdata": {
                "version": lock["tzdata"]["version"],
                "filename": f"packages/{tzdata_wheel.name}",
                "sha256": lock["tzdata"]["sha256"],
            },
            "parity": {"filename": "parity-reference.json", "case_count": len(reference)},
            "first_load_bytes": first_load_bytes,
        }
        (staging / "runtime-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(staging, target)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the pinned offline Pyodide runtime for the MingLi PWA")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    manifest = build_runtime(args.root)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
