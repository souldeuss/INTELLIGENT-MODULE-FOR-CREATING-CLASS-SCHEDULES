"""API для генерації рандомних тестових даних."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import random
import logging
from datetime import time

from ..models.database import (
    Course,
    Teacher,
    StudentGroup,
    Classroom,
    Timeslot,
    ScheduledClass,
)
from ..core.database_session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


# Українські імена та прізвища
FIRST_NAMES = [
    "Олена", "Максим", "Андрій", "Марія", "Тарас", "Ірина", "Олег", "Наталія",
    "Василь", "Софія", "Дмитро", "Анна", "Богдан", "Юлія", "Ігор", "Катерина",
    "Сергій", "Віктор", "Людмила", "Петро"
]

LAST_NAMES = [
    "Іванов", "Петренко", "Сидоренко", "Коваленко", "Бондаренко", "Шевченко",
    "Мельник", "Ткаченко", "Кравченко", "Морозов", "Павленко", "Савченко",
    "Данильченко", "Олійник", "Кузнєцов", "Поліщук", "Романенко", "Гончаренко"
]

PATRONYMICS = [
    "Петрович", "Володимирович", "Іванович", "Сергіївна", "Миколайович",
    "Олександрович", "Васильович", "Андріївна", "Ярославович", "Дмитрівна"
]

DEPARTMENTS = [
    "Філологія", "Математика", "Інформатика", "Фізика", "Іноземні мови",
    "Хімія", "Біологія", "Економіка", "Психологія", "Історія"
]

COURSE_SUBJECTS = [
    "Вища математика", "Програмування", "Фізика", "Хімія", "Англійська мова",
    "Українська література", "Історія України", "Філософія", "Економічна теорія",
    "Психологія", "Біологія", "Географія", "Алгоритми та структури даних",
    "Бази даних", "Операційні системи", "Комп'ютерні мережі", "Штучний інтелект",
    "Веб-технології", "Мобільна розробка", "Кібербезпека"
]

COURSE_TYPES = ["lecture", "practice", "lab"]

CLASSROOM_TYPES = ["lecture", "computer_lab", "lab", "seminar"]

BUILDINGS = ["A", "B", "C", "D"]

SPECIALIZATIONS = [
    "Комп'ютерні науки", "Прикладна математика", "Фізика", "Філологія",
    "Економіка", "Психологія", "Хімія", "Біологія"
]


def generate_full_name() -> str:
    """Генерує повне ім'я українською."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    patronymic = random.choice(PATRONYMICS)
    
    # Додаємо правильні закінчення
    if first in ["Олена", "Марія", "Ірина", "Наталія", "Софія", "Анна", "Юлія", "Катерина", "Людмила"]:
        last = last + "а"
        if patronymic.endswith("ич"):
            patronymic = patronymic[:-2] + "івна"
    else:
        patronymic = patronymic if patronymic.endswith("ич") else patronymic + "ович"
    
    return f"{last} {first} {patronymic}"


def generate_email(full_name: str, index: int = 0, domain: str = "univ.edu") -> str:
    """Генерує унікальний email на основі імені."""
    parts = full_name.split()
    last_name = parts[0].lower()
    first_name = parts[1].lower() if len(parts) > 1 else ""
    
    # Транслітерація
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e', 'є': 'ye',
        'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y', 'к': 'k', 'л': 'l',
        'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'yu', 'я': 'ya'
    }
    
    email_last = ''.join(translit.get(c, c) for c in last_name)
    email_first = ''.join(translit.get(c, c) for c in first_name)
    
    # Створюємо унікальний email: прізвище.ім'я або прізвище.ім'я.номер
    if index == 0:
        return f"{email_last}.{email_first}@{domain}"
    else:
        return f"{email_last}.{email_first}{index}@{domain}"


@router.post("/generate")
def generate_random_data(
    num_teachers: int = 8,
    num_groups: int = 6,
    num_courses: int = 14,
    num_classrooms: int = 18,  # Збільшено з 12 до 18 для більшої кількості слотів
    db: Session = Depends(get_db),
):
    """
    Генерує рандомні тестові дані для системи розкладу.
    
    Параметри:
    - num_teachers: кількість викладачів (за замовчуванням 8)
    - num_groups: кількість груп (за замовчуванням 6)
    - num_courses: кількість курсів (за замовчуванням 14)
    - num_classrooms: кількість аудиторій (за замовчуванням 18, було 12)
    """
    try:
        logger.info("🎲 Початок генерації рандомних даних...")
        
        # ЗАВЖДИ очищаємо дані перед генерацією щоб уникнути конфліктів
        logger.info("🗑️ Очищення існуючих даних...")
        try:
            # Видалення в правильному порядку (через foreign keys)
            # Спочатку видаляємо записи з таблиць асоціацій через raw SQL
            db.execute(text("DELETE FROM teacher_course"))
            db.execute(text("DELETE FROM group_course"))
            
            # Потім основні таблиці
            db.query(ScheduledClass).delete()
            db.query(Course).delete()
            db.query(Teacher).delete()
            db.query(StudentGroup).delete()
            db.query(Classroom).delete()
            db.query(Timeslot).delete()
            db.commit()
            logger.info("✅ База даних очищена")
        except Exception as e:
            logger.warning(f"⚠️ Помилка при очищенні (можливо база вже порожня): {e}")
            db.rollback()
        
        # 1. Генерація таймслотів (5 днів × 6 уроків по 45 хв = 30 слотів)
        logger.info("⏰ Генерація таймслотів...")
        days = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця"]
        periods = [
            {"period": 1, "start": time(8, 30), "end": time(9, 15)},
            {"period": 2, "start": time(9, 25), "end": time(10, 10)},
            {"period": 3, "start": time(10, 20), "end": time(11, 5)},
            {"period": 4, "start": time(11, 15), "end": time(12, 0)},
            {"period": 5, "start": time(12, 10), "end": time(12, 55)},
            {"period": 6, "start": time(13, 5), "end": time(13, 50)},
        ]
        
        timeslots = []
        for day_idx in range(5):
            for period in periods:
                timeslot = Timeslot(
                    day_of_week=day_idx,
                    period_number=period["period"],
                    start_time=period["start"],
                    end_time=period["end"],
                    is_active=True
                )
                db.add(timeslot)
                timeslots.append(timeslot)
        
        db.commit()
        logger.info(f"✅ Створено {len(timeslots)} таймслотів")
        
        # 2. Генерація аудиторій
        logger.info("🏫 Генерація аудиторій...")
        classrooms = []
        
        # Розподіл типів аудиторій з більшою кількістю великих аудиторій
        # 50% lecture (великі), 20% computer_lab, 15% lab, 15% seminar
        classroom_types_weighted = (
            ["lecture"] * 6 +  # 50%
            ["computer_lab"] * 2 +  # ~17%
            ["lab"] * 2 +  # ~17%
            ["seminar"] * 2  # ~17%
        )
        
        for i in range(num_classrooms):
            classroom_type = random.choice(classroom_types_weighted)
            building = random.choice(BUILDINGS)
            floor = random.randint(1, 3)
            
            # Збільшена місткість для забезпечення достатньої кількості місць
            capacity = {
                "lecture": random.randint(40, 120),  # Було 60-120, тепер 40-120
                "computer_lab": random.randint(25, 35),  # Було 20-30, тепер 25-35
                "lab": random.randint(20, 30),  # Було 15-25, тепер 20-30
                "seminar": random.randint(30, 40)  # Було 20-30, тепер 30-40
            }[classroom_type]
            
            code = f"{building}{floor}{i+1:02d}"
            
            classroom = Classroom(
                code=code,
                building=building,
                floor=floor,
                capacity=capacity,
                classroom_type=classroom_type,
                has_projector=random.choice([True, False]),
                has_computers=classroom_type == "computer_lab"
            )
            db.add(classroom)
            classrooms.append(classroom)
        
        db.commit()
        logger.info(f"✅ Створено {len(classrooms)} аудиторій")
        logger.info(f"   📊 Типи: lecture={sum(1 for c in classrooms if c.classroom_type=='lecture')}, "
                   f"computer_lab={sum(1 for c in classrooms if c.classroom_type=='computer_lab')}, "
                   f"lab={sum(1 for c in classrooms if c.classroom_type=='lab')}, "
                   f"seminar={sum(1 for c in classrooms if c.classroom_type=='seminar')}")
        
        # 3. Генерація викладачів
        logger.info("👨‍🏫 Генерація викладачів...")
        teachers = []
        used_names = set()
        used_emails = set()
        
        for i in range(num_teachers):
            # Унікальне ім'я
            while True:
                full_name = generate_full_name()
                if full_name not in used_names:
                    used_names.add(full_name)
                    break
            
            # Унікальний email
            email_index = 0
            while True:
                email = generate_email(full_name, email_index)
                if email not in used_emails:
                    used_emails.add(email)
                    break
                email_index += 1
            
            teacher = Teacher(
                code=f"T{i+1:03d}",
                full_name=full_name,
                email=email,
                department=random.choice(DEPARTMENTS),
                max_hours_per_week=random.choice([16, 18, 20, 22]),
                avoid_early_slots=random.choice([True, False]),
                avoid_late_slots=random.choice([True, False])
            )
            db.add(teacher)
            teachers.append(teacher)
        
        db.commit()
        logger.info(f"✅ Створено {len(teachers)} викладачів")
        
        # 4. Генерація груп
        logger.info("👥 Генерація студентських груп...")
        groups = []
        prefixes = ["КН", "ПМ", "ФЗ", "ХМ", "БЛ", "ЕК", "ПС", "ІС"]
        used_codes = set()
        
        for i in range(num_groups):
            # Генеруємо унікальний код групи
            while True:
                prefix = random.choice(prefixes)
                year = random.randint(1, 4)
                group_num = random.randint(1, 3)
                code = f"{prefix}-{year}{group_num}"
                if code not in used_codes:
                    used_codes.add(code)
                    break
            
            group = StudentGroup(
                code=code,
                year=year,
                students_count=random.randint(20, 35),
                specialization=random.choice(SPECIALIZATIONS)
            )
            db.add(group)
            groups.append(group)
        
        db.commit()
        logger.info(f"✅ Створено {len(groups)} груп")
        
        # 5. Генерація курсів
        logger.info("📚 Генерація курсів...")
        courses = []
        unique_subject_limit = len(COURSE_SUBJECTS)
        
        for i in range(num_courses):
            # Спочатку використовуємо унікальні предмети, потім генеруємо додаткові модулі.
            if i < unique_subject_limit:
                subject = COURSE_SUBJECTS[i]
            else:
                base_subject = random.choice(COURSE_SUBJECTS)
                module_index = i - unique_subject_limit + 2
                subject = f"{base_subject} (модуль {module_index})"
            
            course_type = random.choice(COURSE_TYPES)
            
            # Вимоги до аудиторії залежать від типу курсу
            if course_type == "lab":
                preferred_type = random.choice(["lab", "computer_lab"])
                requires_lab = True
            elif course_type == "lecture":
                preferred_type = "lecture"
                requires_lab = False
            else:
                preferred_type = random.choice(["seminar", "lecture"])
                requires_lab = False
            
            course = Course(
                code=f"C{i+1:03d}",
                name=subject,
                credits=random.choice([3, 4, 5, 6]),
                hours_per_week=random.choice([2, 3, 4]),
                requires_lab=requires_lab,
                preferred_classroom_type=preferred_type,
                difficulty=random.randint(1, 5)
            )
            db.add(course)
            courses.append(course)
        
        db.commit()
        logger.info(f"✅ Створено {len(courses)} курсів")
        
        # 6. Створення призначень (course-teacher-group)
        logger.info("🔗 Створення призначень курсів...")
        assignments_count = 0
        
        for course in courses:
            # Призначаємо 1-2 викладачів на курс
            num_teachers_for_course = random.randint(1, min(2, len(teachers)))
            assigned_teachers = random.sample(teachers, num_teachers_for_course)
            
            for teacher in assigned_teachers:
                if teacher not in course.teachers:
                    course.teachers.append(teacher)
            
            # Призначаємо 2-4 групи на курс
            num_groups_for_course = random.randint(2, min(4, len(groups)))
            assigned_groups = random.sample(groups, num_groups_for_course)
            
            for group in assigned_groups:
                if group not in course.groups:
                    course.groups.append(group)
                    assignments_count += 1
        
        db.commit()
        logger.info(f"✅ Створено {assignments_count} призначень (курс-викладач-група)")
        
        # Статистика
        stats = {
            "timeslots": len(timeslots),
            "classrooms": len(classrooms),
            "teachers": len(teachers),
            "groups": len(groups),
            "courses": len(courses),
            "assignments": assignments_count,
            "message": "Рандомні дані успішно згенеровані! ✅"
        }
        
        logger.info("🎉 Генерація завершена успішно!")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Помилка при генерації даних: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка генерації даних: {str(e)}")


@router.delete("/clear")
def clear_all_data(db: Session = Depends(get_db)):
    """Видаляє всі дані з бази."""
    try:
        logger.info("🗑️ Очищення бази даних...")
        
        # Видалення в правильному порядку (через foreign keys)
        db.query(ScheduledClass).delete()
        db.query(Course).delete()
        db.query(Teacher).delete()
        db.query(StudentGroup).delete()
        db.query(Classroom).delete()
        db.query(Timeslot).delete()
        
        db.commit()
        logger.info("✅ База даних очищена")
        
        return {"message": "Всі дані успішно видалені"}
        
    except Exception as e:
        logger.error(f"❌ Помилка при очищенні: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка очищення: {str(e)}")
