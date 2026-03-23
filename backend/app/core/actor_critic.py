"""Actor-Critic модель з Dual-Attention механізмом."""
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple


class DualAttentionModule(nn.Module):
    """Модуль подвійної уваги: часово-ресурсний + семантичний потік."""

    def __init__(self, input_dim: int, attention_dim: int = 128):
        super().__init__()
        self.temporal_attention = nn.MultiheadAttention(embed_dim=attention_dim, num_heads=4, batch_first=True)
        self.semantic_attention = nn.MultiheadAttention(embed_dim=attention_dim, num_heads=4, batch_first=True)

        self.temporal_projection = nn.Linear(input_dim, attention_dim)
        self.semantic_projection = nn.Linear(input_dim, attention_dim)
        self.fusion = nn.Linear(attention_dim * 2, attention_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [batch, seq_len, input_dim]"""
        # Часово-ресурсний потік
        temporal_input = self.temporal_projection(x)
        temporal_attn, _ = self.temporal_attention(temporal_input, temporal_input, temporal_input)

        # Семантичний потік
        semantic_input = self.semantic_projection(x)
        semantic_attn, _ = self.semantic_attention(semantic_input, semantic_input, semantic_input)

        # Об'єднання
        fused = torch.cat([temporal_attn, semantic_attn], dim=-1)
        output = self.fusion(fused)
        return output


class ActorNetwork(nn.Module):
    """Actor мережа (policy) з окремими виходами для кожного компонента."""

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256):
        super().__init__()
        # Використовуємо менші розмірності для швидкодії
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim //  2)
        
        # Замість одного величезного виходу, створюємо менший
        # Оскільки action_dim дуже великий, використовуємо bottleneck
        self.fc3 = nn.Linear(hidden_dim // 2, min(action_dim, 2048))  # Обмежуємо до 2048
        
        self.layer_norm1 = nn.LayerNorm(hidden_dim)
        self.layer_norm2 = nn.LayerNorm(hidden_dim // 2)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Повертає логіти для дій."""
        x = F.relu(self.layer_norm1(self.fc1(state)))
        x = F.relu(self.layer_norm2(self.fc2(x)))
        logits = self.fc3(x)
        return logits


class CriticNetwork(nn.Module):
    """Critic мережа (value function) спрощена."""

    def __init__(self, state_dim: int, hidden_dim: int = 256):
        super().__init__()
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc3 = nn.Linear(hidden_dim // 2, 1)

        self.layer_norm1 = nn.LayerNorm(hidden_dim)
        self.layer_norm2 = nn.LayerNorm(hidden_dim // 2)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Повертає оцінку значення стану."""
        x = F.relu(self.layer_norm1(self.fc1(state)))
        x = F.relu(self.layer_norm2(self.fc2(x)))
        value = self.fc3(x)
        return value


class ActorCritic(nn.Module):
    """Повна Actor-Critic модель."""

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256):
        super().__init__()
        self.actor = ActorNetwork(state_dim, action_dim, hidden_dim)
        self.critic = CriticNetwork(state_dim, hidden_dim)

    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Повертає (action_logits, state_value)."""
        logits = self.actor(state)
        value = self.critic(state)
        return logits, value

    def get_action(self, state: torch.Tensor, valid_actions_mask: torch.Tensor = None) -> Tuple[int, torch.Tensor]:
        """Семплює дію з policy."""
        logits, value = self.forward(state)

        # Маскування невалідних дій
        if valid_actions_mask is not None:
            logits = logits.masked_fill(valid_actions_mask == 0, float("-inf"))

        probs = F.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        log_prob = dist.log_prob(action)

        return action.item(), log_prob

    def evaluate_actions(
        self, states: torch.Tensor, actions: torch.Tensor, valid_actions_mask: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Оцінює дії для навчання."""
        logits, values = self.forward(states)

        if valid_actions_mask is not None:
            logits = logits.masked_fill(valid_actions_mask == 0, float("-inf"))

        probs = F.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)

        log_probs = dist.log_prob(actions)
        entropy = dist.entropy()

        return values.squeeze(-1), log_probs, entropy
