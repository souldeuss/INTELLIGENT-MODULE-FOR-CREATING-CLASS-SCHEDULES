# 📊 Візуалізація метрик навчання нейромережі

## Огляд

Додано повну систему моніторингу та візуалізації процесу навчання DRL-моделі для генерації розкладів. Тепер можна в реальному часі переглядати ефективність навчання нейромережі через зручний веб-інтерфейс.

## Оновлення протоколу train/eval/promote

Додатково до графіків, пайплайн `backend/train_eval_pipeline.py` формує `evaluation_report_*.json` з:

- `manifest_version`, `dataset_policy`, `seed`
- hash датасетів (`sha256`) для train/test наборів
- score margin моделі проти baseline
- перевіркою критеріїв `promotion_policy` (completion/hard/soft/margin)

Це дає відтворюваність та контроль якості перед активацією моделі (`--promote`).

## Основні компоненти

### 1. Backend API Endpoint

**Endpoint:** `GET /api/schedule/training-metrics`

**Розташування:** `backend/app/api/schedule.py`

**Функціонал:**

- Зчитує файл `backend/saved_models/training_metrics.json`
- Повертає повні метрики останнього навчання
- Обробляє помилки (файл не знайдено, помилка читання)

**Приклад відповіді:**

```json
{
  "timestamp": "2024-12-25T15:30:45",
  "iterations": 100,
  "metrics": {
    "rewards": [45.2, 67.8, 89.1, ...],
    "hard_violations": [15, 12, 8, ...],
    "soft_violations": [45, 38, 25, ...],
    "completion_rates": [0.65, 0.78, 0.92, ...],
    "actor_losses": [0.45, 0.38, 0.25, ...],
    "critic_losses": [1.23, 0.98, 0.67, ...]
  }
}
```

### 2. Збір метрик під час навчання

**Файл:** `backend/app/core/ppo_trainer_v2.py`

**Зміни в методі `train()`:**

```python
# Додані масиви для збереження історії
episode_rewards = []
hard_violations_history = []
soft_violations_history = []
completion_rates = []
actor_losses = []
critic_losses = []

# Збір метрик після кожної епохи
episode_rewards.append(episode_reward)
hard_violations_history.append(episode_hard_violations)
soft_violations_history.append(episode_soft_violations)
completion_rates.append(completion_rate)

# Збір втрат моделі
actor_loss, critic_loss = self._update_policy()
actor_losses.append(actor_loss)
critic_losses.append(critic_loss)
```

**Збереження в JSON:**

```python
import json
from datetime import datetime

final_stats["metrics"] = {
    "rewards": episode_rewards,
    "hard_violations": hard_violations_history,
    "soft_violations": soft_violations_history,
    "completion_rates": completion_rates,
    "actor_losses": actor_losses,
    "critic_losses": critic_losses
}

metrics_path = Path(__file__).parent.parent.parent / "saved_models" / "training_metrics.json"
with open(metrics_path, 'w', encoding='utf-8') as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "iterations": iterations,
        "metrics": final_stats["metrics"]
    }, f, indent=2)
```

**Модифікація `_update_policy()`:**

```python
def _update_policy(self) -> Tuple[float, float]:
    """
    Оновлює політику Actor-Critic та повертає втрати.

    Returns:
        Tuple[actor_loss, critic_loss]: Середні втрати за епоху
    """
    actor_loss_total = 0.0
    critic_loss_total = 0.0

    for _ in range(self.ppo_epochs):
        # ... логіка оновлення ...
        actor_loss_total += actor_loss.item()
        critic_loss_total += critic_loss.item()

    return (
        actor_loss_total / self.ppo_epochs,
        critic_loss_total / self.ppo_epochs
    )
```

### 3. Frontend компонент

**Файл:** `frontend/src/components/TrainingMetrics.tsx`

**Ключові особливості:**

#### Інформаційна панель (Summary)

Відображає:

- 📅 Дата та час останнього навчання
- 🔢 Кількість епох навчання
- 🎯 Фінальна винагорода (з кольоровим індикатором)
- ✅ Відсоток завершеності розкладу

#### Графік 1: Винагороди за епохами

- **Тип:** Стовпчаста діаграма (BarChart)
- **Дані:** `metrics.rewards[]`
- **Осі:**
  - X: Номер епохи
  - Y: Значення винагороди
- **Колір:** Синій (#8884d8)

#### Графік 2: Порушення обмежень

- **Тип:** Лінійна діаграма (LineChart)
- **Дані:**
  - Червона лінія: Жорсткі порушення (`hard_violations`)
  - Помаранчева лінія: М'які порушення (`soft_violations`)
- **Осі:**
  - X: Номер епохи
  - Y: Кількість порушень

#### Графік 3: Завершеність розкладу

- **Тип:** Лінійна діаграма
- **Дані:** `completion_rates[]` (у відсотках)
- **Колір:** Зелений (#4caf50)
- **Діапазон Y:** 0-100%

#### Графік 4: Втрати моделі

- **Тип:** Лінійна діаграма
- **Дані:**
  - Фіолетова лінія: Втрати Actor (`actor_losses`)
  - Синя лінія: Втрати Critic (`critic_losses`)

**Бібліотека візуалізації:** Recharts 2.10.3

### 4. Інтеграція в навігацію

**Файл:** `frontend/src/components/Navigation.tsx`

**Новий пункт меню:**

```typescript
{
  text: "Метрики навчання",
  icon: <TimelineIcon />,
  path: "/training-metrics",
  badge: null,
}
```

**Секція:** Аналітика (разом зі Статистикою та Збереженими розкладами)

**Маршрут:** `frontend/src/App.tsx`

```typescript
<Route path="/training-metrics" element={<TrainingMetrics />} />
```

## Як використовувати

### 1. Запустіть навчання моделі

```bash
# Через AI Generator у веб-інтерфейсі
# або через backend API
POST /api/schedule/generate
```

### 2. Перейдіть на сторінку метрик

- Відкрийте веб-інтерфейс
- У бічному меню виберіть **Аналітика → Метрики навчання**
- Або перейдіть безпосередньо: `http://localhost:3000/training-metrics`

### 3. Аналізуйте результати

**Що шукати:**

✅ **Хороші ознаки:**

- Винагорода зростає з епохами
- Порушення зменшуються
- Completion rate наближається до 100%
- Втрати (losses) стабілізуються або зменшуються

⚠️ **Проблемні ознаки:**

- Винагорода не зростає або падає
- Порушення залишаються високими
- Completion rate < 80% після багатьох епох
- Втрати зростають або сильно коливаються

## Технічні деталі

### Формат збережених даних

**Файл:** `backend/saved_models/training_metrics.json`

```json
{
  "timestamp": "ISO-8601 datetime string",
  "iterations": 100,
  "metrics": {
    "rewards": [float, ...],           // Винагорода за кожну епоху
    "hard_violations": [int, ...],     // Жорсткі порушення
    "soft_violations": [int, ...],     // М'які порушення
    "completion_rates": [float, ...],  // 0.0-1.0 (частка заповнених слотів)
    "actor_losses": [float, ...],      // Втрати actor мережі
    "critic_losses": [float, ...]      // Втрати critic мережі
  }
}
```

### Обробка помилок

**Backend:**

- 404: Файл метрик не знайдено (модель ще не навчалась)
- 500: Помилка читання файлу

**Frontend:**

- Loading state: Показує CircularProgress під час завантаження
- Error state: Відображає Alert з повідомленням про помилку
- Empty state: "No training metrics available"

## Розширення можливостей

### Майбутні покращення:

1. **Real-time streaming**

   - WebSocket з'єднання для live-оновлень під час навчання
   - Progress bar з поточною епохою

2. **Історія навчань**

   - Збереження метрик кількох тренувань
   - Порівняння різних запусків
   - Фільтрація за датою

3. **Додаткові метрики**

   - Learning rate schedule
   - Gradient norms
   - Policy entropy
   - Value function estimates

4. **Експорт даних**

   - Завантаження метрик у CSV/Excel
   - Експорт графіків у PNG/PDF

5. **Налаштування відображення**
   - Вибір типів графіків (лінія/стовпці)
   - Масштабування осей
   - Фільтрація діапазону епох

## Приклади інтерпретації

### Сценарій 1: Успішне навчання

```
Епохи: 1-100
Rewards: 10 → 85 (зростання)
Hard violations: 20 → 2 (зменшення)
Completion: 65% → 98% (зростання)
Losses: стабілізація після епохи 40
```

✅ **Висновок:** Модель навчилась ефективно. Можна використовувати для генерації.

### Сценарій 2: Проблеми зі збіжністю

```
Епохи: 1-100
Rewards: коливання -50 ↔ +30
Hard violations: 15-25 (без тренду)
Completion: 70-75% (плато)
Losses: зростають після епохи 60
```

⚠️ **Висновок:** Потрібно:

- Зменшити learning rate
- Збільшити розмір batch
- Перевірити архітектуру reward function

### Сценарій 3: Overfitting

```
Епохи: 1-150
Rewards: 20 → 95 (епохи 1-80), потім падіння
Losses: спочатку ↓, потім ↑ після епохи 80
```

⚠️ **Висновок:** Потрібно:

- Зупинити навчання раніше (early stopping)
- Додати regularization
- Використати checkpoint з епохи 80

## Файли проекту

### Backend

- `backend/app/api/schedule.py` - API endpoint
- `backend/app/core/ppo_trainer_v2.py` - Збір метрик
- `backend/saved_models/training_metrics.json` - Збережені дані

### Frontend

- `frontend/src/components/TrainingMetrics.tsx` - Компонент візуалізації
- `frontend/src/components/Navigation.tsx` - Меню навігації
- `frontend/src/App.tsx` - Маршрути додатку

## Залежності

**Backend:**

- `json` (standard library)
- `datetime` (standard library)
- `pathlib` (standard library)

**Frontend:**

- `recharts@^2.10.3` (вже встановлено)
- `@mui/material@^5.14.20`
- `@mui/icons-material@^5.14.19` (Timeline icon)
- `axios@^1.6.2`

## Запуск системи

```bash
# Terminal 1: Backend
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm start
```

Відкрийте: `http://localhost:3000/training-metrics`

---

**Автор:** DRL Scheduler Team  
**Дата оновлення:** 25.12.2024  
**Версія:** 2.1.0
