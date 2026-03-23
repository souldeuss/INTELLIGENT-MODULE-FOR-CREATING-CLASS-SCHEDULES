"""Script to populate database with comprehensive sample data for timetabling system."""
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

def clear_database():
    """Clear all existing data."""
    print("\n🗑️  Clearing existing data...")
    try:
        response = requests.delete(f"{BASE_URL}/schedule/clear")
        if response.status_code == 200:
            print("✅ Database cleared successfully")
        else:
            print(f"⚠️  Warning: Could not clear database - {response.text}")
    except Exception as e:
        print(f"⚠️  Warning: Could not clear database - {e}")

def create_timeslots():
    """Create timeslots for the week."""
    print("\n⏰ Creating timeslots...")
    
    # Days of week: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    # Time periods (8:00 - 18:00, 6 periods per day)
    periods = [
        {"period": 1, "start": "08:00:00", "end": "09:30:00"},
        {"period": 2, "start": "09:45:00", "end": "11:15:00"},
        {"period": 3, "start": "11:30:00", "end": "13:00:00"},
        {"period": 4, "start": "13:30:00", "end": "15:00:00"},
        {"period": 5, "start": "15:15:00", "end": "16:45:00"},
        {"period": 6, "start": "17:00:00", "end": "18:30:00"},
    ]
    
    for day_idx, day_name in enumerate(days):
        for period in periods:
            timeslot = {
                "day_of_week": day_idx,
                "period_number": period["period"],
                "start_time": period["start"],
                "end_time": period["end"],
                "is_active": True
            }
            
            try:
                response = requests.post(f"{BASE_URL}/timeslots", json=timeslot)
                if response.status_code in [200, 201]:
                    print(f"✅ Created timeslot: {day_name} Period {period['period']} ({period['start']}-{period['end']})")
                else:
                    print(f"❌ Failed to create timeslot for {day_name} Period {period['period']} (status {response.status_code}): {response.text}")
            except Exception as e:
                print(f"❌ Error creating timeslot: {e}")

def create_classrooms():
    """Create sample classrooms."""
    print("\n🏫 Creating classrooms...")
    
    classrooms = [
        # Lecture halls
        {"code": "101", "building": "A", "floor": 1, "capacity": 100, "classroom_type": "lecture", 
         "has_projector": True, "has_computers": False},
        {"code": "102", "building": "A", "floor": 1, "capacity": 80, "classroom_type": "lecture",
         "has_projector": True, "has_computers": False},
        {"code": "201", "building": "A", "floor": 2, "capacity": 120, "classroom_type": "lecture",
         "has_projector": True, "has_computers": False},
        {"code": "202", "building": "A", "floor": 2, "capacity": 90, "classroom_type": "lecture",
         "has_projector": True, "has_computers": False},
        
        # Computer labs
        {"code": "301", "building": "B", "floor": 3, "capacity": 30, "classroom_type": "computer_lab",
         "has_projector": True, "has_computers": True},
        {"code": "302", "building": "B", "floor": 3, "capacity": 25, "classroom_type": "computer_lab",
         "has_projector": True, "has_computers": True},
        {"code": "303", "building": "B", "floor": 3, "capacity": 28, "classroom_type": "computer_lab",
         "has_projector": True, "has_computers": True},
        
        # Labs
        {"code": "L101", "building": "C", "floor": 1, "capacity": 20, "classroom_type": "lab",
         "has_projector": False, "has_computers": False},
        {"code": "L102", "building": "C", "floor": 1, "capacity": 22, "classroom_type": "lab",
         "has_projector": False, "has_computers": False},
        {"code": "L201", "building": "C", "floor": 2, "capacity": 18, "classroom_type": "lab",
         "has_projector": True, "has_computers": False},
        
        # Seminar rooms
        {"code": "S101", "building": "A", "floor": 1, "capacity": 25, "classroom_type": "seminar",
         "has_projector": True, "has_computers": False},
        {"code": "S102", "building": "A", "floor": 1, "capacity": 20, "classroom_type": "seminar",
         "has_projector": True, "has_computers": False},
    ]
    
    for classroom in classrooms:
        try:
            response = requests.post(f"{BASE_URL}/classrooms", json=classroom)
            if response.status_code == 200:
                print(f"✅ Created classroom: {classroom['code']} ({classroom['classroom_type']}, capacity: {classroom['capacity']})")
            else:
                print(f"❌ Failed to create classroom {classroom['code']}: {response.text}")
        except Exception as e:
            print(f"❌ Error creating classroom: {e}")

def create_teachers():
    """Create sample teachers."""
    print("\n👨‍🏫 Creating teachers...")
    
    teachers = [
        {"code": "T001", "full_name": "Іванова Олена Петрівна", "email": "ivanova@univ.edu",
         "department": "Філологія", "max_hours_per_week": 20, "avoid_early_slots": False, "avoid_late_slots": False},
        {"code": "T002", "full_name": "Петренко Максим Володимирович", "email": "petrenko@univ.edu",
         "department": "Математика", "max_hours_per_week": 18, "avoid_early_slots": False, "avoid_late_slots": True},
        {"code": "T003", "full_name": "Сидоренко Андрій Іванович", "email": "sydorenko@univ.edu",
         "department": "Інформатика", "max_hours_per_week": 20, "avoid_early_slots": True, "avoid_late_slots": False},
        {"code": "T004", "full_name": "Коваленко Марія Сергіївна", "email": "kovalenko@univ.edu",
         "department": "Фізика", "max_hours_per_week": 16, "avoid_early_slots": False, "avoid_late_slots": False},
        {"code": "T005", "full_name": "Бондаренко Тарас Миколайович", "email": "bondarenko@univ.edu",
         "department": "Іноземні мови", "max_hours_per_week": 22, "avoid_early_slots": False, "avoid_late_slots": False},
        {"code": "T006", "full_name": "Шевченко Ірина Олександрівна", "email": "shevchenko@univ.edu",
         "department": "Інформатика", "max_hours_per_week": 18, "avoid_early_slots": False, "avoid_late_slots": True},
        {"code": "T007", "full_name": "Мельник Олег Ярославович", "email": "melnyk@univ.edu",
         "department": "Математика", "max_hours_per_week": 20, "avoid_early_slots": False, "avoid_late_slots": False},
        {"code": "T008", "full_name": "Ткаченко Наталія Василівна", "email": "tkachenko@univ.edu",
         "department": "Фізика", "max_hours_per_week": 16, "avoid_early_slots": True, "avoid_late_slots": False},
    ]
    
    for teacher in teachers:
        try:
            response = requests.post(f"{BASE_URL}/teachers", json=teacher)
            if response.status_code == 200:
                print(f"✅ Created teacher: {teacher['code']} - {teacher['full_name']}")
            else:
                print(f"❌ Failed to create teacher {teacher['code']}: {response.text}")
        except Exception as e:
            print(f"❌ Error creating teacher: {e}")

def create_groups():
    """Create student groups."""
    print("\n👥 Creating student groups...")
    
    groups = [
        {"code": "КН-21", "year": 2, "students_count": 28, "specialization": "Комп'ютерні науки"},
        {"code": "КН-22", "year": 2, "students_count": 25, "specialization": "Комп'ютерні науки"},
        {"code": "ПМ-21", "year": 2, "students_count": 30, "specialization": "Прикладна математика"},
        {"code": "ПМ-22", "year": 2, "students_count": 27, "specialization": "Прикладна математика"},
        {"code": "ФЗ-21", "year": 2, "students_count": 22, "specialization": "Фізика"},
        {"code": "ФІЛ-21", "year": 2, "students_count": 20, "specialization": "Філологія"},
    ]
    
    for group in groups:
        try:
            response = requests.post(f"{BASE_URL}/groups", json=group)
            if response.status_code == 200:
                print(f"✅ Created group: {group['code']} ({group['students_count']} students, {group['specialization']})")
            else:
                print(f"❌ Failed to create group {group['code']}: {response.text}")
        except Exception as e:
            print(f"❌ Error creating group: {e}")

def create_courses():
    """Create sample courses."""
    print("\n📚 Creating courses...")
    
    courses = [
        # Computer Science courses
        {"code": "КН-101", "name": "Програмування Python", "credits": 4, "hours_per_week": 4,
         "requires_lab": True, "preferred_classroom_type": "computer_lab", "difficulty": 3},
        {"code": "КН-102", "name": "Структури даних та алгоритми", "credits": 4, "hours_per_week": 4,
         "requires_lab": True, "preferred_classroom_type": "computer_lab", "difficulty": 4},
        {"code": "КН-103", "name": "Бази даних", "credits": 3, "hours_per_week": 3,
         "requires_lab": True, "preferred_classroom_type": "computer_lab", "difficulty": 3},
        {"code": "КН-104", "name": "Веб-технології", "credits": 3, "hours_per_week": 3,
         "requires_lab": True, "preferred_classroom_type": "computer_lab", "difficulty": 3},
        
        # Mathematics courses
        {"code": "МАТ-201", "name": "Математичний аналіз", "credits": 5, "hours_per_week": 4,
         "requires_lab": False, "preferred_classroom_type": "lecture", "difficulty": 4},
        {"code": "МАТ-202", "name": "Лінійна алгебра", "credits": 4, "hours_per_week": 4,
         "requires_lab": False, "preferred_classroom_type": "lecture", "difficulty": 4},
        {"code": "МАТ-203", "name": "Дискретна математика", "credits": 3, "hours_per_week": 3,
         "requires_lab": False, "preferred_classroom_type": "lecture", "difficulty": 3},
        {"code": "МАТ-204", "name": "Теорія ймовірностей", "credits": 3, "hours_per_week": 3,
         "requires_lab": False, "preferred_classroom_type": "lecture", "difficulty": 3},
        
        # Physics courses
        {"code": "ФІЗ-301", "name": "Загальна фізика", "credits": 4, "hours_per_week": 4,
         "requires_lab": True, "preferred_classroom_type": "lab", "difficulty": 3},
        {"code": "ФІЗ-302", "name": "Квантова механіка", "credits": 4, "hours_per_week": 3,
         "requires_lab": True, "preferred_classroom_type": "lab", "difficulty": 5},
        {"code": "ФІЗ-303", "name": "Термодинаміка", "credits": 3, "hours_per_week": 3,
         "requires_lab": True, "preferred_classroom_type": "lab", "difficulty": 4},
        
        # Language courses
        {"code": "УКР-401", "name": "Українська мова", "credits": 2, "hours_per_week": 2,
         "requires_lab": False, "preferred_classroom_type": "seminar", "difficulty": 2},
        {"code": "АНГ-402", "name": "Англійська мова (технічна)", "credits": 2, "hours_per_week": 2,
         "requires_lab": False, "preferred_classroom_type": "seminar", "difficulty": 2},
        {"code": "АНГ-403", "name": "Англійська мова (розмовна)", "credits": 2, "hours_per_week": 2,
         "requires_lab": False, "preferred_classroom_type": "seminar", "difficulty": 2},
    ]
    
    for course in courses:
        try:
            response = requests.post(f"{BASE_URL}/courses", json=course)
            if response.status_code == 200:
                print(f"✅ Created course: {course['code']} - {course['name']} ({course['hours_per_week']}h/week)")
            else:
                print(f"❌ Failed to create course {course['code']}: {response.text}")
        except Exception as e:
            print(f"❌ Error creating course: {e}")

def main():
    """Main function to populate database."""
    print("=" * 80)
    print("🎓 INTELLIGENT TIMETABLING SYSTEM - DATABASE POPULATION")
    print("=" * 80)
    print(f"\n📍 Target API: {BASE_URL}")
    print("\nThis script will populate the database with sample data:")
    print("  • Timeslots (5 days × 6 periods = 30 slots)")
    print("  • Classrooms (12 rooms: lectures, labs, computer labs)")
    print("  • Teachers (8 instructors)")
    print("  • Student Groups (6 groups)")
    print("  • Courses (14 courses)")
    print("\n" + "=" * 80)
    
    input("\n⏸️  Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        # Step 1: Clear existing data
        clear_database()
        
        # Step 2: Create foundational data (required for scheduling)
        create_timeslots()
        create_classrooms()
        create_teachers()
        create_groups()
        create_courses()
        
        # Summary
        print("\n" + "=" * 80)
        print("✅ DATABASE POPULATION COMPLETED!")
        print("=" * 80)
        print("\n📊 Summary:")
        print("  ✓ Timeslots: 30 (5 days × 6 periods)")
        print("  ✓ Classrooms: 12")
        print("  ✓ Teachers: 8")
        print("  ✓ Groups: 6")
        print("  ✓ Courses: 14")
        print("\n🚀 You can now generate schedules through:")
        print("  • Web UI: http://localhost:3000")
        print("  • API: http://localhost:8000/docs")
        print("  • Desktop GUI: python gui_app.py")
        print("\n💡 Tip: Try generating a schedule with 1000 iterations!")
        print("=" * 80 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user.")
    except Exception as e:
        print(f"\n\n❌ Error during population: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
