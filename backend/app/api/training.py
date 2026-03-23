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
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import logging

from ..core.training_metrics import get_metrics_collector, TrainingMetricsCollector
from ..core.checkpoint_manager import get_checkpoint_manager, CheckpointManager
from ..core.training_visualizer import TrainingVisualizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["Training"])


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
):
    """
    Отримати історію метрик.
    
    Args:
        metrics: Список метрик (policy_loss, value_loss, entropy, episode_reward, etc.)
        last_n: Кількість останніх записів
    """
    collector = get_metrics_collector()
    
    if metrics == "all":
        metric_names = None
    else:
        metric_names = [m.strip() for m in metrics.split(",")]
    
    history = collector.get_metrics_history(metric_names=metric_names, last_n=last_n)
    
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
        return {
            "active": False,
            "message": "No active training session",
            "checkpoints_available": len(checkpoint_mgr.checkpoints),
        }
    
    session = collector.current_session
    
    # Get last step metrics
    last_step = session.steps[-1] if session.steps else None
    
    # Calculate progress
    config = session.config
    total_iterations = config.get("num_iterations", 100)
    current_iteration = last_step.iteration if last_step else 0
    progress = (current_iteration / total_iterations) * 100
    
    # Stability analysis
    stability = collector.analyze_stability() if len(session.steps) >= 20 else {"stable": True}
    
    return {
        "active": session.status == "running",
        "session_id": session.session_id,
        "status": session.status,
        "progress": {
            "current_iteration": current_iteration,
            "total_iterations": total_iterations,
            "percentage": round(progress, 1),
        },
        "metrics": {
            "current_reward": last_step.episode_reward if last_step else 0,
            "best_reward": last_step.best_reward if last_step else 0,
            "hard_violations": last_step.hard_violations if last_step else 0,
            "learning_rate": last_step.learning_rate if last_step else 0,
        } if last_step else None,
        "stability": stability,
        "start_time": session.start_time,
        "checkpoints_saved": len(checkpoint_mgr.checkpoints),
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
