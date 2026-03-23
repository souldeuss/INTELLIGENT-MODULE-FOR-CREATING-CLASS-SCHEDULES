# 🚀 DRL Backend Successfully Running!

## ✅ What's Working Now

1. **Backend Server**: Running on http://127.0.0.1:8000
2. **SQLite Database**: Created successfully with all tables
3. **FastAPI Swagger Docs**: Available at http://127.0.0.1:8000/docs
4. **Dependencies**: All installed successfully

---

## 📝 Next Steps

### Step 1: Populate Database (Manual Method)

Since the auto-reload is interfering with the populate script, you'll need to:

**Option A - Use Swagger UI (Easiest)**

1. Open http://127.0.0.1:8000/docs in your browser
2. Create data using the interactive API:

#### Create a Course:

- Click `POST /api/courses/`
- Click "Try it out"
- Use this JSON:

```json
{
  "code": "CS-101",
  "name": "Основи програмування",
  "credits": 4,
  "hours_per_week": 8,
  "requires_lab": true,
  "preferred_classroom_type": "computer_lab",
  "difficulty": 3
}
```

#### Create a Teacher:

- Click `POST /api/teachers/`
- Use:

```json
{
  "code": "TCH-001",
  "full_name": "Сидоренко Андрій Іванович",
  "email": "sydorenko@university.edu",
  "department": "Комп'ютерні науки",
  "max_hours_per_week": 16,
  "avoid_early_slots": false,
  "avoid_late_slots": false
}
```

#### Create a Student Group:

- Click `POST /api/groups/`
- Use:

```json
{
  "code": "CS-1A",
  "year": 1,
  "students_count": 25,
  "specialization": "Computer Science"
}
```

#### Create a Classroom:

- Click `POST /api/classrooms/`
- Use:

```json
{
  "code": "B-201",
  "building": "B",
  "floor": 2,
  "capacity": 30,
  "classroom_type": "computer_lab",
  "has_projector": true,
  "has_computers": true
}
```

#### Create Timeslots:

- Click `POST /api/timeslots/`
- Create a few timeslots (Monday Period 1-3):

```json
{
  "day_of_week": 0,
  "period_number": 1,
  "start_time": "08:30",
  "end_time": "10:05",
  "is_active": true
}
```

```json
{
  "day_of_week": 0,
  "period_number": 2,
  "start_time": "10:25",
  "end_time": "12:00",
  "is_active": true
}
```

**Option B - Run populate_db.py (Stop server first)**

1. Stop the uvicorn server (Ctrl+C in terminal)
2. Run:

```powershell
python populate_db.py
```

3. Restart server:

```powershell
python -m uvicorn app.main:app --reload
```

---

### Step 2: Test DRL Schedule Generation

Once you have data, generate a schedule:

1. In Swagger UI, find `POST /api/schedule/generate`
2. Click "Try it out"
3. Use:

```json
{
  "iterations": 100
}
```

4. Click "Execute"
5. Copy the `generation_id` from response
6. Check status with `GET /api/schedule/status/{generation_id}`
7. When status is "completed", view schedule with `GET /api/timetable/{group_id}`

---

### Step 3: Test React Frontend (Optional)

```powershell
cd ../frontend
npm install
npm start
```

Frontend will open at http://localhost:3000 and connect to backend.

---

## 🐛 Troubleshooting

### Server stopped?

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

### Database issues?

Delete `timetabling.db` file and restart server to recreate tables.

### DRL training too slow?

Reduce iterations from 1000 to 50-100 for testing.

---

## 📊 What You Have Now

### Initial System (src/imscheduler/)

- ✅ CLI-based constraint solver
- ✅ 3 modes: Dense, Balanced, Append
- ✅ Tested with Ukrainian curriculum
- ✅ All unit tests passing

### DRL System (backend/)

- ✅ FastAPI REST API
- ✅ SQLAlchemy + SQLite database
- ✅ PyTorch Actor-Critic neural network
- ✅ PPO training algorithm
- ✅ Dual-attention mechanism
- ✅ Background task processing
- ⏳ Ready for testing with real data

---

## 🎯 Quick Command Reference

Start backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

API docs:

- http://127.0.0.1:8000/docs (Swagger)
- http://127.0.0.1:8000/redoc (ReDoc)

Database file location:

- `backend/timetabling.db`

---

## 💡 Tips

1. **Small Test First**: Create 2-3 entities of each type before full population
2. **Monitor Training**: DRL training output will show in console
3. **Check Logs**: Server terminal shows all database operations
4. **Start Simple**: Test with 10-50 iterations before scaling to 1000+

---

**Your backend is ready to use! Start by adding some test data via Swagger UI.**
