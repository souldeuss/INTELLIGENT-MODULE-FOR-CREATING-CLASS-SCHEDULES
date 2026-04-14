import axios from "axios";

const backendHost = window.location.hostname || "localhost";
const API_BASE_URL =
  process.env.REACT_APP_API_URL || `http://${backendHost}:8000/api`;

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
export const exportCoursesCsv = () =>
  api.get("/courses/export/csv", { responseType: "blob" });

// ==================== TEACHERS ====================
export const getTeachers = () => api.get("/teachers");
export const createTeacher = (data: any) => api.post("/teachers", data);
export const updateTeacher = (id: number, data: any) =>
  api.put(`/teachers/${id}`, data);
export const deleteTeacher = (id: number) => api.delete(`/teachers/${id}`);
export const exportTeachersCsv = () =>
  api.get("/teachers/export/csv", { responseType: "blob" });

// ==================== GROUPS ====================
export const getGroups = () => api.get("/groups");
export const createGroup = (data: any) => api.post("/groups", data);
export const updateGroup = (id: number, data: any) =>
  api.put(`/groups/${id}`, data);
export const deleteGroup = (id: number) => api.delete(`/groups/${id}`);
export const exportGroupsCsv = () =>
  api.get("/groups/export/csv", { responseType: "blob" });

// ==================== CLASSROOMS ====================
export const getClassrooms = () => api.get("/classrooms");
export const createClassroom = (data: any) => api.post("/classrooms", data);
export const updateClassroom = (id: number, data: any) =>
  api.put(`/classrooms/${id}`, data);
export const deleteClassroom = (id: number) => api.delete(`/classrooms/${id}`);
export const exportClassroomsCsv = () =>
  api.get("/classrooms/export/csv", { responseType: "blob" });

// ==================== TIMESLOTS ====================
export const getTimeslots = () => api.get("/timeslots");
export const createTimeslot = (data: any) => api.post("/timeslots", data);

// ==================== SCHEDULE GENERATION ====================
export interface GenerationParams {
  iterations: number;
  preserve_locked?: boolean;
  use_existing?: boolean;
  model_version?: string;
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

export interface ModelCompatibilityResponse {
  model_version: string;
  compatible: boolean;
  reason: "ok" | "model_not_found" | "meta_not_found" | "dimension_mismatch" | string;
  detail: string;
  current: {
    state_dim: number;
    action_dim: number;
    raw_action_dim: number;
  };
  model: {
    model_found: boolean;
    meta_found: boolean;
    state_dim: number | null;
    action_dim: number | null;
  };
}

export const checkModelCompatibility = (modelVersion: string) =>
  api.get<ModelCompatibilityResponse>("/schedule/model-compatibility", {
    params: { model_version: modelVersion },
  });

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

  exportLessonsCsv: () =>
    api.get("/schedule/export/lessons/csv", { responseType: "blob" }),

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
export interface ScheduleScoreResponse {
  overall: number;
  teacher_conflicts: number;
  room_conflicts: number;
  group_conflicts: number;
  gap_penalty: number;
  distribution: number;
  occupancy_rate: number;
  details:
    | string
    | {
        total_classes: number;
        hard_violations: number;
        soft_violations: number;
      };
}

export const aiService = {
  // Отримати пояснення для конкретного рішення AI
  getDecisionExplanation: (classId: number) =>
    api.get(`/ai/explain/${classId}`),

  // Отримати загальний score розкладу
  getScheduleScore: () => api.get<ScheduleScoreResponse>("/ai/score"),

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
export interface TimetableCompletionStats {
  scheduled_count: number;
  total_required_periods: number;
  unscheduled_count: number;
  completion_rate: number;
}

export interface TimetableDayDistributionItem {
  day: string;
  day_index: number;
  periods_count: number;
}

export interface TimetableGroupUsageItem {
  group_id: number;
  group_code: string;
  assigned_periods: number;
  available_periods: number;
  usage_rate: number;
}

export interface TimetableTeacherUsageItem {
  teacher_id: number;
  teacher_name: string;
  assigned_periods: number;
  max_periods: number;
  usage_rate: number;
}

export interface TimetableInsightsResponse {
  generated_at: string;
  scheduled_lessons: number;
  completion: TimetableCompletionStats;
  lesson_distribution_by_day: TimetableDayDistributionItem[];
  class_period_usage: TimetableGroupUsageItem[];
  teacher_period_usage: TimetableTeacherUsageItem[];
}

export const statsService = {
  getDashboardStats: () => api.get("/stats/dashboard"),

  getConstraintViolations: () => api.get("/stats/violations"),

  getUtilizationStats: () => api.get("/stats/utilization"),

  getDistributionStats: () => api.get("/stats/distribution"),

  getTimetableInsights: () =>
    api.get<TimetableInsightsResponse>("/stats/timetable-insights"),
};

// ==================== TRAINING DASHBOARD ====================
export interface TrainingStatusResponse {
  active: boolean;
  session_id?: string;
  status?: string;
  timing?: {
    elapsed_seconds: number;
    elapsed_hms: string;
    estimated_remaining_seconds: number | null;
    estimated_remaining_hms: string | null;
    avg_time_per_iteration: number | null;
  };
  progress?: {
    current_iteration: number;
    total_iterations: number;
    percentage: number;
  };
  hyperparameters?: {
    learning_rate?: number;
    gamma?: number;
    epsilon?: number;
    batch_size?: number;
    gae_lambda?: number;
    entropy_coef?: number;
    value_coef?: number;
    lr_scheduler?: string;
  };
  session_summary?: {
    dataset_version: string;
    dataset_manifest: string | null;
    model_version: string;
    epochs_completed: number;
    epochs_total: number;
    runtime_hms: string;
    best_checkpoint: {
      checkpoint_id: string;
      iteration: number;
      best_reward: number;
      created_at: string;
    } | null;
  };
  metrics?: {
    current_reward: number;
    best_reward: number;
    hard_violations: number;
    soft_violations: number;
    successful_generations: number;
    success_rate: number;
    completion_rate: number;
    policy_loss: number;
    value_loss: number;
    total_loss: number;
    learning_rate: number;
  } | null;
}

export interface TrainingHistoryResponse {
  iteration: number[];
  model_version?: string;
  data_available?: boolean;
  source_file?: string | null;
  policy_loss?: Array<number | null>;
  value_loss?: Array<number | null>;
  total_loss?: Array<number | null>;
  episode_reward?: Array<number | null>;
  average_reward?: Array<number | null>;
  reward_per_step?: Array<number | null>;
  learning_rate?: Array<number | null>;
  hard_violations?: Array<number | null>;
  soft_violations?: Array<number | null>;
  success_count?: Array<number | null>;
  success_rate?: Array<number | null>;
  completion_rate?: Array<number | null>;
}

export interface BestSchedulePreviewResponse {
  available: boolean;
  data_available?: boolean;
  message?: string;
  source_file?: string;
  source_model_version?: string;
  updated_at?: string;
  meta?: {
    generation_id?: number;
    model_version?: string;
    best_reward?: number;
    hard_violations?: number;
    soft_violations?: number;
    classes_count?: number;
  };
  heatmap: Array<{
    day: number;
    day_label: string;
    period: number;
    count: number;
  }>;
  table: Array<{
    course: string;
    teacher: string;
    group: string;
    room: string;
    day: number;
    day_label: string;
    period: number;
    start_time: string | null;
    end_time: string | null;
  }>;
}

export interface Dataset100PresetStatusResponse {
  job_id: string;
  status: "running" | "completed" | "failed" | "stopped" | "unknown";
  pid?: number;
  return_code?: number | null;
  created_at?: string;
  stopped_at?: string;
  updated_at?: string;
  finished_at?: string;
  dataset_name?: string;
  manifest?: string;
  iterations?: number;
  seed?: number;
  command?: string[];
  log_path?: string;
  cases_total?: number | null;
  cases_done?: number;
  current_case?: number | null;
  remaining_cases?: number | null;
  progress_percent?: number | null;
  effective_iterations?: number | null;
  iterations_mode?: string | null;
  dataset_size_mode?: string | null;
  dataset_size?: number | null;
  run_id?: string | null;
  model_version?: string | null;
}

export interface DatasetDimensionsResponse {
  dataset_name: string;
  current_db: {
    state_dim: number;
    action_dim: number;
    raw_action_dim: number;
  };
  dataset: {
    found: boolean;
    manifest_path: string;
    sample_case: string | null;
    state_dim: number | null;
    action_dim: number | null;
    raw_action_dim: number | null;
    error?: string | null;
  };
}

export interface ModelTrainingCreateRequest {
  iterations?: number;
  seed?: number;
  train_ratio?: number;
  dataset_size_mode?: "compatible_100" | "compatible_1000" | "custom";
  custom_case_count?: number;
  dataset_name?: string;
  device?: string;
  promote?: boolean;
  regenerate_dataset?: boolean;
  iterations_mode?: "total" | "per-case";
  learning_rate?: number;
  gamma?: number;
  epsilon?: number;
}

export interface HyperparameterUpdateRequest {
  parameter: "learning_rate" | "gamma" | "epsilon" | "gae_lambda" | "entropy_coef" | "value_coef";
  value: number;
  reason?: string;
}

export interface ModelAdaptRequest {
  source_model_version: string;
  iterations?: number;
  count?: number;
  seed?: number;
  train_ratio?: number;
  dataset_name?: string;
  device?: string;
  promote?: boolean;
  iterations_mode?: "total" | "per-case";
}

export interface ModelVersionItem {
  name: string;
  is_active: boolean;
  size_bytes: number;
  updated_at: number;
  avg_reward?: number | null;
  final_loss?: number | null;
  training_duration?: number | null;
  success_rate?: number | null;
  hard_violations?: number;
  soft_violations?: number;
  training_sessions_count?: number;
}

export interface TrainingModelsResponse {
  model_dir: string;
  active_model: string;
  total: number;
  versions: ModelVersionItem[];
}

export interface TrainingCheckpointItem {
  checkpoint_id: string;
  created_at: string;
  iteration: number;
  best_reward: number;
  current_reward: number;
  hard_violations: number;
  learning_rate: number;
  description: string;
  tags: string[];
}

export interface TrainingCheckpointsResponse {
  total: number;
  checkpoints: TrainingCheckpointItem[];
}

export interface TrainingSessionItem {
  session_id: string;
  start_time: string;
  end_time?: string | null;
  status: string;
  total_iterations: number;
  best_reward: number;
  model_version?: string | null;
  dataset_version?: string | null;
  file: string;
}

export interface TrainingSessionsResponse {
  sessions: TrainingSessionItem[];
}

export interface Dataset100PresetJobsResponse {
  jobs: Dataset100PresetStatusResponse[];
}

export interface ModelAdaptJobsResponse {
  jobs: Dataset100PresetStatusResponse[];
}

export const trainingService = {
  /**
   * @deprecated Legacy dataset-100 preset endpoint. Use createModelTraining with
   * dataset_size_mode="compatible_100" or "compatible_1000".
   */
  startDataset100Preset: (payload?: {
    iterations?: number;
    seed?: number;
    train_ratio?: number;
    dataset_name?: string;
    device?: string;
    promote?: boolean;
    regenerate_dataset?: boolean;
  }) => api.post("/training/presets/dataset-100/start", payload || {}),

  /**
   * @deprecated Legacy dataset-100 preset endpoint.
   */
  getDataset100PresetJobs: () =>
    api.get<Dataset100PresetJobsResponse>("/training/presets/dataset-100/jobs"),

  /**
   * @deprecated Legacy dataset-100 preset endpoint.
   */
  getDataset100PresetStatus: (jobId: string) =>
    api.get<Dataset100PresetStatusResponse>(`/training/presets/dataset-100/status/${jobId}`),

  createModelTraining: (payload?: ModelTrainingCreateRequest) =>
    api.post<Dataset100PresetStatusResponse>("/training/models/create", payload || {}),

  updateHyperparameter: (payload: HyperparameterUpdateRequest) =>
    api.post<{ status: string; message: string; will_apply_on: string }>("/training/hyperparameters", payload),

  getModelTrainingJobs: () =>
    api.get<{ jobs: Dataset100PresetStatusResponse[] }>("/training/models/create/jobs"),

  getModelTrainingStatus: (jobId: string) =>
    api.get<Dataset100PresetStatusResponse>(`/training/models/create/status/${jobId}`),

  stopModelTraining: (jobId: string) =>
    api.post<Dataset100PresetStatusResponse>(`/training/models/create/stop/${jobId}`),

  startModelAdaptation: (payload: ModelAdaptRequest) =>
    api.post<Dataset100PresetStatusResponse>("/training/models/adapt", payload),

  getModelAdaptationJobs: () =>
    api.get<ModelAdaptJobsResponse>("/training/models/adapt/jobs"),

  getModelAdaptationStatus: (jobId: string) =>
    api.get<Dataset100PresetStatusResponse>(`/training/models/adapt/status/${jobId}`),

  stopModelAdaptation: (jobId: string) =>
    api.post<Dataset100PresetStatusResponse>(`/training/models/adapt/stop/${jobId}`),

  getDatasetDimensions: (datasetName: string) =>
    api.get<DatasetDimensionsResponse>("/training/dataset-dimensions", {
      params: { dataset_name: datasetName },
    }),

  getStatus: () => api.get<TrainingStatusResponse>("/training/status"),

  getHistory: (lastN: number = 200, modelVersion?: string) =>
    api.get<TrainingHistoryResponse>("/training/metrics/history", {
      params: {
        metrics:
          "policy_loss,value_loss,total_loss,episode_reward,average_reward,reward_per_step,learning_rate,hard_violations,soft_violations,success_count,success_rate,completion_rate",
        last_n: lastN,
        model_version: modelVersion || undefined,
      },
    }),

  getBestSchedulePreview: (maxRows: number = 20, modelVersion?: string) =>
    api.get<BestSchedulePreviewResponse>("/training/best-schedule-preview", {
      params: {
        max_rows: maxRows,
        model_version: modelVersion || undefined,
      },
    }),

  getModelVersions: () => api.get<TrainingModelsResponse>("/training/models"),

  getModelMetrics: (modelName: string) =>
    api.get<TrainingHistoryResponse>(`/training/models/${modelName}/metrics`),

  getCheckpoints: () => api.get<TrainingCheckpointsResponse>("/training/checkpoints"),

  getTrainingSessions: () => api.get<TrainingSessionsResponse>("/training/sessions"),

  getLegacyMetricsSnapshot: () => api.get("/schedule/training-metrics"),
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
