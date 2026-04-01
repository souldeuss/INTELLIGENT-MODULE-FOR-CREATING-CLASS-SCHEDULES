"""
Enhanced PPO Trainer з підтримкою:
- Dynamic Learning Rate Scheduling
- Training Metrics Collection & Visualization
- Persistent Learning (Checkpoints)
- Runtime Hyperparameter Control
- Stability Monitoring

Це ОСНОВНИЙ модуль навчання, який інтегрує всі компоненти.

Автор: AI Research Engineer
Дата: 2024-12-25
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
from typing import List, Tuple, Optional, Callable, Dict, Any
import logging
import time
import threading

from .actor_critic import ActorCritic
from .environment_optimized import OptimizedTimetablingEnvironment
from .lr_scheduler import (
    BaseLRScheduler, 
    create_lr_scheduler,
    CombinedScheduler,
    ReduceOnPlateauScheduler,
)
from .training_metrics import TrainingMetricsCollector, get_metrics_collector
from .training_visualizer import TrainingVisualizer, visualize_current_training
from .checkpoint_manager import CheckpointManager, get_checkpoint_manager

logger = logging.getLogger(__name__)


class EnhancedPPOTrainer:
    """
    Покращений PPO Trainer з повною підтримкою:
    
    1. Dynamic Learning Rate:
       - Підтримка різних стратегій (cosine, plateau, combined)
       - Warmup фаза для стабільного старту
       - Автоматичне зменшення при plateau
    
    2. Training Monitoring:
       - Збір метрик на кожній ітерації
       - Аналіз стабільності
       - Експорт для GUI
    
    3. Persistent Learning:
       - Автоматичне збереження checkpoints
       - Відновлення з попереднього стану
       - Fine-tuning з частковим скиданням
    
    4. Runtime Control:
       - Зміна гіперпараметрів під час навчання
       - Warmup після змін для стабільності
       - Policy divergence detection
    """

    def __init__(
        self,
        env: OptimizedTimetablingEnvironment,
        state_dim: int,
        action_dim: int,
        
        # Learning rate config
        lr: float = 3e-4,
        lr_scheduler_type: str = "combined",  # linear, cosine, plateau, combined
        lr_warmup_ratio: float = 0.1,
        lr_min: float = 1e-6,
        
        # PPO hyperparameters
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        epsilon: float = 0.2,
        epochs: int = 4,
        
        # Training config
        batch_size: int = 64,
        n_steps: int = 128,
        num_envs: int = 4,
        
        # Loss coefficients
        value_coef: float = 0.5,
        entropy_coef: float = 0.01,
        max_grad_norm: float = 0.5,
        
        # Device
        device: str = "auto",
        use_mixed_precision: bool = True,
        
        # Callbacks
        progress_callback: Optional[Callable] = None,
        stop_callback: Optional[Callable] = None,
        
        # Persistent learning
        checkpoint_dir: Path = None,
        auto_save_interval: int = 50,
        keep_best_n: int = 3,
        
        # Visualization
        visualization_dir: Path = None,
        generate_plots: bool = True,
    ):
        """
        Ініціалізація Enhanced PPO Trainer.
        
        Args:
            env: Середовище для навчання
            state_dim: Розмірність стану
            action_dim: Розмірність дій
            
            lr: Початковий learning rate
            lr_scheduler_type: Тип LR scheduler
            lr_warmup_ratio: Частка ітерацій на warmup
            lr_min: Мінімальний LR
            
            gamma: Discount factor
            gae_lambda: GAE lambda
            epsilon: PPO clip range
            epochs: Кількість epochs на ітерацію
            
            batch_size: Розмір mini-batch
            n_steps: Кроків перед оновленням
            num_envs: Кількість паралельних середовищ
            
            value_coef: Коефіцієнт value loss
            entropy_coef: Коефіцієнт entropy bonus
            max_grad_norm: Максимальна норма градієнтів
            
            device: Пристрій (auto, cpu, cuda)
            use_mixed_precision: Використовувати FP16
            
            progress_callback: Callback для прогресу
            stop_callback: Callback для перевірки зупинки
            
            checkpoint_dir: Директорія для checkpoints
            auto_save_interval: Інтервал автозбереження
            keep_best_n: Зберігати N найкращих
            
            visualization_dir: Директорія для графіків
            generate_plots: Генерувати графіки після навчання
        """
        # Device setup
        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        logger.info(f"🖥️ Device: {self.device}")
        
        # Environment
        self.env = env
        self.num_envs = num_envs
        self.n_steps = n_steps
        self.batch_size = batch_size
        
        # Store dimensions
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Neural network
        self.model = ActorCritic(state_dim, action_dim).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr, eps=1e-5)
        
        # PPO hyperparameters (stored for runtime modification)
        self.config = {
            "gamma": gamma,
            "gae_lambda": gae_lambda,
            "epsilon": epsilon,
            "epochs": epochs,
            "value_coef": value_coef,
            "entropy_coef": entropy_coef,
            "max_grad_norm": max_grad_norm,
        }
        
        # LR Scheduler (буде створено в train())
        self.lr_scheduler_type = lr_scheduler_type
        self.lr_warmup_ratio = lr_warmup_ratio
        self.lr_min = lr_min
        self.initial_lr = lr
        self.lr_scheduler: Optional[BaseLRScheduler] = None
        
        # Mixed precision
        self.use_mixed_precision = use_mixed_precision and self.device.type == "cuda"
        if self.use_mixed_precision:
            self.scaler = GradScaler()
            logger.info("⚡ Mixed precision (FP16) enabled")
        
        # Callbacks
        self.progress_callback = progress_callback
        self.stop_callback = stop_callback
        
        # === Metrics Collection ===
        self.metrics_collector = get_metrics_collector()
        
        # === Checkpoint Manager ===
        self.checkpoint_manager = CheckpointManager(
            checkpoint_dir=checkpoint_dir or Path("./backend/checkpoints"),
            max_checkpoints=20,
            keep_best_n=keep_best_n,
            auto_save_interval=auto_save_interval,
        )
        self.auto_save_interval = auto_save_interval
        
        # === Visualization ===
        self.visualizer = TrainingVisualizer(
            output_dir=visualization_dir or Path("./backend/training_plots"),
            style="dark",
        )
        self.generate_plots = generate_plots
        
        # === Training State ===
        self.reward_history = deque(maxlen=100)
        self.best_reward = float("-inf")
        self.best_iteration = 0
        self.no_improvement_count = 0
        
        # Early stopping
        self.early_stop_patience = 50
        self.early_stop_threshold = 0.01
        
        # Curriculum learning
        self.curriculum_enabled = True
        self.curriculum_stage = 0
        
        # Try to load pretrained model
        self._try_load_pretrained()
    
    def _try_load_pretrained(self) -> bool:
        """Спробувати завантажити попередньо навчену модель з сумісними розмірами."""
        try:
            result = self.checkpoint_manager.load_latest(
                self.model,
                self.optimizer,
                self.device,
                filter_best=True,
                state_dim=self.state_dim,
                action_dim=self.action_dim,
            )
            
            if result:
                logger.info(f"✅ Завантажено checkpoint: {result['checkpoint_id']}")
                
                # Restore scheduler state if available
                if result.get('scheduler_state'):
                    # Will be properly initialized in train()
                    self._loaded_scheduler_state = result['scheduler_state']
                
                return True
            else:
                logger.info(f"📥 Немає сумісних checkpoints для state_dim={self.state_dim}")
                
        except ValueError as e:
            logger.warning(f"⚠️ Checkpoint несумісний: {e}")
        except Exception as e:
            logger.info(f"📥 Помилка завантаження: {e}")
        
        return False
    
    def train(
        self,
        num_iterations: int,
        resume_from_checkpoint: str = None,
    ) -> Tuple[List[float], Dict[str, Any]]:
        """
        Основний цикл навчання з усіма покращеннями.
        
        Args:
            num_iterations: Кількість ітерацій
            resume_from_checkpoint: ID checkpoint для продовження
            
        Returns:
            episode_rewards: Історія винагород
            final_stats: Фінальна статистика
        """
        start_time = time.time()
        
        # === Resume from checkpoint if specified ===
        if resume_from_checkpoint:
            result = self.checkpoint_manager.load_checkpoint(
                resume_from_checkpoint,
                self.model,
                self.optimizer,
                self.device,
            )
            logger.info(f"📥 Продовження з checkpoint: {resume_from_checkpoint}")
            
            if result.get('scheduler_state'):
                self._loaded_scheduler_state = result['scheduler_state']
        
        # === Initialize LR Scheduler ===
        self.lr_scheduler = create_lr_scheduler(
            scheduler_type=self.lr_scheduler_type,
            initial_lr=self.initial_lr,
            total_steps=num_iterations,
            warmup_ratio=self.lr_warmup_ratio,
            min_lr=self.lr_min,
        )
        
        # Restore scheduler state if loaded
        if hasattr(self, '_loaded_scheduler_state') and self._loaded_scheduler_state:
            self.lr_scheduler.load_state(self._loaded_scheduler_state)
            delattr(self, '_loaded_scheduler_state')
        
        # === Start metrics session ===
        session_config = {
            "num_iterations": num_iterations,
            "lr_scheduler": self.lr_scheduler_type,
            "initial_lr": self.initial_lr,
            **self.config,
        }
        self.metrics_collector.start_session(session_config)
        
        # === Training loop ===
        episode_rewards = []
        
        logger.info(f"🚀 Початок навчання: {num_iterations} ітерацій")
        logger.info(f"📊 LR Scheduler: {self.lr_scheduler_type}, Initial LR: {self.initial_lr}")
        logger.info(f"📊 PPO: γ={self.config['gamma']}, λ={self.config['gae_lambda']}, ε={self.config['epsilon']}")
        
        state = self.env.reset()
        
        for iteration in range(num_iterations):
            iter_start = time.time()
            
            # === Check for stop signal ===
            if self.stop_callback and self.stop_callback():
                logger.info(f"🛑 Зупинено на ітерації {iteration + 1}")
                break
            
            # === Check for runtime hyperparameter updates ===
            self._apply_pending_updates()
            
            # === Warmup step (if loaded from checkpoint) ===
            self.checkpoint_manager.warmup_step(self.optimizer)
            
            # === Collect rollout ===
            (states, actions, rewards, log_probs,
             values, dones, valid_action_counts) = self._collect_rollout(state)
            
            state = self.env._get_compact_state()
            
            if len(states) == 0:
                continue
            
            # === Compute GAE ===
            with torch.no_grad():
                next_value = self.model.critic(
                    torch.FloatTensor(state).unsqueeze(0).to(self.device)
                ).squeeze()
            
            advantages, returns = self._compute_gae(
                rewards, values, dones, next_value
            )
            
            # === PPO Update ===
            policy_loss, value_loss, entropy, clip_fraction, approx_kl = \
                self._update_policy(states, actions, log_probs, returns, advantages, valid_action_counts)
            
            # === Update LR ===
            episode_reward = rewards.sum().item()
            current_lr = self.lr_scheduler.step(metric=episode_reward)
            
            # Apply new LR to optimizer
            for param_group in self.optimizer.param_groups:
                param_group['lr'] = current_lr
            
            # === Statistics ===
            episode_rewards.append(episode_reward)
            self.reward_history.append(episode_reward)
            
            hard_violations = self.env._count_hard_violations()
            soft_violations = self.env._count_soft_violations()
            
            # === Log metrics ===
            self.metrics_collector.log_step(
                iteration=iteration,
                policy_loss=policy_loss,
                value_loss=value_loss,
                entropy=entropy,
                episode_reward=episode_reward,
                learning_rate=current_lr,
                hard_violations=hard_violations,
                soft_violations=soft_violations,
                completion_rate=len(self.env.assignments_list) / max(len(self.env.pending_courses) + len(self.env.assignments_list), 1),
                clip_fraction=clip_fraction,
                approx_kl=approx_kl,
            )
            
            # === Progress callback ===
            if self.progress_callback:
                self.progress_callback(iteration + 1, num_iterations)
            
            # === Track best ===
            if episode_reward > self.best_reward:
                improvement = episode_reward - self.best_reward
                self.best_reward = episode_reward
                self.best_iteration = iteration
                self.no_improvement_count = 0
                
                if improvement > self.early_stop_threshold:
                    # Save best checkpoint
                    self._save_checkpoint(
                        iteration, 
                        episode_reward, 
                        hard_violations,
                        is_best=True,
                        description=f"Best at iter {iteration}, reward={episode_reward:.2f}"
                    )
                    logger.info(f"⭐ Новий рекорд: {self.best_reward:.2f} (+{improvement:.2f})")
            else:
                self.no_improvement_count += 1
            
            # === Auto-save checkpoint ===
            if (iteration + 1) % self.auto_save_interval == 0:
                self._save_checkpoint(
                    iteration,
                    episode_reward,
                    hard_violations,
                    is_best=False,
                    description=f"Auto-save at iter {iteration + 1}"
                )
            
            # === Early stopping ===
            if self._check_early_stopping():
                logger.info(f"🛑 Early stopping на ітерації {iteration + 1}")
                break
            
            # === Stability check ===
            if (iteration + 1) % 20 == 0:
                stability = self.checkpoint_manager.check_training_stability(
                    list(self.reward_history)
                )
                if not stability['stable']:
                    logger.warning(f"⚠️ Нестабільність: {stability['issues']}")
            
            # === Logging ===
            if (iteration + 1) % 10 == 0:
                iter_time = time.time() - iter_start
                avg_reward = np.mean(list(self.reward_history))
                
                logger.info(
                    f"📈 Iter {iteration + 1}/{num_iterations} | "
                    f"R: {episode_reward:.1f} (avg: {avg_reward:.1f}) | "
                    f"Hard: {hard_violations} | "
                    f"LR: {current_lr:.2e} | "
                    f"Loss: {policy_loss:.3f} | "
                    f"Time: {iter_time:.2f}s"
                )
        
        # === Training completed ===
        total_time = time.time() - start_time
        
        # End metrics session
        stop_reason = "completed"
        if self.stop_callback and self.stop_callback():
            stop_reason = "user_stopped"
        elif self._check_early_stopping():
            stop_reason = "early_stopping"
        
        self.metrics_collector.end_session(status="completed", stop_reason=stop_reason)
        
        # Save final checkpoint
        final_reward = episode_rewards[-1] if episode_rewards else 0
        self._save_checkpoint(
            len(episode_rewards) - 1,
            final_reward,
            self.env._count_hard_violations(),
            is_best=False,
            description="Final checkpoint",
            tags=["final"]
        )
        
        # === Generate visualizations ===
        if self.generate_plots and self.metrics_collector.current_session:
            try:
                saved_plots = self.visualizer.generate_all_plots(
                    self.metrics_collector.current_session,
                    formats=["png"],
                )
                logger.info(f"📊 Згенеровано {len(saved_plots)} графіків")
            except Exception as e:
                logger.warning(f"Error generating plots: {e}")
        
        # Save metrics to file
        try:
            metrics_file = self.metrics_collector.save_to_file()
            logger.info(f"📊 Метрики збережено: {metrics_file}")
        except Exception as e:
            logger.warning(f"Error saving metrics: {e}")
        
        # === Final statistics ===
        final_stats = {
            "best_reward": float(self.best_reward),
            "best_iteration": self.best_iteration,
            "final_reward": float(final_reward),
            "final_hard_violations": self.env._count_hard_violations(),
            "final_soft_violations": self.env._count_soft_violations(),
            "total_time_seconds": total_time,
            "iterations_completed": len(episode_rewards),
            "avg_time_per_iteration": total_time / max(len(episode_rewards), 1),
            "final_learning_rate": self.lr_scheduler.get_lr(),
            "training_summary": self.metrics_collector.get_training_summary(),
        }
        
        logger.info(f"🎯 Навчання завершено за {total_time:.1f}с")
        logger.info(f"🎯 Best reward: {self.best_reward:.2f} @ iter {self.best_iteration}")
        
        return episode_rewards, final_stats
    
    def _collect_rollout(
        self, 
        initial_state: np.ndarray
    ) -> Tuple[torch.Tensor, ...]:
        """Збір даних траєкторії."""
        states_list = []
        actions_list = []
        rewards_list = []
        log_probs_list = []
        values_list = []
        dones_list = []
        valid_action_counts_list = []
        
        state = initial_state
        
        for _ in range(self.n_steps):
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

            valid_actions = self.env.get_valid_actions()
            if not valid_actions:
                break

            # Limit valid actions by model action dimension and mask invalid logits.
            max_model_actions = int(self.action_dim)
            valid_count = min(len(valid_actions), max_model_actions)
            if valid_count <= 0:
                break
            
            with torch.no_grad():
                logits, value = self.model(state_tensor)
                masked_logits = logits.clone()
                if valid_count < masked_logits.size(-1):
                    masked_logits[:, valid_count:] = -1e9

                probs = torch.softmax(masked_logits, dim=-1)
                dist = torch.distributions.Categorical(probs)
                action_idx = dist.sample()
                log_prob = dist.log_prob(action_idx)

            action_idx_int = int(action_idx.item())
            action = valid_actions[action_idx_int]
            
            next_state, reward, done, info = self.env.step(action)
            
            states_list.append(state)
            actions_list.append(action_idx.item())
            rewards_list.append(reward)
            log_probs_list.append(log_prob)
            values_list.append(value.squeeze())
            dones_list.append(done)
            valid_action_counts_list.append(valid_count)
            
            state = next_state
            
            if done:
                state = self.env.reset()
        
        if not states_list:
            return (
                torch.FloatTensor([]).to(self.device),
                torch.LongTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                torch.FloatTensor([]).to(self.device),
                torch.LongTensor([]).to(self.device),
            )
        
        return (
            torch.FloatTensor(np.array(states_list)).to(self.device),
            torch.LongTensor(actions_list).to(self.device),
            torch.FloatTensor(rewards_list).to(self.device),
            torch.stack(log_probs_list).to(self.device),
            torch.stack(values_list).to(self.device),
            torch.FloatTensor(dones_list).to(self.device),
            torch.LongTensor(valid_action_counts_list).to(self.device),
        )
    
    def _compute_gae(
        self,
        rewards: torch.Tensor,
        values: torch.Tensor,
        dones: torch.Tensor,
        next_value: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute Generalized Advantage Estimation."""
        if len(rewards) == 0:
            return torch.FloatTensor([]).to(self.device), torch.FloatTensor([]).to(self.device)
        
        advantages = torch.zeros_like(rewards)
        last_gae = 0
        
        gamma = self.config['gamma']
        gae_lambda = self.config['gae_lambda']
        
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_val = next_value
                next_non_terminal = 1.0 - dones[t]
            else:
                next_val = values[t + 1]
                next_non_terminal = 1.0 - dones[t]
            
            delta = rewards[t] + gamma * next_val * next_non_terminal - values[t]
            advantages[t] = last_gae = delta + gamma * gae_lambda * next_non_terminal * last_gae
        
        returns = advantages + values
        return advantages, returns
    
    def _update_policy(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        old_log_probs: torch.Tensor,
        returns: torch.Tensor,
        advantages: torch.Tensor,
        valid_action_counts: torch.Tensor,
    ) -> Tuple[float, float, float, float, float]:
        """
        PPO policy update with mini-batches.
        
        Returns:
            policy_loss, value_loss, entropy, clip_fraction, approx_kl
        """
        if len(states) == 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        dataset_size = len(states)
        batch_size = min(self.batch_size, dataset_size)
        
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_clip_fraction = 0.0
        total_approx_kl = 0.0
        n_updates = 0
        
        epochs = self.config['epochs']
        epsilon = self.config['epsilon']
        value_coef = self.config['value_coef']
        entropy_coef = self.config['entropy_coef']
        max_grad_norm = self.config['max_grad_norm']
        
        for epoch in range(epochs):
            indices = torch.randperm(dataset_size)
            
            for start in range(0, dataset_size, batch_size):
                end = min(start + batch_size, dataset_size)
                batch_indices = indices[start:end]
                
                batch_states = states[batch_indices]
                batch_actions = actions[batch_indices]
                batch_old_log_probs = old_log_probs[batch_indices]
                batch_returns = returns[batch_indices]
                batch_advantages = advantages[batch_indices]
                batch_valid_counts = valid_action_counts[batch_indices]
                
                # Forward pass
                logits, values = self.model(batch_states)

                # Mask invalid actions per sample to keep action/log-prob consistency.
                action_positions = torch.arange(logits.size(-1), device=logits.device).unsqueeze(0)
                invalid_mask = action_positions >= batch_valid_counts.unsqueeze(1)
                masked_logits = logits.masked_fill(invalid_mask, -1e9)

                probs = torch.softmax(masked_logits, dim=-1)
                dist = torch.distributions.Categorical(probs)
                
                max_action = logits.size(-1) - 1
                clamped_actions = torch.clamp(batch_actions, 0, max_action)
                
                log_probs = dist.log_prob(clamped_actions)
                entropy = dist.entropy().mean()
                
                # PPO ratio
                ratio = torch.exp(log_probs - batch_old_log_probs.detach())
                
                # Clipped surrogate
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - epsilon, 1 + epsilon) * batch_advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # Value loss
                value_loss = nn.functional.mse_loss(values.squeeze(-1), batch_returns)
                
                # Total loss
                loss = policy_loss + value_coef * value_loss - entropy_coef * entropy
                
                # Backward
                self.optimizer.zero_grad()
                
                if self.use_mixed_precision:
                    self.scaler.scale(loss).backward()
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=max_grad_norm)
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=max_grad_norm)
                    self.optimizer.step()
                
                # Statistics
                with torch.no_grad():
                    clip_fraction = (torch.abs(ratio - 1.0) > epsilon).float().mean().item()
                    approx_kl = (batch_old_log_probs - log_probs).mean().item()
                
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()
                total_clip_fraction += clip_fraction
                total_approx_kl += approx_kl
                n_updates += 1
        
        n_updates = max(n_updates, 1)
        return (
            total_policy_loss / n_updates,
            total_value_loss / n_updates,
            total_entropy / n_updates,
            total_clip_fraction / n_updates,
            total_approx_kl / n_updates,
        )
    
    def _apply_pending_updates(self):
        """Застосувати відкладені оновлення гіперпараметрів."""
        updates = self.checkpoint_manager.get_pending_updates()
        
        if updates:
            applied = self.checkpoint_manager.apply_hyperparameter_updates(
                self.optimizer,
                self.config,
                updates,
            )
            
            for param, update in applied.items():
                logger.info(f"✅ Застосовано {param}: {update.old_value} → {update.new_value}")
    
    def _save_checkpoint(
        self,
        iteration: int,
        current_reward: float,
        hard_violations: int,
        is_best: bool = False,
        description: str = "",
        tags: List[str] = None,
    ):
        """Зберегти checkpoint."""
        training_state = {
            "iteration": iteration,
            "best_reward": self.best_reward,
            "current_reward": current_reward,
            "hard_violations": hard_violations,
            "state_dim": self.state_dim,
            "action_dim": self.action_dim,
            **self.config,
        }
        
        scheduler_state = self.lr_scheduler.get_state() if self.lr_scheduler else None
        
        self.checkpoint_manager.save_checkpoint(
            self.model,
            self.optimizer,
            scheduler_state,
            training_state,
            tags=tags,
            description=description,
            is_best=is_best,
        )
    
    def _check_early_stopping(self) -> bool:
        """Перевірка умов для early stopping."""
        if self.no_improvement_count >= self.early_stop_patience:
            return True
        
        if (self.env._count_hard_violations() == 0 and 
            len(self.reward_history) >= 20):
            recent_rewards = list(self.reward_history)[-20:]
            std = np.std(recent_rewards)
            if std < 0.5:
                return True
        
        return False
    
    def generate_schedule(self) -> List[Tuple[int, int, int, int, int]]:
        """Генерація розкладу з навченою моделлю."""
        state = self.env.reset()
        schedule = []
        
        self.model.eval()
        with torch.no_grad():
            while True:
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                valid_actions = self.env.get_valid_actions()
                
                if not valid_actions:
                    break
                
                logits = self.model.actor(state_tensor)
                action_idx = logits.argmax().item()
                action = valid_actions[action_idx % len(valid_actions)]
                schedule.append(action)
                
                state, _, done, _ = self.env.step(action)
                
                if done:
                    break
        
        self.model.train()
        return schedule
    
    # === API Methods for Runtime Control ===
    
    def update_hyperparameter(self, parameter: str, value: float, reason: str = "") -> bool:
        """
        Оновити гіперпараметр під час навчання.
        
        Args:
            parameter: Ім'я параметра
            value: Нове значення
            reason: Причина зміни
            
        Returns:
            True якщо запит прийнято
        """
        return self.checkpoint_manager.request_hyperparameter_update(parameter, value, reason)
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Отримати поточні метрики."""
        return self.metrics_collector.get_current_metrics()
    
    def get_training_summary(self) -> Dict[str, Any]:
        """Отримати summary навчання."""
        return self.metrics_collector.get_training_summary()
    
    def get_plot_base64(self, plot_type: str = "dashboard") -> str:
        """Отримати графік як base64 для GUI."""
        if self.metrics_collector.current_session:
            return self.visualizer.get_plot_as_base64(
                self.metrics_collector.current_session,
                plot_type
            )
        return ""
    
    def get_chart_data(self) -> Dict[str, Any]:
        """Отримати дані для інтерактивних графіків."""
        if self.metrics_collector.current_session:
            return self.visualizer.get_chart_data_json(
                self.metrics_collector.current_session
            )
        return {}


# === Factory Function ===

def create_enhanced_trainer(
    courses,
    teachers,
    groups,
    classrooms,
    timeslots,
    num_iterations: int = 100,
    lr_scheduler_type: str = "combined",
    progress_callback=None,
    **kwargs
) -> EnhancedPPOTrainer:
    """
    Factory function для створення Enhanced PPO Trainer.
    
    Автоматично визначає оптимальні параметри на основі розміру задачі.
    """
    env = OptimizedTimetablingEnvironment(
        courses, teachers, groups, classrooms, timeslots
    )
    
    state_dim = env.state_dim
    action_dim = min(
        len(teachers) * len(groups) * len(classrooms) * len(timeslots),
        4096
    )
    
    # Auto-tune parameters
    batch_size = min(64, max(16, action_dim // 100))
    
    # Adaptive LR based on problem size
    base_lr = 3e-4
    if action_dim > 2000:
        base_lr = 1e-4  # Lower LR for larger problems
    
    trainer = EnhancedPPOTrainer(
        env=env,
        state_dim=state_dim,
        action_dim=action_dim,
        lr=base_lr,
        lr_scheduler_type=lr_scheduler_type,
        batch_size=batch_size,
        progress_callback=progress_callback,
        **kwargs
    )
    
    return trainer
