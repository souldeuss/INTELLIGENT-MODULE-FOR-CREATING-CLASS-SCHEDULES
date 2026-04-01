"""Teachers API."""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List

from ..models.database import Teacher
from ..schemas.schemas import TeacherCreate, TeacherResponse, TeacherUpdate
from ..core.database_session import get_db

router = APIRouter()


@router.post("/", response_model=TeacherResponse, status_code=201)
def create_teacher(teacher: TeacherCreate, db: Session = Depends(get_db)):
    existing = db.query(Teacher).filter(Teacher.code == teacher.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Teacher '{teacher.code}' already exists")
    db_teacher = Teacher(**teacher.model_dump())
    db.add(db_teacher)
    db.commit()
    db.refresh(db_teacher)
    return db_teacher


@router.get("/", response_model=List[TeacherResponse])
def list_teachers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Teacher).offset(skip).limit(limit).all()


@router.get("/export/csv")
def export_teachers_csv(db: Session = Depends(get_db)):
    teachers = db.query(Teacher).order_by(Teacher.code.asc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(["Name", "Short Name", "Email", "Phone", "Role", "Designation"])

    for teacher in teachers:
        writer.writerow(
            [
                teacher.full_name,
                teacher.code,
                teacher.email or "",
                "",
                "member",
                teacher.department or "Teacher",
            ]
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"teachers_{timestamp}.csv"
    csv_bytes = ("\ufeff" + buffer.getvalue()).encode("utf-8")

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{teacher_id}", response_model=TeacherResponse)
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return teacher
