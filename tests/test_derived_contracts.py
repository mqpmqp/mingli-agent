from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from dataclasses import FrozenInstanceError
from pathlib import Path

from jsonschema import Draft202012Validator

from mingli.bazi import DeterministicBaziEngine
from mingli.contracts import (
    DERIVED_METHOD_ID,
    DERIVED_SCHEMA_VERSION,
    BaseChartRef,
    DependencyAmbiguity,
    DerivedChartResult,
    DerivedContractError,
    DerivedError,
    DerivedPillar,
    HiddenStemRecord,
    NayinRecord,
    TenGodRecord,
    XunKongRecord,
    canonical_json,
    digest,
    get_schema,
    load_convention_profile,
    validate_source_manifest,
)
from mingli.derived import adapt_base_chart


def base_input() -> dict[str, object]:
    return {
        "birth_date": "2000-01-07",
        "birth_time": "12:00",
        "timezone": "Asia/Shanghai",
        "gender": "male",
        "calendar": "solar",
    }


class CanonicalContractTests(unittest.TestCase):
    def test_models_are_immutable_and_serialization_is_stable(self) -> None:
        profile = load_convention_profile("derived-static-r1@0.1")
        with self.assertRaises(FrozenInstanceError):
            profile.profile_id = "changed"  # type: ignore[misc]
        self.assertEqual(
            canonical_json({"中文": "值", "b": 2, "a": 1}),
            canonical_json({"a": 1, "b": 2, "中文": "值"}),
        )
        self.assertEqual(digest({"b": 2, "a": 1}), digest({"a": 1, "b": 2}))
        self.assertIn("中文", canonical_json({"中文": "值"}))

    def test_base_adapter_allowlist_shape_and_fingerprint(self) -> None:
        base = DeterministicBaziEngine().calculate(base_input())
        ref = adapt_base_chart(base)
        self.assertEqual("bazi-deterministic-lichun-jie-noaa-v0.1", ref.base_method_id)
        self.assertTrue(ref.base_result_sha256.startswith("sha256:"))

        unsupported = dict(base, calculation_version="9.9.9")
        with self.assertRaisesRegex(DerivedContractError, "DERIVED_BASE_METHOD_UNSUPPORTED"):
            adapt_base_chart(unsupported)
        invalid = dict(base)
        invalid.pop("pillars")
        with self.assertRaisesRegex(DerivedContractError, "DERIVED_BASE_RESULT_INVALID"):
            adapt_base_chart(invalid)
        with self.assertRaisesRegex(DerivedContractError, "DERIVED_BASE_FINGERPRINT_MISMATCH"):
            adapt_base_chart(base, expected_pillar_fingerprint="sha256:wrong")

    def test_unknown_profile_and_local_paths_are_rejected(self) -> None:
        with self.assertRaisesRegex(DerivedContractError, "DERIVED_CONVENTION_UNSUPPORTED"):
            load_convention_profile("unknown")
        with self.assertRaisesRegex(ValueError, "absolute local path"):
            canonical_json({"source": "C:\\Users\\person\\fixture.json"})

    def test_complete_partial_and_refused_results_remain_non_predictive(self) -> None:
        base = adapt_base_chart(DeterministicBaziEngine().calculate(base_input()))
        profile = load_convention_profile("derived-static-r1@0.1")
        ambiguity = DependencyAmbiguity(
            dependency="base.pillars.hour",
            field_paths=("pillars.hour",),
            source_ids=("source-conflict",),
            message="基础时柱未决",
        )
        for status in ("complete", "partial", "refused"):
            result = DerivedChartResult(
                base_ref=base,
                convention_profile=profile,
                status=status,
                ambiguities=(ambiguity,) if status == "partial" else (),
                warnings=("基础盘未决",) if status == "partial" else (),
            )
            payload = result.to_dict()
            self.assertEqual(DERIVED_SCHEMA_VERSION, payload["schema_version"])
            self.assertEqual(DERIVED_METHOD_ID, payload["method_id"])
            self.assertEqual("not_evaluated", payload["prediction_validity"])
            self.assertEqual(digest(payload), digest(result))
            Draft202012Validator(get_schema("derived_chart_result.schema.json")).validate(payload)

        with self.assertRaises(ValueError):
            DerivedChartResult(base_ref=base, convention_profile=profile, status="partial")
        with self.assertRaises(TypeError):
            DerivedChartResult(  # type: ignore[call-arg]
                base_ref=base,
                convention_profile=profile,
                prediction_validity="evaluated",
            )

    def test_record_contracts_have_no_interpretation_fields(self) -> None:
        pillar = DerivedPillar(
            position="year",
            stem="甲",
            branch="子",
            stem_ten_god=TenGodRecord("authority_same_polarity", "七杀", ("a", "b")),
            hidden_stems=(HiddenStemRecord(1, "癸", TenGodRecord("wealth_opposite_polarity", "正财", ("a", "b"))),),
            nayin=NayinRecord("sea_gold", "海中金", ("a", "b")),
            xunkong=XunKongRecord("甲子", 1, ("戌", "亥"), ("a", "b")),
        )
        payload = pillar.to_dict()
        forbidden = {"good", "bad", "auspicious", "inauspicious", "personality", "wealth", "marriage", "career", "health", "prediction", "recommendation"}
        self.assertTrue(forbidden.isdisjoint(payload))

    def test_structured_error_schema(self) -> None:
        error = DerivedError(
            code="DERIVED_FIELD_NOT_AVAILABLE",
            message="字段不可用",
            field_path="pillars.hour",
            dependency="base.pillars.hour",
            method_id=DERIVED_METHOD_ID,
            profile_id="derived-static-r1@0.1",
        )
        Draft202012Validator(get_schema("derived_error.schema.json")).validate(error.to_dict())


class SourceAndPackagingTests(unittest.TestCase):
    def test_r1_capability_manifest_is_frozen(self) -> None:
        path = Path(__file__).parent / "fixtures" / "phase6_capability_manifest_v0.1.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("PHASE_6_R1_CONSERVATIVE_BOUNDARY_APPROVED", manifest["decision_id"])
        self.assertEqual(
            {"hidden_stems", "visible_stem_ten_gods", "hidden_stem_ten_gods", "nayin", "xunkong"},
            set(manifest["enabled"]),
        )
        self.assertFalse(manifest["unresolved_counts_as_pass"])
        self.assertEqual("not_evaluated", manifest["prediction_validity"])

    def test_source_manifest_has_independent_pairs(self) -> None:
        path = Path(__file__).parent / "fixtures" / "phase6_source_manifest_v0.1.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        result = validate_source_manifest(manifest)
        self.assertEqual((), result.issues)
        self.assertEqual(
            {"hidden_stems", "visible_stem_ten_gods", "hidden_stem_ten_gods", "nayin", "xunkong"},
            set(result.implementation_ready),
        )
        Draft202012Validator(get_schema("source_manifest.schema.json")).validate(manifest)

        same_group = json.loads(path.read_text(encoding="utf-8"))
        for source in same_group["sources"]:
            source["independence_group"] = "same"
        self.assertFalse(validate_source_manifest(same_group).implementation_ready)

    def test_all_schemas_self_validate_and_are_package_resources(self) -> None:
        names = {
            "base_chart_ref.schema.json",
            "derived_convention_profile.schema.json",
            "derived_chart_result.schema.json",
            "derived_error.schema.json",
            "source_manifest.schema.json",
        }
        for name in names:
            schema = get_schema(name)
            self.assertEqual("object", schema["type"])
            Draft202012Validator.check_schema(schema)

    def test_wheel_contains_readable_schemas(self) -> None:
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as temp:
            clean_env = {
                key: value
                for key, value in os.environ.items()
                if key.upper() in {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}
            }
            clean_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
            clean_env["PYTHONIOENCODING"] = "utf-8"
            clean_env["PYTHONUTF8"] = "1"
            temp_path = Path(temp).resolve()
            build_root = temp_path / "source"
            shutil.copytree(
                root,
                build_root,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".pytest_cache",
                    "__pycache__",
                    "build",
                    "dist",
                    "*.egg-info",
                ),
            )
            output = temp_path / "dist"
            subprocess.run(
                [sys.executable, "-m", "build", "--wheel", "--outdir", str(output)],
                cwd=build_root,
                env=clean_env,
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
            wheel = next(output.glob("*.whl"))
            subprocess.run(
                [sys.executable, "-m", "zipfile", "-l", str(wheel)],
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
            import zipfile

            with zipfile.ZipFile(wheel) as archive:
                packaged = {name for name in archive.namelist() if "/schemas/" in name and name.endswith(".json")}
            self.assertEqual(33, len(packaged))
            ziwei_schemas = {
                f"ziwei_{name}.schema.json"
                for name in (
                    "analysis_result",
                    "anonymous_case",
                    "birth_input",
                    "brightness",
                    "chart",
                    "fingerprint",
                    "palace",
                    "rule_card",
                    "star",
                    "temporal_context",
                    "time_correction",
                    "transformation",
                )
            }
            self.assertEqual(
                ziwei_schemas,
                {Path(name).name for name in packaged if Path(name).name.startswith("ziwei_")},
            )
            packaged_names = {Path(name).name for name in packaged}
            self.assertTrue({
                "product_runtime_input.schema.json",
                "product_runtime_envelope.schema.json",
                "training_case.schema.json",
                "analysis_run.schema.json",
                "user_feedback.schema.json",
                "outcome_observation.schema.json",
                "rule_review_candidate.schema.json",
                "training_iteration.schema.json",
            }.issubset(packaged_names))
            self.assertIn("mingli/contracts/schemas/phase16_domain_contract_result.schema.json", packaged)
            self.assertIn("mingli/contracts/schemas/real_case_intake.schema.json", packaged)
            self.assertIn("mingli/contracts/schemas/product_release_authorization.schema.json", packaged)
            with zipfile.ZipFile(wheel) as archive:
                self.assertIn(
                    "mingli/derived/data/ziwei_traditional_rules_v1.json",
                    archive.namelist(),
                )
            environment = temp_path / "installed"
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            subprocess.run(
                [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
                env=clean_env,
            )
            code = (
                "from mingli.contracts import get_schema; "
                "from mingli.derived import benchmark_static_mappings, derive_static_chart, "
                "load_packaged_capability_manifest, load_packaged_source_manifest; "
                "base={'method_id':'bazi-deterministic-lichun-jie-noaa-v0.1','calculation_version':'0.1.0',"
                "'pillars':{'year':'甲子','month':'丙寅','day':'戊辰','hour':'庚申'},'conventions':{'day_boundary':'00:00'}}; "
                "print('|'.join(["
                "get_schema('derived_chart_result.schema.json')['type'], "
                "load_packaged_capability_manifest()['decision_id'], "
                "load_packaged_source_manifest()['manifest_version'], "
                "str(benchmark_static_mappings().passed), "
                "derive_static_chart(base).status"
                "]))"
            )
            probe = subprocess.run(
                [str(python), "-I", "-c", code],
                cwd=temp_path,
                env=clean_env,
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
            self.assertEqual(
                "object|PHASE_6_R1_CONSERVATIVE_BOUNDARY_APPROVED|phase6-source-manifest@0.1|352|complete",
                probe.stdout.strip(),
            )


if __name__ == "__main__":
    unittest.main()
