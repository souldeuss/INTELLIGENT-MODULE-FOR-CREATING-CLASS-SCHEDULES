"""Automate DB-aligned compatible dataset generation and model activation.

Pipeline:
1) Export a reference case from current DB.
2) Generate/update compatible dataset from that reference.
3) Train/evaluate model with manifest.
4) Activate the newest trained model in both saved_models locations.
5) Run compatibility preflight load on the DB reference profile.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple


def _run(cmd: Iterable[str], *, cwd: Path, env: Dict[str, str]) -> None:
    command = [str(part) for part in cmd]
    print(f"[AUTO] RUN: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=str(cwd), env=env)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed (exit={completed.returncode}): {' '.join(command)}")


def _list_versioned_models(model_dir: Path) -> Set[str]:
    if not model_dir.exists():
        return set()
    return {path.name for path in model_dir.glob("actor_critic_*.pt")}


def _latest_model(model_dir: Path) -> Optional[str]:
    candidates = list(model_dir.glob("actor_critic_*.pt"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].name


def _extract_run_id(model_name: str) -> str:
    stem = Path(model_name).stem
    if not stem.startswith("actor_critic_"):
        raise ValueError(f"Unexpected model name format: {model_name}")
    return stem.replace("actor_critic_", "", 1)


def _load_json(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _sync_and_activate_model(workspace_root: Path, model_name: str) -> None:
    sys.path.insert(0, str(workspace_root / "backend"))
    try:
        from app.core.model_registry import set_active_model_name  # type: ignore
    finally:
        sys.path.pop(0)

    root_models = workspace_root / "saved_models"
    backend_models = workspace_root / "backend" / "saved_models"
    root_models.mkdir(parents=True, exist_ok=True)
    backend_models.mkdir(parents=True, exist_ok=True)

    source_model = root_models / model_name
    if not source_model.exists():
        backend_candidate = backend_models / model_name
        if backend_candidate.exists():
            source_model = backend_candidate
        else:
            raise FileNotFoundError(f"Trained model not found: {source_model}")

    root_target = root_models / model_name
    backend_target = backend_models / model_name

    # Keep both runtime locations aligned.
    if source_model.resolve() != root_target.resolve():
        shutil.copy2(source_model, root_target)
    if source_model.resolve() != backend_target.resolve():
        shutil.copy2(source_model, backend_target)

    run_id = _extract_run_id(model_name)
    meta_name = f"meta_{run_id}.json"
    root_meta = root_models / meta_name
    backend_meta = backend_models / meta_name
    if root_meta.exists() and root_meta.resolve() != backend_meta.resolve():
        shutil.copy2(root_meta, backend_meta)
    elif backend_meta.exists() and backend_meta.resolve() != root_meta.resolve():
        shutil.copy2(backend_meta, root_meta)

    set_active_model_name(root_models, model_name)
    set_active_model_name(backend_models, model_name)


def _run_preflight(workspace_root: Path, model_name: str, reference_case_rel: str) -> Tuple[int, int]:
    sys.path.insert(0, str(workspace_root / "backend"))
    try:
        from app.core.environment_v2 import TimetablingEnvironmentV2  # type: ignore
        from app.core.json_dataset import load_dataset_case  # type: ignore
        from app.core.ppo_trainer_v2 import PPOTrainerV2  # type: ignore
    finally:
        sys.path.pop(0)

    reference_path = workspace_root / reference_case_rel
    case = load_dataset_case(str(reference_path))
    env = TimetablingEnvironmentV2(
        case.courses,
        case.teachers,
        case.groups,
        case.classrooms,
        case.timeslots,
        course_teacher_map=case.course_teacher_map,
        course_group_map=case.course_group_map,
    )
    action_dim = min(env.n_courses * env.n_teachers * env.n_groups * env.n_classrooms * env.n_timeslots, 4096)
    _ = PPOTrainerV2(env, env.state_dim, action_dim, device="cpu", model_version=model_name)
    return env.state_dim, action_dim


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate compatibility training and activation pipeline")
    parser.add_argument("--workspace-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--python", default=sys.executable, help="Python executable for subprocess steps")

    parser.add_argument("--db-path", default="backend/timetabling.db", help="SQLite DB path used by backend")
    parser.add_argument("--reference-case", default="data/db_reference_case.json")

    parser.add_argument("--dataset-name", default="dataset_compatible_100")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.8)

    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--iterations-mode", choices=["per-case", "total"], default="total")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--promote", action="store_true", help="Enable policy-based promotion in training step")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_root = Path(args.workspace_root).resolve()

    env = os.environ.copy()
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = workspace_root / db_path
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    root_models = workspace_root / "saved_models"
    before_models = _list_versioned_models(root_models)

    _run(
        [
            args.python,
            "backend/export_db_reference_case.py",
            "--output",
            args.reference_case,
        ],
        cwd=workspace_root,
        env=env,
    )

    _run(
        [
            args.python,
            "backend/generate_compatible_datasets.py",
            "--workspace-root",
            str(workspace_root),
            "--reference-case",
            args.reference_case,
            "--dataset-name",
            args.dataset_name,
            "--count",
            str(args.count),
            "--seed",
            str(args.seed),
            "--train-ratio",
            str(args.train_ratio),
        ],
        cwd=workspace_root,
        env=env,
    )

    train_cmd = [
        args.python,
        "backend/train_eval_pipeline.py",
        "--manifest",
        f"data/{args.dataset_name}/dataset_manifest.json",
        "--iterations",
        str(args.iterations),
        "--iterations-mode",
        args.iterations_mode,
        "--device",
        args.device,
    ]
    if args.promote:
        train_cmd.append("--promote")

    _run(train_cmd, cwd=workspace_root, env=env)

    after_models = _list_versioned_models(root_models)
    created = sorted(after_models - before_models)
    if created:
        model_name = created[-1]
    else:
        model_name = _latest_model(root_models) or ""

    if not model_name:
        raise RuntimeError("No trained versioned model was found after training")

    _sync_and_activate_model(workspace_root, model_name)

    run_id = _extract_run_id(model_name)
    report_path = workspace_root / "backend" / "saved_models" / f"evaluation_report_{run_id}.json"
    summary: Dict[str, object] = {}
    if report_path.exists():
        summary = _load_json(report_path).get("summary", {})

    state_dim, action_dim = _run_preflight(workspace_root, model_name, args.reference_case)

    print("[AUTO] DONE")
    print(
        json.dumps(
            {
                "model": model_name,
                "active_model": model_name,
                "state_dim": state_dim,
                "action_dim": action_dim,
                "report": str(report_path) if report_path.exists() else None,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
