# Enhanced Training System Documentation

## Огляд

Цей документ описує вдосконалення системи навчання нейронної мережі для
автоматичного складання розкладу занять з використанням Deep Reinforcement Learning (PPO).

## Manifest Governance та Promotion Policy

Пайплайн `backend/train_eval_pipeline.py` працює через manifest (`data/dataset_manifest.sample.json`) і підтримує:

- `seed` для відтворюваності (random/numpy/torch)
- `train` / `test` hold-out split
- `sha256` перевірку датасетів перед запуском
- policy-gating для активації моделі (`--promote`):
    - `min_completion_rate`
    - `max_hard_violations`
    - `max_soft_violations`
    - `min_score_margin` (модель проти baseline)

Модель промотується в active лише якщо виконані всі критерії policy. У звіт `evaluation_report_*.json` записуються:

- фактичні hash датасетів
- середні метрики тесту
- score margin проти baseline
- детальний статус кожного критерію policy

## Структура модулів

```
backend/app/core/
├── lr_scheduler.py          # Dynamic Learning Rate Scheduling
├── training_metrics.py      # Metrics Collection & Analysis
├── training_visualizer.py   # Training Visualization
├── checkpoint_manager.py    # Persistent Learning & Checkpoints
├── enhanced_ppo_trainer.py  # Integrated PPO Trainer
└── ...

backend/app/api/
├── training.py              # REST API endpoints
└── ...
```

---

## 1. Dynamic Learning Rate Scheduling

### Обґрунтування підходу

Learning rate є критичним гіперпараметром для PPO:

- **Занадто високий LR**: нестабільне навчання, policy collapse
- **Занадто низький LR**: повільна конвергенція, застрягання в локальних мінімумах

**Рішення**: Динамічне планування LR з:

- Warmup фазою для стабільного старту
- Поступовим зменшенням для fine-tuning
- Адаптацією до прогресу навчання

### Реалізовані стратегії

#### 1.1 Linear Decay

```python
LR(t) = initial_lr - (initial_lr - min_lr) * (t / total_steps)
```

- **Переваги**: Простий, передбачуваний
- **Використання**: Фіксована кількість ітерацій

#### 1.2 Exponential Decay

```python
LR(t) = initial_lr * decay_rate^(t / decay_steps)
```

- **Переваги**: Швидке зменшення на початку
- **Використання**: Швидка конвергенція потрібна

#### 1.3 Cosine Annealing (РЕКОМЕНДОВАНО для PPO)

```python
LR(t) = min_lr + 0.5 * (initial_lr - min_lr) * (1 + cos(π * t / T))
```

- **Переваги**:
  - Плавне зменшення
  - Теплі рестарти допомагають виходити з локальних мінімумів
- **Використання**: Основна стратегія для policy gradient методів

#### 1.4 Reduce on Plateau

```python
if metric не покращується протягом patience кроків:
    LR = LR * factor
```

- **Переваги**: Адаптивність до прогресу
- **Використання**: Невідома оптимальна кількість ітерацій

#### 1.5 Combined (РЕКОМЕНДОВАНО для Production)

```
Warmup → Cosine Annealing → Plateau Detection
```

- Поєднує всі переваги
- Автоматична адаптація

### Приклад використання

```python
from backend.app.core.lr_scheduler import create_lr_scheduler

# Створення scheduler
scheduler = create_lr_scheduler(
    scheduler_type="combined",
    initial_lr=3e-4,
    total_steps=1000,
    warmup_ratio=0.1,
    min_lr=1e-6,
)

# В циклі навчання
for iteration in range(num_iterations):
    # ... training ...

    # Оновити LR
    current_lr = scheduler.step(metric=episode_reward)

    # Застосувати до optimizer
    for param_group in optimizer.param_groups:
        param_group['lr'] = current_lr
```

---

## 2. Persistent / Continual Learning

### Механізм запам'ятовування параметрів

Система зберігає повний стан навчання:

```python
checkpoint = {
    "model.pt":      # Ваги нейронної мережі
    "optimizer.pt":  # Стан optimizer (momentum, etc.)
    "scheduler.json": # Стан LR scheduler
    "metadata.json": # Метадані та гіперпараметри
}
```

### Сценарії використання

#### 2.1 Continue Training (повне відновлення)

```python
checkpoint_mgr = CheckpointManager()

# Завантажити останній checkpoint
result = checkpoint_mgr.load_latest(
    model, optimizer, device,
    filter_best=True  # або False для останнього
)

# Продовжити навчання
trainer.train(num_iterations=500)
```

#### 2.2 Fine-tuning (часткове відновлення)

```python
# Завантажити тільки ваги, скинути optimizer
result = checkpoint_mgr.load_checkpoint(
    checkpoint_id="best_ckpt_20241225_120000",
    model=model,
    optimizer=None,  # Не завантажувати optimizer
    load_optimizer=False,
)

# Створити новий optimizer з іншим LR
optimizer = Adam(model.parameters(), lr=1e-5)
```

#### 2.3 Transfer Learning

```python
# Завантажити модель, навчену на іншій задачі
checkpoint_mgr.load_checkpoint(
    checkpoint_id="pretrained_model",
    model=model,
    load_optimizer=False,
    apply_warmup=True,  # Warmup для стабільності
    warmup_steps=20,
)
```

### Автоматичне збереження

```python
trainer = EnhancedPPOTrainer(
    ...,
    auto_save_interval=50,  # Кожні 50 ітерацій
    keep_best_n=3,          # Зберігати 3 найкращі моделі
)
```

---

## 3. Контроль стабільності при зміні параметрів

### 3.1 Warmup після завантаження

При завантаженні checkpoint застосовується warmup:

```
LR: target * 0.1 → target (за warmup_steps кроків)
```

Це запобігає різким оновленням при відновленні навчання.

### 3.2 Обмеження різких змін LR

При runtime зміні гіперпараметрів:

```python
# Обмеження: max 50% зміни за раз
if abs(new_lr - old_lr) > old_lr * 0.5:
    new_lr = old_lr + sign(new_lr - old_lr) * old_lr * 0.5
```

### 3.3 Policy Divergence Detection

Система моніторить стабільність:

```python
stability = checkpoint_mgr.check_training_stability(
    recent_rewards=reward_history,
    recent_kl=kl_divergence_history,
    window=20
)

if not stability['stable']:
    # Автоматичне зменшення LR
    # Повідомлення в лог
    # Рекомендації
```

Критерії нестабільності:

- High reward variance (> 100)
- Increasing loss trend
- KL divergence > 0.02

---

## 4. Runtime Hyperparameter Control

### Зміна параметрів під час навчання

```python
# Через API
POST /api/training/hyperparameters
{
    "parameter": "learning_rate",
    "value": 1e-4,
    "reason": "Стагнація reward"
}

# Через trainer
trainer.update_hyperparameter("epsilon", 0.15, "Reduce exploration")
```

### Підтримувані параметри:

- `learning_rate` - Learning rate optimizer
- `gamma` - Discount factor
- `epsilon` - PPO clip range
- `gae_lambda` - GAE lambda
- `entropy_coef` - Entropy coefficient
- `value_coef` - Value loss coefficient

### Механізм застосування:

1. Запит додається в чергу
2. На наступній ітерації тренер перевіряє чергу
3. Застосовується з контролем стабільності
4. Записується в історію

---

## 5. API Endpoints

### Метрики

- `GET /api/training/metrics` - Поточні метрики
- `GET /api/training/metrics/history` - Історія метрик
- `GET /api/training/metrics/summary` - Summary навчання
- `GET /api/training/metrics/stability` - Аналіз стабільності

### Гіперпараметри

- `POST /api/training/hyperparameters` - Оновити параметр
- `GET /api/training/hyperparameters/history` - Історія змін

### Checkpoints

- `GET /api/training/checkpoints` - Список checkpoints
- `GET /api/training/checkpoints/{id}` - Деталі checkpoint
- `DELETE /api/training/checkpoints/{id}` - Видалити checkpoint

### Візуалізації

- `GET /api/training/visualizations/{type}` - Графік (base64 PNG)
- `GET /api/training/visualizations/chart-data` - Дані для Chart.js

### Статус

- `GET /api/training/status` - Загальний статус навчання

---

## 6. Візуалізація

### Автоматична генерація графіків

Після завершення навчання автоматично генеруються:

1. **losses.png** - Policy loss, Value loss, Entropy
2. **rewards.png** - Episode, Average, Best reward
3. **learning_rate.png** - LR schedule
4. **violations.png** - Hard/Soft violations
5. **stability.png** - Variance analysis
6. **dashboard.png** - Комплексний dashboard

### Формати виводу

- PNG (для GUI та швидкого перегляду)
- PDF (для документації)
- JSON (для інтерактивних графіків)

### Приклад отримання графіка для GUI

```python
# Backend
visualizer = TrainingVisualizer()
img_base64 = visualizer.get_plot_as_base64(session, "dashboard")

# Frontend
<img src={`data:image/png;base64,${img_base64}`} />
```

---

## 7. Приклад повного workflow

```python
from backend.app.core.enhanced_ppo_trainer import create_enhanced_trainer

# 1. Створити trainer
trainer = create_enhanced_trainer(
    courses=courses,
    teachers=teachers,
    groups=groups,
    classrooms=classrooms,
    timeslots=timeslots,
    num_iterations=1000,
    lr_scheduler_type="combined",
    progress_callback=lambda i, n: print(f"{i}/{n}"),
)

# 2. Навчання (автоматично використовує попередній checkpoint якщо є)
rewards, stats = trainer.train(num_iterations=1000)

# 3. Результати
print(f"Best reward: {stats['best_reward']}")
print(f"Final violations: {stats['final_hard_violations']}")

# 4. Генерація розкладу
schedule = trainer.generate_schedule()

# 5. Графіки вже збережені в ./backend/training_plots/
```

---

## 8. Рекомендації

### Для стабільного навчання:

1. Використовуйте `combined` LR scheduler
2. Починайте з warmup (10% ітерацій)
3. Не змінюйте гіперпараметри більш ніж на 50% за раз
4. Моніторьте KL divergence

### Для швидкої конвергенції:

1. Початковий LR: 3e-4 (для невеликих задач) або 1e-4 (для великих)
2. Batch size: 64 (GPU) або 32 (CPU)
3. N_steps: 128-256

### Для continual learning:

1. Зберігайте checkpoints кожні 50 ітерацій
2. Зберігайте 3-5 найкращих моделей
3. Використовуйте warmup при відновленні

---

## Версія

- Автор: AI Research Engineer
- Дата: 2024-12-25
- Версія: 2.0.0
