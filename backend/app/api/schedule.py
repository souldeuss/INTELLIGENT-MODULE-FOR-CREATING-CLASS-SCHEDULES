"""Schedule Generation API."""
import csv
import io
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, UploadFile, File
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import threading
import logging
import json
import os
from pathlib import Path
from datetime import datetime

from ..models.database import (
    Course,
    Teacher,
    StudentGroup,
    Classroom,
    Timeslot,
    ScheduledClass,
    ScheduleGeneration,
)
from ..schemas.schemas import (
    ScheduleGenerationRequest,
    ScheduleGenerationStatus,
    ScheduledClassResponse,
    ScheduledClassFullResponse,
    ScheduledClassUpdate,
    ScheduledClassLock,
    AnalyticsResponse,
    ClassroomUtilization,
    TeacherWorkload,
)
from ..core.database_session import get_db

# Імпортуємо V2 версії з гарантією повноти (з fallback на оптимізовані та оригінальні)
try:
    from ..core.environment_v2 import TimetablingEnvironmentV2 as TimetablingEnvironment
    from ..core.ppo_trainer_v2 import PPOTrainerV2 as PPOTrainer
    USING_V2 = True
    USING_OPTIMIZED = False
except ImportError:
    try:
        from ..core.environment_optimized import OptimizedTimetablingEnvironment as TimetablingEnvironment
        from ..core.ppo_trainer_optimized import OptimizedPPOTrainer as PPOTrainer
        USING_V2 = False
        USING_OPTIMIZED = True
    except ImportError:
        from ..core.environment import TimetablingEnvironment
        from ..core.ppo_trainer import PPOTrainer
        USING_V2 = False
        USING_OPTIMIZED = False

router = APIRouter()
logger = logging.getLogger(__name__)

if USING_V2:
    logger.info("🚀 Використовуємо V2 версії Environment та PPOTrainer (з гарантією повноти)")
elif USING_OPTIMIZED:
    logger.info("🔧 Використовуємо оптимізовані версії Environment та PPOTrainer")
else:
    logger.info("⚠️ Використовуємо оригінальні версії")

# Директорія для збереження розкладів
SCHEDULES_DIR = Path("./saved_schedules")
SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)


def _calculate_schedule_score(db: Session, scheduled_classes: List[ScheduledClass]) -> Dict[str, Any]:
    """Calculate 0-100 schedule quality score and violation counters."""
    if not scheduled_classes:
        return {
            "overall": 0.0,
            "hard_violations": 0,
            "soft_violations": 0,
        }

    total_classes = len(scheduled_classes)

    timeslot_classes: Dict[int, List[ScheduledClass]] = {}
    for scheduled_class in scheduled_classes:
        timeslot_classes.setdefault(scheduled_class.timeslot_id, []).append(scheduled_class)

    teacher_conflicts = 0
    room_conflicts = 0
    group_conflicts = 0
    for classes in timeslot_classes.values():
        if len(classes) < 2:
            continue
        teacher_ids = [c.teacher_id for c in classes]
        room_ids = [c.classroom_id for c in classes]
        group_ids = [c.group_id for c in classes]

        teacher_conflicts += len(teacher_ids) - len(set(teacher_ids))
        room_conflicts += len(room_ids) - len(set(room_ids))
        group_conflicts += len(group_ids) - len(set(group_ids))

    capacity_issues = 0
    day_distribution = [0] * 5

    for scheduled_class in scheduled_classes:
        group = db.query(StudentGroup).filter(StudentGroup.id == scheduled_class.group_id).first()
        classroom = db.query(Classroom).filter(Classroom.id == scheduled_class.classroom_id).first()
        if group and classroom and group.students_count > classroom.capacity:
            capacity_issues += 1

        timeslot = db.query(Timeslot).filter(Timeslot.id == scheduled_class.timeslot_id).first()
        if timeslot and 0 <= timeslot.day_of_week < 5:
            day_distribution[timeslot.day_of_week] += 1

    avg_per_day = total_classes / 5
    distribution_variance = sum((day_count - avg_per_day) ** 2 for day_count in day_distribution) / 5
    max_variance = (total_classes ** 2) / 5
    distribution_score = (
        100 * (1 - min(distribution_variance / max_variance, 1)) if max_variance > 0 else 100
    )

    teacher_score = max(0, 100 - (teacher_conflicts * 20))
    room_score = max(0, 100 - (room_conflicts * 20))
    group_score = max(0, 100 - (group_conflicts * 20))
    gap_score = max(0, 100 - (capacity_issues * 10))

    overall = (
        teacher_score * 0.25
        + room_score * 0.25
        + group_score * 0.25
        + gap_score * 0.15
        + distribution_score * 0.10
    )

    return {
        "overall": round(overall, 1),
        "hard_violations": int(teacher_conflicts + room_conflicts + group_conflicts),
        "soft_violations": int(capacity_issues),
    }


def _build_lessons_export_rows(db: Session, scheduled_classes: List[ScheduledClass]) -> List[List[str]]:
    """Build rows for lessons CSV template:
    Teacher Names,Class Names,Subject Names,Room Names,No. of Lessons,Length.
    """
    if not scheduled_classes:
        return []

    teacher_ids = {item.teacher_id for item in scheduled_classes}
    group_ids = {item.group_id for item in scheduled_classes}
    course_ids = {item.course_id for item in scheduled_classes}
    classroom_ids = {item.classroom_id for item in scheduled_classes}
    timeslot_ids = {item.timeslot_id for item in scheduled_classes}

    teachers = (
        db.query(Teacher).filter(Teacher.id.in_(teacher_ids)).all() if teacher_ids else []
    )
    groups = (
        db.query(StudentGroup).filter(StudentGroup.id.in_(group_ids)).all() if group_ids else []
    )
    courses = (
        db.query(Course).filter(Course.id.in_(course_ids)).all() if course_ids else []
    )
    classrooms = (
        db.query(Classroom).filter(Classroom.id.in_(classroom_ids)).all() if classroom_ids else []
    )
    timeslots = (
        db.query(Timeslot).filter(Timeslot.id.in_(timeslot_ids)).all() if timeslot_ids else []
    )

    teacher_map = {item.id: item for item in teachers}
    group_map = {item.id: item for item in groups}
    course_map = {item.id: item for item in courses}
    classroom_map = {item.id: item for item in classrooms}
    timeslot_map = {item.id: item for item in timeslots}

    periods_by_key: Dict[Tuple[str, str, str, str], Dict[int, List[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    lesson_counter: Dict[Tuple[str, str, str, str, int], int] = defaultdict(int)

    for scheduled_class in scheduled_classes:
        teacher = teacher_map.get(scheduled_class.teacher_id)
        group = group_map.get(scheduled_class.group_id)
        course = course_map.get(scheduled_class.course_id)
        classroom = classroom_map.get(scheduled_class.classroom_id)
        timeslot = timeslot_map.get(scheduled_class.timeslot_id)

        teacher_name = teacher.full_name if teacher else f"Teacher {scheduled_class.teacher_id}"
        class_name = group.code if group else f"Group {scheduled_class.group_id}"
        subject_name = course.name if course else f"Course {scheduled_class.course_id}"
        room_name = classroom.code if classroom else ""
        key = (teacher_name, class_name, subject_name, room_name)

        if not timeslot:
            lesson_counter[(teacher_name, class_name, subject_name, room_name, 1)] += 1
            continue

        periods_by_key[key][timeslot.day_of_week].append(timeslot.period_number)

    for key, day_periods in periods_by_key.items():
        teacher_name, class_name, subject_name, room_name = key

        for periods in day_periods.values():
            sorted_periods = sorted(set(periods))
            if not sorted_periods:
                continue

            current_length = 1
            for idx in range(1, len(sorted_periods)):
                if sorted_periods[idx] == sorted_periods[idx - 1] + 1:
                    current_length += 1
                else:
                    lesson_counter[(teacher_name, class_name, subject_name, room_name, current_length)] += 1
                    current_length = 1

            lesson_counter[(teacher_name, class_name, subject_name, room_name, current_length)] += 1

    rows: List[List[str]] = []
    sorted_keys = sorted(
        lesson_counter.keys(),
        key=lambda item: (item[0].lower(), item[1].lower(), item[2].lower(), item[3].lower(), item[4]),
    )

    for teacher_name, class_name, subject_name, room_name, length in sorted_keys:
        lessons_count = lesson_counter[(teacher_name, class_name, subject_name, room_name, length)]
        rows.append(
            [
                teacher_name,
                class_name,
                subject_name,
                room_name,
                str(lessons_count),
                str(length),
            ]
        )

    return rows


ASSIGNMENTS_TEMPLATE_HEADERS = [
    "Teacher Names",
    "Class Names",
    "Subject Names",
    "Room Names",
    "No. of Lessons",
    "Length",
]


def _normalize_lookup_value(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _normalize_header_value(value: str) -> str:
    return " ".join((value or "").replace("\ufeff", "").strip().lower().split())


def _split_template_values(raw_value: str) -> List[str]:
    if not raw_value:
        return []
    return [part.strip() for part in raw_value.split("&") if part and part.strip()]


def _decode_csv_text(raw_bytes: bytes) -> Tuple[str, str]:
    encodings = ["utf-8-sig", "utf-8", "cp1251", "windows-1251", "utf-16"]
    for encoding in encodings:
        try:
            return raw_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="CSV encoding is not supported")


def _build_csv_dict_reader(csv_text: str) -> Tuple[csv.DictReader, str]:
    sample = csv_text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        delimiter = dialect.delimiter
    except csv.Error:
        dialect = csv.excel
        delimiter = ","

    reader = csv.DictReader(io.StringIO(csv_text), dialect=dialect)
    return reader, delimiter


def _build_assignments_export_rows(db: Session) -> List[List[str]]:
    """Build rows for assignments CSV template used by import."""
    courses = db.query(Course).all()
    rows: List[List[str]] = []

    for course in courses:
        if not course.teachers or not course.groups:
            continue

        teacher_names = " & ".join(
            sorted({teacher.full_name for teacher in course.teachers if teacher.full_name})
        )
        class_names = " & ".join(
            sorted(
                {
                    group.code[6:].strip()
                    if group.code and group.code.lower().startswith("grade ")
                    else (group.code or "").strip()
                    for group in course.groups
                    if group.code and group.code.strip()
                }
            )
        )

        room_names = ""
        room_codes = {
            item.classroom.code
            for item in db.query(ScheduledClass).filter(ScheduledClass.course_id == course.id).all()
            if item.classroom and item.classroom.code
        }
        if room_codes:
            room_names = " & ".join(sorted(room_codes))

        lessons_per_week = course.hours_per_week if course.hours_per_week and course.hours_per_week > 0 else 1

        rows.append(
            [
                teacher_names,
                class_names,
                course.name,
                room_names,
                str(lessons_per_week),
                "1",
            ]
        )

    rows.sort(key=lambda row: (row[2].lower(), row[0].lower(), row[1].lower()))
    return rows


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _normalize_model_name(model_name: str) -> str:
    return model_name if model_name.endswith(".pt") else f"{model_name}.pt"


def _candidate_model_dirs() -> List[Path]:
    root = _workspace_root()
    candidates = [
        root / "saved_models",
        root / "backend" / "saved_models",
        root / "backend" / "backend" / "saved_models",
    ]

    existing = [path for path in candidates if path.exists()]
    if existing:
        return existing

    # Keep old behavior as fallback while creating default dir for future saves.
    candidates[0].mkdir(parents=True, exist_ok=True)
    return [candidates[0]]


def _resolve_model_dir_for_schedule(
    model_version: Optional[str] = None,
    expected_state_dim: Optional[int] = None,
    expected_action_dim: Optional[int] = None,
) -> Path:
    dirs = _candidate_model_dirs()

    if model_version:
        selected_model_path = _resolve_model_path(
            model_version,
            expected_state_dim=expected_state_dim,
            expected_action_dim=expected_action_dim,
        )
        if selected_model_path is not None:
            return selected_model_path.parent

    if expected_state_dim is not None and expected_action_dim is not None:
        for model_dir in dirs:
            best_path = model_dir / "actor_critic_best.pt"
            meta_info = _read_model_meta_dimensions_for_path(best_path)
            if (
                best_path.exists()
                and meta_info.get("meta_found")
                and meta_info.get("state_dim") == expected_state_dim
                and meta_info.get("action_dim") == expected_action_dim
            ):
                return model_dir

    ranked = sorted(
        dirs,
        key=lambda p: (
            len(list(p.glob("actor_critic_*.pt"))),
            max((f.stat().st_mtime for f in p.glob("actor_critic_*.pt")), default=0.0),
        ),
        reverse=True,
    )
    return ranked[0]


def _model_exists_in_any_dir(model_version: str) -> bool:
    target_name = _normalize_model_name(model_version)
    return any((model_dir / target_name).exists() for model_dir in _candidate_model_dirs())


def _list_model_candidates(model_version: str) -> List[Path]:
    target_name = _normalize_model_name(model_version)
    candidates: List[Path] = []
    for model_dir in _candidate_model_dirs():
        candidate = model_dir / target_name
        if candidate.exists():
            candidates.append(candidate)
    return candidates


def _read_model_meta_dimensions_for_path(model_path: Path) -> Dict[str, Any]:
    if not model_path.exists():
        return {
            "model_found": False,
            "meta_found": False,
            "state_dim": None,
            "action_dim": None,
            "model_path": str(model_path),
        }

    stem = model_path.stem
    run_id: Optional[str] = None
    if stem.startswith("actor_critic_"):
        run_id = stem.replace("actor_critic_", "", 1)
    elif stem == "actor_critic_best":
        run_id = "best"

    if not run_id:
        return {
            "model_found": True,
            "meta_found": False,
            "state_dim": None,
            "action_dim": None,
            "model_path": str(model_path),
        }

    meta_path = model_path.parent / f"meta_{run_id}.json"
    if not meta_path.exists():
        return {
            "model_found": True,
            "meta_found": False,
            "state_dim": None,
            "action_dim": None,
            "model_path": str(model_path),
        }

    try:
        with open(meta_path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return {
            "model_found": True,
            "meta_found": False,
            "state_dim": None,
            "action_dim": None,
            "model_path": str(model_path),
        }

    raw_state_dim = payload.get("state_dim")
    raw_action_dim = payload.get("action_dim")
    state_dim = int(raw_state_dim) if isinstance(raw_state_dim, (int, float)) else None
    action_dim = int(raw_action_dim) if isinstance(raw_action_dim, (int, float)) else None

    return {
        "model_found": True,
        "meta_found": True,
        "state_dim": state_dim,
        "action_dim": action_dim,
        "model_path": str(model_path),
    }


def _resolve_model_path(
    model_version: str,
    expected_state_dim: Optional[int] = None,
    expected_action_dim: Optional[int] = None,
) -> Optional[Path]:
    candidates = _list_model_candidates(model_version)
    if not candidates:
        return None

    if expected_state_dim is not None and expected_action_dim is not None:
        for candidate in candidates:
            meta = _read_model_meta_dimensions_for_path(candidate)
            if (
                meta.get("meta_found")
                and meta.get("state_dim") == expected_state_dim
                and meta.get("action_dim") == expected_action_dim
            ):
                return candidate

    return candidates[0]


def _find_compatible_model_candidate(
    expected_state_dim: Optional[int],
    expected_action_dim: Optional[int],
) -> Optional[Path]:
    if expected_state_dim is None or expected_action_dim is None:
        return None

    compatible_candidates: List[Path] = []
    for model_dir in _candidate_model_dirs():
        for candidate in model_dir.glob("actor_critic_*.pt"):
            meta = _read_model_meta_dimensions_for_path(candidate)
            if (
                meta.get("meta_found")
                and meta.get("state_dim") == expected_state_dim
                and meta.get("action_dim") == expected_action_dim
            ):
                compatible_candidates.append(candidate)

    if not compatible_candidates:
        return None

    compatible_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return compatible_candidates[0]


def _extract_model_run_id(model_version: str) -> Optional[str]:
    normalized = _normalize_model_name(model_version)
    stem = Path(normalized).stem
    if stem.startswith("actor_critic_"):
        return stem.replace("actor_critic_", "", 1)
    if stem == "actor_critic_best":
        return "best"
    return None


def _read_model_meta_dimensions(model_version: str) -> Dict[str, Any]:
    model_path = _resolve_model_path(model_version)
    if not model_path:
        return {
            "model_found": False,
            "meta_found": False,
            "state_dim": None,
            "action_dim": None,
            "model_path": None,
        }
    return _read_model_meta_dimensions_for_path(model_path)


def _build_environment_dimensions(db: Session) -> Dict[str, int]:
    courses = db.query(Course).all()
    teachers = db.query(Teacher).all()
    groups = db.query(StudentGroup).all()
    classrooms = db.query(Classroom).all()
    timeslots = db.query(Timeslot).filter(Timeslot.is_active == True).all()

    if not all([courses, teachers, groups, classrooms, timeslots]):
        raise ValueError("Insufficient data: ensure courses, teachers, groups, classrooms, and timeslots exist")

    course_teacher_map = {}
    course_group_map = {}

    for course in courses:
        if hasattr(course, "teachers") and course.teachers:
            course_teacher_map[course.id] = [t.id for t in course.teachers]
        else:
            course_teacher_map[course.id] = [t.id for t in teachers]

        if hasattr(course, "groups") and course.groups:
            course_group_map[course.id] = [g.id for g in course.groups]
        else:
            course_group_map[course.id] = [g.id for g in groups]

    if USING_V2:
        env = TimetablingEnvironment(
            courses,
            teachers,
            groups,
            classrooms,
            timeslots,
            course_teacher_map=course_teacher_map,
            course_group_map=course_group_map,
        )
    else:
        env = TimetablingEnvironment(courses, teachers, groups, classrooms, timeslots)

    state_dim = env.state_dim if (USING_V2 or USING_OPTIMIZED) else env._get_state().shape[0]
    raw_action_dim = env.n_courses * env.n_teachers * env.n_groups * env.n_classrooms * env.n_timeslots
    action_dim = min(raw_action_dim, 4096)

    return {
        "state_dim": int(state_dim),
        "action_dim": int(action_dim),
        "raw_action_dim": int(raw_action_dim),
    }


def _ensure_pretrained_model_loaded(trainer, model_version: str = None) -> None:
    """Переконатися, що trainer завантажив сумісну попередньо навчену модель."""
    expected_state_dim = getattr(trainer, "state_dim", None)
    expected_action_dim = getattr(trainer, "action_dim", None)

    if not isinstance(expected_state_dim, int):
        expected_state_dim = None
    if not isinstance(expected_action_dim, int):
        expected_action_dim = None

    if hasattr(trainer, "model_dir"):
        trainer.model_dir = _resolve_model_dir_for_schedule(
            model_version,
            expected_state_dim=expected_state_dim,
            expected_action_dim=expected_action_dim,
        )

    if not hasattr(trainer, "_try_load_pretrained"):
        logger.warning("⚠️ Trainer не має перевірки pretrained-моделі, продовжуємо без валідації")
        return

    loaded = trainer._try_load_pretrained()
    if loaded:
        return

    fallback_candidate: Optional[Path] = None
    if isinstance(expected_state_dim, int) and isinstance(expected_action_dim, int):
        fallback_candidate = _find_compatible_model_candidate(expected_state_dim, expected_action_dim)

    if fallback_candidate is not None:
        normalized_requested = _normalize_model_name(model_version) if model_version else None
        if normalized_requested != fallback_candidate.name:
            logger.warning(
                "⚠️ Обрана модель несумісна. Використовуємо сумісну модель: %s",
                fallback_candidate.name,
            )
            trainer.model_version = fallback_candidate.name
            if hasattr(trainer, "model_dir"):
                trainer.model_dir = fallback_candidate.parent
            if trainer._try_load_pretrained():
                return

    if model_version:
        if not _model_exists_in_any_dir(model_version):
            raise ValueError(
                f"Модель '{model_version}' не знайдено у директоріях saved_models. Перевірте назву моделі."
            )
        current_state_dim = expected_state_dim
        current_action_dim = expected_action_dim
        dims_hint = ""
        if isinstance(current_state_dim, int) and isinstance(current_action_dim, int):
            dims_hint = f" Поточні розмірності середовища: state_dim={current_state_dim}, action_dim={current_action_dim}."
        raise ValueError(
            f"Модель '{model_version}' знайдено, але не вдалося завантажити. Ймовірно, вона несумісна з поточними даними (state/action dimensions)."
            f" Створіть/натренуйте нову модель під поточний набір даних.{dims_hint}"
        )

    raise ValueError(
        "Не знайдено сумісної натренованої моделі. Спочатку виконайте навчання у вкладці Training або вкажіть model_version."
    )


@router.get("/model-compatibility")
def check_model_compatibility(
    model_version: str = Query(..., description="Model name, e.g. actor_critic_20260328_015845.pt"),
    db: Session = Depends(get_db),
):
    """Preflight compatibility check between selected model and current DB environment dimensions."""
    try:
        env_dims = _build_environment_dimensions(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build environment dimensions: {exc}")

    model_path = _resolve_model_path(
        model_version,
        expected_state_dim=env_dims.get("state_dim"),
        expected_action_dim=env_dims.get("action_dim"),
    )
    if model_path is not None:
        meta_dims = _read_model_meta_dimensions_for_path(model_path)
    else:
        meta_dims = {
            "model_found": False,
            "meta_found": False,
            "state_dim": None,
            "action_dim": None,
            "model_path": None,
        }

    if not meta_dims.get("model_found"):
        return {
            "model_version": _normalize_model_name(model_version),
            "compatible": False,
            "reason": "model_not_found",
            "detail": "Model file not found in saved_models directories",
            "current": env_dims,
            "model": meta_dims,
        }

    if not meta_dims.get("meta_found"):
        return {
            "model_version": _normalize_model_name(model_version),
            "compatible": False,
            "reason": "meta_not_found",
            "detail": "Model metadata (meta_*.json) not found; cannot verify dimensions",
            "current": env_dims,
            "model": meta_dims,
        }

    compatible = (
        meta_dims.get("state_dim") == env_dims.get("state_dim")
        and meta_dims.get("action_dim") == env_dims.get("action_dim")
    )

    detail = "Model dimensions are compatible with current DB environment"
    reason = "ok"
    if not compatible:
        reason = "dimension_mismatch"
        detail = (
            "Model dimensions do not match current DB environment. "
            f"Model: state_dim={meta_dims.get('state_dim')}, action_dim={meta_dims.get('action_dim')}; "
            f"Current: state_dim={env_dims.get('state_dim')}, action_dim={env_dims.get('action_dim')}"
        )

    return {
        "model_version": _normalize_model_name(model_version),
        "compatible": compatible,
        "reason": reason,
        "detail": detail,
        "current": env_dims,
        "model": meta_dims,
    }


def _auto_export_schedule(
    db: Session,
    generation_id: int,
    stats: dict,
    model_version: Optional[str] = None,
):
    """Автоматично зберегти розклад після генерації."""
    scheduled_classes = db.query(ScheduledClass).all()
    
    if not scheduled_classes:
        return
    
    classes_data = []
    for sc in scheduled_classes:
        course = db.query(Course).filter(Course.id == sc.course_id).first()
        teacher = db.query(Teacher).filter(Teacher.id == sc.teacher_id).first()
        group = db.query(StudentGroup).filter(StudentGroup.id == sc.group_id).first()
        classroom = db.query(Classroom).filter(Classroom.id == sc.classroom_id).first()
        timeslot = db.query(Timeslot).filter(Timeslot.id == sc.timeslot_id).first()
        
        classes_data.append({
            "course_id": sc.course_id,
            "course_code": course.code if course else None,
            "course_name": course.name if course else None,
            "teacher_id": sc.teacher_id,
            "teacher_name": teacher.full_name if teacher else None,
            "group_id": sc.group_id,
            "group_code": group.code if group else None,
            "classroom_id": sc.classroom_id,
            "classroom_code": classroom.code if classroom else None,
            "timeslot_id": sc.timeslot_id,
            "day_of_week": timeslot.day_of_week if timeslot else None,
            "period_number": timeslot.period_number if timeslot else None,
            "start_time": str(timeslot.start_time) if timeslot else None,
            "end_time": str(timeslot.end_time) if timeslot else None,
            "is_locked": sc.is_locked,
        })

    score_summary = _calculate_schedule_score(db, scheduled_classes)
    hard_violations = (
        stats.get("hard_violations")
        if stats.get("hard_violations") is not None
        else stats.get("final_hard_violations", score_summary["hard_violations"])
    )
    soft_violations = (
        stats.get("soft_violations")
        if stats.get("soft_violations") is not None
        else stats.get("final_soft_violations", score_summary["soft_violations"])
    )
    
    meta = {
        "created_at": datetime.now().isoformat(),
        "generation_id": generation_id,
        "model_version": _normalize_model_name(model_version) if model_version else None,
        "classes_count": len(classes_data),
        "best_reward": stats.get("best_reward", 0),
        "overall_score": score_summary["overall"],
        "hard_violations": int(hard_violations),
        "soft_violations": int(soft_violations),
        "description": f"Auto-saved after generation #{generation_id}",
    }
    
    export_data = {"meta": meta, "classes": classes_data}
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"schedule_gen{generation_id}_{timestamp}.json"
    filepath = SCHEDULES_DIR / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📁 Автоматично збережено розклад: {filepath}")


@router.post("/generate", response_model=ScheduleGenerationStatus, status_code=202)
def generate_schedule(
    request: ScheduleGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Запустити DRL-генерацію розкладу."""
    # Створити запис про генерацію
    generation = ScheduleGeneration(
        status="pending",
        iterations=request.iterations,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)

    # Запустити генерацію у окремому потоці
    thread = threading.Thread(
        target=_run_generation,
        args=(generation.id, request.iterations, request.preserve_locked, request.use_existing, request.model_version),
        daemon=True
    )
    thread.start()
    
    logger.info(f"✅ Запущено thread для генерації ID={generation.id}")

    return generation


def _run_generation(
    generation_id: int,
    iterations: int,
    preserve_locked: bool,
    use_existing: bool,
    model_version: str = None,
):
    """Фонова задача генерації (виконується в окремому потоці)."""
    import time
    from ..core.database_session import SessionLocal
    
    logger.info(f"🚀 [Thread] Запуск генерації ID={generation_id} з {iterations} ітераціями")

    # Створюємо нову сесію БД для потоку
    db = SessionLocal()
    start_time = time.time()

    try:
        generation = db.query(ScheduleGeneration).filter(ScheduleGeneration.id == generation_id).first()
        if not generation:
            logger.error(f"❌ Генерація ID={generation_id} не знайдена!")
            return
            
        generation.status = "running"
        db.commit()
        
        logger.info(f"📊 [Thread] Статус змінено на 'running' для генерації ID={generation_id}")

        # Завантаження даних
        courses = db.query(Course).all()
        teachers = db.query(Teacher).all()
        groups = db.query(StudentGroup).all()
        classrooms = db.query(Classroom).all()
        timeslots = db.query(Timeslot).filter(Timeslot.is_active == True).all()

        logger.info(f"📚 Завантажено: {len(courses)} курсів, {len(teachers)} викладачів, "
                   f"{len(groups)} груп, {len(classrooms)} аудиторій, {len(timeslots)} слотів")

        if not all([courses, teachers, groups, classrooms, timeslots]):
            raise ValueError("Insufficient data: ensure courses, teachers, groups, classrooms, and timeslots exist")

        # Створюємо map-и курс-викладач та курс-група з relationships
        course_teacher_map = {}
        course_group_map = {}
        
        for course in courses:
            # Викладачі для курсу (з many-to-many relationship)
            if hasattr(course, 'teachers') and course.teachers:
                course_teacher_map[course.id] = [t.id for t in course.teachers]
            else:
                # Якщо немає призначених викладачів - всі можуть вести
                course_teacher_map[course.id] = [t.id for t in teachers]
            
            # Групи для курсу (з many-to-many relationship)
            if hasattr(course, 'groups') and course.groups:
                course_group_map[course.id] = [g.id for g in course.groups]
            else:
                # Якщо немає призначених груп - всі відвідують
                course_group_map[course.id] = [g.id for g in groups]
        
        logger.info(f"🔗 Завантажено призначення: {sum(len(v) for v in course_teacher_map.values())} зв'язків курс-викладач, "
                   f"{sum(len(v) for v in course_group_map.values())} зв'язків курс-група")

        # Створення середовища (V2 або fallback)
        version_name = "V2 (з гарантією повноти)" if USING_V2 else ("оптимізованого" if USING_OPTIMIZED else "оригінального")
        logger.info(f"🔧 Створення {version_name} DRL середовища...")
        
        if USING_V2:
            env = TimetablingEnvironment(
                courses, teachers, groups, classrooms, timeslots,
                course_teacher_map=course_teacher_map,
                course_group_map=course_group_map
            )
        else:
            env = TimetablingEnvironment(courses, teachers, groups, classrooms, timeslots)

        # Розрахунок розмірностей
        if USING_V2 or USING_OPTIMIZED:
            state_dim = env.state_dim  # Compact state
        else:
            state_dim = env._get_state().shape[0]
        
        # Обмежуємо action_dim для ефективності
        raw_action_dim = env.n_courses * env.n_teachers * env.n_groups * env.n_classrooms * env.n_timeslots
        action_dim = min(raw_action_dim, 4096)  # Обмеження для швидкодії

        logger.info(f"🧠 Розмірності: state_dim={state_dim}, action_dim={action_dim} (raw: {raw_action_dim})")

        # Функція callback для оновлення прогресу в БД
        def update_progress(current_iter, total_iter):
            try:
                gen = db.query(ScheduleGeneration).filter(ScheduleGeneration.id == generation_id).first()
                if gen:
                    gen.current_iteration = current_iter
                    db.commit()
            except Exception as e:
                logger.warning(f"⚠️ Не вдалось оновити прогрес: {e}")

        # Функція для перевірки прапорця зупинки
        def check_stop():
            return _stop_flags.get(generation_id, False)

        # Індивідуальна генерація: inference-only з натренованою моделлю (без донавчання)
        logger.info("🧠 Індивідуальна генерація: завантаження натренованої моделі (без навчання)...")
        trainer = PPOTrainer(
            env,
            state_dim,
            action_dim,
            device="cpu",
            progress_callback=update_progress,
            stop_callback=check_stop,
            model_version=model_version,
        )
        _ensure_pretrained_model_loaded(trainer, model_version=model_version)
        stats = {
            "best_reward": 0.0,
            "final_hard_violations": 0,
            "final_soft_violations": 0,
            "completion_rate": 0.0,
            "best_model_score": 0.0,
        }
        
        # Перевірка чи було зупинено
        if check_stop():
            logger.info(f"🛑 Генерація ID={generation_id} була зупинена користувачем")
            generation = db.query(ScheduleGeneration).filter(ScheduleGeneration.id == generation_id).first()
            if generation:
                generation.status = "stopped"
                generation.execution_time = time.time() - start_time
                db.commit()
            # Очищуємо прапорець
            _stop_flags.pop(generation_id, None)
            return

        generation.current_iteration = 1
        db.commit()

        logger.info("✅ Натреновану модель успішно завантажено")

        # Генерація фінального розкладу
        logger.info("📅 Генерація фінального розкладу...")
        
        if USING_V2:
            # V2 повертає (schedule, generation_stats)
            schedule_actions, gen_stats = trainer.generate_schedule(use_local_search=True)
            stats.update(gen_stats)
            logger.info(f"📊 V2 статистика: completion={gen_stats.get('completion_rate', 0):.1%}, "
                       f"remaining={gen_stats.get('remaining', 0)}")
        else:
            schedule_actions = trainer.generate_schedule()

        logger.info(f"📋 Згенеровано {len(schedule_actions)} занять")

        # Перед збереженням нового розкладу завжди очищаємо замінювані заняття,
        # щоб уникнути нашарування нової генерації поверх існуючого розкладу.
        if preserve_locked:
            deleted = db.query(ScheduledClass).filter(ScheduledClass.is_locked == False).delete()
            logger.info(f"🗑️ Видалено {deleted} незафіксованих занять перед записом нової генерації")
        else:
            deleted = db.query(ScheduledClass).delete()
            logger.info(f"🗑️ Видалено {deleted} старих занять перед записом нової генерації")

        # Збереження нових занять
        for action in schedule_actions:
            course_idx, teacher_idx, group_idx, classroom_idx, timeslot_idx = action
            scheduled_class = ScheduledClass(
                course_id=courses[course_idx].id,
                teacher_id=teachers[teacher_idx].id,
                group_id=groups[group_idx].id,
                classroom_id=classrooms[classroom_idx].id,
                timeslot_id=timeslots[timeslot_idx].id,
            )
            db.add(scheduled_class)

        # Оновлення статусу генерації
        generation.status = "completed"
        generation.current_iteration = max(iterations, 1)
        generation.final_score = stats.get("best_model_score", stats.get("best_reward", 0))
        
        # V2 версія має інші ключі в stats
        if "hard_violations" in stats:
            generation.hard_violations = stats["hard_violations"]
            generation.soft_violations = stats["soft_violations"]
        else:
            # Fallback для старих версій
            generation.hard_violations = stats.get("final_hard_violations", 0)
            generation.soft_violations = stats.get("final_soft_violations", 0)
        
        generation.execution_time = time.time() - start_time
        db.commit()
        
        # Логування статистики завершення
        completion_rate = stats.get("completion_rate", len(schedule_actions) / max(env.total_classes_to_schedule, 1))
        logger.info(f"📊 Completion rate: {completion_rate:.1%} ({len(schedule_actions)}/{getattr(env, 'total_classes_to_schedule', 'N/A')})")
        
        # === АВТОМАТИЧНЕ ЗБЕРЕЖЕННЯ РОЗКЛАДУ У ФАЙЛ ===
        try:
            _auto_export_schedule(db, generation_id, stats, model_version=model_version)
        except Exception as e:
            logger.warning(f"⚠️ Не вдалось автоматично зберегти розклад: {e}")
        
        logger.info(f"🎉 Генерація ID={generation_id} успішно завершена! "
                   f"Час: {generation.execution_time:.2f}s, "
                   f"Hard: {generation.hard_violations}, Soft: {generation.soft_violations}")

    except Exception as e:
        logger.error(f"❌ Помилка генерації ID={generation_id}: {str(e)}", exc_info=True)
        generation = db.query(ScheduleGeneration).filter(ScheduleGeneration.id == generation_id).first()
        if generation:
            generation.status = "failed"
            generation.error_message = str(e)
            generation.execution_time = time.time() - start_time
            db.commit()
    finally:
        db.close()
        logger.info(f"🔒 Закрито сесію БД для генерації ID={generation_id}")


# Глобальний словник для зберігання прапорців зупинки
_stop_flags = {}


@router.post("/stop/{generation_id}")
def stop_generation(generation_id: int, db: Session = Depends(get_db)):
    """Зупинити генерацію розкладу."""
    generation = db.query(ScheduleGeneration).filter(ScheduleGeneration.id == generation_id).first()
    if not generation:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    if generation.status not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail=f"Cannot stop generation with status: {generation.status}")
    
    # Встановлюємо прапорець зупинки
    _stop_flags[generation_id] = True
    
    # Оновлюємо статус
    generation.status = "stopped"
    db.commit()
    
    logger.info(f"🛑 Генерація ID={generation_id} зупинена користувачем")
    
    return {"success": True, "message": "Generation stopped", "status": "stopped"}


@router.get("/status/{generation_id}", response_model=ScheduleGenerationStatus)
def get_generation_status(generation_id: int, db: Session = Depends(get_db)):
    """Перевірити статус генерації."""
    generation = db.query(ScheduleGeneration).filter(ScheduleGeneration.id == generation_id).first()
    if not generation:
        raise HTTPException(status_code=404, detail="Generation not found")
    return generation


@router.get("/timetable/teacher/{teacher_id}", response_model=List[ScheduledClassFullResponse])
def get_teacher_timetable(teacher_id: int, db: Session = Depends(get_db)):
    """Отримати розклад викладача."""
    scheduled_classes = (
        db.query(ScheduledClass).filter(ScheduledClass.teacher_id == teacher_id).all()
    )
    return _enrich_scheduled_classes(db, scheduled_classes)


@router.get("/timetable/classroom/{classroom_id}", response_model=List[ScheduledClassFullResponse])
def get_classroom_timetable(classroom_id: int, db: Session = Depends(get_db)):
    """Отримати розклад аудиторії."""
    scheduled_classes = (
        db.query(ScheduledClass).filter(ScheduledClass.classroom_id == classroom_id).all()
    )
    return _enrich_scheduled_classes(db, scheduled_classes)


def _enrich_scheduled_classes(db: Session, scheduled_classes: list) -> List[dict]:
    """Збагатити scheduled classes повними даними для UI."""
    result = []
    
    # Detect conflicts first
    conflict_classes = _detect_conflicts_for_classes(db, scheduled_classes)
    
    for sc in scheduled_classes:
        course = db.query(Course).filter(Course.id == sc.course_id).first()
        teacher = db.query(Teacher).filter(Teacher.id == sc.teacher_id).first()
        group = db.query(StudentGroup).filter(StudentGroup.id == sc.group_id).first()
        classroom = db.query(Classroom).filter(Classroom.id == sc.classroom_id).first()
        timeslot = db.query(Timeslot).filter(Timeslot.id == sc.timeslot_id).first()
        
        has_conflict = sc.id in conflict_classes
        conflict_type = conflict_classes.get(sc.id)
        
        result.append({
            "id": sc.id,
            "course_id": sc.course_id,
            "teacher_id": sc.teacher_id,
            "group_id": sc.group_id,
            "classroom_id": sc.classroom_id,
            "timeslot_id": sc.timeslot_id,
            "week_number": sc.week_number,
            "is_locked": sc.is_locked,
            "notes": sc.notes,
            "day_of_week": timeslot.day_of_week if timeslot else 0,
            "period_number": timeslot.period_number if timeslot else 1,
            "start_time": str(timeslot.start_time) if timeslot else None,
            "end_time": str(timeslot.end_time) if timeslot else None,
            "course_code": course.code if course else "N/A",
            "course_name": course.name if course else "N/A",
            "teacher_name": teacher.full_name if teacher else "N/A",
            "group_code": group.code if group else "N/A",
            "classroom_code": classroom.code if classroom else "N/A",
            "has_conflict": has_conflict,
            "conflict_type": conflict_type,
        })
    
    return result


def _detect_conflicts_for_classes(db: Session, scheduled_classes: list) -> dict:
    """Знайти конфлікти для заданого списку занять."""
    conflicts = {}
    
    # Get all scheduled classes to check against
    all_classes = db.query(ScheduledClass).all()
    
    # Group by timeslot
    timeslot_map = {}
    for sc in all_classes:
        if sc.timeslot_id not in timeslot_map:
            timeslot_map[sc.timeslot_id] = []
        timeslot_map[sc.timeslot_id].append(sc)
    
    for sc in scheduled_classes:
        same_slot = timeslot_map.get(sc.timeslot_id, [])
        
        for other in same_slot:
            if other.id == sc.id:
                continue
            
            # Teacher conflict
            if sc.teacher_id == other.teacher_id:
                conflicts[sc.id] = "Конфлікт викладача"
            # Group conflict
            elif sc.group_id == other.group_id:
                conflicts[sc.id] = "Конфлікт групи"
            # Room conflict  
            elif sc.classroom_id == other.classroom_id:
                conflicts[sc.id] = "Конфлікт аудиторії"
    
    return conflicts


@router.get("/timetable/group/{group_id}", response_model=List[ScheduledClassFullResponse])
def get_group_timetable_alt(group_id: int, db: Session = Depends(get_db)):
    """Отримати розклад групи (альтернативний URL)."""
    scheduled_classes = (
        db.query(ScheduledClass).filter(ScheduledClass.group_id == group_id).all()
    )
    return _enrich_scheduled_classes(db, scheduled_classes)


@router.get("/timetable/{group_id}", response_model=List[ScheduledClassFullResponse])
def get_group_timetable(group_id: int, db: Session = Depends(get_db)):
    """Отримати розклад групи."""
    scheduled_classes = (
        db.query(ScheduledClass).filter(ScheduledClass.group_id == group_id).all()
    )
    return _enrich_scheduled_classes(db, scheduled_classes)


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db)):
    """Отримати аналітику розкладу."""
    # Classroom utilization
    classrooms = db.query(Classroom).all()
    total_timeslots = db.query(Timeslot).filter(Timeslot.is_active == True).count()
    classroom_util = []

    for classroom in classrooms:
        occupied = db.query(ScheduledClass).filter(ScheduledClass.classroom_id == classroom.id).count()
        rate = occupied / total_timeslots if total_timeslots > 0 else 0
        classroom_util.append(
            ClassroomUtilization(
                classroom_id=classroom.id,
                classroom_code=classroom.code,
                total_slots=total_timeslots,
                occupied_slots=occupied,
                utilization_rate=round(rate, 2),
            )
        )

    # Teacher workload
    teachers = db.query(Teacher).all()
    teacher_workload = []

    for teacher in teachers:
        assigned = db.query(ScheduledClass).filter(ScheduledClass.teacher_id == teacher.id).count()
        rate = assigned / teacher.max_hours_per_week if teacher.max_hours_per_week > 0 else 0
        teacher_workload.append(
            TeacherWorkload(
                teacher_id=teacher.id,
                teacher_name=teacher.full_name,
                assigned_hours=assigned,
                max_hours=teacher.max_hours_per_week,
                workload_rate=round(rate, 2),
            )
        )

    total_classes = db.query(ScheduledClass).count()

    return AnalyticsResponse(
        classroom_utilization=classroom_util,
        teacher_workload=teacher_workload,
        total_classes=total_classes,
        hard_constraint_violations=0,  # TODO: calculate
        soft_constraint_violations=0,  # TODO: calculate
        average_score=0.0,  # TODO: calculate
    )


@router.get("/training-metrics")
def get_training_metrics(db: Session = Depends(get_db)):
    """Отримати метрики навчання нейромережі."""
    import json
    from pathlib import Path

    candidate_paths = [
        Path("./saved_models/training_metrics.json"),
        Path("./backend/saved_models/training_metrics.json"),
        Path(__file__).parent.parent.parent / "saved_models" / "training_metrics.json",
    ]

    metrics_path = next((p for p in candidate_paths if p.exists()), None)

    if metrics_path is None:
        checked = ", ".join(str(p) for p in candidate_paths)
        raise HTTPException(
            status_code=404,
            detail=f"Training metrics not found. Checked: {checked}",
        )
    
    try:
        with open(metrics_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Перевірка на порожній/неповний файл
        if not content.strip():
            raise HTTPException(status_code=404, detail="Training metrics file is empty. Train the model again.")
            
        try:
            metrics = json.loads(content)
        except json.JSONDecodeError as je:
            # Видалити пошкоджений файл
            metrics_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=500, 
                detail=f"Corrupted training metrics file (deleted). Please train the model again. Error: {str(je)}"
            )
        
        # Валідація структури
        if 'metrics' not in metrics:
            raise HTTPException(status_code=500, detail="Invalid metrics format: missing 'metrics' key")
            
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load training metrics: {str(e)}")


@router.delete("/clear", status_code=204)
def clear_schedule(db: Session = Depends(get_db)):
    """Очистити весь розклад."""
    db.query(ScheduledClass).filter(ScheduledClass.is_locked == False).delete()
    db.commit()
    return None


# === SCHEDULED CLASS MANAGEMENT ===

@router.get("/class/{class_id}")
def get_scheduled_class(class_id: int, db: Session = Depends(get_db)):
    """Отримати інформацію про конкретне заняття."""
    scheduled_class = db.query(ScheduledClass).filter(ScheduledClass.id == class_id).first()
    if not scheduled_class:
        raise HTTPException(status_code=404, detail="Заняття не знайдено")
    return _enrich_scheduled_classes(db, [scheduled_class])[0]


@router.put("/class/{class_id}")
def update_scheduled_class(
    class_id: int,
    update_data: ScheduledClassUpdate,
    db: Session = Depends(get_db)
):
    """Оновити заняття (перемістити в інший час/аудиторію)."""
    scheduled_class = db.query(ScheduledClass).filter(ScheduledClass.id == class_id).first()
    if not scheduled_class:
        raise HTTPException(status_code=404, detail="Заняття не знайдено")
    
    if scheduled_class.is_locked:
        raise HTTPException(status_code=400, detail="Неможливо змінити заблоковане заняття")
    
    timeslot_id = update_data.timeslot_id
    classroom_id = update_data.classroom_id
    teacher_id = update_data.teacher_id
    
    # Оновлюємо поля якщо вони передані
    if timeslot_id is not None:
        timeslot = db.query(Timeslot).filter(Timeslot.id == timeslot_id).first()
        if not timeslot:
            raise HTTPException(status_code=404, detail="Таймслот не знайдено")
        
        # Перевірка конфліктів
        conflicts = db.query(ScheduledClass).filter(
            ScheduledClass.timeslot_id == timeslot_id,
            ScheduledClass.id != class_id
        ).all()
        
        for c in conflicts:
            if c.teacher_id == scheduled_class.teacher_id:
                raise HTTPException(status_code=400, detail="Конфлікт: викладач вже має заняття в цей час")
            if c.group_id == scheduled_class.group_id:
                raise HTTPException(status_code=400, detail="Конфлікт: група вже має заняття в цей час")
            if classroom_id is None and c.classroom_id == scheduled_class.classroom_id:
                raise HTTPException(status_code=400, detail="Конфлікт: аудиторія вже зайнята в цей час")
        
        scheduled_class.timeslot_id = timeslot_id
    
    if classroom_id is not None:
        classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        if not classroom:
            raise HTTPException(status_code=404, detail="Аудиторію не знайдено")
        
        # Перевірка конфлікту аудиторії
        conflict = db.query(ScheduledClass).filter(
            ScheduledClass.timeslot_id == scheduled_class.timeslot_id,
            ScheduledClass.classroom_id == classroom_id,
            ScheduledClass.id != class_id
        ).first()
        
        if conflict:
            raise HTTPException(status_code=400, detail="Аудиторія вже зайнята в цей час")
        
        scheduled_class.classroom_id = classroom_id
    
    if teacher_id is not None:
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Викладача не знайдено")
        
        # Перевірка конфлікту викладача
        conflict = db.query(ScheduledClass).filter(
            ScheduledClass.timeslot_id == scheduled_class.timeslot_id,
            ScheduledClass.teacher_id == teacher_id,
            ScheduledClass.id != class_id
        ).first()
        
        if conflict:
            raise HTTPException(status_code=400, detail="Викладач вже має заняття в цей час")
        
        scheduled_class.teacher_id = teacher_id
    
    db.commit()
    db.refresh(scheduled_class)
    
    return _enrich_scheduled_classes(db, [scheduled_class])[0]


@router.patch("/class/{class_id}/lock")
def toggle_lock_scheduled_class(
    class_id: int,
    lock_data: ScheduledClassLock,
    db: Session = Depends(get_db)
):
    """Заблокувати/розблокувати заняття."""
    scheduled_class = db.query(ScheduledClass).filter(ScheduledClass.id == class_id).first()
    if not scheduled_class:
        raise HTTPException(status_code=404, detail="Заняття не знайдено")
    
    scheduled_class.is_locked = lock_data.locked
    
    db.commit()
    db.refresh(scheduled_class)
    
    return {
        "id": scheduled_class.id,
        "is_locked": scheduled_class.is_locked,
        "message": "Заняття заблоковано" if scheduled_class.is_locked else "Заняття розблоковано"
    }


@router.delete("/class/{class_id}", status_code=200)
def delete_scheduled_class(class_id: int, db: Session = Depends(get_db)):
    """Видалити заняття з розкладу."""
    scheduled_class = db.query(ScheduledClass).filter(ScheduledClass.id == class_id).first()
    if not scheduled_class:
        raise HTTPException(status_code=404, detail="Заняття не знайдено")
    
    if scheduled_class.is_locked:
        raise HTTPException(status_code=400, detail="Неможливо видалити заблоковане заняття")
    
    db.delete(scheduled_class)
    db.commit()
    
    return {"success": True, "message": "Заняття видалено"}


# === CONFLICT DETECTION ===

@router.get("/conflicts")
def get_conflicts(db: Session = Depends(get_db)):
    """Отримати список конфліктів у розкладі."""
    conflicts = []
    
    # Отримуємо всі заняття з пов'язаними даними
    scheduled_classes = db.query(ScheduledClass).all()
    
    # Групуємо за timeslot для перевірки конфліктів
    timeslot_classes = {}
    for sc in scheduled_classes:
        if sc.timeslot_id not in timeslot_classes:
            timeslot_classes[sc.timeslot_id] = []
        timeslot_classes[sc.timeslot_id].append(sc)
    
    conflict_id = 1
    
    DAYS = ['Понеділок', 'Вівторок', 'Середа', 'Четвер', "П'ятниця"]
    
    for timeslot_id, classes in timeslot_classes.items():
        if len(classes) < 2:
            continue
            
        timeslot = db.query(Timeslot).filter(Timeslot.id == timeslot_id).first()
        time_str = f"{DAYS[timeslot.day_of_week]}, {timeslot.start_time}-{timeslot.end_time}" if timeslot else "Unknown"
        
        # Перевірка конфліктів викладачів
        teacher_counts = {}
        for sc in classes:
            if sc.teacher_id not in teacher_counts:
                teacher_counts[sc.teacher_id] = []
            teacher_counts[sc.teacher_id].append(sc)
        
        for teacher_id, teacher_classes in teacher_counts.items():
            if len(teacher_classes) > 1:
                teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
                affected = []
                for tc in teacher_classes:
                    course = db.query(Course).filter(Course.id == tc.course_id).first()
                    group = db.query(StudentGroup).filter(StudentGroup.id == tc.group_id).first()
                    affected.append(f"{course.name if course else 'Unknown'} ({group.code if group else 'Unknown'})")
                
                conflicts.append({
                    "id": str(conflict_id),
                    "type": "hard",
                    "category": "teacher",
                    "message": f"Конфлікт викладача: {teacher.full_name if teacher else 'Unknown'} має {len(teacher_classes)} заняття одночасно",
                    "details": {
                        "class_id": teacher_classes[0].id,
                        "timeslot": time_str,
                        "affected_items": affected
                    },
                    "suggestions": [
                        f"Перемістити одне з занять на інший час",
                        f"Призначити іншого викладача"
                    ]
                })
                conflict_id += 1
        
        # Перевірка конфліктів аудиторій
        room_counts = {}
        for sc in classes:
            if sc.classroom_id not in room_counts:
                room_counts[sc.classroom_id] = []
            room_counts[sc.classroom_id].append(sc)
        
        for room_id, room_classes in room_counts.items():
            if len(room_classes) > 1:
                room = db.query(Classroom).filter(Classroom.id == room_id).first()
                affected = []
                for rc in room_classes:
                    course = db.query(Course).filter(Course.id == rc.course_id).first()
                    group = db.query(StudentGroup).filter(StudentGroup.id == rc.group_id).first()
                    affected.append(f"{course.name if course else 'Unknown'} ({group.code if group else 'Unknown'})")
                
                conflicts.append({
                    "id": str(conflict_id),
                    "type": "hard",
                    "category": "room",
                    "message": f"Конфлікт аудиторії: ауд. {room.code if room else 'Unknown'} зайнята двічі",
                    "details": {
                        "class_id": room_classes[0].id,
                        "timeslot": time_str,
                        "affected_items": affected
                    },
                    "suggestions": [
                        f"Перемістити одне з занять в іншу аудиторію",
                        f"Змінити час одного з занять"
                    ]
                })
                conflict_id += 1
        
        # Перевірка конфліктів груп
        group_counts = {}
        for sc in classes:
            if sc.group_id not in group_counts:
                group_counts[sc.group_id] = []
            group_counts[sc.group_id].append(sc)
        
        for group_id, group_classes in group_counts.items():
            if len(group_classes) > 1:
                group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
                affected = []
                for gc in group_classes:
                    course = db.query(Course).filter(Course.id == gc.course_id).first()
                    teacher = db.query(Teacher).filter(Teacher.id == gc.teacher_id).first()
                    affected.append(f"{course.name if course else 'Unknown'} ({teacher.full_name if teacher else 'Unknown'})")
                
                conflicts.append({
                    "id": str(conflict_id),
                    "type": "hard",
                    "category": "group",
                    "message": f"Конфлікт групи: {group.code if group else 'Unknown'} має {len(group_classes)} заняття одночасно",
                    "details": {
                        "class_id": group_classes[0].id,
                        "timeslot": time_str,
                        "affected_items": affected
                    },
                    "suggestions": [
                        f"Перемістити одне з занять на інший час"
                    ]
                })
                conflict_id += 1
    
    # Перевірка м'яких обмежень - місткість аудиторій
    for sc in scheduled_classes:
        group = db.query(StudentGroup).filter(StudentGroup.id == sc.group_id).first()
        classroom = db.query(Classroom).filter(Classroom.id == sc.classroom_id).first()
        timeslot = db.query(Timeslot).filter(Timeslot.id == sc.timeslot_id).first()
        
        if group and classroom and group.students_count > classroom.capacity:
            time_str = f"{DAYS[timeslot.day_of_week]}, {timeslot.start_time}-{timeslot.end_time}" if timeslot else "Unknown"
            course = db.query(Course).filter(Course.id == sc.course_id).first()
            
            conflicts.append({
                "id": str(conflict_id),
                "type": "soft",
                "category": "capacity",
                "message": f"Місткість: група {group.code} ({group.students_count} осіб) у ауд. {classroom.code} ({classroom.capacity} місць)",
                "details": {
                    "class_id": sc.id,
                    "timeslot": time_str,
                    "affected_items": [f"{course.name if course else 'Unknown'}"]
                },
                "suggestions": [
                    f"Перемістити в аудиторію більшої місткості"
                ]
            })
            conflict_id += 1
    
    return conflicts


# === SCHEDULE FILE MANAGEMENT ===

@router.get("/files")
def list_schedule_files():
    """Отримати список збережених розкладів."""
    files = []
    for f in SCHEDULES_DIR.glob("*.json"):
        stat = f.stat()
        # Читаємо метадані з файлу
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                meta = data.get("meta", {})
        except:
            meta = {}

        if not isinstance(meta, dict):
            meta = {}

        classes_count = meta.get("classes_count", 0)
        description = meta.get("description", "")
        created_at = meta.get("created_at", datetime.fromtimestamp(stat.st_mtime).isoformat())
        
        files.append({
            "filename": f.name,
            "created_at": created_at,
            "size_kb": round(stat.st_size / 1024, 2),
            "classes_count": classes_count,
            "description": description,
            "meta": {
                **meta,
                "created_at": created_at,
                "classes_count": classes_count,
                "description": description,
            },
        })
    
    # Сортуємо за датою (найновіші спочатку)
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files


@router.post("/export")
def export_schedule(description: str = "", db: Session = Depends(get_db)):
    """Експортувати поточний розклад у файл."""
    # Отримуємо всі заняття
    scheduled_classes = db.query(ScheduledClass).all()
    
    if not scheduled_classes:
        raise HTTPException(status_code=400, detail="No schedule to export")
    
    # Формуємо дані для експорту
    classes_data = []
    for sc in scheduled_classes:
        # Отримуємо пов'язані дані
        course = db.query(Course).filter(Course.id == sc.course_id).first()
        teacher = db.query(Teacher).filter(Teacher.id == sc.teacher_id).first()
        group = db.query(StudentGroup).filter(StudentGroup.id == sc.group_id).first()
        classroom = db.query(Classroom).filter(Classroom.id == sc.classroom_id).first()
        timeslot = db.query(Timeslot).filter(Timeslot.id == sc.timeslot_id).first()
        
        classes_data.append({
            "course_id": sc.course_id,
            "course_code": course.code if course else None,
            "course_name": course.name if course else None,
            "teacher_id": sc.teacher_id,
            "teacher_name": teacher.full_name if teacher else None,
            "group_id": sc.group_id,
            "group_code": group.code if group else None,
            "classroom_id": sc.classroom_id,
            "classroom_code": classroom.code if classroom else None,
            "timeslot_id": sc.timeslot_id,
            "day_of_week": timeslot.day_of_week if timeslot else None,
            "period_number": timeslot.period_number if timeslot else None,
            "start_time": str(timeslot.start_time) if timeslot else None,
            "end_time": str(timeslot.end_time) if timeslot else None,
            "is_locked": sc.is_locked,
        })

    score_summary = _calculate_schedule_score(db, scheduled_classes)
    
    # Метадані
    meta = {
        "created_at": datetime.now().isoformat(),
        "classes_count": len(classes_data),
        "overall_score": score_summary["overall"],
        "hard_violations": score_summary["hard_violations"],
        "soft_violations": score_summary["soft_violations"],
        "description": description,
    }
    
    export_data = {
        "meta": meta,
        "classes": classes_data,
    }
    
    # Генеруємо ім'я файлу
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"schedule_{timestamp}.json"
    filepath = SCHEDULES_DIR / filename
    
    # Зберігаємо
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📁 Експортовано розклад: {filepath} ({len(classes_data)} занять)")
    
    return {
        "filename": filename,
        "classes_count": len(classes_data),
        "message": "Schedule exported successfully"
    }


@router.get("/export/lessons/csv")
def export_lessons_csv(db: Session = Depends(get_db)):
    """Export lessons in CSV template format.

    Template columns:
    Teacher Names,Class Names,Subject Names,Room Names,No. of Lessons,Length
    """
    scheduled_classes = db.query(ScheduledClass).all()
    if not scheduled_classes:
        raise HTTPException(status_code=400, detail="No lessons to export")

    rows = _build_lessons_export_rows(db, scheduled_classes)

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(
        [
            "Teacher Names",
            "Class Names",
            "Subject Names",
            "Room Names",
            "No. of Lessons",
            "Length",
        ]
    )
    writer.writerows(rows)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"lessons_{timestamp}.csv"
    csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/{filename}")
def import_schedule(filename: str, clear_existing: bool = True, db: Session = Depends(get_db)):
    """Імпортувати розклад з файлу."""
    filepath = SCHEDULES_DIR / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    # Читаємо файл
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    classes_data = data.get("classes", [])
    
    if not classes_data:
        raise HTTPException(status_code=400, detail="No classes in file")
    
    # Очищаємо існуючий розклад якщо потрібно
    if clear_existing:
        deleted = db.query(ScheduledClass).delete()
        logger.info(f"🗑️ Видалено {deleted} існуючих занять")
    
    # Імпортуємо заняття
    imported_count = 0
    errors = []
    
    for cls in classes_data:
        try:
            # Перевіряємо чи існують пов'язані записи
            course = db.query(Course).filter(Course.id == cls["course_id"]).first()
            teacher = db.query(Teacher).filter(Teacher.id == cls["teacher_id"]).first()
            group = db.query(StudentGroup).filter(StudentGroup.id == cls["group_id"]).first()
            classroom = db.query(Classroom).filter(Classroom.id == cls["classroom_id"]).first()
            timeslot = db.query(Timeslot).filter(Timeslot.id == cls["timeslot_id"]).first()
            
            if not all([course, teacher, group, classroom, timeslot]):
                errors.append(f"Missing reference for class with course_id={cls['course_id']}")
                continue
            
            scheduled_class = ScheduledClass(
                course_id=cls["course_id"],
                teacher_id=cls["teacher_id"],
                group_id=cls["group_id"],
                classroom_id=cls["classroom_id"],
                timeslot_id=cls["timeslot_id"],
                is_locked=cls.get("is_locked", False),
            )
            db.add(scheduled_class)
            imported_count += 1
        except Exception as e:
            errors.append(str(e))
    
    db.commit()
    
    logger.info(f"📥 Імпортовано {imported_count} занять з {filename}")
    
    return {
        "imported_count": imported_count,
        "errors": errors if errors else None,
        "message": f"Successfully imported {imported_count} classes"
    }


@router.delete("/files/{filename}")
def delete_schedule_file(filename: str):
    """Видалити файл розкладу."""
    filepath = SCHEDULES_DIR / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    try:
        os.remove(filepath)
        logger.info(f"🗑️ Видалено файл: {filename}")
        return {"message": f"File {filename} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.get("/files/{filename}/download")
def download_schedule_file(filename: str):
    """Завантажити файл розкладу."""
    filepath = SCHEDULES_DIR / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/json"
    )


# ====== ASSIGNMENTS API ======

@router.get("/assignments")
def get_assignments(db: Session = Depends(get_db)):
    """Отримати всі призначення курсів викладачам і групам."""
    assignments = []
    
    # Отримуємо всі курси з їх зв'язками
    courses = db.query(Course).all()
    
    assignment_id = 1
    for course in courses:
        for teacher in course.teachers:
            for group in course.groups:
                assignments.append({
                    "id": assignment_id,
                    "course_id": course.id,
                    "teacher_id": teacher.id,
                    "group_id": group.id,
                    "course_code": course.code,
                    "course_name": course.name,
                    "teacher_name": teacher.full_name,
                    "group_code": group.code,
                })
                assignment_id += 1
    
    return assignments


@router.post("/assignments")
def create_assignment(
    assignment: dict,
    db: Session = Depends(get_db)
):
    """Створити нове призначення курсу викладачу і групі."""
    course_id = assignment.get("course_id")
    teacher_id = assignment.get("teacher_id")
    group_id = assignment.get("group_id")
    
    if not all([course_id, teacher_id, group_id]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Перевіряємо чи існують сутності
    course = db.query(Course).filter(Course.id == course_id).first()
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
    
    if not course:
        raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
    if not teacher:
        raise HTTPException(status_code=404, detail=f"Teacher {teacher_id} not found")
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_id} not found")
    
    # Додаємо зв'язки якщо їх ще немає
    if teacher not in course.teachers:
        course.teachers.append(teacher)
    
    if group not in course.groups:
        course.groups.append(group)
    
    db.commit()
    
    return {"message": "Assignment created successfully"}


@router.get("/assignments/export/csv")
def export_assignments_csv(db: Session = Depends(get_db)):
    """Експорт призначень курсів у CSV за шаблоном lessons CSV."""
    rows = _build_assignments_export_rows(db)
    if not rows:
        raise HTTPException(status_code=400, detail="No assignments to export")

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(ASSIGNMENTS_TEMPLATE_HEADERS)
    writer.writerows(rows)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"assignments_{timestamp}.csv"
    csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/assignments/import/csv")
async def import_assignments_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Імпорт призначень курсів за шаблоном sample_lessons.csv."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="CSV file is required")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty")

    csv_text, detected_encoding = _decode_csv_text(raw_bytes)

    reader, detected_delimiter = _build_csv_dict_reader(csv_text)
    headers = [header.strip() for header in (reader.fieldnames or [])]
    normalized_headers = [_normalize_header_value(header) for header in headers]
    expected_headers = [_normalize_header_value(header) for header in ASSIGNMENTS_TEMPLATE_HEADERS]
    if normalized_headers != expected_headers:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid CSV header. Expected: "
                + ", ".join(ASSIGNMENTS_TEMPLATE_HEADERS)
            ),
        )

    courses = db.query(Course).all()
    teachers = db.query(Teacher).all()
    groups = db.query(StudentGroup).all()
    classrooms = db.query(Classroom).all()

    course_lookup: Dict[str, Course] = {}
    for course in courses:
        for alias in [course.name, course.code]:
            normalized = _normalize_lookup_value(alias or "")
            if normalized and normalized not in course_lookup:
                course_lookup[normalized] = course

    teacher_lookup: Dict[str, Teacher] = {}
    for teacher in teachers:
        for alias in [teacher.full_name, teacher.code]:
            normalized = _normalize_lookup_value(alias or "")
            if normalized and normalized not in teacher_lookup:
                teacher_lookup[normalized] = teacher

    group_lookup: Dict[str, StudentGroup] = {}
    for group in groups:
        aliases = [group.code, f"Grade {group.code}"]
        if group.code.lower().startswith("grade "):
            aliases.append(group.code[6:])
        for alias in aliases:
            normalized = _normalize_lookup_value(alias or "")
            if normalized and normalized not in group_lookup:
                group_lookup[normalized] = group

    classroom_lookup: Dict[str, Classroom] = {}
    for classroom in classrooms:
        normalized = _normalize_lookup_value(classroom.code or "")
        if normalized and normalized not in classroom_lookup:
            classroom_lookup[normalized] = classroom

    rows_total = 0
    rows_imported = 0
    teacher_links_created = 0
    group_links_created = 0
    duplicates_skipped = 0
    ignored_schedule_fields_rows = 0
    errors: List[str] = []
    warnings: List[str] = []

    if detected_encoding not in {"utf-8", "utf-8-sig"}:
        warnings.append(
            f"CSV decoded as {detected_encoding}; recommended encoding is UTF-8"
        )
    if detected_delimiter != ",":
        warnings.append(f"CSV delimiter '{detected_delimiter}' detected and supported")

    try:
        for row_number, row in enumerate(reader, start=2):
            teacher_raw = (row.get("Teacher Names") or "").strip()
            class_raw = (row.get("Class Names") or "").strip()
            subject_raw = (row.get("Subject Names") or "").strip()
            room_raw = (row.get("Room Names") or "").strip()
            lessons_raw = (row.get("No. of Lessons") or "").strip()
            length_raw = (row.get("Length") or "").strip()

            if not any([teacher_raw, class_raw, subject_raw, room_raw, lessons_raw, length_raw]):
                continue

            rows_total += 1

            try:
                lessons_count = int(lessons_raw)
                lesson_length = int(length_raw)
                if lessons_count <= 0 or lesson_length <= 0:
                    raise ValueError()
            except ValueError:
                errors.append(
                    f"Row {row_number}: 'No. of Lessons' and 'Length' must be positive integers"
                )
                continue

            teacher_tokens = _split_template_values(teacher_raw)
            class_tokens = _split_template_values(class_raw)
            subject_tokens = _split_template_values(subject_raw)
            room_tokens = _split_template_values(room_raw)

            if not teacher_tokens or not class_tokens or not subject_tokens:
                errors.append(
                    f"Row {row_number}: 'Teacher Names', 'Class Names' and 'Subject Names' are required"
                )
                continue

            resolved_teachers: List[Teacher] = []
            resolved_groups: List[StudentGroup] = []
            resolved_courses: List[Course] = []

            missing_teachers: List[str] = []
            missing_groups: List[str] = []
            missing_courses: List[str] = []

            seen_teacher_ids = set()
            seen_group_ids = set()
            seen_course_ids = set()

            for token in teacher_tokens:
                teacher = teacher_lookup.get(_normalize_lookup_value(token))
                if not teacher:
                    missing_teachers.append(token)
                    continue
                if teacher.id not in seen_teacher_ids:
                    resolved_teachers.append(teacher)
                    seen_teacher_ids.add(teacher.id)

            for token in class_tokens:
                group = group_lookup.get(_normalize_lookup_value(token))
                if not group:
                    missing_groups.append(token)
                    continue
                if group.id not in seen_group_ids:
                    resolved_groups.append(group)
                    seen_group_ids.add(group.id)

            for token in subject_tokens:
                course = course_lookup.get(_normalize_lookup_value(token))
                if not course:
                    missing_courses.append(token)
                    continue
                if course.id not in seen_course_ids:
                    resolved_courses.append(course)
                    seen_course_ids.add(course.id)

            if missing_teachers or missing_groups or missing_courses:
                missing_parts = []
                if missing_teachers:
                    missing_parts.append(f"teachers: {', '.join(missing_teachers)}")
                if missing_groups:
                    missing_parts.append(f"classes: {', '.join(missing_groups)}")
                if missing_courses:
                    missing_parts.append(f"subjects: {', '.join(missing_courses)}")

                errors.append(f"Row {row_number}: unresolved entities -> {'; '.join(missing_parts)}")
                continue

            if room_tokens:
                missing_rooms = []
                for token in room_tokens:
                    if _normalize_lookup_value(token) not in classroom_lookup:
                        missing_rooms.append(token)
                if missing_rooms:
                    warnings.append(
                        f"Row {row_number}: rooms not found (ignored for assignments): {', '.join(missing_rooms)}"
                    )

            for course in resolved_courses:
                for teacher in resolved_teachers:
                    if teacher in course.teachers:
                        duplicates_skipped += 1
                    else:
                        course.teachers.append(teacher)
                        teacher_links_created += 1

                for group in resolved_groups:
                    if group in course.groups:
                        duplicates_skipped += 1
                    else:
                        course.groups.append(group)
                        group_links_created += 1

            rows_imported += 1
            ignored_schedule_fields_rows += 1

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"❌ CSV assignment import failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to import assignments: {str(exc)}") from exc

    return {
        "message": "Assignments CSV imported",
        "rows_total": rows_total,
        "rows_imported": rows_imported,
        "teacher_links_created": teacher_links_created,
        "group_links_created": group_links_created,
        "duplicates_skipped": duplicates_skipped,
        "ignored_schedule_fields_rows": ignored_schedule_fields_rows,
        "errors": errors,
        "warnings": warnings,
    }


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    course_id: int,
    teacher_id: int,
    group_id: int,
    db: Session = Depends(get_db)
):
    """Видалити призначення курсу викладачу і групі."""
    
    # Перевіряємо чи існують сутності
    course = db.query(Course).filter(Course.id == course_id).first()
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    group = db.query(StudentGroup).filter(StudentGroup.id == group_id).first()
    
    if not course:
        raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
    if not teacher:
        raise HTTPException(status_code=404, detail=f"Teacher {teacher_id} not found")
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_id} not found")
    
    # Видаляємо зв'язки
    if teacher in course.teachers:
        course.teachers.remove(teacher)
    
    if group in course.groups:
        course.groups.remove(group)
    
    db.commit()
    
    return {"message": "Assignment deleted successfully"}


@router.post("/assignments/auto")
def auto_assign_courses(
    min_weekly_lessons_per_group: int = Query(10, ge=1, le=40),
    teachers_per_course: int = Query(2, ge=1, le=3),
    max_groups_per_course: int = Query(4, ge=1, le=20),
    strict_teacher_load: bool = Query(True),
    db: Session = Depends(get_db)
):
    """Автоматичне AI-призначення курсів викладачам та групам.
    
    Логіка призначення:
    1. Викладачі з певного департаменту отримують курси схожої тематики
    2. Групи призначаються курсам відповідно до року навчання та складності
    3. Враховується навантаження викладачів (max_hours_per_week)
    4. Розподіл намагається бути збалансованим
    """
    try:
        logger.info(
            "🤖 Початок автоматичного AI-призначення... "
            f"min_weekly={min_weekly_lessons_per_group}, "
            f"teachers_per_course={teachers_per_course}, "
            f"max_groups_per_course={max_groups_per_course}, "
            f"strict_teacher_load={strict_teacher_load}"
        )
        
        # Отримуємо всі сутності
        courses = db.query(Course).all()
        teachers = db.query(Teacher).all()
        groups = db.query(StudentGroup).all()
        
        if not courses or not teachers or not groups:
            raise HTTPException(
                status_code=400,
                detail="Недостатньо даних для призначення. Створіть курси, викладачів та групи."
            )
        
        # Очищуємо існуючі призначення
        for course in courses:
            course.teachers.clear()
            course.groups.clear()
        db.commit()
        
        assignments_count = 0
        
        # Мапінг департаментів на предмети
        department_subject_map = {
            "Математика": ["математика", "алгоритми", "структури даних"],
            "Інформатика": ["програмування", "бази даних", "операційні системи", "мережі", "штучний інтелект", "веб", "мобільна", "кібербезпека"],
            "Фізика": ["фізика"],
            "Хімія": ["хімія"],
            "Філологія": ["література", "мова"],
            "Іноземні мови": ["англійська", "німецька", "французька"],
            "Біологія": ["біологія"],
            "Економіка": ["економічна", "економіка"],
            "Психологія": ["психологія"],
            "Історія": ["історія"]
        }
        
        # Мапінг складності курсу на рік навчання
        difficulty_to_year = {
            1: [1, 2],  # Легкі курси для 1-2 курсів
            2: [1, 2, 3],
            3: [2, 3, 4],
            4: [3, 4],  # Важкі курси для старших курсів
            5: [4]      # Найважчі тільки для 4 курсу
        }
        
        # Індекси для швидкого доступу
        group_by_id = {g.id: g for g in groups}
        course_groups: Dict[int, set] = {c.id: set() for c in courses}
        group_hours: Dict[int, int] = {g.id: 0 for g in groups}

        def _course_suitable_for_group(course: Course, group: StudentGroup) -> bool:
            suitable_years = difficulty_to_year.get(course.difficulty, [1, 2, 3, 4])
            return group.year in suitable_years

        def _add_group_to_course(course: Course, group: StudentGroup) -> bool:
            if group.id in course_groups[course.id]:
                return False
            if len(course_groups[course.id]) >= max_groups_per_course:
                return False
            course_groups[course.id].add(group.id)
            group_hours[group.id] += max(1, int(course.hours_per_week or 0))
            return True

        # 1) Coverage-first: добираємо мінімум занять для кожної групи
        unresolved_groups = []
        for group in sorted(groups, key=lambda g: (g.year, g.code)):
            safety_counter = 0
            while group_hours[group.id] < min_weekly_lessons_per_group and safety_counter < len(courses) * 2:
                safety_counter += 1
                deficit = min_weekly_lessons_per_group - group_hours[group.id]

                preferred_courses = [
                    c
                    for c in courses
                    if _course_suitable_for_group(c, group)
                    and group.id not in course_groups[c.id]
                    and len(course_groups[c.id]) < max_groups_per_course
                ]

                fallback_courses = [
                    c
                    for c in courses
                    if group.id not in course_groups[c.id]
                    and len(course_groups[c.id]) < max_groups_per_course
                ]

                candidate_courses = preferred_courses if preferred_courses else fallback_courses
                if not candidate_courses:
                    break

                # Кращий матч: ближче до дефіциту + менш перевантажений курс
                candidate_courses.sort(
                    key=lambda c: (
                        abs(deficit - max(1, int(c.hours_per_week or 0))),
                        len(course_groups[c.id]),
                        c.difficulty,
                    )
                )

                if not _add_group_to_course(candidate_courses[0], group):
                    break

            if group_hours[group.id] < min_weekly_lessons_per_group:
                unresolved_groups.append(group.id)

        # 2) Гарантуємо, що кожен курс має хоча б одну групу
        for course in courses:
            if course_groups[course.id]:
                continue
            preferred_groups = [g for g in groups if _course_suitable_for_group(course, g)]
            candidate_groups = preferred_groups if preferred_groups else groups
            candidate_groups = sorted(candidate_groups, key=lambda g: (group_hours[g.id], g.year, g.code))
            for group in candidate_groups:
                if _add_group_to_course(course, group):
                    break

        # 3) Після груп - призначаємо викладачів з урахуванням навантаження
        teacher_load: Dict[int, float] = {t.id: 0.0 for t in teachers}
        teacher_capacity: Dict[int, float] = {
            t.id: float(t.max_hours_per_week if (t.max_hours_per_week and t.max_hours_per_week > 0) else 10**9)
            for t in teachers
        }

        for course in courses:
            course_name_lower = (course.name or "").lower()
            course_weekly_demand = max(1, int(course.hours_per_week or 0)) * max(1, len(course_groups[course.id]))

            def _teacher_match_score(teacher: Teacher) -> tuple:
                dept_keywords = department_subject_map.get(teacher.department, []) if teacher.department else []
                matched = any(keyword in course_name_lower for keyword in dept_keywords)
                utilization = teacher_load[teacher.id] / max(teacher_capacity[teacher.id], 1.0)
                # Перевага: релевантний департамент + менша утилізація
                return (0 if matched else 1, utilization, teacher_load[teacher.id])

            ranked_teachers = sorted(teachers, key=_teacher_match_score)

            selected_teachers: List[Teacher] = []
            max_teacher_count = min(max(1, teachers_per_course), len(ranked_teachers))

            for teacher in ranked_teachers:
                if len(selected_teachers) >= max_teacher_count:
                    break
                projected_share = course_weekly_demand / float(len(selected_teachers) + 1)
                projected_load = teacher_load[teacher.id] + projected_share
                if strict_teacher_load and projected_load > teacher_capacity[teacher.id]:
                    continue
                selected_teachers.append(teacher)

            if not selected_teachers:
                # Fallback: мінімально завантажений викладач
                selected_teachers = [min(ranked_teachers, key=lambda t: teacher_load[t.id])]

            per_teacher_share = course_weekly_demand / float(len(selected_teachers))
            for teacher in selected_teachers:
                teacher_load[teacher.id] += per_teacher_share
                if teacher not in course.teachers:
                    course.teachers.append(teacher)

            # Фактичне застосування груп до курсу
            for group_id in sorted(course_groups[course.id]):
                group = group_by_id.get(group_id)
                if group and group not in course.groups:
                    course.groups.append(group)
                    assignments_count += 1
        
        db.commit()
        
        logger.info(f"✅ Автоматично створено {assignments_count} призначень")
        
        groups_below_target = sum(1 for g in groups if group_hours[g.id] < min_weekly_lessons_per_group)

        # Статистика навантаження викладачів
        teacher_stats = [
            {
                "teacher": t.full_name,
                "hours": round(float(teacher_load[t.id]), 2),
                "max_hours": t.max_hours_per_week,
                "utilization": round(float(teacher_load[t.id]) / t.max_hours_per_week * 100, 1) if t.max_hours_per_week > 0 else 0
            }
            for t in teachers
        ]

        group_stats = [
            {
                "group": g.code,
                "year": g.year,
                "assigned_hours": int(group_hours[g.id]),
                "target_hours": int(min_weekly_lessons_per_group),
                "missing_hours": max(0, int(min_weekly_lessons_per_group - group_hours[g.id])),
            }
            for g in sorted(groups, key=lambda grp: (grp.year, grp.code))
        ]
        
        return {
            "message": "AI-призначення успішно виконано",
            "assignments_created": assignments_count,
            "teacher_stats": teacher_stats,
            "group_stats": group_stats,
            "groups_below_target": int(groups_below_target),
            "requested_min_weekly_lessons": int(min_weekly_lessons_per_group),
            "unresolved_group_ids": unresolved_groups,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Помилка при автопризначенні: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка автопризначення: {str(e)}")
