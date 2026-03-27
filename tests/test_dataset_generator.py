from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

GENERATOR_MODULE_PATH = BACKEND / "dataset_generator.py"
GENERATOR_SPEC = importlib.util.spec_from_file_location("dataset_generator", GENERATOR_MODULE_PATH)
if GENERATOR_SPEC is None or GENERATOR_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {GENERATOR_MODULE_PATH}")

GENERATOR_MODULE = importlib.util.module_from_spec(GENERATOR_SPEC)
sys.modules["dataset_generator"] = GENERATOR_MODULE
GENERATOR_SPEC.loader.exec_module(GENERATOR_MODULE)

generate_dataset_package = GENERATOR_MODULE.generate_dataset_package

PIPELINE_MODULE_PATH = BACKEND / "train_eval_pipeline.py"
PIPELINE_SPEC = importlib.util.spec_from_file_location("train_eval_pipeline", PIPELINE_MODULE_PATH)
if PIPELINE_SPEC is None or PIPELINE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {PIPELINE_MODULE_PATH}")

PIPELINE_MODULE = importlib.util.module_from_spec(PIPELINE_SPEC)
sys.modules["train_eval_pipeline"] = PIPELINE_MODULE
PIPELINE_SPEC.loader.exec_module(PIPELINE_MODULE)

_validate_and_prepare_manifest = PIPELINE_MODULE._validate_and_prepare_manifest

JSON_DATASET_MODULE_PATH = BACKEND / "app" / "core" / "json_dataset.py"
JSON_DATASET_SPEC = importlib.util.spec_from_file_location("json_dataset", JSON_DATASET_MODULE_PATH)
if JSON_DATASET_SPEC is None or JSON_DATASET_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {JSON_DATASET_MODULE_PATH}")

JSON_DATASET_MODULE = importlib.util.module_from_spec(JSON_DATASET_SPEC)
sys.modules["json_dataset"] = JSON_DATASET_MODULE
JSON_DATASET_SPEC.loader.exec_module(JSON_DATASET_MODULE)

load_dataset_case = JSON_DATASET_MODULE.load_dataset_case


def test_generate_dataset_package_creates_expected_layout(tmp_path: Path) -> None:
    result = generate_dataset_package(
        workspace_root=tmp_path,
        dataset_name="dataset_100",
        count=20,
        seed=123,
        train_ratio=0.8,
    )

    dataset_root = result["dataset_root"]
    cases_dir = result["cases_dir"]
    manifest_path = result["manifest_path"]

    assert dataset_root.exists()
    assert cases_dir.exists()
    assert manifest_path.exists()

    case_files = sorted(cases_dir.glob("case_*.json"))
    assert len(case_files) == 20

    with open(manifest_path, "r", encoding="utf-8") as file:
        manifest = json.load(file)

    assert manifest["manifest_version"] == "v2"
    assert manifest["dataset_policy"] == "train_test_holdout"
    assert len(manifest["train"]) == 16
    assert len(manifest["test"]) == 4


def test_generated_manifest_is_compatible_with_train_eval_pipeline(tmp_path: Path) -> None:
    result = generate_dataset_package(
        workspace_root=tmp_path,
        dataset_name="dataset_compat",
        count=12,
        seed=77,
        train_ratio=0.75,
    )

    with open(result["manifest_path"], "r", encoding="utf-8") as file:
        manifest = json.load(file)

    prepared = _validate_and_prepare_manifest(manifest, tmp_path)

    assert len(prepared["train_files"]) == 9
    assert len(prepared["test_files"]) == 3
    assert all(entry.get("sha256") for entry in prepared["train_entries"])
    assert all(entry.get("sha256") for entry in prepared["test_entries"])


def test_generated_cases_load_with_json_dataset_loader(tmp_path: Path) -> None:
    result = generate_dataset_package(
        workspace_root=tmp_path,
        dataset_name="dataset_loader",
        count=6,
        seed=19,
        train_ratio=0.66,
    )

    case_files = sorted(result["cases_dir"].glob("case_*.json"))
    assert case_files, "Expected generated case files"

    for case_path in case_files:
        dataset_case = load_dataset_case(str(case_path))
        assert dataset_case.courses, "Courses should not be empty"
        assert dataset_case.teachers, "Teachers should not be empty"
        assert dataset_case.groups, "Groups should not be empty"
        assert dataset_case.classrooms, "Classrooms should not be empty"
        assert dataset_case.timeslots, "Timeslots should not be empty"
