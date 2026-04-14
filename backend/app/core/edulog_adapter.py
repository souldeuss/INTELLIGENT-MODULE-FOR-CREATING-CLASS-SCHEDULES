"""Adapter for converting EduLog payloads to and from imscheduler formats."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


class EduLogAdapter:
    """Stateless converter between EduLog entities and imscheduler JSON contracts."""

    GROUP_PREFIX = "cls_"
    SUBJECT_PREFIX = "subj_"
    TEACHER_PREFIX = "tch_"
    ROOM_PREFIX = "room_"
    VIRTUAL_ROOM_PREFIX = "vroom_"
    VIRTUAL_MODE_MARKER = "__virtual_mode__"

    DEFAULT_STUDENTS_COUNT = 25
    DEFAULT_ROOM_CAPACITY = 35
    DEFAULT_MAX_DAILY_LESSONS = 8

    def to_scheduler_input(self, school_data: dict) -> dict:
        """Convert EduLog school payload into imscheduler input format.

        Args:
            school_data: Plain dict containing EduLog-like entities in PascalCase.

        Returns:
            A dict compatible with imscheduler input.json schema.
        """
        classes = self._as_list(school_data.get("Classes"))
        subjects = self._as_list(school_data.get("Subjects"))
        teachers = self._as_list(school_data.get("Teachers"))
        class_subjects = self._as_list(school_data.get("ClassSubjects"))
        schedule_slots = self._as_list(school_data.get("ScheduleSlots"))
        classrooms = self._as_list(school_data.get("Classrooms"))
        constraints = school_data.get("Constraints") if isinstance(school_data.get("Constraints"), dict) else {}

        subject_by_id: Dict[str, Dict[str, Any]] = {}
        for subject in subjects:
            subject_id = self._id_str(subject.get("Id"))
            if subject_id is not None:
                subject_by_id[subject_id] = subject

        class_subject_pairs = self._extract_class_subject_pairs(class_subjects, subjects)
        active_subject_ids: Set[str] = {subject_id for _, subject_id in class_subject_pairs}
        if not active_subject_ids:
            active_subject_ids = {subject_id for subject_id in subject_by_id.keys()}

        groups_payload: List[Dict[str, Any]] = []
        for class_item in classes:
            class_id = self._id_str(class_item.get("Id"))
            if class_id is None:
                continue
            groups_payload.append(
                {
                    "id": self._encode_class_id(class_id),
                    "students_count": self._positive_int(
                        class_item.get("StudentsCount"),
                        default=self.DEFAULT_STUDENTS_COUNT,
                    ),
                }
            )

        subjects_payload: List[Dict[str, Any]] = []
        teacher_subjects: Dict[str, Set[str]] = defaultdict(set)
        for subject in subjects:
            subject_id = self._id_str(subject.get("Id"))
            if subject_id is None:
                continue
            scheduler_subject_id = self._encode_subject_id(subject_id)
            subjects_payload.append(
                {
                    "id": scheduler_subject_id,
                    "name": str(subject.get("Name") or f"Subject {subject_id}"),
                    "requires_specialized": self._to_bool(subject.get("RequiresSpecialized", False)),
                    "classroom_type": subject.get("ClassroomType"),
                    "difficulty": self._positive_int(subject.get("Difficulty"), default=1),
                }
            )

            teacher_id = self._id_str(subject.get("TeacherId"))
            if teacher_id is None:
                continue
            if subject_id in active_subject_ids:
                teacher_subjects[self._encode_teacher_id(teacher_id)].add(scheduler_subject_id)

        teachers_payload: List[Dict[str, Any]] = []
        for teacher in teachers:
            teacher_id = self._id_str(teacher.get("Id"))
            if teacher_id is None:
                continue
            scheduler_teacher_id = self._encode_teacher_id(teacher_id)
            teachers_payload.append(
                {
                    "id": scheduler_teacher_id,
                    "name": self._build_teacher_name(teacher, teacher_id),
                    "subjects": sorted(teacher_subjects.get(scheduler_teacher_id, set())),
                    "preferences": {},
                }
            )

        classrooms_payload, room_map = self._build_classrooms_payload(classes, teachers, classrooms)

        lessons_counter: Counter[Tuple[str, str, str]] = Counter()
        existing_schedule_payload: List[Dict[str, Any]] = []

        for slot in schedule_slots:
            class_id = self._id_str(slot.get("ClassId"))
            subject_id = self._id_str(slot.get("SubjectId"))
            teacher_id = self._id_str(slot.get("TeacherId"))
            if class_id is None or subject_id is None or teacher_id is None:
                continue

            scheduler_group_id = self._encode_class_id(class_id)
            scheduler_subject_id = self._encode_subject_id(subject_id)
            scheduler_teacher_id = self._encode_teacher_id(teacher_id)
            lessons_counter[(scheduler_subject_id, scheduler_teacher_id, scheduler_group_id)] += 1

            day_index = self._safe_int(slot.get("DayOfWeek"), default=1) - 1
            slot_index = self._safe_int(slot.get("LessonNumber"), default=1) - 1
            scheduler_room_id = self._resolve_room_id(slot.get("Room"), classrooms_payload, room_map)

            existing_schedule_payload.append(
                {
                    "subject": scheduler_subject_id,
                    "teacher": scheduler_teacher_id,
                    "group": scheduler_group_id,
                    "classroom": scheduler_room_id,
                    "day_index": day_index,
                    "slot_index": slot_index,
                }
            )

        lessons_pool_payload: List[Dict[str, Any]] = [
            {
                "subject": subject_id,
                "teacher": teacher_id,
                "group": group_id,
                "count": count,
            }
            for (subject_id, teacher_id, group_id), count in sorted(lessons_counter.items())
        ]

        if not lessons_pool_payload:
            lessons_pool_payload = self._fallback_lessons_pool(class_subject_pairs, subject_by_id)

        max_daily_lessons = self._extract_max_daily_lessons(constraints, schedule_slots)

        return {
            "groups": groups_payload,
            "subjects": subjects_payload,
            "teachers": teachers_payload,
            "classrooms": classrooms_payload,
            "lessons_pool": lessons_pool_payload,
            "existing_schedule": existing_schedule_payload,
            "constraints": {"max_daily_lessons": max_daily_lessons},
        }

    def from_scheduler_output(self, output: dict, school_id: int, academic_year_id: int) -> list[dict]:
        """Convert imscheduler output payload into EduLog ScheduleSlot-compatible rows.

        Args:
            output: Dict compatible with imscheduler output.json schema.
            school_id: EduLog school identifier.
            academic_year_id: EduLog academic year identifier.

        Returns:
            List of dictionaries compatible with EduLog ScheduleSlot fields.
        """
        schedule = self._as_list(output.get("schedule"))
        rows: List[Dict[str, Any]] = []

        for lesson in schedule:
            class_id = self._decode_prefixed_int(lesson.get("group"), self.GROUP_PREFIX)
            subject_id = self._decode_prefixed_int(lesson.get("subject"), self.SUBJECT_PREFIX)
            teacher_id = self._decode_prefixed_int(lesson.get("teacher"), self.TEACHER_PREFIX)
            if class_id is None or subject_id is None or teacher_id is None:
                continue

            day_index = self._safe_int(lesson.get("day_index"), default=-1)
            slot_index = self._safe_int(lesson.get("slot_index"), default=-1)
            if not 0 <= day_index <= 4:
                continue
            if not 0 <= slot_index <= 7:
                continue

            rows.append(
                {
                    "AcademicYearId": int(academic_year_id),
                    "ClassId": class_id,
                    "SubjectId": subject_id,
                    "TeacherId": teacher_id,
                    "DayOfWeek": day_index + 1,
                    "LessonNumber": slot_index + 1,
                    "Room": self._decode_room_value(lesson.get("classroom")),
                    "SchoolId": int(school_id),
                }
            )

        return rows

    def validate_mapping(self, input_data: dict) -> list[str]:
        """Validate mapping integrity of scheduler input data.

        Args:
            input_data: Dict in imscheduler input format.

        Returns:
            List of validation errors. Empty list means mapping is valid.
        """
        errors: List[str] = []

        required_sections = ["groups", "subjects", "teachers", "classrooms", "lessons_pool"]
        for section in required_sections:
            value = input_data.get(section)
            if not isinstance(value, list) or not value:
                errors.append(f"Missing or empty required section: {section}")

        groups = self._as_list(input_data.get("groups"))
        subjects = self._as_list(input_data.get("subjects"))
        teachers = self._as_list(input_data.get("teachers"))
        classrooms = self._as_list(input_data.get("classrooms"))
        lessons_pool = self._as_list(input_data.get("lessons_pool"))
        existing_schedule = self._as_list(input_data.get("existing_schedule"))

        group_ids = {self._id_str(item.get("id")) for item in groups if self._id_str(item.get("id")) is not None}
        subject_ids = {
            self._id_str(item.get("id"))
            for item in subjects
            if self._id_str(item.get("id")) is not None
        }
        teacher_ids = {
            self._id_str(item.get("id"))
            for item in teachers
            if self._id_str(item.get("id")) is not None
        }
        classroom_ids = {
            self._id_str(item.get("id"))
            for item in classrooms
            if self._id_str(item.get("id")) is not None
        }

        teacher_subject_map: Dict[str, Set[str]] = {}
        for teacher in teachers:
            teacher_id = self._id_str(teacher.get("id"))
            if teacher_id is None:
                continue
            teacher_subject_map[teacher_id] = {
                self._id_str(subject_id)
                for subject_id in self._as_list(teacher.get("subjects"))
                if self._id_str(subject_id) is not None
            }

        for index, lesson in enumerate(lessons_pool):
            subject_id = self._id_str(lesson.get("subject"))
            teacher_id = self._id_str(lesson.get("teacher"))
            group_id = self._id_str(lesson.get("group"))
            count = self._safe_int(lesson.get("count"), default=0)

            if subject_id is None or subject_id not in subject_ids:
                errors.append(f"lessons_pool[{index}] references unknown subject: {lesson.get('subject')}")
            if teacher_id is None or teacher_id not in teacher_ids:
                errors.append(f"lessons_pool[{index}] references unknown teacher: {lesson.get('teacher')}")
            if group_id is None or group_id not in group_ids:
                errors.append(f"lessons_pool[{index}] references unknown group: {lesson.get('group')}")
            if count <= 0:
                errors.append(f"lessons_pool[{index}] has non-positive count: {lesson.get('count')}")

            if (
                teacher_id is not None
                and subject_id is not None
                and teacher_id in teacher_subject_map
                and subject_id not in teacher_subject_map[teacher_id]
            ):
                errors.append(
                    f"lessons_pool[{index}] subject {subject_id} is not listed in teacher {teacher_id} subjects"
                )

        constraints = input_data.get("constraints")
        max_daily_lessons: Optional[int] = None
        if constraints is not None and not isinstance(constraints, dict):
            errors.append("constraints must be an object")
        if isinstance(constraints, dict):
            raw_max = constraints.get("max_daily_lessons")
            if raw_max is not None:
                max_daily_lessons = self._safe_int(raw_max, default=0)
                if max_daily_lessons <= 0:
                    errors.append("constraints.max_daily_lessons must be a positive integer")

        max_slot_index = 7
        if max_daily_lessons is not None and max_daily_lessons > 0:
            max_slot_index = max_daily_lessons - 1

        for index, slot in enumerate(existing_schedule):
            subject_id = self._id_str(slot.get("subject"))
            teacher_id = self._id_str(slot.get("teacher"))
            group_id = self._id_str(slot.get("group"))
            classroom_id = self._id_str(slot.get("classroom"))

            if subject_id is None or subject_id not in subject_ids:
                errors.append(f"existing_schedule[{index}] references unknown subject: {slot.get('subject')}")
            if teacher_id is None or teacher_id not in teacher_ids:
                errors.append(f"existing_schedule[{index}] references unknown teacher: {slot.get('teacher')}")
            if group_id is None or group_id not in group_ids:
                errors.append(f"existing_schedule[{index}] references unknown group: {slot.get('group')}")
            if classroom_id is None or classroom_id not in classroom_ids:
                errors.append(
                    f"existing_schedule[{index}] references unknown classroom: {slot.get('classroom')}"
                )

            day_index = self._safe_int(slot.get("day_index"), default=-1)
            slot_index = self._safe_int(slot.get("slot_index"), default=-1)
            if not 0 <= day_index <= 4:
                errors.append(f"existing_schedule[{index}] has invalid day_index: {slot.get('day_index')}")
            if slot_index < 0:
                errors.append(f"existing_schedule[{index}] has invalid slot_index: {slot.get('slot_index')}")
            elif slot_index > max_slot_index:
                if max_daily_lessons is not None and max_daily_lessons > 0:
                    errors.append(
                        f"existing_schedule[{index}] slot_index {slot_index} exceeds max_daily_lessons {max_daily_lessons}"
                    )
                else:
                    errors.append(
                        f"existing_schedule[{index}] has invalid slot_index: {slot.get('slot_index')}"
                    )

        return errors

    @classmethod
    def _extract_class_subject_pairs(
        cls,
        class_subjects: List[Dict[str, Any]],
        subjects: List[Dict[str, Any]],
    ) -> Set[Tuple[str, str]]:
        pairs: Set[Tuple[str, str]] = set()

        for relation in class_subjects:
            class_id = cls._id_str(relation.get("ClassId"))
            subject_id = cls._id_str(relation.get("SubjectId"))
            if class_id is not None and subject_id is not None:
                pairs.add((class_id, subject_id))

        for subject in subjects:
            subject_id = cls._id_str(subject.get("Id"))
            if subject_id is None:
                continue
            for relation in cls._as_list(subject.get("ClassSubjects")):
                class_id = cls._id_str(relation.get("ClassId"))
                if class_id is not None:
                    pairs.add((class_id, subject_id))

        return pairs

    def _fallback_lessons_pool(
        self,
        class_subject_pairs: Set[Tuple[str, str]],
        subject_by_id: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        lessons_pool: List[Dict[str, Any]] = []
        for class_id, subject_id in sorted(class_subject_pairs):
            subject = subject_by_id.get(subject_id)
            if not subject:
                continue
            teacher_id = self._id_str(subject.get("TeacherId"))
            if teacher_id is None:
                continue
            lessons_pool.append(
                {
                    "subject": self._encode_subject_id(subject_id),
                    "teacher": self._encode_teacher_id(teacher_id),
                    "group": self._encode_class_id(class_id),
                    "count": 1,
                }
            )
        return lessons_pool

    def _build_classrooms_payload(
        self,
        classes: List[Dict[str, Any]],
        teachers: List[Dict[str, Any]],
        classrooms: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        payload: List[Dict[str, Any]] = []
        room_map: Dict[str, str] = {}

        if classrooms:
            for index, room in enumerate(classrooms, start=1):
                source = room.get("Code") or room.get("Name") or room.get("Id") or f"room{index}"
                scheduler_id = self._encode_room_id(source)
                payload.append(
                    {
                        "id": scheduler_id,
                        "capacity": self._positive_int(room.get("Capacity"), default=self.DEFAULT_ROOM_CAPACITY),
                        "type": str(room.get("Type") or room.get("ClassroomType") or "general"),
                    }
                )

                for candidate in (
                    source,
                    room.get("Id"),
                    room.get("Code"),
                    room.get("Name"),
                    scheduler_id,
                ):
                    if candidate is not None and str(candidate).strip():
                        room_map[str(candidate)] = scheduler_id
            return payload, room_map

        virtual_rooms = max(len(classes), len(teachers), 1)
        for index in range(1, virtual_rooms + 1):
            room_id = f"{self.VIRTUAL_ROOM_PREFIX}{index}"
            payload.append(
                {
                    "id": room_id,
                    "capacity": self.DEFAULT_ROOM_CAPACITY,
                    "type": "general",
                }
            )
            room_map[room_id] = room_id

        room_map[self.VIRTUAL_MODE_MARKER] = "1"

        return payload, room_map

    def _resolve_room_id(
        self,
        room_value: Any,
        classrooms_payload: List[Dict[str, Any]],
        room_map: Dict[str, str],
    ) -> str:
        if not classrooms_payload:
            return ""

        if room_value is None or not str(room_value).strip():
            return classrooms_payload[0]["id"]

        room_key = str(room_value)
        mapped = room_map.get(room_key)
        if mapped:
            return mapped

        if room_map.get(self.VIRTUAL_MODE_MARKER) == "1":
            return classrooms_payload[0]["id"]

        scheduler_id = self._encode_room_id(room_key)
        existing_ids = {room["id"] for room in classrooms_payload}
        if scheduler_id not in existing_ids:
            classrooms_payload.append(
                {
                    "id": scheduler_id,
                    "capacity": self.DEFAULT_ROOM_CAPACITY,
                    "type": "general",
                }
            )
        room_map[room_key] = scheduler_id
        room_map[scheduler_id] = scheduler_id
        return scheduler_id

    def _extract_max_daily_lessons(self, constraints: Dict[str, Any], schedule_slots: List[Dict[str, Any]]) -> int:
        raw_value = constraints.get("MaxDailyLessons")
        if raw_value is None:
            raw_value = constraints.get("max_daily_lessons")

        if raw_value is not None:
            parsed = self._safe_int(raw_value, default=0)
            if parsed > 0:
                return parsed

        inferred = 0
        for slot in schedule_slots:
            inferred = max(inferred, self._safe_int(slot.get("LessonNumber"), default=0))
        if inferred > 0:
            return inferred

        return self.DEFAULT_MAX_DAILY_LESSONS

    @staticmethod
    def _build_teacher_name(teacher: Dict[str, Any], fallback_id: str) -> str:
        parts = [
            str(teacher.get("Surname") or "").strip(),
            str(teacher.get("Name") or "").strip(),
            str(teacher.get("Patronymic") or "").strip(),
        ]
        full_name = " ".join(part for part in parts if part).strip()
        if full_name:
            return full_name
        return str(teacher.get("Name") or f"Teacher {fallback_id}")

    @classmethod
    def _encode_class_id(cls, value: Any) -> str:
        return f"{cls.GROUP_PREFIX}{cls._room_token(value)}"

    @classmethod
    def _encode_subject_id(cls, value: Any) -> str:
        return f"{cls.SUBJECT_PREFIX}{cls._room_token(value)}"

    @classmethod
    def _encode_teacher_id(cls, value: Any) -> str:
        return f"{cls.TEACHER_PREFIX}{cls._room_token(value)}"

    @classmethod
    def _encode_room_id(cls, value: Any) -> str:
        return f"{cls.ROOM_PREFIX}{cls._room_token(value)}"

    @classmethod
    def _decode_prefixed_int(cls, value: Any, prefix: str) -> Optional[int]:
        text = cls._id_str(value)
        if text is None or not text.startswith(prefix):
            return None
        suffix = text[len(prefix) :]
        if not suffix:
            return None
        try:
            return int(suffix)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _decode_room_value(cls, value: Any) -> str:
        text = str(value or "")
        if text.startswith(cls.ROOM_PREFIX):
            return text[len(cls.ROOM_PREFIX) :]
        return text

    @staticmethod
    def _as_list(value: Any) -> List[Any]:
        return list(value) if isinstance(value, list) else []

    @staticmethod
    def _id_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _positive_int(cls, value: Any, default: int) -> int:
        parsed = cls._safe_int(value, default=default)
        return parsed if parsed > 0 else default

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        if isinstance(value, (int, float)):
            return value != 0
        return False

    @staticmethod
    def _room_token(value: Any) -> str:
        text = str(value).strip()
        if not text:
            return "unknown"
        normalized = []
        for char in text:
            if char.isalnum() or char in {"_", "-"}:
                normalized.append(char)
            else:
                normalized.append("_")
        token = "".join(normalized).strip("_")
        return token or "unknown"
