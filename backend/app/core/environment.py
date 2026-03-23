"""DRL Environment для University Course Timetabling Problem."""
import numpy as np
import torch
from typing import Dict, List, Optional, Tuple

from ..models.database import Course, Teacher, StudentGroup, Classroom, Timeslot


class TimetablingEnvironment:
    """Середовище для DRL агента."""

    def __init__(
        self,
        courses: List[Course],
        teachers: List[Teacher],
        groups: List[StudentGroup],
        classrooms: List[Classroom],
        timeslots: List[Timeslot],
    ):
        self.courses = courses
        self.teachers = teachers
        self.groups = groups
        self.classrooms = classrooms
        self.timeslots = timeslots

        # Індексування для швидкого доступу
        self.course_idx = {c.id: idx for idx, c in enumerate(courses)}
        self.teacher_idx = {t.id: idx for idx, t in enumerate(teachers)}
        self.group_idx = {g.id: idx for idx, g in enumerate(groups)}
        self.classroom_idx = {r.id: idx for idx, r in enumerate(classrooms)}
        self.timeslot_idx = {ts.id: idx for idx, ts in enumerate(timeslots)}

        # Розміри для векторизації
        self.n_courses = len(courses)
        self.n_teachers = len(teachers)
        self.n_groups = len(groups)
        self.n_classrooms = len(classrooms)
        self.n_timeslots = len(timeslots)

        # Стан: матриці призначень
        self.reset()

    def reset(self) -> np.ndarray:
        """Скидає середовище до початкового стану."""
        # Матриця призначень: [course, teacher, group, classroom, timeslot]
        self.assignments = np.zeros(
            (self.n_courses, self.n_teachers, self.n_groups, self.n_classrooms, self.n_timeslots),
            dtype=np.float32,
        )

        # Лічильники зайнятості
        self.teacher_schedule = np.zeros((self.n_teachers, self.n_timeslots), dtype=np.int32)
        self.group_schedule = np.zeros((self.n_groups, self.n_timeslots), dtype=np.int32)
        self.classroom_schedule = np.zeros((self.n_classrooms, self.n_timeslots), dtype=np.int32)

        # Створюємо список занять що потрібно запланувати (курс + група + раз на тиждень)
        # Кожен курс для кожної групи повинен бути запланований hours_per_week разів
        self.pending_courses = []
        for course_idx, course in enumerate(self.courses):
            hours = course.hours_per_week or 2  # За замовчуванням 2 години
            # Для кожної групи створюємо потрібну кількість занять
            for group_idx in range(self.n_groups):
                for _ in range(hours):
                    self.pending_courses.append((course_idx, group_idx))
        
        self.current_step = 0
        self.max_steps = len(self.pending_courses)

        return self._get_state()

    def _get_state(self) -> np.ndarray:
        """Повертає векторизований стан для нейромережі."""
        # Flatten assignments + schedules
        flat_assignments = self.assignments.flatten()
        flat_teacher_schedule = self.teacher_schedule.flatten()
        flat_group_schedule = self.group_schedule.flatten()
        flat_classroom_schedule = self.classroom_schedule.flatten()

        # Додаткові ознаки
        progress = np.array([self.current_step / max(self.max_steps, 1)])  # Нормалізований прогрес
        pending_count = np.array([len(self.pending_courses) / max(self.max_steps, 1)])

        state = np.concatenate(
            [
                flat_assignments,
                flat_teacher_schedule,
                flat_group_schedule,
                flat_classroom_schedule,
                progress,
                pending_count,
            ]
        )
        return state.astype(np.float32)

    def step(self, action: Tuple[int, int, int, int, int]) -> Tuple[np.ndarray, float, bool, Dict]:
        """Виконує дію: призначає (course, teacher, group, classroom, timeslot)."""
        course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx = action

        # Перевірка валідності - чи є така комбінація в pending
        target = (course_idx, group_idx)
        if target not in self.pending_courses:
            reward = -10.0  # Спроба призначити вже призначене заняття
            return self._get_state(), reward, False, {"error": "class_already_assigned"}

        # Обчислення винагороди
        reward = self._calculate_reward(course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx)

        # Оновлення стану
        self.assignments[course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx] = 1.0
        self.teacher_schedule[teacher_idx, timeslot_idx] += 1
        self.group_schedule[group_idx, timeslot_idx] += 1
        self.classroom_schedule[classroom_idx, timeslot_idx] += 1

        self.pending_courses.remove(target)
        self.current_step += 1

        # Перевірка завершення
        done = len(self.pending_courses) == 0

        info = {
            "hard_violations": self._count_hard_violations(),
            "soft_violations": self._count_soft_violations(),
        }

        return self._get_state(), reward, done, info

    def _calculate_reward(
        self,
        course_idx: int,
        teacher_idx: int,
        group_idx: int,
        classroom_idx: int,
        timeslot_idx: int,
    ) -> float:
        """Обчислює винагороду за дію."""
        reward = 0.0

        # Жорсткі обмеження (великі штрафи)
        if self.teacher_schedule[teacher_idx, timeslot_idx] > 0:
            reward -= 5.0  # Конфлікт викладача
        if self.group_schedule[group_idx, timeslot_idx] > 0:
            reward -= 5.0  # Конфлікт групи
        if self.classroom_schedule[classroom_idx, timeslot_idx] > 0:
            reward -= 5.0  # Конфлікт аудиторії

        # Перевірка місткості
        classroom = self.classrooms[classroom_idx]
        group = self.groups[group_idx]
        if classroom.capacity < group.students_count:
            reward -= 3.0  # Недостатня місткість

        # М'які обмеження (малі штрафи/бонуси)
        course = self.courses[course_idx]
        if course.requires_lab and classroom.classroom_type != "lab":
            reward -= 1.0  # Немає лабораторії
        if course.preferred_classroom_type and classroom.classroom_type == course.preferred_classroom_type:
            reward += 0.5  # Бажаний тип аудиторії

        # === РІВНОМІРНИЙ РОЗПОДІЛ УРОКІВ ПО ЧАСОВИХ СЛОТАХ ===
        # Штраф за концентрацію занять групи в одному слоті
        group_load_in_slot = self.group_schedule[group_idx, timeslot_idx]
        if group_load_in_slot > 0:
            reward -= 3.0  # Сильний штраф - уже є заняття в цьому слоті для групи
        
        # Бонус за рівномірний розподіл - вибираємо слоти з меншим навантаженням
        total_group_classes = np.sum(self.group_schedule[group_idx])
        if total_group_classes > 0:
            # Середнє навантаження на слот
            avg_load = total_group_classes / self.n_timeslots
            current_slot_load = self.group_schedule[group_idx, timeslot_idx]
            if current_slot_load < avg_load:
                reward += 1.0  # Бонус за вибір менш завантаженого слота
            elif current_slot_load > avg_load + 1:
                reward -= 2.0  # Штраф за перевантаження слота
        
        # Бонус за розподіл по різних днях тижня (timeslot містить день)
        timeslot = self.timeslots[timeslot_idx]
        day = timeslot.day_of_week
        
        # Підрахувати скільки занять у групи в цей день
        classes_this_day = 0
        for ts_idx, ts in enumerate(self.timeslots):
            if ts.day_of_week == day:
                classes_this_day += self.group_schedule[group_idx, ts_idx]
        
        # Штраф за забагато занять в один день (більше 4)
        if classes_this_day >= 4:
            reward -= 1.5
        elif classes_this_day >= 3:
            reward -= 0.5
        
        # Бонус за перший урок в цей день (розподіл по днях)
        if classes_this_day == 0:
            reward += 1.0

        # Бонус за відсутність конфліктів
        if reward >= 0:
            reward += 1.0

        return reward

    def _count_hard_violations(self) -> int:
        """Підраховує порушення жорстких обмежень."""
        violations = 0
        violations += np.sum(self.teacher_schedule > 1)
        violations += np.sum(self.group_schedule > 1)
        violations += np.sum(self.classroom_schedule > 1)
        return int(violations)

    def _count_soft_violations(self) -> int:
        """Підраховує порушення м'яких обмежень."""
        violations = 0
        # Тут можна додати логіку для м'яких обмежень
        # Наприклад, перевірка бажаних часів викладачів
        return violations

    def get_valid_actions(self) -> List[Tuple[int, int, int, int, int]]:
        """Повертає список валідних дій для поточного стану, відсортованих за пріоритетом."""
        if not self.pending_courses:
            return []

        valid_actions = []
        # Для простоти беремо перший курс із pending
        course_idx = self.pending_courses[0]

        # Створюємо список дій з оцінкою пріоритету
        actions_with_priority = []

        # Перебираємо всі комбінації teacher/group/classroom/timeslot
        for teacher_idx in range(self.n_teachers):
            for group_idx in range(self.n_groups):
                for classroom_idx in range(self.n_classrooms):
                    for timeslot_idx in range(self.n_timeslots):
                        # Перевірка базових конфліктів
                        if (
                            self.teacher_schedule[teacher_idx, timeslot_idx] == 0
                            and self.group_schedule[group_idx, timeslot_idx] == 0
                            and self.classroom_schedule[classroom_idx, timeslot_idx] == 0
                        ):
                            # Обчислюємо пріоритет (менше - краще)
                            priority = 0
                            
                            # Пріоритет для рівномірного розподілу по слотах
                            # Менше занять у групи в цьому слоті - вищий пріоритет
                            priority += self.group_schedule[group_idx, timeslot_idx] * 10
                            
                            # Пріоритет по днях - менше занять в день = вищий пріоритет
                            timeslot = self.timeslots[timeslot_idx]
                            day = timeslot.day_of_week
                            classes_this_day = sum(
                                self.group_schedule[group_idx, ts_idx]
                                for ts_idx, ts in enumerate(self.timeslots)
                                if ts.day_of_week == day
                            )
                            priority += classes_this_day * 5
                            
                            # Пріоритет по номеру пари - розподіляємо рівномірно
                            period = timeslot.period_number
                            priority += abs(period - 3) * 2  # Середні пари мають пріоритет
                            
                            actions_with_priority.append((
                                (course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx),
                                priority
                            ))

        # Сортуємо за пріоритетом і беремо тільки дії
        actions_with_priority.sort(key=lambda x: x[1])
        valid_actions = [action for action, _ in actions_with_priority]
        
        # Обмежуємо кількість для швидкодії
        return valid_actions[:1000] if len(valid_actions) > 1000 else valid_actions
