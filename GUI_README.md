# 🖥️ Графічний інтерфейс користувача (GUI)

## 📋 Опис

Система має **ДВА графічні інтерфейси**:

### 1. 🐍 Python Desktop GUI (Tkinter)

Нативний desktop додаток для демонстрації всіх функцій обох систем.

### 2. 🌐 Web GUI (React)

Сучасний веб-інтерфейс для DRL системи з повним функціоналом.

---

## 🚀 Python Desktop GUI

### Запуск

**Windows:**

```cmd
RUN_GUI.bat
```

**Або напряму:**

```cmd
python gui_app.py
```

### Функції

#### Головна сторінка

- 🏠 Огляд обох систем
- 📊 Порівняння можливостей
- ⚡ Швидкий доступ до основних функцій

#### System 1: Classical Scheduler

- 📝 Створення розкладів через GUI
- 📂 Вибір файлів конфігурації
- 📊 Перегляд результатів у реальному часі
- 💾 Збереження output файлів
- 📈 Візуалізація логів виконання

#### System 2: DRL Scheduler

- 🚀 Запуск Backend сервера
- 🌐 Відкриття Web інтерфейсу
- 📊 Моніторинг статусу backend
- 🗄️ Наповнення бази даних
- 📚 Доступ до API документації

#### Додатково

- 📈 Детальне порівняння систем
- ℹ️ Інформація про проект
- 📝 Статистика та результати тестів

### Вимоги

```bash
# Вбудовані модулі Python:
- tkinter (зазвичай включений)
- json
- subprocess
- threading
- webbrowser
```

### Скріншоти функцій

**Головна сторінка:**

- Дві інформаційні картки (System 1 & 2)
- Швидкі кнопки дій
- Статус індикатори

**System 1 Interface:**

- Вкладка "Опис" - детальна інформація
- Вкладка "Запуск" - створення розкладів
- Вкладка "Результати" - перегляд output

**System 2 Interface:**

- Керування Backend
- Статус моніторинг
- Швидкий доступ до Web UI
- Наповнення БД

---

## 🌐 Web GUI (React)

### Запуск

```bash
cd frontend
npm install
npm start
```

Відкриється на: **http://localhost:3000**

### Архітектура

```
frontend/
├── src/
│   ├── App.tsx              # Головний компонент з навігацією
│   ├── components/
│   │   ├── Dashboard.tsx    # Головна панель управління
│   │   ├── CourseManagement.tsx       # CRUD для курсів
│   │   ├── TeacherManagement.tsx      # CRUD для викладачів
│   │   ├── GroupManagement.tsx        # CRUD для груп
│   │   ├── TimetableView.tsx          # Візуалізація розкладу
│   │   ├── Analytics.tsx              # Аналітика DRL
│   │   └── Navigation.tsx             # Бічна навігація
│   └── services/
│       └── api.ts           # API клієнт
```

### Компоненти

#### 1. Dashboard 📊

**Функції:**

- Генерація розкладів через DRL
- Моніторинг процесу навчання
- Статус поточної генерації
- Real-time оновлення

**Використання:**

1. Встановіть кількість ітерацій (10-1000)
2. Натисніть "Generate Schedule"
3. Спостерігайте за прогресом
4. Перегляньте результати

#### 2. Course Management 📚

**Функції:**

- Створення нових курсів
- Редагування існуючих
- Видалення курсів
- Перегляд списку

**Поля:**

- Code (унікальний)
- Name
- Credits
- Hours per week
- Lab requirement
- Preferred classroom type
- Difficulty level

#### 3. Teacher Management 👨‍🏫

**Функції:**

- Додавання викладачів
- Редагування профілів
- Управління preferences
- Видалення

**Поля:**

- Code
- Full name
- Email
- Department
- Max hours per week
- Avoid early/late slots

#### 4. Group Management 👥

**Функції:**

- Створення студентських груп
- Редагування інформації
- Видалення груп

**Поля:**

- Code (наприклад, CS-1A)
- Year
- Students count
- Specialization

#### 5. Timetable View 📅

**Функції:**

- Візуалізація розкладів
- Вибір групи
- Календарний вигляд
- Експорт (TODO)

**Режими:**

- Таблиця по днях
- Календар (FullCalendar)
- Список занять

#### 6. Analytics 📈

**Функції:**

- Графіки навчання DRL
- Метрики якості
- Історія генерацій
- Статистика конфліктів

**Візуалізації:**

- Reward dynamics
- Loss curves
- Conflict statistics
- Training progress

### Технології

| Технологія   | Версія  | Призначення   |
| ------------ | ------- | ------------- |
| React        | 18.2.0  | UI Framework  |
| TypeScript   | 4.9.5   | Type Safety   |
| Material-UI  | 5.14.20 | UI Components |
| React Router | 6.20.1  | Navigation    |
| Axios        | 1.6.2   | HTTP Client   |
| Recharts     | 2.10.3  | Charts        |
| FullCalendar | 6.1.10  | Calendar      |
| D3.js        | 7.8.5   | Data Viz      |

### API Endpoints

Всі компоненти взаємодіють з Backend через REST API:

```typescript
// Courses
GET /
  api /
  courses / // Список курсів
  POST /
  api /
  courses / // Створити курс
  PUT /
  api /
  courses /
  { id }; // Оновити курс
DELETE / api / courses / { id }; // Видалити курс

// Teachers
GET /
  api /
  teachers / // Список викладачів
  POST /
  api /
  teachers / // Створити викладача
  PUT /
  api /
  teachers /
  { id }; // Оновити викладача
DELETE / api / teachers / { id }; // Видалити викладача

// Groups
GET /
  api /
  groups / // Список груп
  POST /
  api /
  groups / // Створити групу
  PUT /
  api /
  groups /
  { id }; // Оновити групу
DELETE / api / groups / { id }; // Видалити групу

// Schedule
POST / api / schedule / generate; // Генерація розкладу
GET / api / schedule / status / { id }; // Статус генерації
GET / api / timetable / { group_id }; // Розклад групи
```

### Стилі та Теми

**Кольорова схема:**

- Primary: `#1976d2` (синій)
- Secondary: `#dc004e` (червоний)
- Success: `#4caf50` (зелений)
- Warning: `#ff9800` (помаранчевий)
- Background: `#f5f5f5` (світло-сірий)

**Responsive Design:**

- Desktop: повна навігація
- Tablet: адаптивна навігація
- Mobile: бургер-меню

---

## 🎨 Особливості дизайну

### Python GUI

✅ Нативний вигляд Windows  
✅ Інтуїтивна навігація  
✅ Real-time логування  
✅ Кольорові індикатори статусу  
✅ Картки з інформацією  
✅ Модальні діалоги

### Web GUI

✅ Material Design  
✅ Responsive layout  
✅ Smooth animations  
✅ Dark mode ready  
✅ Professional look  
✅ Modern UX patterns

---

## 📸 Демонстрація

### Python Desktop GUI

**1. Головне меню:**

```
┌─────────────────────────────────────┐
│  Меню                               │
├─────────────────────────────────────┤
│  🏠 Головна                         │
│  📊 System 1: Classical            │
│  🤖 System 2: DRL                  │
│  📝 Створити розклад (S1)          │
│  🚀 DRL Backend                    │
│  🌐 Web Interface                  │
│  📈 Порівняння систем              │
│  ℹ️ Про програму                   │
└─────────────────────────────────────┘
```

**2. Робота з System 1:**

- Вибір config.json
- Вибір input.json
- Запуск генерації
- Перегляд логів у реальному часі
- Результат у output.json

**3. Керування System 2:**

- Запуск uvicorn backend
- Статус моніторинг
- Відкриття браузера
- Наповнення БД

### Web GUI

**1. Dashboard:**

```
┌────────────────────────────────────────────┐
│  Generate Schedule                         │
├────────────────────────────────────────────┤
│  Iterations: [100] ▼                       │
│  [Generate Schedule] 🚀                    │
│                                            │
│  Status: Running...                        │
│  Progress: 45%                             │
└────────────────────────────────────────────┘
```

**2. Course Management:**

- Таблиця всіх курсів
- Кнопка "Add Course"
- Edit/Delete для кожного
- Форма з валідацією

**3. Timetable View:**

- Calendar view
- Фільтр по групах
- Кольорове кодування
- Export кнопки

---

## 🔧 Налаштування

### Python GUI

Немає конфігурації - працює "з коробки"!

### Web GUI

**Backend URL:**  
За замовчуванням: `http://127.0.0.1:8000`

Змінити в `frontend/src/services/api.ts`:

```typescript
const API_BASE_URL = "http://127.0.0.1:8000/api";
```

**Port:**  
За замовчуванням: `3000`

Змінити: створіть `.env` файл:

```env
PORT=3001
```

---

## 🐛 Troubleshooting

### Python GUI

**Проблема:** Tkinter не знайдено  
**Рішення:** Перевстановіть Python з опцією "tcl/tk"

**Проблема:** GUI не відкривається  
**Рішення:**

```bash
python -m tkinter  # Перевірка tkinter
```

### Web GUI

**Проблема:** npm install fails  
**Рішення:**

```bash
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

**Проблема:** Backend connection error  
**Рішення:**

1. Перевірте backend: http://127.0.0.1:8000/docs
2. Перевірте CORS налаштування
3. Перезапустіть backend

**Проблема:** Port 3000 зайнятий  
**Рішення:**

```bash
PORT=3001 npm start
```

---

## 📚 Документація компонентів

### Приклад використання API у React:

```typescript
import { getCourses, createCourse } from "../services/api";

// Завантажити курси
const courses = await getCourses();

// Створити курс
const newCourse = await createCourse({
  code: "CS-101",
  name: "Programming",
  credits: 4,
  hours_per_week: 8,
});
```

### Приклад використання Python GUI:

```python
# gui_app.py вже містить всі функції
# Запустіть через:
python gui_app.py
```

---

## ✨ Майбутні покращення

### Python GUI

- [ ] Drag & drop для файлів
- [ ] Графіки результатів
- [ ] Експорт в PDF
- [ ] Порівняння розкладів
- [ ] Історія запусків

### Web GUI

- [ ] Dark mode
- [ ] Excel import/export
- [ ] Drag & drop розкладу
- [ ] Multi-language
- [ ] User authentication
- [ ] Real-time updates (WebSocket)
- [ ] Mobile app

---

## 📞 Підтримка

**Технічна інформація:**

- Python GUI: tkinter (built-in)
- Web GUI: React 18 + Material-UI 5
- Backend: FastAPI (має бути запущений)
- Browser: Chrome/Firefox/Edge (latest)

**Тестування:**

- Python GUI: Windows 10/11
- Web GUI: Всі сучасні браузери
- Backend: Python 3.13, SQLite

---

**Графічний інтерфейс готовий до використання!**  
Оберіть той, що підходить вам найкраще:

- 🐍 Python GUI - для швидкого desktop доступу
- 🌐 Web GUI - для професійного web досвіду
