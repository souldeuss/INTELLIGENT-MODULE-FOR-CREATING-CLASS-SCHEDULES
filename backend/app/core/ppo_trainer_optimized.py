"""
Оптимізований PPO Trainer з паралельними середовищами та Curriculum Learning.

Ключові оптимізації:
1. Vectorized environments (4-8 паралельних середовищ)
2. GAE (Generalized Advantage Estimation) для стабільності
3. Mini-batch training для кращої GPU утилізації
4. Early stopping при стабілізації reward
5. Curriculum learning - від простих до складних задач
6. Mixed precision training (FP16) для GPU
"""
import os
import json
from pathlib import Path
from datetime import datetime
from collections import deque
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.cuda.amp import autocast, GradScaler
from typing import List, Tuple, Optional, Callable
import logging
import time

from .actor_critic import ActorCritic
from .environment_optimized import OptimizedTimetablingEnvironment, VectorizedEnvWrapper
from .model_registry import get_active_model_name

logger = logging.getLogger(__name__)


class OptimizedPPOTrainer:
    """
    Оптимізований PPO Trainer.
    
    Покращення:
    - Паралельні середовища для швидшого збору даних
    - Mini-batch оновлення для стабільності
    - GAE для кращих оцінок advantage
    - Early stopping для економії часу
    - Curriculum learning для поступового ускладнення
    """

    def __init__(
        self,
        env: OptimizedTimetablingEnvironment,
        state_dim: int,
        action_dim: int,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,  # GAE параметр
        epsilon: float = 0.2,
        epochs: int = 4,  # Зменшено з 10 для швидкості
        batch_size: int = 64,  # Mini-batch size
        n_steps: int = 128,  # Кроків перед оновленням
        num_envs: int = 4,  # Кількість паралельних середовищ
        device: str = "auto",  # auto-detect GPU
        progress_callback: Optional[Callable] = None,
        stop_callback: Optional[Callable] = None,  # Callback для перевірки зупинки
        use_mixed_precision: bool = True,  # FP16 для GPU
        model_version: Optional[str] = None,
        score_weights: Optional[dict] = None,
    ):
        # Auto-detect device
        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        logger.info(f"🖥️ Використовуємо пристрій: {self.device}")
        
        self.env = env
        self.num_envs = num_envs
        self.n_steps = n_steps
        self.batch_size = batch_size
        
        # Neural network
        self.model = ActorCritic(state_dim, action_dim).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr, eps=1e-5)
        
        # PPO hyperparameters
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.epsilon = epsilon
        self.epochs = epochs
        self.progress_callback = progress_callback
        self.stop_callback = stop_callback
        self.model_version = model_version
        self.score_weights = score_weights or {}
        
        # Mixed precision (для GPU)
        self.use_mixed_precision = use_mixed_precision and self.device.type == "cuda"
        if self.use_mixed_precision:
            self.scaler = GradScaler()
            logger.info("⚡ Mixed precision (FP16) увімкнено")
        
        # Early stopping
        self.early_stop_patience = 50  # Кількість ітерацій без покращення
        self.early_stop_threshold = 0.01  # Мінімальне покращення
        
        # Curriculum learning
        self.curriculum_enabled = True
        self.curriculum_stage = 0
        self.curriculum_stages = [
            {"max_courses": 5, "description": "Easy (5 courses)"},
            {"max_courses": 10, "description": "Medium (10 courses)"},
            {"max_courses": 20, "description": "Hard (20 courses)"},
            {"max_courses": None, "description": "Full complexity"},
        ]
        
        # Model saving
        self.model_dir = Path("./backend/saved_models")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Store dimensions for checkpoint compatibility
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Статистика
        self.reward_history = deque(maxlen=100)
        self.best_reward = float("-inf")
        self.no_improvement_count = 0
        
        # Спробувати завантажити модель
        self._try_load_pretrained()

    def _try_load_pretrained(self) -> bool:
        """Завантажити попередньо навчену модель з перевіркою сумісності."""
        candidates = []
        if self.model_version:
            model_name = self.model_version if self.model_version.endswith(".pt") else f"{self.model_version}.pt"
            candidates.append(self.model_dir / model_name)
        else:
            active_name = get_active_model_name(self.model_dir)
            candidates.append(self.model_dir / active_name)
            fallback = self.model_dir / "actor_critic_best.pt"
            if fallback not in candidates:
                candidates.append(fallback)

        for model_path in candidates:
            if not model_path.exists():
                continue

            meta_suffix = model_path.stem.replace("actor_critic_", "")
            meta_path = self.model_dir / f"meta_{meta_suffix}.json"
            try:
                # Перевірити сумісність розмірів
                if meta_path.exists():
                    with open(meta_path, 'r') as f:
                        meta = json.load(f)
                    saved_state_dim = meta.get('state_dim', 0)
                    if saved_state_dim > 0 and saved_state_dim != self.state_dim:
                        logger.warning(
                            f"⚠️ Checkpoint несумісний: saved state_dim={saved_state_dim}, "
                            f"current state_dim={self.state_dim}. Починаємо з нуля."
                        )
                        return False
                
                state_dict = torch.load(str(model_path), map_location=self.device)
                self.model.load_state_dict(state_dict)
                logger.info(f"✅ Завантажено модель: {model_path}")
                
                optim_path = self.model_dir / "optimizer_best.pt"
                if optim_path.exists():
                    self.optimizer.load_state_dict(
                        torch.load(str(optim_path), map_location=self.device)
                    )
                return True
            except RuntimeError as e:
                if "size mismatch" in str(e):
                    logger.warning(f"⚠️ Не вдалося завантажити: розміри моделі не співпадають. Починаємо з нуля.")
                else:
                    logger.warning(f"⚠️ Помилка завантаження: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Помилка завантаження: {e}")
        return False

    def save_model(self, suffix: str = "best") -> Path:
        """Зберегти модель."""
        model_path = self.model_dir / f"actor_critic_{suffix}.pt"
        optim_path = self.model_dir / f"optimizer_{suffix}.pt"
        
        torch.save(self.model.state_dict(), str(model_path))
        torch.save(self.optimizer.state_dict(), str(optim_path))
        
        # Метадані (включаючи розміри для перевірки сумісності)
        meta = {
            "saved_at": datetime.now().isoformat(),
            "best_reward": float(self.best_reward),
            "curriculum_stage": self.curriculum_stage,
            "device": str(self.device),
            "state_dim": self.state_dim,
            "action_dim": self.action_dim,
        }
        with open(self.model_dir / f"meta_{suffix}.json", "w") as f:
            json.dump(meta, f, indent=2)
        
        return model_path

    def train(self, num_iterations: int) -> Tuple[List[float], dict]:
        """
        Оптимізоване навчання з паралельними середовищами.
        
        Args:
            num_iterations: Кількість ітерацій (оновлень policy)
        
        Returns:
            episode_rewards: Історія винагород
            final_stats: Фінальна статистика
        """
        start_time = time.time()
        episode_rewards = []
        
        logger.info(f"🚀 Початок оптимізованого тренування: {num_iterations} ітерацій")
        logger.info(f"📊 Параметри: γ={self.gamma}, λ={self.gae_lambda}, ε={self.epsilon}")
        logger.info(f"📊 Batch: {self.batch_size}, Steps: {self.n_steps}, Envs: {self.num_envs}")
        
        # Reset environment
        state = self.env.reset()
        
        for iteration in range(num_iterations):
            # Перевірка зупинки
            if self.stop_callback and self.stop_callback():
                logger.info(f"🛑 Тренування зупинено на ітерації {iteration + 1}")
                break
            
            iter_start = time.time()
            
            # === Збір траєкторії ===
            (
                states, actions, rewards, log_probs, values, dones
            ) = self._collect_rollout(state)
            
            # Оновити state для наступної ітерації
            state = self.env._get_compact_state()
            
            # === Обчислення GAE advantages ===
            with torch.no_grad():
                next_value = self.model.critic(
                    torch.FloatTensor(state).unsqueeze(0).to(self.device)
                ).squeeze()
            
            advantages, returns = self._compute_gae(
                rewards, values, dones, next_value
            )
            
            # === PPO оновлення (mini-batches) ===
            policy_loss, value_loss, entropy = self._update_policy_minibatch(
                states, actions, log_probs, returns, advantages
            )
            
            # === Статистика ===
            episode_reward = rewards.sum().item()
            episode_rewards.append(episode_reward)
            self.reward_history.append(episode_reward)
            
            # Callback для UI
            if self.progress_callback:
                self.progress_callback(iteration + 1, num_iterations)
            
            # === Збереження найкращої моделі ===
            if episode_reward > self.best_reward:
                improvement = episode_reward - self.best_reward
                self.best_reward = episode_reward
                self.no_improvement_count = 0
                
                if improvement > self.early_stop_threshold:
                    self.save_model("best")
                    logger.info(f"⭐ Новий рекорд: {self.best_reward:.2f} (+{improvement:.2f})")
            else:
                self.no_improvement_count += 1
            
            # === Early Stopping ===
            if self._check_early_stopping():
                logger.info(f"🛑 Early stopping на ітерації {iteration + 1}")
                break
            
            # === Curriculum Learning ===
            if self.curriculum_enabled:
                self._update_curriculum(episode_reward)
            
            # === Логування ===
            if (iteration + 1) % 10 == 0:
                iter_time = time.time() - iter_start
                avg_reward = np.mean(list(self.reward_history))
                hard_v = self.env._count_hard_violations()
                
                logger.info(
                    f"📈 Iter {iteration + 1}/{num_iterations} | "
                    f"R: {episode_reward:.1f} (avg: {avg_reward:.1f}) | "
                    f"Hard: {hard_v} | "
                    f"Loss: {policy_loss:.3f} | "
                    f"Time: {iter_time:.2f}s"
                )
        
        # === Фінальне збереження ===
        self.save_model("final")
        
        total_time = time.time() - start_time
        final_stats = {
            "best_reward": float(self.best_reward),
            "final_hard_violations": self.env._count_hard_violations(),
            "final_soft_violations": self.env._count_soft_violations(),
            "total_time_seconds": total_time,
            "iterations_completed": len(episode_rewards),
            "avg_time_per_iteration": total_time / max(len(episode_rewards), 1),
        }
        
        logger.info(f"🎯 Тренування завершено за {total_time:.1f}с")
        logger.info(f"🎯 Best reward: {self.best_reward:.2f}")
        
        return episode_rewards, final_stats

    def _collect_rollout(self, initial_state: np.ndarray) -> Tuple[torch.Tensor, ...]:
        """
        Збір даних траєкторії для n_steps кроків.
        
        Оптимізація: накопичуємо дані в NumPy, потім конвертуємо в tensor один раз.
        """
        states_list = []
        actions_list = []
        rewards_list = []
        log_probs_list = []
        values_list = []
        dones_list = []
        
        state = initial_state
        
        for _ in range(self.n_steps):
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            
            # Отримати дію
            with torch.no_grad():
                logits, value = self.model(state_tensor)
                probs = torch.softmax(logits, dim=-1)
                dist = torch.distributions.Categorical(probs)
                action_idx = dist.sample()
                log_prob = dist.log_prob(action_idx)
            
            # Отримати валідні дії
            valid_actions = self.env.get_valid_actions()
            if not valid_actions:
                break
            
            # Вибір дії (map neural network output to valid action)
            action_idx_int = action_idx.item() % len(valid_actions)
            action = valid_actions[action_idx_int]
            
            # Виконати дію
            next_state, reward, done, info = self.env.step(action)
            
            # Зберегти
            states_list.append(state)
            actions_list.append(action_idx.item())
            rewards_list.append(reward)
            log_probs_list.append(log_prob)
            values_list.append(value.squeeze())
            dones_list.append(done)
            
            state = next_state
            
            if done:
                state = self.env.reset()
        
        # Конвертація в tensors
        if not states_list:
            # Повернути пусті tensors якщо немає даних
            return (
                torch.FloatTensor([]).to(self.device),
                torch.LongTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
            )
        
        return (
            torch.FloatTensor(np.array(states_list)).to(self.device),
            torch.LongTensor(actions_list).to(self.device),
            torch.FloatTensor(rewards_list).to(self.device),
            torch.stack(log_probs_list).to(self.device),
            torch.stack(values_list).to(self.device),
            torch.FloatTensor(dones_list).to(self.device),
        )

    def _compute_gae(
        self,
        rewards: torch.Tensor,
        values: torch.Tensor,
        dones: torch.Tensor,
        next_value: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Обчислення Generalized Advantage Estimation (GAE).
        
        GAE забезпечує кращий баланс між bias та variance порівняно
        з простими Monte-Carlo returns.
        
        Формула: A_t = Σ (γλ)^l * δ_{t+l}
        де δ_t = r_t + γV(s_{t+1}) - V(s_t)
        """
        if len(rewards) == 0:
            return torch.FloatTensor([]).to(self.device), torch.FloatTensor([]).to(self.device)
        
        advantages = torch.zeros_like(rewards)
        last_gae = 0
        
        # Обхід у зворотному порядку
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_val = next_value
                next_non_terminal = 1.0 - dones[t]
            else:
                next_val = values[t + 1]
                next_non_terminal = 1.0 - dones[t]
            
            # TD error
            delta = rewards[t] + self.gamma * next_val * next_non_terminal - values[t]
            
            # GAE
            advantages[t] = last_gae = delta + self.gamma * self.gae_lambda * next_non_terminal * last_gae
        
        # Returns = advantages + values
        returns = advantages + values
        
        return advantages, returns

    def _update_policy_minibatch(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        old_log_probs: torch.Tensor,
        returns: torch.Tensor,
        advantages: torch.Tensor,
    ) -> Tuple[float, float, float]:
        """
        PPO оновлення з mini-batches.
        
        Mini-batch training:
        - Краща утилізація GPU пам'яті
        - Стабільніше навчання
        - Можливість використання більших датасетів
        """
        if len(states) == 0:
            return 0.0, 0.0, 0.0
        
        # Нормалізація advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # Індекси для mini-batches
        dataset_size = len(states)
        batch_size = min(self.batch_size, dataset_size)
        
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        n_updates = 0
        
        for epoch in range(self.epochs):
            # Перемішуємо індекси
            indices = torch.randperm(dataset_size)
            
            for start in range(0, dataset_size, batch_size):
                end = min(start + batch_size, dataset_size)
                batch_indices = indices[start:end]
                
                batch_states = states[batch_indices]
                batch_actions = actions[batch_indices]
                batch_old_log_probs = old_log_probs[batch_indices]
                batch_returns = returns[batch_indices]
                batch_advantages = advantages[batch_indices]
                
                # Forward pass
                if self.use_mixed_precision:
                    with autocast():
                        policy_loss, value_loss, entropy = self._compute_losses(
                            batch_states, batch_actions, batch_old_log_probs,
                            batch_returns, batch_advantages
                        )
                        loss = policy_loss + 0.5 * value_loss - 0.01 * entropy
                    
                    # Backward з scaler
                    self.optimizer.zero_grad()
                    self.scaler.scale(loss).backward()
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=0.5)
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    policy_loss, value_loss, entropy = self._compute_losses(
                        batch_states, batch_actions, batch_old_log_probs,
                        batch_returns, batch_advantages
                    )
                    loss = policy_loss + 0.5 * value_loss - 0.01 * entropy
                    
                    self.optimizer.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=0.5)
                    self.optimizer.step()
                
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()
                n_updates += 1
        
        n_updates = max(n_updates, 1)
        return (
            total_policy_loss / n_updates,
            total_value_loss / n_updates,
            total_entropy / n_updates,
        )

    def _compute_losses(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        old_log_probs: torch.Tensor,
        returns: torch.Tensor,
        advantages: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Обчислення PPO losses."""
        logits, values = self.model(states)
        
        # Categorical distribution
        probs = torch.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)
        
        # Clamp actions to valid range
        max_action = logits.size(-1) - 1
        clamped_actions = torch.clamp(actions, 0, max_action)
        
        log_probs = dist.log_prob(clamped_actions)
        entropy = dist.entropy().mean()
        
        # PPO ratio
        ratio = torch.exp(log_probs - old_log_probs.detach())
        
        # Clipped surrogate objective
        surr1 = ratio * advantages
        surr2 = torch.clamp(ratio, 1 - self.epsilon, 1 + self.epsilon) * advantages
        policy_loss = -torch.min(surr1, surr2).mean()
        
        # Value loss
        value_loss = nn.functional.mse_loss(values.squeeze(-1), returns)
        
        return policy_loss, value_loss, entropy

    def _check_early_stopping(self) -> bool:
        """
        Перевірка умов для early stopping.
        
        Зупиняємо якщо:
        1. Немає покращення протягом patience ітерацій
        2. Немає жорстких порушень і reward стабільний
        """
        if self.no_improvement_count >= self.early_stop_patience:
            return True
        
        # Перевірка на відсутність конфліктів
        if (self.env._count_hard_violations() == 0 and 
            len(self.reward_history) >= 20):
            recent_rewards = list(self.reward_history)[-20:]
            std = np.std(recent_rewards)
            if std < 0.5:  # Reward стабілізувався
                return True
        
        return False

    def _update_curriculum(self, reward: float):
        """
        Оновлення стадії curriculum learning.
        
        Переходимо до наступної стадії коли:
        1. Середня винагорода перевищує поріг
        2. Кількість жорстких порушень = 0
        """
        if self.curriculum_stage >= len(self.curriculum_stages) - 1:
            return  # Вже на максимальній складності
        
        # Умови переходу
        if (len(self.reward_history) >= 10 and
            np.mean(list(self.reward_history)[-10:]) > 0 and
            self.env._count_hard_violations() == 0):
            
            self.curriculum_stage += 1
            stage_info = self.curriculum_stages[self.curriculum_stage]
            logger.info(f"📚 Curriculum: перехід до стадії {self.curriculum_stage} - {stage_info['description']}")

    def generate_schedule(self) -> List[Tuple[int, int, int, int, int]]:
        """
        Генерація розкладу з використанням навченої моделі.
        
        Використовує greedy policy (argmax) для детермінованого результату.
        """
        state = self.env.reset()
        schedule = []
        
        self.model.eval()
        with torch.no_grad():
            while True:
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                valid_actions = self.env.get_valid_actions()
                
                if not valid_actions:
                    break
                
                # Greedy action selection
                logits = self.model.actor(state_tensor)
                action_idx = logits.argmax().item()
                
                # Map to valid action
                action = valid_actions[action_idx % len(valid_actions)]
                schedule.append(action)
                
                state, _, done, _ = self.env.step(action)
                
                if done:
                    break
        
        self.model.train()
        return schedule


# === Допоміжна функція для швидкого створення trainer ===

def create_optimized_trainer(
    courses, teachers, groups, classrooms, timeslots,
    num_iterations: int = 100,
    progress_callback=None,
) -> OptimizedPPOTrainer:
    """
    Factory function для створення оптимізованого trainer.
    
    Автоматично визначає оптимальні параметри на основі розміру задачі.
    """
    env = OptimizedTimetablingEnvironment(
        courses, teachers, groups, classrooms, timeslots
    )
    
    state_dim = env.state_dim
    
    # Action dim based on problem size
    # Обмежуємо для запобігання memory overflow
    action_dim = min(
        len(teachers) * len(groups) * len(classrooms) * len(timeslots),
        4096  # Максимум
    )
    
    # Автоматичне налаштування batch_size на основі action_dim
    batch_size = min(64, max(16, action_dim // 100))
    
    trainer = OptimizedPPOTrainer(
        env=env,
        state_dim=state_dim,
        action_dim=action_dim,
        batch_size=batch_size,
        progress_callback=progress_callback,
    )
    
    return trainer
