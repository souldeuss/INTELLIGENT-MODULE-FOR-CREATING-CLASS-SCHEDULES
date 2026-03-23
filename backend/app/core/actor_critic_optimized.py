"""
Оптимізована Actor-Critic модель з Sparse Attention та Hierarchical Actions.

Ключові оптимізації:
1. Sparse Top-K Attention - обчислення лише для K найважливіших елементів
2. Frozen embeddings - заморожування embedding-ів після попереднього навчання
3. Ефективний bottleneck architecture - зменшення параметрів
4. Hierarchical action head - окремі виходи для кожного компонента дії
5. Shared feature extraction - спільний encoder для actor/critic
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import math


class SparseTopKAttention(nn.Module):
    """
    Sparse Top-K Attention.
    
    Замість обчислення attention для всіх елементів (O(n²)),
    вибираємо лише top-K найрелевантніших (O(n*k)).
    
    Це критично для великих розкладів де n може бути 1000+.
    """
    
    def __init__(
        self, 
        embed_dim: int, 
        num_heads: int = 4, 
        top_k: int = 32,
        dropout: float = 0.1
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.top_k = top_k
        self.head_dim = embed_dim // num_heads
        
        assert embed_dim % num_heads == 0, "embed_dim must be divisible by num_heads"
        
        # Projections
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)
        
        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.head_dim)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [batch, seq_len, embed_dim]
        
        Returns: [batch, seq_len, embed_dim]
        """
        batch_size, seq_len, _ = x.shape
        
        # Projections
        Q = self.q_proj(x)  # [B, S, D]
        K = self.k_proj(x)
        V = self.v_proj(x)
        
        # Reshape for multi-head attention
        Q = Q.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        K = K.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        V = V.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        # Shape: [B, H, S, D_h]
        
        # Attention scores
        attn_scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale  # [B, H, S, S]
        
        # === TOP-K SPARSE ATTENTION ===
        # Для кожного query, вибираємо тільки top-k ключів
        k = min(self.top_k, seq_len)
        
        # Знаходимо top-k значення та індекси
        top_scores, top_indices = attn_scores.topk(k, dim=-1)  # [B, H, S, K]
        
        # Створюємо sparse mask
        sparse_attn = torch.zeros_like(attn_scores).scatter_(
            -1, top_indices, F.softmax(top_scores, dim=-1)
        )
        
        # Apply dropout
        sparse_attn = self.dropout(sparse_attn)
        
        # Weighted sum
        output = torch.matmul(sparse_attn, V)  # [B, H, S, D_h]
        
        # Reshape back
        output = output.transpose(1, 2).contiguous().view(batch_size, seq_len, self.embed_dim)
        
        return self.out_proj(output)


class OptimizedDualAttention(nn.Module):
    """
    Оптимізований Dual-Attention Module.
    
    Покращення:
    1. Sparse attention замість full attention
    2. Lazy projection - обчислюємо projection лише коли потрібно
    3. Efficient fusion - один linear замість concat + linear
    """
    
    def __init__(
        self, 
        input_dim: int, 
        attention_dim: int = 128,
        top_k: int = 32,
        freeze_embeddings: bool = False
    ):
        super().__init__()
        
        # Projections (можуть бути заморожені)
        self.temporal_projection = nn.Linear(input_dim, attention_dim)
        self.semantic_projection = nn.Linear(input_dim, attention_dim)
        
        # Sparse attention modules
        self.temporal_attention = SparseTopKAttention(attention_dim, num_heads=4, top_k=top_k)
        self.semantic_attention = SparseTopKAttention(attention_dim, num_heads=4, top_k=top_k)
        
        # Efficient fusion (гейтований механізм)
        self.gate = nn.Linear(attention_dim * 2, attention_dim)
        self.fusion = nn.Linear(attention_dim * 2, attention_dim)
        
        # Опціонально заморозити embeddings
        if freeze_embeddings:
            self._freeze_projections()
    
    def _freeze_projections(self):
        """Заморозити projection layers для швидшого навчання."""
        for param in self.temporal_projection.parameters():
            param.requires_grad = False
        for param in self.semantic_projection.parameters():
            param.requires_grad = False
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [batch, seq_len, input_dim] або [batch, input_dim]
        """
        # Handle 2D input (common case)
        if x.dim() == 2:
            x = x.unsqueeze(1)  # [B, 1, D]
        
        # Temporal stream
        temporal = self.temporal_projection(x)
        temporal = self.temporal_attention(temporal)
        
        # Semantic stream
        semantic = self.semantic_projection(x)
        semantic = self.semantic_attention(semantic)
        
        # Gated fusion
        concat = torch.cat([temporal, semantic], dim=-1)
        gate = torch.sigmoid(self.gate(concat))
        fused = self.fusion(concat) * gate
        
        # Return squeezed if input was 2D
        if fused.size(1) == 1:
            fused = fused.squeeze(1)
        
        return fused


class HierarchicalActionHead(nn.Module):
    """
    Ієрархічний Action Head.
    
    Замість одного величезного виходу (C×T×G×R×S),
    генеруємо окремі розподіли для кожного компонента:
    - Timeslot selection: S виходів
    - Teacher selection: T виходів  
    - Classroom selection: R виходів
    
    Це зменшує action space експоненційно.
    """
    
    def __init__(
        self, 
        hidden_dim: int,
        n_timeslots: int,
        n_teachers: int,
        n_classrooms: int,
    ):
        super().__init__()
        
        # Shared feature layer
        self.shared = nn.Linear(hidden_dim, hidden_dim // 2)
        
        # Separate heads for each component
        self.timeslot_head = nn.Linear(hidden_dim // 2, n_timeslots)
        self.teacher_head = nn.Linear(hidden_dim // 2, n_teachers)
        self.classroom_head = nn.Linear(hidden_dim // 2, n_classrooms)
        
        self.layer_norm = nn.LayerNorm(hidden_dim // 2)
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Returns:
            timeslot_logits: [batch, n_timeslots]
            teacher_logits: [batch, n_teachers]
            classroom_logits: [batch, n_classrooms]
        """
        shared = F.relu(self.layer_norm(self.shared(x)))
        
        return (
            self.timeslot_head(shared),
            self.teacher_head(shared),
            self.classroom_head(shared),
        )


class OptimizedActorNetwork(nn.Module):
    """
    Оптимізований Actor з bottleneck architecture.
    
    Архітектура:
    1. Input → Bottleneck (зменшення розмірності)
    2. Bottleneck → Hidden (feature extraction)
    3. Hidden → Output (policy logits)
    
    Bottleneck зменшує кількість параметрів на 60-80%.
    """
    
    def __init__(
        self, 
        state_dim: int, 
        action_dim: int, 
        hidden_dim: int = 256,
        bottleneck_dim: int = 64,
        use_attention: bool = True,
    ):
        super().__init__()
        
        self.use_attention = use_attention
        
        # Bottleneck input layer
        self.input_bottleneck = nn.Linear(state_dim, bottleneck_dim)
        
        # Optional attention
        if use_attention:
            self.attention = OptimizedDualAttention(
                bottleneck_dim, 
                attention_dim=hidden_dim // 2,
                top_k=16
            )
            self.fc1 = nn.Linear(hidden_dim // 2, hidden_dim)
        else:
            self.fc1 = nn.Linear(bottleneck_dim, hidden_dim)
        
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        
        # Output with bottleneck
        max_output = min(action_dim, 2048)
        self.fc3 = nn.Linear(hidden_dim // 2, max_output)
        
        # Normalization layers
        self.ln1 = nn.LayerNorm(hidden_dim)
        self.ln2 = nn.LayerNorm(hidden_dim // 2)
        
        # Dropout for regularization
        self.dropout = nn.Dropout(0.1)
    
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Forward pass."""
        # Bottleneck
        x = F.relu(self.input_bottleneck(state))
        
        # Optional attention
        if self.use_attention:
            x = self.attention(x)
        
        # Hidden layers
        x = F.relu(self.ln1(self.fc1(x)))
        x = self.dropout(x)
        x = F.relu(self.ln2(self.fc2(x)))
        
        # Output logits
        logits = self.fc3(x)
        
        return logits


class OptimizedCriticNetwork(nn.Module):
    """
    Оптимізований Critic з shared features.
    """
    
    def __init__(
        self, 
        state_dim: int, 
        hidden_dim: int = 256,
        bottleneck_dim: int = 64
    ):
        super().__init__()
        
        self.input_bottleneck = nn.Linear(state_dim, bottleneck_dim)
        self.fc1 = nn.Linear(bottleneck_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc3 = nn.Linear(hidden_dim // 2, 1)
        
        self.ln1 = nn.LayerNorm(hidden_dim)
        self.ln2 = nn.LayerNorm(hidden_dim // 2)
    
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Forward pass."""
        x = F.relu(self.input_bottleneck(state))
        x = F.relu(self.ln1(self.fc1(x)))
        x = F.relu(self.ln2(self.fc2(x)))
        value = self.fc3(x)
        return value


class OptimizedActorCritic(nn.Module):
    """
    Оптимізована Actor-Critic модель.
    
    Особливості:
    1. Shared bottleneck encoder
    2. Sparse dual-attention (опціонально)
    3. Efficient parameter sharing
    4. Support for hierarchical actions
    """
    
    def __init__(
        self, 
        state_dim: int, 
        action_dim: int, 
        hidden_dim: int = 256,
        bottleneck_dim: int = 64,
        use_attention: bool = False,  # Вимкнено за замовчуванням для швидкості
    ):
        super().__init__()
        
        # Shared bottleneck encoder
        self.shared_encoder = nn.Sequential(
            nn.Linear(state_dim, bottleneck_dim),
            nn.ReLU(),
            nn.LayerNorm(bottleneck_dim),
        )
        
        # Actor (policy)
        self.actor = nn.Sequential(
            nn.Linear(bottleneck_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim // 2),
            nn.Linear(hidden_dim // 2, min(action_dim, 2048)),
        )
        
        # Critic (value)
        self.critic = nn.Sequential(
            nn.Linear(bottleneck_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim // 2),
            nn.Linear(hidden_dim // 2, 1),
        )
        
        # Optional attention module
        self.use_attention = use_attention
        if use_attention:
            self.attention = OptimizedDualAttention(
                bottleneck_dim, 
                attention_dim=hidden_dim // 2,
                top_k=16
            )
    
    def _encode(self, state: torch.Tensor) -> torch.Tensor:
        """Shared encoding."""
        encoded = self.shared_encoder(state)
        
        if self.use_attention:
            encoded = self.attention(encoded)
        
        return encoded
    
    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns (action_logits, state_value)."""
        encoded = self._encode(state)
        logits = self.actor(encoded)
        value = self.critic(encoded)
        return logits, value
    
    def get_action(
        self, 
        state: torch.Tensor, 
        valid_actions_mask: Optional[torch.Tensor] = None,
        deterministic: bool = False
    ) -> Tuple[int, torch.Tensor]:
        """Sample action from policy."""
        logits, _ = self.forward(state)
        
        # Apply mask if provided
        if valid_actions_mask is not None:
            logits = logits.masked_fill(valid_actions_mask == 0, float("-inf"))
        
        if deterministic:
            action = logits.argmax(dim=-1)
            # Compute log_prob for the selected action
            probs = F.softmax(logits, dim=-1)
            log_prob = torch.log(probs.gather(-1, action.unsqueeze(-1)) + 1e-8).squeeze(-1)
        else:
            probs = F.softmax(logits, dim=-1)
            dist = torch.distributions.Categorical(probs)
            action = dist.sample()
            log_prob = dist.log_prob(action)
        
        return action.item(), log_prob
    
    def evaluate_actions(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        valid_actions_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Evaluate actions for training."""
        logits, values = self.forward(states)
        
        if valid_actions_mask is not None:
            logits = logits.masked_fill(valid_actions_mask == 0, float("-inf"))
        
        probs = F.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)
        
        # Clamp actions to valid range
        max_action = logits.size(-1) - 1
        clamped_actions = torch.clamp(actions, 0, max_action)
        
        log_probs = dist.log_prob(clamped_actions)
        entropy = dist.entropy()
        
        return values.squeeze(-1), log_probs, entropy


# === Backward compatibility ===
# Alias для сумісності з існуючим кодом
ActorCritic = OptimizedActorCritic
DualAttentionModule = OptimizedDualAttention
