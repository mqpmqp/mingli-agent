from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

from .contracts.serialization import canonical_json
from .validation_astro_etl import transform_astro_record
from .validation_authorization import evaluate_product_release
from .validation_dataset import build_dataset_manifest, verify_dataset_manifest
from .validation_freeze import freeze_prediction, verify_prediction_snapshot
from .validation_intake import import_intakes, rollback_import, validate_intake
from .validation_privacy import scan_for_pii
from .validation_protocol import verify_validation_protocol
from .release_hold_attack_v1 import (
    assess_release_hold_reassessment,
    calculate_release_hold_attack_metrics,
)


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value) + "\n")


def _controlled_external_path(path: Path, repo_root: Path, *, label: str) -> Path:
    resolved = path.resolve()
    root = repo_root.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError(f"{label} must be outside the Git checkout")
    return resolved


def _controlled_store(path: Path, repo_root: Path) -> Path:
    return _controlled_external_path(path, repo_root, label="validation store")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mingli validation")
    commands = parser.add_subparsers(dest="command", required=True)
    intake = commands.add_parser("intake")
    intake.add_argument("--file", type=Path, required=True)
    intake.add_argument("--store", type=Path, required=True)
    intake.add_argument("--source-ref", required=True)
    intake.add_argument("--dry-run", action="store_true")
    astro = commands.add_parser("astro-intake")
    astro.add_argument("--file", type=Path, required=True)
    astro.add_argument("--store", type=Path, required=True)
    astro.add_argument("--source-ref", required=True)
    astro.add_argument("--project-salt-file", type=Path, required=True)
    astro.add_argument("--dry-run", action="store_true")
    batch = commands.add_parser("intake-batch")
    batch.add_argument("--directory", type=Path, required=True)
    batch.add_argument("--store", type=Path, required=True)
    batch.add_argument("--source-ref", required=True)
    batch.add_argument("--dry-run", action="store_true")
    rollback = commands.add_parser("rollback-import")
    rollback.add_argument("--store", type=Path, required=True)
    rollback.add_argument("--batch-id", required=True)
    validate = commands.add_parser("validate-intake")
    validate.add_argument("--file", type=Path, required=True)
    freeze = commands.add_parser("freeze-prediction")
    freeze.add_argument("--file", type=Path, required=True)
    freeze.add_argument("--store", type=Path, required=True)
    freeze.add_argument("--frozen-at", default=None)
    verify = commands.add_parser("verify-freeze")
    verify.add_argument("--file", type=Path, required=True)
    privacy = commands.add_parser("privacy-scan")
    privacy.add_argument("paths", nargs="+", type=Path)
    dataset = commands.add_parser("freeze-dataset")
    dataset.add_argument("--request", type=Path, required=True)
    dataset.add_argument("--output", type=Path, required=True)
    verify_dataset = commands.add_parser("verify-dataset")
    verify_dataset.add_argument("--file", type=Path, required=True)
    protocol = commands.add_parser("verify-protocol")
    protocol.add_argument("--file", type=Path, default=Path("validation_protocol.json"))
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--manifest", type=Path, default=Path("validation_dataset_manifest.json"))
    benchmark.add_argument("--authorization", type=Path, default=Path("product_release_authorization.json"))
    benchmark.add_argument("--gates", type=Path)
    reassessment = commands.add_parser("hold-reassessment")
    reassessment.add_argument("--records", type=Path, required=True)
    reassessment.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "astro-intake":
            repo_root = Path.cwd()
            source_path = _controlled_external_path(
                args.file,
                repo_root,
                label="Astro source file",
            )
            salt_path = _controlled_external_path(
                args.project_salt_file,
                repo_root,
                label="project salt file",
            )
            project_salt = salt_path.read_text(encoding="utf-8").strip()
            raw_record = _read(source_path)
            if not isinstance(raw_record, Mapping):
                raise ValueError("Astro source file must contain a JSON object")
            transformed = transform_astro_record(raw_record, project_salt=project_salt)
            result = import_intakes(
                _controlled_store(args.store, repo_root),
                [transformed],
                source_ref=args.source_ref,
                dry_run=args.dry_run,
            ).to_dict()
        elif args.command == "intake":
            store = _controlled_store(args.store, Path.cwd())
            result = import_intakes(store, [_read(args.file)], source_ref=args.source_ref, dry_run=args.dry_run).to_dict()
        elif args.command == "intake-batch":
            store = _controlled_store(args.store, Path.cwd())
            records = [_read(path) for path in sorted(args.directory.glob("*.json"))]
            result = import_intakes(store, records, source_ref=args.source_ref, dry_run=args.dry_run).to_dict()
        elif args.command == "rollback-import":
            store = _controlled_store(args.store, Path.cwd())
            result = rollback_import(store, args.batch_id).__dict__
        elif args.command == "validate-intake":
            result = {"valid": True, "intake_canonical_hash": validate_intake(_read(args.file))["intake_canonical_hash"]}
        elif args.command == "freeze-prediction":
            store = _controlled_store(args.store, Path.cwd())
            result = freeze_prediction(
                _read(args.file), store=store,
                frozen_at=args.frozen_at or datetime.now(timezone.utc).isoformat(),
            )
        elif args.command == "verify-freeze":
            valid = verify_prediction_snapshot(_read(args.file))
            result = {"valid": valid}
        elif args.command == "privacy-scan":
            findings = []
            for path in args.paths:
                candidates = sorted(path.rglob("*.json")) if path.is_dir() else [path]
                for candidate in candidates:
                    findings.extend({"file": str(candidate), **item.to_dict()} for item in scan_for_pii(_read(candidate)))
            result = {"passed": not findings, "findings": findings}
        elif args.command == "freeze-dataset":
            request = _read(args.request)
            result = build_dataset_manifest(**request)
            _write_new(args.output, result)
        elif args.command == "verify-dataset":
            result = {"valid": verify_dataset_manifest(_read(args.file))}
        elif args.command == "verify-protocol":
            result = {"valid": verify_validation_protocol(_read(args.file))}
        elif args.command == "hold-reassessment":
            repo_root = Path.cwd()
            records_path = _controlled_external_path(
                args.records,
                repo_root,
                label="Hold reassessment records",
            )
            output_path = _controlled_external_path(
                args.output,
                repo_root,
                label="Hold reassessment output",
            )
            records = _read(records_path)
            if not isinstance(records, list):
                raise ValueError("Hold reassessment records must contain a JSON array")
            metrics = calculate_release_hold_attack_metrics(records)
            reassessment = assess_release_hold_reassessment(metrics)
            result = {
                "report_type": "ReleaseHoldAttackReassessmentReportV1",
                "source_commit_sha": metrics["source_commit_sha"],
                "data_classification": metrics["data_classification"],
                "metrics": metrics,
                "reassessment": reassessment,
            }
            _write_new(output_path, result)
        else:
            manifest = _read(args.manifest)
            authorization = _read(args.authorization)
            gates = _read(args.gates) if args.gates else {}
            release = evaluate_product_release(manifest, authorization, gates)
            result = {
                "dataset_id": manifest.get("dataset_id"),
                "dataset_manifest_sha": manifest.get("aggregate_canonical_hash"),
                "validation_closure_passed": manifest.get("validation_closure_passed") is True,
                "product_accuracy_claim_allowed": manifest.get("product_accuracy_claim_allowed") is True,
                "product_release": release,
                "real_case_count": manifest.get("unique_person_count", 0),
            }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        failed = result.get("valid") is False or result.get("passed") is False
        return 1 if failed else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
