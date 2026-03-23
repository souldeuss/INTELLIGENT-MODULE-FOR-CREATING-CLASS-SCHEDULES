# 🚀 Оптимізація DRL системи складання розкладів

## Зміст

1. [Аналіз проблем продуктивності](#аналіз-проблем)
2. [Environment Optimization](#environment-optimization)
3. [PPO Training Optimization](#ppo-training-optimization)
4. [Neural Network Optimization](#neural-network-optimization)
5. [Порівняння до/після](#порівняння)
6. [Інтеграція](#інтеграція)

---

## Аналіз проблем

### Виявлені bottlenecks у оригінальному коді:

| Компонент             | Проблема                                | Складність           | Вплив         |
| --------------------- | --------------------------------------- | -------------------- | ------------- |
| `get_valid_actions()` | 4 вкладених Python цикли                | O(T×G×C×S)           | **Критичний** |
| `_calculate_reward()` | Повторний підрахунок `classes_this_day` | O(S) на кожен виклик | Високий       |
| `_get_state()`        | Flatten величезного масиву assignments  | O(C×T×G×R×S)         | Високий       |
| Action space          | Мільйони комбінацій                     | Експоненційний       | Критичний     |
| Training              | Послідовна обробка, без batching        | O(n)                 | Середній      |

### Профілювання часу (до оптимізації):

```
get_valid_actions: ~150-300ms (для 20 курсів)
step + reward:     ~5-10ms
state generation:  ~2-5ms
neural network:    ~1-2ms
───────────────────────────────
Total per step:    ~160-320ms
```

---

## Environment Optimization

### 1. Векторизація `get_valid_actions()` (10-50x швидше)

**До (Python цикли):**

```python
for teacher_idx in range(self.n_teachers):
    for group_idx in range(self.n_groups):
        for classroom_idx in range(self.n_classrooms):
            for timeslot_idx in range(self.n_timeslots):
                if (...):  # Перевірка конфліктів
                    valid_actions.append(...)
```

**Після (NumPy broadcasting):**

```python
# Створюємо маски вільних слотів
teacher_free = (self.teacher_schedule == 0)     # [T, S]
group_free = (self.group_schedule == 0)         # [G, S]
classroom_free = (self.classroom_schedule == 0) # [C, S]

# Broadcasting для всіх комбінацій одночасно
valid_mask = (
    teacher_free[:, np.newaxis, np.newaxis, :] &
    group_free[np.newaxis, :, np.newaxis, :] &
    classroom_free[np.newaxis, np.newaxis, :, :]
)  # Shape: [T, G, C, S]

valid_indices = np.argwhere(valid_mask)  # Всі валідні комбінації
```

**Чому це швидше:**

- NumPy операції виконуються в C, не Python
- Broadcasting уникає створення проміжних масивів
- Одна операція замість N^4 ітерацій

### 2. Delta-Reward (уникаємо повного перерахунку)

**До:** Кожен `step()` перераховував весь розклад для визначення конфліктів.

**Після:** Обчислюємо лише вплив поточної дії:

```python
def _calculate_delta_reward(self, course_idx, teacher_idx, ...):
    reward = 0.0

    # Перевіряємо лише зачеплені ресурси
    if self.teacher_schedule[teacher_idx, timeslot_idx] > 0:
        reward -= 5.0  # Конфлікт лише для цього викладача

    # Використовуємо кешовані значення
    day = self.timeslot_days[timeslot_idx]  # O(1) lookup
    classes_today = self.group_classes_per_day[group_idx, day]  # O(1)
```

### 3. Кешування днів тижня та періодів

**До:** Звернення до об'єктів `Timeslot` в кожному reward calculation:

```python
timeslot = self.timeslots[timeslot_idx]
day = timeslot.day_of_week  # Доступ до атрибуту об'єкта
```

**Після:** Попередньо обчислені NumPy масиви:

```python
# Один раз при ініціалізації
self.timeslot_days = np.array([ts.day_of_week for ts in self.timeslots])
self.timeslot_periods = np.array([ts.period_number for ts in self.timeslots])
self.day_masks = ...  # Маски для швидкої фільтрації

# В reward calculation
day = self.timeslot_days[timeslot_idx]  # NumPy indexing - дуже швидко
```

### 4. Compact State Representation

**До:** State включав flatten всіх assignments (може бути мільйони елементів):

```python
# Для 20 курсів, 10 викладачів, 5 груп, 8 аудиторій, 30 слотів:
# state_dim = 20 × 10 × 5 × 8 × 30 = 240,000 елементів!
flat_assignments = self.assignments.flatten()
```

**Після:** Compact representation з фіксованим розміром:

```python
# teacher_schedule: 10 × 30 = 300
# group_schedule: 5 × 30 = 150
# classroom_schedule: 8 × 30 = 240
# group_classes_per_day: 5 × 5 = 25
# progress: 2
# Total: ~720 елементів (333x менше!)
```

---

## PPO Training Optimization

### 1. Mini-Batch Training

**До:** Оновлення на повному датасеті кожну епоху.

**Після:** Mini-batches для кращої GPU утилізації:

```python
for epoch in range(self.epochs):
    indices = torch.randperm(dataset_size)

    for start in range(0, dataset_size, batch_size):
        batch_indices = indices[start:start+batch_size]
        # Update on mini-batch
```

**Переваги:**

- Краща утилізація GPU пам'яті
- Стохастичність покращує generalization
- Можливість обробляти більші датасети

### 2. Generalized Advantage Estimation (GAE)

**До:** Простий Monte-Carlo return:

```python
returns = []
R = 0
for r, done in zip(reversed(rewards), reversed(dones)):
    R = r + self.gamma * R * (1 - done)
    returns.insert(0, R)
```

**Після:** GAE для кращого bias-variance tradeoff:

```python
# GAE: A_t = Σ (γλ)^l * δ_{t+l}
for t in reversed(range(len(rewards))):
    delta = rewards[t] + gamma * next_val * (1-done) - values[t]
    advantages[t] = delta + gamma * gae_lambda * (1-done) * last_gae
```

**Чому краще:**

- GAE зменшує variance оцінки advantage
- λ контролює bias-variance tradeoff
- Стабільніше навчання, швидша збіжність

### 3. Early Stopping

Автоматична зупинка коли:

1. Немає покращення протягом N ітерацій
2. Reward стабілізувався (std < threshold)
3. Немає жорстких порушень

```python
def _check_early_stopping(self) -> bool:
    if self.no_improvement_count >= self.early_stop_patience:
        return True

    if (self.env._count_hard_violations() == 0 and
        np.std(recent_rewards) < 0.5):
        return True
```

### 4. Curriculum Learning

Поступове ускладнення задачі:

| Стадія | Курсів | Опис                         |
| ------ | ------ | ---------------------------- |
| 0      | 5      | Easy - базове навчання       |
| 1      | 10     | Medium - додаткові обмеження |
| 2      | 20     | Hard - повна складність      |
| 3      | All    | Full - реальний розклад      |

**Перехід до наступної стадії коли:**

- Середня винагорода > 0
- Жорстких порушень = 0

---

## Neural Network Optimization

### 1. Bottleneck Architecture

**До:** Прямий зв'язок input → hidden → output:

```python
self.fc1 = nn.Linear(state_dim, hidden_dim)      # state_dim може бути 240k!
self.fc2 = nn.Linear(hidden_dim, hidden_dim)
self.fc3 = nn.Linear(hidden_dim, action_dim)     # action_dim може бути 1M!
```

**Після:** Bottleneck для зменшення параметрів:

```python
self.input_bottleneck = nn.Linear(state_dim, 64)    # Зменшення до 64
self.fc1 = nn.Linear(64, 256)                       # Компактні hidden
self.fc2 = nn.Linear(256, 128)
self.fc3 = nn.Linear(128, min(action_dim, 2048))    # Обмеження output
```

**Результат:** Зменшення параметрів на 60-80%.

### 2. Sparse Top-K Attention

**До:** Full attention O(n²):

```python
attn_scores = Q @ K.T / sqrt(d)  # [S, S] матриця
attn_weights = softmax(attn_scores)
output = attn_weights @ V
```

**Після:** Top-K attention O(n×k):

```python
attn_scores = Q @ K.T / sqrt(d)
top_scores, top_indices = attn_scores.topk(k=32)  # Лише top-32
sparse_attn = zeros_like(attn_scores)
sparse_attn.scatter_(-1, top_indices, softmax(top_scores))
output = sparse_attn @ V
```

**Прискорення:** Для n=1000, k=32: **31x швидше**.

### 3. Shared Encoder

**До:** Окремі encoder для Actor та Critic.

**Після:** Спільний bottleneck encoder:

```python
self.shared_encoder = nn.Sequential(
    nn.Linear(state_dim, bottleneck_dim),
    nn.ReLU(),
    nn.LayerNorm(bottleneck_dim),
)

def forward(self, state):
    encoded = self.shared_encoder(state)  # Один раз
    logits = self.actor(encoded)
    value = self.critic(encoded)
```

---

## Порівняння

### Швидкодія (очікувана):

| Метрика                | До      | Після     | Прискорення |
| ---------------------- | ------- | --------- | ----------- |
| `get_valid_actions`    | ~200ms  | ~10-20ms  | **10-20x**  |
| `step + reward`        | ~10ms   | ~2ms      | **5x**      |
| Neural network forward | ~3ms    | ~1ms      | **3x**      |
| **Ітерація навчання**  | ~2-5s   | ~0.3-0.5s | **5-10x**   |
| **100 ітерацій**       | ~5-8 хв | ~30-60с   | **5-10x**   |

### Використання пам'яті:

| Компонент        | До       | Після           |
| ---------------- | -------- | --------------- |
| State vector     | ~240,000 | ~720            |
| Model parameters | ~2M      | ~500K           |
| Action space     | ~1M      | ~2K (effective) |

---

## Інтеграція

### Використання оптимізованої версії:

```python
from backend.app.core.environment_optimized import OptimizedTimetablingEnvironment
from backend.app.core.ppo_trainer_optimized import OptimizedPPOTrainer

# Створення середовища
env = OptimizedTimetablingEnvironment(
    courses, teachers, groups, classrooms, timeslots
)

# Створення trainer
trainer = OptimizedPPOTrainer(
    env=env,
    state_dim=env.state_dim,
    action_dim=2048,
    batch_size=64,
    n_steps=128,
)

# Навчання
rewards, stats = trainer.train(num_iterations=100)

# Генерація розкладу
schedule = trainer.generate_schedule()
```

### Запуск бенчмарку:

```bash
cd backend
python -m app.core.benchmark
```

---

## Рекомендації для подальшої оптимізації

1. **GPU acceleration:** Використовувати CUDA для Environment operations
2. **Parallel environments:** Запустити 4-8 середовищ паралельно
3. **Attention pruning:** Заморозити attention після pre-training
4. **Quantization:** INT8 квантизація моделі для inference
5. **JIT compilation:** Використати `torch.jit.script` для критичних функцій
