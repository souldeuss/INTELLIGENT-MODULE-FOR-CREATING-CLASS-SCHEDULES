"""Вирішувач обмежень для генерації розкладу."""
from __future__ import annotations

from typing import Dict, List, Optional

from .config import Config
from .models import Classroom, ConstraintContext, LessonRequest, ScheduledLesson, SlotCandidate, Subject, TimeSlot

SPECIALIZED_KEYWORDS: Dict[str, str] = {
    "біолог": "biology_lab",
    "biology": "biology_lab",
    "хім": "chemistry_lab",
    "chem": "chemistry_lab",
    "фізик": "physics_lab",
    "phys": "physics_lab",
    "інформ": "computer_lab",
    "comp": "computer_lab",
    "фізк": "gym",
    "sport": "gym",
}


class ConstraintSolver:
    """Клас, що інкапсулює перевірку обмежень."""

    def __init__(self, config: Config, context: ConstraintContext):
        self.config = config
        self.context = context

    # --- Перевірки конфліктів ---
    def check_teacher_conflict(self, lesson: LessonRequest, timeslot: TimeSlot, assigned: List[ScheduledLesson]) -> bool:
        for existing in assigned:
            if existing.teacher == lesson.teacher and self._is_same_slot(existing, timeslot):
                return True
        return False

    def check_group_conflict(self, lesson: LessonRequest, timeslot: TimeSlot, assigned: List[ScheduledLesson]) -> bool:
        for existing in assigned:
            if existing.group == lesson.group and self._is_same_slot(existing, timeslot):
                return True
        return False

    def check_classroom_conflict(
        self, classroom_id: str, timeslot: TimeSlot, assigned: List[ScheduledLesson]
    ) -> bool:
        for existing in assigned:
            if existing.classroom == classroom_id and self._is_same_slot(existing, timeslot):
                return True
        return False

    def minimize_duplicates(self, subject: Subject, lesson: LessonRequest, day_count: int, state) -> bool:
        """Перевіряє, чи не перевищено ліміт повторів предмету за день."""
        if not self.config.allow_duplicates:
            return day_count == 0
        return day_count < self.config.max_duplicates_per_day

    # --- Пошук можливих аудиторій ---
    def assign_specialized_classrooms(self, subject: Subject) -> List[Classroom]:
        required_type = self._required_classroom_type(subject)
        if not required_type:
            return list(self.context.classrooms.values())
        return [room for room in self.context.classrooms.values() if room.type == required_type]

    # --- Допоміжні методи ---
    def build_candidate(
        self,
        subject: Subject,
        lesson: LessonRequest,
        timeslot: TimeSlot,
        state,
    ) -> List[SlotCandidate]:
        candidates: List[SlotCandidate] = []
        classrooms = self.assign_specialized_classrooms(subject)
        if not classrooms:
            classrooms = list(self.context.classrooms.values())
        for room in classrooms:
            if self.check_classroom_conflict(room.id, timeslot, state.assigned):
                continue
            candidates.append(SlotCandidate(timeslot=timeslot, classroom=room))
        return candidates

    def _required_classroom_type(self, subject: Subject) -> Optional[str]:
        if not self.config.use_specialized_classrooms:
            return None
        if subject.id in self.context.specialized_map:
            return self.context.specialized_map[subject.id]
        if subject.requires_specialized:
            return SUBJECT_SPECIALIZATION_MAP.get(subject.id) or SUBJECT_SPECIALIZATION_MAP.get(subject.name.lower())
        lowered = subject.id.lower()
        for keyword, room_type in SPECIALIZED_KEYWORDS.items():
            if keyword in lowered or keyword in subject.name.lower():
                return room_type
        return None

    @staticmethod
    def _is_same_slot(lesson: ScheduledLesson, timeslot: TimeSlot) -> bool:
        return (
            lesson.timeslot.day_index == timeslot.day_index
            and lesson.timeslot.slot_index == timeslot.slot_index
        )


SUBJECT_SPECIALIZATION_MAP: Dict[str, str] = {
    "biology": "biology_lab",
    "chemistry": "chemistry_lab",
    "physics": "physics_lab",
    "informatics": "computer_lab",
    "physical_education": "gym",
}
