"""
Checkpoint Manager для Persistent / Continual Learning.

Забезпечує:
1. Збереження повного стану навчання:
   - Ваги нейронної мережі
   - Стан optimizer'а
   - Стан LR scheduler'а
   - Гіперпараметри
   - Метрики навчання
   
2. Відновлення стану:
   - Повне відновлення (continue training)
   - Часткове відновлення (fine-tuning)
   - Transfer learning (тільки ваги)

3. Керування версіями checkpoints:
   - Автоматичне версіонування
   - Збереження N найкращих моделей
   - Періодичне збереження

4. Контроль стабільності при зміні параметрів:
   - Warmup після завантаження
   - Обмеження різких змін LR
   - Policy divergence detection

Автор: AI Research Engineer
Дата: 2024-12-25
"""
import os
import json
import shutil
import torch
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
import logging
import threading
from collections import OrderedDict

logger = logging.getLogger(__name__)


@dataclass
class CheckpointMetadata:
    """Метадані checkpoint'а."""
    checkpoint_id: str
    created_at: str
    
    # Training state
    iteration: int
    best_reward: float
    current_reward: float
    hard_violations: int
    
    # Model info
    state_dim: int
    action_dim: int
    model_architecture: str
    
    # Training config
    learning_rate: float
    gamma: float
    epsilon: float
    gae_lambda: float
    
    # LR Scheduler
    scheduler_type: str
    scheduler_step: int
    
    # Tags for filtering
    tags: List[str] = None
    description: str = ""
    
    # File paths (relative to checkpoint dir)
    model_file: str = "model.pt"
    optimizer_file: str = "optimizer.pt"
    scheduler_file: str = "scheduler.json"
    metrics_file: str = "metrics.json"


@dataclass
class HyperparameterUpdate:
    """Запит на зміну гіперпараметрів."""
    parameter: str  # learning_rate, gamma, epsilon, etc.
    old_value: float
    new_value: float
    timestamp: str
    reason: str = ""


class CheckpointManager:
    """
    Менеджер checkpoints для continual learning.
    
    Забезпечує:
    - Повне збереження/відновлення стану
    - Керування версіями
    - Runtime зміну гіперпараметрів
    - Контроль стабільності
    """
    
    def __init__(
        self,
        checkpoint_dir: Path = None,
        max_checkpoints: int = 10,
        keep_best_n: int = 3,
        auto_save_interval: int = 50,  # Кожні N ітерацій
    ):
        """
        Args:
            checkpoint_dir: Директорія для checkpoints
            max_checkpoints: Максимальна кількість checkpoints
            keep_best_n: Зберігати N найкращих за reward
            auto_save_interval: Інтервал автозбереження
        """
        self.checkpoint_dir = checkpoint_dir or Path("./backend/checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_checkpoints = max_checkpoints
        self.keep_best_n = keep_best_n
        self.auto_save_interval = auto_save_interval
        
        # Tracking
        self.checkpoints: List[CheckpointMetadata] = []
        self.hyperparameter_history: List[HyperparameterUpdate] = []
        self._load_checkpoint_index()
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Runtime hyperparameter control
        self._pending_updates: Dict[str, Any] = {}
        self._update_callbacks: List[callable] = []
        
        logger.info(f"📁 CheckpointManager ініціалізовано: {self.checkpoint_dir}")
    
    def save_checkpoint(
        self,
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler_state: Dict[str, Any] = None,
        training_state: Dict[str, Any] = None,
        tags: List[str] = None,
        description: str = "",
        is_best: bool = False,
    ) -> str:
        """
        Зберегти checkpoint.
        
        Args:
            model: Нейронна мережа
            optimizer: Optimizer
            scheduler_state: Стан LR scheduler'а
            training_state: Поточний стан навчання (iteration, reward, etc.)
            tags: Теги для фільтрації
            description: Опис checkpoint'а
            is_best: Чи це найкраща модель
            
        Returns:
            checkpoint_id
        """
        with self._lock:
            # Generate ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            checkpoint_id = f"ckpt_{timestamp}"
            
            if is_best:
                checkpoint_id = f"best_{checkpoint_id}"
            
            # Create directory
            ckpt_path = self.checkpoint_dir / checkpoint_id
            ckpt_path.mkdir(exist_ok=True)
            
            # Save model
            model_path = ckpt_path / "model.pt"
            torch.save(model.state_dict(), model_path)
            
            # Save optimizer
            optim_path = ckpt_path / "optimizer.pt"
            torch.save(optimizer.state_dict(), optim_path)
            
            # Save scheduler state
            if scheduler_state:
                scheduler_path = ckpt_path / "scheduler.json"
                with open(scheduler_path, 'w') as f:
                    json.dump(scheduler_state, f, indent=2)
            
            # Extract config from optimizer
            lr = optimizer.param_groups[0]['lr']
            
            # Create metadata
            training_state = training_state or {}
            metadata = CheckpointMetadata(
                checkpoint_id=checkpoint_id,
                created_at=datetime.now().isoformat(),
                iteration=training_state.get('iteration', 0),
                best_reward=training_state.get('best_reward', 0),
                current_reward=training_state.get('current_reward', 0),
                hard_violations=training_state.get('hard_violations', 0),
                state_dim=training_state.get('state_dim', 0),
                action_dim=training_state.get('action_dim', 0),
                model_architecture=model.__class__.__name__,
                learning_rate=lr,
                gamma=training_state.get('gamma', 0.99),
                epsilon=training_state.get('epsilon', 0.2),
                gae_lambda=training_state.get('gae_lambda', 0.95),
                scheduler_type=scheduler_state.get('scheduler_type', 'none') if scheduler_state else 'none',
                scheduler_step=scheduler_state.get('current_step', 0) if scheduler_state else 0,
                tags=tags or [],
                description=description,
            )
            
            # Save metadata
            meta_path = ckpt_path / "metadata.json"
            with open(meta_path, 'w') as f:
                json.dump(asdict(metadata), f, indent=2, ensure_ascii=False)
            
            # Add to index
            self.checkpoints.append(metadata)
            self._save_checkpoint_index()
            
            # Cleanup old checkpoints
            self._cleanup_old_checkpoints()
            
            logger.info(f"💾 Checkpoint збережено: {checkpoint_id} (reward={metadata.current_reward:.2f})")
            return checkpoint_id
    
    def load_checkpoint(
        self,
        checkpoint_id: str,
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer = None,
        device: torch.device = None,
        load_optimizer: bool = True,
        apply_warmup: bool = True,
        warmup_steps: int = 10,
        state_dim: int = None,
        action_dim: int = None,
    ) -> Dict[str, Any]:
        """
        Завантажити checkpoint.
        
        Args:
            checkpoint_id: ID checkpoint'а
            model: Модель для завантаження ваг
            optimizer: Optimizer (опціонально)
            device: Пристрій для завантаження
            load_optimizer: Чи завантажувати стан optimizer'а
            apply_warmup: Застосувати warmup після завантаження
            warmup_steps: Кількість warmup кроків
            state_dim: Очікувана розмірність стану (для перевірки сумісності)
            action_dim: Очікувана розмірність дій (для перевірки сумісності)
            
        Returns:
            Dict з метаданими та станом scheduler'а
            
        Raises:
            ValueError: Якщо розміри моделі не співпадають
        """
        with self._lock:
            ckpt_path = self.checkpoint_dir / checkpoint_id
            
            if not ckpt_path.exists():
                raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")
            
            device = device or torch.device('cpu')
            
            # Load metadata first to check compatibility
            meta_path = ckpt_path / "metadata.json"
            metadata = None
            if meta_path.exists():
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
            
            # Check dimension compatibility
            if metadata and state_dim is not None:
                saved_state_dim = metadata.get('state_dim', 0)
                if saved_state_dim > 0 and saved_state_dim != state_dim:
                    raise ValueError(
                        f"Checkpoint dimension mismatch: saved state_dim={saved_state_dim}, "
                        f"current state_dim={state_dim}. The model was trained with different "
                        f"environment configuration (different number of courses/teachers/etc)."
                    )
            
            if metadata and action_dim is not None:
                saved_action_dim = metadata.get('action_dim', 0)
                if saved_action_dim > 0 and saved_action_dim != action_dim:
                    raise ValueError(
                        f"Checkpoint dimension mismatch: saved action_dim={saved_action_dim}, "
                        f"current action_dim={action_dim}."
                    )
            
            # Load model
            model_path = ckpt_path / "model.pt"
            state_dict = torch.load(model_path, map_location=device)
            model.load_state_dict(state_dict)
            logger.info(f"📥 Завантажено ваги моделі: {checkpoint_id}")
            
            # Load optimizer
            if load_optimizer and optimizer is not None:
                optim_path = ckpt_path / "optimizer.pt"
                if optim_path.exists():
                    optim_state = torch.load(optim_path, map_location=device)
                    optimizer.load_state_dict(optim_state)
                    
                    # Apply warmup (reduce LR initially, then restore)
                    if apply_warmup:
                        self._apply_warmup_to_optimizer(optimizer, warmup_steps)
                    
                    logger.info(f"📥 Завантажено стан optimizer'а")
            
            # Load scheduler state
            scheduler_state = None
            scheduler_path = ckpt_path / "scheduler.json"
            if scheduler_path.exists():
                with open(scheduler_path, 'r') as f:
                    scheduler_state = json.load(f)
            
            # Load metadata
            meta_path = ckpt_path / "metadata.json"
            metadata = None
            if meta_path.exists():
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
            
            return {
                "checkpoint_id": checkpoint_id,
                "metadata": metadata,
                "scheduler_state": scheduler_state,
                "warmup_applied": apply_warmup,
            }
    
    def load_latest(
        self,
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer = None,
        device: torch.device = None,
        filter_best: bool = False,
        state_dim: int = None,
        action_dim: int = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Завантажити останній (або найкращий) checkpoint.
        
        Args:
            filter_best: Завантажити найкращий за reward
            state_dim: Очікувана розмірність стану (для перевірки сумісності)
            action_dim: Очікувана розмірність дій (для перевірки сумісності)
        """
        if not self.checkpoints:
            logger.info("📥 Немає збережених checkpoints")
            return None
        
        if filter_best:
            # Сортуємо за best_reward
            sorted_ckpts = sorted(
                self.checkpoints, 
                key=lambda x: x.best_reward, 
                reverse=True
            )
            # Filter by compatible dimensions if specified
            if state_dim is not None:
                sorted_ckpts = [c for c in sorted_ckpts 
                               if c.state_dim == 0 or c.state_dim == state_dim]
            checkpoint = sorted_ckpts[0] if sorted_ckpts else None
        else:
            # Останній за часом, але з сумісними розмірами
            compatible = self.checkpoints
            if state_dim is not None:
                compatible = [c for c in compatible 
                              if c.state_dim == 0 or c.state_dim == state_dim]
            checkpoint = compatible[-1] if compatible else None
        
        if checkpoint is None:
            logger.info(f"📥 Немає сумісних checkpoints (state_dim={state_dim})")
            return None
        
        return self.load_checkpoint(
            checkpoint.checkpoint_id,
            model,
            optimizer,
            device,
            state_dim=state_dim,
            action_dim=action_dim,
        )
    
    def get_checkpoint_list(
        self,
        tags: List[str] = None,
        min_reward: float = None,
    ) -> List[CheckpointMetadata]:
        """
        Отримати список checkpoints з фільтрацією.
        """
        result = self.checkpoints.copy()
        
        if tags:
            result = [c for c in result if any(t in c.tags for t in tags)]
        
        if min_reward is not None:
            result = [c for c in result if c.best_reward >= min_reward]
        
        return result
    
    def delete_checkpoint(self, checkpoint_id: str):
        """Видалити checkpoint."""
        with self._lock:
            ckpt_path = self.checkpoint_dir / checkpoint_id
            
            if ckpt_path.exists():
                shutil.rmtree(ckpt_path)
            
            self.checkpoints = [c for c in self.checkpoints if c.checkpoint_id != checkpoint_id]
            self._save_checkpoint_index()
            
            logger.info(f"🗑️ Checkpoint видалено: {checkpoint_id}")
    
    # === Runtime Hyperparameter Control ===
    
    def request_hyperparameter_update(
        self,
        parameter: str,
        new_value: float,
        reason: str = "",
    ) -> bool:
        """
        Запит на зміну гіперпараметра під час навчання.
        
        Це thread-safe операція, яка додає оновлення до черги.
        Тренер перевірить чергу на кожній ітерації.
        
        Args:
            parameter: Ім'я параметра (learning_rate, gamma, epsilon, etc.)
            new_value: Нове значення
            reason: Причина зміни
            
        Returns:
            True якщо запит прийнято
        """
        valid_params = ['learning_rate', 'gamma', 'epsilon', 'gae_lambda', 
                        'entropy_coef', 'value_coef', 'clip_range']
        
        if parameter not in valid_params:
            logger.warning(f"Invalid parameter: {parameter}")
            return False
        
        with self._lock:
            self._pending_updates[parameter] = {
                'value': new_value,
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
            }
            
            logger.info(f"📝 Запит на зміну {parameter} → {new_value}")
            return True
    
    def get_pending_updates(self) -> Dict[str, Any]:
        """
        Отримати та очистити чергу оновлень.
        
        Викликається тренером на кожній ітерації.
        """
        with self._lock:
            updates = self._pending_updates.copy()
            self._pending_updates.clear()
            return updates
    
    def apply_hyperparameter_updates(
        self,
        optimizer: torch.optim.Optimizer,
        trainer_config: Dict[str, Any],
        updates: Dict[str, Any],
        gradual: bool = True,
        transition_steps: int = 10,
    ) -> Dict[str, HyperparameterUpdate]:
        """
        Застосувати оновлення гіперпараметрів з контролем стабільності.
        
        Args:
            optimizer: Optimizer для оновлення LR
            trainer_config: Конфігурація тренера
            updates: Словник оновлень {param: {value, reason}}
            gradual: Застосовувати поступово (для стабільності)
            transition_steps: Кількість кроків для переходу
            
        Returns:
            Dict зі записами про оновлення
        """
        applied = {}
        
        for param, update_info in updates.items():
            new_value = update_info['value']
            reason = update_info.get('reason', '')
            
            # Get current value
            if param == 'learning_rate':
                old_value = optimizer.param_groups[0]['lr']
                
                # Stability check: limit change magnitude
                max_change = old_value * 0.5  # Max 50% change
                if abs(new_value - old_value) > max_change:
                    logger.warning(
                        f"⚠️ LR change too large ({old_value} → {new_value}). "
                        f"Limiting to {old_value + np.sign(new_value - old_value) * max_change}"
                    )
                    new_value = old_value + np.sign(new_value - old_value) * max_change
                
                # Apply
                for param_group in optimizer.param_groups:
                    param_group['lr'] = new_value
                    
            else:
                old_value = trainer_config.get(param, 0)
                trainer_config[param] = new_value
            
            # Record update
            update_record = HyperparameterUpdate(
                parameter=param,
                old_value=old_value,
                new_value=new_value,
                timestamp=datetime.now().isoformat(),
                reason=reason,
            )
            
            self.hyperparameter_history.append(update_record)
            applied[param] = update_record
            
            logger.info(f"✅ Застосовано: {param} {old_value} → {new_value}")
        
        return applied
    
    def check_training_stability(
        self,
        recent_rewards: List[float],
        recent_kl: List[float] = None,
        window: int = 20,
    ) -> Dict[str, Any]:
        """
        Перевірка стабільності навчання після зміни параметрів.
        
        Returns:
            Dict з аналізом стабільності та рекомендаціями
        """
        if len(recent_rewards) < window:
            return {"stable": True, "message": "Insufficient data"}
        
        recent = recent_rewards[-window:]
        variance = np.var(recent)
        trend = np.polyfit(range(len(recent)), recent, 1)[0]
        
        issues = []
        recommendations = []
        
        # High variance
        if variance > 100:
            issues.append("High reward variance")
            recommendations.append("Consider reducing learning rate")
        
        # Decreasing trend
        if trend < -1:
            issues.append("Reward decreasing")
            recommendations.append("Consider reverting last hyperparameter change")
        
        # KL divergence check
        if recent_kl and len(recent_kl) >= 5:
            avg_kl = np.mean(recent_kl[-5:])
            if avg_kl > 0.02:
                issues.append(f"High KL divergence: {avg_kl:.4f}")
                recommendations.append("Policy is diverging, reduce LR or clip range")
        
        return {
            "stable": len(issues) == 0,
            "variance": float(variance),
            "trend": float(trend),
            "issues": issues,
            "recommendations": recommendations,
        }
    
    # === Internal Methods ===
    
    def _apply_warmup_to_optimizer(
        self,
        optimizer: torch.optim.Optimizer,
        warmup_steps: int,
    ):
        """
        Застосувати warmup після завантаження checkpoint.
        
        Зменшує LR на початку, щоб уникнути різких оновлень.
        """
        current_lr = optimizer.param_groups[0]['lr']
        warmup_lr = current_lr * 0.1  # 10% від поточного
        
        # Store target LR for gradual restore
        for param_group in optimizer.param_groups:
            param_group['_target_lr'] = current_lr
            param_group['_warmup_steps'] = warmup_steps
            param_group['_warmup_step'] = 0
            param_group['lr'] = warmup_lr
        
        logger.info(f"🔥 Warmup: LR {warmup_lr:.2e} → {current_lr:.2e} за {warmup_steps} кроків")
    
    def warmup_step(self, optimizer: torch.optim.Optimizer):
        """
        Крок warmup (викликати на кожній ітерації після завантаження).
        """
        for param_group in optimizer.param_groups:
            if '_warmup_step' in param_group:
                param_group['_warmup_step'] += 1
                
                if param_group['_warmup_step'] >= param_group['_warmup_steps']:
                    # Warmup завершено
                    param_group['lr'] = param_group['_target_lr']
                    del param_group['_target_lr']
                    del param_group['_warmup_steps']
                    del param_group['_warmup_step']
                    logger.info("🔥 Warmup завершено")
                else:
                    # Лінійне збільшення
                    progress = param_group['_warmup_step'] / param_group['_warmup_steps']
                    current_warmup_lr = param_group['_target_lr'] * 0.1
                    target = param_group['_target_lr']
                    param_group['lr'] = current_warmup_lr + (target - current_warmup_lr) * progress
    
    def _load_checkpoint_index(self):
        """Завантажити індекс checkpoints."""
        index_path = self.checkpoint_dir / "checkpoint_index.json"
        
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)
                
                self.checkpoints = [
                    CheckpointMetadata(**item) 
                    for item in data.get('checkpoints', [])
                ]
                
                self.hyperparameter_history = [
                    HyperparameterUpdate(**item)
                    for item in data.get('hyperparameter_history', [])
                ]
                
                logger.info(f"📂 Завантажено {len(self.checkpoints)} checkpoints")
            except Exception as e:
                logger.warning(f"Error loading checkpoint index: {e}")
                self.checkpoints = []
    
    def _save_checkpoint_index(self):
        """Зберегти індекс checkpoints."""
        index_path = self.checkpoint_dir / "checkpoint_index.json"
        
        data = {
            'checkpoints': [asdict(c) for c in self.checkpoints],
            'hyperparameter_history': [asdict(h) for h in self.hyperparameter_history[-100:]],  # Last 100
            'updated_at': datetime.now().isoformat(),
        }
        
        with open(index_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _cleanup_old_checkpoints(self):
        """Видалити старі checkpoints, зберігаючи найкращі."""
        if len(self.checkpoints) <= self.max_checkpoints:
            return
        
        # Sort by reward (descending)
        sorted_ckpts = sorted(
            self.checkpoints,
            key=lambda x: x.best_reward,
            reverse=True
        )
        
        # Keep best N
        to_keep = set(c.checkpoint_id for c in sorted_ckpts[:self.keep_best_n])
        
        # Keep also N latest
        to_keep.update(c.checkpoint_id for c in self.checkpoints[-self.keep_best_n:])
        
        # Remove others
        for ckpt in self.checkpoints.copy():
            if ckpt.checkpoint_id not in to_keep and len(self.checkpoints) > self.max_checkpoints:
                self.delete_checkpoint(ckpt.checkpoint_id)
        
        logger.info(f"🧹 Cleanup: залишилось {len(self.checkpoints)} checkpoints")
    
    def export_training_state(self, filepath: Path):
        """
        Експортувати повний стан для transfer/sharing.
        
        Створює ZIP архів з:
        - Останнім checkpoint'ом
        - Історією гіперпараметрів
        - Метриками
        """
        import zipfile
        
        if not self.checkpoints:
            raise ValueError("No checkpoints to export")
        
        # Get best checkpoint
        best = max(self.checkpoints, key=lambda x: x.best_reward)
        best_path = self.checkpoint_dir / best.checkpoint_id
        
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add checkpoint files
            for file in best_path.iterdir():
                zf.write(file, f"checkpoint/{file.name}")
            
            # Add hyperparameter history
            history = {
                'checkpoints': [asdict(c) for c in self.checkpoints],
                'hyperparameter_history': [asdict(h) for h in self.hyperparameter_history],
            }
            zf.writestr("history.json", json.dumps(history, indent=2))
        
        logger.info(f"📦 Експортовано: {filepath}")


# === Singleton instance ===
_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager() -> CheckpointManager:
    """Отримати глобальний checkpoint manager."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager
