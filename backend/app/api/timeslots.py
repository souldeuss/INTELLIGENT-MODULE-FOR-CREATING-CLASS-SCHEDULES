"""Timeslots API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..models.database import Timeslot
from ..schemas.schemas import TimeslotCreate, TimeslotResponse
from ..core.database_session import get_db

router = APIRouter()


@router.post("/", response_model=TimeslotResponse, status_code=201)
def create_timeslot(timeslot: TimeslotCreate, db: Session = Depends(get_db)):
    db_timeslot = Timeslot(**timeslot.model_dump())
    db.add(db_timeslot)
    db.commit()
    db.refresh(db_timeslot)
    return db_timeslot


@router.get("/", response_model=List[TimeslotResponse])
def list_timeslots(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Timeslot).offset(skip).limit(limit).all()


@router.get("/{timeslot_id}", response_model=TimeslotResponse)
def get_timeslot(timeslot_id: int, db: Session = Depends(get_db)):
    timeslot = db.query(Timeslot).filter(Timeslot.id == timeslot_id).first()
    if not timeslot:
        raise HTTPException(status_code=404, detail="Timeslot not found")
    return timeslot
