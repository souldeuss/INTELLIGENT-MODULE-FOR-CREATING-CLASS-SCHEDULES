"""SQLAlchemy моделі бази даних."""
from datetime import datetime, time
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Time, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# Many-to-Many зв'язок між викладачами та курсами
teacher_course = Table(
    "teacher_course",
    Base.metadata,
    Column("teacher_id", Integer, ForeignKey("teachers.id")),
    Column("course_id", Integer, ForeignKey("courses.id")),
)

# Many-to-Many зв'язок між групами та курсами
group_course = Table(
    "group_course",
    Base.metadata,
    Column("group_id", Integer, ForeignKey("student_groups.id")),
    Column("course_id", Integer, ForeignKey("courses.id")),
)


class Course(Base):
    """Навчальний курс."""

    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    credits = Column(Integer, default=3)
    hours_per_week = Column(Integer, default=2)
    requires_lab = Column(Boolean, default=False)
    preferred_classroom_type = Column(String(50), nullable=True)
    difficulty = Column(Integer, default=1)  # 1-5 шкала складності

    # Relationships
    teachers = relationship("Teacher", secondary=teacher_course, back_populates="courses")
    groups = relationship("StudentGroup", secondary=group_course, back_populates="courses")
    scheduled_classes = relationship("ScheduledClass", back_populates="course")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Teacher(Base):
    """Викладач."""

    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    full_name = Column(String(200), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    department = Column(String(100), nullable=True)
    max_hours_per_week = Column(Integer, default=18)

    # Preferences (JSON або окрема таблиця)
    preferred_days = Column(String(50), nullable=True)  # "1,2,3" - ПН, ВТ, СР
    avoid_early_slots = Column(Boolean, default=False)
    avoid_late_slots = Column(Boolean, default=False)

    # Relationships
    courses = relationship("Course", secondary=teacher_course, back_populates="teachers")
    scheduled_classes = relationship("ScheduledClass", back_populates="teacher")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StudentGroup(Base):
    """Студентська група."""

    __tablename__ = "student_groups"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    year = Column(Integer, nullable=False)  # Рік навчання (1-4)
    students_count = Column(Integer, default=25)
    specialization = Column(String(100), nullable=True)

    # Relationships
    courses = relationship("Course", secondary=group_course, back_populates="groups")
    scheduled_classes = relationship("ScheduledClass", back_populates="group")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Classroom(Base):
    """Аудиторія."""

    __tablename__ = "classrooms"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    building = Column(String(50), nullable=True)
    floor = Column(Integer, nullable=True)
    capacity = Column(Integer, nullable=False)
    classroom_type = Column(String(50), default="general")  # general, lab, computer, gym
    has_projector = Column(Boolean, default=True)
    has_computers = Column(Boolean, default=False)

    # Geographic coordinates (для PostGIS)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Relationships
    scheduled_classes = relationship("ScheduledClass", back_populates="classroom")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Timeslot(Base):
    """Часовий слот (день тижня + час)."""

    __tablename__ = "timeslots"

    id = Column(Integer, primary_key=True, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0=ПН, 1=ВТ, ..., 4=ПТ
    period_number = Column(Integer, nullable=False)  # 1-7 (номер пари)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    scheduled_classes = relationship("ScheduledClass", back_populates="timeslot")

    created_at = Column(DateTime, default=datetime.utcnow)


class ScheduledClass(Base):
    """Призначене заняття (результат розкладу)."""

    __tablename__ = "scheduled_classes"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("student_groups.id"), nullable=False)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    timeslot_id = Column(Integer, ForeignKey("timeslots.id"), nullable=False)

    # Additional info
    week_number = Column(Integer, nullable=True)  # Для 2-тижневого розкладу
    is_locked = Column(Boolean, default=False)  # Заборонити редагування
    notes = Column(Text, nullable=True)

    # Relationships
    course = relationship("Course", back_populates="scheduled_classes")
    teacher = relationship("Teacher", back_populates="scheduled_classes")
    group = relationship("StudentGroup", back_populates="scheduled_classes")
    classroom = relationship("Classroom", back_populates="scheduled_classes")
    timeslot = relationship("Timeslot", back_populates="scheduled_classes")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Constraint(Base):
    """Обмеження (жорсткі та м'які)."""

    __tablename__ = "constraints"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    constraint_type = Column(String(20), nullable=False)  # "hard" або "soft"
    weight = Column(Float, default=1.0)  # Вага для м'яких обмежень
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    # Параметри обмеження (JSON або окремі поля)
    target_entity = Column(String(50), nullable=True)  # teacher, group, classroom
    target_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class ScheduleGeneration(Base):
    """Історія генерацій розкладу."""

    __tablename__ = "schedule_generations"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(20), nullable=False)  # pending, running, completed, failed
    iterations = Column(Integer, default=1000)
    current_iteration = Column(Integer, default=0)  # Поточна ітерація для прогресу
    final_score = Column(Float, nullable=True)
    hard_violations = Column(Integer, default=0)
    soft_violations = Column(Integer, default=0)
    execution_time = Column(Float, nullable=True)  # секунди
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
