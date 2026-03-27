"""PPO Trainer для навчання Actor-Critic моделі."""
import os
import json
from pathlib import Path
from datetime import datetime
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from typing import List, Tuple, Optional
import logging

from .actor_critic import ActorCritic
from .environment import TimetablingEnvironment
from .model_registry import get_active_model_name

logger = logging.getLogger(__name__)


class PPOTrainer:
    """Proximal Policy Optimization trainer."""

    def __init__(
        self,
        env: TimetablingEnvironment,
        state_dim: int,
        action_dim: int,
        lr: float = 3e-4,
        gamma: float = 0.99,
        epsilon: float = 0.2,
        epochs: int = 10,
        device: str = "cpu",
        progress_callback=None,  # Callback для оновлення прогресу
        stop_callback=None,  # Callback для перевірки зупинки
        model_version: Optional[str] = None,
        score_weights: Optional[dict] = None,
    ):
        self.env = env
        self.device = torch.device(device)

        self.model = ActorCritic(state_dim, action_dim).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)

        self.gamma = gamma
        self.epsilon = epsilon
        self.epochs = epochs
        self.progress_callback = progress_callback
        self.stop_callback = stop_callback
        self.model_version = model_version
        self.score_weights = score_weights or {}
        
        # Директорія для збереження моделей
        self.model_dir = Path("./backend/saved_models")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Спробувати завантажити попередньо навчену модель
        self._try_load_pretrained()
    
    def _try_load_pretrained(self) -> bool:
        """Спробувати завантажити збережену модель."""
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

            try:
                state_dict = torch.load(str(model_path), map_location=self.device)
                self.model.load_state_dict(state_dict)
                logger.info(f"✅ Завантажено попередньо навчену модель: {model_path}")
                
                # Завантажити оптимізатор якщо є
                optim_path = self.model_dir / "optimizer_best.pt"
                if optim_path.exists():
                    optim_state = torch.load(str(optim_path), map_location=self.device)
                    self.optimizer.load_state_dict(optim_state)
                    logger.info(f"✅ Завантажено стан оптимізатора")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Не вдалося завантажити модель: {e}")

        return False
    
    def save_model(self, suffix: str = "best") -> Path:
        """Зберегти модель на диск."""
        model_path = self.model_dir / f"actor_critic_{suffix}.pt"
        optim_path = self.model_dir / f"optimizer_{suffix}.pt"
        meta_path = self.model_dir / f"meta_{suffix}.json"
        
        torch.save(self.model.state_dict(), str(model_path))
        torch.save(self.optimizer.state_dict(), str(optim_path))
        
        # Зберегти метадані
        meta = {
            "saved_at": datetime.now().isoformat(),
            "gamma": self.gamma,
            "epsilon": self.epsilon,
            "epochs": self.epochs,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        
        logger.info(f"💾 Збережено модель: {model_path}")
        return model_path

    def train(self, num_iterations: int) -> Tuple[List[float], dict]:
        """Навчає модель на протязі num_iterations епізодів."""
        episode_rewards = []
        best_reward = float("-inf")
        best_state_dict = None

        logger.info(f"🚀 Початок тренування DRL: {num_iterations} ітерацій")
        logger.info(f"📊 Параметри: gamma={self.gamma}, epsilon={self.epsilon}, epochs={self.epochs}")

        for iteration in range(num_iterations):
            # Перевірка зупинки
            if self.stop_callback and self.stop_callback():
                logger.info(f"🛑 Тренування зупинено на ітерації {iteration + 1}")
                break
            
            # Збір траєкторії
            states, actions, rewards, log_probs, dones = self._collect_trajectory()

            # Обчислення returns і advantages
            returns = self._compute_returns(rewards, dones)
            advantages = returns  # Simplified (можна використати GAE)

            # Нормалізація advantages
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

            # PPO update
            self._update_policy(states, actions, log_probs, returns, advantages)

            # Логування
            episode_reward = sum(rewards)
            episode_rewards.append(episode_reward)

            # Оновлення прогресу через callback
            if self.progress_callback:
                self.progress_callback(iteration + 1, num_iterations)

            if episode_reward > best_reward:
                best_reward = episode_reward
                best_state_dict = self.model.state_dict().copy()
                logger.info(f"⭐ Нова найкраща винагорода: {best_reward:.2f} (ітерація {iteration + 1})")
                # Зберігаємо кращу модель на диск
                try:
                    self.save_model("best")
                except Exception as e:
                    logger.warning(f"⚠️ Не вдалося зберегти модель: {e}")

            # Виводимо прогрес кожні 50 ітерацій
            if (iteration + 1) % 50 == 0:
                avg_reward = np.mean(episode_rewards[-50:])
                hard_violations = self.env._count_hard_violations()
                soft_violations = self.env._count_soft_violations()
                progress = ((iteration + 1) / num_iterations) * 100
                logger.info(
                    f"📈 Ітерація {iteration + 1}/{num_iterations} ({progress:.1f}%) | "
                    f"Avg Reward: {avg_reward:.2f} | Hard: {hard_violations} | Soft: {soft_violations}"
                )
            # Виводимо кожні 10 ітерацій для більш детального моніторингу
            elif (iteration + 1) % 10 == 0:
                avg_reward = np.mean(episode_rewards[-10:])
                logger.info(f"⏳ Ітерація {iteration + 1}/{num_iterations} | Avg Reward: {avg_reward:.2f}")

        # Відновлення найкращих ваг
        if best_state_dict:
            self.model.load_state_dict(best_state_dict)
            logger.info(f"✅ Відновлено найкращу модель (винагорода: {best_reward:.2f})")
            # Зберігаємо фінальну модель
            try:
                self.save_model("final")
            except Exception as e:
                logger.warning(f"⚠️ Не вдалося зберегти фінальну модель: {e}")

        final_stats = {
            "best_reward": best_reward,
            "final_hard_violations": self.env._count_hard_violations(),
            "final_soft_violations": self.env._count_soft_violations(),
        }

        logger.info(f"🎯 Завершення тренування | Best Reward: {best_reward:.2f}")
        logger.info(f"🎯 Фінальні показники | Hard: {final_stats['final_hard_violations']} | Soft: {final_stats['final_soft_violations']}")

        return episode_rewards, final_stats

    def _collect_trajectory(self) -> Tuple[torch.Tensor, ...]:
        """Збирає траєкторію (епізод)."""
        state = self.env.reset()
        states, actions, rewards, log_probs, dones = [], [], [], [], []

        done = False
        while not done:
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

            # Отримання валідних дій
            valid_actions = self.env.get_valid_actions()
            if not valid_actions:
                break  # Немає валідних дій

            # Вибір дії
            action, log_prob = self.model.get_action(state_tensor)

            # Виконання дії (simplified: використовуємо випадкову валідну дію)
            random_valid_action = valid_actions[np.random.randint(len(valid_actions))]
            next_state, reward, done, info = self.env.step(random_valid_action)

            states.append(state)
            actions.append(action)
            rewards.append(reward)
            log_probs.append(log_prob)
            dones.append(done)

            state = next_state

        return (
            torch.FloatTensor(np.array(states)).to(self.device),
            torch.LongTensor(actions).to(self.device),
            torch.FloatTensor(rewards).to(self.device),
            torch.stack(log_probs).to(self.device),
            torch.FloatTensor(dones).to(self.device),
        )

    def _compute_returns(self, rewards: torch.Tensor, dones: torch.Tensor) -> torch.Tensor:
        """Обчислює discounted returns."""
        returns = []
        R = 0
        for r, done in zip(reversed(rewards.cpu().numpy()), reversed(dones.cpu().numpy())):
            R = r + self.gamma * R * (1 - done)
            returns.insert(0, R)
        return torch.FloatTensor(returns).to(self.device)

    def _update_policy(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        old_log_probs: torch.Tensor,
        returns: torch.Tensor,
        advantages: torch.Tensor,
    ):
        """PPO policy update."""
        for _ in range(self.epochs):
            values, log_probs, entropy = self.model.evaluate_actions(states, actions)

            # PPO ratio
            ratio = torch.exp(log_probs - old_log_probs.detach())
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.epsilon, 1 + self.epsilon) * advantages

            # Loss
            actor_loss = -torch.min(surr1, surr2).mean()
            critic_loss = nn.functional.mse_loss(values, returns)
            entropy_loss = -entropy.mean()

            loss = actor_loss + 0.5 * critic_loss + 0.01 * entropy_loss

            # Backprop
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=0.5)
            self.optimizer.step()

    def generate_schedule(self) -> List[Tuple[int, int, int, int, int]]:
        """Генерує розклад за допомогою навченої моделі."""
        state = self.env.reset()
        schedule = []

        done = False
        while not done:
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            valid_actions = self.env.get_valid_actions()

            if not valid_actions:
                break

            # Greedy action
            with torch.no_grad():
                logits = self.model.actor(state_tensor)
                action = logits.argmax().item()

            # Якщо дія невалідна, беремо випадкову валідну
            if action >= len(valid_actions):
                action_tuple = valid_actions[0]
            else:
                action_tuple = valid_actions[action % len(valid_actions)]

            schedule.append(action_tuple)
            state, reward, done, info = self.env.step(action_tuple)

        return schedule
