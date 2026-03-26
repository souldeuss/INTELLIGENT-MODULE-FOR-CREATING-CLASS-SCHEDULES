"""Базові класи режимів складання розкладу."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..models import LessonRequest, ScheduleState, SlotCandidate, Subject


class ScheduleMode(ABC):
    """Абстрактний режим складання розкладу."""

    def __init__(self, config: Config):
        self.config = config

    @abstractmethod
    def score(self, candidate: SlotCandidate, lesson: LessonRequest, subject: Subject, state: ScheduleState) -> float:
        """Повертає оцінку кандидата (чим більше, тим краще)."""


class DenseMode(ScheduleMode):
    """Максимально щільний режим розкладу."""

    def score(self, candidate: SlotCandidate, lesson: LessonRequest, subject: Subject, state: ScheduleState) -> float:
        day_weight = -candidate.timeslot.day_index * 10
        slot_weight = -candidate.timeslot.slot_index
        load = state.day_load(lesson.group, candidate.timeslot.day_index)
        contiguity_bonus = max(0, 5 - abs(load - candidate.timeslot.slot_index))
        return day_weight + slot_weight + contiguity_bonus


class BalancedMode(ScheduleMode):
    """Збалансований режим з урахуванням відпочинку."""

    def score(self, candidate: SlotCandidate, lesson: LessonRequest, subject: Subject, state: ScheduleState) -> float:
        load = state.day_load(lesson.group, candidate.timeslot.day_index)
        teacher_load = state.teacher_load(lesson.teacher, candidate.timeslot.day_index)
        slot_pref = -abs(candidate.timeslot.slot_index - 2)
        difficulty_bonus = subject.difficulty * 0.5
        balance_penalty = abs(load - teacher_load)
        return 10 + slot_pref + difficulty_bonus - balance_penalty


class AppendMode(ScheduleMode):
    """Режим мінімальних змін, що доповнює існуючий розклад."""

    def score(self, candidate: SlotCandidate, lesson: LessonRequest, subject: Subject, state: ScheduleState) -> float:
        load = state.day_load(lesson.group, candidate.timeslot.day_index)
        penalty = load * 0.5
        # заохочуємо слоти, де група ще не має занять
        empty_bonus = 5 if load == 0 else 0
        return 5 + empty_bonus - penalty - candidate.timeslot.slot_index
