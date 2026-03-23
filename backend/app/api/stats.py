"""Statistics and AI API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.database import (
    Course,
    Teacher,
    StudentGroup,
    Classroom,
    Timeslot,
    ScheduledClass,
    ScheduleGeneration,
)
from ..core.database_session import get_db

router = APIRouter()


@router.get("/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Отримати статистику для dashboard."""
    groups_count = db.query(StudentGroup).count()
    teachers_count = db.query(Teacher).count()
    classrooms_count = db.query(Classroom).count()
    courses_count = db.query(Course).count()
    
    # Кількість збережених розкладів (генерацій)
    schedules_count = db.query(ScheduleGeneration).filter(
        ScheduleGeneration.status == "completed"
    ).count()
    
    # Підрахунок активних конфліктів
    scheduled_classes = db.query(ScheduledClass).all()
    active_conflicts = 0
    
    # Групуємо за timeslot
    timeslot_classes = {}
    for sc in scheduled_classes:
        if sc.timeslot_id not in timeslot_classes:
            timeslot_classes[sc.timeslot_id] = []
        timeslot_classes[sc.timeslot_id].append(sc)
    
    for timeslot_id, classes in timeslot_classes.items():
        if len(classes) < 2:
            continue
        
        # Конфлікти викладачів
        teacher_ids = [c.teacher_id for c in classes]
        active_conflicts += len(teacher_ids) - len(set(teacher_ids))
        
        # Конфлікти аудиторій
        room_ids = [c.classroom_id for c in classes]
        active_conflicts += len(room_ids) - len(set(room_ids))
        
        # Конфлікти груп
        group_ids = [c.group_id for c in classes]
        active_conflicts += len(group_ids) - len(set(group_ids))
    
    # Середній score (з останньої генерації)
    last_gen = db.query(ScheduleGeneration).filter(
        ScheduleGeneration.status == "completed"
    ).order_by(ScheduleGeneration.id.desc()).first()
    
    average_score = 0.0
    if last_gen and last_gen.final_score:
        # Нормалізуємо reward до 0-100
        average_score = max(0, min(100, (last_gen.final_score + 100) / 2))
    
    return {
        "groups_count": groups_count,
        "teachers_count": teachers_count,
        "classrooms_count": classrooms_count,
        "courses_count": courses_count,
        "schedules_count": schedules_count,
        "active_conflicts": active_conflicts,
        "average_score": round(average_score, 1),
    }


@router.get("/violations")
def get_constraint_violations(db: Session = Depends(get_db)):
    """Отримати детальну інформацію про порушення обмежень."""
    violations = {
        "hard": {
            "teacher_conflicts": 0,
            "room_conflicts": 0,
            "group_conflicts": 0,
        },
        "soft": {
            "capacity_issues": 0,
            "preference_violations": 0,
        }
    }
    
    scheduled_classes = db.query(ScheduledClass).all()
    
    # Групуємо за timeslot
    timeslot_classes = {}
    for sc in scheduled_classes:
        if sc.timeslot_id not in timeslot_classes:
            timeslot_classes[sc.timeslot_id] = []
        timeslot_classes[sc.timeslot_id].append(sc)
    
    for classes in timeslot_classes.values():
        if len(classes) < 2:
            continue
        
        teacher_ids = [c.teacher_id for c in classes]
        violations["hard"]["teacher_conflicts"] += len(teacher_ids) - len(set(teacher_ids))
        
        room_ids = [c.classroom_id for c in classes]
        violations["hard"]["room_conflicts"] += len(room_ids) - len(set(room_ids))
        
        group_ids = [c.group_id for c in classes]
        violations["hard"]["group_conflicts"] += len(group_ids) - len(set(group_ids))
    
    # Перевірка місткості
    for sc in scheduled_classes:
        group = db.query(StudentGroup).filter(StudentGroup.id == sc.group_id).first()
        classroom = db.query(Classroom).filter(Classroom.id == sc.classroom_id).first()
        if group and classroom and group.students_count > classroom.capacity:
            violations["soft"]["capacity_issues"] += 1
    
    return violations


@router.get("/utilization")
def get_utilization_stats(db: Session = Depends(get_db)):
    """Отримати статистику завантаженості."""
    classrooms = db.query(Classroom).all()
    timeslots = db.query(Timeslot).filter(Timeslot.is_active == True).all()
    total_slots = len(timeslots)
    
    classroom_util = []
    for room in classrooms:
        used = db.query(ScheduledClass).filter(
            ScheduledClass.classroom_id == room.id
        ).count()
        rate = (used / total_slots * 100) if total_slots > 0 else 0
        classroom_util.append({
            "id": room.id,
            "code": room.code,
            "used_slots": used,
            "total_slots": total_slots,
            "utilization_rate": round(rate, 1),
        })
    
    teachers = db.query(Teacher).all()
    teacher_util = []
    for teacher in teachers:
        assigned = db.query(ScheduledClass).filter(
            ScheduledClass.teacher_id == teacher.id
        ).count()
        rate = (assigned / teacher.max_hours_per_week * 100) if teacher.max_hours_per_week > 0 else 0
        teacher_util.append({
            "id": teacher.id,
            "name": teacher.full_name,
            "assigned_hours": assigned,
            "max_hours": teacher.max_hours_per_week,
            "workload_rate": round(rate, 1),
        })
    
    return {
        "classrooms": classroom_util,
        "teachers": teacher_util,
    }


@router.get("/distribution")
def get_distribution_stats(db: Session = Depends(get_db)):
    """Отримати статистику розподілу занять."""
    # Розподіл по днях
    days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця"]
    day_distribution = []
    
    for day_idx, day_name in enumerate(days):
        timeslots = db.query(Timeslot).filter(Timeslot.day_of_week == day_idx).all()
        timeslot_ids = [t.id for t in timeslots]
        count = db.query(ScheduledClass).filter(
            ScheduledClass.timeslot_id.in_(timeslot_ids)
        ).count() if timeslot_ids else 0
        day_distribution.append({
            "day": day_name,
            "day_index": day_idx,
            "classes_count": count,
        })
    
    # Розподіл по парах
    period_distribution = []
    for period in range(1, 7):
        timeslots = db.query(Timeslot).filter(Timeslot.period_number == period).all()
        timeslot_ids = [t.id for t in timeslots]
        count = db.query(ScheduledClass).filter(
            ScheduledClass.timeslot_id.in_(timeslot_ids)
        ).count() if timeslot_ids else 0
        period_distribution.append({
            "period": period,
            "classes_count": count,
        })
    
    return {
        "by_day": day_distribution,
        "by_period": period_distribution,
    }
