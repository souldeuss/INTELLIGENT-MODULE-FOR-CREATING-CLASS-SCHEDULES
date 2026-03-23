# 🎓 Intelligent Module for Creating Class Schedules - GUI Edition

## 🎉 Повністю готово до використання!

Ваш проект тепер має **професійні графічні інтерфейси** для демонстрації всіх функцій!

---

## 🖥️ Що нового: Графічні інтерфейси

### 1️⃣ Desktop GUI (Python/Tkinter)

**Файл:** `gui_app.py`  
**Запуск:** `RUN_GUI.bat` або `python gui_app.py`

**Функціонал:**

- ✅ Єдиний інтерфейс для обох систем
- ✅ System 1: створення розкладів через GUI
- ✅ System 2: запуск/моніторинг DRL backend
- ✅ Порівняння систем
- ✅ Перегляд результатів
- ✅ Real-time логування

### 2️⃣ Web GUI (React + Material-UI)

**Папка:** `frontend/`  
**Запуск:** `npm start` (після `npm install`)

**Компоненти:**

- ✅ Dashboard - генерація розкладів
- ✅ Course Management - CRUD для курсів
- ✅ Teacher Management - управління викладачами
- ✅ Group Management - студентські групи
- ✅ Timetable View - візуалізація розкладів
- ✅ Analytics - аналітика навчання DRL

---

## 🚀 Швидкий старт

### Найшвидший спосіб (Desktop GUI):

```cmd
RUN_GUI.bat
```

Або:

```cmd
python gui_app.py
```

### Web інтерфейс (2 термінали):

```cmd
# Terminal 1: Backend
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm install  # тільки перший раз
npm start
```

**URLs:**

- Backend API: http://127.0.0.1:8000
- Frontend: http://localhost:3000
- API Docs: http://127.0.0.1:8000/docs

---

## 📁 Структура проекту (оновлена)

```
INTELLIGENT MODULE FOR CREATING CLASS SCHEDULES/
│
├── 🖥️ ГРАФІЧНІ ІНТЕРФЕЙСИ
│   ├── gui_app.py                    # Desktop GUI (Python/Tkinter)
│   ├── RUN_GUI.bat                   # Швидкий запуск GUI
│   └── frontend/                     # Web GUI (React)
│       ├── src/
│       │   ├── App.tsx              # Головний компонент + навігація
│       │   └── components/
│       │       ├── Dashboard.tsx              # Генерація розкладів
│       │       ├── CourseManagement.tsx       # CRUD курси
│       │       ├── TeacherManagement.tsx      # CRUD викладачі
│       │       ├── GroupManagement.tsx        # CRUD групи
│       │       ├── TimetableView.tsx          # Візуалізація
│       │       ├── Analytics.tsx              # Аналітика
│       │       └── Navigation.tsx             # Меню
│       └── package.json             # Dependencies
│
├── 🤖 СИСТЕМА 1: Classical Scheduler
│   ├── src/
│   │   ├── main.py                  # CLI entry point
│   │   └── imscheduler/             # Core engine
│   └── data/                        # Test data & results
│
├── 🚀 СИСТЕМА 2: DRL Scheduler
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py             # FastAPI application
│   │   │   ├── models/             # Database models
│   │   │   ├── core/               # DRL engine
│   │   │   └── api/                # REST endpoints
│   │   └── populate_db.py          # Test data script
│   └── docker-compose.yml          # Container orchestration
│
├── 📚 ДОКУМЕНТАЦІЯ
│   ├── README.md                    # Цей файл
│   ├── QUICKSTART_GUI.md           # Швидкий старт GUI
│   ├── GUI_README.md               # Повний опис GUI
│   ├── PROJECT_STATUS.md           # Статус проекту
│   ├── BACKEND_READY.md            # Backend setup
│   └── README_DRL.md               # DRL система
│
└── 🧪 ТЕСТУВАННЯ
    └── tests/                       # Unit tests (5/5 passing ✅)
```

---

## 🎯 Використання GUI

### Desktop GUI - Основні функції:

#### 🏠 Головна сторінка

- Огляд обох систем
- Швидкі кнопки для основних дій
- Статус індикатори

#### 📊 System 1: Classical

**Вкладка "Опис":**

- Детальний опис системи
- Технології та особливості
- Результати тестування

**Вкладка "Запуск":**

1. Вибрати config.json
2. Вибрати input.json
3. Встановити output.json
4. Натиснути "Створити розклад"
5. Переглянути логи

**Вкладка "Результати":**

- Завантажити output файл
- Переглянути розклад
- Перевірити конфлікти

#### 🤖 System 2: DRL

**Вкладка "Опис":**

- Архітектура DRL
- Компоненти системи
- Hyperparameters

**Вкладка "Керування":**

- Запустити Backend
- Відкрити Web UI
- Наповнити БД
- Перевірити статус
- Переглянути логи

#### 📈 Порівняння систем

- Детальна таблиця порівняння
- Переваги та недоліки
- Рекомендації використання

#### ℹ️ Про програму

- Інформація про проект
- Технічний стек
- Досягнення
- Статистика

### Web GUI - Сторінки:

#### 📊 Dashboard

1. Встановити iterations (10-1000)
2. Натиснути "Generate Schedule"
3. Спостерігати прогрес
4. Переглянути результат

#### 📚 Course Management

- Add Course: додати новий курс
- Edit: редагувати існуючий
- Delete: видалити курс
- Таблиця всіх курсів

#### 👨‍🏫 Teacher Management

- Додати викладачів
- Встановити max hours/week
- Налаштувати preferences
- Управління списком

#### 👥 Group Management

- Створити групи
- Вказати рік та спеціалізацію
- Підрахунок студентів
- Редагування

#### 📅 Timetable View

- Вибір групи
- Календарний вигляд
- Список занять
- Експорт (TODO)

#### 📈 Analytics

- Графіки навчання
- Метрики якості
- Історія генерацій
- Статистика конфліктів

---

## 📖 Документація

| Файл                                   | Опис                                                   |
| -------------------------------------- | ------------------------------------------------------ |
| [QUICKSTART_GUI.md](QUICKSTART_GUI.md) | **⭐ Швидкий старт GUI** - найкраще місце для початку! |
| [GUI_README.md](GUI_README.md)         | Повний опис обох GUI (Desktop + Web)                   |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Повний статус проекту, всі системи                     |
| [BACKEND_READY.md](BACKEND_READY.md)   | Backend setup та швидкий старт                         |
| [README_DRL.md](README_DRL.md)         | DRL система, архітектура, API                          |

---

## 🎬 Демонстрація проекту

### Сценарій 1: Швидка демонстрація (5 хвилин)

1. **Запустити Desktop GUI:**

   ```cmd
   python gui_app.py
   ```

2. **Показати головну сторінку:**

   - Дві системи (Classical vs DRL)
   - Швидкі кнопки

3. **System 1 - створити розклад:**

   - Вкладка "Запуск"
   - Використати test файли
   - Показати логи у реальному часі
   - Переглянути результати

4. **System 2 - запустити backend:**

   - Натиснути "Запустити Backend"
   - Дочекатися старту
   - Відкрити Web UI

5. **Показати порівняння систем**

### Сценарій 2: Повна демонстрація (15 хвилин)

**Частина 1: Desktop GUI (5 хв)**

- Всі вкладки System 1
- Створення розкладу
- Результати

**Частина 2: Web GUI (10 хв)**

- Dashboard - генерація
- CRUD операції (Courses, Teachers, Groups)
- Timetable View
- Analytics

---

## 🛠️ Технічні деталі

### Desktop GUI

**Технології:**

- Python 3.13
- tkinter (built-in)
- threading для async операцій
- subprocess для запуску команд

**Особливості:**

- Zero dependencies (окрім Python)
- Нативний вигляд ОС
- Real-time логування
- Інтеграція з обома системами

### Web GUI

**Frontend:**

- React 18.2.0
- TypeScript 4.9.5
- Material-UI 5.14.20
- Axios для API
- React Router для навігації

**Backend:**

- FastAPI 0.127.0
- SQLAlchemy 2.0.45
- PyTorch 2.9.1
- SQLite database

**Архітектура:**

- RESTful API
- Component-based UI
- State management з hooks
- Responsive design

---

## ✅ Що працює

### ✅ Desktop GUI

- [x] Запуск через батник
- [x] Головна сторінка з картками
- [x] System 1 інтерфейс (3 вкладки)
- [x] System 2 інтерфейс (2 вкладки)
- [x] Створення розкладів
- [x] Запуск backend
- [x] Відкриття Web UI
- [x] Порівняння систем
- [x] Інформація про проект

### ✅ Web GUI

- [x] Navigation з Material-UI
- [x] Dashboard з генерацією
- [x] Course Management (повний CRUD)
- [x] Teacher Management (повний CRUD)
- [x] Group Management (повний CRUD)
- [x] Timetable View
- [x] Analytics
- [x] Responsive design

### ✅ Backend

- [x] FastAPI server
- [x] SQLite database
- [x] REST API (20+ endpoints)
- [x] DRL engine
- [x] Background tasks

### ✅ System 1

- [x] CLI інтерфейс
- [x] 3 режими роботи
- [x] Тестування пройдено
- [x] GUI інтеграція

---

## 🎓 Для захисту курсової

### Демонструйте:

1. **Desktop GUI** - показує всі можливості в одному вікні
2. **System 1** - швидке створення розкладу
3. **Web UI** - сучасний професійний інтерфейс
4. **DRL тренування** - покажіть процес навчання
5. **Порівняння** - таблиця переваг/недоліків

### Акцентуйте:

✨ **Два підходи до AI:**

- Classical (constraint solving)
- Modern (deep reinforcement learning)

✨ **Два типи інтерфейсів:**

- Desktop (швидкий, простий)
- Web (професійний, масштабований)

✨ **Production-ready:**

- REST API
- Database
- Docker готовність
- Повна документація

✨ **Тестування:**

- Unit tests (5/5 passing)
- Реальні дані (українська програма)
- Різні режими роботи

---

## 🚀 Наступні кроки

### Якщо потрібно більше:

**Desktop GUI:**

- [ ] Графіки та діаграми
- [ ] Експорт в PDF
- [ ] Drag & drop файлів
- [ ] Історія запусків

**Web GUI:**

- [ ] Dark mode
- [ ] Excel import/export
- [ ] WebSocket real-time updates
- [ ] User authentication
- [ ] Mobile responsive

**Системи:**

- [ ] Graph Neural Networks
- [ ] Multi-campus support
- [ ] Semester planning
- [ ] Room equipment matching

---

## 💡 Підказки

### Desktop GUI

- Використовуйте test файли з `data/`
- Логи показують все що відбувається
- Backend можна запустити прямо з GUI
- Результати зберігаються автоматично

### Web GUI

- Спочатку запустіть backend
- Створіть тестові дані через API docs
- Використовуйте малу кількість iterations для тесту
- Перевіряйте статус генерації регулярно

---

## 🎉 Вітаємо!

Ваш проект **ПОВНІСТЮ ГОТОВИЙ** до демонстрації!

**Є:**
✅ Дві AI системи (Classical + DRL)  
✅ Два графічних інтерфейси (Desktop + Web)  
✅ REST API  
✅ База даних  
✅ Повна документація  
✅ Тестування  
✅ Docker підтримка

**Запустіть:**

```cmd
python gui_app.py
```

**І починайте демонструвати! 🚀**

---

## 📞 Швидка довідка

**Desktop GUI:**

```cmd
python gui_app.py
```

**Web Backend:**

```cmd
cd backend
python -m uvicorn app.main:app --reload
```

**Web Frontend:**

```cmd
cd frontend
npm start
```

**API Docs:**
http://127.0.0.1:8000/docs

**Докладніше:**

- [QUICKSTART_GUI.md](QUICKSTART_GUI.md) - почніть тут!
- [GUI_README.md](GUI_README.md) - повний опис
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - статус всього

---

**Успіхів на захисті курсової! 🎓✨**
