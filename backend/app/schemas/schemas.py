"""Pydantic схеми для API."""
from datetime import datetime, time
from typing import List, Optional

from pydantic import BaseModel, Field


# --- Course Schemas ---
class CourseBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    credits: int = Field(default=3, ge=1, le=10)
    hours_per_week: int = Field(default=2, ge=1, le=10)
    requires_lab: bool = False
    preferred_classroom_type: Optional[str] = None
    difficulty: int = Field(default=1, ge=1, le=5)


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    credits: Optional[int] = None
    hours_per_week: Optional[int] = None
    requires_lab: Optional[bool] = None
    preferred_classroom_type: Optional[str] = None
    difficulty: Optional[int] = None


class CourseResponse(CourseBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Teacher Schemas ---
class TeacherBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    full_name: str = Field(..., min_length=1, max_length=200)
    email: Optional[str] = None
    department: Optional[str] = None
    max_hours_per_week: int = Field(default=18, ge=1, le=40)
    preferred_days: Optional[str] = None
    avoid_early_slots: bool = False
    avoid_late_slots: bool = False


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    max_hours_per_week: Optional[int] = None
    preferred_days: Optional[str] = None
    avoid_early_slots: Optional[bool] = None
    avoid_late_slots: Optional[bool] = None


class TeacherResponse(TeacherBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Student Group Schemas ---
class StudentGroupBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    year: int = Field(..., ge=1, le=6)
    students_count: int = Field(default=25, ge=1, le=100)
    specialization: Optional[str] = None


class StudentGroupCreate(StudentGroupBase):
    pass


class StudentGroupUpdate(BaseModel):
    year: Optional[int] = None
    students_count: Optional[int] = None
    specialization: Optional[str] = None


class StudentGroupResponse(StudentGroupBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Classroom Schemas ---
class ClassroomBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    building: Optional[str] = None
    floor: Optional[int] = None
    capacity: int = Field(..., ge=1, le=500)
    classroom_type: str = Field(default="general")
    has_projector: bool = True
    has_computers: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ClassroomCreate(ClassroomBase):
    pass


class ClassroomUpdate(BaseModel):
    building: Optional[str] = None
    floor: Optional[int] = None
    capacity: Optional[int] = None
    classroom_type: Optional[str] = None
    has_projector: Optional[bool] = None
    has_computers: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ClassroomResponse(ClassroomBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Timeslot Schemas ---
class TimeslotBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=4)
    period_number: int = Field(..., ge=1, le=10)
    start_time: time
    end_time: time
    is_active: bool = True


class TimeslotCreate(TimeslotBase):
    pass


class TimeslotResponse(TimeslotBase):
    id: int

    class Config:
        from_attributes = True


# --- Scheduled Class Schemas ---
class ScheduledClassBase(BaseModel):
    course_id: int
    teacher_id: int
    group_id: int
    classroom_id: int
    timeslot_id: int
    week_number: Optional[int] = None
    is_locked: bool = False
    notes: Optional[str] = None


class ScheduledClassCreate(ScheduledClassBase):
    pass


class ScheduledClassUpdate(BaseModel):
    classroom_id: Optional[int] = None
    timeslot_id: Optional[int] = None
    teacher_id: Optional[int] = None
    is_locked: Optional[bool] = None
    notes: Optional[str] = None


class ScheduledClassLock(BaseModel):
    locked: bool


class ScheduledClassResponse(ScheduledClassBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduledClassFullResponse(BaseModel):
    """Extended response with all related data for UI display."""
    id: int
    course_id: int
    teacher_id: int
    group_id: int
    classroom_id: int
    timeslot_id: int
    week_number: Optional[int] = None
    is_locked: bool = False
    notes: Optional[str] = None
    
    # Expanded fields for UI
    day_of_week: int  # 0-4 (Mon-Fri)
    period_number: int  # 1-6
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    course_code: str
    course_name: str
    teacher_name: str
    group_code: str
    classroom_code: str
    
    # Conflict info
    has_conflict: bool = False
    conflict_type: Optional[str] = None

    class Config:
        from_attributes = True


# --- Schedule Generation Schemas ---
class ScheduleGenerationRequest(BaseModel):
    iterations: int = Field(default=1000, ge=100, le=10000)
    use_existing: bool = Field(default=False)
    preserve_locked: bool = Field(default=True)
    model_version: Optional[str] = Field(default=None, description="Назва файлу моделі, наприклад actor_critic_20260327_120000.pt")


class ScheduleGenerationStatus(BaseModel):
    id: int
    status: str
    iterations: int
    current_iteration: int = 0  # Поточна ітерація для прогресу
    final_score: Optional[float] = None
    hard_violations: int
    soft_violations: int
    execution_time: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Analytics Schemas ---
class ClassroomUtilization(BaseModel):
    classroom_id: int
    classroom_code: str
    total_slots: int
    occupied_slots: int
    utilization_rate: float


class TeacherWorkload(BaseModel):
    teacher_id: int
    teacher_name: str
    assigned_hours: int
    max_hours: int
    workload_rate: float


class AnalyticsResponse(BaseModel):
    classroom_utilization: List[ClassroomUtilization]
    teacher_workload: List[TeacherWorkload]
    total_classes: int
    hard_constraint_violations: int
    soft_constraint_violations: int
    average_score: float
