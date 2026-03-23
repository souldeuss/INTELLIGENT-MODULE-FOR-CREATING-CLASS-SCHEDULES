"""
Модуль збору та аналізу метрик навчання.

Збирає та зберігає:
- Policy Loss
- Value Loss  
- Entropy
- Reward (episode, average, best)
- Learning Rate
- Gradient Norms
- Training Variance / Stability

Забезпечує:
- Логування на кожній ітерації/епосі
- Експорт в JSON для GUI
- Статистичний аналіз стабільності

Автор: AI Research Engineer
Дата: 2024-12-25
"""
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import deque
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import logging
import threading

logger = logging.getLogger(__name__)


@dataclass
class TrainingStep:
    """Метрики одного кроку навчання."""
    iteration: int
    timestamp: str
    
    # Core metrics
    policy_loss: float
    value_loss: float
    entropy: float
    total_loss: float
    
    # Reward metrics
    episode_reward: float
    average_reward: float
    best_reward: float
    
    # Learning metrics
    learning_rate: float
    gradient_norm: Optional[float] = None
    
    # PPO specific
    clip_fraction: Optional[float] = None  # Частка кліпованих оновлень
    approx_kl: Optional[float] = None      # Приблизна KL divergence
    
    # Environment metrics
    hard_violations: int = 0
    soft_violations: int = 0
    completion_rate: float = 0.0
    
    # Stability metrics
    reward_variance: Optional[float] = None
    loss_variance: Optional[float] = None


@dataclass
class TrainingSession:
    """Повна сесія навчання."""
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    
    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Steps
    steps: List[TrainingStep] = field(default_factory=list)
    
    # Final results
    final_reward: Optional[float] = None
    best_reward: Optional[float] = None
    total_iterations: int = 0
    training_time_seconds: float = 0.0
    
    # Status
    status: str = "running"  # running, completed, stopped, failed
    stop_reason: Optional[str] = None


class TrainingMetricsCollector:
    """
    Колектор метрик навчання з thread-safe операціями.
    
    Використання:
        collector = TrainingMetricsCollector()
        collector.start_session(config)
        
        for iteration in range(num_iterations):
            # ... training ...
            collector.log_step(iteration, policy_loss, value_loss, ...)
        
        collector.end_session()
        collector.save_to_file("metrics.json")
    """
    
    def __init__(
        self,
        history_size: int = 100,
        metrics_dir: Path = None,
    ):
        """
        Args:
            history_size: Розмір буфера для moving averages
            metrics_dir: Директорія для збереження метрик
        """
        self.history_size = history_size
        self.metrics_dir = metrics_dir or Path("./backend/training_metrics")
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Current session
        self.current_session: Optional[TrainingSession] = None
        
        # Rolling buffers for statistics
        self.reward_buffer = deque(maxlen=history_size)
        self.policy_loss_buffer = deque(maxlen=history_size)
        self.value_loss_buffer = deque(maxlen=history_size)
        self.lr_buffer = deque(maxlen=history_size)
        
        # Best tracking
        self.best_reward = float('-inf')
        self.best_iteration = 0
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Real-time callbacks (for GUI)
        self._callbacks: List[callable] = []
        
    def add_callback(self, callback: callable):
        """Додати callback для real-time оновлень."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: callable):
        """Видалити callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def start_session(self, config: Dict[str, Any] = None) -> str:
        """
        Почати нову сесію навчання.
        
        Args:
            config: Конфігурація навчання (hyperparameters)
            
        Returns:
            session_id
        """
        with self._lock:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            self.current_session = TrainingSession(
                session_id=session_id,
                start_time=datetime.now().isoformat(),
                config=config or {},
            )
            
            # Reset buffers
            self.reward_buffer.clear()
            self.policy_loss_buffer.clear()
            self.value_loss_buffer.clear()
            self.lr_buffer.clear()
            self.best_reward = float('-inf')
            self.best_iteration = 0
            
            logger.info(f"📊 Розпочато сесію збору метрик: {session_id}")
            return session_id
    
    def log_step(
        self,
        iteration: int,
        policy_loss: float,
        value_loss: float,
        entropy: float,
        episode_reward: float,
        learning_rate: float,
        hard_violations: int = 0,
        soft_violations: int = 0,
        completion_rate: float = 0.0,
        gradient_norm: float = None,
        clip_fraction: float = None,
        approx_kl: float = None,
    ):
        """
        Логувати метрики одного кроку.
        
        Викликати після кожної ітерації навчання.
        """
        with self._lock:
            if self.current_session is None:
                logger.warning("No active session. Call start_session() first.")
                return
            
            # Update buffers
            self.reward_buffer.append(episode_reward)
            self.policy_loss_buffer.append(policy_loss)
            self.value_loss_buffer.append(value_loss)
            self.lr_buffer.append(learning_rate)
            
            # Calculate statistics
            avg_reward = np.mean(self.reward_buffer)
            reward_variance = np.var(self.reward_buffer) if len(self.reward_buffer) > 1 else 0.0
            loss_variance = np.var(self.policy_loss_buffer) if len(self.policy_loss_buffer) > 1 else 0.0
            
            # Update best
            if episode_reward > self.best_reward:
                self.best_reward = episode_reward
                self.best_iteration = iteration
            
            # Create step record
            step = TrainingStep(
                iteration=iteration,
                timestamp=datetime.now().isoformat(),
                policy_loss=float(policy_loss),
                value_loss=float(value_loss),
                entropy=float(entropy),
                total_loss=float(policy_loss + 0.5 * value_loss - 0.01 * entropy),
                episode_reward=float(episode_reward),
                average_reward=float(avg_reward),
                best_reward=float(self.best_reward),
                learning_rate=float(learning_rate),
                gradient_norm=float(gradient_norm) if gradient_norm else None,
                clip_fraction=float(clip_fraction) if clip_fraction else None,
                approx_kl=float(approx_kl) if approx_kl else None,
                hard_violations=hard_violations,
                soft_violations=soft_violations,
                completion_rate=completion_rate,
                reward_variance=float(reward_variance),
                loss_variance=float(loss_variance),
            )
            
            self.current_session.steps.append(step)
            self.current_session.total_iterations = iteration + 1
            
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(step)
                except Exception as e:
                    logger.warning(f"Callback error: {e}")
    
    def end_session(
        self,
        status: str = "completed",
        stop_reason: str = None,
    ):
        """
        Завершити сесію навчання.
        
        Args:
            status: Статус завершення (completed, stopped, failed)
            stop_reason: Причина зупинки (для early stopping)
        """
        with self._lock:
            if self.current_session is None:
                return
            
            self.current_session.end_time = datetime.now().isoformat()
            self.current_session.status = status
            self.current_session.stop_reason = stop_reason
            self.current_session.final_reward = float(self.reward_buffer[-1]) if self.reward_buffer else None
            self.current_session.best_reward = float(self.best_reward)
            
            # Calculate training time
            start = datetime.fromisoformat(self.current_session.start_time)
            end = datetime.fromisoformat(self.current_session.end_time)
            self.current_session.training_time_seconds = (end - start).total_seconds()
            
            logger.info(
                f"📊 Сесію завершено: {self.current_session.session_id} | "
                f"Status: {status} | Best: {self.best_reward:.2f}"
            )
    
    def save_to_file(self, filename: str = None) -> Path:
        """
        Зберегти метрики у файл.
        
        Args:
            filename: Ім'я файлу (або автоматична генерація)
            
        Returns:
            Шлях до збереженого файлу
        """
        with self._lock:
            if self.current_session is None:
                raise ValueError("No session to save")
            
            if filename is None:
                filename = f"metrics_{self.current_session.session_id}.json"
            
            filepath = self.metrics_dir / filename
            
            # Convert to dict
            data = {
                "session_id": self.current_session.session_id,
                "start_time": self.current_session.start_time,
                "end_time": self.current_session.end_time,
                "config": self.current_session.config,
                "status": self.current_session.status,
                "stop_reason": self.current_session.stop_reason,
                "total_iterations": self.current_session.total_iterations,
                "training_time_seconds": self.current_session.training_time_seconds,
                "final_reward": self.current_session.final_reward,
                "best_reward": self.current_session.best_reward,
                "steps": [asdict(step) for step in self.current_session.steps],
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📊 Метрики збережено: {filepath}")
            return filepath
    
    def load_from_file(self, filepath: Path) -> TrainingSession:
        """Завантажити метрики з файлу."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        steps = [
            TrainingStep(**step_data) 
            for step_data in data.get("steps", [])
        ]
        
        session = TrainingSession(
            session_id=data["session_id"],
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            config=data.get("config", {}),
            steps=steps,
            final_reward=data.get("final_reward"),
            best_reward=data.get("best_reward"),
            total_iterations=data.get("total_iterations", 0),
            training_time_seconds=data.get("training_time_seconds", 0),
            status=data.get("status", "unknown"),
            stop_reason=data.get("stop_reason"),
        )
        
        return session
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Отримати поточні метрики (для GUI).
        
        Returns:
            Dict з поточними метриками
        """
        with self._lock:
            if not self.current_session or not self.current_session.steps:
                return {
                    "status": "no_data",
                    "current_iteration": 0,
                }
            
            last_step = self.current_session.steps[-1]
            
            return {
                "status": self.current_session.status,
                "session_id": self.current_session.session_id,
                "current_iteration": last_step.iteration,
                "policy_loss": last_step.policy_loss,
                "value_loss": last_step.value_loss,
                "entropy": last_step.entropy,
                "episode_reward": last_step.episode_reward,
                "average_reward": last_step.average_reward,
                "best_reward": last_step.best_reward,
                "learning_rate": last_step.learning_rate,
                "hard_violations": last_step.hard_violations,
                "reward_variance": last_step.reward_variance,
                "training_time": self._get_elapsed_time(),
            }
    
    def get_metrics_history(
        self, 
        metric_names: List[str] = None,
        last_n: int = None,
    ) -> Dict[str, List[float]]:
        """
        Отримати історію метрик.
        
        Args:
            metric_names: Список метрик для отримання (або всі)
            last_n: Останні N кроків (або всі)
            
        Returns:
            Dict {metric_name: [values]}
        """
        with self._lock:
            if not self.current_session:
                return {}
            
            steps = self.current_session.steps
            if last_n:
                steps = steps[-last_n:]
            
            if metric_names is None:
                metric_names = [
                    "policy_loss", "value_loss", "entropy", 
                    "episode_reward", "average_reward", "learning_rate",
                    "hard_violations", "reward_variance",
                ]
            
            result = {"iteration": [s.iteration for s in steps]}
            
            for name in metric_names:
                result[name] = [getattr(s, name, None) for s in steps]
            
            return result
    
    def get_training_summary(self) -> Dict[str, Any]:
        """
        Отримати summary навчання.
        
        Returns:
            Dict зі статистикою навчання
        """
        with self._lock:
            if not self.current_session or not self.current_session.steps:
                return {"status": "no_data"}
            
            steps = self.current_session.steps
            rewards = [s.episode_reward for s in steps]
            losses = [s.policy_loss for s in steps]
            
            return {
                "session_id": self.current_session.session_id,
                "status": self.current_session.status,
                "total_iterations": len(steps),
                "training_time_seconds": self._get_elapsed_time(),
                
                # Reward statistics
                "reward": {
                    "initial": rewards[0] if rewards else None,
                    "final": rewards[-1] if rewards else None,
                    "best": self.best_reward,
                    "best_iteration": self.best_iteration,
                    "mean": float(np.mean(rewards)) if rewards else None,
                    "std": float(np.std(rewards)) if rewards else None,
                    "improvement": (rewards[-1] - rewards[0]) if len(rewards) > 1 else 0,
                },
                
                # Loss statistics
                "loss": {
                    "initial": losses[0] if losses else None,
                    "final": losses[-1] if losses else None,
                    "mean": float(np.mean(losses)) if losses else None,
                    "std": float(np.std(losses)) if losses else None,
                },
                
                # Learning rate
                "learning_rate": {
                    "initial": steps[0].learning_rate if steps else None,
                    "final": steps[-1].learning_rate if steps else None,
                },
                
                # Violations
                "violations": {
                    "initial_hard": steps[0].hard_violations if steps else None,
                    "final_hard": steps[-1].hard_violations if steps else None,
                },
            }
    
    def _get_elapsed_time(self) -> float:
        """Отримати час з початку сесії."""
        if not self.current_session:
            return 0.0
        
        start = datetime.fromisoformat(self.current_session.start_time)
        now = datetime.now()
        return (now - start).total_seconds()
    
    def analyze_stability(self, window_size: int = 20) -> Dict[str, Any]:
        """
        Аналіз стабільності навчання.
        
        Перевіряє:
        - Variance reward в останніх N ітераціях
        - Тренд loss (зростає/спадає)
        - Policy divergence (KL)
        
        Returns:
            Dict з аналізом стабільності
        """
        with self._lock:
            if not self.current_session or len(self.current_session.steps) < window_size:
                return {"stable": True, "reason": "insufficient_data"}
            
            recent = self.current_session.steps[-window_size:]
            
            rewards = [s.episode_reward for s in recent]
            losses = [s.policy_loss for s in recent]
            
            reward_variance = np.var(rewards)
            loss_trend = np.polyfit(range(len(losses)), losses, 1)[0]  # Slope
            
            # Stability checks
            issues = []
            
            # High variance
            if reward_variance > 100:
                issues.append(f"High reward variance: {reward_variance:.2f}")
            
            # Loss increasing
            if loss_trend > 0.01:
                issues.append(f"Policy loss increasing: slope={loss_trend:.4f}")
            
            # KL divergence (if available)
            kls = [s.approx_kl for s in recent if s.approx_kl is not None]
            if kls and np.mean(kls) > 0.02:
                issues.append(f"High KL divergence: {np.mean(kls):.4f}")
            
            return {
                "stable": len(issues) == 0,
                "issues": issues,
                "reward_variance": float(reward_variance),
                "loss_trend": float(loss_trend),
                "avg_kl": float(np.mean(kls)) if kls else None,
            }


# === Singleton instance for global access ===
_metrics_collector: Optional[TrainingMetricsCollector] = None


def get_metrics_collector() -> TrainingMetricsCollector:
    """Отримати глобальний metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = TrainingMetricsCollector()
    return _metrics_collector
