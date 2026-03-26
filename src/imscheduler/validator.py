"""Модуль валідації даних та результатів."""
from __future__ import annotations

from typing import Dict, List

from .models import ScheduleResults, ScheduledLesson


class Validator:
    """Здійснює валідацію вхідних даних та кінцевого розкладу."""

    REQUIRED_FIELDS = [
        "groups",
        "subjects",
        "teachers",
        "classrooms",
        "lessons_pool",
    ]

    def validate_input(self, data: Dict) -> List[str]:
        problems: List[str] = []
        for field in self.REQUIRED_FIELDS:
            if field not in data or not data[field]:
                problems.append(f"Відсутнє поле '{field}' у вхідному файлі")
        if data.get("constraints") and not isinstance(data["constraints"], dict):
            problems.append("Поле 'constraints' повинно бути об'єктом")
        return problems

    def validate_schedule(self, results: ScheduleResults) -> List[str]:
        """Перевіряє, чи немає конфліктів у фінальному розкладі."""
        warnings: List[str] = []
        seen_slots = set()
        for lesson in results.schedule:
            slot_key = (lesson.timeslot.day_index, lesson.timeslot.slot_index)
            teacher_key = (lesson.teacher, *slot_key)
            group_key = (lesson.group, *slot_key)
            classroom_key = (lesson.classroom, *slot_key)
            if teacher_key in seen_slots:
                warnings.append(f"Конфлікт викладача {lesson.teacher} у слоті {slot_key}")
            if group_key in seen_slots:
                warnings.append(f"Конфлікт групи {lesson.group} у слоті {slot_key}")
            if classroom_key in seen_slots:
                warnings.append(f"Конфлікт аудиторії {lesson.classroom} у слоті {slot_key}")
            seen_slots.add(teacher_key)
            seen_slots.add(group_key)
            seen_slots.add(classroom_key)
        return warnings

    def generate_report(self, results: ScheduleResults) -> Dict[str, object]:
        return results.to_dict()
