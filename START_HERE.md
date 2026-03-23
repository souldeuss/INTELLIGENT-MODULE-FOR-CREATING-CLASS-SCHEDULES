# 🎯 START HERE - Центр управління проектом

## 🚀 Найшвидший старт

### ⚡ Запустити ВСЮ систему (Backend + Web UI):

**Подвійний клік на:** **RUN_FULL_SYSTEM.bat** ⭐ **РЕКОМЕНДОВАНО!**

Автоматично запустить:

- Backend Server (FastAPI + DRL)
- Web UI (React)
- Відкриє браузер

### 🖥️ Або запустити Desktop GUI:

**Подвійний клік на:** **RUN_GUI.bat**

```cmd
python gui_app.py
```

---

## 📚 Документація - що читати?

### Для швидкого старту:

1. **[QUICKSTART_GUI.md](QUICKSTART_GUI.md)** ⭐ - ПОЧНІТЬ ТУТ! Швидкий старт GUI
2. **[README_GUI.md](README_GUI.md)** - Огляд GUI можливостей

### Для глибокого розуміння:

3. **[PROJECT_STATUS.md](PROJECT_STATUS.md)** - Повний статус проекту
4. **[GUI_README.md](GUI_README.md)** - Детальний опис GUI
5. **[BACKEND_READY.md](BACKEND_READY.md)** - Backend setup
6. **[README_DRL.md](README_DRL.md)** - DRL архітектура

---

## 🎬 Що можна робити?

### 1. Desktop GUI (Python)

```cmd
python gui_app.py
```

- ✅ Створювати розклади (System 1)
- ✅ Запускати DRL backend (System 2)
- ✅ Переглядати результати
- ✅ Порівнювати системи
- ✅ Моніторити статус

### 2. Web Interface (React)

**Автоматичний запуск:**

```cmd
RUN_FULL_SYSTEM.bat
```

**Або вручну:**

```cmd
# Terminal 1 - Backend:
RUN_BACKEND.bat

# Terminal 2 - Frontend:
RUN_WEB_UI.bat
```

- ✅ CRUD для всіх сутностей (викладачі, групи, курси, аудиторії)
- ✅ Генерація розкладів через DRL
- ✅ Візуалізація розкладу
- ✅ Аналітика DRL навчання

### 3. CLI (Classical System)

```cmd
python src/main.py --config data/test_config_dense.json --input data/test_input_dense.json --output data/output.json
```

- ✅ Швидке створення розкладів
- ✅ 3 режими роботи
- ✅ Консольний вивід

---

## 🗂️ Структура файлів

```
📂 Головна папка
│
├── 🚀 ЗАПУСК
│   ├── RUN_FULL_SYSTEM.bat         # Запуск всієї системи ⭐ NEW!
│   ├── RUN_BACKEND.bat             # Запуск тільки Backend ⭐ NEW!
│   ├── RUN_WEB_UI.bat              # Запуск тільки Web UI ⭐ NEW!
│   ├── RUN_GUI.bat                 # Запуск Desktop GUI
│   ├── gui_app.py                  # Desktop GUI
│   └── src/main.py                 # CLI для System 1
│
├── 📚 ДОКУМЕНТАЦІЯ (читайте по порядку)
│   ├── START_HERE.md              # ⭐ Цей файл
│   ├── QUICKSTART_GUI.md          # Швидкий старт GUI
│   ├── README_GUI.md              # Огляд GUI
│   ├── GUI_README.md              # Детальний опис GUI
│   ├── PROJECT_STATUS.md          # Статус проекту
│   ├── BACKEND_READY.md           # Backend setup
│   └── README_DRL.md              # DRL система
│
├── 🤖 СИСТЕМА 1: Classical
│   ├── src/imscheduler/           # Engine
│   ├── data/                      # Test data
│   └── tests/                     # Unit tests
│
├── 🚀 СИСТЕМА 2: DRL
│   ├── backend/                   # FastAPI + DRL
│   └── frontend/                  # React UI
│
└── 🐳 DOCKER
    └── docker-compose.yml         # Containers
```

---

## ⚡ Швидкі команди

### GUI (Desktop)

```cmd
python gui_app.py
```

### Backend (DRL)

```cmd
cd backend
python -m uvicorn app.main:app --reload
```

### Frontend (React)

```cmd
cd frontend
npm install  # перший раз
npm start
```

### CLI (System 1)

```cmd
python src/main.py --config data/test_config_dense.json --input data/test_input_dense.json --output output.json
```

### Tests

```cmd
pytest tests/
```

### Populate DB

```cmd
cd backend
python populate_db.py
```

---

## 🎯 URLs

| Сервіс      | URL                        |
| ----------- | -------------------------- |
| Backend API | http://127.0.0.1:8000      |
| API Docs    | http://127.0.0.1:8000/docs |
| Frontend    | http://localhost:3000      |

---

## ✅ Чеклист для демонстрації

### Перед презентацією:

- [ ] Запустити Desktop GUI
- [ ] Протестувати System 1 (створити розклад)
- [ ] Запустити Backend
- [ ] Запустити Frontend
- [ ] Додати тестові дані через Web UI
- [ ] Згенерувати розклад через DRL

### Під час презентації:

1. Показати Desktop GUI - головна сторінка
2. Продемонструвати System 1 (швидко)
3. Показати порівняння систем
4. Відкрити Web UI
5. Показати CRUD операції
6. Запустити DRL генерацію
7. Показати результати

---

## 🎓 Ключові досягнення проекту

### Технічні:

✅ 2 AI підходи (Classical + DRL)  
✅ 2 GUI (Desktop + Web)  
✅ REST API (20+ endpoints)  
✅ PyTorch Actor-Critic  
✅ React + TypeScript  
✅ SQLite database  
✅ Docker готовність  
✅ Unit tests (5/5)

### Функціональні:

✅ 3 режими складання розкладів  
✅ Повний CRUD для всіх сутностей  
✅ Real-time моніторинг  
✅ Візуалізація результатів  
✅ Аналітика навчання  
✅ Background processing

---

## 💡 Поради

### Для швидкої демонстрації:

1. Використовуйте **Desktop GUI** - все в одному вікні
2. Test файли вже готові в `data/`
3. Iterations: 10-50 для швидкого тесту

### Для повної демонстрації:

1. **Desktop GUI** - показати обидві системи
2. **Web UI** - професійний інтерфейс
3. **API Docs** - показати endpoints
4. **Порівняння** - переваги кожної системи

---

## 🐛 Якщо щось не працює

### Desktop GUI не запускається:

```cmd
python -m tkinter  # Перевірка
```

### Backend connection error:

```cmd
# Перевірити чи працює:
curl http://127.0.0.1:8000/docs
```

### Frontend не компілюється:

```cmd
cd frontend
rm -rf node_modules
npm install
```

### Port 3000 зайнятий:

```cmd
PORT=3001 npm start
```

---

## 📖 Що читати далі?

**Новачкам:**

1. [QUICKSTART_GUI.md](QUICKSTART_GUI.md) - швидкий старт
2. [README_GUI.md](README_GUI.md) - огляд можливостей

**Досвідченим:**

1. [PROJECT_STATUS.md](PROJECT_STATUS.md) - повний статус
2. [README_DRL.md](README_DRL.md) - технічні деталі
3. [GUI_README.md](GUI_README.md) - архітектура GUI

---

## 🎉 Все готово!

Ваш проект **ПОВНІСТЮ ФУНКЦІОНАЛЬНИЙ** та готовий до демонстрації!

**Швидкий старт:**

```cmd
python gui_app.py
```

**Або читайте далі:**
→ [QUICKSTART_GUI.md](QUICKSTART_GUI.md)

---

**Успіхів! 🚀🎓**
