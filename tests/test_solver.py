from imscheduler.config import Config
from imscheduler.models import Classroom, ConstraintContext, Group, LessonRequest, ScheduledLesson, Subject, Teacher, TimeSlot, TimeSlotTemplate
from imscheduler.solver import ConstraintSolver


def build_context():
    groups = {"G1": Group(id="G1", students_count=25)}
    subjects = {"physics": Subject(id="physics", name="Physics", requires_specialized=True)}
    teachers = {"T1": Teacher(id="T1", name="Teach", subjects=["physics"])}
    classrooms = {
        "Lab": Classroom(id="Lab", capacity=20, type="physics_lab"),
        "101": Classroom(id="101", capacity=30, type="general"),
    }
    return ConstraintContext(
        groups=groups,
        subjects=subjects,
        teachers=teachers,
        classrooms=classrooms,
        existing_schedule=[],
        specialized_map={}
    )


def test_assign_specialized_classroom_prefers_lab():
    config = Config(use_specialized_classrooms=True)
    solver = ConstraintSolver(config, build_context())
    subject = solver.context.subjects["physics"]
    classrooms = solver.assign_specialized_classrooms(subject)
    assert all(room.type == "physics_lab" for room in classrooms)


def test_detects_teacher_conflict():
    config = Config()
    solver = ConstraintSolver(config, build_context())
    template = TimeSlotTemplate.parse(0, "08:00-08:45")
    timeslot = TimeSlot(day_index=0, slot_template=template)
    lesson_req = LessonRequest(subject="physics", teacher="T1", group="G1", count=1)
    scheduled = ScheduledLesson(
        subject="physics",
        teacher="T1",
        group="G1",
        classroom="Lab",
        timeslot=timeslot,
    )
    assert solver.check_teacher_conflict(lesson_req, timeslot, [scheduled])
