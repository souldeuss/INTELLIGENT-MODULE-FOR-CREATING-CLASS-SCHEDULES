"""
Бенчмарк для порівняння швидкодії оригінальної та оптимізованої версій.

Запуск:
    python -m backend.app.core.benchmark

Результати покажуть прискорення у:
- Обчислення reward
- Генерація valid_actions  
- Час ітерації навчання
- Загальний час для 100 ітерацій
"""
import time
import numpy as np
import torch
from typing import List, Tuple
import sys
from pathlib import Path

# Додаємо шлях до проекту
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.app.models.database import Course, Teacher, StudentGroup, Classroom, Timeslot


def create_mock_data(
    n_courses: int = 20,
    n_teachers: int = 10,
    n_groups: int = 5,
    n_classrooms: int = 8,
    n_days: int = 5,
    n_periods: int = 6,
):
    """Створити mock дані для тестування."""
    
    # Courses
    courses = []
    for i in range(n_courses):
        c = Course()
        c.id = i + 1
        c.code = f"COURSE{i+1}"
        c.name = f"Course {i+1}"
        c.credits = 3
        c.requires_lab = (i % 4 == 0)
        c.preferred_classroom_type = "lab" if c.requires_lab else "lecture"
        courses.append(c)
    
    # Teachers
    teachers = []
    for i in range(n_teachers):
        t = Teacher()
        t.id = i + 1
        t.full_name = f"Teacher {i+1}"
        t.department = "CS"
        teachers.append(t)
    
    # Groups
    groups = []
    for i in range(n_groups):
        g = StudentGroup()
        g.id = i + 1
        g.code = f"GROUP{i+1}"
        g.name = f"Group {i+1}"
        g.students_count = 25 + (i * 5)
        groups.append(g)
    
    # Classrooms
    classrooms = []
    for i in range(n_classrooms):
        r = Classroom()
        r.id = i + 1
        r.code = f"ROOM{i+1}"
        r.capacity = 30 + (i * 10)
        r.classroom_type = "lab" if i < 2 else "lecture"
        classrooms.append(r)
    
    # Timeslots
    timeslots = []
    ts_id = 1
    for day in range(n_days):
        for period in range(n_periods):
            ts = Timeslot()
            ts.id = ts_id
            ts.day_of_week = day
            ts.period_number = period + 1
            ts.start_time = f"{8 + period}:00"
            ts.end_time = f"{9 + period}:00"
            timeslots.append(ts)
            ts_id += 1
    
    return courses, teachers, groups, classrooms, timeslots


def benchmark_environment():
    """Порівняння швидкодії Environment."""
    print("\n" + "=" * 60)
    print("🔬 BENCHMARK: Environment")
    print("=" * 60)
    
    # Дані
    courses, teachers, groups, classrooms, timeslots = create_mock_data(
        n_courses=20, n_teachers=10, n_groups=5, n_classrooms=8
    )
    
    print(f"📊 Розмір задачі: {len(courses)} курсів, {len(teachers)} викладачів, "
          f"{len(groups)} груп, {len(classrooms)} аудиторій, {len(timeslots)} слотів")
    
    # === Оригінальна версія ===
    try:
        from backend.app.core.environment import TimetablingEnvironment
        
        env_orig = TimetablingEnvironment(courses, teachers, groups, classrooms, timeslots)
        
        # Benchmark get_valid_actions (оригінальна)
        env_orig.reset()
        start = time.perf_counter()
        for _ in range(10):
            actions = env_orig.get_valid_actions()
        orig_valid_actions_time = (time.perf_counter() - start) / 10
        
        # Benchmark step (оригінальна)
        env_orig.reset()
        times = []
        for _ in range(20):
            actions = env_orig.get_valid_actions()
            if not actions:
                break
            start = time.perf_counter()
            env_orig.step(actions[0])
            times.append(time.perf_counter() - start)
        orig_step_time = np.mean(times) if times else 0
        
        print(f"\n📈 ОРИГІНАЛЬНА версія:")
        print(f"   get_valid_actions: {orig_valid_actions_time*1000:.2f} ms")
        print(f"   step (avg):        {orig_step_time*1000:.3f} ms")
        print(f"   Кількість actions: {len(actions)}")
        
    except Exception as e:
        print(f"⚠️ Помилка оригінальної версії: {e}")
        orig_valid_actions_time = None
        orig_step_time = None
    
    # === Оптимізована версія ===
    try:
        from backend.app.core.environment_optimized import OptimizedTimetablingEnvironment
        
        env_opt = OptimizedTimetablingEnvironment(courses, teachers, groups, classrooms, timeslots)
        
        # Benchmark get_valid_actions (оптимізована)
        env_opt.reset()
        start = time.perf_counter()
        for _ in range(10):
            actions = env_opt.get_valid_actions_vectorized()
        opt_valid_actions_time = (time.perf_counter() - start) / 10
        
        # Benchmark step (оптимізована)
        env_opt.reset()
        times = []
        valid_actions = env_opt.get_valid_actions()
        for i in range(min(20, len(valid_actions))):
            start = time.perf_counter()
            env_opt.step(valid_actions[i])
            times.append(time.perf_counter() - start)
            valid_actions = env_opt.get_valid_actions()
            if not valid_actions:
                break
        opt_step_time = np.mean(times) if times else 0
        
        print(f"\n🚀 ОПТИМІЗОВАНА версія:")
        print(f"   get_valid_actions: {opt_valid_actions_time*1000:.2f} ms")
        print(f"   step (avg):        {opt_step_time*1000:.3f} ms")
        print(f"   Кількість actions: {len(actions)}")
        
        # Порівняння
        if orig_valid_actions_time:
            speedup_va = orig_valid_actions_time / opt_valid_actions_time
            speedup_step = orig_step_time / opt_step_time if opt_step_time > 0 else 0
            print(f"\n⚡ ПРИСКОРЕННЯ:")
            print(f"   get_valid_actions: {speedup_va:.1f}x")
            print(f"   step:              {speedup_step:.1f}x")
        
    except Exception as e:
        print(f"⚠️ Помилка оптимізованої версії: {e}")
        import traceback
        traceback.print_exc()


def benchmark_neural_network():
    """Порівняння швидкодії нейронних мереж."""
    print("\n" + "=" * 60)
    print("🔬 BENCHMARK: Neural Networks")
    print("=" * 60)
    
    state_dim = 5000  # Типовий розмір стану
    action_dim = 2048  # Обмежений action space
    batch_size = 64
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🖥️ Device: {device}")
    
    # Тестові дані
    states = torch.randn(batch_size, state_dim).to(device)
    actions = torch.randint(0, action_dim, (batch_size,)).to(device)
    
    # === Оригінальна модель ===
    try:
        from backend.app.core.actor_critic import ActorCritic
        
        model_orig = ActorCritic(state_dim, action_dim).to(device)
        
        # Warmup
        for _ in range(5):
            with torch.no_grad():
                model_orig(states)
        
        # Benchmark forward
        start = time.perf_counter()
        for _ in range(100):
            with torch.no_grad():
                model_orig(states)
        orig_forward_time = (time.perf_counter() - start) / 100
        
        # Count parameters
        orig_params = sum(p.numel() for p in model_orig.parameters())
        
        print(f"\n📈 ОРИГІНАЛЬНА модель:")
        print(f"   Forward time: {orig_forward_time*1000:.2f} ms")
        print(f"   Parameters:   {orig_params:,}")
        
    except Exception as e:
        print(f"⚠️ Помилка оригінальної моделі: {e}")
        orig_forward_time = None
        orig_params = None
    
    # === Оптимізована модель ===
    try:
        from backend.app.core.actor_critic_optimized import OptimizedActorCritic
        
        model_opt = OptimizedActorCritic(state_dim, action_dim, use_attention=False).to(device)
        
        # Warmup
        for _ in range(5):
            with torch.no_grad():
                model_opt(states)
        
        # Benchmark forward
        start = time.perf_counter()
        for _ in range(100):
            with torch.no_grad():
                model_opt(states)
        opt_forward_time = (time.perf_counter() - start) / 100
        
        # Count parameters
        opt_params = sum(p.numel() for p in model_opt.parameters())
        
        print(f"\n🚀 ОПТИМІЗОВАНА модель:")
        print(f"   Forward time: {opt_forward_time*1000:.2f} ms")
        print(f"   Parameters:   {opt_params:,}")
        
        # Порівняння
        if orig_forward_time:
            speedup = orig_forward_time / opt_forward_time
            param_reduction = (1 - opt_params / orig_params) * 100 if orig_params else 0
            print(f"\n⚡ РЕЗУЛЬТАТИ:")
            print(f"   Прискорення forward: {speedup:.1f}x")
            print(f"   Зменшення параметрів: {param_reduction:.1f}%")
        
    except Exception as e:
        print(f"⚠️ Помилка оптимізованої моделі: {e}")
        import traceback
        traceback.print_exc()


def benchmark_training_iteration():
    """Порівняння швидкодії ітерації навчання."""
    print("\n" + "=" * 60)
    print("🔬 BENCHMARK: Training Iteration")
    print("=" * 60)
    
    courses, teachers, groups, classrooms, timeslots = create_mock_data()
    
    # Оптимізований trainer
    try:
        from backend.app.core.environment_optimized import OptimizedTimetablingEnvironment
        from backend.app.core.ppo_trainer_optimized import OptimizedPPOTrainer
        
        env = OptimizedTimetablingEnvironment(courses, teachers, groups, classrooms, timeslots)
        
        trainer = OptimizedPPOTrainer(
            env=env,
            state_dim=env.state_dim,
            action_dim=2048,
            num_envs=1,  # Single env для fair comparison
            n_steps=32,
            batch_size=32,
            epochs=2,
        )
        
        print(f"\n🚀 Оптимізований trainer (10 ітерацій)...")
        start = time.perf_counter()
        rewards, stats = trainer.train(num_iterations=10)
        total_time = time.perf_counter() - start
        
        print(f"   Загальний час:  {total_time:.2f} s")
        print(f"   Час на ітерацію: {total_time/10:.3f} s")
        print(f"   Best reward:     {stats['best_reward']:.2f}")
        print(f"   Hard violations: {stats['final_hard_violations']}")
        
    except Exception as e:
        print(f"⚠️ Помилка: {e}")
        import traceback
        traceback.print_exc()


def run_all_benchmarks():
    """Запустити всі бенчмарки."""
    print("\n" + "=" * 60)
    print("🎯 DRL TIMETABLING OPTIMIZATION BENCHMARK")
    print("=" * 60)
    
    benchmark_environment()
    benchmark_neural_network()
    benchmark_training_iteration()
    
    print("\n" + "=" * 60)
    print("✅ BENCHMARK COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_all_benchmarks()
