"""
API endpoints для керування навчанням та моніторингу.

Endpoints:
- /training/metrics - Поточні метрики навчання
- /training/history - Історія метрик
- /training/hyperparameters - Перегляд/зміна гіперпараметрів
- /training/checkpoints - Список та управління checkpoints
- /training/visualizations - Графіки навчання
- /training/status - Статус навчання

Автор: AI Research Engineer
Дата: 2024-12-25
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import json
import logging
import subprocess
import sys
import re
from uuid import uuid4

from ..core.training_metrics import get_metrics_collector, TrainingMetricsCollector
from ..core.checkpoint_manager import get_checkpoint_manager, CheckpointManager
from ..core.training_visualizer import TrainingVisualizer
from ..core.model_registry import get_active_model_name, list_model_versions, set_active_model_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["Training"])

_preset_jobs: Dict[str, Dict[str, Any]] = {}


DAY_LABELS = {
    0: "Понеділок",
    1: "Вівторок",
    2: "Середа",
    3: "Четвер",
    4: "П'ятниця",
    5: "Субота",
    6: "Неділя",
}


def _pick_first(config: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in config and config.get(key) is not None:
            return config.get(key)
    return None


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_hyperparameters(config: Dict[str, Any]) -> Dict[str, Any]:
    safe_config = config if isinstance(config, dict) else {}

    return {
        "learning_rate": _as_float(
            _pick_first(safe_config, ["initial_lr", "learning_rate", "lr"]),
            3e-4,
        ),
        "gamma": _as_float(
            _pick_first(safe_config, ["gamma", "discount_factor"]),
            0.99,
        ),
        "epsilon": _as_float(
            _pick_first(safe_config, ["epsilon", "clip_range", "ppo_clip", "clip_epsilon"]),
            0.2,
        ),
        "batch_size": _as_int(
            _pick_first(safe_config, ["batch_size", "mini_batch_size", "batch"]),
            None,
        ),
        "gae_lambda": _as_float(
            _pick_first(safe_config, ["gae_lambda", "gae", "lambda"]),
            0.95,
        ),
        "entropy_coef": _as_float(
            _pick_first(safe_config, ["entropy_coef", "entropy_coefficient", "ent_coef"]),
            0.01,
        ),
        "value_coef": _as_float(
            _pick_first(safe_config, ["value_coef", "vf_coef", "value_loss_coef"]),
            0.5,
        ),
        "lr_scheduler": _pick_first(
            safe_config,
            ["lr_scheduler", "lr_scheduler_type", "scheduler", "scheduler_type"],
        ),
    }


def _seconds_to_hms(total_seconds: float) -> str:
    seconds = max(int(total_seconds), 0)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _build_best_checkpoint_summary(checkpoint_mgr: CheckpointManager) -> Optional[Dict[str, Any]]:
    if not checkpoint_mgr.checkpoints:
        return None

    best = max(checkpoint_mgr.checkpoints, key=lambda item: float(item.best_reward))
    return {
        "checkpoint_id": best.checkpoint_id,
        "iteration": int(best.iteration),
        "best_reward": float(best.best_reward),
        "created_at": best.created_at,
    }


def _build_session_summary(
    *,
    config: Dict[str, Any],
    current_iteration: int,
    total_iterations: int,
    elapsed_seconds: float,
    checkpoint_mgr: CheckpointManager,
) -> Dict[str, Any]:
    model_dir = _resolve_model_dir()
    active_model = get_active_model_name(model_dir)

    dataset_version = _pick_first(
        config,
        ["dataset_version", "dataset_name", "dataset_id", "dataset"],
    )
    if dataset_version is None:
        dataset_version = "unknown"

    manifest_path = _pick_first(config, ["dataset_manifest", "manifest_path"])

    model_version = _pick_first(config, ["model_version", "active_model", "model_name"])
    if model_version is None:
        model_version = active_model

    return {
        "dataset_version": str(dataset_version),
        "dataset_manifest": str(manifest_path) if manifest_path else None,
        "model_version": str(model_version),
        "epochs_completed": int(current_iteration),
        "epochs_total": int(total_iterations),
        "runtime_hms": _seconds_to_hms(elapsed_seconds),
        "best_checkpoint": _build_best_checkpoint_summary(checkpoint_mgr),
    }


def _read_latest_schedule_file() -> Optional[Path]:
    candidate_dirs = [
        Path("./saved_schedules"),
        Path("./backend/saved_schedules"),
        Path("./backend/backend/saved_schedules"),
    ]

    schedule_files: List[Path] = []
    for schedules_dir in candidate_dirs:
        if not schedules_dir.exists():
            continue
        schedule_files.extend(
            [p for p in schedules_dir.glob("schedule_*.json") if p.is_file()]
        )

    if not schedule_files:
        return None

    return max(schedule_files, key=lambda p: p.stat().st_mtime)


def _load_legacy_training_metrics() -> Optional[Dict[str, Any]]:
    candidate_files = [
        Path("./saved_models/training_metrics.json"),
        Path("./backend/saved_models/training_metrics.json"),
        Path("./backend/backend/saved_models/training_metrics.json"),
    ]

    for metrics_path in candidate_files:
        if not metrics_path.exists():
            continue
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("metrics"), dict):
                return data
        except Exception as e:
            logger.warning(f"Failed to read legacy metrics from {metrics_path}: {e}")

    return None


def _build_history_from_legacy(legacy_data: Dict[str, Any]) -> Dict[str, List[Any]]:
    metrics = legacy_data.get("metrics", {}) if isinstance(legacy_data, dict) else {}
    legacy_config = legacy_data.get("config", {}) if isinstance(legacy_data, dict) and isinstance(legacy_data.get("config"), dict) else {}

    rewards = metrics.get("rewards") if isinstance(metrics.get("rewards"), list) else []
    actor_losses = metrics.get("actor_losses") if isinstance(metrics.get("actor_losses"), list) else []
    critic_losses = metrics.get("critic_losses") if isinstance(metrics.get("critic_losses"), list) else []
    hard_violations = metrics.get("hard_violations") if isinstance(metrics.get("hard_violations"), list) else []
    soft_violations = metrics.get("soft_violations") if isinstance(metrics.get("soft_violations"), list) else []
    completion_rates = metrics.get("completion_rates") if isinstance(metrics.get("completion_rates"), list) else []

    series_lengths = [
        len(rewards),
        len(actor_losses),
        len(critic_losses),
        len(hard_violations),
        len(soft_violations),
        len(completion_rates),
    ]
    total_points = max(series_lengths) if series_lengths else 0

    def _fit(values: List[Any], fill: Any = None) -> List[Any]:
        result = list(values[:total_points])
        if len(result) < total_points:
            result.extend([fill] * (total_points - len(result)))
        return result

    rewards = _fit(rewards, None)
    actor_losses = _fit(actor_losses, None)
    critic_losses = _fit(critic_losses, None)
    hard_violations = _fit(hard_violations, None)
    soft_violations = _fit(soft_violations, None)
    completion_rates = _fit(completion_rates, None)

    average_reward: List[Optional[float]] = []
    running_sum = 0.0
    running_count = 0
    for reward in rewards:
        if isinstance(reward, (int, float)):
            running_sum += float(reward)
            running_count += 1
        average_reward.append((running_sum / running_count) if running_count else None)

    total_loss: List[Optional[float]] = []
    for policy_loss, value_loss in zip(actor_losses, critic_losses):
        if isinstance(policy_loss, (int, float)) and isinstance(value_loss, (int, float)):
            total_loss.append(float(policy_loss) + float(value_loss))
        else:
            total_loss.append(None)

    default_lr = legacy_config.get("initial_lr", legacy_config.get("learning_rate"))
    if not isinstance(default_lr, (int, float)):
        default_lr = 3e-4

    history = {
        "iteration": list(range(total_points)),
        "policy_loss": actor_losses,
        "value_loss": critic_losses,
        "total_loss": total_loss,
        "episode_reward": rewards,
        "average_reward": average_reward,
        "learning_rate": [float(default_lr)] * total_points,
        "hard_violations": hard_violations,
        "soft_violations": soft_violations,
        "completion_rate": completion_rates,
    }

    history.update(_derive_success_series(hard_violations))
    return history


def _extract_run_id(model_version: str) -> Optional[str]:
    match = re.search(r"(\d{8}_\d{6})", model_version or "")
    return match.group(1) if match else None


def _resolve_evaluation_report(model_version: str) -> Optional[Path]:
    run_id = _extract_run_id(model_version)
    if not run_id:
        return None

    candidate_files = [
        Path(f"./saved_models/evaluation_report_{run_id}.json"),
        Path(f"./backend/saved_models/evaluation_report_{run_id}.json"),
        Path(f"./backend/backend/saved_models/evaluation_report_{run_id}.json"),
    ]

    for report_path in candidate_files:
        if report_path.exists():
            return report_path
    return None


def _build_history_from_evaluation_report(report_data: Dict[str, Any]) -> Dict[str, List[Any]]:
    reports = report_data.get("train_reports") if isinstance(report_data.get("train_reports"), list) else []

    rewards: List[Optional[float]] = []
    completion_rate: List[Optional[float]] = []
    success_count: List[int] = []
    success_rate: List[Optional[float]] = []
    hard_violations: List[Optional[int]] = []
    soft_violations: List[Optional[int]] = []

    cumulative_success = 0
    for idx, item in enumerate(reports):
        reward = item.get("best_reward")
        reward_value = float(reward) if isinstance(reward, (int, float)) else None
        rewards.append(reward_value)

        completion = item.get("best_completion")
        completion_percent: Optional[float] = None
        if isinstance(completion, (int, float)):
            raw_completion = float(completion)
            completion_percent = raw_completion * 100.0 if raw_completion <= 1.0 else raw_completion
            if raw_completion >= 0.999:
                cumulative_success += 1
        success_count.append(cumulative_success)
        success_rate.append(round((cumulative_success / (idx + 1)) * 100.0, 2))
        completion_rate.append(completion_percent)

        hard_value = item.get("hard_violations")
        soft_value = item.get("soft_violations")
        hard_violations.append(int(hard_value) if isinstance(hard_value, (int, float)) else None)
        soft_violations.append(int(soft_value) if isinstance(soft_value, (int, float)) else None)

    average_reward: List[Optional[float]] = []
    running_sum = 0.0
    running_count = 0
    for reward in rewards:
        if isinstance(reward, (int, float)):
            running_sum += float(reward)
            running_count += 1
        average_reward.append((running_sum / running_count) if running_count else None)

    total_points = len(rewards)

    return {
        "iteration": list(range(total_points)),
        "policy_loss": [None] * total_points,
        "value_loss": [None] * total_points,
        "total_loss": [None] * total_points,
        "episode_reward": rewards,
        "average_reward": average_reward,
        "learning_rate": [None] * total_points,
        "hard_violations": hard_violations,
        "soft_violations": soft_violations,
        "completion_rate": completion_rate,
        "success_count": success_count,
        "success_rate": success_rate,
    }


def _get_history_by_model_version(model_version: str) -> Dict[str, Any]:
    model_dir = _resolve_model_dir()
    active_model = get_active_model_name(model_dir)
    selected_model = model_version if model_version.endswith(".pt") else f"{model_version}.pt"

    collector = get_metrics_collector()

    # Active model may have live collector data.
    if selected_model == active_model:
        live_history = collector.get_metrics_history(metric_names=None, last_n=None)
        has_live_data = any(isinstance(v, list) and len(v) > 0 for v in live_history.values())
        if has_live_data:
            return live_history

    report_path = _resolve_evaluation_report(selected_model)
    if report_path:
        with open(report_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)
        return _build_history_from_evaluation_report(report_data)

    if selected_model == active_model:
        legacy_data = _load_legacy_training_metrics()
        if legacy_data:
            return _build_history_from_legacy(legacy_data)

    raise HTTPException(
        status_code=404,
        detail=f"Історію метрик для моделі '{selected_model}' не знайдено",
    )


def _derive_success_series(hard_violations: List[Any]) -> Dict[str, List[Any]]:
    """Build cumulative success count and success rate by iteration.

    Success criterion: hard_violations == 0.
    """
    success_count: List[int] = []
    success_rate: List[Optional[float]] = []

    cumulative_success = 0
    observed = 0

    for value in hard_violations:
        if isinstance(value, (int, float)):
            observed += 1
            if int(value) == 0:
                cumulative_success += 1

        success_count.append(cumulative_success)
        if observed > 0:
            success_rate.append(round((cumulative_success / observed) * 100.0, 2))
        else:
            success_rate.append(None)

    return {
        "success_count": success_count,
        "success_rate": success_rate,
    }


def _resolve_model_dir() -> Path:
    root = _workspace_root()
    candidates = [
        root / "saved_models",
        root / "backend" / "saved_models",
        root / "backend" / "backend" / "saved_models",
    ]

    existing: List[Path] = [path for path in candidates if path.exists()]
    if existing:
        # Prefer the directory with the largest number of versioned artifacts.
        # This keeps UI model lists complete even when backend cwd differs.
        ranked = sorted(
            existing,
            key=lambda p: (
                len(list(p.glob("actor_critic_*.pt"))),
                max((f.stat().st_mtime for f in p.glob("actor_critic_*.pt")), default=0.0),
            ),
            reverse=True,
        )
        selected = ranked[0]
        selected.mkdir(parents=True, exist_ok=True)
        return selected

    default_path = candidates[0]
    default_path.mkdir(parents=True, exist_ok=True)
    return default_path


# === Pydantic Models ===

class HyperparameterUpdate(BaseModel):
    """Запит на оновлення гіперпараметра."""
    parameter: str = Field(..., description="Ім'я параметра (learning_rate, gamma, epsilon, etc.)")
    value: float = Field(..., description="Нове значення")
    reason: str = Field("", description="Причина зміни (опціонально)")


class HyperparameterConfig(BaseModel):
    """Конфігурація гіперпараметрів."""
    learning_rate: Optional[float] = Field(None, ge=1e-7, le=1e-1)
    gamma: Optional[float] = Field(None, ge=0.9, le=1.0)
    epsilon: Optional[float] = Field(None, ge=0.05, le=0.5)
    gae_lambda: Optional[float] = Field(None, ge=0.8, le=1.0)
    entropy_coef: Optional[float] = Field(None, ge=0.0, le=0.1)
    value_coef: Optional[float] = Field(None, ge=0.1, le=1.0)


class CheckpointInfo(BaseModel):
    """Інформація про checkpoint."""
    checkpoint_id: str
    created_at: str
    iteration: int
    best_reward: float
    current_reward: float
    hard_violations: int
    description: str
    tags: List[str]


class TrainingConfig(BaseModel):
    """Конфігурація тренування."""
    num_iterations: int = Field(100, ge=10, le=10000)
    lr_scheduler_type: str = Field("combined", description="linear, cosine, plateau, combined")
    initial_lr: float = Field(3e-4, ge=1e-6, le=1e-2)
    warmup_ratio: float = Field(0.1, ge=0.0, le=0.5)
    auto_save_interval: int = Field(50, ge=10, le=500)


class ActivateModelRequest(BaseModel):
    model_name: str = Field(..., description="Назва файлу моделі, наприклад actor_critic_20260327_120000.pt")


class Dataset100PresetRequest(BaseModel):
    iterations: int = Field(100, ge=10, le=10000)
    seed: int = Field(42)
    train_ratio: float = Field(0.8, gt=0.0, lt=1.0)
    dataset_name: str = Field("dataset_100")
    device: str = Field("cpu")
    promote: bool = Field(False)
    regenerate_dataset: bool = Field(True)


class ModelTrainingRequest(BaseModel):
    iterations: int = Field(100, ge=10, le=10000)
    seed: int = Field(42)
    train_ratio: float = Field(0.8, gt=0.0, lt=1.0)
    dataset_size_mode: str = Field("100", description="100 | 1000 | compatible_100 | compatible_1000 | custom")
    custom_case_count: Optional[int] = Field(None, ge=2, le=10000)
    dataset_name: Optional[str] = Field(None)
    device: str = Field("cpu")
    promote: bool = Field(False)
    regenerate_dataset: bool = Field(True)
    iterations_mode: str = Field("total", description="total | per-case")


def _resolve_dataset_selection(payload: ModelTrainingRequest) -> Dict[str, Any]:
    mode = (payload.dataset_size_mode or "").strip().lower()
    if mode not in {"100", "1000", "compatible_100", "compatible_1000", "custom"}:
        raise HTTPException(
            status_code=400,
            detail="dataset_size_mode must be one of: 100, 1000, compatible_100, compatible_1000, custom",
        )

    if mode == "100":
        case_count = 100
    elif mode == "1000":
        case_count = 1000
    elif mode == "compatible_100":
        case_count = 100
    elif mode == "compatible_1000":
        case_count = 1000
    else:
        if payload.custom_case_count is None:
            raise HTTPException(status_code=400, detail="custom_case_count is required when dataset_size_mode=custom")
        case_count = int(payload.custom_case_count)

    default_dataset_name = f"dataset_{case_count}"
    if mode == "compatible_100":
        default_dataset_name = "dataset_compatible_100"
    elif mode == "compatible_1000":
        default_dataset_name = "dataset_compatible_1000"

    dataset_name = (payload.dataset_name or default_dataset_name).strip()
    if not dataset_name:
        dataset_name = default_dataset_name

    iterations_mode = (payload.iterations_mode or "total").strip().lower()
    if iterations_mode not in {"total", "per-case"}:
        raise HTTPException(status_code=400, detail="iterations_mode must be one of: total, per-case")

    return {
        "dataset_name": dataset_name,
        "case_count": case_count,
        "iterations_mode": iterations_mode,
    }


def _start_model_training_job(payload: ModelTrainingRequest) -> Dict[str, Any]:
    from dataset_generator import generate_dataset_package

    root = _workspace_root()
    dataset_info = _resolve_dataset_selection(payload)
    dataset_name = dataset_info["dataset_name"]
    case_count = dataset_info["case_count"]
    iterations_mode = dataset_info["iterations_mode"]
    dataset_mode = (payload.dataset_size_mode or "").strip().lower()

    manifest_path = root / "data" / dataset_name / "dataset_manifest.json"

    if dataset_mode in {"compatible_100", "compatible_1000"}:
        if not manifest_path.exists():
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Compatible dataset manifest not found: {manifest_path}. "
                    "Generate it first with backend/generate_compatible_datasets.py or switch dataset mode."
                ),
            )
    elif payload.regenerate_dataset or not manifest_path.exists():
        generate_dataset_package(
            workspace_root=root,
            dataset_name=dataset_name,
            count=case_count,
            seed=payload.seed,
            train_ratio=payload.train_ratio,
        )

    job_id = uuid4().hex
    logs_dir = root / "backend" / "training_metrics" / "preset_runs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"model_training_{job_id}.log"

    manifest_rel = manifest_path.relative_to(root).as_posix()
    command: List[str] = [
        sys.executable,
        "backend/train_eval_pipeline.py",
        "--manifest",
        manifest_rel,
        "--iterations",
        str(payload.iterations),
        "--iterations-mode",
        iterations_mode,
        "--device",
        payload.device,
    ]
    if payload.promote:
        command.append("--promote")

    log_file = open(log_path, "a", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=str(root),
        stdout=log_file,
        stderr=log_file,
        text=True,
    )

    _preset_jobs[job_id] = {
        "process": process,
        "log_file": log_file,
        "log_path": str(log_path),
        "created_at": datetime.now().isoformat(),
        "command": command,
        "manifest": manifest_rel,
        "dataset_name": dataset_name,
        "dataset_size_mode": payload.dataset_size_mode,
        "dataset_size": case_count,
        "iterations": payload.iterations,
        "iterations_mode": iterations_mode,
        "seed": payload.seed,
    }

    return {
        "job_id": job_id,
        "status": "running",
        "pid": process.pid,
        "manifest": manifest_rel,
        "dataset_name": dataset_name,
        "dataset_size_mode": payload.dataset_size_mode,
        "dataset_size": case_count,
        "iterations": payload.iterations,
        "iterations_mode": iterations_mode,
        "seed": payload.seed,
        "command": command,
        "log_path": str(log_path),
    }


def _start_dataset_100_preset_job(payload: Dataset100PresetRequest) -> Dict[str, Any]:
    generic_payload = ModelTrainingRequest(
        iterations=payload.iterations,
        seed=payload.seed,
        train_ratio=payload.train_ratio,
        dataset_size_mode="100",
        custom_case_count=100,
        dataset_name=payload.dataset_name,
        device=payload.device,
        promote=payload.promote,
        regenerate_dataset=payload.regenerate_dataset,
        iterations_mode="total",
    )
    return _start_model_training_job(generic_payload)


def _read_training_job(job_id: str) -> Dict[str, Any]:
    job = _preset_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Preset job not found")

    process: subprocess.Popen[str] = job["process"]
    return_code = process.poll()
    status = "running" if return_code is None else ("completed" if return_code == 0 else "failed")
    if job.get("stopped"):
        status = "stopped"

    if return_code is not None:
        log_file = job.get("log_file")
        if log_file and not log_file.closed:
            log_file.close()

    progress = _extract_dataset_100_preset_progress(job.get("log_path"), status)

    return {
        "job_id": job_id,
        "status": status,
        "pid": process.pid,
        "return_code": return_code,
        "created_at": job.get("created_at"),
        "stopped_at": job.get("stopped_at"),
        "dataset_name": job.get("dataset_name"),
        "manifest": job.get("manifest"),
        "iterations": job.get("iterations"),
        "iterations_mode": job.get("iterations_mode"),
        "seed": job.get("seed"),
        "dataset_size_mode": job.get("dataset_size_mode"),
        "dataset_size": job.get("dataset_size"),
        "command": job.get("command"),
        "log_path": job.get("log_path"),
        **progress,
    }


def _stop_training_job(job_id: str) -> Dict[str, Any]:
    job = _preset_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")

    process: subprocess.Popen[str] = job["process"]
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    log_file = job.get("log_file")
    if log_file and not log_file.closed:
        log_file.close()

    job["stopped"] = True
    job["stopped_at"] = datetime.now().isoformat()
    return _read_training_job(job_id)


def _read_dataset_100_preset_job(job_id: str) -> Dict[str, Any]:
    return _read_training_job(job_id)


def _read_log_tail_text(log_path: str, max_bytes: int = 256 * 1024) -> str:
    path = Path(log_path)
    if not path.exists() or not path.is_file():
        return ""

    with open(path, "rb") as file:
        file.seek(0, 2)
        file_size = file.tell()
        offset = max(file_size - max_bytes, 0)
        file.seek(offset)
        data = file.read()

    # Keep parser resilient to mixed encodings and terminal control bytes.
    return data.decode("utf-8", errors="ignore")


def _extract_dataset_100_preset_progress(log_path: Optional[str], status: str) -> Dict[str, Any]:
    if not log_path:
        return {}

    text = _read_log_tail_text(log_path)
    if not text:
        if status == "completed":
            return {"progress_percent": 100.0}
        return {}

    plan_matches = re.findall(r"\[PRESET_PROGRESS\]\s+TRAIN_PLAN\s+cases=(\d+)\s+effective_iterations=(\d+)\s+mode=([a-z\-]+)", text)
    start_matches = re.findall(r"\[PRESET_PROGRESS\]\s+TRAIN_START\s+case=(\d+)/(\d+)\s+iterations=(\d+)", text)
    done_matches = re.findall(r"\[PRESET_PROGRESS\]\s+TRAIN_DONE\s+case=(\d+)/(\d+)", text)
    result_matches = re.findall(
        r"\[PRESET_PROGRESS\]\s+TRAIN_RESULT\s+run_id=([^\s]+)\s+model_version=([^\s]+)",
        text,
    )

    total_cases = 0
    effective_iterations = None
    iterations_mode = None
    if plan_matches:
        last_plan = plan_matches[-1]
        total_cases = int(last_plan[0])
        effective_iterations = int(last_plan[1])
        iterations_mode = last_plan[2]

    if total_cases == 0 and start_matches:
        total_cases = int(start_matches[-1][1])
    if total_cases == 0 and done_matches:
        total_cases = int(done_matches[-1][1])

    done_cases = max((int(item[0]) for item in done_matches), default=0)
    current_case = max((int(item[0]) for item in start_matches), default=0)

    if status == "completed" and total_cases > 0:
        done_cases = total_cases
    elif status == "completed" and total_cases == 0:
        return {
            "progress_percent": 100.0,
            "effective_iterations": effective_iterations,
            "iterations_mode": iterations_mode,
        }

    progress_percent = None
    remaining_cases = None
    if total_cases > 0:
        if status == "completed":
            progress_percent = 100.0
            remaining_cases = 0
        else:
            # Report progress by completed train cases to avoid over-promising mid-case completion.
            progress_percent = round((done_cases / total_cases) * 100.0, 2)
            remaining_cases = max(total_cases - done_cases, 0)

    return {
        "cases_total": total_cases if total_cases > 0 else None,
        "cases_done": done_cases,
        "current_case": current_case if current_case > 0 else None,
        "remaining_cases": remaining_cases,
        "progress_percent": progress_percent,
        "effective_iterations": effective_iterations,
        "iterations_mode": iterations_mode,
        "run_id": result_matches[-1][0] if result_matches else None,
        "model_version": result_matches[-1][1] if result_matches else None,
    }


@router.post("/presets/dataset-100/start")
async def start_dataset_100_preset(payload: Dataset100PresetRequest):
    """One-call preset: generate dataset-100 (optional) and launch train/eval pipeline."""
    try:
        return _start_dataset_100_preset_job(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start dataset-100 preset: {e}")


@router.post("/models/create")
async def create_model_training_job(payload: ModelTrainingRequest):
    """Створити та запустити нову модель: підготовка датасету + запуск train/eval пайплайну."""
    try:
        return _start_model_training_job(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start model training: {e}")


@router.get("/models/create/jobs")
async def list_model_training_jobs():
    """Список усіх модельних тренувальних job-ів."""
    return {
        "jobs": [_read_training_job(job_id) for job_id in list(_preset_jobs.keys())]
    }


@router.get("/models/create/status/{job_id}")
async def get_model_training_status(job_id: str):
    """Статус тренувального job для створення моделі."""
    return _read_training_job(job_id)


@router.post("/models/create/stop/{job_id}")
async def stop_model_training_job(job_id: str):
    """Явна зупинка тренувального job створення моделі."""
    return _stop_training_job(job_id)


@router.get("/presets/dataset-100/jobs")
async def list_dataset_100_preset_jobs():
    """List all preset jobs with current state."""
    return {
        "jobs": [_read_dataset_100_preset_job(job_id) for job_id in list(_preset_jobs.keys())]
    }


@router.get("/presets/dataset-100/status/{job_id}")
async def get_dataset_100_preset_status(job_id: str):
    """Get status for a dataset-100 preset job."""
    return _read_dataset_100_preset_job(job_id)


# === Metrics Endpoints ===

@router.get("/metrics")
async def get_current_metrics():
    """
    Отримати поточні метрики навчання.
    
    Повертає:
    - Поточну ітерацію
    - Policy loss, value loss, entropy
    - Reward (episode, average, best)
    - Learning rate
    - Violations
    """
    collector = get_metrics_collector()
    metrics = collector.get_current_metrics()
    
    return JSONResponse(content=metrics)


@router.get("/metrics/history")
async def get_metrics_history(
    metrics: str = Query("all", description="Список метрик через кому або 'all'"),
    last_n: int = Query(None, ge=1, le=10000, description="Останні N записів"),
    model_version: Optional[str] = Query(None, description="Назва моделі для історії (наприклад actor_critic_20260327_234422.pt)"),
):
    """
    Отримати історію метрик.
    
    Args:
        metrics: Список метрик (policy_loss, value_loss, entropy, episode_reward, etc.)
        last_n: Кількість останніх записів
    """
    if metrics == "all":
        metric_names = None
    else:
        metric_names = [m.strip() for m in metrics.split(",")]

    if model_version:
        history = _get_history_by_model_version(model_version)
    else:
        collector = get_metrics_collector()
        history = collector.get_metrics_history(metric_names=metric_names, last_n=last_n)

        has_live_data = any(isinstance(v, list) and len(v) > 0 for v in history.values())
        if not has_live_data:
            legacy_data = _load_legacy_training_metrics()
            if legacy_data:
                history = _build_history_from_legacy(legacy_data)

    if isinstance(last_n, int) and last_n > 0:
        for key, values in list(history.items()):
            if isinstance(values, list) and key != "iteration":
                history[key] = values[-last_n:]
        if isinstance(history.get("iteration"), list):
            history["iteration"] = list(range(len(history.get("episode_reward", history["iteration"]))))

    needs_success_metrics = metric_names is None or any(
        key in metric_names for key in ["success_count", "success_rate"]
    )
    if needs_success_metrics and "hard_violations" in history and "success_count" not in history:
        hard_violations = history.get("hard_violations")
        if isinstance(hard_violations, list):
            history.update(_derive_success_series(hard_violations))

    if metric_names:
        history = {
            key: value
            for key, value in history.items()
            if key in metric_names or key == "iteration"
        }
    
    if model_version:
        history["model_version"] = model_version

    return JSONResponse(content=history)


@router.get("/metrics/summary")
async def get_training_summary():
    """
    Отримати summary навчання.
    
    Повертає:
    - Статистику rewards (initial, final, best, mean, std)
    - Статистику losses
    - Learning rate history
    - Violations
    """
    collector = get_metrics_collector()
    summary = collector.get_training_summary()
    
    return JSONResponse(content=summary)


@router.get("/metrics/stability")
async def analyze_stability(
    window_size: int = Query(20, ge=5, le=100, description="Розмір вікна аналізу"),
):
    """
    Аналіз стабільності навчання.
    
    Повертає:
    - stable: True/False
    - variance: Variance reward
    - trend: Тренд loss
    - issues: Список проблем
    """
    collector = get_metrics_collector()
    stability = collector.analyze_stability(window_size=window_size)
    
    return JSONResponse(content=stability)


# === Hyperparameters Endpoints ===

@router.post("/hyperparameters")
async def update_hyperparameter(update: HyperparameterUpdate):
    """
    Оновити гіперпараметр під час навчання.
    
    Підтримувані параметри:
    - learning_rate: Learning rate optimizer'а
    - gamma: Discount factor
    - epsilon: PPO clip range
    - gae_lambda: GAE lambda
    - entropy_coef: Entropy coefficient
    - value_coef: Value loss coefficient
    
    Зміни застосовуються на наступній ітерації з контролем стабільності.
    """
    checkpoint_mgr = get_checkpoint_manager()
    
    success = checkpoint_mgr.request_hyperparameter_update(
        parameter=update.parameter,
        new_value=update.value,
        reason=update.reason,
    )
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid parameter: {update.parameter}. "
                   f"Valid: learning_rate, gamma, epsilon, gae_lambda, entropy_coef, value_coef"
        )
    
    return {
        "status": "queued",
        "message": f"Update queued: {update.parameter} → {update.value}",
        "will_apply_on": "next_iteration",
    }


@router.get("/hyperparameters/history")
async def get_hyperparameter_history(
    last_n: int = Query(50, ge=1, le=500),
):
    """
    Отримати історію змін гіперпараметрів.
    """
    checkpoint_mgr = get_checkpoint_manager()
    
    history = checkpoint_mgr.hyperparameter_history[-last_n:]
    
    return {
        "total_changes": len(checkpoint_mgr.hyperparameter_history),
        "history": [
            {
                "parameter": h.parameter,
                "old_value": h.old_value,
                "new_value": h.new_value,
                "timestamp": h.timestamp,
                "reason": h.reason,
            }
            for h in history
        ]
    }


# === Checkpoints Endpoints ===

@router.get("/checkpoints")
async def list_checkpoints(
    min_reward: float = Query(None, description="Мінімальний reward"),
    tags: str = Query(None, description="Теги через кому"),
):
    """
    Отримати список збережених checkpoints.
    """
    checkpoint_mgr = get_checkpoint_manager()
    
    tag_list = tags.split(",") if tags else None
    
    checkpoints = checkpoint_mgr.get_checkpoint_list(
        tags=tag_list,
        min_reward=min_reward,
    )
    
    return {
        "total": len(checkpoints),
        "checkpoints": [
            {
                "checkpoint_id": c.checkpoint_id,
                "created_at": c.created_at,
                "iteration": c.iteration,
                "best_reward": c.best_reward,
                "current_reward": c.current_reward,
                "hard_violations": c.hard_violations,
                "learning_rate": c.learning_rate,
                "description": c.description,
                "tags": c.tags or [],
            }
            for c in checkpoints
        ]
    }


@router.get("/checkpoints/{checkpoint_id}")
async def get_checkpoint_details(checkpoint_id: str):
    """
    Отримати детальну інформацію про checkpoint.
    """
    checkpoint_mgr = get_checkpoint_manager()
    
    checkpoints = [c for c in checkpoint_mgr.checkpoints if c.checkpoint_id == checkpoint_id]
    
    if not checkpoints:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    
    checkpoint = checkpoints[0]
    
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "created_at": checkpoint.created_at,
        "iteration": checkpoint.iteration,
        "best_reward": checkpoint.best_reward,
        "current_reward": checkpoint.current_reward,
        "hard_violations": checkpoint.hard_violations,
        "state_dim": checkpoint.state_dim,
        "action_dim": checkpoint.action_dim,
        "model_architecture": checkpoint.model_architecture,
        "learning_rate": checkpoint.learning_rate,
        "gamma": checkpoint.gamma,
        "epsilon": checkpoint.epsilon,
        "gae_lambda": checkpoint.gae_lambda,
        "scheduler_type": checkpoint.scheduler_type,
        "scheduler_step": checkpoint.scheduler_step,
        "description": checkpoint.description,
        "tags": checkpoint.tags or [],
    }


@router.delete("/checkpoints/{checkpoint_id}")
async def delete_checkpoint(checkpoint_id: str):
    """
    Видалити checkpoint.
    """
    checkpoint_mgr = get_checkpoint_manager()
    
    try:
        checkpoint_mgr.delete_checkpoint(checkpoint_id)
        return {"status": "deleted", "checkpoint_id": checkpoint_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/models")
async def get_model_versions():
    """Список доступних версій моделей і активна версія."""
    model_dir = _resolve_model_dir()
    active_model = get_active_model_name(model_dir)
    versions = list_model_versions(model_dir)

    return {
        "model_dir": str(model_dir),
        "active_model": active_model,
        "total": len(versions),
        "versions": versions,
    }


@router.get("/models/active")
async def get_active_model():
    """Отримати активну версію моделі для генерації."""
    model_dir = _resolve_model_dir()
    active_model = get_active_model_name(model_dir)
    model_path = model_dir / active_model

    return {
        "model_dir": str(model_dir),
        "active_model": active_model,
        "exists": model_path.exists(),
    }


@router.post("/models/activate")
async def activate_model(request: ActivateModelRequest):
    """Встановити активну версію моделі для наступних запусків генерації."""
    model_dir = _resolve_model_dir()

    try:
        payload = set_active_model_name(model_dir, request.model_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "ok",
        "model_dir": str(model_dir),
        **payload,
    }


# === Visualizations Endpoints ===

@router.get("/visualizations/dashboard")
async def get_dashboard_image():
    """
    Отримати dashboard як base64 PNG.
    """
    collector = get_metrics_collector()
    
    if not collector.current_session or not collector.current_session.steps:
        return {"error": "No training data available"}
    
    visualizer = TrainingVisualizer()
    
    try:
        img_base64 = visualizer.get_plot_as_base64(
            collector.current_session,
            plot_type="dashboard"
        )
        
        return {
            "image": img_base64,
            "format": "png",
            "encoding": "base64",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/visualizations/{plot_type}")
async def get_visualization(
    plot_type: str,
):
    """
    Отримати конкретний графік як base64 PNG.
    
    Типи графіків:
    - losses: Policy loss, value loss, entropy
    - rewards: Episode, average, best reward
    - learning_rate: LR schedule
    - violations: Hard/soft violations
    - stability: Variance analysis
    - dashboard: Комплексний dashboard
    """
    valid_types = ["losses", "rewards", "learning_rate", "violations", "stability", "dashboard"]
    
    if plot_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plot type. Valid: {valid_types}"
        )
    
    collector = get_metrics_collector()
    
    if not collector.current_session or not collector.current_session.steps:
        return {"error": "No training data available"}
    
    visualizer = TrainingVisualizer()
    
    try:
        img_base64 = visualizer.get_plot_as_base64(
            collector.current_session,
            plot_type=plot_type
        )
        
        return {
            "image": img_base64,
            "format": "png",
            "encoding": "base64",
            "plot_type": plot_type,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/visualizations/chart-data")
async def get_chart_data():
    """
    Отримати дані для побудови інтерактивних графіків (Chart.js, Plotly).
    
    Повертає JSON з:
    - labels: Ітерації
    - datasets: Дані для кожної метрики з кольорами
    - summary: Загальна статистика
    """
    collector = get_metrics_collector()
    
    if not collector.current_session or not collector.current_session.steps:
        return {"error": "No training data available"}
    
    visualizer = TrainingVisualizer()
    chart_data = visualizer.get_chart_data_json(collector.current_session)
    
    return JSONResponse(content=chart_data)


# === Training Status Endpoint ===

@router.get("/status")
async def get_training_status():
    """
    Отримати загальний статус навчання.
    
    Повертає:
    - Чи активне навчання
    - Поточний прогрес
    - Останні метрики
    - Стабільність
    """
    collector = get_metrics_collector()
    checkpoint_mgr = get_checkpoint_manager()
    
    if not collector.current_session:
        legacy_data = _load_legacy_training_metrics()
        if legacy_data:
            history = _build_history_from_legacy(legacy_data)
            total_points = len(history.get("iteration", []))
            legacy_config = legacy_data.get("config", {}) if isinstance(legacy_data.get("config"), dict) else {}
            normalized_hyperparameters = _normalize_hyperparameters(legacy_config)

            if total_points > 0:
                last_idx = total_points - 1

                def _last_numeric(values: List[Any], default: float = 0.0) -> float:
                    if not values:
                        return default
                    value = values[last_idx]
                    return float(value) if isinstance(value, (int, float)) else default

                best_reward = max(
                    [float(v) for v in history.get("episode_reward", []) if isinstance(v, (int, float))],
                    default=0.0,
                )

                return {
                    "active": False,
                    "message": "No active training session. Showing last saved training snapshot.",
                    "status": "completed",
                    "timing": {
                        "elapsed_seconds": 0,
                        "elapsed_hms": "00:00:00",
                        "estimated_remaining_seconds": None,
                        "estimated_remaining_hms": None,
                        "avg_time_per_iteration": None,
                    },
                    "progress": {
                        "current_iteration": total_points,
                        "total_iterations": total_points,
                        "percentage": 100.0,
                    },
                    "hyperparameters": {
                        **normalized_hyperparameters,
                    },
                    "session_summary": _build_session_summary(
                        config=legacy_config,
                        current_iteration=total_points,
                        total_iterations=total_points,
                        elapsed_seconds=0.0,
                        checkpoint_mgr=checkpoint_mgr,
                    ),
                    "metrics": {
                        "current_reward": _last_numeric(history.get("episode_reward", [])),
                        "best_reward": best_reward,
                        "hard_violations": int(_last_numeric(history.get("hard_violations", []), 0.0)),
                        "soft_violations": int(_last_numeric(history.get("soft_violations", []), 0.0)),
                        "successful_generations": int(_last_numeric(history.get("success_count", []), 0.0)),
                        "success_rate": _last_numeric(history.get("success_rate", [])),
                        "completion_rate": _last_numeric(history.get("completion_rate", [])),
                        "policy_loss": _last_numeric(history.get("policy_loss", [])),
                        "value_loss": _last_numeric(history.get("value_loss", [])),
                        "total_loss": _last_numeric(history.get("total_loss", [])),
                        "learning_rate": _last_numeric(
                            history.get("learning_rate", []),
                            float(normalized_hyperparameters.get("learning_rate", 3e-4)),
                        ),
                    },
                    "checkpoints_available": len(checkpoint_mgr.checkpoints),
                }

        return {
            "active": False,
            "message": "No active training session",
            "session_summary": {
                "dataset_version": "unknown",
                "dataset_manifest": None,
                "model_version": get_active_model_name(_resolve_model_dir()),
                "epochs_completed": 0,
                "epochs_total": 0,
                "runtime_hms": "00:00:00",
                "best_checkpoint": _build_best_checkpoint_summary(checkpoint_mgr),
            },
            "checkpoints_available": len(checkpoint_mgr.checkpoints),
        }
    
    session = collector.current_session
    
    # Get last step metrics
    last_step = session.steps[-1] if session.steps else None

    successful_generations = 0
    success_rate = 0.0
    if session.steps:
        successful_generations = sum(1 for step in session.steps if step.hard_violations == 0)
        success_rate = round((successful_generations / len(session.steps)) * 100.0, 2)
    
    # Calculate progress
    config = session.config
    total_iterations = config.get("num_iterations", 100)
    current_iteration = session.total_iterations if session.total_iterations else (last_step.iteration + 1 if last_step else 0)
    progress = (current_iteration / total_iterations) * 100

    # Calculate elapsed and ETA (EMA or advanced smoothing can be added later)
    elapsed_seconds = 0.0
    estimated_remaining_seconds = None
    avg_time_per_iteration = None
    try:
        start_dt = datetime.fromisoformat(session.start_time)
        elapsed_seconds = max((datetime.now() - start_dt).total_seconds(), 0.0)
        if current_iteration > 0:
            avg_time_per_iteration = elapsed_seconds / current_iteration
            remaining_iterations = max(total_iterations - current_iteration, 0)
            estimated_remaining_seconds = remaining_iterations * avg_time_per_iteration
    except Exception:
        # Keep API resilient even if session timestamp is malformed
        elapsed_seconds = 0.0
    
    # Stability analysis
    stability = collector.analyze_stability() if len(session.steps) >= 20 else {"stable": True}
    
    return {
        "active": session.status == "running",
        "session_id": session.session_id,
        "status": session.status,
        "timing": {
            "elapsed_seconds": round(elapsed_seconds, 2),
            "elapsed_hms": _seconds_to_hms(elapsed_seconds),
            "estimated_remaining_seconds": round(estimated_remaining_seconds, 2) if estimated_remaining_seconds is not None else None,
            "estimated_remaining_hms": _seconds_to_hms(estimated_remaining_seconds) if estimated_remaining_seconds is not None else None,
            "avg_time_per_iteration": round(avg_time_per_iteration, 4) if avg_time_per_iteration is not None else None,
        },
        "progress": {
            "current_iteration": current_iteration,
            "total_iterations": total_iterations,
            "percentage": round(progress, 1),
        },
        "hyperparameters": {
            **_normalize_hyperparameters(config),
        },
        "session_summary": _build_session_summary(
            config=config,
            current_iteration=current_iteration,
            total_iterations=total_iterations,
            elapsed_seconds=elapsed_seconds,
            checkpoint_mgr=checkpoint_mgr,
        ),
        "metrics": {
            "current_reward": last_step.episode_reward if last_step else 0,
            "best_reward": last_step.best_reward if last_step else 0,
            "hard_violations": last_step.hard_violations if last_step else 0,
            "soft_violations": last_step.soft_violations if last_step else 0,
            "successful_generations": successful_generations,
            "success_rate": success_rate,
            "completion_rate": last_step.completion_rate if last_step else 0,
            "policy_loss": last_step.policy_loss if last_step else 0,
            "value_loss": last_step.value_loss if last_step else 0,
            "total_loss": last_step.total_loss if last_step else 0,
            "learning_rate": last_step.learning_rate if last_step else 0,
        } if last_step else None,
        "stability": stability,
        "start_time": session.start_time,
        "checkpoints_saved": len(checkpoint_mgr.checkpoints),
    }


@router.get("/best-schedule-preview")
async def get_best_schedule_preview(
    max_rows: int = Query(20, ge=5, le=100, description="Максимальна кількість рядків у mini-table"),
):
    """
    Отримати preview найкращого знайденого розкладу для dashboard.

    Повертає:
    - heatmap (day x period)
    - mini table (короткий список занять)
    - метадані джерела
    """
    latest_file = _read_latest_schedule_file()
    if not latest_file:
        return {
            "available": False,
            "message": "No saved schedules found",
            "heatmap": [],
            "table": [],
        }

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        classes = data.get("classes", [])
        meta = data.get("meta", {})

        # Heatmap aggregation by (day_of_week, period_number)
        counts: Dict[str, int] = {}
        periods = set()

        for item in classes:
            day = item.get("day_of_week")
            period = item.get("period_number")
            if isinstance(day, int) and isinstance(period, int):
                key = f"{day}:{period}"
                counts[key] = counts.get(key, 0) + 1
                periods.add(period)

        sorted_periods = sorted(periods) if periods else list(range(1, 7))
        heatmap = []
        for day in range(5):
            for period in sorted_periods:
                key = f"{day}:{period}"
                heatmap.append({
                    "day": day,
                    "day_label": DAY_LABELS.get(day, str(day)),
                    "period": period,
                    "count": counts.get(key, 0),
                })

        # Compact rows for mini-table
        table_rows = []
        for item in classes[:max_rows]:
            day = item.get("day_of_week")
            table_rows.append({
                "course": item.get("course_code") or item.get("course_name") or "N/A",
                "teacher": item.get("teacher_name") or "N/A",
                "group": item.get("group_code") or "N/A",
                "room": item.get("classroom_code") or "N/A",
                "day": day,
                "day_label": DAY_LABELS.get(day, str(day)) if isinstance(day, int) else "N/A",
                "period": item.get("period_number"),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
            })

        return {
            "available": len(classes) > 0,
            "source_file": latest_file.name,
            "updated_at": datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat(),
            "meta": {
                "generation_id": meta.get("generation_id"),
                "best_reward": meta.get("best_reward"),
                "hard_violations": meta.get("hard_violations"),
                "soft_violations": meta.get("soft_violations"),
                "classes_count": len(classes),
            },
            "heatmap": heatmap,
            "table": table_rows,
        }
    except Exception as e:
        logger.warning("Failed to build schedule preview from %s: %s", latest_file, e)
        return {
            "available": False,
            "message": f"Schedule preview temporarily unavailable: {e}",
            "source_file": latest_file.name,
            "heatmap": [],
            "table": [],
        }


# === Sessions Endpoints ===

@router.get("/sessions")
async def list_training_sessions():
    """
    Отримати список збережених сесій навчання.
    """
    metrics_dir = Path("./backend/training_metrics")
    
    if not metrics_dir.exists():
        return {"sessions": []}

    model_dir = _resolve_model_dir()
    available_model_names = {item.get("name") for item in list_model_versions(model_dir)}

    def _extract_model_version(payload: Dict[str, Any], file_name: str) -> Optional[str]:
        if not isinstance(payload, dict):
            return None

        direct_candidates = [
            payload.get("model_version"),
            payload.get("active_model"),
            payload.get("model_name"),
        ]

        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        summary = payload.get("session_summary") if isinstance(payload.get("session_summary"), dict) else {}
        nested_candidates = [
            config.get("model_version"),
            config.get("active_model"),
            config.get("model_name"),
            summary.get("model_version"),
        ]

        for candidate in direct_candidates + nested_candidates:
            if isinstance(candidate, str) and candidate.strip():
                normalized = candidate.strip()
                normalized = normalized if normalized.endswith(".pt") else f"{normalized}.pt"
                if normalized in available_model_names:
                    return normalized

        run_id = _extract_run_id(str(payload.get("session_id") or "")) or _extract_run_id(file_name)
        if run_id:
            inferred = f"actor_critic_{run_id}.pt"
            if inferred in available_model_names:
                return inferred

        return None

    def _extract_dataset_version(payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        summary = payload.get("session_summary") if isinstance(payload.get("session_summary"), dict) else {}
        for value in [
            payload.get("dataset_version"),
            config.get("dataset_version"),
            config.get("dataset_name"),
            config.get("dataset"),
            summary.get("dataset_version"),
        ]:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    
    sessions = []
    for file in metrics_dir.glob("metrics_*.json"):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id"),
                    "start_time": data.get("start_time"),
                    "end_time": data.get("end_time"),
                    "status": data.get("status"),
                    "total_iterations": data.get("total_iterations"),
                    "best_reward": data.get("best_reward"),
                    "model_version": _extract_model_version(data, file.name),
                    "dataset_version": _extract_dataset_version(data),
                    "file": file.name,
                })
        except Exception as e:
            logger.warning(f"Error reading session file {file}: {e}")
    
    # Sort by start time (newest first)
    sessions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    """
    Отримати детальну інформацію про сесію навчання.
    """
    metrics_dir = Path("./backend/training_metrics")
    session_file = metrics_dir / f"metrics_{session_id}.json"
    
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    
    with open(session_file, 'r') as f:
        data = json.load(f)
    
    return JSONResponse(content=data)


# === LR Scheduler Info ===

@router.get("/lr-schedulers")
async def get_available_lr_schedulers():
    """
    Отримати інформацію про доступні LR schedulers.
    """
    return {
        "schedulers": [
            {
                "type": "linear",
                "name": "Linear Decay",
                "description": "Лінійне зменшення LR від початкового до мінімального",
                "best_for": "Фіксована кількість ітерацій",
                "parameters": ["total_steps", "min_lr", "warmup_steps"],
            },
            {
                "type": "exponential",
                "name": "Exponential Decay",
                "description": "Експоненційне зменшення: LR *= decay_rate кожні N кроків",
                "best_for": "Швидка конвергенція на початку",
                "parameters": ["decay_rate", "decay_steps", "min_lr"],
            },
            {
                "type": "cosine",
                "name": "Cosine Annealing",
                "description": "Косинусне згасання з теплими рестартами",
                "best_for": "PPO та інші policy gradient методи",
                "parameters": ["T_max", "T_mult", "min_lr", "warmup_steps"],
                "recommended": True,
            },
            {
                "type": "plateau",
                "name": "Reduce on Plateau",
                "description": "Зменшення LR при стагнації reward",
                "best_for": "Невідома оптимальна кількість ітерацій",
                "parameters": ["patience", "factor", "threshold", "min_lr"],
            },
            {
                "type": "combined",
                "name": "Combined (Recommended)",
                "description": "Warmup + Cosine Annealing + Plateau Detection",
                "best_for": "Production використання",
                "parameters": ["warmup_ratio", "plateau_patience", "min_lr"],
                "recommended": True,
                "default": True,
            },
        ]
    }
