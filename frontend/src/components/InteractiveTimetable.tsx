import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  Box,
  Paper,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  ToggleButtonGroup,
  ToggleButton,
  IconButton,
  Tooltip,
  Chip,
  Stack,
  Button,
  Menu,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Snackbar,
  Card,
  CardContent,
  Divider,
  Badge,
  LinearProgress,
} from "@mui/material";
import {
  ViewWeek as WeekIcon,
  Today as DayIcon,
  CalendarMonth as MonthIcon,
  Undo as UndoIcon,
  Redo as RedoIcon,
  Lock as LockIcon,
  LockOpen as UnlockIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  FilterList as FilterIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  ZoomIn as ZoomInIcon,
  ZoomOut as ZoomOutIcon,
  Group as GroupIcon,
  Person as PersonIcon,
  Room as RoomIcon,
  MoreVert as MoreIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
} from "@mui/icons-material";
import {
  getGroups,
  getTeachers,
  getClassrooms,
  getGroupTimetable,
  getTeacherTimetable,
  getClassroomTimetable,
  generateSchedule,
  checkModelCompatibility,
  getGenerationStatus,
  stopGeneration,
  lockScheduledClass,
  deleteScheduledClass,
  updateScheduledClass,
  historyService,
  ModelVersionItem,
  trainingService,
  aiService,
  ScheduleScoreResponse,
} from "../services/api";

interface ScheduledClass {
  id: number;
  course_id: number;
  course_name: string;
  course_code: string;
  teacher_id: number;
  teacher_name: string;
  group_id: number;
  group_code: string;
  classroom_id: number;
  classroom_code: string;
  timeslot_id: number;
  day_of_week: number;
  period_number: number;
  start_time: string;
  end_time: string;
  is_locked: boolean;
  has_conflict?: boolean;
  conflict_type?: string;
}

interface ViewFilter {
  type: "group" | "teacher" | "classroom";
  id: number;
  name: string;
}

const DAYS = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця"];
const PERIODS = [
  { number: 1, time: "08:30 - 10:00" },
  { number: 2, time: "10:15 - 11:45" },
  { number: 3, time: "12:00 - 13:30" },
  { number: 4, time: "14:00 - 15:30" },
  { number: 5, time: "15:45 - 17:15" },
  { number: 6, time: "17:30 - 19:00" },
];

const InteractiveTimetable: React.FC = () => {
  // Data state
  const [groups, setGroups] = useState<any[]>([]);
  const [teachers, setTeachers] = useState<any[]>([]);
  const [classrooms, setClassrooms] = useState<any[]>([]);
  const [schedule, setSchedule] = useState<ScheduledClass[]>([]);

  // View state
  const [viewMode, setViewMode] = useState<"week" | "day">("week");
  const [filter, setFilter] = useState<ViewFilter>({
    type: "group",
    id: 0,
    name: "",
  });
  const [selectedDay, setSelectedDay] = useState(0);
  const [zoom, setZoom] = useState(1);

  // Edit state
  const [selectedClass, setSelectedClass] = useState<ScheduledClass | null>(
    null
  );
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    classItem: ScheduledClass;
  } | null>(null);
  const [editDialog, setEditDialog] = useState(false);
  const [draggedClass, setDraggedClass] = useState<ScheduledClass | null>(null);
  const [dropTarget, setDropTarget] = useState<{
    day: number;
    period: number;
  } | null>(null);

  // History state
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const generationPollRef = useRef<number | null>(null);
  const adaptationPollRef = useRef<number | null>(null);
  const [availableModels, setAvailableModels] = useState<ModelVersionItem[]>([]);
  const [selectedModelVersion, setSelectedModelVersion] = useState<string>("");
  const [generationId, setGenerationId] = useState<number | null>(null);
  const [generationStatus, setGenerationStatus] = useState<
    "idle" | "running" | "completed" | "failed" | "stopped"
  >("idle");
  const [generationProgress, setGenerationProgress] = useState(0);
  const [adaptationJobId, setAdaptationJobId] = useState<string | null>(null);
  const [adaptationStatus, setAdaptationStatus] = useState<
    "idle" | "running" | "completed" | "failed" | "stopped"
  >("idle");
  const [adaptationProgress, setAdaptationProgress] = useState(0);
  const [scheduleScore, setScheduleScore] = useState<ScheduleScoreResponse | null>(null);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [scoreError, setScoreError] = useState<string | null>(null);

  // Notifications
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "info";
  }>({
    open: false,
    message: "",
    severity: "info",
  });

  // Load initial data
  useEffect(() => {
    loadData();
    loadModels();
  }, []);

  useEffect(() => {
    if (filter.id) {
      loadSchedule();
    }
  }, [filter]);

  const loadData = async () => {
    try {
      const [groupsRes, teachersRes, classroomsRes] = await Promise.all([
        getGroups(),
        getTeachers(),
        getClassrooms(),
      ]);

      setGroups(groupsRes.data);
      setTeachers(teachersRes.data);
      setClassrooms(classroomsRes.data);

      // Set default filter
      if (groupsRes.data.length > 0) {
        setFilter({
          type: "group",
          id: groupsRes.data[0].id,
          name: groupsRes.data[0].code,
        });
      }
    } catch (error) {
      console.error("Failed to load data:", error);
    }
  };

  const loadModels = async () => {
    try {
      const response = await trainingService.getModelVersions();
      const models = response.data?.versions || [];
      const active = response.data?.active_model || "";
      setAvailableModels(models);
      setSelectedModelVersion((prev) => {
        if (prev && models.some((m) => m.name === prev)) {
          return prev;
        }
        if (active && models.some((m) => m.name === active)) {
          return active;
        }
        return models[0]?.name || "";
      });
    } catch (error) {
      console.error("Failed to load model versions:", error);
    }
  };

  const loadScheduleScore = useCallback(async () => {
    setScoreLoading(true);
    try {
      const response = await aiService.getScheduleScore();
      setScheduleScore(response.data);
      setScoreError(null);
    } catch (error) {
      console.error("Failed to load schedule score:", error);
      setScoreError("Не вдалося оновити оцінку розкладу");
    } finally {
      setScoreLoading(false);
    }
  }, []);

  const loadSchedule = async () => {
    try {
      let response;
      switch (filter.type) {
        case "group":
          response = await getGroupTimetable(filter.id);
          break;
        case "teacher":
          response = await getTeacherTimetable(filter.id);
          break;
        case "classroom":
          response = await getClassroomTimetable(filter.id);
          break;
      }
      setSchedule(response?.data || []);
      await loadScheduleScore();
    } catch (error) {
      console.error("Failed to load schedule:", error);
      setSchedule([]);
      await loadScheduleScore();
    }
  };

  const checkHistoryState = async () => {
    try {
      const [undoRes, redoRes] = await Promise.all([
        historyService.canUndo(),
        historyService.canRedo(),
      ]);
      setCanUndo(undoRes.data.can_undo);
      setCanRedo(redoRes.data.can_redo);
    } catch (error) {
      // Ignore if history API not available
    }
  };

  const stopGenerationPolling = useCallback(() => {
    if (generationPollRef.current !== null) {
      window.clearInterval(generationPollRef.current);
      generationPollRef.current = null;
    }
  }, []);

  const stopAdaptationPolling = useCallback(() => {
    if (adaptationPollRef.current !== null) {
      window.clearInterval(adaptationPollRef.current);
      adaptationPollRef.current = null;
    }
  }, []);

  const syncAdaptation = useCallback(
    async (jobId: string) => {
      try {
        const response = await trainingService.getModelAdaptationStatus(jobId);
        const data: any = response.data;

        if (typeof data.progress_percent === "number") {
          setAdaptationProgress(Math.max(0, Math.min(100, data.progress_percent)));
        }

        if (data.status === "completed") {
          setAdaptationStatus("completed");
          setAdaptationJobId(null);
          stopAdaptationPolling();

          const adaptedModelVersion =
            typeof data.model_version === "string" ? data.model_version : "";
          await loadModels();

          if (adaptedModelVersion) {
            setSelectedModelVersion(adaptedModelVersion);
            showNotification(
              `Адаптацію завершено. Обрано модель ${adaptedModelVersion}`,
              "success"
            );
          } else {
            showNotification("Адаптацію моделі завершено", "success");
          }
          return;
        }

        if (data.status === "failed") {
          setAdaptationStatus("failed");
          setAdaptationJobId(null);
          stopAdaptationPolling();
          showNotification("Адаптація моделі завершилась з помилкою", "error");
          return;
        }

        if (data.status === "stopped") {
          setAdaptationStatus("stopped");
          setAdaptationJobId(null);
          stopAdaptationPolling();
          showNotification("Адаптацію моделі зупинено", "info");
          return;
        }

        setAdaptationStatus("running");
      } catch (error) {
        console.error("Failed to sync adaptation status:", error);
        setAdaptationStatus("failed");
        setAdaptationJobId(null);
        stopAdaptationPolling();
        showNotification("Не вдалося оновити статус адаптації", "error");
      }
    },
    [stopAdaptationPolling]
  );

  const syncGeneration = useCallback(
    async (id: number) => {
      try {
        const response = await getGenerationStatus(id);
        const data = response.data;
        const total = typeof data.iterations === "number" && data.iterations > 0 ? data.iterations : 1;
        const current = typeof data.current_iteration === "number" ? data.current_iteration : 0;
        setGenerationProgress(Math.max(0, Math.min(100, (current / total) * 100)));

        if (data.status === "completed") {
          setGenerationStatus("completed");
          stopGenerationPolling();
          setGenerationId(null);
          await loadSchedule();
          showNotification("Генерацію розкладу завершено", "success");
          return;
        }
        if (data.status === "failed") {
          setGenerationStatus("failed");
          stopGenerationPolling();
          setGenerationId(null);
          showNotification("Генерація завершилась з помилкою", "error");
          return;
        }
        if (data.status === "stopped") {
          setGenerationStatus("stopped");
          stopGenerationPolling();
          setGenerationId(null);
          showNotification("Генерацію зупинено", "info");
          return;
        }

        setGenerationStatus("running");
      } catch (error) {
        console.error("Failed to sync generation status:", error);
        setGenerationStatus("failed");
        stopGenerationPolling();
      }
    },
    [stopGenerationPolling]
  );

  const handleStartModelGeneration = async () => {
    if (!selectedModelVersion) {
      showNotification("Оберіть модель для генерації", "error");
      return;
    }

    try {
      const compatibilityResponse = await checkModelCompatibility(selectedModelVersion);
      const compatibility = compatibilityResponse.data;
      if (!compatibility.compatible) {
        const confirmAdapt = window.confirm(
          `Модель несумісна: ${compatibility.detail}\n\n` +
            "Модель буде перенавчена під вашу поточну розмірність розкладу. Продовжити?"
        );

        if (!confirmAdapt) {
          showNotification(`Модель несумісна: ${compatibility.detail}`, "error");
          setGenerationStatus("failed");
          return;
        }

        const adaptationResponse = await trainingService.startModelAdaptation({
          source_model_version: selectedModelVersion,
          iterations: 400,
          count: 100,
          seed: 42,
          train_ratio: 0.8,
          dataset_name: "dataset_compatible_100",
          device: "cpu",
          promote: false,
          iterations_mode: "total",
        });

        const jobId = adaptationResponse.data?.job_id;
        if (!jobId) {
          throw new Error("Adaptation job id is missing");
        }

        setAdaptationJobId(jobId);
        setAdaptationStatus("running");
        setAdaptationProgress(0);
        setGenerationStatus("idle");

        stopAdaptationPolling();
        adaptationPollRef.current = window.setInterval(() => {
          void syncAdaptation(jobId);
        }, 3000);
        await syncAdaptation(jobId);

        showNotification(
          "Запущено адаптацію моделі під поточну розмірність. Після завершення можна запускати генерацію.",
          "info"
        );
        return;
      }

      setGenerationStatus("running");
      setGenerationProgress(0);

      const response = await generateSchedule({
        iterations: 100,
        preserve_locked: false,
        use_existing: false,
        model_version: selectedModelVersion,
      });

      const id = response.data?.id;
      setGenerationId(id);
      await syncGeneration(id);

      stopGenerationPolling();
      generationPollRef.current = window.setInterval(() => {
        void syncGeneration(id);
      }, 1000);
      showNotification(`Генерацію запущено моделлю ${selectedModelVersion}`, "info");
    } catch (error: any) {
      console.error("Generation start failed:", error);
      setGenerationStatus("failed");
      showNotification(
        error?.response?.data?.detail || "Не вдалося запустити генерацію",
        "error"
      );
    }
  };

  const handleStopModelGeneration = async () => {
    if (!generationId) {
      return;
    }

    try {
      await stopGeneration(generationId);
      setGenerationStatus("stopped");
      setGenerationId(null);
      stopGenerationPolling();
      showNotification("Генерацію зупинено", "info");
    } catch (error) {
      console.error("Failed to stop generation:", error);
      showNotification("Не вдалося зупинити генерацію", "error");
    }
  };

  useEffect(() => {
    return () => {
      stopGenerationPolling();
      stopAdaptationPolling();
    };
  }, [stopAdaptationPolling, stopGenerationPolling]);

  // Handlers
  const handleUndo = async () => {
    try {
      await historyService.undo();
      await loadSchedule();
      checkHistoryState();
      showNotification("Скасовано останню дію", "success");
    } catch (error) {
      showNotification("Помилка скасування", "error");
    }
  };

  const handleRedo = async () => {
    try {
      await historyService.redo();
      await loadSchedule();
      checkHistoryState();
      showNotification("Повторено дію", "success");
    } catch (error) {
      showNotification("Помилка повторення", "error");
    }
  };

  const handleLockToggle = async (classItem: ScheduledClass) => {
    try {
      await lockScheduledClass(classItem.id, !classItem.is_locked);
      await loadSchedule();
      showNotification(
        classItem.is_locked ? "Заняття розблоковано" : "Заняття заблоковано",
        "success"
      );
    } catch (error) {
      showNotification("Помилка зміни статусу блокування", "error");
    }
  };

  const handleDelete = async (classItem: ScheduledClass) => {
    if (classItem.is_locked) {
      showNotification("Неможливо видалити заблоковане заняття", "error");
      return;
    }

    try {
      await deleteScheduledClass(classItem.id);
      await loadSchedule();
      showNotification("Заняття видалено", "success");
    } catch (error) {
      showNotification("Помилка видалення", "error");
    }
  };

  // Drag & Drop handlers
  const handleDragStart = (e: React.DragEvent, classItem: ScheduledClass) => {
    if (classItem.is_locked) {
      e.preventDefault();
      return;
    }
    setDraggedClass(classItem);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent, day: number, period: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDropTarget({ day, period });
  };

  const handleDragLeave = () => {
    setDropTarget(null);
  };

  const handleDrop = async (
    e: React.DragEvent,
    day: number,
    period: number
  ) => {
    e.preventDefault();
    setDropTarget(null);

    if (!draggedClass) return;

    // Find target timeslot
    // In real implementation, you would look up timeslot by day and period
    const targetTimeslotId = day * 6 + period; // Simplified calculation

    try {
      await updateScheduledClass(draggedClass.id, {
        class_id: draggedClass.id,
        timeslot_id: targetTimeslotId,
      });
      await loadSchedule();
      showNotification("Заняття переміщено", "success");
    } catch (error) {
      showNotification("Помилка переміщення", "error");
    }

    setDraggedClass(null);
  };

  const handleContextMenu = (
    e: React.MouseEvent,
    classItem: ScheduledClass
  ) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, classItem });
  };

  const showNotification = (
    message: string,
    severity: "success" | "error" | "info"
  ) => {
    setSnackbar({ open: true, message, severity });
  };

  // Get classes for specific cell
  const getClassesForCell = (day: number, period: number): ScheduledClass[] => {
    return schedule.filter(
      (c) => c.day_of_week === day && c.period_number === period
    );
  };

  const getOverallScoreColor = (score: number): "success" | "warning" | "error" => {
    if (score >= 85) return "success";
    if (score >= 65) return "warning";
    return "error";
  };

  const hardViolations =
    scheduleScore && typeof scheduleScore.details === "object"
      ? scheduleScore.details.hard_violations
      : null;
  const softViolations =
    scheduleScore && typeof scheduleScore.details === "object"
      ? scheduleScore.details.soft_violations
      : null;

  // Class Card Component
  const ClassCard: React.FC<{ classItem: ScheduledClass }> = ({
    classItem,
  }) => (
    <Card
      draggable={!classItem.is_locked}
      onDragStart={(e) => handleDragStart(e, classItem)}
      onContextMenu={(e) => handleContextMenu(e, classItem)}
      onClick={() => setSelectedClass(classItem)}
      sx={{
        mb: 0.5,
        cursor: classItem.is_locked ? "default" : "grab",
        opacity: draggedClass?.id === classItem.id ? 0.5 : 1,
        border: classItem.has_conflict ? 2 : 0,
        borderColor: "error.main",
        bgcolor: classItem.is_locked ? "grey.100" : "primary.50",
        transition: "all 0.2s",
        "&:hover": {
          transform: "scale(1.02)",
          boxShadow: 3,
        },
      }}
    >
      <CardContent sx={{ p: 1, "&:last-child": { pb: 1 } }}>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <Typography variant="subtitle2" fontWeight="bold" noWrap>
            {classItem.course_code}
          </Typography>
          <Stack direction="row" spacing={0.5}>
            {classItem.is_locked && (
              <Tooltip title="Заблоковано">
                <LockIcon sx={{ fontSize: 14, color: "warning.main" }} />
              </Tooltip>
            )}
            {classItem.has_conflict && (
              <Tooltip title={classItem.conflict_type || "Конфлікт"}>
                <WarningIcon sx={{ fontSize: 14, color: "error.main" }} />
              </Tooltip>
            )}
          </Stack>
        </Box>
        <Typography
          variant="caption"
          display="block"
          color="text.secondary"
          noWrap
        >
          {classItem.course_name}
        </Typography>
        <Divider sx={{ my: 0.5 }} />
        <Stack spacing={0.25}>
          <Typography
            variant="caption"
            sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
          >
            <PersonIcon sx={{ fontSize: 12 }} /> {classItem.teacher_name}
          </Typography>
          <Typography
            variant="caption"
            sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
          >
            <GroupIcon sx={{ fontSize: 12 }} /> {classItem.group_code}
          </Typography>
          <Typography
            variant="caption"
            sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
          >
            <RoomIcon sx={{ fontSize: 12 }} /> {classItem.classroom_code}
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );

  return (
    <Box sx={{ p: 2 }}>
      {/* Toolbar */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 2,
          }}
        >
          {/* Filter Section */}
          <Stack direction="row" spacing={2} alignItems="center">
            <ToggleButtonGroup
              value={filter.type}
              exclusive
              onChange={(_, value) =>
                value && setFilter({ ...filter, type: value })
              }
              size="small"
            >
              <ToggleButton value="group">
                <Tooltip title="По групах">
                  <GroupIcon />
                </Tooltip>
              </ToggleButton>
              <ToggleButton value="teacher">
                <Tooltip title="По викладачах">
                  <PersonIcon />
                </Tooltip>
              </ToggleButton>
              <ToggleButton value="classroom">
                <Tooltip title="По аудиторіях">
                  <RoomIcon />
                </Tooltip>
              </ToggleButton>
            </ToggleButtonGroup>

            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel>
                {filter.type === "group"
                  ? "Група"
                  : filter.type === "teacher"
                  ? "Викладач"
                  : "Аудиторія"}
              </InputLabel>
              <Select
                value={filter.id}
                label={
                  filter.type === "group"
                    ? "Група"
                    : filter.type === "teacher"
                    ? "Викладач"
                    : "Аудиторія"
                }
                onChange={(e) => {
                  const id = Number(e.target.value);
                  const items =
                    filter.type === "group"
                      ? groups
                      : filter.type === "teacher"
                      ? teachers
                      : classrooms;
                  const item = items.find((i) => i.id === id);
                  setFilter({
                    ...filter,
                    id,
                    name: item?.code || item?.full_name || "",
                  });
                }}
              >
                {(filter.type === "group"
                  ? groups
                  : filter.type === "teacher"
                  ? teachers
                  : classrooms
                ).map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.code || item.full_name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>

          {/* View Controls */}
          <Stack direction="row" spacing={1} alignItems="center">
            <FormControl size="small" sx={{ minWidth: 260 }}>
              <InputLabel>Модель для генерації</InputLabel>
              <Select
                value={selectedModelVersion}
                label="Модель для генерації"
                onChange={(e) => setSelectedModelVersion(String(e.target.value))}
              >
                {availableModels.map((model) => (
                  <MenuItem key={model.name} value={model.name}>
                    {model.name} {model.is_active ? "(active)" : ""}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Button
              variant="contained"
              color={generationStatus === "running" ? "error" : "primary"}
              onClick={generationStatus === "running" ? handleStopModelGeneration : handleStartModelGeneration}
              disabled={availableModels.length === 0 || adaptationStatus === "running"}
            >
              {generationStatus === "running" ? "Зупинити генерацію" : "Генерувати розклад"}
            </Button>

            {generationStatus === "running" && (
              <Box sx={{ minWidth: 160 }}>
                <LinearProgress variant="determinate" value={generationProgress} />
                <Typography variant="caption" color="text.secondary">
                  {generationProgress.toFixed(1)}%
                </Typography>
              </Box>
            )}

            {adaptationStatus === "running" && (
              <Box sx={{ minWidth: 200 }}>
                <LinearProgress variant="determinate" value={adaptationProgress} />
                <Typography variant="caption" color="text.secondary">
                  Адаптація моделі: {adaptationProgress.toFixed(1)}%
                </Typography>
              </Box>
            )}

            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={(_, v) => v && setViewMode(v)}
              size="small"
            >
              <ToggleButton value="week">
                <Tooltip title="Тижневий вигляд">
                  <WeekIcon />
                </Tooltip>
              </ToggleButton>
              <ToggleButton value="day">
                <Tooltip title="Денний вигляд">
                  <DayIcon />
                </Tooltip>
              </ToggleButton>
            </ToggleButtonGroup>

            <Divider orientation="vertical" flexItem />

            <Tooltip title="Скасувати">
              <span>
                <IconButton
                  onClick={handleUndo}
                  disabled={!canUndo}
                  size="small"
                >
                  <UndoIcon />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Повторити">
              <span>
                <IconButton
                  onClick={handleRedo}
                  disabled={!canRedo}
                  size="small"
                >
                  <RedoIcon />
                </IconButton>
              </span>
            </Tooltip>

            <Divider orientation="vertical" flexItem />

            <Tooltip title="Зменшити">
              <IconButton
                onClick={() => setZoom((z) => Math.max(0.7, z - 0.1))}
                size="small"
              >
                <ZoomOutIcon />
              </IconButton>
            </Tooltip>
            <Typography variant="body2">{Math.round(zoom * 100)}%</Typography>
            <Tooltip title="Збільшити">
              <IconButton
                onClick={() => setZoom((z) => Math.min(1.3, z + 0.1))}
                size="small"
              >
                <ZoomInIcon />
              </IconButton>
            </Tooltip>

            <Divider orientation="vertical" flexItem />

            <Tooltip title="Оновити">
              <IconButton onClick={() => void loadSchedule()} size="small">
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Stack>
        </Box>
      </Paper>

      {/* Timetable Grid */}
      <Paper sx={{ p: 2, overflow: "auto" }}>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 1,
            mb: 1,
          }}
        >
          <Typography
            variant="h6"
            sx={{ display: "flex", alignItems: "center", gap: 1 }}
          >
            📅 Розклад: {filter.name}
            <Chip size="small" label={`${schedule.length} занять`} />
          </Typography>

          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            {scoreLoading ? (
              <Chip size="small" label="Оцінка: ..." variant="outlined" />
            ) : scheduleScore ? (
              <Chip
                size="small"
                color={getOverallScoreColor(scheduleScore.overall)}
                label={`Оцінка: ${scheduleScore.overall.toFixed(1)}%`}
              />
            ) : (
              <Chip size="small" label="Оцінка: Н/Д" variant="outlined" />
            )}

            {hardViolations !== null && (
              <Chip
                size="small"
                label={`Hard: ${hardViolations}`}
                color={hardViolations === 0 ? "success" : "error"}
                variant="outlined"
              />
            )}
            {softViolations !== null && (
              <Chip
                size="small"
                label={`Soft: ${softViolations}`}
                color={softViolations === 0 ? "success" : "warning"}
                variant="outlined"
              />
            )}
            {scoreError && (
              <Tooltip title={scoreError}>
                <Chip
                  size="small"
                  label="Оцінка недоступна"
                  color="warning"
                  variant="outlined"
                  icon={<InfoIcon />}
                />
              </Tooltip>
            )}
          </Stack>
        </Box>

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: `100px repeat(${
              viewMode === "week" ? 5 : 1
            }, 1fr)`,
            gap: 1,
            transform: `scale(${zoom})`,
            transformOrigin: "top left",
          }}
        >
          {/* Header Row */}
          <Box sx={{ fontWeight: "bold", textAlign: "center", p: 1 }}>Пара</Box>
          {(viewMode === "week" ? DAYS : [DAYS[selectedDay]]).map(
            (day, idx) => (
              <Box
                key={day}
                sx={{
                  fontWeight: "bold",
                  textAlign: "center",
                  p: 1,
                  bgcolor: "primary.main",
                  color: "white",
                  borderRadius: 1,
                }}
              >
                {day}
              </Box>
            )
          )}

          {/* Time Slots */}
          {PERIODS.map((period) => (
            <React.Fragment key={period.number}>
              {/* Period label */}
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  alignItems: "center",
                  p: 1,
                  bgcolor: "grey.100",
                  borderRadius: 1,
                }}
              >
                <Typography variant="subtitle2">
                  {period.number} пара
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {period.time}
                </Typography>
              </Box>

              {/* Day cells */}
              {(viewMode === "week" ? [0, 1, 2, 3, 4] : [selectedDay]).map(
                (dayIdx) => {
                  const cellClasses = getClassesForCell(dayIdx, period.number);
                  const isDropTarget =
                    dropTarget?.day === dayIdx &&
                    dropTarget?.period === period.number;

                  return (
                    <Box
                      key={`${dayIdx}-${period.number}`}
                      onDragOver={(e) =>
                        handleDragOver(e, dayIdx, period.number)
                      }
                      onDragLeave={handleDragLeave}
                      onDrop={(e) => handleDrop(e, dayIdx, period.number)}
                      sx={{
                        minHeight: 100 * zoom,
                        p: 0.5,
                        bgcolor: isDropTarget
                          ? "primary.100"
                          : "background.paper",
                        border: isDropTarget ? 2 : 1,
                        borderColor: isDropTarget ? "primary.main" : "grey.200",
                        borderStyle: isDropTarget ? "dashed" : "solid",
                        borderRadius: 1,
                        transition: "all 0.2s",
                      }}
                    >
                      {cellClasses.map((classItem) => (
                        <ClassCard key={classItem.id} classItem={classItem} />
                      ))}
                      {cellClasses.length === 0 && (
                        <Box
                          sx={{
                            height: "100%",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "grey.400",
                          }}
                        >
                          <Typography variant="caption">Вільно</Typography>
                        </Box>
                      )}
                    </Box>
                  );
                }
              )}
            </React.Fragment>
          ))}
        </Box>
      </Paper>

      {/* Context Menu */}
      <Menu
        open={contextMenu !== null}
        onClose={() => setContextMenu(null)}
        anchorReference="anchorPosition"
        anchorPosition={
          contextMenu ? { top: contextMenu.y, left: contextMenu.x } : undefined
        }
      >
        <MenuItem
          onClick={() => {
            setEditDialog(true);
            setSelectedClass(contextMenu?.classItem || null);
            setContextMenu(null);
          }}
        >
          <EditIcon sx={{ mr: 1 }} /> Редагувати
        </MenuItem>
        <MenuItem
          onClick={() => {
            handleLockToggle(contextMenu?.classItem!);
            setContextMenu(null);
          }}
        >
          {contextMenu?.classItem?.is_locked ? (
            <UnlockIcon sx={{ mr: 1 }} />
          ) : (
            <LockIcon sx={{ mr: 1 }} />
          )}
          {contextMenu?.classItem?.is_locked ? "Розблокувати" : "Заблокувати"}
        </MenuItem>
        <Divider />
        <MenuItem
          onClick={() => {
            handleDelete(contextMenu?.classItem!);
            setContextMenu(null);
          }}
          sx={{ color: "error.main" }}
        >
          <DeleteIcon sx={{ mr: 1 }} /> Видалити
        </MenuItem>
      </Menu>

      {/* Day Selector for Day View */}
      {viewMode === "day" && (
        <Paper sx={{ p: 1, mt: 2 }}>
          <Stack direction="row" spacing={1} justifyContent="center">
            {DAYS.map((day, idx) => (
              <Button
                key={day}
                variant={selectedDay === idx ? "contained" : "outlined"}
                onClick={() => setSelectedDay(idx)}
                size="small"
              >
                {day}
              </Button>
            ))}
          </Stack>
        </Paper>
      )}

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
      </Snackbar>
    </Box>
  );
};

export default InteractiveTimetable;
