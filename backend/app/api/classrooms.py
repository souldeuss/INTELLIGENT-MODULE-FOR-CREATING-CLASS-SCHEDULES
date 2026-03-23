"""Classrooms API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..models.database import Classroom
from ..schemas.schemas import ClassroomCreate, ClassroomResponse, ClassroomUpdate
from ..core.database_session import get_db

router = APIRouter()


@router.post("/", response_model=ClassroomResponse, status_code=201)
def create_classroom(classroom: ClassroomCreate, db: Session = Depends(get_db)):
    existing = db.query(Classroom).filter(Classroom.code == classroom.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Classroom '{classroom.code}' already exists")
    db_classroom = Classroom(**classroom.model_dump())
    db.add(db_classroom)
    db.commit()
    db.refresh(db_classroom)
    return db_classroom


@router.get("/", response_model=List[ClassroomResponse])
def list_classrooms(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Classroom).offset(skip).limit(limit).all()


@router.get("/{classroom_id}", response_model=ClassroomResponse)
def get_classroom(classroom_id: int, db: Session = Depends(get_db)):
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    return classroom
