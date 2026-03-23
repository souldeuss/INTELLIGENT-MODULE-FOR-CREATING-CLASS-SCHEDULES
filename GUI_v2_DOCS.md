# 🎨 GUI v2.0 - Інтелектуальна Система Розкладу

## 🆕 Що нового в версії 2.0

Повністю переробленний графічний інтерфейс для системи автоматичного складання розкладу занять на основі Deep Reinforcement Learning (DRL).

### Основні покращення:

- 🎯 **Модульна архітектура** - розділення на незалежні компоненти
- 🤖 **AI Control Panel** - повний контроль над PPO параметрами
- ⚠️ **Conflict Center** - real-time виявлення конфліктів
- 📅 **Interactive Timetable** - drag & drop редагування
- 📊 **Modern Dashboard** - AI метрики та візуалізація

---

## 🏗️ Архітектура

### Структура компонентів

```
frontend/src/
├── components/
│   ├── ModernDashboard.tsx      # 📊 Головна панель з AI метриками
│   ├── InteractiveTimetable.tsx # 📅 Інтерактивний розклад
│   ├── AIControlPanel.tsx       # 🤖 Панель керування AI
│   ├── ConflictCenter.tsx       # ⚠️ Центр конфліктів
│   ├── Navigation.tsx           # 🧭 Навігація
│   ├── Analytics.tsx            # 📈 Аналітика
│   └── [управління даними...]
├── services/
│   └── api.ts                   # 🔌 Розширений API
└── App.tsx                      # 🏠 Головний компонент
```

---

## 🎯 Компоненти

### 1. ModernDashboard 📊

**Файл:** `components/ModernDashboard.tsx`

Головна панель з віджетами:

| Віджет               | Опис                                              |
| -------------------- | ------------------------------------------------- |
| **Stat Cards**       | Кількість груп, викладачів, аудиторій, конфліктів |
| **AI Score Card**    | Візуалізація оцінки розкладу з прогрес-барами     |
| **Training Chart**   | Графік reward по епізодах (AreaChart)             |
| **Quick Actions**    | Швидкий доступ: генерація, перегляд, оновлення    |
| **Recent Schedules** | Список останніх збережених розкладів              |
| **Compact AI Panel** | Міні-версія AI Control Panel                      |

```typescript
// Приклад використання
<ModernDashboard />
```

---

### 2. InteractiveTimetable 📅

**Файл:** `components/InteractiveTimetable.tsx`

Інтерактивний розклад з повним редагуванням:

#### Функції:

| Функція          | Опис                      | Як використати             |
| ---------------- | ------------------------- | -------------------------- |
| **Drag & Drop**  | Переміщення занять        | Затисни картку → перетягни |
| **Lock/Unlock**  | Блокування від змін       | ПКМ → Заблокувати          |
| **Undo/Redo**    | Відміна дій               | Кнопки або Ctrl+Z/Y        |
| **Context Menu** | Швидкі дії                | Права кнопка миші          |
| **View Modes**   | Тиждень/День              | Toggle в тулбарі           |
| **Zoom**         | Масштабування             | Кнопки +/-                 |
| **Filters**      | Групи/Викладачі/Аудиторії | Dropdown меню              |

```typescript
// Картка заняття показує:
- Код курсу
- Назву курсу
- Викладача (👤)
- Групу (👥)
- Аудиторію (🏠)
- Статус блокування (🔒)
- Індикатор конфлікту (⚠️)
```

---

### 3. AIControlPanel 🤖

**Файл:** `components/AIControlPanel.tsx`

Повний контроль над AI генерацією:

#### PPO Hyperparameters:

```typescript
interface PPOParams {
  learning_rate: number; // 0.00001 - 0.01 (default: 0.0003)
  gamma: number; // 0.9 - 0.999 (default: 0.99)
  epsilon: number; // 0.1 - 0.3 (default: 0.2)
  batch_size: number; // 16, 32, 64, 128 (default: 32)
}
```

#### Constraint Weights (слайдери 0-100%):

| Обмеження            | Опис                          |
| -------------------- | ----------------------------- |
| **Teacher Conflict** | Уникнення накладок викладачів |
| **Room Conflict**    | Уникнення накладок аудиторій  |
| **Group Conflict**   | Уникнення накладок груп       |
| **Capacity**         | Відповідність місткості       |
| **Preferences**      | Врахування побажань           |

#### Режими роботи:

- **Compact Mode** - для sidebar/dashboard
- **Full Mode** - окрема сторінка

```typescript
<AIControlPanel compact={true} onGenerationComplete={() => loadSchedule()} />
```

---

### 4. ConflictCenter ⚠️

**Файл:** `components/ConflictCenter.tsx`

Центр управління конфліктами:

#### Типи конфліктів:

| Тип                 | Колір       | Пріоритет    |
| ------------------- | ----------- | ------------ |
| **Hard** (Жорсткий) | 🔴 Червоний | Критичний    |
| **Soft** (М'який)   | 🟡 Жовтий   | Рекомендація |

#### Категорії:

| Категорія    | Іконка | Опис               |
| ------------ | ------ | ------------------ |
| `teacher`    | 👤     | Конфлікт викладача |
| `room`       | 🏠     | Конфлікт аудиторії |
| `group`      | 👥     | Конфлікт групи     |
| `capacity`   | ⚠️     | Проблема місткості |
| `preference` | ℹ️     | Порушення побажань |

#### AI Рекомендації:

Кожен конфлікт має:

- Детальний опис проблеми
- Список зачеплених елементів
- AI-генеровані рекомендації
- Кнопка "Застосувати" для швидкого виправлення

```typescript
<ConflictCenter compact={false} autoRefresh={true} refreshInterval={5000} />
```

---

## 🔌 API Сервіси

### Розширений api.ts

#### Schedule Generation:

```typescript
interface GenerationParams {
  iterations: number;
  preserve_locked?: boolean;
  use_existing?: boolean;
  // PPO Hyperparameters
  learning_rate?: number;
  gamma?: number;
  epsilon?: number;
  batch_size?: number;
  // Constraint weights
  constraint_weights?: {
    teacher_conflict: number;
    room_conflict: number;
    group_conflict: number;
    capacity: number;
    preferences: number;
  };
}

generateSchedule(params: GenerationParams)
getGenerationStatus(id: number)
stopGeneration(id: number)
```

#### AI Explainability:

```typescript
aiService = {
  getDecisionExplanation(classId)  // Чому AI так вирішив
  getScheduleScore()               // Загальна оцінка
  getTrainingHistory(genId?)       // Історія reward
  getImprovementSuggestions()      // Рекомендації
  getModelInfo()                   // Інфо про модель
}
```

#### History / Undo-Redo:

```typescript
historyService = {
  getHistory(limit?)  // Історія змін
  undo()              // Відміна
  redo()              // Повтор
  canUndo()           // Чи можна відмінити
  canRedo()           // Чи можна повторити
}
```

#### Statistics:

```typescript
statsService = {
  getDashboardStats()         // Загальна статистика
  getConstraintViolations()   // Порушення обмежень
  getUtilizationStats()       // Завантаженість
  getDistributionStats()      // Розподіл
}
```

---

## 🎨 Дизайн система

### Кольорова палітра:

| Призначення | Колір        | Hex       |
| ----------- | ------------ | --------- |
| Primary     | Синій        | `#1976d2` |
| Success     | Зелений      | `#4caf50` |
| Warning     | Помаранчевий | `#ff9800` |
| Error       | Червоний     | `#f44336` |
| Secondary   | Фіолетовий   | `#9c27b0` |
| Background  | Світло-сірий | `#f5f7fa` |

### Типографіка:

- **Шрифт:** Inter, Roboto, Helvetica
- **Headers:** fontWeight: 700, 600
- **Body:** fontWeight: 400

### Компоненти Material-UI:

- `Card` - контейнери з тінню
- `Chip` - теги та індикатори
- `Badge` - числові позначки
- `LinearProgress` - прогрес-бари
- `CircularProgress` - кругові індикатори
- `Tooltip` - підказки

---

## 🚀 Запуск

### Frontend:

```bash
cd frontend
npm install
npm start
```

### Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Повна система:

```bash
RUN_FULL_SYSTEM.bat
```

---

## 📱 Адаптивність

| Пристрій            | Sidebar     | Layout   |
| ------------------- | ----------- | -------- |
| Desktop (>1200px)   | Постійний   | Grid     |
| Tablet (600-1200px) | Collapsible | Flexible |
| Mobile (<600px)     | Hamburger   | Stack    |

---

## ⌨️ Клавіатурні скорочення

| Комбінація | Дія           |
| ---------- | ------------- |
| `Ctrl+Z`   | Undo          |
| `Ctrl+Y`   | Redo          |
| `Ctrl+S`   | Зберегти      |
| `Esc`      | Закрити модал |

---

## 🛠️ Технології

- **React 18** + TypeScript
- **Material-UI v5** для UI
- **Recharts** для графіків
- **React Router v6** для маршрутизації
- **Axios** для HTTP

---

## 📁 Маршрути

| Шлях            | Компонент            | Опис           |
| --------------- | -------------------- | -------------- |
| `/`             | ModernDashboard      | Головна панель |
| `/timetable`    | InteractiveTimetable | Розклад        |
| `/ai-generator` | AIControlPanel       | AI генерація   |
| `/conflicts`    | ConflictCenter       | Конфлікти      |
| `/courses`      | CourseManagement     | Курси          |
| `/teachers`     | TeacherManagement    | Викладачі      |
| `/groups`       | GroupManagement      | Групи          |
| `/classrooms`   | CourseManagement     | Аудиторії      |
| `/schedules`    | ScheduleManager      | Збережені      |
| `/analytics`    | Analytics            | Аналітика      |
