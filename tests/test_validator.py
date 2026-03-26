import datetime as dt

from imscheduler.models import ScheduleResults, ScheduledLesson, TimeSlot, TimeSlotTemplate
from imscheduler.validator import Validator


def test_validate_input_missing_fields():
    validator = Validator()
    problems = validator.validate_input({"groups": []})
    assert problems, "Очікується помилка при відсутності обов'язкових полів"


def test_validate_schedule_detects_conflict():
    validator = Validator()
    template = TimeSlotTemplate.parse(0, "08:00-08:45")
    lesson = ScheduledLesson(
        subject="math",
        teacher="T1",
        group="G1",
        classroom="101",
        timeslot=TimeSlot(day_index=0, slot_template=template),
    )
    results = ScheduleResults(schedule=[lesson, lesson])
    warnings = validator.validate_schedule(results)
    assert any("викладача" in warn for warn in warnings)
