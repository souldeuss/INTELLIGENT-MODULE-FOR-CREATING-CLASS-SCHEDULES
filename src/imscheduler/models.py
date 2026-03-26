"""Моделі даних для генератора розкладу."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Group:
    id: str
    students_count: int = 0


@dataclass
class Subject:
    id: str
    name: str
    requires_specialized: bool = False
    preferred_period: Optional[str] = None  # morning/midday/evening
    difficulty: int = 1


@dataclass
class Teacher:
    id: str
    name: str
    subjects: List[str] = field(default_factory=list)
    preferences: Dict[str, List[int]] = field(default_factory=dict)


@dataclass
class Classroom:
    id: str
    capacity: int
    type: str = "general"


@dataclass
class LessonRequest:
    subject: str
    teacher: str
    group: str
    count: int


@dataclass
class ExistingLesson:
    subject: str
    teacher: str
    group: str
    classroom: str
    day_index: int
    slot_index: int


@dataclass
class TimeSlotTemplate:
    """Описує часовий слот в межах дня."""

    index: int
    label: str
    start: _dt.time
    end: _dt.time

    @staticmethod
    def parse(index: int, descriptor: str) -> "TimeSlotTemplate":
        start_str, end_str = descriptor.split("-")
        start_hour, start_minute = map(int, start_str.split(":"))
        end_hour, end_minute = map(int, end_str.split(":"))
        return TimeSlotTemplate(
            index=index,
            label=descriptor,
            start=_dt.time(start_hour, start_minute),
            end=_dt.time(end_hour, end_minute),
        )


@dataclass
class TimeSlot:
    day_index: int
    slot_template: TimeSlotTemplate

    @property
    def slot_index(self) -> int:
        return self.slot_template.index

    @property
    def label(self) -> str:
        return f"day{self.day_index}:{self.slot_template.label}"


@dataclass
class ScheduledLesson:
    subject: str
    teacher: str
    group: str
    classroom: str
    timeslot: TimeSlot


@dataclass
class ScheduleStatistics:
    """Збирає статистику для сформованого розкладу."""

    lessons_per_group: Dict[str, int] = field(default_factory=dict)
    lessons_per_teacher: Dict[str, int] = field(default_factory=dict)
    classroom_usage: Dict[str, int] = field(default_factory=dict)
    subject_distribution: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def register(self, lesson: ScheduledLesson) -> None:
        self.lessons_per_group[lesson.group] = self.lessons_per_group.get(lesson.group, 0) + 1
        self.lessons_per_teacher[lesson.teacher] = self.lessons_per_teacher.get(lesson.teacher, 0) + 1
        self.classroom_usage[lesson.classroom] = self.classroom_usage.get(lesson.classroom, 0) + 1
        self.subject_distribution.setdefault(lesson.subject, {})
        key = f"day{lesson.timeslot.day_index}"
        self.subject_distribution[lesson.subject][key] = (
            self.subject_distribution[lesson.subject].get(key, 0) + 1
        )


@dataclass
class ScheduleResults:
    schedule: List[ScheduledLesson] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    statistics: ScheduleStatistics = field(default_factory=ScheduleStatistics)

    def to_dict(self) -> Dict[str, object]:
        return {
            "schedule": [
                {
                    "subject": lesson.subject,
                    "teacher": lesson.teacher,
                    "group": lesson.group,
                    "classroom": lesson.classroom,
                    "day_index": lesson.timeslot.day_index,
                    "slot_index": lesson.timeslot.slot_index,
                    "label": lesson.timeslot.slot_template.label,
                }
                for lesson in self.schedule
            ],
            "conflicts": self.conflicts,
            "warnings": self.warnings,
            "statistics": {
                "lessons_per_group": self.statistics.lessons_per_group,
                "lessons_per_teacher": self.statistics.lessons_per_teacher,
                "classroom_usage": self.statistics.classroom_usage,
                "subject_distribution": self.statistics.subject_distribution,
            },
        }


@dataclass
class SlotCandidate:
    """Можливий варіант розміщення уроку."""

    timeslot: TimeSlot
    classroom: Classroom
    score: float = 0.0


@dataclass
class ConstraintContext:
    groups: Dict[str, Group]
    subjects: Dict[str, Subject]
    teachers: Dict[str, Teacher]
    classrooms: Dict[str, Classroom]
    existing_schedule: List[ExistingLesson] = field(default_factory=list)
    specialized_map: Dict[str, str] = field(default_factory=dict)


@dataclass
class ScheduleState:
    """Поточний стан під час генерації."""

    assigned: List[ScheduledLesson] = field(default_factory=list)
    group_day_load: Dict[Tuple[str, int], int] = field(default_factory=dict)
    group_day_subjects: Dict[Tuple[str, int, str], int] = field(default_factory=dict)
    teacher_day_load: Dict[Tuple[str, int], int] = field(default_factory=dict)
    gaps_counter: Dict[Tuple[str, int], int] = field(default_factory=dict)
    group_day_slots: Dict[Tuple[str, int], List[int]] = field(default_factory=dict)

    def register(self, lesson: ScheduledLesson) -> None:
        key_group = (lesson.group, lesson.timeslot.day_index)
        key_teacher = (lesson.teacher, lesson.timeslot.day_index)
        key_subject = (lesson.group, lesson.timeslot.day_index, lesson.subject)
        self.group_day_load[key_group] = self.group_day_load.get(key_group, 0) + 1
        self.teacher_day_load[key_teacher] = self.teacher_day_load.get(key_teacher, 0) + 1
        self.group_day_subjects[key_subject] = self.group_day_subjects.get(key_subject, 0) + 1
        slots = self.group_day_slots.setdefault(key_group, [])
        slots.append(lesson.timeslot.slot_index)

    def count_subject(self, group: str, day_index: int, subject: str) -> int:
        return self.group_day_subjects.get((group, day_index, subject), 0)

    def day_load(self, group: str, day_index: int) -> int:
        return self.group_day_load.get((group, day_index), 0)

    def teacher_load(self, teacher: str, day_index: int) -> int:
        return self.teacher_day_load.get((teacher, day_index), 0)

    def slots_for_day(self, group: str, day_index: int) -> List[int]:
        return self.group_day_slots.get((group, day_index), [])
