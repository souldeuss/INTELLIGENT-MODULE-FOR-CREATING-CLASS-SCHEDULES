"""
DRL Environment v2 для University Course Timetabling Problem.

КЛЮЧОВІ ВИПРАВЛЕННЯ:
1. Правильна генерація pending_courses: кожен курс × група × hours_per_week
2. Посилений reward за повноту розкладу
3. Правильна termination condition - лише коли ВСІ години заплановані
4. Local Search для заповнення порожніх слотів
5. Детальна діагностика незаповнених годин
6. БАЛАНСУВАННЯ ДЕННОГО НАВАНТАЖЕННЯ (NEW!)
   - Target lessons per day з допустимим відхиленням ±1
   - Reward penalty за дисперсію денних занять
   - Action biasing для менш завантажених днів
   - Day-load balancing local search

Автор: AI Research Engineer
Дата: 2024-12-25
"""
import numpy as np
import torch
from typing import Dict, List, Optional, Tuple, Set
from functools import lru_cache
import logging

from ..models.database import Course, Teacher, StudentGroup, Classroom, Timeslot

logger = logging.getLogger(__name__)


class TimetablingEnvironmentV2:
    """
    Покращене середовище для DRL агента з гарантією повноти розкладу
    та РІВНОМІРНИМ РОЗПОДІЛОМ занять по днях тижня.
    
    Критичні покращення:
    1. HARD CONSTRAINT: всі курси повинні використати ВСІ свої години
    2. Штраф за невикористані години пропорційний до важливості
    3. Local Search фаза після DRL для заповнення порожнин
    4. Детальна діагностика причин незаповнення
    5. БАЛАНСУВАННЯ: target_lessons_per_day з variance penalty
    """

    # === НАЛАШТУВАННЯ REWARD ===
    REWARD_VALID_ASSIGNMENT = 2.0       # Бонус за кожне валідне призначення
    REWARD_COMPLETE_COURSE = 5.0        # Бонус за повністю заповнений курс
    REWARD_BALANCED_DAY = 1.5           # Бонус за рівномірний розподіл по днях
    REWARD_PREFERRED_CLASSROOM = 0.5    # Бонус за бажаний тип аудиторії
    REWARD_TARGET_DAY_LOAD = 2.0        # Бонус за досягнення target занять на день
    
    PENALTY_TEACHER_CONFLICT = -10.0    # Конфлікт викладача (HARD)
    PENALTY_GROUP_CONFLICT = -10.0      # Конфлікт групи (HARD)
    PENALTY_CLASSROOM_CONFLICT = -10.0  # Конфлікт аудиторії (HARD)
    PENALTY_CAPACITY = -5.0             # Недостатня місткість (HARD)
    PENALTY_MISSING_HOUR = -8.0         # За кожну невикористану годину курсу
    PENALTY_OVERLOADED_DAY = -3.0       # Більше target+1 занять на день
    PENALTY_NO_LAB = -3.0               # Потрібна лабораторія, але немає
    PENALTY_DAY_VARIANCE = -2.0         # Штраф за високу дисперсію по днях
    PENALTY_IMBALANCED_SCHEDULE = -5.0  # Штраф за незбалансований розклад при завершенні
    PENALTY_SKIP_EMPTY_DAY = -2.5       # Штраф за заповнення вже активного дня коли є порожні
    PENALTY_EMPTY_DAY_AT_END = -6.0     # Штраф за порожні дні у фінальному розкладі
    REWARD_FILL_EMPTY_DAY = 3.0         # Бонус за перше заняття у порожньому дні
    
    # === НАЛАШТУВАННЯ БАЛАНСУВАННЯ ===
    MAX_DAY_DEVIATION = 1               # Допустиме відхилення від target (±1 заняття)
    VARIANCE_THRESHOLD = 2.0            # Поріг дисперсії для termination
    DAY_BALANCE_ALPHA = 1.5             # Вага penalty за variance
    DAY_BALANCE_BETA = 1.0              # Вага penalty за відхилення від target
    EMPTY_DAY_BETA = 2.0                # Вага penalty за дефіцит активних днів
    PENALTY_GAP_HOUR = -1.5             # Штраф за "вікна" між парами в межах дня
    REWARD_CONSECUTIVE_LESSON = 1.0     # Бонус за суміжні пари

    def __init__(
        self,
        courses: List[Course],
        teachers: List[Teacher],
        groups: List[StudentGroup],
        classrooms: List[Classroom],
        timeslots: List[Timeslot],
        course_teacher_map: Dict[int, List[int]] = None,  # Які викладачі ведуть які курси
        course_group_map: Dict[int, List[int]] = None,    # Які групи відвідують які курси
    ):
        self.courses = courses
        self.teachers = teachers
        self.groups = groups
        self.classrooms = classrooms
        self.timeslots = timeslots

        # === Індексування ===
        self.course_idx = {c.id: idx for idx, c in enumerate(courses)}
        self.teacher_idx = {t.id: idx for idx, t in enumerate(teachers)}
        self.group_idx = {g.id: idx for idx, g in enumerate(groups)}
        self.classroom_idx = {r.id: idx for idx, r in enumerate(classrooms)}
        self.timeslot_idx = {ts.id: idx for idx, ts in enumerate(timeslots)}

        # Розміри
        self.n_courses = len(courses)
        self.n_teachers = len(teachers)
        self.n_groups = len(groups)
        self.n_classrooms = len(classrooms)
        self.n_timeslots = len(timeslots)

        # === Мапінг курс-викладач та курс-група ===
        # Якщо не передано - кожен викладач може вести будь-який курс
        self.course_teacher_map = course_teacher_map or self._default_course_teacher_map()
        self.course_group_map = course_group_map or self._default_course_group_map()

        # === Попередньо обчислені структури ===
        self._precompute_timeslot_info()
        self._precompute_constraints()
        
        # Розмір стану
        self.state_dim = self._calculate_state_dim()
        
        logger.info(f"🎓 TimetablingEnvironmentV2 ініціалізовано:")
        logger.info(f"   Курсів: {self.n_courses}, Викладачів: {self.n_teachers}")
        logger.info(f"   Груп: {self.n_groups}, Аудиторій: {self.n_classrooms}")
        logger.info(f"   Таймслотів: {self.n_timeslots}")
        
        self.reset()

    def _default_course_teacher_map(self) -> Dict[int, List[int]]:
        """За замовчуванням - кожен викладач може вести кожен курс."""
        return {c.id: [t.id for t in self.teachers] for c in self.courses}
    
    def _default_course_group_map(self) -> Dict[int, List[int]]:
        """За замовчуванням - кожна група відвідує кожен курс."""
        return {c.id: [g.id for g in self.groups] for c in self.courses}

    def _precompute_timeslot_info(self):
        """Попередньо обчислюємо інформацію про таймслоти."""
        self.timeslot_days = np.array([ts.day_of_week for ts in self.timeslots], dtype=np.int32)
        self.timeslot_periods = np.array([ts.period_number for ts in self.timeslots], dtype=np.int32)
        
        # Маски по днях
        self.day_masks = np.zeros((5, self.n_timeslots), dtype=np.bool_)
        for day in range(5):
            self.day_masks[day] = (self.timeslot_days == day)
        
        self.slots_per_day = np.sum(self.day_masks, axis=1)

    def _precompute_constraints(self):
        """Попередньо обчислюємо обмеження."""
        self.classroom_capacities = np.array([c.capacity for c in self.classrooms], dtype=np.int32)
        
        classroom_types = {"lecture": 0, "lab": 1, "computer_lab": 1, "seminar": 2, "computer": 3, "general": 0}
        self.classroom_types = np.array(
            [classroom_types.get(c.classroom_type, 0) for c in self.classrooms], 
            dtype=np.int32
        )
        
        self.group_sizes = np.array([g.students_count for g in self.groups], dtype=np.int32)
        
        self.course_requires_lab = np.array(
            [getattr(c, 'requires_lab', False) for c in self.courses],
            dtype=np.bool_
        )
        
        self.course_preferred_type = np.array(
            [classroom_types.get(getattr(c, 'preferred_classroom_type', None), -1) 
             for c in self.courses],
            dtype=np.int32
        )
        
        # Години на тиждень для кожного курсу
        self.course_hours = np.array(
            [getattr(c, 'hours_per_week', 2) for c in self.courses],
            dtype=np.int32
        )

    def _calculate_state_dim(self) -> int:
        """Розмір стану."""
        return (
            self.n_teachers * self.n_timeslots +  # teacher_schedule
            self.n_groups * self.n_timeslots +     # group_schedule
            self.n_classrooms * self.n_timeslots + # classroom_schedule
            self.n_courses +                        # course_hours_remaining
            self.n_groups * 5 +                    # classes_per_day
            self.n_groups +                        # target_per_day for each group
            self.n_groups +                        # day_variance for each group
            5                                       # progress, pending_ratio, completion_rate, avg_variance, balance_score
        )

    def reset(self) -> np.ndarray:
        """
        Скидає середовище.
        
        КРИТИЧНО: Правильна генерація pending_courses!
        Кожен курс для кожної групи повинен бути запланований hours_per_week разів.
        """
        # === Матриці зайнятості ===
        self.teacher_schedule = np.zeros((self.n_teachers, self.n_timeslots), dtype=np.int32)
        self.group_schedule = np.zeros((self.n_groups, self.n_timeslots), dtype=np.int32)
        self.classroom_schedule = np.zeros((self.n_classrooms, self.n_timeslots), dtype=np.int32)
        
        # Кількість занять на день для кожної групи
        self.group_classes_per_day = np.zeros((self.n_groups, 5), dtype=np.int32)
        
        # === КРИТИЧНО: Правильне створення pending_courses ===
        # Формат: (course_idx, group_idx) - повторюється hours_per_week разів
        self.pending_courses: List[Tuple[int, int]] = []
        self.course_hours_remaining = np.zeros(self.n_courses, dtype=np.int32)
        
        # Лічильники для обчислення target_per_day
        self.group_total_lessons = np.zeros(self.n_groups, dtype=np.int32)
        group_course_candidates: Dict[int, List[int]] = {g_idx: [] for g_idx in range(self.n_groups)}
        
        for course_idx, course in enumerate(self.courses):
            hours = course.hours_per_week if hasattr(course, 'hours_per_week') else 2
            self.course_hours_remaining[course_idx] = hours
            
            # Отримуємо групи для цього курсу
            course_id = course.id
            group_ids = self.course_group_map.get(course_id, [])
            
            if not group_ids:
                # Якщо немає призначених груп - беремо всі
                group_ids = [g.id for g in self.groups]
            
            for group_id in group_ids:
                if group_id in self.group_idx:
                    group_idx = self.group_idx[group_id]
                    if course_idx not in group_course_candidates[group_idx]:
                        group_course_candidates[group_idx].append(course_idx)
                    # Додаємо hours разів для цієї пари курс-група
                    for _ in range(hours):
                        self.pending_courses.append((course_idx, group_idx))
                    # Оновлюємо лічильник загальних занять для групи
                    self.group_total_lessons[group_idx] += hours

        # === ОБЧИСЛЕННЯ TARGET ЗАНЯТЬ НА ДЕНЬ ===
        # target = загальна кількість занять / 5 днів
        self.target_lessons_per_day = np.zeros(self.n_groups, dtype=np.float32)
        self.target_active_days = np.zeros(self.n_groups, dtype=np.int32)
        for group_idx in range(self.n_groups):
            total = self.group_total_lessons[group_idx]
            self.target_lessons_per_day[group_idx] = total / 5.0
            self.target_active_days[group_idx] = min(5, int(total)) if total > 0 else 0
        
        logger.info(f"📊 Target занять на день по групах: {self.target_lessons_per_day}")
        logger.info(f"📊 Target активних днів по групах: {self.target_active_days}")
        
        # Список призначень
        self.assignments_list: List[Tuple[int, int, int, int, int]] = []
        
        self.current_step = 0
        self.total_classes_to_schedule = len(self.pending_courses)
        self.max_steps = self.total_classes_to_schedule + 100  # Запас для пошуку
        
        logger.info(f"🔄 Environment reset: {self.total_classes_to_schedule} занять до розкладу")
        
        return self._get_state()

    def _get_state(self) -> np.ndarray:
        """Повертає стан для нейромережі."""
        # Нормалізація
        max_val = max(
            np.max(self.teacher_schedule) if self.teacher_schedule.size > 0 else 1,
            np.max(self.group_schedule) if self.group_schedule.size > 0 else 1,
            np.max(self.classroom_schedule) if self.classroom_schedule.size > 0 else 1,
            1
        )
        
        flat_teacher = (self.teacher_schedule.flatten() / max(max_val, 1)).astype(np.float32)
        flat_group = (self.group_schedule.flatten() / max(max_val, 1)).astype(np.float32)
        flat_classroom = (self.classroom_schedule.flatten() / max(max_val, 1)).astype(np.float32)
        
        # Залишок годин по курсах
        max_hours = max(np.max(self.course_hours_remaining), 1)
        hours_remaining = (self.course_hours_remaining / max_hours).astype(np.float32)
        
        # Заняття по днях
        max_classes = max(np.max(self.group_classes_per_day), 1)
        flat_day_load = (self.group_classes_per_day.flatten() / max_classes).astype(np.float32)
        
        # Target per day (нормалізовано)
        max_target = max(np.max(self.target_lessons_per_day), 1)
        target_normalized = (self.target_lessons_per_day / max_target).astype(np.float32)
        
        # Variance per group
        day_variances = np.array([
            np.var(self.group_classes_per_day[g]) for g in range(self.n_groups)
        ], dtype=np.float32)
        max_var = max(np.max(day_variances), 1)
        variance_normalized = (day_variances / max_var).astype(np.float32)
        
        # Прогрес та баланс
        scheduled = len(self.assignments_list)
        total = self.total_classes_to_schedule
        avg_variance = np.mean(day_variances) if self.n_groups > 0 else 0
        balance_score = self._calculate_balance_score()
        
        progress = np.array([
            self.current_step / max(self.max_steps, 1),
            len(self.pending_courses) / max(total, 1),
            scheduled / max(total, 1),  # Completion rate
            avg_variance / max(self.VARIANCE_THRESHOLD, 1),  # Normalized variance
            balance_score  # 0-1 score
        ], dtype=np.float32)
        
        state = np.concatenate([
            flat_teacher, flat_group, flat_classroom,
            hours_remaining, flat_day_load, 
            target_normalized, variance_normalized,
            progress
        ])
        
        return state
    
    def _calculate_balance_score(self) -> float:
        """
        Обчислює score балансу (0-1, де 1 = ідеально збалансовано).
        """
        if self.n_groups == 0:
            return 1.0
        
        total_deviation = 0.0
        for group_idx in range(self.n_groups):
            target = self.target_lessons_per_day[group_idx]
            if target == 0:
                continue
            for day in range(5):
                actual = self.group_classes_per_day[group_idx, day]
                deviation = abs(actual - target)
                total_deviation += deviation

            # Окремо штрафуємо за дефіцит активних днів (повністю порожні дні).
            _, _, active_day_deficit = self._get_group_active_day_stats(group_idx)
            if active_day_deficit > 0:
                total_deviation += active_day_deficit * 2.0
        
        # Нормалізуємо
        max_deviation = self.n_groups * 5 * 5  # Максимальне теоретичне відхилення
        score = 1.0 - (total_deviation / max(max_deviation, 1))
        return max(0.0, min(1.0, score))

    def _get_group_active_day_stats(self, group_idx: int) -> Tuple[int, int, int]:
        """
        Повертає статистику активних днів для групи.

        Returns:
            (active_days, expected_active_days, active_day_deficit)
        """
        day_loads = self.group_classes_per_day[group_idx]
        active_days = int(np.sum(day_loads > 0))
        expected_active_days = int(self.target_active_days[group_idx])
        active_day_deficit = max(0, expected_active_days - active_days)
        return active_days, expected_active_days, active_day_deficit

    def _group_max_day_deviation(self, group_idx: int) -> float:
        """
        Повертає максимальне відхилення денного навантаження від target.
        """
        target = float(self.target_lessons_per_day[group_idx])
        if target <= 0:
            return 0.0

        day_loads = self.group_classes_per_day[group_idx].astype(np.float32)
        return float(np.max(np.abs(day_loads - target)))

    def step(self, action: Tuple[int, int, int, int, int]) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        Виконує дію.
        
        Action: (course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx)
        """
        course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx = action
        
        # Перевірка валідності
        target = (course_idx, group_idx)
        if target not in self.pending_courses:
            return self._get_state(), -15.0, False, {"error": "invalid_assignment"}
        
        # Обчислення reward
        reward = self._calculate_reward(course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx)
        
        # Оновлення стану
        self.teacher_schedule[teacher_idx, timeslot_idx] += 1
        self.group_schedule[group_idx, timeslot_idx] += 1
        self.classroom_schedule[classroom_idx, timeslot_idx] += 1
        
        day = self.timeslot_days[timeslot_idx]
        self.group_classes_per_day[group_idx, day] += 1
        
        # Зберігаємо та видаляємо з pending
        self.assignments_list.append(action)
        self.pending_courses.remove(target)
        self.current_step += 1
        
        # === КРИТИЧНО: Умова завершення з перевіркою балансу ===
        all_scheduled = len(self.pending_courses) == 0
        
        # Перевірка балансу при завершенні
        is_balanced = self._check_balance_acceptable()
        
        # Завершуємо якщо все заплановано
        done = all_scheduled
        
        # Додаткова перевірка на досягнення ліміту кроків
        if self.current_step >= self.max_steps and not done:
            # Штраф за незавершений розклад
            remaining = len(self.pending_courses)
            reward += self.PENALTY_MISSING_HOUR * remaining
            done = True
            logger.warning(f"⚠️ Досягнуто ліміт кроків. Незаплановано: {remaining} занять")
        
        # Бонус/штраф за завершення
        if done and all_scheduled:
            reward += self.REWARD_COMPLETE_COURSE * self.n_courses
            
            # === ШТРАФ ЗА НЕЗБАЛАНСОВАНИЙ РОЗКЛАД ===
            if not is_balanced:
                variance_penalty = self._calculate_total_variance_penalty()
                reward += variance_penalty
                logger.warning(f"⚠️ Розклад незбалансований. Penalty: {variance_penalty:.2f}")
            else:
                # Бонус за ідеальний баланс
                reward += self.REWARD_BALANCED_DAY * self.n_groups
                logger.info(f"✅ Розклад ідеально збалансовано!")

            logger.info(f"✅ Розклад повністю сформовано! Reward: {reward:.2f}")
        
        # Логування балансу кожні 20 кроків
        if self.current_step % 20 == 0:
            self._log_balance_status()
        
        info = {
            "hard_violations": self._count_hard_violations(),
            "soft_violations": self._count_soft_violations(),
            "scheduled": len(self.assignments_list),
            "remaining": len(self.pending_courses),
            "completion_rate": len(self.assignments_list) / max(self.total_classes_to_schedule, 1),
            "is_balanced": is_balanced,
            "balance_score": self._calculate_balance_score(),
            "weekly_group_load": [int(np.sum(self.group_classes_per_day[g])) for g in range(self.n_groups)],
            "day_variance": self._get_day_variance_stats()
        }
        
        return self._get_state(), reward, done, info
    
    def _check_balance_acceptable(self) -> bool:
        """
        Перевіряє чи баланс денного навантаження прийнятний.
        
        Returns:
            True якщо max_deviation <= MAX_DAY_DEVIATION для всіх груп
        """
        for group_idx in range(self.n_groups):
            target = float(self.target_lessons_per_day[group_idx])

            if target <= 0:
                continue

            active_days, expected_active_days, active_day_deficit = self._get_group_active_day_stats(group_idx)
            if expected_active_days > 0 and active_day_deficit > 0:
                return False

            # Допускаємо невеликий запас для дробового target.
            if self._group_max_day_deviation(group_idx) > self.MAX_DAY_DEVIATION + 0.5:
                return False
        
        return True
    
    def _calculate_total_variance_penalty(self) -> float:
        """
        Обчислює загальний штраф за variance.
        """
        total_penalty = 0.0
        
        for group_idx in range(self.n_groups):
            day_loads = self.group_classes_per_day[group_idx]
            target = self.target_lessons_per_day[group_idx]
            
            # Variance penalty
            variance = np.var(day_loads)
            total_penalty += self.DAY_BALANCE_ALPHA * variance
            
            # Deviation from target penalty
            for day in range(5):
                deviation = abs(day_loads[day] - target)
                if deviation > self.MAX_DAY_DEVIATION:
                    total_penalty += self.DAY_BALANCE_BETA * (deviation - self.MAX_DAY_DEVIATION)

            # Штраф за дефіцит активних днів (повністю порожні дні).
            _, _, active_day_deficit = self._get_group_active_day_stats(group_idx)
            if active_day_deficit > 0:
                total_penalty += self.EMPTY_DAY_BETA * active_day_deficit
                total_penalty += abs(self.PENALTY_EMPTY_DAY_AT_END) * active_day_deficit
        
        return -total_penalty  # Негативне значення = штраф
    
    def _get_day_variance_stats(self) -> Dict:
        """Повертає статистику variance по днях."""
        stats = {}
        for group_idx in range(self.n_groups):
            group = self.groups[group_idx]
            day_loads = self.group_classes_per_day[group_idx].tolist()
            variance = float(np.var(day_loads))
            target = float(self.target_lessons_per_day[group_idx])
            active_days, expected_active_days, active_day_deficit = self._get_group_active_day_stats(group_idx)
            max_deviation = self._group_max_day_deviation(group_idx)
            stats[group.code] = {
                "day_loads": day_loads,
                "variance": variance,
                "target": target,
                "max_deviation": round(max_deviation, 2),
                "active_days": active_days,
                "target_active_days": expected_active_days,
                "active_day_deficit": active_day_deficit,
                "empty_days": int(sum(1 for value in day_loads if value == 0)),
            }
        return stats
    
    def _log_balance_status(self):
        """Логує поточний стан балансу."""
        logger.info(f"📊 Balance Status (step {self.current_step}):")
        for group_idx in range(min(3, self.n_groups)):  # Перші 3 групи
            group = self.groups[group_idx]
            day_loads = self.group_classes_per_day[group_idx]
            target = self.target_lessons_per_day[group_idx]
            variance = np.var(day_loads)
            logger.info(f"   {group.code}: days={day_loads.tolist()}, target={target:.1f}, var={variance:.2f}")

    def _calculate_reward(
        self,
        course_idx: int,
        teacher_idx: int,
        group_idx: int,
        classroom_idx: int,
        timeslot_idx: int,
    ) -> float:
        """
        Обчислює reward з акцентом на ПОВНОТУ та БАЛАНС розкладу.
        
        Включає:
        - Hard constraints (конфлікти)
        - Soft constraints (тип аудиторії, лабораторії)
        - DAY BALANCE: variance penalty та target deviation
        """
        reward = 0.0
        
        # === HARD CONSTRAINTS (великі штрафи) ===
        # Конфлікт викладача
        if self.teacher_schedule[teacher_idx, timeslot_idx] > 0:
            reward += self.PENALTY_TEACHER_CONFLICT
        
        # Конфлікт групи
        if self.group_schedule[group_idx, timeslot_idx] > 0:
            reward += self.PENALTY_GROUP_CONFLICT
        
        # Конфлікт аудиторії
        if self.classroom_schedule[classroom_idx, timeslot_idx] > 0:
            reward += self.PENALTY_CLASSROOM_CONFLICT
        
        # Місткість аудиторії
        if self.classroom_capacities[classroom_idx] < self.group_sizes[group_idx]:
            reward += self.PENALTY_CAPACITY
        
        # === SOFT CONSTRAINTS ===
        # Лабораторія
        if self.course_requires_lab[course_idx]:
            if self.classroom_types[classroom_idx] != 1:  # 1 = lab
                reward += self.PENALTY_NO_LAB
            else:
                reward += 1.0  # Бонус за правильний тип
        
        # Бажаний тип аудиторії
        if self.course_preferred_type[course_idx] >= 0:
            if self.classroom_types[classroom_idx] == self.course_preferred_type[course_idx]:
                reward += self.REWARD_PREFERRED_CLASSROOM
        
        # === БАЛАНСУВАННЯ ДЕННОГО НАВАНТАЖЕННЯ ===
        day = self.timeslot_days[timeslot_idx]
        classes_today = self.group_classes_per_day[group_idx, day]
        day_loads = self.group_classes_per_day[group_idx]
        target = self.target_lessons_per_day[group_idx]
        period = int(self.timeslot_periods[timeslot_idx])
        _, _, active_day_deficit = self._get_group_active_day_stats(group_idx)

        temp_loads = day_loads.copy()
        temp_loads[day] += 1
        empty_days_before = int(np.sum(day_loads == 0))
        empty_days_after = int(np.sum(temp_loads == 0))
        
        # Штраф за перевищення target + допустиме відхилення
        if classes_today >= target + self.MAX_DAY_DEVIATION:
            reward += self.PENALTY_OVERLOADED_DAY * (classes_today - target - self.MAX_DAY_DEVIATION + 1)
        
        # Бонус за рівномірний розподіл (додавання в менш завантажений день)
        min_day_load = np.min(self.group_classes_per_day[group_idx])
        if classes_today == min_day_load:
            reward += self.REWARD_BALANCED_DAY

        # Пріоритет - закривати порожні дні, якщо група ще має дефіцит активних днів.
        if active_day_deficit > 0:
            if classes_today == 0:
                reward += self.REWARD_FILL_EMPTY_DAY
            else:
                reward += self.PENALTY_SKIP_EMPTY_DAY

        # Додатковий бонус, якщо після дії кількість порожніх днів зменшується.
        if empty_days_after < empty_days_before:
            reward += self.REWARD_FILL_EMPTY_DAY * (empty_days_before - empty_days_after)
        
        # Бонус якщо близько до target
        if abs(classes_today - target) <= self.MAX_DAY_DEVIATION:
            reward += self.REWARD_TARGET_DAY_LOAD * 0.5

        # === МІНІМІЗАЦІЯ "ВІКОН" В РОЗКЛАДІ ГРУПИ ===
        day_slots = np.where(self.timeslot_days == day)[0]
        occupied_periods = sorted(
            [int(self.timeslot_periods[ts]) for ts in day_slots if self.group_schedule[group_idx, ts] > 0]
        )

        if occupied_periods:
            min_distance = min(abs(period - p) for p in occupied_periods)
            if min_distance == 1:
                reward += self.REWARD_CONSECUTIVE_LESSON
            elif min_distance >= 3:
                reward += self.PENALTY_GAP_HOUR

            before_gaps = self._count_day_gaps(occupied_periods)
            after_gaps = self._count_day_gaps(sorted(occupied_periods + [period]))
            reward += self.PENALTY_GAP_HOUR * (after_gaps - before_gaps)
        
        # === VARIANCE PENALTY (INCREMENTAL) ===
        # Обчислюємо як змінюється variance після цього призначення
        current_variance = np.var(self.group_classes_per_day[group_idx])

        # Симулюємо новий стан
        new_variance = np.var(temp_loads)
        
        # Штраф якщо variance зростає
        if new_variance > current_variance:
            variance_increase = new_variance - current_variance
            reward += self.PENALTY_DAY_VARIANCE * variance_increase
        elif new_variance < current_variance:
            # Бонус якщо variance зменшується
            reward += abs(current_variance - new_variance) * 0.5
        
        # === БОНУС ЗА ВАЛІДНЕ ПРИЗНАЧЕННЯ ===
        # Якщо немає жорстких конфліктів
        has_hard_conflict = (
            self.teacher_schedule[teacher_idx, timeslot_idx] > 0 or
            self.group_schedule[group_idx, timeslot_idx] > 0 or
            self.classroom_schedule[classroom_idx, timeslot_idx] > 0
        )
        
        if not has_hard_conflict:
            reward += self.REWARD_VALID_ASSIGNMENT

        return reward

    @staticmethod
    def _count_day_gaps(periods: List[int]) -> int:
        """Повертає кількість порожніх пар між заняттями в межах дня."""
        if len(periods) < 2:
            return 0
        gaps = 0
        for i in range(1, len(periods)):
            diff = periods[i] - periods[i - 1]
            if diff > 1:
                gaps += diff - 1
        return gaps

    def _count_hard_violations(self) -> int:
        """Підрахунок жорстких порушень."""
        return int(
            np.sum(self.teacher_schedule > 1) +
            np.sum(self.group_schedule > 1) +
            np.sum(self.classroom_schedule > 1)
        )

    def _count_soft_violations(self) -> int:
        """Підрахунок м'яких порушень."""
        violations = 0
        
        # Нерівномірність по днях (з урахуванням target)
        for group_idx in range(self.n_groups):
            day_loads = self.group_classes_per_day[group_idx]
            target = self.target_lessons_per_day[group_idx]
            
            # Кількість днів з відхиленням > MAX_DAY_DEVIATION
            for day in range(5):
                if abs(day_loads[day] - target) > self.MAX_DAY_DEVIATION:
                    violations += 1
            
            # Variance check
            if np.var(day_loads) > self.VARIANCE_THRESHOLD:
                violations += 1

            # Дефіцит активних днів (повністю порожні дні при очікуваному навантаженні).
            _, _, active_day_deficit = self._get_group_active_day_stats(group_idx)
            violations += active_day_deficit

            # "Вікна" в межах дня для групи
            for day in range(5):
                day_slots = np.where(self.timeslot_days == day)[0]
                occupied_periods = sorted(
                    [int(self.timeslot_periods[ts]) for ts in day_slots if self.group_schedule[group_idx, ts] > 0]
                )
                violations += self._count_day_gaps(occupied_periods)
        
        return violations

    def get_valid_actions(self) -> List[Tuple[int, int, int, int, int]]:
        """
        Повертає список валідних дій з ПРІОРИТЕТОМ для балансування.
        
        КРИТИЧНО: Враховує пару (course_idx, group_idx) з pending!
        Action Biasing: надає пріоритет дням з меншою кількістю занять.
        """
        if not self.pending_courses:
            return []
        
        # Беремо першу незаплановану пару (курс, група)
        course_idx, target_group_idx = self.pending_courses[0]
        course = self.courses[course_idx]
        
        # Отримуємо доступних викладачів для курсу
        course_id = course.id
        teacher_ids = self.course_teacher_map.get(course_id, [t.id for t in self.teachers])
        teacher_indices = [self.teacher_idx[tid] for tid in teacher_ids if tid in self.teacher_idx]
        
        if not teacher_indices:
            teacher_indices = list(range(self.n_teachers))
        
        valid_actions = []
        
        # Перебираємо комбінації
        for teacher_idx in teacher_indices:
            for classroom_idx in range(self.n_classrooms):
                for timeslot_idx in range(self.n_timeslots):
                    # Перевірка конфліктів
                    if (self.teacher_schedule[teacher_idx, timeslot_idx] == 0 and
                        self.group_schedule[target_group_idx, timeslot_idx] == 0 and
                        self.classroom_schedule[classroom_idx, timeslot_idx] == 0):
                        
                        # Перевірка місткості
                        if self.classroom_capacities[classroom_idx] >= self.group_sizes[target_group_idx]:
                            action = (course_idx, teacher_idx, target_group_idx, classroom_idx, timeslot_idx)
                            valid_actions.append(action)
        
        # Сортуємо за пріоритетом (ACTION BIASING для балансу)
        valid_actions = self._sort_actions_by_balance_priority(valid_actions, target_group_idx)
        
        # Обмежуємо кількість
        return valid_actions[:500]

    def _sort_actions_by_balance_priority(self, actions: List[Tuple], group_idx: int) -> List[Tuple]:
        """
        Сортує дії з пріоритетом балансування денного навантаження.
        
        Пріоритет:
        1. Дні з меншою кількістю занять (HEAD)
        2. Дні ближче до target
        3. Середні пари краще
        """
        target = self.target_lessons_per_day[group_idx]
        current_loads = self.group_classes_per_day[group_idx]
        min_load = np.min(current_loads)
        _, _, active_day_deficit = self._get_group_active_day_stats(group_idx)
        
        def priority(action):
            _, teacher_idx, _, classroom_idx, timeslot_idx = action
            day = self.timeslot_days[timeslot_idx]
            day_load = current_loads[day]
            period = int(self.timeslot_periods[timeslot_idx])
            
            score = 0
            
            # === ГОЛОВНИЙ ПРІОРИТЕТ: менш завантажені дні ===
            # Бонус за додавання в день з мінімальним навантаженням
            if day_load == min_load:
                score -= 100  # Великий бонус (менше = краще)

            # Якщо є дефіцит активних днів - форсуємо заповнення порожніх днів.
            if active_day_deficit > 0:
                if day_load == 0:
                    score -= 180
                else:
                    score += 70
            
            # Штраф за перевищення target
            if day_load >= target:
                score += 50 * (day_load - target + 1)
            
            # Штраф пропорційний кількості занять у цей день
            score += day_load * 20
            
            # Штраф за високе відхилення від target
            deviation = abs(day_load - target)
            if deviation > self.MAX_DAY_DEVIATION:
                score += deviation * 30
            
            # === ВТОРИННИЙ ПРІОРИТЕТ: середні пари ===
            score += abs(period - 3) * 2

            # === ДОДАТКОВО: менше "вікон" та більш послідовне призначення ===
            day_slots = np.where(self.timeslot_days == day)[0]
            occupied_periods = sorted(
                [int(self.timeslot_periods[ts]) for ts in day_slots if self.group_schedule[group_idx, ts] > 0]
            )
            if occupied_periods:
                min_distance = min(abs(period - p) for p in occupied_periods)
                if min_distance == 1:
                    score -= 25
                elif min_distance >= 3:
                    score += 35

                before_gaps = self._count_day_gaps(occupied_periods)
                after_gaps = self._count_day_gaps(sorted(occupied_periods + [period]))
                score += (after_gaps - before_gaps) * 40
            
            return score
        
        return sorted(actions, key=priority)

    def _sort_actions_by_priority(self, actions: List[Tuple]) -> List[Tuple]:
        """Сортує дії за пріоритетом (краще - спочатку). LEGACY."""
        def priority(action):
            _, teacher_idx, group_idx, classroom_idx, timeslot_idx = action
            score = 0
            
            # Менше занять у цей день = краще
            day = self.timeslot_days[timeslot_idx]
            score += self.group_classes_per_day[group_idx, day] * 10
            
            # Середні пари краще
            period = self.timeslot_periods[timeslot_idx]
            score += abs(period - 3) * 2
            
            return score
        
        return sorted(actions, key=priority)

    # === LOCAL SEARCH ДЛЯ ЗАПОВНЕННЯ ТА БАЛАНСУВАННЯ ===
    
    def run_local_search(self, max_iterations: int = 100) -> int:
        """
        Локальний пошук для заповнення порожніх слотів.
        
        Викликається ПІСЛЯ DRL фази для гарантії повноти.
        
        Returns:
            Кількість додатково заповнених слотів
        """
        filled = 0
        
        for _ in range(max_iterations):
            if not self.pending_courses:
                break
            
            # Пробуємо заповнити кожен pending
            course_idx, group_idx = self.pending_courses[0]
            
            action = self._find_best_balanced_slot(course_idx, group_idx)
            if action:
                # Виконуємо дію напряму (без reward)
                _, teacher_idx, _, classroom_idx, timeslot_idx = action
                
                self.teacher_schedule[teacher_idx, timeslot_idx] += 1
                self.group_schedule[group_idx, timeslot_idx] += 1
                self.classroom_schedule[classroom_idx, timeslot_idx] += 1
                
                day = self.timeslot_days[timeslot_idx]
                self.group_classes_per_day[group_idx, day] += 1
                
                self.assignments_list.append(action)
                self.pending_courses.remove((course_idx, group_idx))
                filled += 1
            else:
                # Не можемо заповнити - пропускаємо
                logger.warning(f"⚠️ Не можу знайти слот для курсу {course_idx}, групи {group_idx}")
                # Переміщуємо в кінець черги для повторної спроби
                item = self.pending_courses.pop(0)
                self.pending_courses.append(item)
        
        if filled > 0:
            logger.info(f"🔧 Local Search заповнив {filled} додаткових слотів")
        
        return filled
    
    def run_day_balance_local_search(self, max_iterations: int = 50) -> int:
        """
        Локальний пошук для БАЛАНСУВАННЯ денного навантаження.
        
        Переміщує заняття з перевантажених днів у менш заповнені.
        
        Returns:
            Кількість переміщених занять
        """
        moved = 0
        
        logger.info(f"⚖️ Запуск Day Balance Local Search...")
        initial_variance = self._calculate_total_variance()
        
        for iteration in range(max_iterations):
            # Знаходимо найбільш незбалансовану групу
            worst_group_idx = self._find_most_imbalanced_group()
            if worst_group_idx is None:
                break
            
            # Пробуємо переmістити заняття
            success = self._try_move_to_balance(worst_group_idx)
            if success:
                moved += 1
            
            # Перевіряємо чи досягли балансу
            if self._check_balance_acceptable():
                logger.info(f"✅ Досягнуто баланс після {iteration + 1} ітерацій")
                break
        
        final_variance = self._calculate_total_variance()
        
        logger.info(f"⚖️ Day Balance: moved={moved}, variance: {initial_variance:.2f} -> {final_variance:.2f}")
        self._log_final_balance()
        
        return moved
    
    def _find_most_imbalanced_group(self) -> Optional[int]:
        """Знаходить групу з найбільшим дисбалансом."""
        worst_idx = None
        worst_imbalance = 0.0
        
        for group_idx in range(self.n_groups):
            day_loads = self.group_classes_per_day[group_idx]
            if np.sum(day_loads) == 0:
                continue

            _, _, active_day_deficit = self._get_group_active_day_stats(group_idx)
            max_deviation = self._group_max_day_deviation(group_idx)
            imbalance = float(active_day_deficit) * 2.0 + max(0.0, max_deviation - self.MAX_DAY_DEVIATION)

            if imbalance > 0 and imbalance > worst_imbalance:
                worst_imbalance = imbalance
                worst_idx = group_idx
        
        return worst_idx
    
    def _try_move_to_balance(self, group_idx: int) -> bool:
        """
        Намагається переmістити заняття для балансування групи.
        
        Returns:
            True якщо вдалося переmістити
        """
        day_loads = self.group_classes_per_day[group_idx]
        _, expected_active_days, active_day_deficit = self._get_group_active_day_stats(group_idx)
        
        # Знаходимо найбільш завантажений день
        overloaded_day = int(np.argmax(day_loads))

        # Якщо є дефіцит активних днів - пріоритет віддаємо повністю порожнім дням.
        if active_day_deficit > 0:
            zero_days = np.where(day_loads == 0)[0]
            if len(zero_days) > 0:
                underloaded_day = int(max(zero_days, key=lambda d: self._count_free_slots_for_group_day(group_idx, int(d))))
            else:
                underloaded_day = int(np.argmin(day_loads))
        else:
            underloaded_day = int(np.argmin(day_loads))
        
        max_deviation = self._group_max_day_deviation(group_idx)
        if active_day_deficit == 0 and max_deviation <= self.MAX_DAY_DEVIATION + 0.5:
            return False  # Вже збалансовано
        
        # Шукаємо заняття для переміщення з overloaded_day
        for i, assignment in enumerate(self.assignments_list):
            course_idx, teacher_idx, a_group_idx, classroom_idx, timeslot_idx = assignment
            
            if a_group_idx != group_idx:
                continue
            
            day = self.timeslot_days[timeslot_idx]
            if day != overloaded_day:
                continue
            
            # Пробуємо знайти новий слот в underloaded_day
            new_slot = self._find_slot_in_day(course_idx, group_idx, teacher_idx, underloaded_day)
            
            if new_slot:
                new_teacher_idx, new_classroom_idx, new_timeslot_idx = new_slot
                
                # Перевіряємо що переміщення не погіршує баланс
                old_variance = np.var(day_loads)
                temp_loads = day_loads.copy()
                temp_loads[overloaded_day] -= 1
                temp_loads[underloaded_day] += 1
                new_variance = np.var(temp_loads)
                old_active_days = int(np.sum(day_loads > 0))
                new_active_days = int(np.sum(temp_loads > 0))
                old_active_day_deficit = max(0, expected_active_days - old_active_days)
                new_active_day_deficit = max(0, expected_active_days - new_active_days)
                
                if new_active_day_deficit >= old_active_day_deficit and new_variance >= old_variance:
                    continue  # Не погіршуємо баланс
                
                # Виконуємо переміщення
                # Видаляємо старе
                self.teacher_schedule[teacher_idx, timeslot_idx] -= 1
                self.group_schedule[group_idx, timeslot_idx] -= 1
                self.classroom_schedule[classroom_idx, timeslot_idx] -= 1
                self.group_classes_per_day[group_idx, overloaded_day] -= 1
                
                # Додаємо нове
                self.teacher_schedule[new_teacher_idx, new_timeslot_idx] += 1
                self.group_schedule[group_idx, new_timeslot_idx] += 1
                self.classroom_schedule[new_classroom_idx, new_timeslot_idx] += 1
                self.group_classes_per_day[group_idx, underloaded_day] += 1
                
                # Оновлюємо assignment
                self.assignments_list[i] = (course_idx, new_teacher_idx, group_idx, new_classroom_idx, new_timeslot_idx)
                
                logger.debug(f"   Moved: group {group_idx}, day {overloaded_day}->{underloaded_day}")
                return True
        
        return False
    
    def _find_slot_in_day(self, course_idx: int, group_idx: int, 
                          preferred_teacher_idx: int, target_day: int) -> Optional[Tuple[int, int, int]]:
        """Знаходить вільний слот у конкретний день."""
        course = self.courses[course_idx]
        course_id = course.id
        
        # Отримуємо викладачів
        teacher_ids = self.course_teacher_map.get(course_id, [t.id for t in self.teachers])
        teacher_indices = [self.teacher_idx[tid] for tid in teacher_ids if tid in self.teacher_idx]
        
        # Пріоритет - той самий викладач
        if preferred_teacher_idx in teacher_indices:
            teacher_indices.remove(preferred_teacher_idx)
            teacher_indices.insert(0, preferred_teacher_idx)
        
        # Шукаємо слоти в цей день
        for ts_idx in range(self.n_timeslots):
            if self.timeslot_days[ts_idx] != target_day:
                continue
            
            # Перевіряємо чи група вільна
            if self.group_schedule[group_idx, ts_idx] > 0:
                continue
            
            for teacher_idx in teacher_indices:
                if self.teacher_schedule[teacher_idx, ts_idx] > 0:
                    continue
                
                for classroom_idx in range(self.n_classrooms):
                    if self.classroom_schedule[classroom_idx, ts_idx] > 0:
                        continue
                    
                    if self.classroom_capacities[classroom_idx] < self.group_sizes[group_idx]:
                        continue
                    
                    return (teacher_idx, classroom_idx, ts_idx)
        
        return None

    def _count_free_slots_for_group_day(self, group_idx: int, target_day: int) -> int:
        """Рахує кількість вільних таймслотів для групи у конкретний день."""
        free_slots = 0
        for ts_idx in range(self.n_timeslots):
            if self.timeslot_days[ts_idx] != target_day:
                continue
            if self.group_schedule[group_idx, ts_idx] == 0:
                free_slots += 1
        return free_slots
    
    def _calculate_total_variance(self) -> float:
        """Обчислює загальну variance по всіх групах."""
        total = 0.0
        for group_idx in range(self.n_groups):
            total += np.var(self.group_classes_per_day[group_idx])
        return total / max(self.n_groups, 1)
    
    def _log_final_balance(self):
        """Логує фінальний стан балансу."""
        logger.info(f"📊 Final Balance Report:")
        for group_idx in range(self.n_groups):
            group = self.groups[group_idx]
            day_loads = self.group_classes_per_day[group_idx]
            target = self.target_lessons_per_day[group_idx]
            variance = np.var(day_loads)
            max_dev = self._group_max_day_deviation(group_idx)
            active_days, expected_active_days, _ = self._get_group_active_day_stats(group_idx)

            status = "✅" if (max_dev <= self.MAX_DAY_DEVIATION + 0.5 and active_days >= expected_active_days) else "⚠️"
            logger.info(
                f"   {status} {group.code}: {day_loads.tolist()}, target={target:.1f}, "
                f"var={variance:.2f}, max_dev={max_dev:.2f}, active_days={active_days}/{expected_active_days}"
            )

    def _find_best_balanced_slot(self, course_idx: int, group_idx: int) -> Optional[Tuple]:
        """
        Знаходить найкращий слот для заняття з урахуванням БАЛАНСУ.
        
        Пріоритет: дні з найменшим навантаженням.
        """
        course = self.courses[course_idx]
        course_id = course.id
        
        teacher_ids = self.course_teacher_map.get(course_id, [t.id for t in self.teachers])
        teacher_indices = [self.teacher_idx[tid] for tid in teacher_ids if tid in self.teacher_idx]
        
        if not teacher_indices:
            teacher_indices = list(range(self.n_teachers))
        
        # Сортуємо дні за навантаженням (менше = краще)
        day_loads = self.group_classes_per_day[group_idx]
        sorted_days = np.argsort(day_loads)  # Від найменш до найбільш завантаженого
        
        best_action = None
        best_score = float('-inf')
        
        # Пріоритетно шукаємо в менш завантажених днях
        for target_day in sorted_days:
            if best_action is not None:
                break  # Знайшли в менш завантаженому дні
            
            for teacher_idx in teacher_indices:
                for classroom_idx in range(self.n_classrooms):
                    # Перевірка місткості
                    if self.classroom_capacities[classroom_idx] < self.group_sizes[group_idx]:
                        continue
                    
                    for timeslot_idx in range(self.n_timeslots):
                        day = self.timeslot_days[timeslot_idx]
                        if day != target_day:
                            continue
                        
                        # Перевірка конфліктів
                        if (self.teacher_schedule[teacher_idx, timeslot_idx] > 0 or
                            self.group_schedule[group_idx, timeslot_idx] > 0 or
                            self.classroom_schedule[classroom_idx, timeslot_idx] > 0):
                            continue
                        
                        # Оцінка якості слота
                        score = self._evaluate_balanced_slot(
                            course_idx, group_idx, classroom_idx, timeslot_idx
                        )
                        
                        if score > best_score:
                            best_score = score
                            best_action = (course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx)
        
        return best_action

    def _find_best_slot(self, course_idx: int, group_idx: int) -> Optional[Tuple]:
        """Знаходить найкращий слот для заняття. LEGACY - використовуйте _find_best_balanced_slot."""
        return self._find_best_balanced_slot(course_idx, group_idx)

    def _evaluate_balanced_slot(self, course_idx: int, group_idx: int, 
                                classroom_idx: int, timeslot_idx: int) -> float:
        """Оцінює якість слота з акцентом на баланс."""
        score = 0.0
        
        day = self.timeslot_days[timeslot_idx]
        day_load = self.group_classes_per_day[group_idx, day]
        target = self.target_lessons_per_day[group_idx]
        _, _, active_day_deficit = self._get_group_active_day_stats(group_idx)
        
        # === ГОЛОВНИЙ ПРІОРИТЕТ: баланс ===
        # Бонус за день з навантаженням нижче target
        if day_load < target:
            score += 10 * (target - day_load)
        
        # Штраф за перевищення target
        if day_load >= target:
            score -= 5 * (day_load - target + 1)

        # Якщо є дефіцит активних днів - даємо пріоритет дням без занять.
        if active_day_deficit > 0:
            if day_load == 0:
                score += 12.0
            else:
                score -= 6.0
        
        # Мінімізація variance
        temp_loads = self.group_classes_per_day[group_idx].copy()
        temp_loads[day] += 1
        variance = np.var(temp_loads)
        score -= variance * 2
        
        # === ВТОРИННИЙ: середні пари ===
        period = self.timeslot_periods[timeslot_idx]
        score -= abs(period - 3)

        # === ДОДАТКОВО: компактність розкладу (менше "вікон") ===
        day_slots = np.where(self.timeslot_days == day)[0]
        occupied_periods = sorted(
            [int(self.timeslot_periods[ts]) for ts in day_slots if self.group_schedule[group_idx, ts] > 0]
        )
        if occupied_periods:
            min_distance = min(abs(int(period) - p) for p in occupied_periods)
            if min_distance == 1:
                score += 2.0
            elif min_distance >= 3:
                score -= 3.0

            before_gaps = self._count_day_gaps(occupied_periods)
            after_gaps = self._count_day_gaps(sorted(occupied_periods + [int(period)]))
            score -= (after_gaps - before_gaps) * 4.0
        
        # === ВТОРИННИЙ: тип аудиторії ===
        if self.course_requires_lab[course_idx] and self.classroom_types[classroom_idx] == 1:
            score += 3
        
        return score

    def _evaluate_slot(self, course_idx: int, group_idx: int, 
                       classroom_idx: int, timeslot_idx: int) -> float:
        """Оцінює якість слота для Local Search. LEGACY."""
        return self._evaluate_balanced_slot(course_idx, group_idx, classroom_idx, timeslot_idx)

    # === ДІАГНОСТИКА ===
    
    def get_diagnostic_info(self) -> Dict:
        """
        Повертає детальну діагностику стану розкладу.
        """
        scheduled = len(self.assignments_list)
        remaining = len(self.pending_courses)
        total = self.total_classes_to_schedule
        
        # Аналіз по курсах
        course_stats = []
        for course_idx, course in enumerate(self.courses):
            expected = course.hours_per_week if hasattr(course, 'hours_per_week') else 2
            # Рахуємо скільки годин заплановано
            scheduled_hours = sum(
                1 for a in self.assignments_list if a[0] == course_idx
            )
            remaining_hours = sum(
                1 for p in self.pending_courses if p[0] == course_idx
            )
            
            course_stats.append({
                "course": course.name,
                "expected_hours": expected,
                "scheduled_hours": scheduled_hours,
                "remaining_hours": remaining_hours,
                "complete": remaining_hours == 0
            })
        
        # Аналіз вільних слотів
        free_slots = 0
        for ts_idx in range(self.n_timeslots):
            for group_idx in range(self.n_groups):
                if self.group_schedule[group_idx, ts_idx] == 0:
                    # Перевіряємо чи є вільна аудиторія
                    has_free_classroom = np.any(self.classroom_schedule[:, ts_idx] == 0)
                    if has_free_classroom:
                        free_slots += 1
        
        # === БАЛАНС ПО ДНЯХ ===
        balance_stats = {}
        for group_idx in range(self.n_groups):
            group = self.groups[group_idx]
            day_loads = self.group_classes_per_day[group_idx]
            target = self.target_lessons_per_day[group_idx]
            variance = float(np.var(day_loads))
            active_days, expected_active_days, active_day_deficit = self._get_group_active_day_stats(group_idx)
            max_deviation = self._group_max_day_deviation(group_idx)
            
            balance_stats[group.code] = {
                "day_loads": day_loads.tolist(),
                "target_per_day": float(target),
                "variance": variance,
                "max_deviation": round(max_deviation, 2),
                "active_days": active_days,
                "target_active_days": expected_active_days,
                "active_day_deficit": active_day_deficit,
                "empty_days": int(np.sum(day_loads == 0)),
                "is_balanced": (max_deviation <= self.MAX_DAY_DEVIATION + 0.5) and (active_day_deficit == 0),
            }
        
        return {
            "total_to_schedule": total,
            "scheduled": scheduled,
            "remaining": remaining,
            "completion_rate": scheduled / max(total, 1),
            "hard_violations": self._count_hard_violations(),
            "soft_violations": self._count_soft_violations(),
            "free_slots_available": free_slots,
            "course_stats": course_stats,
            "incomplete_courses": [c for c in course_stats if not c["complete"]],
            # === НОВИЙ: balance info ===
            "balance_stats": balance_stats,
            "overall_balance_score": self._calculate_balance_score(),
            "is_schedule_balanced": self._check_balance_acceptable(),
            "total_variance": self._calculate_total_variance()
        }

    def explain_unfilled(self) -> List[str]:
        """
        Пояснює чому деякі заняття не вдалося запланувати.
        """
        explanations = []
        
        for course_idx, group_idx in self.pending_courses[:10]:  # Перші 10
            course = self.courses[course_idx]
            group = self.groups[group_idx]
            
            reasons = []
            
            # Перевіряємо кожен таймслот
            for ts_idx in range(self.n_timeslots):
                # Конфлікт групи
                if self.group_schedule[group_idx, ts_idx] > 0:
                    continue  # Група зайнята
                
                # Шукаємо вільну аудиторію з достатньою місткістю
                suitable_classrooms = [
                    c_idx for c_idx in range(self.n_classrooms)
                    if (self.classroom_schedule[c_idx, ts_idx] == 0 and
                        self.classroom_capacities[c_idx] >= self.group_sizes[group_idx])
                ]
                
                if not suitable_classrooms:
                    reasons.append(f"Таймслот {ts_idx}: немає вільних аудиторій з місткістю >= {self.group_sizes[group_idx]}")
                    continue
                
                # Шукаємо вільного викладача
                course_id = course.id
                teacher_ids = self.course_teacher_map.get(course_id, [t.id for t in self.teachers])
                
                available_teachers = [
                    tid for tid in teacher_ids
                    if tid in self.teacher_idx and 
                       self.teacher_schedule[self.teacher_idx[tid], ts_idx] == 0
                ]
                
                if not available_teachers:
                    reasons.append(f"Таймслот {ts_idx}: всі викладачі зайняті")
            
            if not reasons:
                reasons.append("Невідома причина - перевірте логіку")
            
            explanations.append(
                f"Курс '{course.name}' для групи '{group.code}': {'; '.join(reasons[:3])}"
            )
        
        return explanations
    
    def explain_imbalance(self) -> List[str]:
        """
        Пояснює чому певні групи мають незбалансований розклад.
        
        Returns:
            Список пояснень для кожної незбалансованої групи
        """
        explanations = []
        
        for group_idx in range(self.n_groups):
            group = self.groups[group_idx]
            day_loads = self.group_classes_per_day[group_idx]
            target = self.target_lessons_per_day[group_idx]

            if np.sum(day_loads) == 0:
                continue

            active_days, expected_active_days, active_day_deficit = self._get_group_active_day_stats(group_idx)
            max_deviation = self._group_max_day_deviation(group_idx)

            if max_deviation <= self.MAX_DAY_DEVIATION + 0.5 and active_day_deficit == 0:
                continue  # Група збалансована
            
            # Аналізуємо причини
            days_names = ["Пн", "Вт", "Ср", "Чт", "Пт"]
            overloaded_days = [days_names[d] for d in range(5) if day_loads[d] > target + 1]
            underloaded_days = [days_names[d] for d in range(5) if day_loads[d] < target - 1]
            
            reason_parts = []
            
            if overloaded_days:
                reason_parts.append(f"Перевантажені дні: {', '.join(overloaded_days)}")
            
            if underloaded_days:
                reason_parts.append(f"Недовантажені дні: {', '.join(underloaded_days)}")

            if active_day_deficit > 0:
                empty_days = [days_names[d] for d in range(5) if day_loads[d] == 0]
                if empty_days:
                    reason_parts.append(
                        f"Порожні дні: {', '.join(empty_days)} (active_days={active_days}/{expected_active_days})"
                    )
            
            # Перевіряємо чому не можна переmістити
            for overloaded_day_idx in [d for d in range(5) if day_loads[d] > target + 1]:
                for underloaded_day_idx in [d for d in range(5) if day_loads[d] < target - 1]:
                    # Шукаємо вільні слоти в недовантажений день
                    free_slots_in_target = sum(
                        1 for ts_idx in range(self.n_timeslots)
                        if self.timeslot_days[ts_idx] == underloaded_day_idx
                        and self.group_schedule[group_idx, ts_idx] == 0
                    )
                    
                    if free_slots_in_target == 0:
                        reason_parts.append(
                            f"Немає вільних слотів у {days_names[underloaded_day_idx]} для групи"
                        )
            
            explanation = f"Група '{group.code}': навантаження по днях {day_loads.tolist()}, "
            explanation += f"target={target:.1f}, max_dev={max_deviation:.2f}, active_days={active_days}/{expected_active_days}. "
            explanation += "; ".join(reason_parts) if reason_parts else "Причина невідома"
            
            explanations.append(explanation)
        
        return explanations

