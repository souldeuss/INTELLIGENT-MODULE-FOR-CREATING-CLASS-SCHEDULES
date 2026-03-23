"""
Модуль візуалізації результатів навчання.

Генерує графіки:
1. Loss vs Iteration (policy, value, total)
2. Reward vs Iteration (episode, average, best)
3. Learning Rate vs Iteration
4. Stability Analysis (variance, KL divergence)
5. Comprehensive Training Dashboard

Формати виводу:
- PNG (для GUI та звітів)
- PDF (для документації)
- JSON (дані для інтерактивних графіків)

Автор: AI Research Engineer
Дата: 2024-12-25
"""
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import logging
import io
import base64

# Matplotlib з backend для headless rendering
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.figure import Figure

from .training_metrics import TrainingSession, TrainingMetricsCollector, get_metrics_collector

logger = logging.getLogger(__name__)

# Стилі для графіків
PLOT_STYLE = {
    'figure.facecolor': '#1e1e1e',
    'axes.facecolor': '#252526',
    'axes.edgecolor': '#3c3c3c',
    'axes.labelcolor': '#cccccc',
    'axes.titlecolor': '#ffffff',
    'xtick.color': '#cccccc',
    'ytick.color': '#cccccc',
    'text.color': '#cccccc',
    'grid.color': '#3c3c3c',
    'legend.facecolor': '#252526',
    'legend.edgecolor': '#3c3c3c',
}

# Кольори для ліній
COLORS = {
    'policy_loss': '#ff6b6b',
    'value_loss': '#4ecdc4',
    'total_loss': '#ffe66d',
    'episode_reward': '#95e1d3',
    'average_reward': '#f38181',
    'best_reward': '#aa96da',
    'learning_rate': '#fcbad3',
    'entropy': '#a8d8ea',
    'hard_violations': '#ff6b6b',
    'soft_violations': '#ffd93d',
}


class TrainingVisualizer:
    """
    Візуалізатор результатів навчання.
    
    Підтримує:
    - Статичні графіки (PNG, PDF)
    - Дані для інтерактивних графіків (JSON)
    - Real-time оновлення (для GUI)
    """
    
    def __init__(
        self,
        output_dir: Path = None,
        style: str = "dark",  # dark, light
        dpi: int = 150,
    ):
        """
        Args:
            output_dir: Директорія для збереження графіків
            style: Стиль графіків (dark для GUI, light для друку)
            dpi: DPI для растрових зображень
        """
        self.output_dir = output_dir or Path("./backend/training_plots")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.style = style
        self.dpi = dpi
        
        # Apply style
        if style == "dark":
            plt.rcParams.update(PLOT_STYLE)
        else:
            plt.style.use('seaborn-v0_8-whitegrid')
    
    def plot_losses(
        self,
        session: TrainingSession,
        save_path: Path = None,
        show_legend: bool = True,
    ) -> Figure:
        """
        Графік losses: policy loss, value loss, entropy.
        
        Args:
            session: Сесія навчання з метриками
            save_path: Шлях для збереження (опціонально)
            
        Returns:
            matplotlib Figure
        """
        if not session.steps:
            return self._empty_figure("No training data")
        
        iterations = [s.iteration for s in session.steps]
        policy_losses = [s.policy_loss for s in session.steps]
        value_losses = [s.value_loss for s in session.steps]
        entropies = [s.entropy for s in session.steps]
        
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        
        # Policy & Value Loss
        ax1 = axes[0]
        ax1.plot(iterations, policy_losses, color=COLORS['policy_loss'], 
                 label='Policy Loss', linewidth=1.5, alpha=0.8)
        ax1.plot(iterations, value_losses, color=COLORS['value_loss'], 
                 label='Value Loss', linewidth=1.5, alpha=0.8)
        
        # Add smoothed lines
        if len(iterations) > 10:
            smoothed_policy = self._smooth(policy_losses, window=10)
            smoothed_value = self._smooth(value_losses, window=10)
            ax1.plot(iterations, smoothed_policy, color=COLORS['policy_loss'], 
                     linewidth=2.5, linestyle='--', alpha=0.9)
            ax1.plot(iterations, smoothed_value, color=COLORS['value_loss'], 
                     linewidth=2.5, linestyle='--', alpha=0.9)
        
        ax1.set_ylabel('Loss', fontsize=12)
        ax1.set_title('Training Losses', fontsize=14, fontweight='bold')
        if show_legend:
            ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)
        
        # Entropy
        ax2 = axes[1]
        ax2.plot(iterations, entropies, color=COLORS['entropy'], 
                 label='Entropy', linewidth=1.5, alpha=0.8)
        ax2.fill_between(iterations, 0, entropies, color=COLORS['entropy'], alpha=0.2)
        ax2.set_xlabel('Iteration', fontsize=12)
        ax2.set_ylabel('Entropy', fontsize=12)
        ax2.set_title('Policy Entropy (Exploration)', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"📊 Графік losses збережено: {save_path}")
        
        return fig
    
    def plot_rewards(
        self,
        session: TrainingSession,
        save_path: Path = None,
    ) -> Figure:
        """
        Графік rewards: episode, average, best.
        """
        if not session.steps:
            return self._empty_figure("No training data")
        
        iterations = [s.iteration for s in session.steps]
        episode_rewards = [s.episode_reward for s in session.steps]
        avg_rewards = [s.average_reward for s in session.steps]
        best_rewards = [s.best_reward for s in session.steps]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Episode reward (scatter for variance visibility)
        ax.scatter(iterations, episode_rewards, color=COLORS['episode_reward'], 
                   alpha=0.4, s=10, label='Episode Reward')
        
        # Average reward (line)
        ax.plot(iterations, avg_rewards, color=COLORS['average_reward'], 
                linewidth=2.5, label='Average Reward (100 ep)')
        
        # Best reward (line)
        ax.plot(iterations, best_rewards, color=COLORS['best_reward'], 
                linewidth=2, linestyle='--', label='Best Reward')
        
        # Highlight best point
        best_idx = np.argmax(best_rewards)
        ax.scatter([iterations[best_idx]], [best_rewards[best_idx]], 
                   color=COLORS['best_reward'], s=100, marker='*', 
                   zorder=5, edgecolors='white', linewidth=1.5)
        
        ax.set_xlabel('Iteration', fontsize=12)
        ax.set_ylabel('Reward', fontsize=12)
        ax.set_title('Training Rewards', fontsize=14, fontweight='bold')
        ax.legend(loc='lower right')
        ax.grid(True, alpha=0.3)
        
        # Add annotation for best
        ax.annotate(
            f'Best: {best_rewards[best_idx]:.1f}',
            xy=(iterations[best_idx], best_rewards[best_idx]),
            xytext=(10, 10), textcoords='offset points',
            fontsize=10, color=COLORS['best_reward'],
            arrowprops=dict(arrowstyle='->', color=COLORS['best_reward'], alpha=0.5)
        )
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"📊 Графік rewards збережено: {save_path}")
        
        return fig
    
    def plot_learning_rate(
        self,
        session: TrainingSession,
        save_path: Path = None,
    ) -> Figure:
        """
        Графік learning rate vs iteration.
        """
        if not session.steps:
            return self._empty_figure("No training data")
        
        iterations = [s.iteration for s in session.steps]
        lrs = [s.learning_rate for s in session.steps]
        
        fig, ax = plt.subplots(figsize=(12, 4))
        
        ax.plot(iterations, lrs, color=COLORS['learning_rate'], linewidth=2)
        ax.fill_between(iterations, 0, lrs, color=COLORS['learning_rate'], alpha=0.2)
        
        ax.set_xlabel('Iteration', fontsize=12)
        ax.set_ylabel('Learning Rate', fontsize=12)
        ax.set_title('Learning Rate Schedule', fontsize=14, fontweight='bold')
        ax.set_yscale('log')  # Log scale for better visibility
        ax.grid(True, alpha=0.3)
        
        # Add annotations for key points
        if len(lrs) > 1:
            ax.annotate(f'Start: {lrs[0]:.2e}', xy=(iterations[0], lrs[0]),
                       xytext=(5, 5), textcoords='offset points', fontsize=9)
            ax.annotate(f'End: {lrs[-1]:.2e}', xy=(iterations[-1], lrs[-1]),
                       xytext=(-50, 5), textcoords='offset points', fontsize=9)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"📊 Графік LR збережено: {save_path}")
        
        return fig
    
    def plot_violations(
        self,
        session: TrainingSession,
        save_path: Path = None,
    ) -> Figure:
        """
        Графік порушень: hard violations, soft violations.
        """
        if not session.steps:
            return self._empty_figure("No training data")
        
        iterations = [s.iteration for s in session.steps]
        hard = [s.hard_violations for s in session.steps]
        soft = [s.soft_violations for s in session.steps]
        
        fig, ax = plt.subplots(figsize=(12, 5))
        
        ax.fill_between(iterations, 0, hard, color=COLORS['hard_violations'], 
                        alpha=0.7, label='Hard Violations')
        ax.fill_between(iterations, hard, [h+s for h,s in zip(hard, soft)], 
                        color=COLORS['soft_violations'], alpha=0.5, label='Soft Violations')
        
        ax.set_xlabel('Iteration', fontsize=12)
        ax.set_ylabel('Violations', fontsize=12)
        ax.set_title('Constraint Violations', fontsize=14, fontweight='bold')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"📊 Графік violations збережено: {save_path}")
        
        return fig
    
    def plot_stability(
        self,
        session: TrainingSession,
        window_size: int = 20,
        save_path: Path = None,
    ) -> Figure:
        """
        Графік стабільності: variance, KL divergence.
        """
        if not session.steps or len(session.steps) < window_size:
            return self._empty_figure("Insufficient data for stability analysis")
        
        # Calculate rolling variance
        rewards = [s.episode_reward for s in session.steps]
        variances = []
        for i in range(len(rewards)):
            if i < window_size:
                variances.append(np.var(rewards[:i+1]) if i > 0 else 0)
            else:
                variances.append(np.var(rewards[i-window_size+1:i+1]))
        
        iterations = [s.iteration for s in session.steps]
        
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        
        # Reward Variance
        ax1 = axes[0]
        ax1.plot(iterations, variances, color='#ff6b6b', linewidth=1.5)
        ax1.fill_between(iterations, 0, variances, color='#ff6b6b', alpha=0.2)
        ax1.set_ylabel('Reward Variance', fontsize=12)
        ax1.set_title(f'Training Stability (window={window_size})', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Add stability threshold line
        median_var = np.median(variances)
        ax1.axhline(y=median_var, color='white', linestyle='--', alpha=0.5, 
                    label=f'Median: {median_var:.1f}')
        ax1.legend()
        
        # Loss trend (optional: if we have gradient norms)
        ax2 = axes[1]
        if session.steps[0].loss_variance is not None:
            loss_vars = [s.loss_variance for s in session.steps]
            ax2.plot(iterations, loss_vars, color='#4ecdc4', linewidth=1.5)
            ax2.fill_between(iterations, 0, loss_vars, color='#4ecdc4', alpha=0.2)
            ax2.set_ylabel('Loss Variance', fontsize=12)
        else:
            # Plot episode rewards as fallback
            ax2.plot(iterations, rewards, color='#95e1d3', linewidth=1.5, alpha=0.5)
            ax2.set_ylabel('Episode Reward', fontsize=12)
        
        ax2.set_xlabel('Iteration', fontsize=12)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"📊 Графік stability збережено: {save_path}")
        
        return fig
    
    def plot_comprehensive_dashboard(
        self,
        session: TrainingSession,
        save_path: Path = None,
    ) -> Figure:
        """
        Комплексний dashboard з усіма метриками.
        
        Включає:
        - Losses
        - Rewards
        - Learning Rate
        - Violations
        - Summary statistics
        """
        if not session.steps:
            return self._empty_figure("No training data")
        
        fig = plt.figure(figsize=(16, 12))
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)
        
        iterations = [s.iteration for s in session.steps]
        
        # === Row 1: Losses ===
        ax_loss = fig.add_subplot(gs[0, :2])
        policy_losses = [s.policy_loss for s in session.steps]
        value_losses = [s.value_loss for s in session.steps]
        ax_loss.plot(iterations, policy_losses, color=COLORS['policy_loss'], 
                     label='Policy Loss', linewidth=1.5, alpha=0.8)
        ax_loss.plot(iterations, value_losses, color=COLORS['value_loss'], 
                     label='Value Loss', linewidth=1.5, alpha=0.8)
        ax_loss.set_title('Training Losses', fontsize=12, fontweight='bold')
        ax_loss.legend(loc='upper right', fontsize=8)
        ax_loss.grid(True, alpha=0.3)
        
        # Summary Box
        ax_summary = fig.add_subplot(gs[0, 2])
        ax_summary.axis('off')
        summary_text = self._create_summary_text(session)
        ax_summary.text(0.1, 0.9, summary_text, transform=ax_summary.transAxes,
                       fontsize=10, verticalalignment='top', fontfamily='monospace',
                       bbox=dict(boxstyle='round', facecolor='#252526', edgecolor='#3c3c3c'))
        
        # === Row 2: Rewards ===
        ax_reward = fig.add_subplot(gs[1, :2])
        episode_rewards = [s.episode_reward for s in session.steps]
        avg_rewards = [s.average_reward for s in session.steps]
        ax_reward.scatter(iterations, episode_rewards, color=COLORS['episode_reward'], 
                         alpha=0.3, s=8)
        ax_reward.plot(iterations, avg_rewards, color=COLORS['average_reward'], 
                       linewidth=2.5, label='Average Reward')
        ax_reward.set_title('Rewards', fontsize=12, fontweight='bold')
        ax_reward.legend(loc='lower right', fontsize=8)
        ax_reward.grid(True, alpha=0.3)
        
        # Learning Rate
        ax_lr = fig.add_subplot(gs[1, 2])
        lrs = [s.learning_rate for s in session.steps]
        ax_lr.plot(iterations, lrs, color=COLORS['learning_rate'], linewidth=2)
        ax_lr.set_title('Learning Rate', fontsize=12, fontweight='bold')
        ax_lr.set_yscale('log')
        ax_lr.grid(True, alpha=0.3)
        
        # === Row 3: Violations & Entropy ===
        ax_viol = fig.add_subplot(gs[2, :2])
        hard = [s.hard_violations for s in session.steps]
        ax_viol.fill_between(iterations, 0, hard, color=COLORS['hard_violations'], 
                             alpha=0.7, label='Hard Violations')
        ax_viol.set_title('Constraint Violations', fontsize=12, fontweight='bold')
        ax_viol.legend(fontsize=8)
        ax_viol.set_xlabel('Iteration')
        ax_viol.grid(True, alpha=0.3)
        
        # Entropy
        ax_ent = fig.add_subplot(gs[2, 2])
        entropies = [s.entropy for s in session.steps]
        ax_ent.plot(iterations, entropies, color=COLORS['entropy'], linewidth=1.5)
        ax_ent.fill_between(iterations, 0, entropies, color=COLORS['entropy'], alpha=0.2)
        ax_ent.set_title('Policy Entropy', fontsize=12, fontweight='bold')
        ax_ent.set_xlabel('Iteration')
        ax_ent.grid(True, alpha=0.3)
        
        # Main title
        fig.suptitle(f'Training Dashboard - Session {session.session_id}', 
                     fontsize=14, fontweight='bold', y=0.98)
        
        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"📊 Dashboard збережено: {save_path}")
        
        return fig
    
    def generate_all_plots(
        self,
        session: TrainingSession,
        formats: List[str] = ["png"],
        prefix: str = None,
    ) -> Dict[str, Path]:
        """
        Згенерувати всі графіки.
        
        Args:
            session: Сесія навчання
            formats: Формати виводу ("png", "pdf")
            prefix: Префікс для файлів
            
        Returns:
            Dict {plot_name: file_path}
        """
        if prefix is None:
            prefix = f"training_{session.session_id}"
        
        saved_files = {}
        
        plots = [
            ("losses", self.plot_losses),
            ("rewards", self.plot_rewards),
            ("learning_rate", self.plot_learning_rate),
            ("violations", self.plot_violations),
            ("stability", self.plot_stability),
            ("dashboard", self.plot_comprehensive_dashboard),
        ]
        
        for plot_name, plot_func in plots:
            for fmt in formats:
                filename = f"{prefix}_{plot_name}.{fmt}"
                save_path = self.output_dir / filename
                
                try:
                    fig = plot_func(session, save_path=save_path)
                    plt.close(fig)
                    saved_files[f"{plot_name}_{fmt}"] = save_path
                except Exception as e:
                    logger.error(f"Error creating {plot_name}: {e}")
        
        logger.info(f"📊 Згенеровано {len(saved_files)} графіків")
        return saved_files
    
    def get_plot_as_base64(
        self,
        session: TrainingSession,
        plot_type: str = "dashboard",
    ) -> str:
        """
        Отримати графік як base64 string для GUI.
        
        Args:
            session: Сесія навчання
            plot_type: Тип графіка
            
        Returns:
            Base64 encoded PNG string
        """
        plot_funcs = {
            "losses": self.plot_losses,
            "rewards": self.plot_rewards,
            "learning_rate": self.plot_learning_rate,
            "violations": self.plot_violations,
            "stability": self.plot_stability,
            "dashboard": self.plot_comprehensive_dashboard,
        }
        
        if plot_type not in plot_funcs:
            raise ValueError(f"Unknown plot type: {plot_type}")
        
        fig = plot_funcs[plot_type](session)
        
        # Save to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        
        # Encode to base64
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return img_base64
    
    def get_chart_data_json(
        self,
        session: TrainingSession,
    ) -> Dict[str, Any]:
        """
        Отримати дані для інтерактивних графіків (Chart.js, Plotly).
        
        Returns:
            Dict з даними для побудови графіків на frontend
        """
        if not session.steps:
            return {"error": "No data"}
        
        steps = session.steps
        
        return {
            "labels": [s.iteration for s in steps],
            "datasets": {
                "policy_loss": {
                    "label": "Policy Loss",
                    "data": [s.policy_loss for s in steps],
                    "color": COLORS['policy_loss'],
                },
                "value_loss": {
                    "label": "Value Loss",
                    "data": [s.value_loss for s in steps],
                    "color": COLORS['value_loss'],
                },
                "entropy": {
                    "label": "Entropy",
                    "data": [s.entropy for s in steps],
                    "color": COLORS['entropy'],
                },
                "episode_reward": {
                    "label": "Episode Reward",
                    "data": [s.episode_reward for s in steps],
                    "color": COLORS['episode_reward'],
                },
                "average_reward": {
                    "label": "Average Reward",
                    "data": [s.average_reward for s in steps],
                    "color": COLORS['average_reward'],
                },
                "learning_rate": {
                    "label": "Learning Rate",
                    "data": [s.learning_rate for s in steps],
                    "color": COLORS['learning_rate'],
                },
                "hard_violations": {
                    "label": "Hard Violations",
                    "data": [s.hard_violations for s in steps],
                    "color": COLORS['hard_violations'],
                },
            },
            "summary": {
                "total_iterations": len(steps),
                "best_reward": max(s.episode_reward for s in steps),
                "final_reward": steps[-1].episode_reward,
                "final_hard_violations": steps[-1].hard_violations,
            }
        }
    
    def _smooth(self, data: List[float], window: int = 10) -> List[float]:
        """Згладжування даних за допомогою moving average."""
        smoothed = []
        for i in range(len(data)):
            start = max(0, i - window + 1)
            smoothed.append(np.mean(data[start:i+1]))
        return smoothed
    
    def _empty_figure(self, message: str) -> Figure:
        """Створити порожній figure з повідомленням."""
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, message, ha='center', va='center', fontsize=14)
        ax.axis('off')
        return fig
    
    def _create_summary_text(self, session: TrainingSession) -> str:
        """Створити текст summary для dashboard."""
        if not session.steps:
            return "No data"
        
        steps = session.steps
        rewards = [s.episode_reward for s in steps]
        
        text = f"""Training Summary
═══════════════════════
Session: {session.session_id}
Status:  {session.status}
Iters:   {len(steps)}

Reward
──────────────────────
Best:    {max(rewards):.2f}
Final:   {rewards[-1]:.2f}
Mean:    {np.mean(rewards):.2f}

Learning Rate
──────────────────────
Start:   {steps[0].learning_rate:.2e}
End:     {steps[-1].learning_rate:.2e}

Violations
──────────────────────
Initial: {steps[0].hard_violations}
Final:   {steps[-1].hard_violations}
"""
        return text


# === Helper functions ===

def visualize_current_training(
    output_dir: Path = None,
    formats: List[str] = ["png"],
) -> Dict[str, Path]:
    """
    Візуалізувати поточну сесію навчання.
    
    Returns:
        Dict з шляхами до збережених файлів
    """
    collector = get_metrics_collector()
    
    if collector.current_session is None:
        logger.warning("No active training session")
        return {}
    
    visualizer = TrainingVisualizer(output_dir=output_dir)
    return visualizer.generate_all_plots(
        collector.current_session,
        formats=formats,
    )


def visualize_from_file(
    metrics_file: Path,
    output_dir: Path = None,
    formats: List[str] = ["png"],
) -> Dict[str, Path]:
    """
    Візуалізувати сесію з файлу метрик.
    """
    collector = TrainingMetricsCollector()
    session = collector.load_from_file(metrics_file)
    
    visualizer = TrainingVisualizer(output_dir=output_dir)
    return visualizer.generate_all_plots(session, formats=formats)
