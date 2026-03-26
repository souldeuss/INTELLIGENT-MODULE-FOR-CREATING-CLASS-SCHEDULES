"""Конфігурація модуля розкладу."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class OptimizationPriority:
    """Пріоритети оптимізації для генерації розкладу."""

    priorities: List[str] = field(default_factory=lambda: ["no_conflicts", "minimize_gaps"])

    def weight(self, name: str) -> int:
        """Повертає вагу пріоритету (менше значення – вищий пріоритет)."""
        try:
            return self.priorities.index(name)
        except ValueError:
            return len(self.priorities)


@dataclass
class Config:
    """Налаштування роботи генератора розкладу."""

    mode: str = "balanced"
    planning_period_weeks: int = 1
    max_lessons_per_day: int = 7
    time_slots: List[str] = field(default_factory=list)
    allow_duplicates: bool = True
    max_duplicates_per_day: int = 2
    use_specialized_classrooms: bool = True
    optimization_priority: OptimizationPriority = field(default_factory=OptimizationPriority)
    preferred_day_order: List[int] = field(default_factory=lambda: list(range(10)))
    allow_gaps: bool = True
    min_gaps: int = 0
    max_gaps: int = 2

    @staticmethod
    def from_dict(data: dict) -> "Config":
        """Створює конфігурацію з словника."""
        priorities = data.get("optimization_priority", [])
        return Config(
            mode=data.get("mode", "balanced"),
            planning_period_weeks=int(data.get("planning_period_weeks", 1)),
            max_lessons_per_day=int(data.get("max_lessons_per_day", 7)),
            time_slots=list(data.get("time_slots", [])),
            allow_duplicates=bool(data.get("allow_duplicates", True)),
            max_duplicates_per_day=int(data.get("max_duplicates_per_day", 2)),
            use_specialized_classrooms=bool(data.get("use_specialized_classrooms", True)),
            optimization_priority=OptimizationPriority(priorities=priorities)
            if priorities
            else OptimizationPriority(),
            preferred_day_order=list(data.get("preferred_day_order", [])) or list(range(10)),
            allow_gaps=bool(data.get("allow_gaps", True)),
            min_gaps=int(data.get("min_gaps", 0)),
            max_gaps=int(data.get("max_gaps", 2)),
        )
