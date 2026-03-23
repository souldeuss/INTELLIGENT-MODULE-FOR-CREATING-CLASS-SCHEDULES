# Intelligent University Timetabling System

Proof-of-Concept веб-застосунку з Deep Reinforcement Learning для автоматичної генерації розкладів занять у ВНЗ.

## Архітектура

### Backend (FastAPI + PostgreSQL)

- **DRL Engine**: Actor-Critic модель з dual-attention механізмом
- **API**: REST endpoints для CRUD операцій та генерації розкладу
- **Database**: PostgreSQL з моделями Course, Teacher, Group, Classroom, Timeslot

### Frontend (React + TypeScript)

- **Admin Panel**: Завантаження даних, управління обмеженнями, генерація розкладу
- **Interactive Grid**: Drag-and-drop інтерфейс з FullCalendar
- **Analytics**: D3.js графіки використання ресурсів

### AI Features

- **Dual-Attention Mechanism**: Часово-ресурсні + семантичні зв'язки
- **Hybrid Optimizer**: DRL (PPO) + Local Search
- **Conflict Detection**: Real-time валідація при ручних змінах

## Структура проекту

```
backend/
  app/
    api/              # FastAPI routes
    core/             # DRL engine
    models/           # SQLAlchemy ORM
    schemas/          # Pydantic models
    services/         # Business logic
  tests/
  requirements.txt
  Dockerfile

frontend/
  src/
    components/       # React components
    services/         # API client
    store/            # State management
  package.json
  Dockerfile

docker-compose.yml
```

## Швидкий старт

### Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm start
```

### Docker

```bash
docker-compose up --build
```

## API Endpoints

- `POST /api/courses` - Створити курс
- `POST /api/teachers` - Додати викладача
- `POST /api/generate` - Згенерувати розклад (DRL)
- `GET /api/timetable/{group_id}` - Отримати розклад групи
- `POST /api/upload` - Завантажити CSV/Excel

## Технології

**Backend**: FastAPI, PyTorch, SQLAlchemy, PostgreSQL, Redis  
**Frontend**: React, TypeScript, Material-UI, FullCalendar, D3.js  
**ML**: Actor-Critic (PPO), NetworkX, PyTorch Geometric  
**DevOps**: Docker, Docker Compose
