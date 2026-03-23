# 🚀 Швидкий старт - Графічний інтерфейс

## 🎯 Два способи використання

### 🖥️ Варіант 1: Desktop GUI (Python/Tkinter)

**Найшвидший спосіб - подвійний клік:**

```
📂 Подвійний клік на файл: RUN_GUI.bat
```

**Або через командний рядок:**

```cmd
python gui_app.py
```

**Що відкриється:**

- ✅ Повноцінний desktop застосунок
- ✅ Доступ до обох систем (Classical + DRL)
- ✅ Створення розкладів через GUI
- ✅ Запуск DRL backend
- ✅ Моніторинг статусу
- ✅ Перегляд результатів

**Немає залежностей!** Tkinter входить до складу Python.

---

### 🌐 Варіант 2: Web GUI (React)

**Крок 1: Запустити Backend**

```cmd
cd backend
python -m uvicorn app.main:app --reload
```

✅ Backend: http://127.0.0.1:8000

**Крок 2: Запустити Frontend**

```cmd
cd frontend
npm install    # тільки перший раз
npm start
```

✅ Frontend: http://localhost:3000

**Що відкриється:**

- ✅ Сучасний web інтерфейс
- ✅ Material-UI дизайн
- ✅ CRUD для всіх сутностей
- ✅ Візуалізація розкладів
- ✅ Аналітика DRL навчання
- ✅ Real-time оновлення

---

## 📋 Що можна робити

### Desktop GUI (Python)

**System 1 - Classical Scheduler:**

1. Вибрати config файл (data/test_config_dense.json)
2. Вибрати input файл (data/test_input_dense.json)
3. Встановити output файл
4. Натиснути "Створити розклад"
5. Переглянути логи у реальному часі
6. Завантажити результати

**System 2 - DRL Scheduler:**

1. Натиснути "Запустити Backend"
2. Дочекатися "Application startup complete"
3. Натиснути "Відкрити Web Interface"
4. Працювати через браузер
5. Або натиснути "Наповнити БД" для тестових даних

**Додатково:**

- Порівняння систем (таблиця)
- Інформація про проект
- Статус індикатори

### Web GUI (React)

**Dashboard:**

- Генерація розкладів (встановити iterations: 10-1000)
- Моніторинг прогресу генерації
- Перегляд статусу

**Course Management:**

- Додати курси (Code, Name, Credits, Hours/week)
- Редагувати існуючі
- Видаляти курси
- Переглядати список

**Teacher Management:**

- Додати викладачів
- Встановити max hours per week
- Налаштувати preferences
- Управління списком

**Group Management:**

- Створити студентські групи
- Вказати рік та спеціалізацію
- Підрахунок студентів

**Timetable View:**

- Вибрати групу
- Переглянути розклад
- Календарний вигляд

**Analytics:**

- Графіки навчання
- Метрики якості
- Статистика конфліктів

---

## ✅ Швидкий тест

### Desktop GUI Test (1 хвилина)

```cmd
# 1. Запустити GUI
python gui_app.py

# 2. У меню вибрати "System 1: Classical"

# 3. Перевірити, що файли встановлені:
#    Config: data/test_config_dense.json
#    Input:  data/test_input_dense.json
#    Output: data/output_gui.json

# 4. Натиснути "Створити розклад"

# 5. Переглянути логи - має з'явитися:
#    "Розклад успішно створено!"

# 6. Перейти на вкладку "Результати"

# 7. Натиснути "Завантажити"

# 8. Переглянути розклад!
```

### Web GUI Test (2 хвилини)

```cmd
# Terminal 1: Backend
cd backend
python -m uvicorn app.main:app --reload
# Дочекатись: "Application startup complete"

# Terminal 2: Frontend
cd frontend
npm start
# Дочекатись: "Compiled successfully!"

# Браузер відкриється автоматично на http://localhost:3000

# 1. Натиснути Dashboard (ліве меню)

# 2. Натиснути "Courses" → "Add Course"
#    Code: CS-101
#    Name: Programming
#    Credits: 4
#    Hours/week: 8
#    Save

# 3. Аналогічно додати Teacher, Group, Classroom, Timeslot

# 4. Повернутися на Dashboard

# 5. Iterations: 10

# 6. Натиснути "Generate Schedule"

# 7. Спостерігати за статусом!
```

---

## 🎨 Переваги кожного GUI

### Desktop (Python/Tkinter)

✅ **Pros:**

- Миттєвий запуск (без dependencies)
- Нативний вигляд Windows
- Доступ до обох систем в одному вікні
- Не потребує браузера
- Легкий вага
- Простий у використанні

❌ **Cons:**

- Тільки Windows/Mac/Linux desktop
- Базовий дизайн
- Немає real-time web features

### Web (React/Material-UI)

✅ **Pros:**

- Професійний сучасний дизайн
- Responsive (працює на всіх пристроях)
- Real-time оновлення
- Інтеграція з REST API
- Багаті можливості візуалізації
- Production-ready

❌ **Cons:**

- Потребує npm install
- Треба запускати backend + frontend
- Більше залежностей

---

## 🔧 Налаштування

### Desktop GUI - Немає конфігурації! 🎉

Працює "з коробки".

### Web GUI - Опціонально

**Змінити backend URL:**

`frontend/src/services/api.ts`

```typescript
const API_BASE_URL = "http://your-server:8000/api";
```

**Змінити port:**

`frontend/.env`

```
PORT=3001
```

---

## 📸 Скріншоти функцій

### Desktop GUI

```
┌────────────────────────────────────────────────────────────┐
│  🎓 Система складання розкладів занять                    │
├─────────────┬──────────────────────────────────────────────┤
│ Меню:       │  Головна сторінка                            │
│             │                                              │
│ 🏠 Головна  │  ┌────────────────┐  ┌────────────────┐    │
│ 📊 System 1 │  │ System 1       │  │ System 2       │    │
│ 🤖 System 2 │  │ Classical      │  │ DRL Scheduler  │    │
│ 📝 Розклад  │  │ ⚡ Швидко      │  │ 🤖 AI-based    │    │
│ 🚀 Backend  │  │ ✅ Простий     │  │ 🌐 Web UI      │    │
│ 🌐 Web UI   │  └────────────────┘  └────────────────┘    │
│ 📈 Порівн.  │                                              │
│ ℹ️ Про      │  [Створити розклад] [DRL Backend] [Web UI] │
└─────────────┴──────────────────────────────────────────────┘
```

### Web GUI

```
┌──────────────────────────────────────────────────────────────┐
│ Intelligent Module for Creating Class Schedules         ☰   │
├──────────────────────────────────────────────────────────────┤
│ ┌─────────────┐                                              │
│ │ Dashboard   │  Generate Schedule                           │
│ │ Courses     │  ┌─────────────────────────────────────┐    │
│ │ Teachers    │  │ Iterations: [100]     ▼             │    │
│ │ Groups      │  │                                     │    │
│ │ Classrooms  │  │ [Generate Schedule] 🚀              │    │
│ │ Timeslots   │  └─────────────────────────────────────┘    │
│ │ Timetable   │                                              │
│ │ Analytics   │  Status: ● Running                           │
│ └─────────────┘  Progress: [████████──────] 60%             │
└──────────────────────────────────────────────────────────────┘
```

---

## 💡 Поради

### Для Desktop GUI:

1. **Використовуйте існуючі test файли** з папки `data/`
2. **Слідкуйте за логами** - вони показують всі кроки
3. **Результати зберігаються** у вказаний output файл
4. **Backend можна запустити** прямо з GUI

### Для Web GUI:

1. **Спочатку backend, потім frontend**
2. **Використовуйте API docs** (http://127.0.0.1:8000/docs)
3. **Створіть тестові дані** перед генерацією
4. **Iterations: 10-50** для швидкого тесту, 100-1000 для якості

---

## 🐛 Швидке вирішення проблем

### Desktop GUI не запускається

```cmd
python -m tkinter
# Якщо помилка - переінсталюйте Python з tcl/tk
```

### Web Frontend не компілюється

```cmd
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Backend connection error

```cmd
# Перевірити:
curl http://127.0.0.1:8000/docs
# Або відкрити у браузері
```

### Port 3000 зайнятий

```cmd
# Windows:
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Або змінити port:
PORT=3001 npm start
```

---

## 🎯 Рекомендації

**Для демонстрації проекту:**

1. Запустіть **Desktop GUI** - показує обидві системи
2. Створіть розклад через System 1 (швидко)
3. Покажіть порівняння систем
4. Запустіть Web UI через GUI
5. Продемонструйте modern web interface

**Для щоденної роботи:**

- **Desktop GUI** - швидкий доступ, прості задачі
- **Web GUI** - професійна робота, складні розклади

**Для презентації:**

- Desktop GUI відкрито на головному екрані
- Web UI відкритий на другому моніторі/вкладці
- Показ паралельної роботи обох систем

---

## ✨ Готово!

Обидва інтерфейси повністю функціональні та готові до використання!

**Desktop GUI:** `python gui_app.py` або `RUN_GUI.bat`  
**Web GUI:** Backend + Frontend (див. вище)

**Документація:**

- [GUI_README.md](GUI_README.md) - повний опис
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - статус проекту
- [BACKEND_READY.md](BACKEND_READY.md) - backend setup

Приємного використання! 🚀
