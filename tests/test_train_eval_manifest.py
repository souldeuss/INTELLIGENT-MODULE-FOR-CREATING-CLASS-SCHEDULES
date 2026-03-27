from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

MODULE_PATH = BACKEND / "train_eval_pipeline.py"
SPEC = importlib.util.spec_from_file_location("train_eval_pipeline", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {MODULE_PATH}")

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

_evaluate_promotion_policy = MODULE._evaluate_promotion_policy
_normalize_manifest_entries = MODULE._normalize_manifest_entries
_sha256_file = MODULE._sha256_file
_validate_and_prepare_manifest = MODULE._validate_and_prepare_manifest


def test_normalize_manifest_entries_supports_string_and_object() -> None:
    entries = _normalize_manifest_entries(
        [
            "data/a.json",
            {"path": "data/b.json", "sha256": "abc"},
        ],
        "train",
    )

    assert entries == [
        {"path": "data/a.json", "sha256": None},
        {"path": "data/b.json", "sha256": "abc"},
    ]


def test_validate_manifest_computes_hashes(tmp_path: Path) -> None:
    train_file = tmp_path / "train.json"
    test_file = tmp_path / "test.json"
    train_file.write_text('{"ok": true}', encoding="utf-8")
    test_file.write_text('{"ok": true}', encoding="utf-8")

    manifest = {
        "manifest_version": "v2",
        "dataset_policy": "train_test_holdout",
        "seed": 7,
        "train": [{"path": "train.json", "sha256": _sha256_file(train_file)}],
        "test": ["test.json"],
        "scoring": {"completion_weight": 120.0},
        "promotion_policy": {"min_completion_rate": 0.95},
    }

    prepared = _validate_and_prepare_manifest(manifest, tmp_path)

    assert prepared["seed"] == 7
    assert prepared["train_files"] == ["train.json"]
    assert prepared["test_files"] == ["test.json"]
    assert prepared["train_entries"][0]["sha256"] == _sha256_file(train_file)
    assert prepared["test_entries"][0]["sha256"] == _sha256_file(test_file)
    assert prepared["scoring"]["completion_weight"] == 120.0
    assert prepared["promotion_policy"]["min_completion_rate"] == 0.95


def test_validate_manifest_rejects_hash_mismatch(tmp_path: Path) -> None:
    train_file = tmp_path / "train.json"
    test_file = tmp_path / "test.json"
    train_file.write_text('{"ok": true}', encoding="utf-8")
    test_file.write_text('{"ok": true}', encoding="utf-8")

    manifest = {
        "train": [{"path": "train.json", "sha256": "deadbeef"}],
        "test": ["test.json"],
    }

    with pytest.raises(ValueError, match="Dataset hash mismatch"):
        _validate_and_prepare_manifest(manifest, tmp_path)


def test_evaluate_promotion_policy_checks_all_thresholds() -> None:
    passed, criteria = _evaluate_promotion_policy(
        avg_model_score=85.0,
        avg_baseline_score=80.0,
        avg_completion=0.92,
        avg_hard_violations=0.0,
        avg_soft_violations=20.0,
        policy={
            "min_completion_rate": 0.9,
            "max_hard_violations": 0.0,
            "max_soft_violations": 25.0,
            "min_score_margin": 1.0,
        },
    )

    assert passed is True
    assert all(criteria.values())

    failed, failed_criteria = _evaluate_promotion_policy(
        avg_model_score=80.5,
        avg_baseline_score=80.0,
        avg_completion=0.89,
        avg_hard_violations=1.0,
        avg_soft_violations=40.0,
        policy={
            "min_completion_rate": 0.9,
            "max_hard_violations": 0.0,
            "max_soft_violations": 25.0,
            "min_score_margin": 1.0,
        },
    )

    assert failed is False
    assert failed_criteria["score_margin_ok"] is False
    assert failed_criteria["completion_ok"] is False
    assert failed_criteria["hard_violations_ok"] is False
    assert failed_criteria["soft_violations_ok"] is False
