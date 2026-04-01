# Frontend Pages Documentation for Course Project Report

## Purpose of this document
This file describes each frontend page of the system, its functional role, user interactions, and the statistical indicators shown in the UI (if available).

## Application routes and pages

| Route | Page | Component |
|---|---|---|
| / | Dashboard | ModernDashboard |
| /timetable | Timetable | InteractiveTimetable |
| /conflicts | Conflict Center | ConflictCenter |
| /courses | Course Management | CourseManagement |
| /teachers | Teacher Management | TeacherManagement |
| /groups | Group Management | GroupManagement |
| /classrooms | Classroom Management | ClassroomManagement |
| /assignments | Course Assignments | CourseAssignments |
| /training-metrics | Model Training and Metrics | TrainingMetrics |
| /schedules | Saved Schedules | ScheduleManager |
| /analytics | Analytics | Analytics |
| /legacy-timetable | Legacy Timetable View | TimetableView |

Additional compatibility routes that open the same training page:
- /individual-generation -> TrainingMetrics
- /ai-generator -> TrainingMetrics

---

## 1) Dashboard (/)
### Functional purpose
- Central entry point with system status and quick navigation.
- Combines operational state, AI quality score, training trend, and conflict preview.
- Provides quick actions and data generation action.

### Main user actions
- Refresh dashboard data.
- Navigate to timetable and training pages.
- Open compact conflict preview.
- Trigger compact data generation action.

### Data sources
- statsService.getDashboardStats()
- aiService.getScheduleScore()
- aiService.getTrainingHistory()
- getSchedules()

### Displayed statistics and indicators
- Entity counters:
  - groups_count
  - teachers_count
  - classrooms_count
  - active_conflicts
- AI quality block:
  - overall (total score, %)
  - teacher_conflicts (%)
  - room_conflicts (%)
  - gap_penalty (%)
  - distribution (%)
- Training chart:
  - reward by episode (area chart)
- Recent schedules list:
  - score (%) per saved schedule
  - conflicts count badge per item

---

## 2) Timetable (/timetable)
### Functional purpose
- Main operational page for schedule generation, adaptation, and manual timetable editing.
- Supports filtering by group, teacher, or classroom.
- Supports day/week visual modes and drag-and-drop editing.

### Main user actions
- Select target view entity (group/teacher/classroom).
- Select model version for generation.
- Start/stop generation.
- Trigger automatic model adaptation if incompatible.
- Move classes (drag-and-drop), lock/unlock, delete class entries.
- Undo/redo changes.
- Refresh timetable.

### Data sources
- getGroups(), getTeachers(), getClassrooms()
- getGroupTimetable(), getTeacherTimetable(), getClassroomTimetable()
- generateSchedule(), stopGeneration(), getGenerationStatus()
- trainingService.getModelVersions()
- trainingService.startModelAdaptation(), getModelAdaptationStatus()
- aiService.getScheduleScore()
- historyService.undo(), historyService.redo(), historyService.canUndo(), historyService.canRedo()

### Displayed statistics and indicators
- Schedule size indicator: schedule.length (number of lessons in current view).
- Current schedule score chip:
  - scheduleScore.overall (%).
- Violation chips (if available in score details):
  - hard_violations
  - soft_violations
- Generation progress:
  - generationProgress (%) with progress bar.
- Adaptation progress:
  - adaptationProgress (%) with progress bar.
- Conflict marker at class level:
  - has_conflict + conflict_type tooltip.
- Zoom percentage indicator (visual scale only).

---

## 3) Conflict Center (/conflicts)
### Functional purpose
- Dedicated conflict management page.
- Shows hard and soft conflicts, details, affected entities, and AI suggestions.
- Supports semi-automatic conflict resolution.

### Main user actions
- Refresh conflict list.
- Expand/collapse conflict details.
- Apply AI suggestion.
- Delete conflicting class.
- Navigate to specific class in timetable.

### Data sources
- checkConflicts()
- aiService.getAvailableSlots()
- aiService.getAvailableRooms()
- aiService.applySuggestion()
- deleteScheduledClass()

### Displayed statistics and indicators
- Conflict summary cards:
  - hardConflicts.length
  - softConflicts.length
- Status banner:
  - no conflicts / hard conflict warning / soft conflict warning.
- Section counters:
  - number of hard conflicts
  - number of soft conflicts
- Per-conflict metadata:
  - type (hard/soft)
  - category (teacher/room/group/capacity/preference)
  - timeslot
  - affected_items (if present)

---

## 4) Course Management (/courses)
### Functional purpose
- CRUD page for courses.
- Supports bulk delete and CSV export.

### Main user actions
- Add/edit/delete course.
- Delete all courses.
- Export courses to CSV.

### Data sources
- getCourses(), createCourse(), updateCourse(), deleteCourse()
- exportCoursesCsv()

### Displayed statistics and indicators
- Header aggregate:
  - Total courses: courses.length
- Per-course fields shown in table:
  - credits
  - hours_per_week
  - difficulty (1..5, chip)

---

## 5) Teacher Management (/teachers)
### Functional purpose
- CRUD page for teachers.
- Supports bulk delete and CSV export.

### Main user actions
- Add/edit/delete teacher.
- Delete all teachers.
- Export teachers to CSV.

### Data sources
- getTeachers(), createTeacher(), updateTeacher(), deleteTeacher()
- exportTeachersCsv()

### Displayed statistics and indicators
- Header aggregate:
  - Total teachers: teachers.length
- Per-teacher fields shown in table:
  - max_hours_per_week
  - preference flags via chips:
    - avoid_early_slots
    - avoid_late_slots

---

## 6) Group Management (/groups)
### Functional purpose
- CRUD page for student groups.
- Supports bulk delete and CSV export.

### Main user actions
- Add/edit/delete group.
- Delete all groups.
- Export groups to CSV.

### Data sources
- getGroups(), createGroup(), updateGroup(), deleteGroup()
- exportGroupsCsv()

### Displayed statistics and indicators
- No standalone KPI cards.
- Per-group fields shown in table:
  - year (chip, for example "2 курс")
  - students_count
  - specialization

---

## 7) Classroom Management (/classrooms)
### Functional purpose
- CRUD page for classrooms/auditoria.
- Supports bulk delete and CSV export.

### Main user actions
- Add/edit/delete classroom.
- Delete all classrooms.
- Export classrooms to CSV.

### Data sources
- getClassrooms(), createClassroom(), updateClassroom(), deleteClassroom()
- exportClassroomsCsv()

### Displayed statistics and indicators
- Header aggregates:
  - Total classrooms: classrooms.length
  - Total capacity: sum of classroom.capacity
- Per-classroom fields shown in table:
  - capacity (chip)
  - classroom_type
  - equipment indicators:
    - has_projector
    - has_computers

---

## 8) Course Assignments (/assignments)
### Functional purpose
- Maps courses to teachers and groups.
- Supports manual assignment, AI auto-assignment, CSV import/export.

### Main user actions
- Add/delete assignment.
- Start AI auto-assignment with configurable parameters.
- Import assignment CSV.
- Export assignment CSV.

### Data sources
- getCourses(), getTeachers(), getGroups()
- api.get("/schedule/assignments")
- api.post("/schedule/assignments")
- api.delete("/schedule/assignments/{id}?... ")
- api.post("/schedule/assignments/auto", params)
- api.post("/schedule/assignments/import/csv")
- api.get("/schedule/assignments/export/csv")

### Displayed statistics and indicators
- KPI cards:
  - totalCourses
  - totalTeachers
  - totalGroups
  - totalAssignments
- Auto-assignment result indicators:
  - assignments_created
  - requested_min_weekly_lessons
  - groups_below_target
  - top underfilled groups (missing_hours)
- CSV import result indicators:
  - rows_total
  - rows_imported
  - teacher_links_created
  - group_links_created
  - duplicates_skipped
  - warnings and errors (previewed)

---

## 9) Model Training and Metrics (/training-metrics)
### Functional purpose
- Full DRL model training dashboard.
- Model version comparison and historical training analytics.
- Hyperparameter control for new run and live update.
- Preview of best generated schedule.

### Main user actions
- Select primary model and comparison model.
- Start/stop model training job.
- Configure training settings:
  - iterations, dataset mode, custom case count, iterations mode, seed, device.
- Configure PPO hyperparameters:
  - learning_rate, gamma, epsilon.
- Apply hyperparameter updates to active running job.
- Open charts in full-screen dialog.

### Data sources
- trainingService.getStatus()
- trainingService.getModelVersions()
- trainingService.getHistory()
- trainingService.getBestSchedulePreview()
- trainingService.getDatasetDimensions()
- trainingService.createModelTraining()
- trainingService.stopModelTraining()
- trainingService.getModelTrainingJobs()
- trainingService.getModelTrainingStatus()
- trainingService.updateHyperparameter()
- trainingService.getLegacyMetricsSnapshot() (fallback)

### Displayed statistics and indicators
- KPI block:
  - currentEpisode
  - totalEpisodes
  - meanReward
  - bestReward
  - hardConflicts
  - successfulGenerations
  - successRate (%)
  - softSatisfaction (%)
  - trainingDurationMinutes
- Environment dimensions:
  - state_dim/action_dim for current DB and selected dataset
  - raw_action_dim
- Session summary:
  - dataset version
  - model version
  - epochs completed/total
  - duration
  - best checkpoint
  - current status
- Training job runtime progress:
  - progress_percent
  - cases_done/cases_total
  - current_case
  - remaining_cases
- Model history table:
  - model version list with activity and update date
- Charts:
  - Policy Loss Curve
  - Training Loss
  - Mean Reward per Episode
  - Completion Rate over Time
  - Successful Generations Trend
- Hyperparameter display block:
  - learning rate
  - gamma
  - batch size (read-only from status)
  - epsilon
- Best schedule preview:
  - heatmap counts by day/period
  - mini-table of scheduled classes

---

## 10) Saved Schedules (/schedules)
### Functional purpose
- Manages saved schedule files and reusable schedule snapshots.
- Supports import/export, download, delete.

### Main user actions
- Refresh list.
- Save current schedule.
- Export lessons CSV template data.
- Import selected schedule file to active DB.
- Download saved schedule file.
- Delete schedule file.

### Data sources
- scheduleService.getScheduleFiles()
- scheduleService.exportSchedule()
- scheduleService.exportLessonsCsv()
- scheduleService.importSchedule()
- scheduleService.downloadScheduleFile()
- scheduleService.deleteScheduleFile()

### Displayed statistics and indicators
- Per-file indicators in table:
  - classes_count
  - file size (size_bytes / size_kb)
- Quality chips (if metadata exists):
  - overall_score (O)
  - best_reward (R)
  - hard_violations (H)
  - soft_violations (S)

---

## 11) Analytics (/analytics)
### Functional purpose
- Analytical page with aggregated charts and summary metrics.

### Main user actions
- Open analytics dashboard and inspect charts.

### Data sources
- getAnalytics()

### Displayed statistics and indicators
- Chart 1: Classroom Utilization
  - classroom_code vs utilization_rate
- Chart 2: Teacher Workload
  - teacher_name vs workload_rate
- Summary metrics:
  - total_classes
  - hard_constraint_violations
  - soft_constraint_violations
  - average_score

---

## 12) Legacy Timetable View (/legacy-timetable)
### Functional purpose
- Legacy calendar-based timetable view using FullCalendar.
- Kept for backward compatibility.

### Main user actions
- Select group.
- View weekly/daily calendar representation.

### Data sources
- getGroups()
- getGroupTimetable()

### Displayed statistics and indicators
- No dedicated KPI/statistics widgets.
- Only calendar events derived from timetable data.

---

## Notes for course project report
- The system combines operational pages (CRUD and timetable management) with analytical pages (Dashboard, Analytics, Training Metrics).
- The most data-rich pages for report visuals are:
  - Dashboard (/)
  - Timetable (/timetable)
  - Training Metrics (/training-metrics)
  - Analytics (/analytics)
  - Saved Schedules (/schedules)
- If needed, this README can be transformed into a chapter structure for the explanatory note (functional decomposition + UI metrics map).
