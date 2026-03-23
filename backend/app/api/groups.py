"""Student Groups API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..models.database import StudentGroup
from ..schemas.schemas import StudentGroupCreate, StudentGroupResponse, StudentGroupUpdate
from ..core.database_session import get_db

router = APIRouter()


@router.post("/", response_model=StudentGroupResponse, status_code=201)
def create_group(group: StudentGroupCreate, db: Session = Depends(get_db)):
    existing = db.query(StudentGroup).filter(StudentGroup.code == group.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Group '{group.code}' already exists")
    db_group = StudentGroup(**group.model_dump())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group


@router.get("/", response_model=List[StudentGroupResponse])
def list_groups(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(StudentGroup).offset(skip).limit(limit).all()


@router.get("/{group_id}", response_model=StudentGroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group
