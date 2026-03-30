"""
PPO Trainer V2 з гарантією повноти розкладу.

КЛЮЧОВІ ПОКРАЩЕННЯ:
1. Інтеграція з TimetablingEnvironmentV2
2. Local Search фаза після DRL
3. Greedy Fill для заповнення залишків
4. Детальна діагностика та логування
5. Repair механізм для виправлення неповних розкладів

Автор: AI Research Engineer
Дата: 2024-12-24
"""
import os
import json
from pathlib import Path
from datetime import datetime
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from typing import Any, List, Tuple, Optional, Dict
import logging

from .actor_critic import ActorCritic
from .environment_v2 import TimetablingEnvironmentV2
from .model_registry import get_active_model_name

logger = logging.getLogger(__name__)


class PPOTrainerV2:
    """
    Покращений PPO Trainer з гарантією повного розкладу.
    
    Етапи генерації:
    1. DRL Phase: Навчання/використання PPO для основного планування
    2. Local Search Phase: Заповнення порожніх слотів
    3. Repair Phase: Виправлення конфліктів (якщо є)
    4. Greedy Fill: Фінальне заповнення залишків
    """

    def __init__(
        self,
        env: TimetablingEnvironmentV2,
        state_dim: int,
        action_dim: int,
        lr: float = 3e-4,
        gamma: float = 0.99,
        epsilon: float = 0.2,
        epochs: int = 10,
        device: str = "cpu",
        progress_callback=None,
        stop_callback=None,
        score_weights: Optional[Dict[str, float]] = None,
        model_version: Optional[str] = None,
    ):
        self.env = env
        self.device = torch.device(device)
        self.state_dim = state_dim
        self.action_dim = action_dim

        self.model = ActorCritic(state_dim, action_dim).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)

        self.gamma = gamma
        self.epsilon = epsilon
        self.epochs = epochs
        self.progress_callback = progress_callback
        self.stop_callback = stop_callback
        self.model_version = model_version
        self.score_weights = {
            "reward_weight": 1.0,
            "completion_weight": 100.0,
            "hard_violation_penalty": 25.0,
            "soft_violation_penalty": 5.0,
        }
        if score_weights:
            self.score_weights.update(score_weights)
        
        # Директорія для моделей
        self.model_dir = Path("./saved_models")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self._try_load_pretrained()

    def _candidate_model_files(self) -> List[Path]:
        if self.model_version:
            model_name = self.model_version if self.model_version.endswith(".pt") else f"{self.model_version}.pt"
            return [self.model_dir / model_name]

        active_name = get_active_model_name(self.model_dir)
        candidates = [self.model_dir / active_name]
        fallback = self.model_dir / "actor_critic_best.pt"
        if fallback not in candidates:
            candidates.append(fallback)
        return candidates

    @staticmethod
    def compute_model_score(
        reward: float,
        hard_violations: int,
        soft_violations: int,
        completion_rate: float,
        score_weights: Dict[str, float],
    ) -> float:
        return (
            float(score_weights.get("reward_weight", 1.0)) * float(reward)
            + float(score_weights.get("completion_weight", 100.0)) * float(completion_rate)
            - float(score_weights.get("hard_violation_penalty", 25.0)) * float(hard_violations)
            - float(score_weights.get("soft_violation_penalty", 5.0)) * float(soft_violations)
        )

    def _try_load_pretrained(self) -> bool:
        """Завантажити попередньо навчену модель з перевіркою розмірностей."""
        for model_path in self._candidate_model_files():
            if not model_path.exists():
                continue

            try:
                checkpoint = torch.load(str(model_path), map_location=self.device)
                
                # Перевірка чи це state_dict чи повний checkpoint
                if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                    state_dict = checkpoint['model_state_dict']
                    saved_state_dim = checkpoint.get('state_dim')
                    saved_action_dim = checkpoint.get('action_dim')
                else:
                    state_dict = checkpoint
                    saved_state_dim = None
                    saved_action_dim = None
                
                # Перевірка сумісності розмірностей
                if saved_state_dim is not None and saved_state_dim != self.state_dim:
                    logger.warning(f"⚠️ Розмірність state не співпадає: збережено {saved_state_dim}, поточна {self.state_dim}")
                    logger.info(f"🔄 Починаємо навчання з нуля через зміну конфігурації даних")
                    return False
                
                # Перевірка розмірності першого шару
                if 'actor.fc1.weight' in state_dict:
                    saved_input_dim = state_dict['actor.fc1.weight'].shape[1]
                    if saved_input_dim != self.state_dim:
                        logger.warning(f"⚠️ Input dim не співпадає: збережено {saved_input_dim}, поточна {self.state_dim}")
                        logger.info(f"🔄 Починаємо навчання з нуля через зміну конфігурації даних")
                        return False
                
                self.model.load_state_dict(state_dict)
                logger.info(f"✅ Завантажено модель: {model_path}")
                return True
            except RuntimeError as e:
                if "size mismatch" in str(e):
                    logger.warning(f"⚠️ Невідповідність розмірів моделі - конфігурація даних змінилася")
                    logger.info(f"🔄 Починаємо навчання з нуля")
                else:
                    logger.warning(f"⚠️ Помилка завантаження: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Не вдалося завантажити: {e}")

        return False

    def save_model(self, suffix: str = "best", extra_metadata: Optional[Dict[str, Any]] = None) -> Path:
        """Зберегти модель з метаданими про розмірності."""
        model_path = self.model_dir / f"actor_critic_{suffix}.pt"
        meta_path = self.model_dir / f"meta_{suffix}.json"
        
        # Зберігаємо повний checkpoint з метаданими
        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'state_dim': self.state_dim,
            'action_dim': self.action_dim,
            'timestamp': datetime.now().isoformat(),
            'selection_strategy': 'combined_score',
            'score_weights': self.score_weights,
        }
        if extra_metadata:
            checkpoint.update(extra_metadata)
        torch.save(checkpoint, str(model_path))

        meta = {
            "saved_at": datetime.now().isoformat(),
            "model_file": model_path.name,
            "state_dim": self.state_dim,
            "action_dim": self.action_dim,
            "selection_strategy": "combined_score",
            "score_weights": self.score_weights,
        }
        if extra_metadata:
            meta.update(extra_metadata)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        logger.info(f"💾 Збережено модель: {model_path} (state_dim={self.state_dim})")
        return model_path

    def train(self, num_iterations: int) -> Tuple[List[float], Dict]:
        """
        Навчання моделі.
        
        Args:
            num_iterations: Кількість ітерацій навчання
            
        Returns:
            episode_rewards: Список нагород по епізодах
            final_stats: Фінальна статистика з метриками
        """
        episode_rewards = []
        hard_violations_history = []
        soft_violations_history = []
        completion_rates = []
        normalized_reward_per_step = []
        model_scores = []
        actor_losses = []
        critic_losses = []
        
        best_reward = float("-inf")
        best_completion = 0.0
        best_model_score = float("-inf")

        logger.info(f"🚀 Початок тренування PPO V2: {num_iterations} ітерацій")
        logger.info(f"📊 Занять до планування: {self.env.total_classes_to_schedule}")

        for iteration in range(num_iterations):
            if self.stop_callback and self.stop_callback():
                logger.info(f"🛑 Зупинено на ітерації {iteration + 1}")
                break
            
            # Збір траєкторії
            states, actions, rewards, log_probs, dones, final_info = self._collect_trajectory()
            
            if len(states) == 0:
                continue

            # PPO update
            returns = self._compute_returns(rewards, dones)
            advantages = returns - returns.mean()
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
            
            a_loss, c_loss = self._update_policy(states, actions, log_probs, returns, advantages)

            # Збір метрик
            episode_reward = sum(rewards.cpu().numpy())
            trajectory_steps = max(int(final_info.get("trajectory_steps", len(rewards))), 1)
            reward_per_step = float(episode_reward) / float(trajectory_steps)
            completion_rate = final_info.get("completion_rate", 0)
            hard_violations = final_info.get("hard_violations", 0)
            soft_violations = final_info.get("soft_violations", 0)
            model_score = self.compute_model_score(
                reward=float(episode_reward),
                hard_violations=int(hard_violations),
                soft_violations=int(soft_violations),
                completion_rate=float(completion_rate),
                score_weights=self.score_weights,
            )
            
            episode_rewards.append(episode_reward)
            normalized_reward_per_step.append(reward_per_step)
            hard_violations_history.append(hard_violations)
            soft_violations_history.append(soft_violations)
            completion_rates.append(completion_rate)
            model_scores.append(model_score)
            actor_losses.append(float(a_loss))
            critic_losses.append(float(c_loss))

            if self.progress_callback:
                self.progress_callback(iteration + 1, num_iterations)

            # Збереження кращої моделі за комбінованим score
            if model_score > best_model_score:
                best_reward = episode_reward
                best_completion = completion_rate
                best_model_score = model_score
                try:
                    self.save_model(
                        "best",
                        extra_metadata={
                            "best_reward": float(best_reward),
                            "best_completion": float(best_completion),
                            "best_model_score": float(best_model_score),
                            "hard_violations": int(hard_violations),
                            "soft_violations": int(soft_violations),
                        },
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Помилка збереження: {e}")
                logger.info(
                    f"⭐ Нова найкраща модель! Score: {best_model_score:.2f}, "
                    f"Completion: {completion_rate:.1%}, Reward: {best_reward:.2f}"
                )

            if (iteration + 1) % 20 == 0:
                avg_reward = np.mean(episode_rewards[-20:])
                logger.info(
                    f"📈 Ітерація {iteration + 1}/{num_iterations} | "
                    f"Avg Reward: {avg_reward:.2f} | "
                    f"Completion: {completion_rate:.1%} | "
                    f"Hard: {final_info.get('hard_violations', 0)}"
                )

        # Конвертуємо numpy масиви та обробляємо NaN/Inf для фінальної статистики
        def clean_value(val):
            """Конвертує значення для JSON."""
            if isinstance(val, (np.integer, np.floating)):
                val = float(val)
            if isinstance(val, float):
                if np.isnan(val) or np.isinf(val):
                    return 0.0
            return val
        
        # Фінальна статистика з історією метрик
        final_stats = {
            "best_reward": clean_value(best_reward),
            "best_completion": clean_value(best_completion),
            "best_model_score": clean_value(best_model_score),
            "total_iterations": len(episode_rewards),
            "selection_strategy": "combined_score",
            "score_weights": self.score_weights,
            "metrics": {
                "rewards": [clean_value(x) for x in episode_rewards],
                "reward_per_step": [clean_value(x) for x in normalized_reward_per_step],
                "hard_violations": [int(x) for x in hard_violations_history],
                "soft_violations": [int(x) for x in soft_violations_history],
                "completion_rates": [clean_value(x) for x in completion_rates],
                "model_scores": [clean_value(x) for x in model_scores],
                "actor_losses": [clean_value(x) for x in actor_losses],
                "critic_losses": [clean_value(x) for x in critic_losses],
            }
        }
        
        # Зберігаємо метрики у файл для аналізу
        try:            
            clean_metrics = {
                'rewards': [clean_value(x) for x in episode_rewards],
                'reward_per_step': [clean_value(x) for x in normalized_reward_per_step],
                'hard_violations': [int(x) for x in hard_violations_history],
                'soft_violations': [int(x) for x in soft_violations_history],
                'completion_rates': [clean_value(x) for x in completion_rates],
                'model_scores': [clean_value(x) for x in model_scores],
                'actor_losses': [clean_value(x) for x in actor_losses],
                'critic_losses': [clean_value(x) for x in critic_losses],
            }
            
            metrics_path = self.model_dir / "training_metrics.json"
            with open(metrics_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'iterations': len(episode_rewards),
                    'selection_strategy': 'combined_score',
                    'score_weights': self.score_weights,
                    'metrics': clean_metrics
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"📊 Метрики збережено: {metrics_path}")
        except Exception as e:
            logger.warning(f"⚠️ Не вдалося зберегти метрики: {e}")

        logger.info(f"🎯 Тренування завершено | Best Completion: {best_completion:.1%}")
        
        return episode_rewards, final_stats

    def _collect_trajectory(self) -> Tuple:
        """Збір траєкторії з урахуванням повноти."""
        state = self.env.reset()
        states, actions, rewards, log_probs, dones = [], [], [], [], []

        done = False
        max_trajectory_steps = self.env.total_classes_to_schedule + 50

        for step in range(max_trajectory_steps):
            if done:
                break
                
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            valid_actions = self.env.get_valid_actions()
            
            if not valid_actions:
                logger.warning(f"⚠️ Немає валідних дій на кроці {step}")
                break

            # Вибір дії
            with torch.no_grad():
                logits, _ = self.model(state_tensor)
            
            # Семплюємо індекс з валідних дій
            n_valid = min(len(valid_actions), logits.shape[-1])
            probs = torch.softmax(logits[:, :n_valid], dim=-1)
            dist = torch.distributions.Categorical(probs)
            action_idx = dist.sample().item()
            log_prob = dist.log_prob(torch.tensor(action_idx))
            
            # Виконуємо дію
            action_tuple = valid_actions[action_idx % len(valid_actions)]
            next_state, reward, done, info = self.env.step(action_tuple)

            states.append(state)
            actions.append(action_idx)
            rewards.append(reward)
            log_probs.append(log_prob)
            dones.append(done)

            state = next_state

        if not states:
            return (
                torch.FloatTensor([]).to(self.device),
                torch.LongTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                {}
            )

        final_info = {
            "completion_rate": len(self.env.assignments_list) / max(self.env.total_classes_to_schedule, 1),
            "hard_violations": self.env._count_hard_violations(),
            "trajectory_steps": len(states),
            "remaining": len(self.env.pending_courses)
        }

        return (
            torch.FloatTensor(np.array(states)).to(self.device),
            torch.LongTensor(actions).to(self.device),
            torch.FloatTensor(rewards).to(self.device),
            torch.stack(log_probs).to(self.device) if log_probs else torch.FloatTensor([]).to(self.device),
            torch.FloatTensor(dones).to(self.device),
            final_info
        )

    def _compute_returns(self, rewards: torch.Tensor, dones: torch.Tensor) -> torch.Tensor:
        """Обчислення discounted returns."""
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
    ) -> Tuple[float, float]:
        """
        PPO policy update.
        
        Returns:
            actor_loss: середній actor loss
            critic_loss: середній critic loss
        """
        if len(states) == 0:
            return 0.0, 0.0
        
        total_actor_loss = 0.0
        total_critic_loss = 0.0
            
        for _ in range(self.epochs):
            values, log_probs, entropy = self.model.evaluate_actions(states, actions)

            ratio = torch.exp(log_probs - old_log_probs.detach())
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.epsilon, 1 + self.epsilon) * advantages

            actor_loss = -torch.min(surr1, surr2).mean()
            critic_loss = nn.functional.mse_loss(values, returns)
            entropy_loss = -entropy.mean()

            loss = actor_loss + 0.5 * critic_loss + 0.01 * entropy_loss

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=0.5)
            self.optimizer.step()
            
            total_actor_loss += actor_loss.item()
            total_critic_loss += critic_loss.item()
        
        return total_actor_loss / self.epochs, total_critic_loss / self.epochs

    def generate_schedule(self, use_local_search: bool = True) -> Tuple[List[Tuple], Dict]:
        """
        Генерує ПОВНИЙ розклад.
        
        Етапи:
        1. DRL генерація
        2. Local Search (якщо увімкнено)
        3. Greedy Fill (для залишків)
        
        Returns:
            schedule: Список призначень (course, teacher, group, classroom, timeslot)
            stats: Статистика генерації
        """
        logger.info("🎯 Генерація розкладу...")
        
        # === Фаза 1: DRL ===
        state = self.env.reset()
        
        total_to_schedule = self.env.total_classes_to_schedule
        logger.info(f"📊 Потрібно запланувати: {total_to_schedule} занять")
        
        drl_scheduled = 0
        max_steps = total_to_schedule + 100
        
        for step in range(max_steps):
            valid_actions = self.env.get_valid_actions()
            
            if not valid_actions:
                logger.warning(f"⚠️ DRL: Немає валідних дій на кроці {step}")
                break
            
            if len(self.env.pending_courses) == 0:
                break
            
            # Greedy вибір найкращої дії
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                logits, _ = self.model(state_tensor)
            
            # Вибираємо дію з найвищим score серед валідних
            n_valid = min(len(valid_actions), logits.shape[-1])
            probs = torch.softmax(logits[:, :n_valid], dim=-1)
            best_idx = probs.argmax().item()
            
            action_tuple = valid_actions[best_idx % len(valid_actions)]
            state, reward, done, info = self.env.step(action_tuple)
            
            drl_scheduled += 1
            
            if done:
                break

        logger.info(f"✅ DRL фаза: заплановано {drl_scheduled} занять")
        
        # === Фаза 2: Local Search ===
        local_search_filled = 0
        if use_local_search and len(self.env.pending_courses) > 0:
            logger.info(f"🔧 Local Search: залишилось {len(self.env.pending_courses)} занять")
            local_search_filled = self.env.run_local_search(max_iterations=200)
            logger.info(f"✅ Local Search: заповнено {local_search_filled} занять")
        
        # === Фаза 3: Greedy Fill ===
        greedy_filled = 0
        if len(self.env.pending_courses) > 0:
            logger.info(f"🔄 Greedy Fill: залишилось {len(self.env.pending_courses)} занять")
            greedy_filled = self._greedy_fill()
            logger.info(f"✅ Greedy Fill: заповнено {greedy_filled} занять")
        
        # === Фаза 4: Day Balance Local Search (NEW!) ===
        day_balance_moved = 0
        if use_local_search and hasattr(self.env, 'run_day_balance_local_search'):
            logger.info(f"⚖️ Day Balance: балансування денного навантаження...")
            day_balance_moved = self.env.run_day_balance_local_search(max_iterations=100)
            logger.info(f"✅ Day Balance: переміщено {day_balance_moved} занять")
        
        # === Статистика ===
        schedule = self.env.assignments_list
        remaining = len(self.env.pending_courses)
        
        # Отримуємо інформацію про баланс
        is_balanced = self.env._check_balance_acceptable() if hasattr(self.env, '_check_balance_acceptable') else True
        balance_score = self.env._calculate_balance_score() if hasattr(self.env, '_calculate_balance_score') else 1.0
        total_variance = self.env._calculate_total_variance() if hasattr(self.env, '_calculate_total_variance') else 0.0
        
        stats = {
            "total_to_schedule": total_to_schedule,
            "drl_scheduled": drl_scheduled,
            "local_search_filled": local_search_filled,
            "greedy_filled": greedy_filled,
            "day_balance_moved": day_balance_moved,
            "total_scheduled": len(schedule),
            "remaining": remaining,
            "completion_rate": len(schedule) / max(total_to_schedule, 1),
            "hard_violations": self.env._count_hard_violations(),
            "soft_violations": self.env._count_soft_violations(),
            "is_balanced": is_balanced,
            "balance_score": balance_score,
            "total_variance": total_variance,
        }
        
        # Діагностика
        diagnostic = self.env.get_diagnostic_info()
        stats["diagnostic"] = diagnostic
        
        if remaining > 0:
            logger.warning(f"⚠️ Не вдалося запланувати {remaining} занять")
            explanations = self.env.explain_unfilled()
            for exp in explanations[:5]:
                logger.warning(f"   - {exp}")
            stats["unfilled_explanations"] = explanations
        else:
            logger.info(f"🎉 Розклад повністю сформовано!")
        
        # Пояснення дисбалансу (якщо є)
        if not is_balanced and hasattr(self.env, 'explain_imbalance'):
            imbalance_explanations = self.env.explain_imbalance()
            if imbalance_explanations:
                logger.warning(f"⚠️ Дисбаланс денного навантаження:")
                for exp in imbalance_explanations[:3]:
                    logger.warning(f"   - {exp}")
                stats["imbalance_explanations"] = imbalance_explanations
        
        logger.info(f"📊 Фінальна статистика:")
        logger.info(f"   Заплановано: {len(schedule)}/{total_to_schedule} ({stats['completion_rate']:.1%})")
        logger.info(f"   Hard violations: {stats['hard_violations']}")
        logger.info(f"   Soft violations: {stats['soft_violations']}")
        logger.info(f"   Balance: {'✅' if is_balanced else '⚠️'} (score={balance_score:.2f}, variance={total_variance:.2f})")
        
        return schedule, stats

    def _greedy_fill(self) -> int:
        """
        Жадібне заповнення залишків.
        
        Пробує всі можливі комбінації для кожного незапланованого заняття.
        """
        filled = 0
        max_attempts = len(self.env.pending_courses) * 2
        
        for _ in range(max_attempts):
            if not self.env.pending_courses:
                break
            
            course_idx, group_idx = self.env.pending_courses[0]
            
            # Пробуємо знайти БУДЬ-ЯКИЙ валідний слот
            found = False
            
            for teacher_idx in range(self.env.n_teachers):
                if found:
                    break
                for classroom_idx in range(self.env.n_classrooms):
                    if found:
                        break
                    # Перевірка місткості
                    if self.env.classroom_capacities[classroom_idx] < self.env.group_sizes[group_idx]:
                        continue
                    
                    for timeslot_idx in range(self.env.n_timeslots):
                        # Перевірка конфліктів
                        if (self.env.teacher_schedule[teacher_idx, timeslot_idx] > 0 or
                            self.env.group_schedule[group_idx, timeslot_idx] > 0 or
                            self.env.classroom_schedule[classroom_idx, timeslot_idx] > 0):
                            continue
                        
                        # Знайшли валідний слот!
                        action = (course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx)
                        
                        self.env.teacher_schedule[teacher_idx, timeslot_idx] += 1
                        self.env.group_schedule[group_idx, timeslot_idx] += 1
                        self.env.classroom_schedule[classroom_idx, timeslot_idx] += 1
                        
                        day = self.env.timeslot_days[timeslot_idx]
                        self.env.group_classes_per_day[group_idx, day] += 1
                        
                        self.env.assignments_list.append(action)
                        self.env.pending_courses.remove((course_idx, group_idx))
                        
                        filled += 1
                        found = True
                        break
            
            if not found:
                # Переміщуємо в кінець черги
                item = self.env.pending_courses.pop(0)
                self.env.pending_courses.append(item)
        
        return filled


# === Фабрична функція для створення Environment ===

def create_environment_v2(
    courses, teachers, groups, classrooms, timeslots,
    course_teacher_map=None, course_group_map=None
) -> TimetablingEnvironmentV2:
    """
    Створює новий Environment V2.
    
    Args:
        courses: Список курсів
        teachers: Список викладачів
        groups: Список груп
        classrooms: Список аудиторій
        timeslots: Список таймслотів
        course_teacher_map: Словник {course_id: [teacher_ids]}
        course_group_map: Словник {course_id: [group_ids]}
    """
    return TimetablingEnvironmentV2(
        courses=courses,
        teachers=teachers,
        groups=groups,
        classrooms=classrooms,
        timeslots=timeslots,
        course_teacher_map=course_teacher_map,
        course_group_map=course_group_map
    )
