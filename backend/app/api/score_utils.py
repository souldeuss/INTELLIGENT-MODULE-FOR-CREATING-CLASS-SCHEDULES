"""Shared schedule scoring utilities."""

from __future__ import annotations

from datetime import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.database import Classroom, ScheduledClass, StudentGroup, Timeslot


def _time_to_minutes(value: Optional[time]) -> Optional[int]:
    if value is None:
        return None
    return value.hour * 60 + value.minute


def calculate_schedule_score(db: Session, scheduled_classes: List[ScheduledClass]) -> Dict[str, Any]:
    """Calculate 0-100 schedule quality score and violation counters."""
    if not scheduled_classes:
        return {
            "overall": 0.0,
            "teacher_conflicts": 100.0,
            "room_conflicts": 100.0,
            "group_conflicts": 100.0,
            "gap_penalty": 100.0,
            "distribution": 100.0,
            "occupancy_rate": 0.0,
            "occupancy_score": 0.0,
            "hard_violations": 0,
            "soft_violations": 0,
            "details": "Розклад порожній",
        }

    total_classes = len(scheduled_classes)

    timeslot_classes: Dict[int, List[ScheduledClass]] = {}
    for scheduled_class in scheduled_classes:
        timeslot_classes.setdefault(scheduled_class.timeslot_id, []).append(scheduled_class)

    teacher_conflicts = 0
    room_conflicts = 0
    group_conflicts = 0
    for classes in timeslot_classes.values():
        if len(classes) < 2:
            continue

        teacher_ids = [c.teacher_id for c in classes]
        room_ids = [c.classroom_id for c in classes]
        group_ids = [c.group_id for c in classes]

        teacher_conflicts += len(teacher_ids) - len(set(teacher_ids))
        room_conflicts += len(room_ids) - len(set(room_ids))
        group_conflicts += len(group_ids) - len(set(group_ids))

    group_ids = {item.group_id for item in scheduled_classes}
    classroom_ids = {item.classroom_id for item in scheduled_classes}
    timeslot_ids = {item.timeslot_id for item in scheduled_classes}

    groups = db.query(StudentGroup).filter(StudentGroup.id.in_(group_ids)).all() if group_ids else []
    classrooms = db.query(Classroom).filter(Classroom.id.in_(classroom_ids)).all() if classroom_ids else []
    timeslots = db.query(Timeslot).filter(Timeslot.id.in_(timeslot_ids)).all() if timeslot_ids else []

    group_map = {item.id: item for item in groups}
    classroom_map = {item.id: item for item in classrooms}
    timeslot_map = {item.id: item for item in timeslots}

    capacity_issues = 0
    day_distribution = [0] * 5
    occupied_minutes = 0
    first_start_minutes: Optional[int] = None
    last_end_minutes: Optional[int] = None

    for scheduled_class in scheduled_classes:
        group = group_map.get(scheduled_class.group_id)
        classroom = classroom_map.get(scheduled_class.classroom_id)
        timeslot = timeslot_map.get(scheduled_class.timeslot_id)

        if group and classroom and group.students_count > classroom.capacity:
            capacity_issues += 1

        if not timeslot:
            continue

        if 0 <= timeslot.day_of_week < 5:
            day_distribution[timeslot.day_of_week] += 1

        start_minutes = _time_to_minutes(timeslot.start_time)
        end_minutes = _time_to_minutes(timeslot.end_time)
        if start_minutes is None or end_minutes is None or end_minutes <= start_minutes:
            continue

        occupied_minutes += end_minutes - start_minutes
        first_start_minutes = (
            start_minutes
            if first_start_minutes is None
            else min(first_start_minutes, start_minutes)
        )
        last_end_minutes = (
            end_minutes if last_end_minutes is None else max(last_end_minutes, end_minutes)
        )

    span_minutes = 0
    if first_start_minutes is not None and last_end_minutes is not None:
        span_minutes = max(0, last_end_minutes - first_start_minutes)

    occupancy_rate = (occupied_minutes / span_minutes) if span_minutes > 0 else 0.0
    occupancy_rate = max(0.0, min(1.0, occupancy_rate))
    occupancy_score = occupancy_rate * 100

    avg_per_day = total_classes / 5
    distribution_variance = sum((day_count - avg_per_day) ** 2 for day_count in day_distribution) / 5
    max_variance = (total_classes ** 2) / 5
    distribution_score = (
        100 * (1 - min(distribution_variance / max_variance, 1)) if max_variance > 0 else 100
    )

    teacher_score = max(0, 100 - (teacher_conflicts * 20))
    room_score = max(0, 100 - (room_conflicts * 20))
    group_score = max(0, 100 - (group_conflicts * 20))
    gap_score = max(0, 100 - (capacity_issues * 10))

    # Preserve previous balance while allocating 10% weight to occupancy.
    overall = (
        teacher_score * 0.225
        + room_score * 0.225
        + group_score * 0.225
        + gap_score * 0.135
        + distribution_score * 0.09
        + occupancy_score * 0.10
    )

    return {
        "overall": round(overall, 1),
        "teacher_conflicts": round(teacher_score, 1),
        "room_conflicts": round(room_score, 1),
        "group_conflicts": round(group_score, 1),
        "gap_penalty": round(gap_score, 1),
        "distribution": round(distribution_score, 1),
        "occupancy_rate": round(occupancy_rate, 4),
        "occupancy_score": round(occupancy_score, 1),
        "hard_violations": int(teacher_conflicts + room_conflicts + group_conflicts),
        "soft_violations": int(capacity_issues),
        "details": {
            "total_classes": total_classes,
            "hard_violations": int(teacher_conflicts + room_conflicts + group_conflicts),
            "soft_violations": int(capacity_issues),
            "occupied_minutes": int(occupied_minutes),
            "span_minutes": int(span_minutes),
        },
    }
