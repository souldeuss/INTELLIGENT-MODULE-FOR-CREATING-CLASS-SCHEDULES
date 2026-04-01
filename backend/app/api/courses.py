"""CRUD операції для Courses."""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List

from ..models.database import Course
from ..schemas.schemas import CourseCreate, CourseResponse, CourseUpdate
from ..core.database_session import get_db

router = APIRouter()


@router.post("/", response_model=CourseResponse, status_code=201)
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    """Створити новий курс."""
    # Перевірка унікальності коду
    existing = db.query(Course).filter(Course.code == course.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Course with code '{course.code}' already exists")

    db_course = Course(**course.model_dump())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course


@router.get("/", response_model=List[CourseResponse])
def list_courses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Отримати список курсів."""
    courses = db.query(Course).offset(skip).limit(limit).all()
    return courses


@router.get("/export/csv")
def export_courses_csv(db: Session = Depends(get_db)):
    """Експортувати курси в CSV (Subject Name, Short Name)."""
    courses = db.query(Course).order_by(Course.code.asc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(["Subject Name", "Short Name"])

    for course in courses:
        writer.writerow([course.name, course.code or ""])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"courses_{timestamp}.csv"
    csv_bytes = ("\ufeff" + buffer.getvalue()).encode("utf-8")

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, db: Session = Depends(get_db)):
    """Отримати курс за ID."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(course_id: int, course_update: CourseUpdate, db: Session = Depends(get_db)):
    """Оновити курс."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    for key, value in course_update.model_dump(exclude_unset=True).items():
        setattr(course, key, value)

    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db)):
    """Видалити курс."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    db.delete(course)
    db.commit()
    return None
