"""Schedule Generation API."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
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


def _auto_export_schedule(db: Session, generation_id: int, stats: dict):
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
    
    meta = {
        "created_at": datetime.now().isoformat(),
        "generation_id": generation_id,
        "classes_count": len(classes_data),
        "best_reward": stats.get("best_reward", 0),
        "hard_violations": stats.get("final_hard_violations", 0),
        "soft_violations": stats.get("final_soft_violations", 0),
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
        args=(generation.id, request.iterations, request.preserve_locked, request.use_existing),
        daemon=True
    )
    thread.start()
    
    logger.info(f"✅ Запущено thread для генерації ID={generation.id}")

    return generation


def _run_generation(generation_id: int, iterations: int, preserve_locked: bool, use_existing: bool):
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

        # Навчання моделі
        logger.info(f"🎓 Початок тренування на {iterations} ітераціях...")
        trainer = PPOTrainer(env, state_dim, action_dim, device="cpu", progress_callback=update_progress, stop_callback=check_stop)
        episode_rewards, stats = trainer.train(num_iterations=iterations)
        
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

        logger.info(f"✅ Тренування завершено! Best reward: {stats.get('best_reward', 0):.2f}")

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

        # Видалення старого розкладу (якщо preserve_locked=False)
        if not preserve_locked:
            deleted = db.query(ScheduledClass).delete()
            logger.info(f"🗑️ Видалено {deleted} старих занять")
        elif use_existing:
            deleted = db.query(ScheduledClass).filter(ScheduledClass.is_locked == False).delete()
            logger.info(f"🗑️ Видалено {deleted} незафіксованих занять")

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
        generation.final_score = stats.get("best_reward", 0)
        
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
            _auto_export_schedule(db, generation_id, stats)
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
    
    metrics_path = Path(__file__).parent.parent.parent / "saved_models" / "training_metrics.json"
    
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="Training metrics not found. Train the model first.")
    
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
        
        files.append({
            "filename": f.name,
            "created_at": meta.get("created_at", datetime.fromtimestamp(stat.st_mtime).isoformat()),
            "size_kb": round(stat.st_size / 1024, 2),
            "classes_count": meta.get("classes_count", 0),
            "description": meta.get("description", ""),
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
    
    # Метадані
    meta = {
        "created_at": datetime.now().isoformat(),
        "classes_count": len(classes_data),
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
        logger.info("🤖 Початок автоматичного AI-призначення...")
        
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
        
        # Словник для відстеження навантаження викладачів
        teacher_load = {t.id: 0 for t in teachers}
        
        # Призначення викладачів до курсів
        for course in courses:
            suitable_teachers = []
            course_name_lower = course.name.lower()
            
            # Знаходимо викладачів з відповідного департаменту
            for teacher in teachers:
                if not teacher.department:
                    suitable_teachers.append(teacher)
                    continue
                    
                dept_keywords = department_subject_map.get(teacher.department, [])
                
                # Перевіряємо чи назва курсу містить ключові слова департаменту
                if any(keyword in course_name_lower for keyword in dept_keywords):
                    suitable_teachers.append(teacher)
            
            # Якщо не знайшли підходящих - беремо всіх
            if not suitable_teachers:
                suitable_teachers = teachers
            
            # Сортуємо викладачів за навантаженням (менш завантажені першими)
            suitable_teachers.sort(key=lambda t: teacher_load[t.id])
            
            # Призначаємо 1-2 викладачів
            num_teachers = min(2, len(suitable_teachers))
            for i in range(num_teachers):
                teacher = suitable_teachers[i]
                if teacher not in course.teachers:
                    course.teachers.append(teacher)
                    # Оновлюємо навантаження
                    teacher_load[teacher.id] += course.hours_per_week
        
        # Призначення груп до курсів
        for course in courses:
            suitable_groups = []
            
            # Визначаємо підходящі групи за складністю курсу
            suitable_years = difficulty_to_year.get(course.difficulty, [1, 2, 3, 4])
            
            for group in groups:
                if group.year in suitable_years:
                    suitable_groups.append(group)
            
            # Якщо не знайшли підходящих - беремо всі групи
            if not suitable_groups:
                suitable_groups = groups
            
            # Призначаємо 2-4 групи (або всі доступні)
            import random
            num_groups = min(random.randint(2, 4), len(suitable_groups))
            selected_groups = random.sample(suitable_groups, num_groups)
            
            for group in selected_groups:
                if group not in course.groups:
                    course.groups.append(group)
                    assignments_count += 1
        
        db.commit()
        
        logger.info(f"✅ Автоматично створено {assignments_count} призначень")
        
        # Статистика навантаження викладачів
        teacher_stats = [
            {
                "teacher": t.full_name,
                "hours": teacher_load[t.id],
                "max_hours": t.max_hours_per_week,
                "utilization": round(teacher_load[t.id] / t.max_hours_per_week * 100, 1) if t.max_hours_per_week > 0 else 0
            }
            for t in teachers
        ]
        
        return {
            "message": "AI-призначення успішно виконано",
            "assignments_created": assignments_count,
            "teacher_stats": teacher_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Помилка при автопризначенні: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка автопризначення: {str(e)}")
