"""
Модуль динамічного Learning Rate Scheduling для PPO.

Реалізовані стратегії:
1. Linear Decay - лінійне зменшення від початкового до мінімального значення
2. Cosine Annealing - косинусне згасання з теплими рестартами
3. Exponential Decay - експоненційне зменшення
4. Reduce on Plateau - зменшення при стагнації reward
5. Warmup - поступове збільшення на початку навчання

Обґрунтування вибору стратегій:
- Warmup: Запобігає різким оновленням на початку, коли ваги випадкові
- Cosine Annealing: Найкраща для PPO - плавне зменшення з періодичними "спалахами"
- Reduce on Plateau: Адаптивне зменшення при відсутності прогресу

Автор: AI Research Engineer
Дата: 2024-12-25
"""
import math
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from collections import deque
import logging

logger = logging.getLogger(__name__)


class BaseLRScheduler(ABC):
    """Базовий клас для Learning Rate Schedulers."""
    
    def __init__(
        self, 
        initial_lr: float, 
        min_lr: float = 1e-6,
        warmup_steps: int = 0,
    ):
        """
        Args:
            initial_lr: Початковий learning rate (після warmup)
            min_lr: Мінімальний learning rate
            warmup_steps: Кількість кроків для warmup фази
        """
        self.initial_lr = initial_lr
        self.min_lr = min_lr
        self.warmup_steps = warmup_steps
        self.current_step = 0
        self.current_lr = min_lr if warmup_steps > 0 else initial_lr
        
    @abstractmethod
    def _compute_lr(self, step: int) -> float:
        """Обчислити LR для конкретного кроку (без warmup)."""
        pass
    
    def step(self, metric: Optional[float] = None) -> float:
        """
        Виконати крок scheduler і повернути новий LR.
        
        Args:
            metric: Опціональна метрика для adaptive schedulers
            
        Returns:
            Новий learning rate
        """
        self.current_step += 1
        
        # Warmup фаза
        if self.current_step <= self.warmup_steps:
            # Лінійний warmup від min_lr до initial_lr
            warmup_progress = self.current_step / self.warmup_steps
            self.current_lr = self.min_lr + (self.initial_lr - self.min_lr) * warmup_progress
            logger.debug(f"Warmup step {self.current_step}/{self.warmup_steps}: LR = {self.current_lr:.6f}")
        else:
            # Основна стратегія
            effective_step = self.current_step - self.warmup_steps
            self.current_lr = self._compute_lr(effective_step)
            self.current_lr = max(self.current_lr, self.min_lr)
        
        return self.current_lr
    
    def get_lr(self) -> float:
        """Отримати поточний learning rate."""
        return self.current_lr
    
    def get_state(self) -> Dict[str, Any]:
        """Отримати стан для збереження."""
        return {
            "scheduler_type": self.__class__.__name__,
            "initial_lr": self.initial_lr,
            "min_lr": self.min_lr,
            "warmup_steps": self.warmup_steps,
            "current_step": self.current_step,
            "current_lr": self.current_lr,
        }
    
    def load_state(self, state: Dict[str, Any]):
        """Завантажити стан."""
        self.current_step = state.get("current_step", 0)
        self.current_lr = state.get("current_lr", self.initial_lr)
    
    def reset(self):
        """Скинути scheduler."""
        self.current_step = 0
        self.current_lr = self.min_lr if self.warmup_steps > 0 else self.initial_lr


class LinearDecayScheduler(BaseLRScheduler):
    """
    Лінійне зменшення Learning Rate.
    
    LR(t) = initial_lr - (initial_lr - min_lr) * (t / total_steps)
    
    Переваги:
    - Простий та передбачуваний
    - Добре працює для фіксованої кількості ітерацій
    
    Недоліки:
    - Не адаптується до прогресу навчання
    """
    
    def __init__(
        self, 
        initial_lr: float, 
        total_steps: int,
        min_lr: float = 1e-6,
        warmup_steps: int = 0,
    ):
        super().__init__(initial_lr, min_lr, warmup_steps)
        self.total_steps = total_steps
        
    def _compute_lr(self, step: int) -> float:
        # Після total_steps - залишаємо min_lr
        if step >= self.total_steps:
            return self.min_lr
        
        decay = (self.initial_lr - self.min_lr) * (step / self.total_steps)
        return self.initial_lr - decay
    
    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["total_steps"] = self.total_steps
        return state


class ExponentialDecayScheduler(BaseLRScheduler):
    """
    Експоненційне зменшення Learning Rate.
    
    LR(t) = initial_lr * decay_rate^(t / decay_steps)
    
    Переваги:
    - Швидке зменшення на початку, повільне наприкінці
    - Добре для швидкої конвергенції
    
    Рекомендовані параметри:
    - decay_rate: 0.95-0.99
    - decay_steps: 100-1000
    """
    
    def __init__(
        self, 
        initial_lr: float, 
        decay_rate: float = 0.97,
        decay_steps: int = 100,
        min_lr: float = 1e-6,
        warmup_steps: int = 0,
    ):
        super().__init__(initial_lr, min_lr, warmup_steps)
        self.decay_rate = decay_rate
        self.decay_steps = decay_steps
        
    def _compute_lr(self, step: int) -> float:
        exponent = step / self.decay_steps
        return self.initial_lr * (self.decay_rate ** exponent)
    
    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["decay_rate"] = self.decay_rate
        state["decay_steps"] = self.decay_steps
        return state


class CosineAnnealingScheduler(BaseLRScheduler):
    """
    Косинусне згасання з теплими рестартами (Warm Restarts).
    
    LR(t) = min_lr + 0.5 * (initial_lr - min_lr) * (1 + cos(π * t_cur / T_cur))
    
    Це РЕКОМЕНДОВАНА стратегія для PPO:
    - Плавне зменшення з періодичними "спалахами"
    - Дозволяє виходити з локальних мінімумів
    - Добре працює з neural networks
    
    Параметри:
    - T_max: Період одного циклу
    - T_mult: Множник періоду після кожного рестарту (2.0 = подвоєння)
    """
    
    def __init__(
        self, 
        initial_lr: float, 
        T_max: int = 50,
        T_mult: float = 2.0,
        min_lr: float = 1e-6,
        warmup_steps: int = 0,
    ):
        super().__init__(initial_lr, min_lr, warmup_steps)
        self.T_max = T_max
        self.T_mult = T_mult
        self.T_cur = 0  # Поточна позиція в циклі
        self.cycle = 0  # Номер поточного циклу
        self.T_i = T_max  # Поточна довжина циклу
        
    def _compute_lr(self, step: int) -> float:
        # Визначити поточну позицію в циклі
        self.T_cur += 1
        
        # Перевірка на рестарт
        if self.T_cur >= self.T_i:
            self.T_cur = 0
            self.cycle += 1
            self.T_i = int(self.T_max * (self.T_mult ** self.cycle))
            logger.info(f"🔄 Cosine Annealing: рестарт циклу {self.cycle}, T={self.T_i}")
        
        # Косинусна формула
        cosine_value = math.cos(math.pi * self.T_cur / self.T_i)
        return self.min_lr + 0.5 * (self.initial_lr - self.min_lr) * (1 + cosine_value)
    
    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state.update({
            "T_max": self.T_max,
            "T_mult": self.T_mult,
            "T_cur": self.T_cur,
            "cycle": self.cycle,
            "T_i": self.T_i,
        })
        return state
    
    def load_state(self, state: Dict[str, Any]):
        super().load_state(state)
        self.T_cur = state.get("T_cur", 0)
        self.cycle = state.get("cycle", 0)
        self.T_i = state.get("T_i", self.T_max)


class ReduceOnPlateauScheduler(BaseLRScheduler):
    """
    Зменшення LR при стагнації метрики (reward).
    
    Якщо метрика не покращується протягом patience кроків,
    LR зменшується на factor.
    
    Це АДАПТИВНА стратегія:
    - Автоматично визначає коли потрібно зменшити LR
    - Добре працює коли невідома оптимальна кількість ітерацій
    
    Параметри:
    - patience: Скільки кроків чекати без покращення
    - factor: На скільки множити LR при зменшенні (0.5 = в 2 рази)
    - threshold: Мінімальне покращення для скидання лічильника
    """
    
    def __init__(
        self, 
        initial_lr: float, 
        patience: int = 10,
        factor: float = 0.5,
        threshold: float = 0.01,
        min_lr: float = 1e-6,
        warmup_steps: int = 0,
        cooldown: int = 5,  # Кроків після зменшення перед новою перевіркою
    ):
        super().__init__(initial_lr, min_lr, warmup_steps)
        self.patience = patience
        self.factor = factor
        self.threshold = threshold
        self.cooldown = cooldown
        
        self.best_metric = float('-inf')
        self.num_bad_steps = 0
        self.cooldown_counter = 0
        self._last_lr = initial_lr
        
    def _compute_lr(self, step: int) -> float:
        # Зберігаємо останній LR (не initial_lr!)
        return self._last_lr
    
    def step(self, metric: Optional[float] = None) -> float:
        """
        Крок з урахуванням метрики.
        
        ВАЖЛИВО: Для цього scheduler потрібно передавати metric!
        """
        self.current_step += 1
        
        # Warmup фаза
        if self.current_step <= self.warmup_steps:
            warmup_progress = self.current_step / self.warmup_steps
            self.current_lr = self.min_lr + (self.initial_lr - self.min_lr) * warmup_progress
            self._last_lr = self.current_lr
            return self.current_lr
        
        # Cooldown після зменшення
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            return self.current_lr
        
        # Перевірка метрики
        if metric is not None:
            if metric > self.best_metric + self.threshold:
                # Покращення!
                self.best_metric = metric
                self.num_bad_steps = 0
            else:
                # Без покращення
                self.num_bad_steps += 1
                
                if self.num_bad_steps >= self.patience:
                    # Зменшуємо LR
                    old_lr = self._last_lr
                    self._last_lr = max(self._last_lr * self.factor, self.min_lr)
                    self.current_lr = self._last_lr
                    self.num_bad_steps = 0
                    self.cooldown_counter = self.cooldown
                    
                    logger.info(
                        f"📉 ReduceOnPlateau: LR {old_lr:.6f} → {self._last_lr:.6f} "
                        f"(best_metric={self.best_metric:.2f})"
                    )
        
        return self.current_lr
    
    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state.update({
            "patience": self.patience,
            "factor": self.factor,
            "threshold": self.threshold,
            "cooldown": self.cooldown,
            "best_metric": self.best_metric,
            "num_bad_steps": self.num_bad_steps,
            "cooldown_counter": self.cooldown_counter,
            "_last_lr": self._last_lr,
        })
        return state
    
    def load_state(self, state: Dict[str, Any]):
        super().load_state(state)
        self.best_metric = state.get("best_metric", float('-inf'))
        self.num_bad_steps = state.get("num_bad_steps", 0)
        self.cooldown_counter = state.get("cooldown_counter", 0)
        self._last_lr = state.get("_last_lr", self.initial_lr)


class CombinedScheduler(BaseLRScheduler):
    """
    Комбінований Scheduler: Warmup + Cosine Annealing + Plateau Detection.
    
    Це РЕКОМЕНДОВАНИЙ scheduler для production:
    1. Warmup фаза для стабільного старту
    2. Cosine annealing для основного навчання
    3. Автоматичне зменшення при plateau
    
    Поєднує переваги всіх стратегій.
    """
    
    def __init__(
        self, 
        initial_lr: float,
        total_steps: int,
        warmup_ratio: float = 0.1,  # 10% на warmup
        min_lr: float = 1e-6,
        plateau_patience: int = 20,
        plateau_factor: float = 0.5,
    ):
        warmup_steps = int(total_steps * warmup_ratio)
        super().__init__(initial_lr, min_lr, warmup_steps)
        
        self.total_steps = total_steps
        self.plateau_patience = plateau_patience
        self.plateau_factor = plateau_factor
        
        # Внутрішній cosine scheduler (без warmup)
        self._cosine_T = total_steps - warmup_steps
        
        # Plateau tracking
        self.best_metric = float('-inf')
        self.num_bad_steps = 0
        self._base_lr = initial_lr  # LR до plateau adjustments
        
    def _compute_lr(self, step: int) -> float:
        # Cosine annealing
        if step >= self._cosine_T:
            return self.min_lr
        
        cosine_value = math.cos(math.pi * step / self._cosine_T)
        return self.min_lr + 0.5 * (self._base_lr - self.min_lr) * (1 + cosine_value)
    
    def step(self, metric: Optional[float] = None) -> float:
        """Крок з опціональною метрикою для plateau detection."""
        # Plateau detection (якщо є метрика)
        if metric is not None and self.current_step > self.warmup_steps:
            if metric > self.best_metric + 0.01:
                self.best_metric = metric
                self.num_bad_steps = 0
            else:
                self.num_bad_steps += 1
                
                if self.num_bad_steps >= self.plateau_patience:
                    old_base = self._base_lr
                    self._base_lr = max(self._base_lr * self.plateau_factor, self.min_lr)
                    self.num_bad_steps = 0
                    logger.info(f"📉 Combined: base_lr {old_base:.6f} → {self._base_lr:.6f}")
        
        # Стандартний крок
        return super().step(metric)
    
    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state.update({
            "total_steps": self.total_steps,
            "plateau_patience": self.plateau_patience,
            "plateau_factor": self.plateau_factor,
            "_cosine_T": self._cosine_T,
            "best_metric": self.best_metric,
            "num_bad_steps": self.num_bad_steps,
            "_base_lr": self._base_lr,
        })
        return state
    
    def load_state(self, state: Dict[str, Any]):
        super().load_state(state)
        self.best_metric = state.get("best_metric", float('-inf'))
        self.num_bad_steps = state.get("num_bad_steps", 0)
        self._base_lr = state.get("_base_lr", self.initial_lr)


# === Factory Function ===

def create_lr_scheduler(
    scheduler_type: str,
    initial_lr: float,
    total_steps: int,
    **kwargs
) -> BaseLRScheduler:
    """
    Factory function для створення LR scheduler.
    
    Args:
        scheduler_type: Тип scheduler ("linear", "exponential", "cosine", "plateau", "combined")
        initial_lr: Початковий learning rate
        total_steps: Загальна кількість кроків
        **kwargs: Додаткові параметри для конкретного scheduler
        
    Returns:
        Інстанс відповідного scheduler
        
    Рекомендації щодо вибору:
    - "combined" - для production (за замовчуванням)
    - "cosine" - для експериментів з фіксованою кількістю ітерацій
    - "plateau" - коли невідома оптимальна кількість ітерацій
    - "linear" - для baseline/порівняння
    """
    schedulers = {
        "linear": lambda: LinearDecayScheduler(
            initial_lr=initial_lr,
            total_steps=total_steps,
            min_lr=kwargs.get("min_lr", 1e-6),
            warmup_steps=kwargs.get("warmup_steps", 0),
        ),
        "exponential": lambda: ExponentialDecayScheduler(
            initial_lr=initial_lr,
            decay_rate=kwargs.get("decay_rate", 0.97),
            decay_steps=kwargs.get("decay_steps", 100),
            min_lr=kwargs.get("min_lr", 1e-6),
            warmup_steps=kwargs.get("warmup_steps", 0),
        ),
        "cosine": lambda: CosineAnnealingScheduler(
            initial_lr=initial_lr,
            T_max=kwargs.get("T_max", total_steps // 5),
            T_mult=kwargs.get("T_mult", 2.0),
            min_lr=kwargs.get("min_lr", 1e-6),
            warmup_steps=kwargs.get("warmup_steps", int(total_steps * 0.1)),
        ),
        "plateau": lambda: ReduceOnPlateauScheduler(
            initial_lr=initial_lr,
            patience=kwargs.get("patience", 10),
            factor=kwargs.get("factor", 0.5),
            threshold=kwargs.get("threshold", 0.01),
            min_lr=kwargs.get("min_lr", 1e-6),
            warmup_steps=kwargs.get("warmup_steps", int(total_steps * 0.1)),
        ),
        "combined": lambda: CombinedScheduler(
            initial_lr=initial_lr,
            total_steps=total_steps,
            warmup_ratio=kwargs.get("warmup_ratio", 0.1),
            min_lr=kwargs.get("min_lr", 1e-6),
            plateau_patience=kwargs.get("plateau_patience", 20),
            plateau_factor=kwargs.get("plateau_factor", 0.5),
        ),
    }
    
    if scheduler_type not in schedulers:
        raise ValueError(
            f"Unknown scheduler type: {scheduler_type}. "
            f"Available: {list(schedulers.keys())}"
        )
    
    scheduler = schedulers[scheduler_type]()
    logger.info(f"📊 Створено LR Scheduler: {scheduler_type} (initial_lr={initial_lr}, steps={total_steps})")
    
    return scheduler
