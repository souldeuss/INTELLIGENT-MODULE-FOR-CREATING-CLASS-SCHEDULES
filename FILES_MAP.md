# 📂 Мапа файлів проекту - GUI Edition

## 🎯 Головні файли для запуску

| Файл                    | Призначення        | Команда                                                 |
| ----------------------- | ------------------ | ------------------------------------------------------- |
| **RUN_GUI.bat**         | Запуск Desktop GUI | Подвійний клік                                          |
| **gui_app.py**          | Desktop GUI код    | `python gui_app.py`                                     |
| **backend/app/main.py** | Backend server     | `cd backend && python -m uvicorn app.main:app --reload` |
| **frontend/**           | Web GUI            | `cd frontend && npm start`                              |

---

## 📚 Документація (читайте в цьому порядку)

### 🌟 Рівень 1: Старт (ПОЧНІТЬ ТУТ)

```
START_HERE.md              # 📍 Центр управління проектом
```

### ⚡ Рівень 2: Швидкий старт

```
QUICKSTART_GUI.md          # Швидкий старт обох GUI
README_GUI.md              # Огляд GUI можливостей
```

### 📖 Рівень 3: Детальна інформація

```
GUI_README.md              # Повний опис GUI
GUI_SUMMARY.md             # Підсумок створеного
PROJECT_STATUS.md          # Статус всього проекту
BACKEND_READY.md           # Backend setup
README_DRL.md              # DRL архітектура
README.md                  # Оригінальний README
```

---

## 🖥️ Desktop GUI файли

```
📂 Корінь проекту/
├── gui_app.py                     # Desktop GUI (982 рядки)
├── RUN_GUI.bat                    # Швидкий запуск
└── START_HERE.md                  # Документація старту
```

**gui_app.py містить:**

- Клас `SchedulerGUI` з 25+ методами
- Головна сторінка з картками
- System 1 інтерфейс (3 вкладки)
- System 2 інтерфейс (2 вкладки)
- Порівняння систем
- Інформація про проект

---

## 🌐 Web GUI файли

```
📂 frontend/
├── package.json                   # Dependencies
├── tsconfig.json                  # TypeScript config
├── public/
│   └── index.html                # HTML template
└── src/
    ├── index.tsx                 # React entry point
    ├── App.tsx                   # Main app + navigation (180 рядків)
    ├── services/
    │   └── api.ts               # API client
    └── components/
        ├── Dashboard.tsx         # Генерація розкладів
        ├── Navigation.tsx        # Sidebar menu (NEW, 70 рядків)
        ├── CourseManagement.tsx  # CRUD курси
        ├── TeacherManagement.tsx # CRUD викладачі (NEW, 180 рядків)
        ├── GroupManagement.tsx   # CRUD групи (NEW, 150 рядків)
        ├── TimetableView.tsx     # Візуалізація розкладу
        └── Analytics.tsx         # Аналітика DRL
```

**Нові компоненти (створені зараз):**

- `Navigation.tsx` - компонент бічного меню
- `TeacherManagement.tsx` - повний CRUD для викладачів
- `GroupManagement.tsx` - повний CRUD для груп

**Оновлені компоненти:**

- `App.tsx` - додано sidebar, drawer, navigation

---

## 🤖 System 1: Classical Scheduler

```
📂 src/
├── main.py                        # CLI entry point
└── imscheduler/
    ├── __init__.py
    ├── config.py                  # Configuration
    ├── models.py                  # Data models
    ├── generator.py               # Schedule generator
    ├── solver.py                  # Constraint solver
    ├── validator.py               # Validation
    ├── logger.py                  # Logging
    └── modes/
        └── base.py                # Dense/Balanced/Append modes

📂 data/
├── config.sample.json             # Sample config
├── input.sample.json              # Sample input
├── test_config_dense.json         # Dense test config
├── test_input_dense.json          # Dense test data
├── test_config_balanced.json      # Balanced test config
├── test_input_balanced.json       # Balanced test data
├── test_config_append.json        # Append test config
├── test_input_append.json         # Append test data
├── output_dense.json              # Dense results
├── output_balanced.json           # Balanced results
└── output_append.json             # Append results

📂 tests/
├── conftest.py                    # Pytest fixtures
├── test_generator.py              # Generator tests
├── test_solver.py                 # Solver tests
└── test_validator.py              # Validator tests
```

---

## 🚀 System 2: DRL Scheduler

```
📂 backend/
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker config
├── start.bat                      # Quick start script
├── populate_db.py                 # DB population utility
├── QUICKSTART.md                  # Backend setup guide
├── timetabling.db                 # SQLite database (auto-created)
└── app/
    ├── main.py                    # FastAPI application
    ├── models/
    │   └── database.py           # SQLAlchemy ORM models
    ├── schemas/
    │   └── schemas.py            # Pydantic models
    ├── core/
    │   ├── environment.py        # DRL environment
    │   ├── actor_critic.py       # Neural network
    │   ├── ppo_trainer.py        # PPO algorithm
    │   └── database_session.py   # DB session
    └── api/
        ├── courses.py            # Course endpoints
        ├── teachers.py           # Teacher endpoints
        ├── groups.py             # Group endpoints
        ├── classrooms.py         # Classroom endpoints
        ├── timeslots.py          # Timeslot endpoints
        └── schedule.py           # Schedule generation
```

---

## 🐳 Docker

```
📂 Корінь/
├── docker-compose.yml             # Multi-container setup
├── backend/Dockerfile             # Backend image
└── frontend/Dockerfile            # Frontend image
```

---

## 📄 Всі документаційні файли

### Створені для GUI:

```
START_HERE.md                      # Центр управління (NEW)
QUICKSTART_GUI.md                  # Швидкий старт GUI (NEW)
README_GUI.md                      # Огляд GUI (NEW)
GUI_README.md                      # Детальний опис GUI (NEW)
GUI_SUMMARY.md                     # Підсумок GUI (NEW)
FILES_MAP.md                       # Цей файл (NEW)
```

### Існуючі:

```
README.md                          # Оригінальний опис
README_DRL.md                      # DRL система
PROJECT_STATUS.md                  # Статус проекту
BACKEND_READY.md                   # Backend ready guide
backend/QUICKSTART.md              # Backend quickstart
```

---

## 🎯 Швидкий доступ по завданням

### Хочу запустити Desktop GUI:

```
1. gui_app.py (код)
2. RUN_GUI.bat (запуск)
3. QUICKSTART_GUI.md (інструкції)
```

### Хочу запустити Web GUI:

```
1. backend/app/main.py (backend)
2. frontend/src/App.tsx (frontend)
3. QUICKSTART_GUI.md (інструкції)
```

### Хочу створити розклад (System 1):

```
1. src/main.py (CLI)
2. gui_app.py (через GUI)
3. data/test_config_dense.json (config)
4. data/test_input_dense.json (input)
```

### Хочу використати DRL (System 2):

```
1. backend/app/main.py (запустити)
2. frontend/ (відкрити Web UI)
3. backend/populate_db.py (наповнити БД)
4. Dashboard → Generate Schedule
```

### Хочу розібратися в коді:

```
Frontend:
- frontend/src/App.tsx (навігація)
- frontend/src/components/*.tsx (компоненти)

Backend:
- backend/app/main.py (FastAPI)
- backend/app/core/*.py (DRL engine)
- backend/app/api/*.py (endpoints)

Desktop GUI:
- gui_app.py (всі функції)
```

### Хочу прочитати документацію:

```
Новачок:
1. START_HERE.md
2. QUICKSTART_GUI.md
3. README_GUI.md

Досвідчений:
1. PROJECT_STATUS.md
2. GUI_README.md
3. README_DRL.md
```

---

## 📊 Статистика файлів

### Python файли:

```
gui_app.py                 982 рядки    (NEW)
src/imscheduler/*.py       ~1500 рядків (System 1)
backend/app/**/*.py        ~2000 рядків (System 2)
tests/*.py                 ~400 рядків  (Tests)
────────────────────────────────────────
Всього Python:            ~4900 рядків
```

### TypeScript/React файли:

```
App.tsx                    180 рядків   (UPDATED)
Navigation.tsx             70 рядків    (NEW)
TeacherManagement.tsx      180 рядків   (NEW)
GroupManagement.tsx        150 рядків   (NEW)
Dashboard.tsx              ~200 рядків  (EXISTING)
CourseManagement.tsx       ~200 рядків  (EXISTING)
TimetableView.tsx          ~150 рядків  (EXISTING)
Analytics.tsx              ~150 рядків  (EXISTING)
api.ts                     ~100 рядків  (EXISTING)
────────────────────────────────────────
Всього TypeScript:        ~1400 рядків
```

### Документація:

```
START_HERE.md              200 рядків   (NEW)
QUICKSTART_GUI.md          400 рядків   (NEW)
README_GUI.md              400 рядків   (NEW)
GUI_README.md              600 рядків   (NEW)
GUI_SUMMARY.md             400 рядків   (NEW)
FILES_MAP.md               300 рядків   (NEW - цей файл)
PROJECT_STATUS.md          500 рядків   (EXISTING)
BACKEND_READY.md           200 рядків   (EXISTING)
README_DRL.md              300 рядків   (EXISTING)
────────────────────────────────────────
Всього документації:      ~3300 рядків
```

### Конфігурація:

```
package.json
tsconfig.json
docker-compose.yml
requirements.txt (x2)
.env.example
Dockerfile (x2)
────────────────────────────────────────
~10 конфігураційних файлів
```

---

## 🎯 Ключові файли для демонстрації

### Для швидкої демонстрації (5 хв):

1. `gui_app.py` - показати Desktop GUI
2. `START_HERE.md` - показати документацію
3. `data/output_dense.json` - показати результати

### Для повної демонстрації (15 хв):

1. `gui_app.py` - Desktop GUI всі розділи
2. `frontend/src/App.tsx` - Web GUI навігація
3. `frontend/src/components/Dashboard.tsx` - генерація
4. `frontend/src/components/TeacherManagement.tsx` - CRUD
5. `backend/app/core/actor_critic.py` - DRL архітектура

### Для технічної презентації:

1. `backend/app/main.py` - FastAPI endpoints
2. `backend/app/core/environment.py` - DRL environment
3. `backend/app/models/database.py` - Database models
4. `frontend/src/services/api.ts` - API integration
5. `PROJECT_STATUS.md` - повна архітектура

---

## 🔍 Пошук файлів

### За типом:

```bash
# Python коду
find . -name "*.py"

# React компоненти
find frontend/src -name "*.tsx"

# Документація
find . -name "*.md"

# Конфігурація
find . -name "*.json"
```

### За функціональністю:

```bash
# GUI файли
gui_app.py
RUN_GUI.bat
frontend/src/components/*.tsx

# Backend API
backend/app/api/*.py

# DRL engine
backend/app/core/*.py

# Тести
tests/*.py

# Документація GUI
*GUI*.md
START_HERE.md
QUICKSTART*.md
```

---

## ✨ Новостворені файли (цей сесія)

### Python:

- ✅ gui_app.py (982 рядки)
- ✅ RUN_GUI.bat

### React/TypeScript:

- ✅ frontend/src/components/Navigation.tsx (70 рядків)
- ✅ frontend/src/components/TeacherManagement.tsx (180 рядків)
- ✅ frontend/src/components/GroupManagement.tsx (150 рядків)
- ✅ frontend/src/App.tsx (оновлено, +80 рядків)

### Документація:

- ✅ START_HERE.md (200 рядків)
- ✅ QUICKSTART_GUI.md (400 рядків)
- ✅ README_GUI.md (400 рядків)
- ✅ GUI_README.md (600 рядків)
- ✅ GUI_SUMMARY.md (400 рядків)
- ✅ FILES_MAP.md (цей файл, 300 рядків)

**Всього: ~3800 рядків нового коду та документації!**

---

## 🎉 Підсумок

**Проект містить:**

- 📂 ~50+ файлів коду
- 📚 ~12 документаційних файлів
- 🐍 ~4900 рядків Python
- ⚛️ ~1400 рядків TypeScript/React
- 📖 ~3300 рядків документації
- ⚙️ ~10 конфігураційних файлів

**Все готово до використання та демонстрації!**

**Почніть з:** [START_HERE.md](START_HERE.md)

---

**Успіхів! 🚀🎓**
