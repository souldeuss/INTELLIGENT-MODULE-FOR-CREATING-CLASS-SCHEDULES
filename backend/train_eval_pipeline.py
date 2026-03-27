"""Train/evaluate DRL model from JSON train/test dataset manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from app.core.environment_v2 import TimetablingEnvironmentV2

DEFAULT_SCORING: Dict[str, float] = {
    "reward_weight": 1.0,
    "completion_weight": 100.0,
    "hard_violation_penalty": 25.0,
    "soft_violation_penalty": 5.0,
}

DEFAULT_PROMOTION_POLICY: Dict[str, float] = {
    "min_completion_rate": 0.9,
    "max_hard_violations": 0,
    "max_soft_violations": 25,
    "min_score_margin": 0.0,
}


def _compute_action_dim(env: Any) -> int:
    raw = env.n_courses * env.n_teachers * env.n_groups * env.n_classrooms * env.n_timeslots
    return min(raw, 4096)


def _build_env(case_path: str) -> TimetablingEnvironmentV2:
    from app.core.environment_v2 import TimetablingEnvironmentV2
    from app.core.json_dataset import load_dataset_case

    case = load_dataset_case(case_path)
    return TimetablingEnvironmentV2(
        case.courses,
        case.teachers,
        case.groups,
        case.classrooms,
        case.timeslots,
        course_teacher_map=case.course_teacher_map,
        course_group_map=case.course_group_map,
    )


def _resolve_model_dir(root: Path) -> Path:
    candidates = [
        root / "saved_models",
        root / "backend" / "saved_models",
        root / "backend" / "backend" / "saved_models",
    ]

    for path in candidates:
        if (path / "actor_critic_best.pt").exists():
            return path

    for path in candidates:
        if path.exists():
            path.mkdir(parents=True, exist_ok=True)
            return path

    default_path = candidates[0]
    default_path.mkdir(parents=True, exist_ok=True)
    return default_path


def _set_global_seed(seed: int) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)

    try:
        import numpy as np  # type: ignore

        np.random.seed(seed)
    except ImportError:
        pass

    try:
        import torch  # type: ignore

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_manifest_entries(entries: Any, field_name: str) -> List[Dict[str, Any]]:
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"Manifest field '{field_name}' must be a non-empty list")

    normalized: List[Dict[str, Any]] = []
    for item in entries:
        if isinstance(item, str):
            normalized.append({"path": item, "sha256": None})
            continue

        if isinstance(item, dict) and isinstance(item.get("path"), str):
            normalized.append({"path": item["path"], "sha256": item.get("sha256")})
            continue

        raise ValueError(f"Invalid entry in '{field_name}'. Expected str or dict[path, sha256]")

    return normalized


def _validate_and_prepare_manifest(manifest: Dict[str, Any], root: Path) -> Dict[str, Any]:
    train_entries = _normalize_manifest_entries(manifest.get("train"), "train")
    test_entries = _normalize_manifest_entries(manifest.get("test"), "test")

    seed = int(manifest.get("seed", 42))
    manifest_version = str(manifest.get("manifest_version", "v1"))
    dataset_policy = str(manifest.get("dataset_policy", "train_test_holdout"))

    scoring = dict(DEFAULT_SCORING)
    scoring.update(manifest.get("scoring", {}))

    promotion_policy = dict(DEFAULT_PROMOTION_POLICY)
    promotion_policy.update(manifest.get("promotion_policy", {}))

    train_paths: List[str] = []
    test_paths: List[str] = []

    for entry in train_entries + test_entries:
        case_path = root / entry["path"]
        if not case_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {entry['path']}")

        actual_sha = _sha256_file(case_path)
        expected_sha = entry.get("sha256")
        if expected_sha and expected_sha != actual_sha:
            raise ValueError(
                f"Dataset hash mismatch for {entry['path']}: expected={expected_sha}, actual={actual_sha}"
            )
        entry["sha256"] = actual_sha

    train_paths.extend([entry["path"] for entry in train_entries])
    test_paths.extend([entry["path"] for entry in test_entries])

    return {
        "seed": seed,
        "manifest_version": manifest_version,
        "dataset_policy": dataset_policy,
        "scoring": scoring,
        "promotion_policy": promotion_policy,
        "train_entries": train_entries,
        "test_entries": test_entries,
        "train_files": train_paths,
        "test_files": test_paths,
    }


def _evaluate_promotion_policy(
    *,
    avg_model_score: float,
    avg_baseline_score: float,
    avg_completion: float,
    avg_hard_violations: float,
    avg_soft_violations: float,
    policy: Dict[str, float],
) -> tuple[bool, Dict[str, bool]]:
    score_margin = avg_model_score - avg_baseline_score
    criteria = {
        "score_margin_ok": score_margin >= float(policy["min_score_margin"]),
        "completion_ok": avg_completion >= float(policy["min_completion_rate"]),
        "hard_violations_ok": avg_hard_violations <= float(policy["max_hard_violations"]),
        "soft_violations_ok": avg_soft_violations <= float(policy["max_soft_violations"]),
    }
    return all(criteria.values()), criteria


def _greedy_fill(env: TimetablingEnvironmentV2) -> int:
    filled = 0
    max_attempts = len(env.pending_courses) * 2

    for _ in range(max_attempts):
        if not env.pending_courses:
            break

        course_idx, group_idx = env.pending_courses[0]
        found = False

        for teacher_idx in range(env.n_teachers):
            if found:
                break
            for classroom_idx in range(env.n_classrooms):
                if found:
                    break
                if env.classroom_capacities[classroom_idx] < env.group_sizes[group_idx]:
                    continue
                for timeslot_idx in range(env.n_timeslots):
                    if (
                        env.teacher_schedule[teacher_idx, timeslot_idx] > 0
                        or env.group_schedule[group_idx, timeslot_idx] > 0
                        or env.classroom_schedule[classroom_idx, timeslot_idx] > 0
                    ):
                        continue

                    action = (course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx)
                    env.teacher_schedule[teacher_idx, timeslot_idx] += 1
                    env.group_schedule[group_idx, timeslot_idx] += 1
                    env.classroom_schedule[classroom_idx, timeslot_idx] += 1
                    day = env.timeslot_days[timeslot_idx]
                    env.group_classes_per_day[group_idx, day] += 1
                    env.assignments_list.append(action)
                    env.pending_courses.remove((course_idx, group_idx))
                    filled += 1
                    found = True
                    break

        if not found:
            item = env.pending_courses.pop(0)
            env.pending_courses.append(item)

    return filled


def _run_baseline(case_path: str, score_weights: Dict[str, float]) -> Dict[str, float]:
    from app.core.ppo_trainer_v2 import PPOTrainerV2

    env = _build_env(case_path)
    env.reset()

    max_steps = env.total_classes_to_schedule + 100
    for _ in range(max_steps):
        if not env.pending_courses:
            break
        valid_actions = env.get_valid_actions()
        if not valid_actions:
            break
        _, _, done, _ = env.step(valid_actions[0])
        if done:
            break

    local_search_filled = 0
    if env.pending_courses:
        local_search_filled = env.run_local_search(max_iterations=200)
    greedy_filled = 0
    if env.pending_courses:
        greedy_filled = _greedy_fill(env)

    hard = env._count_hard_violations()
    soft = env._count_soft_violations()
    completion = len(env.assignments_list) / max(env.total_classes_to_schedule, 1)
    model_score = PPOTrainerV2.compute_model_score(
        reward=0.0,
        hard_violations=hard,
        soft_violations=soft,
        completion_rate=completion,
        score_weights=score_weights,
    )

    return {
        "completion_rate": completion,
        "hard_violations": hard,
        "soft_violations": soft,
        "local_search_filled": local_search_filled,
        "greedy_filled": greedy_filled,
        "score": model_score,
    }


def main() -> None:
    from app.core.model_registry import set_active_model_name
    from app.core.ppo_trainer_v2 import PPOTrainerV2

    parser = argparse.ArgumentParser(description="Train/evaluate DRL from JSON manifest")
    parser.add_argument("--manifest", default="data/dataset_manifest.sample.json")
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--promote", action="store_true", help="Activate trained model if evaluation passes")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    manifest_path = root / args.manifest

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    prepared_manifest = _validate_and_prepare_manifest(manifest, root)
    _set_global_seed(prepared_manifest["seed"])

    train_files: List[str] = prepared_manifest["train_files"]
    test_files: List[str] = prepared_manifest["test_files"]
    score_weights = prepared_manifest["scoring"]
    promotion_policy = prepared_manifest["promotion_policy"]

    train_reports: List[Dict[str, float]] = []
    for case in train_files:
        env = _build_env(str(root / case))
        trainer = PPOTrainerV2(
            env,
            env.state_dim,
            _compute_action_dim(env),
            device=args.device,
            score_weights=score_weights,
        )
        _, stats = trainer.train(num_iterations=args.iterations)
        train_reports.append(
            {
                "case": case,
                "best_reward": float(stats.get("best_reward", 0.0)),
                "best_model_score": float(stats.get("best_model_score", 0.0)),
                "best_completion": float(stats.get("best_completion", 0.0)),
            }
        )

    model_dir = _resolve_model_dir(root)
    best_alias_path = model_dir / "actor_critic_best.pt"
    if not best_alias_path.exists():
        raise FileNotFoundError(f"Expected best model artifact not found: {best_alias_path}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    versioned_name = f"actor_critic_{run_id}.pt"
    versioned_path = model_dir / versioned_name
    shutil.copy2(best_alias_path, versioned_path)

    meta_best = model_dir / "meta_best.json"
    if meta_best.exists():
        shutil.copy2(meta_best, model_dir / f"meta_{run_id}.json")

    test_reports: List[Dict[str, float]] = []
    baseline_reports: List[Dict[str, float]] = []

    for case in test_files:
        case_path = str(root / case)

        eval_env = _build_env(case_path)
        eval_trainer = PPOTrainerV2(
            eval_env,
            eval_env.state_dim,
            _compute_action_dim(eval_env),
            device=args.device,
            score_weights=score_weights,
            model_version=versioned_name,
        )
        _, eval_stats = eval_trainer.generate_schedule(use_local_search=True)

        eval_score = PPOTrainerV2.compute_model_score(
            reward=0.0,
            hard_violations=eval_stats.get("hard_violations", 0),
            soft_violations=eval_stats.get("soft_violations", 0),
            completion_rate=eval_stats.get("completion_rate", 0.0),
            score_weights=score_weights,
        )

        baseline = _run_baseline(case_path, score_weights)

        test_reports.append(
            {
                "case": case,
                "completion_rate": float(eval_stats.get("completion_rate", 0.0)),
                "hard_violations": int(eval_stats.get("hard_violations", 0)),
                "soft_violations": int(eval_stats.get("soft_violations", 0)),
                "score": float(eval_score),
            }
        )
        baseline_reports.append({"case": case, **baseline})

    avg_model_score = sum(item["score"] for item in test_reports) / max(len(test_reports), 1)
    avg_baseline_score = sum(item["score"] for item in baseline_reports) / max(len(baseline_reports), 1)
    avg_completion = sum(item["completion_rate"] for item in test_reports) / max(len(test_reports), 1)
    avg_hard_violations = sum(item["hard_violations"] for item in test_reports) / max(len(test_reports), 1)
    avg_soft_violations = sum(item["soft_violations"] for item in test_reports) / max(len(test_reports), 1)

    passed, criteria = _evaluate_promotion_policy(
        avg_model_score=avg_model_score,
        avg_baseline_score=avg_baseline_score,
        avg_completion=avg_completion,
        avg_hard_violations=avg_hard_violations,
        avg_soft_violations=avg_soft_violations,
        policy=promotion_policy,
    )

    if args.promote and passed:
        set_active_model_name(model_dir, versioned_name)

    report = {
        "run_id": run_id,
        "model_version": versioned_name,
        "train_reports": train_reports,
        "test_reports": test_reports,
        "baseline_reports": baseline_reports,
        "manifest": {
            "manifest_version": prepared_manifest["manifest_version"],
            "dataset_policy": prepared_manifest["dataset_policy"],
            "seed": prepared_manifest["seed"],
            "train_entries": prepared_manifest["train_entries"],
            "test_entries": prepared_manifest["test_entries"],
        },
        "summary": {
            "avg_model_score": avg_model_score,
            "avg_baseline_score": avg_baseline_score,
            "score_margin": avg_model_score - avg_baseline_score,
            "avg_completion_rate": avg_completion,
            "avg_hard_violations": avg_hard_violations,
            "avg_soft_violations": avg_soft_violations,
            "promotion_policy": promotion_policy,
            "criteria": criteria,
            "passed": passed,
            "promoted": bool(args.promote and passed),
        },
    }

    reports_dir = root / "backend" / "saved_models"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"evaluation_report_{run_id}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()
