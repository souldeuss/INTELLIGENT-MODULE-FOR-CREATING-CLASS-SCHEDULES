"""Основний генератор розкладу."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config
from .logger import get_logger
from .modes.base import AppendMode, BalancedMode, DenseMode, ScheduleMode
from .models import (
    Classroom,
    ConstraintContext,
    ExistingLesson,
    Group,
    LessonRequest,
    ScheduleResults,
    ScheduleState,
    ScheduledLesson,
    SlotCandidate,
    Subject,
    Teacher,
    TimeSlot,
    TimeSlotTemplate,
)
from .solver import ConstraintSolver
from .validator import Validator

WORK_DAYS_PER_WEEK = 5


class ScheduleGenerator:
    """Вищорівневий фасад для генерації розкладу."""

    def __init__(self, config_path: Optional[Path] = None, data_path: Optional[Path] = None):
        self.config_path = Path(config_path) if config_path else None
        self.data_path = Path(data_path) if data_path else None
        self.config: Optional[Config] = None
        self.raw_data: Optional[Dict] = None
        self.context: Optional[ConstraintContext] = None
        self.timeslots: List[TimeSlot] = []
        self.slot_templates: Dict[int, TimeSlotTemplate] = {}
        self.context_data: Dict[str, List[LessonRequest]] = {}
        self.logger = get_logger()
        self.validator = Validator()

    # --- Публічні методи ---
    def load_config(self, path: Optional[Path] = None) -> Config:
        target = Path(path) if path else self.config_path
        if not target:
            raise ValueError("Шлях до config.json не вказано")
        with target.open("r", encoding="utf-8") as handler:
            data = json.load(handler)
        self.config = Config.from_dict(data)
        self.logger.info("Конфігурацію завантажено (%s режим)", self.config.mode)
        return self.config

    def load_data(self, path: Optional[Path] = None) -> Dict:
        target = Path(path) if path else self.data_path
        if not target:
            raise ValueError("Шлях до input.json не вказано")
        with target.open("r", encoding="utf-8") as handler:
            data = json.load(handler)
        return self.set_data(data)

    def set_data(self, data: Dict) -> Dict:
        problems = self.validator.validate_input(data)
        if problems:
            raise ValueError("Помилка вхідних даних: " + "; ".join(problems))
        self.raw_data = data
        self.logger.info("Вхідні дані завантажено: %s груп, %s уроків", len(data["groups"]), len(data["lessons_pool"]))
        return data

    def generate_schedule(self) -> ScheduleResults:
        if not self.config:
            raise RuntimeError("Конфігурацію не завантажено")
        if not self.raw_data:
            raise RuntimeError("Вхідні дані не завантажено")
        self._prepare_timeslots()
        self.context = self._build_context()
        solver = ConstraintSolver(self.config, self.context)
        mode = self._resolve_mode()
        state = ScheduleState()
        results = ScheduleResults()
        self._inject_existing_schedule(state, results)
        subjects = self.context.subjects
        for request in self.context_data["lesson_requests"]:
            subject = subjects.get(request.subject)
            if not subject:
                results.conflicts.append(f"Невідомий предмет {request.subject}")
                continue
            self._place_lesson(request, subject, solver, mode, state, results)
        results.warnings.extend(self.validator.validate_schedule(results))
        return results

    def save_schedule(self, results: ScheduleResults, path: Path) -> None:
        payload = self.validator.generate_report(results)
        with Path(path).open("w", encoding="utf-8") as handler:
            json.dump(payload, handler, ensure_ascii=False, indent=2)
        self.logger.info("Розклад збережено у %s", path)

    # --- Допоміжні методи ---
    def _prepare_timeslots(self) -> None:
        if not self.config.time_slots:
            raise ValueError("У config.json потрібно вказати 'time_slots'")
        self.slot_templates.clear()
        for idx, slot in enumerate(self.config.time_slots):
            template = TimeSlotTemplate.parse(idx, slot)
            self.slot_templates[idx] = template
        total_days = self.config.planning_period_weeks * WORK_DAYS_PER_WEEK
        self.timeslots = [
            TimeSlot(day_index=day, slot_template=template)
            for day in range(total_days)
            for template in self.slot_templates.values()
        ]

    def _build_context(self) -> ConstraintContext:
        data = self.raw_data or {}
        groups = {item["id"]: Group(id=item["id"], students_count=item.get("students_count", 0)) for item in data["groups"]}
        subjects = {
            item["id"]: Subject(
                id=item["id"],
                name=item.get("name", item["id"]),
                requires_specialized=item.get("requires_specialized", False),
                preferred_period=item.get("preferred_period"),
                difficulty=item.get("difficulty", 1),
            )
            for item in data["subjects"]
        }
        teachers = {
            item["id"]: Teacher(
                id=item["id"],
                name=item.get("name", item["id"]),
                subjects=item.get("subjects", []),
                preferences=item.get("preferences", {}),
            )
            for item in data["teachers"]
        }
        classrooms = {
            item["id"]: Classroom(
                id=item["id"],
                capacity=item.get("capacity", 0),
                type=item.get("type", "general"),
            )
            for item in data["classrooms"]
        }
        existing_schedule = [
            ExistingLesson(
                subject=item["subject"],
                teacher=item["teacher"],
                group=item["group"],
                classroom=item.get("classroom", ""),
                day_index=item.get("day_index", 0),
                slot_index=item.get("slot_index", 0),
            )
            for item in data.get("existing_schedule", [])
        ]
        lesson_requests = [
            LessonRequest(
                subject=item["subject"],
                teacher=item["teacher"],
                group=item["group"],
                count=int(item.get("count", 1)),
            )
            for item in data.get("lessons_pool", [])
        ]
        specialized_map = {
            item["id"]: item.get("classroom_type")
            for item in data["subjects"]
            if item.get("classroom_type")
        }
        expanded_requests: List[LessonRequest] = []
        for req in lesson_requests:
            for _ in range(req.count):
                expanded_requests.append(
                    LessonRequest(
                        subject=req.subject,
                        teacher=req.teacher,
                        group=req.group,
                        count=1,
                    )
                )
        self.context_data = {"lesson_requests": expanded_requests}
        return ConstraintContext(
            groups=groups,
            subjects=subjects,
            teachers=teachers,
            classrooms=classrooms,
            existing_schedule=existing_schedule,
            specialized_map=specialized_map,
        )

    def _resolve_mode(self) -> ScheduleMode:
        if self.config.mode == "dense":
            return DenseMode(self.config)
        if self.config.mode == "balanced":
            return BalancedMode(self.config)
        if self.config.mode == "append":
            return AppendMode(self.config)
        self.logger.warning("Невідомий режим %s, використано balanced", self.config.mode)
        return BalancedMode(self.config)

    def _inject_existing_schedule(self, state: ScheduleState, results: ScheduleResults) -> None:
        if not self.context:
            return
        for existing in self.context.existing_schedule:
            slot = self._timeslot_from_indices(existing.day_index, existing.slot_index)
            if not slot:
                results.warnings.append(
                    f"Пропущено існуючий урок {existing.subject} через невідомий слот {existing.slot_index}"
                )
                continue
            scheduled = ScheduledLesson(
                subject=existing.subject,
                teacher=existing.teacher,
                group=existing.group,
                classroom=existing.classroom or self._fallback_classroom(existing.subject),
                timeslot=slot,
            )
            state.assigned.append(scheduled)
            state.register(scheduled)
            results.schedule.append(scheduled)
            results.statistics.register(scheduled)

    def _place_lesson(
        self,
        lesson: LessonRequest,
        subject: Subject,
        solver: ConstraintSolver,
        mode: ScheduleMode,
        state: ScheduleState,
        results: ScheduleResults,
    ) -> None:
        candidates = self._generate_candidates(lesson, subject, solver, state, mode)
        if not candidates:
            results.conflicts.append(
                f"Не вдалося розмістити {lesson.subject} для групи {lesson.group} (викладач {lesson.teacher})"
            )
            return
        best = max(candidates, key=lambda candidate: candidate.score)
        scheduled = ScheduledLesson(
            subject=lesson.subject,
            teacher=lesson.teacher,
            group=lesson.group,
            classroom=best.classroom.id,
            timeslot=best.timeslot,
        )
        state.assigned.append(scheduled)
        state.register(scheduled)
        results.schedule.append(scheduled)
        results.statistics.register(scheduled)

    def _generate_candidates(
        self,
        lesson: LessonRequest,
        subject: Subject,
        solver: ConstraintSolver,
        state: ScheduleState,
        mode: ScheduleMode,
    ) -> List[SlotCandidate]:
        candidates: List[SlotCandidate] = []
        for timeslot in self.timeslots:
            day_load = state.day_load(lesson.group, timeslot.day_index)
            if day_load >= self.config.max_lessons_per_day:
                continue
            if not self.config.allow_gaps and not self._is_slot_contiguous(lesson.group, timeslot, state):
                continue
            if solver.check_teacher_conflict(lesson, timeslot, state.assigned):
                continue
            if solver.check_group_conflict(lesson, timeslot, state.assigned):
                continue
            subject_per_day = state.count_subject(lesson.group, timeslot.day_index, lesson.subject)
            if not solver.minimize_duplicates(subject, lesson, subject_per_day, state):
                continue
            for candidate in solver.build_candidate(subject, lesson, timeslot, state):
                candidate.score = mode.score(candidate, lesson, subject, state)
                candidates.append(candidate)
        return candidates

    def _is_slot_contiguous(self, group: str, timeslot: TimeSlot, state: ScheduleState) -> bool:
        slots = state.slots_for_day(group, timeslot.day_index)
        if not slots:
            return True
        return timeslot.slot_index in {min(slots) - 1, max(slots) + 1}

    def _timeslot_from_indices(self, day_index: int, slot_index: int) -> Optional[TimeSlot]:
        template = self.slot_templates.get(slot_index)
        if not template:
            return None
        return TimeSlot(day_index=day_index, slot_template=template)

    def _fallback_classroom(self, subject_id: str) -> str:
        if self.context and subject_id in self.context.specialized_map:
            room_type = self.context.specialized_map[subject_id]
            for classroom in self.context.classrooms.values():
                if classroom.type == room_type:
                    return classroom.id
        if self.context:
            return next(iter(self.context.classrooms.keys()), "")
        return ""
