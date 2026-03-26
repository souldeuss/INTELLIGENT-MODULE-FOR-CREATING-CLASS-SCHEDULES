import axios from "axios";

const API_BASE_URL =
  process.env.REACT_APP_API_URL || "http://localhost:8000/api";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// ==================== COURSES ====================
export const getCourses = () => api.get("/courses");
export const createCourse = (data: any) => api.post("/courses", data);
export const updateCourse = (id: number, data: any) =>
  api.put(`/courses/${id}`, data);
export const deleteCourse = (id: number) => api.delete(`/courses/${id}`);

// ==================== TEACHERS ====================
export const getTeachers = () => api.get("/teachers");
export const createTeacher = (data: any) => api.post("/teachers", data);
export const updateTeacher = (id: number, data: any) =>
  api.put(`/teachers/${id}`, data);
export const deleteTeacher = (id: number) => api.delete(`/teachers/${id}`);

// ==================== GROUPS ====================
export const getGroups = () => api.get("/groups");
export const createGroup = (data: any) => api.post("/groups", data);
export const updateGroup = (id: number, data: any) =>
  api.put(`/groups/${id}`, data);
export const deleteGroup = (id: number) => api.delete(`/groups/${id}`);

// ==================== CLASSROOMS ====================
export const getClassrooms = () => api.get("/classrooms");
export const createClassroom = (data: any) => api.post("/classrooms", data);
export const updateClassroom = (id: number, data: any) =>
  api.put(`/classrooms/${id}`, data);
export const deleteClassroom = (id: number) => api.delete(`/classrooms/${id}`);

// ==================== TIMESLOTS ====================
export const getTimeslots = () => api.get("/timeslots");
export const createTimeslot = (data: any) => api.post("/timeslots", data);

// ==================== SCHEDULE GENERATION ====================
export interface GenerationParams {
  iterations: number;
  preserve_locked?: boolean;
  use_existing?: boolean;
  // PPO Hyperparameters
  learning_rate?: number;
  gamma?: number;
  epsilon?: number;
  batch_size?: number;
  // Constraint priorities
  constraint_weights?: {
    teacher_conflict: number;
    room_conflict: number;
    group_conflict: number;
    capacity: number;
    preferences: number;
  };
}

export const generateSchedule = (data: GenerationParams) =>
  api.post("/schedule/generate", data);

export const getGenerationStatus = (id: number) =>
  api.get(`/schedule/status/${id}`);

export const stopGeneration = (id: number) => api.post(`/schedule/stop/${id}`);

export const getGroupTimetable = (groupId: number) =>
  api.get(`/schedule/timetable/${groupId}`);

export const getTeacherTimetable = (teacherId: number) =>
  api.get(`/schedule/timetable/teacher/${teacherId}`);

export const getClassroomTimetable = (classroomId: number) =>
  api.get(`/schedule/timetable/classroom/${classroomId}`);

export const getAnalytics = () => api.get("/schedule/analytics");
export const clearSchedule = () => api.delete("/schedule/clear");

// ==================== SCHEDULE EDITING ====================
export interface ScheduleUpdate {
  class_id: number;
  timeslot_id?: number;
  classroom_id?: number;
  teacher_id?: number;
}

export const updateScheduledClass = (id: number, data: ScheduleUpdate) =>
  api.put(`/schedule/class/${id}`, data);

export const lockScheduledClass = (id: number, locked: boolean) =>
  api.patch(`/schedule/class/${id}/lock`, { locked });

export const deleteScheduledClass = (id: number) =>
  api.delete(`/schedule/class/${id}`);

export const addScheduledClass = (data: {
  course_id: number;
  teacher_id: number;
  group_id: number;
  classroom_id: number;
  timeslot_id: number;
}) => api.post("/schedule/class", data);

// ==================== CONFLICT DETECTION ====================
export const checkConflicts = () => api.get("/schedule/conflicts");

export const checkMoveConflicts = (data: {
  class_id: number;
  target_timeslot_id: number;
  target_classroom_id?: number;
}) => api.post("/schedule/conflicts/check-move", data);

export const getSuggestions = (classId: number) =>
  api.get(`/schedule/suggestions/${classId}`);

// ==================== SCHEDULE FILES ====================
export const scheduleService = {
  getScheduleFiles: () => api.get("/schedule/files"),

  exportSchedule: (description?: string, format?: "json" | "csv" | "xlsx") =>
    api.post("/schedule/export", { description, format }),

  importSchedule: (filename: string, clearExisting: boolean = true) =>
    api.post(`/schedule/import/${filename}`, null, {
      params: { clear_existing: clearExisting },
    }),

  deleteScheduleFile: (filename: string) =>
    api.delete(`/schedule/files/${filename}`),

  downloadScheduleFile: (filename: string) =>
    api.get(`/schedule/files/${filename}/download`, { responseType: "blob" }),

  // Версіонування
  createVersion: (name: string, description?: string) =>
    api.post("/schedule/version", { name, description }),

  getVersions: () => api.get("/schedule/versions"),

  restoreVersion: (versionId: number) =>
    api.post(`/schedule/version/${versionId}/restore`),

  compareVersions: (v1: number, v2: number) =>
    api.get(`/schedule/versions/compare?v1=${v1}&v2=${v2}`),
};

// ==================== AI EXPLAINABILITY ====================
export const aiService = {
  // Отримати пояснення для конкретного рішення AI
  getDecisionExplanation: (classId: number) =>
    api.get(`/ai/explain/${classId}`),

  // Отримати загальний score розкладу
  getScheduleScore: () => api.get("/ai/score"),

  // Отримати історію reward під час навчання
  getTrainingHistory: (generationId?: number) =>
    generationId
      ? api.get(`/ai/training-history/${generationId}`)
      : api.get("/ai/training-history"),

  // Отримати AI рекомендації для покращення
  getImprovementSuggestions: () => api.get("/ai/suggestions"),

  // Параметри моделі
  getModelInfo: () => api.get("/ai/model-info"),

  // Застосувати AI рекомендацію
  applySuggestion: (
    classId: number,
    suggestionType: "move_timeslot" | "change_room" | "change_teacher",
    targetId: number
  ) =>
    api.post("/ai/apply-suggestion", null, {
      params: {
        class_id: classId,
        suggestion_type: suggestionType,
        target_id: targetId,
      },
    }),

  // Отримати доступні таймслоти для переміщення
  getAvailableSlots: (classId: number) =>
    api.get(`/ai/available-slots/${classId}`),

  // Отримати доступні аудиторії
  getAvailableRooms: (classId: number) =>
    api.get(`/ai/available-rooms/${classId}`),
};

// ==================== HISTORY & UNDO ====================
export const historyService = {
  getHistory: (limit?: number) =>
    api.get("/schedule/history", { params: { limit } }),

  undo: () => api.post("/schedule/undo"),

  redo: () => api.post("/schedule/redo"),

  canUndo: () => api.get("/schedule/can-undo"),

  canRedo: () => api.get("/schedule/can-redo"),
};

// ==================== STATISTICS ====================
export const statsService = {
  getDashboardStats: () => api.get("/stats/dashboard"),

  getConstraintViolations: () => api.get("/stats/violations"),

  getUtilizationStats: () => api.get("/stats/utilization"),

  getDistributionStats: () => api.get("/stats/distribution"),
};

// ==================== SCHEDULES LIST ====================
export const getSchedules = () => api.get("/schedule/files");

// ==================== DATA GENERATION ====================
export const seedService = {
  generateRandomData: (params?: {
    num_teachers?: number;
    num_groups?: number;
    num_courses?: number;
    num_classrooms?: number;
  }) => api.post("/seed/generate", null, { params }),

  clearAllData: () => api.delete("/seed/clear"),
};

export default api;
