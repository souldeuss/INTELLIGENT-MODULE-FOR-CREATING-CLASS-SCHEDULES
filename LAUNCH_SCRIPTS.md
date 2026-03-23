# 🚀 Скрипти запуску системи

## 📍 Огляд скриптів

| Скрипт                     | Призначення    | Запускає                       |
| -------------------------- | -------------- | ------------------------------ |
| **RUN_FULL_SYSTEM.bat** ⭐ | Повний запуск  | Backend + Web UI (автоматично) |
| **RUN_BACKEND.bat**        | Тільки Backend | FastAPI сервер на порту 8000   |
| **RUN_WEB_UI.bat**         | Тільки Web UI  | React dev server на порту 3000 |
| **RUN_GUI.bat**            | Desktop GUI    | Python tkinter додаток         |

---

## 🌟 RUN_FULL_SYSTEM.bat (РЕКОМЕНДОВАНО)

### Що робить:

1. ✅ Перевіряє Python і Node.js
2. ✅ Перевіряє/встановлює залежності
3. ✅ Створює БД якщо потрібно
4. ✅ Запускає Backend у новому вікні
5. ✅ Запускає Frontend у новому вікні
6. ✅ Автоматично відкриває браузер

### Як використовувати:

```cmd
# Просто подвійний клік або:
RUN_FULL_SYSTEM.bat
```

### Що побачите:

- 2 нових вікна терміналу (Backend і Frontend)
- Через 10 секунд відкриється браузер з Web UI
- Backend API доступний на http://localhost:8000
- Web UI доступний на http://localhost:3000

### Як зупинити:

- Закрийте обидва вікна терміналу
- Або натисніть Ctrl+C у кожному вікні

---

## 🔧 RUN_BACKEND.bat

### Що робить:

1. Перевіряє Python
2. Активує virtualenv якщо існує
3. Перевіряє/встановлює залежності
4. Пропонує створити БД
5. Запускає FastAPI сервер

### Використання:

```cmd
RUN_BACKEND.bat
```

### Endpoints:

- 🌐 API Root: http://127.0.0.1:8000/
- 📚 Swagger Docs: http://127.0.0.1:8000/docs
- 📖 ReDoc: http://127.0.0.1:8000/redoc

### Залежності (встановлюються автоматично):

```
fastapi
uvicorn
sqlalchemy
pydantic
torch
numpy
```

---

## 🌐 RUN_WEB_UI.bat

### Що робить:

1. Перевіряє Node.js
2. Перевіряє/встановлює npm залежності
3. Нагадує запустити Backend
4. Запускає React dev server

### Використання:

```cmd
# Спочатку запустіть Backend:
RUN_BACKEND.bat

# Потім у новому терміналі:
RUN_WEB_UI.bat
```

### Доступ:

- 🌐 Web UI: http://localhost:3000
- Автоматично перезавантажується при змінах коду

### Залежності (встановлюються автоматично):

```
react
react-router-dom
@mui/material
axios
recharts
typescript
```

---

## 🖥️ RUN_GUI.bat

### Що робить:

1. Перевіряє Python
2. Запускає Desktop GUI (tkinter)

### Використання:

```cmd
RUN_GUI.bat
```

### Можливості Desktop GUI:

- 📊 Створення розкладів (System 1)
- 🤖 Управління DRL Backend (System 2)
- 📁 Перегляд результатів
- 📈 Порівняння систем
- ℹ️ Інформація про проект

### Залежності:

- Тільки Python (tkinter вбудований)
- Немає зовнішніх залежностей для GUI

---

## 🛠️ Типові проблеми та рішення

### ❌ "Python не знайдено"

```cmd
# Встановіть Python 3.8+ з:
https://www.python.org/downloads/

# Переконайтеся що Python у PATH
python --version
```

### ❌ "Node.js не знайдено"

```cmd
# Встановіть Node.js LTS з:
https://nodejs.org/

# Перевірте:
node --version
npm --version
```

### ❌ "pip: command not found"

```cmd
# Переконайтеся що pip встановлений:
python -m pip --version

# Або оновіть pip:
python -m pip install --upgrade pip
```

### ❌ "npm ERR! network"

```cmd
# Спробуйте очистити кеш:
npm cache clean --force

# Потім знову:
npm install
```

### ❌ Backend не запускається

```cmd
# Перевірте чи не зайнятий порт 8000:
netstat -ano | findstr :8000

# Або змініть порт у команді:
python -m uvicorn app.main:app --port 8001
```

### ❌ Frontend не запускається

```cmd
# Перевірте чи не зайнятий порт 3000:
netstat -ano | findstr :3000

# Або встановіть інший порт:
set PORT=3001
npm start
```

### ❌ "Module not found"

```cmd
# Backend:
cd backend
pip install -r requirements.txt

# Frontend:
cd frontend
npm install
```

### ❌ База даних не створюється

```cmd
cd backend
python populate_db.py
```

---

## 📋 Перевірочний список перед запуском

### Перший запуск системи:

- [ ] ✅ Python 3.8+ встановлений
- [ ] ✅ Node.js 16+ встановлений
- [ ] ✅ npm працює
- [ ] ✅ Git встановлений (опціонально)

### Для Backend:

- [ ] ✅ `cd backend`
- [ ] ✅ `pip install -r requirements.txt`
- [ ] ✅ `python populate_db.py` (перший раз)

### Для Frontend:

- [ ] ✅ `cd frontend`
- [ ] ✅ `npm install`

### Швидка перевірка:

```cmd
# Перевірка всіх інструментів:
python --version
node --version
npm --version

# Все ОК? Запускайте!
RUN_FULL_SYSTEM.bat
```

---

## 🎯 Рекомендований workflow

### Для демонстрації:

```cmd
1. RUN_FULL_SYSTEM.bat         # Повний стек
2. Відкрити http://localhost:3000
3. Почати роботу з Web UI
```

### Для розробки Backend:

```cmd
1. RUN_BACKEND.bat             # Backend з auto-reload
2. Тестувати API через http://localhost:8000/docs
```

### Для розробки Frontend:

```cmd
1. RUN_BACKEND.bat             # У терміналі 1
2. RUN_WEB_UI.bat              # У терміналі 2
3. Редагувати код у frontend/src/
4. Зміни застосуються автоматично
```

### Для швидкого тестування:

```cmd
1. RUN_GUI.bat                 # Без залежностей Node.js
2. Використати System 1 для генерації
```

---

## 📊 Порівняння скриптів

| Критерій               | FULL_SYSTEM | BACKEND | WEB_UI  | GUI         |
| ---------------------- | ----------- | ------- | ------- | ----------- |
| **Потребує Python**    | ✅          | ✅      | ❌      | ✅          |
| **Потребує Node.js**   | ✅          | ❌      | ✅      | ❌          |
| **Автоматичний setup** | ✅          | ✅      | ✅      | ✅          |
| **Відкриває браузер**  | ✅          | ❌      | ❌      | ❌          |
| **Запускає Backend**   | ✅          | ✅      | ❌      | ❌          |
| **Запускає Frontend**  | ✅          | ❌      | ✅      | ❌          |
| **Desktop інтерфейс**  | ❌          | ❌      | ❌      | ✅          |
| **Web інтерфейс**      | ✅          | ❌      | ✅      | ❌          |
| **Складність**         | Проста      | Середня | Проста  | Найпростіша |
| **Час запуску**        | ~15 сек     | ~5 сек  | ~10 сек | ~2 сек      |

---

## 🎓 Для курсового проекту

### Підготовка до демонстрації:

1. **День перед захистом:**

   ```cmd
   # Переконайтеся що все працює:
   RUN_FULL_SYSTEM.bat
   ```

2. **На захисті:**

   ```cmd
   # Швидкий запуск:
   RUN_FULL_SYSTEM.bat

   # Або якщо немає інтернету/Node.js:
   RUN_GUI.bat
   ```

3. **Для offline демонстрації:**
   ```cmd
   # Desktop GUI не потребує мережі:
   RUN_GUI.bat
   ```

### Що показати:

1. **Desktop GUI** - швидка демонстрація обох систем
2. **Web UI** - професійний інтерфейс CRUD
3. **API Docs** - технічна документація
4. **Код** - архітектура та реалізація

---

## 📞 Підтримка

**Проблеми зі скриптами?**

1. Перевірте [QUICKSTART_GUI.md](QUICKSTART_GUI.md)
2. Подивіться [PROJECT_STATUS.md](PROJECT_STATUS.md)
3. Читайте помилки у терміналі уважно

**Все працює?** ✅

Переходьте до [START_HERE.md](START_HERE.md) для повного огляду проекту!

---

## ✨ Підсумок

- ⚡ **RUN_FULL_SYSTEM.bat** - для повного запуску системи
- 🔧 **RUN_BACKEND.bat** - для розробки Backend
- 🌐 **RUN_WEB_UI.bat** - для розробки Frontend
- 🖥️ **RUN_GUI.bat** - для швидкої демонстрації

**Всі скрипти автоматично налаштовують середовище!**

**Успіхів! 🚀**
