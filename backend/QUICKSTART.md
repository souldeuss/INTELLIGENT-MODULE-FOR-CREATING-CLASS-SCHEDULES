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

## 6. Generate 100-case training dataset

Run from repository root:

```powershell
python backend/dataset_generator.py --dataset-name dataset_100 --count 100 --seed 42 --train-ratio 0.8
```

Output:

- `data/dataset_100/cases/case_001.json` ... `case_100.json`
- `data/dataset_100/dataset_manifest.json`

Use the generated manifest with the train/eval pipeline:

```powershell
python backend/train_eval_pipeline.py --manifest data/dataset_100/dataset_manifest.json --iterations 100
```

One-call preset (generate dataset + train in one command):

```powershell
python backend/dataset_100_preset.py --dataset-name dataset_100 --iterations 100 --seed 42 --train-ratio 0.8
```

Note: in preset mode, `--iterations` is interpreted as total iterations across all train cases.

---

## Troubleshooting

### "uvicorn not found"

Use: `python -m uvicorn app.main:app --reload`

### "torch installation fails"

Use CPU version (lighter): `pip install torch --index-url https://download.pytorch.org/whl/cpu`

### Database errors

Delete `timetabling.db` file and restart server.
