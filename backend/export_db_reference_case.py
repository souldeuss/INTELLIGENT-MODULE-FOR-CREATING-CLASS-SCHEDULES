"""Export current DB entities to a JSON dataset case for compatibility training.

The exported case follows the schema expected by backend/app/core/json_dataset.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from app.core.database_session import SessionLocal
from app.models.database import Course, Teacher, StudentGroup, Classroom, Timeslot


def _subject_id(course_id: int) -> str:
    return f"subj_{course_id}"


def build_reference_case() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        courses: List[Course] = db.query(Course).order_by(Course.id.asc()).all()
        teachers: List[Teacher] = db.query(Teacher).order_by(Teacher.id.asc()).all()
        groups: List[StudentGroup] = db.query(StudentGroup).order_by(StudentGroup.id.asc()).all()
        classrooms: List[Classroom] = db.query(Classroom).order_by(Classroom.id.asc()).all()
        timeslots: List[Timeslot] = (
            db.query(Timeslot)
            .filter(Timeslot.is_active == True)  # noqa: E712
            .order_by(Timeslot.day_of_week.asc(), Timeslot.period_number.asc())
            .all()
        )

        if not courses or not teachers or not groups or not classrooms or not timeslots:
            raise RuntimeError(
                "DB is missing required entities. Ensure courses/teachers/groups/classrooms/timeslots are populated."
            )

        max_daily_lessons = max(int(ts.period_number) for ts in timeslots)

        subjects: List[Dict[str, Any]] = []
        for course in courses:
            subjects.append(
                {
                    "id": _subject_id(course.id),
                    "name": course.name,
                    "difficulty": int(getattr(course, "difficulty", 1) or 1),
                    "requires_specialized": bool(getattr(course, "requires_lab", False)),
                    "classroom_type": getattr(course, "preferred_classroom_type", None),
                }
            )

        payload_teachers: List[Dict[str, Any]] = []
        for teacher in teachers:
            payload_teachers.append(
                {
                    "id": teacher.code,
                    "name": teacher.full_name,
                    "max_hours_per_week": int(getattr(teacher, "max_hours_per_week", 24) or 24),
                }
            )

        payload_groups: List[Dict[str, Any]] = []
        for group in groups:
            payload_groups.append(
                {
                    "id": group.code,
                    "year": int(getattr(group, "year", 1) or 1),
                    "students_count": int(getattr(group, "students_count", 25) or 25),
                }
            )

        payload_classrooms: List[Dict[str, Any]] = []
        for room in classrooms:
            payload_classrooms.append(
                {
                    "id": room.code,
                    "capacity": int(getattr(room, "capacity", 30) or 30),
                    "type": getattr(room, "classroom_type", "general") or "general",
                }
            )

        lessons_pool: List[Dict[str, Any]] = []
        fallback_teacher = teachers[0].code
        fallback_group = groups[0].code

        for course in courses:
            course_teachers = list(getattr(course, "teachers", []) or [])
            course_groups = list(getattr(course, "groups", []) or [])

            # Keep one lessons_pool entry per DB course to preserve compatible dimensions.
            teacher_code = course_teachers[0].code if course_teachers else fallback_teacher
            group_code = course_groups[0].code if course_groups else fallback_group

            hours = int(getattr(course, "hours_per_week", 2) or 2)
            lessons_pool.append(
                {
                    "subject": _subject_id(course.id),
                    "teacher": teacher_code,
                    "group": group_code,
                    "count": max(1, hours),
                }
            )

        if not lessons_pool:
            raise RuntimeError("No lessons were generated from DB courses")

        return {
            "groups": payload_groups,
            "teachers": payload_teachers,
            "classrooms": payload_classrooms,
            "subjects": subjects,
            "lessons_pool": lessons_pool,
            "constraints": {
                "max_daily_lessons": max_daily_lessons,
            },
        }
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export current DB to JSON reference case")
    parser.add_argument(
        "--output",
        default="data/db_reference_case.json",
        help="Output path (workspace-relative or absolute)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[1]
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = workspace_root / output_path

    payload = build_reference_case()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    print(f"Exported DB reference case: {output_path}")
    print(
        "Counts -> "
        f"subjects={len(payload['subjects'])}, "
        f"teachers={len(payload['teachers'])}, "
        f"groups={len(payload['groups'])}, "
        f"classrooms={len(payload['classrooms'])}, "
        f"lessons_pool={len(payload['lessons_pool'])}, "
        f"max_daily_lessons={payload['constraints']['max_daily_lessons']}"
    )


if __name__ == "__main__":
    main()
