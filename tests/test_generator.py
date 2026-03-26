from imscheduler.config import Config
from imscheduler.generator import ScheduleGenerator


def sample_data():
    return {
        "groups": [{"id": "10-A", "students_count": 28}],
        "subjects": [
            {"id": "math", "name": "Математика", "difficulty": 2},
            {"id": "physics", "name": "Фізика", "requires_specialized": True},
        ],
        "teachers": [
            {"id": "T001", "name": "Іваненко", "subjects": ["math"]},
            {"id": "T002", "name": "Петрова", "subjects": ["physics"]},
        ],
        "classrooms": [
            {"id": "101", "capacity": 30, "type": "general"},
            {"id": "Lab", "capacity": 20, "type": "physics_lab"}
        ],
        "lessons_pool": [
            {"subject": "math", "teacher": "T001", "group": "10-A", "count": 2},
            {"subject": "physics", "teacher": "T002", "group": "10-A", "count": 1}
        ]
    }


def test_generate_schedule_produces_lessons(tmp_path):
    config = Config(
        mode="balanced",
        planning_period_weeks=1,
        max_lessons_per_day=4,
        time_slots=["08:00-08:45", "08:55-09:40", "09:50-10:35"],
        allow_gaps=True,
    )
    generator = ScheduleGenerator()
    generator.config = config
    generator.set_data(sample_data())
    results = generator.generate_schedule()
    assert results.schedule, "Очікується сформований розклад"
    output_path = tmp_path / "out.json"
    generator.save_schedule(results, output_path)
    assert output_path.exists()
