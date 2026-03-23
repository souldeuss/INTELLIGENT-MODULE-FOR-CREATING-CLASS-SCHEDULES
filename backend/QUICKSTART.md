# Quick Start Guide - DRL Backend

## 1. Install Dependencies

```powershell
cd backend
pip install -r requirements.txt
```

**Note:** If torch installation is slow/fails, you can install CPU version:

```powershell
pip install torch==2.1.1 --index-url https://download.pytorch.org/whl/cpu
```

## 2. Start Backend Server

Option A - Using batch script:

```powershell
.\start.bat
```

Option B - Manual command:

```powershell
python -m uvicorn app.main:app --reload
```

## 3. Verify Backend

Open browser: http://localhost:8000/docs

You should see FastAPI Swagger documentation.

## 4. Database

SQLite database will be created automatically at `timetabling.db` on first request.

## 5. Test API

In FastAPI docs, try:

1. POST `/api/courses/` - Create a course
2. POST `/api/teachers/` - Create a teacher
3. POST `/api/schedule/generate` - Generate schedule with DRL

---

## Troubleshooting

### "uvicorn not found"

Use: `python -m uvicorn app.main:app --reload`

### "torch installation fails"

Use CPU version (lighter): `pip install torch --index-url https://download.pytorch.org/whl/cpu`

### Database errors

Delete `timetabling.db` file and restart server.
