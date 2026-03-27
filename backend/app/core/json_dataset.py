"""Utilities to build DRL training cases from JSON timetable datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import time, timedelta, datetime
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class JsonCourse:
    id: int
    code: str
    name: str
    credits: int
    hours_per_week: int
    requires_lab: bool
    preferred_classroom_type: str | None
    difficulty: int


@dataclass
class JsonTeacher:
    id: int
    code: str
    full_name: str
    max_hours_per_week: int = 24


@dataclass
class JsonGroup:
    id: int
    code: str
    year: int
    students_count: int


@dataclass
class JsonClassroom:
    id: int
    code: str
    capacity: int
    classroom_type: str


@dataclass
class JsonTimeslot:
    id: int
    day_of_week: int
    period_number: int
    start_time: time
    end_time: time
    is_active: bool = True


@dataclass
class DatasetCase:
    source_file: str
    courses: List[JsonCourse]
    teachers: List[JsonTeacher]
    groups: List[JsonGroup]
    classrooms: List[JsonClassroom]
    timeslots: List[JsonTimeslot]
    course_teacher_map: Dict[int, List[int]]
    course_group_map: Dict[int, List[int]]


def _parse_time(raw: str) -> time:
    return datetime.strptime(raw, "%H:%M").time()


def _build_timeslots(periods_per_day: int) -> List[JsonTimeslot]:
    slots: List[JsonTimeslot] = []
    slot_id = 1
    start_dt = datetime.strptime("08:30", "%H:%M")

    for day in range(5):
        current = start_dt
        for period in range(1, periods_per_day + 1):
            end_dt = current + timedelta(minutes=80)
            slots.append(
                JsonTimeslot(
                    id=slot_id,
                    day_of_week=day,
                    period_number=period,
                    start_time=current.time(),
                    end_time=end_dt.time(),
                )
            )
            slot_id += 1
            current = end_dt + timedelta(minutes=10)

    return slots


def validate_case_payload(payload: Dict) -> List[str]:
    errors: List[str] = []

    required = ["groups", "teachers", "classrooms", "lessons_pool", "subjects"]
    for field in required:
        if field not in payload:
            errors.append(f"Missing required field: {field}")

    if not isinstance(payload.get("lessons_pool", []), list) or not payload.get("lessons_pool"):
        errors.append("lessons_pool must be a non-empty list")

    return errors


def load_dataset_case(dataset_path: str) -> DatasetCase:
    """Load a single JSON dataset into in-memory objects for environment/trainer."""
    path = Path(dataset_path)
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    errors = validate_case_payload(payload)
    if errors:
        raise ValueError(f"Invalid dataset {path}: {'; '.join(errors)}")

    subjects = {item["id"]: item for item in payload.get("subjects", [])}
    teacher_index: Dict[str, JsonTeacher] = {}
    teachers: List[JsonTeacher] = []

    for idx, item in enumerate(payload.get("teachers", []), start=1):
        teacher = JsonTeacher(
            id=idx,
            code=item["id"],
            full_name=item.get("name", item["id"]),
        )
        teachers.append(teacher)
        teacher_index[item["id"]] = teacher

    group_index: Dict[str, JsonGroup] = {}
    groups: List[JsonGroup] = []
    for idx, item in enumerate(payload.get("groups", []), start=1):
        group = JsonGroup(
            id=idx,
            code=item["id"],
            year=int(item.get("year", 1)),
            students_count=int(item.get("students_count", 25)),
        )
        groups.append(group)
        group_index[item["id"]] = group

    classrooms: List[JsonClassroom] = []
    for idx, item in enumerate(payload.get("classrooms", []), start=1):
        classrooms.append(
            JsonClassroom(
                id=idx,
                code=item["id"],
                capacity=int(item.get("capacity", 30)),
                classroom_type=item.get("type", "general"),
            )
        )

    periods_per_day = int(payload.get("constraints", {}).get("max_daily_lessons", 6))
    timeslots = _build_timeslots(periods_per_day=max(1, periods_per_day))

    courses: List[JsonCourse] = []
    course_teacher_map: Dict[int, List[int]] = {}
    course_group_map: Dict[int, List[int]] = {}

    for idx, lesson in enumerate(payload.get("lessons_pool", []), start=1):
        subject_id = lesson["subject"]
        teacher_code = lesson["teacher"]
        group_code = lesson["group"]

        if subject_id not in subjects:
            raise ValueError(f"Unknown subject id '{subject_id}' in lessons_pool")
        if teacher_code not in teacher_index:
            raise ValueError(f"Unknown teacher id '{teacher_code}' in lessons_pool")
        if group_code not in group_index:
            raise ValueError(f"Unknown group id '{group_code}' in lessons_pool")

        subject = subjects[subject_id]
        teacher = teacher_index[teacher_code]
        group = group_index[group_code]

        lesson_count = int(lesson.get("count", 1))
        if lesson_count <= 0:
            raise ValueError(f"Invalid lesson count={lesson_count} for subject={subject_id}")

        course = JsonCourse(
            id=idx,
            code=f"{subject_id}_{group.code}_{idx}",
            name=subject.get("name", subject_id),
            credits=max(1, lesson_count // 2),
            hours_per_week=lesson_count,
            requires_lab=bool(subject.get("requires_specialized", False)),
            preferred_classroom_type=subject.get("classroom_type"),
            difficulty=int(subject.get("difficulty", 1)),
        )
        courses.append(course)
        course_teacher_map[course.id] = [teacher.id]
        course_group_map[course.id] = [group.id]

    return DatasetCase(
        source_file=str(path),
        courses=courses,
        teachers=teachers,
        groups=groups,
        classrooms=classrooms,
        timeslots=timeslots,
        course_teacher_map=course_teacher_map,
        course_group_map=course_group_map,
    )
