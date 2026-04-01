"""Student Groups API."""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
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


@router.get("/export/csv")
def export_groups_csv(db: Session = Depends(get_db)):
    groups = db.query(StudentGroup).order_by(StudentGroup.code.asc()).all()

    buffer = io.StringIO()
    buffer.write("Group Name,Short Name\n")
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")

    for group in groups:
        writer.writerow([group.code, group.code])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"groups_{timestamp}.csv"
    csv_bytes = ("\ufeff" + buffer.getvalue()).encode("utf-8")

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{group_id}", response_model=StudentGroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group
