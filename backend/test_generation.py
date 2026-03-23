"""Тестовий скрипт для перевірки генерації розкладу."""
import sys
import os

# Додаємо шлях до модуля
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database_session import SessionLocal
from app.models.database import Course, Teacher, StudentGroup, Classroom, Timeslot
from app.core.environment import TimetablingEnvironment
from app.core.ppo_trainer import PPOTrainer
import logging

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_generation():
    """Тестуємо генерацію поза API."""
    logger.info("🧪 Початок тестування генерації")
    
    db = SessionLocal()
    
    try:
        # Завантаження даних
        courses = db.query(Course).all()
        teachers = db.query(Teacher).all()
        groups = db.query(StudentGroup).all()
        classrooms = db.query(Classroom).all()
        timeslots = db.query(Timeslot).filter(Timeslot.is_active == True).all()
        
        logger.info(f"📚 Завантажено: {len(courses)} курсів, {len(teachers)} викладачів, "
                   f"{len(groups)} груп, {len(classrooms)} аудиторій, {len(timeslots)} слотів")
        
        if not all([courses, teachers, groups, classrooms, timeslots]):
            logger.error("❌ Недостатньо даних для генерації!")
            return
        
        # Створення середовища
        logger.info("🔧 Створення DRL середовища...")
        env = TimetablingEnvironment(courses, teachers, groups, classrooms, timeslots)
        
        # Розрахунок розмірностей
        state_dim = env._get_state().shape[0]
        action_dim = env.n_courses * env.n_teachers * env.n_groups * env.n_classrooms * env.n_timeslots
        
        logger.info(f"🧠 Розмірності: state_dim={state_dim}, action_dim={action_dim}")
        
        # Навчання моделі (лише 10 ітерацій для тесту)
        logger.info("🎓 Початок тренування на 10 ітераціях (тест)...")
        trainer = PPOTrainer(env, state_dim, action_dim, device="cpu")
        episode_rewards, stats = trainer.train(num_iterations=10)
        
        logger.info(f"✅ Тестування завершено!")
        logger.info(f"📊 Best reward: {stats['best_reward']:.2f}")
        logger.info(f"📊 Hard violations: {stats['final_hard_violations']}")
        logger.info(f"📊 Soft violations: {stats['final_soft_violations']}")
        
    except Exception as e:
        logger.error(f"❌ Помилка: {str(e)}", exc_info=True)
    finally:
        db.close()
        logger.info("🔒 Закрито сесію БД")

if __name__ == "__main__":
    test_generation()
