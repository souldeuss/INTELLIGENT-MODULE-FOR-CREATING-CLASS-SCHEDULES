"""FastAPI main application."""
import os

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .api import courses, teachers, groups, classrooms, timeslots, schedule, stats, ai, seed_data, training
from .models.database import Base
from .core.database_session import engine, get_db

# Створення таблиць
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Intelligent Timetabling System",
    description="DRL-based university course scheduling with dual-attention mechanism",
    version="2.0.0",
)

# CORS
default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

extra_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins + extra_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|(?:\d{1,3}\.){3}\d{1,3})(?::\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(courses.router, prefix="/api/courses", tags=["Courses"])
app.include_router(teachers.router, prefix="/api/teachers", tags=["Teachers"])
app.include_router(groups.router, prefix="/api/groups", tags=["Student Groups"])
app.include_router(classrooms.router, prefix="/api/classrooms", tags=["Classrooms"])
app.include_router(timeslots.router, prefix="/api/timeslots", tags=["Timeslots"])
app.include_router(schedule.router, prefix="/api/schedule", tags=["Schedule"])
app.include_router(stats.router, prefix="/api/stats", tags=["Statistics"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI Explainability"])
app.include_router(seed_data.router, prefix="/api/seed", tags=["Data Generation"])
app.include_router(training.router, prefix="/api", tags=["Training Management"])


@app.get("/")
async def root():
    return {"message": "Intelligent Timetabling System API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
