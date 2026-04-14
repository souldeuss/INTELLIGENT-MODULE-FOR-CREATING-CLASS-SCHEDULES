from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

MODULE_PATH = BACKEND / "app" / "core" / "edulog_adapter.py"
SPEC = importlib.util.spec_from_file_location("edulog_adapter", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {MODULE_PATH}")

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

EduLogAdapter = MODULE.EduLogAdapter


def build_school_data(with_classrooms: bool = True) -> dict:
    payload = {
        "SchoolId": 10,
        "Classes": [
            {"Id": 1, "SchoolId": 10, "Name": "10-A", "TeacherId": 101},
            {"Id": 2, "SchoolId": 10, "Name": "10-B", "TeacherId": 101},
        ],
        "Subjects": [
            {
                "Id": 11,
                "SchoolId": 10,
                "Name": "Math",
                "TeacherId": 101,
                "Difficulty": 3,
                "RequiresSpecialized": False,
            },
            {
                "Id": 12,
                "SchoolId": 10,
                "Name": "Physics",
                "TeacherId": 102,
                "Difficulty": 4,
                "RequiresSpecialized": True,
                "ClassroomType": "lab",
            },
        ],
        "Teachers": [
            {"Id": 101, "SchoolId": 10, "Name": "Ivan", "Surname": "Ivanov", "Patronymic": "I."},
            {"Id": 102, "SchoolId": 10, "Name": "Olga", "Surname": "Petrova", "Patronymic": "P."},
        ],
        "ClassSubjects": [
            {"ClassId": 1, "SubjectId": 11},
            {"ClassId": 1, "SubjectId": 12},
            {"ClassId": 2, "SubjectId": 11},
        ],
        "ScheduleSlots": [
            {
                "Id": 1001,
                "SchoolId": 10,
                "AcademicYearId": 77,
                "DayOfWeek": 1,
                "LessonNumber": 1,
                "ClassId": 1,
                "SubjectId": 11,
                "TeacherId": 101,
                "Room": "A101",
            },
            {
                "Id": 1002,
                "SchoolId": 10,
                "AcademicYearId": 77,
                "DayOfWeek": 1,
                "LessonNumber": 2,
                "ClassId": 1,
                "SubjectId": 11,
                "TeacherId": 101,
                "Room": "A101",
            },
            {
                "Id": 1003,
                "SchoolId": 10,
                "AcademicYearId": 77,
                "DayOfWeek": 2,
                "LessonNumber": 1,
                "ClassId": 1,
                "SubjectId": 12,
                "TeacherId": 102,
                "Room": "Lab1",
            },
            {
                "Id": 1004,
                "SchoolId": 10,
                "AcademicYearId": 77,
                "DayOfWeek": 3,
                "LessonNumber": 1,
                "ClassId": 2,
                "SubjectId": 11,
                "TeacherId": 101,
                "Room": "A102",
            },
        ],
        "Constraints": {"MaxDailyLessons": 6},
    }
    if with_classrooms:
        payload["Classrooms"] = [
            {"Id": 1, "Code": "A101", "Capacity": 30, "Type": "general"},
            {"Id": 2, "Code": "Lab1", "Capacity": 18, "Type": "lab"},
        ]
    return payload


def test_to_scheduler_input_maps_entities_and_indices() -> None:
    adapter = EduLogAdapter()
    scheduler_input = adapter.to_scheduler_input(build_school_data(with_classrooms=True))

    assert {item["id"] for item in scheduler_input["groups"]} == {"cls_1", "cls_2"}
    assert {item["id"] for item in scheduler_input["subjects"]} == {"subj_11", "subj_12"}
    assert {item["id"] for item in scheduler_input["teachers"]} == {"tch_101", "tch_102"}
    assert scheduler_input["constraints"]["max_daily_lessons"] == 6

    first_slot = scheduler_input["existing_schedule"][0]
    assert first_slot["day_index"] == 0
    assert first_slot["slot_index"] == 0


def test_to_scheduler_input_aggregates_lessons_pool_counts() -> None:
    adapter = EduLogAdapter()
    scheduler_input = adapter.to_scheduler_input(build_school_data(with_classrooms=True))

    counts = {
        (item["group"], item["subject"], item["teacher"]): item["count"]
        for item in scheduler_input["lessons_pool"]
    }
    assert counts[("cls_1", "subj_11", "tch_101")] == 2
    assert counts[("cls_1", "subj_12", "tch_102")] == 1
    assert counts[("cls_2", "subj_11", "tch_101")] == 1


def test_to_scheduler_input_generates_virtual_rooms_when_absent() -> None:
    adapter = EduLogAdapter()
    scheduler_input = adapter.to_scheduler_input(build_school_data(with_classrooms=False))

    room_ids = [room["id"] for room in scheduler_input["classrooms"]]
    assert len(room_ids) == 2
    assert all(room_id.startswith("vroom_") for room_id in room_ids)


def test_validate_mapping_returns_empty_for_valid_payload() -> None:
    adapter = EduLogAdapter()
    scheduler_input = adapter.to_scheduler_input(build_school_data(with_classrooms=True))

    errors = adapter.validate_mapping(scheduler_input)
    assert errors == []


def test_validate_mapping_reports_missing_references_and_non_positive_count() -> None:
    adapter = EduLogAdapter()
    scheduler_input = adapter.to_scheduler_input(build_school_data(with_classrooms=True))
    scheduler_input["lessons_pool"][0]["subject"] = "subj_999"
    scheduler_input["lessons_pool"][0]["count"] = 0

    errors = adapter.validate_mapping(scheduler_input)
    assert any("unknown subject" in error for error in errors)
    assert any("non-positive count" in error for error in errors)


def test_validate_mapping_reports_invalid_existing_schedule_ranges() -> None:
    adapter = EduLogAdapter()
    scheduler_input = adapter.to_scheduler_input(build_school_data(with_classrooms=True))
    scheduler_input["existing_schedule"][0]["day_index"] = 5
    scheduler_input["existing_schedule"][0]["slot_index"] = 9
    scheduler_input["constraints"]["max_daily_lessons"] = 8

    errors = adapter.validate_mapping(scheduler_input)
    assert any("invalid day_index" in error for error in errors)
    assert any("exceeds max_daily_lessons" in error for error in errors)


def test_validate_mapping_reports_empty_lessons_pool() -> None:
    adapter = EduLogAdapter()
    scheduler_input = adapter.to_scheduler_input(build_school_data(with_classrooms=True))
    scheduler_input["lessons_pool"] = []

    errors = adapter.validate_mapping(scheduler_input)
    assert any("Missing or empty required section: lessons_pool" in error for error in errors)


def test_from_scheduler_output_maps_back_to_edulog_slots() -> None:
    adapter = EduLogAdapter()
    output = {
        "schedule": [
            {
                "subject": "subj_11",
                "teacher": "tch_101",
                "group": "cls_1",
                "classroom": "room_A101",
                "day_index": 0,
                "slot_index": 1,
                "label": "08:55-09:40",
            }
        ],
        "conflicts": [],
        "warnings": [],
        "statistics": {},
    }

    rows = adapter.from_scheduler_output(output, school_id=10, academic_year_id=77)

    assert len(rows) == 1
    assert rows[0] == {
        "AcademicYearId": 77,
        "ClassId": 1,
        "SubjectId": 11,
        "TeacherId": 101,
        "DayOfWeek": 1,
        "LessonNumber": 2,
        "Room": "A101",
        "SchoolId": 10,
    }


def test_from_scheduler_output_skips_rows_with_malformed_ids() -> None:
    adapter = EduLogAdapter()
    output = {
        "schedule": [
            {
                "subject": "subj_bad",
                "teacher": "tch_101",
                "group": "cls_1",
                "classroom": "room_A101",
                "day_index": 0,
                "slot_index": 0,
                "label": "08:00-08:45",
            },
            {
                "subject": "subj_12",
                "teacher": "tch_102",
                "group": "cls_2",
                "classroom": "vroom_1",
                "day_index": 2,
                "slot_index": 3,
                "label": "10:45-11:30",
            },
        ]
    }

    rows = adapter.from_scheduler_output(output, school_id=10, academic_year_id=77)

    assert len(rows) == 1
    assert rows[0]["ClassId"] == 2
    assert rows[0]["SubjectId"] == 12
    assert rows[0]["TeacherId"] == 102
    assert rows[0]["DayOfWeek"] == 3
    assert rows[0]["LessonNumber"] == 4
    assert rows[0]["Room"] == "vroom_1"
