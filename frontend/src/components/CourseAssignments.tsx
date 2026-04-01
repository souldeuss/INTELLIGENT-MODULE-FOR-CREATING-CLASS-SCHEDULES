import React, { useState, useEffect, useRef } from "react";
import {
  Box,
  Paper,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Tooltip,
  Alert,
  Snackbar,
  Chip,
  Stack,
  MenuItem,
  TextField,
  FormControlLabel,
  Switch,
  CircularProgress,
  Card,
  CardContent,
  Grid,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import SchoolIcon from "@mui/icons-material/School";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import DownloadIcon from "@mui/icons-material/Download";
import PersonIcon from "@mui/icons-material/Person";
import GroupIcon from "@mui/icons-material/Group";
import AssignmentIcon from "@mui/icons-material/Assignment";
import { getCourses, getTeachers, getGroups } from "../services/api";
import api from "../services/api";

interface Course {
  id: number;
  code: string;
  name: string;
  hours_per_week: number;
}

interface Teacher {
  id: number;
  code: string;
  full_name: string;
}

interface Group {
  id: number;
  code: string;
  year: number;
  students_count: number;
}

interface Assignment {
  id: number;
  course_id: number;
  teacher_id: number;
  group_id: number;
  course_code?: string;
  course_name?: string;
  teacher_name?: string;
  group_code?: string;
}

interface AutoAssignTeacherStat {
  teacher: string;
  hours: number;
  max_hours: number;
  utilization: number;
}

interface AutoAssignGroupStat {
  group: string;
  year: number;
  assigned_hours: number;
  target_hours: number;
  missing_hours: number;
}

interface AutoAssignResponse {
  message: string;
  assignments_created: number;
  teacher_stats: AutoAssignTeacherStat[];
  group_stats: AutoAssignGroupStat[];
  groups_below_target: number;
  requested_min_weekly_lessons: number;
  unresolved_group_ids: number[];
}

interface AssignmentImportResponse {
  message: string;
  rows_total: number;
  rows_imported: number;
  teacher_links_created: number;
  group_links_created: number;
  duplicates_skipped: number;
  ignored_schedule_fields_rows: number;
  errors: string[];
  warnings: string[];
}

const getFilenameFromDisposition = (
  contentDisposition: string | undefined,
  fallbackName: string
) => {
  if (!contentDisposition) {
    return fallbackName;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const basicMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return basicMatch?.[1] || fallbackName;
};

const CourseAssignments: React.FC = () => {
  const [courses, setCourses] = useState<Course[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [autoDialogOpen, setAutoDialogOpen] = useState(false);
  const [autoAssigning, setAutoAssigning] = useState(false);
  const [importingCsv, setImportingCsv] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);
  const [autoSettings, setAutoSettings] = useState({
    min_weekly_lessons_per_group: 10,
    teachers_per_course: 2,
    max_groups_per_course: 4,
    strict_teacher_load: true,
  });
  const [lastAutoAssignResult, setLastAutoAssignResult] =
    useState<AutoAssignResponse | null>(null);
  const [lastImportResult, setLastImportResult] =
    useState<AssignmentImportResponse | null>(null);
  const importFileInputRef = useRef<HTMLInputElement | null>(null);
  const [formData, setFormData] = useState({
    course_id: 0,
    teacher_id: 0,
    group_id: 0,
  });
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "info";
  }>({ open: false, message: "", severity: "info" });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [coursesRes, teachersRes, groupsRes] = await Promise.all([
        getCourses(),
        getTeachers(),
        getGroups(),
      ]);
      setCourses(coursesRes.data);
      setTeachers(teachersRes.data);
      setGroups(groupsRes.data);

      // Load assignments (course-teacher-group relationships)
      // For now, we'll derive from existing schedule
      try {
        const assignmentsRes = await api.get("/schedule/assignments");
        setAssignments(assignmentsRes.data);
      } catch {
        // If endpoint doesn't exist, show empty
        setAssignments([]);
      }
    } catch (error) {
      console.error("Failed to load data:", error);
      showSnackbar("Помилка завантаження даних", "error");
    }
  };

  const showSnackbar = (
    message: string,
    severity: "success" | "error" | "info"
  ) => {
    setSnackbar({ open: true, message, severity });
  };

  const handleOpenDialog = () => {
    setFormData({
      course_id: courses[0]?.id || 0,
      teacher_id: teachers[0]?.id || 0,
      group_id: groups[0]?.id || 0,
    });
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
  };

  const handleSave = async () => {
    try {
      await api.post("/schedule/assignments", formData);
      showSnackbar("Призначення створено", "success");
      handleCloseDialog();
      loadData();
    } catch (error: any) {
      showSnackbar(
        error.response?.data?.detail || "Помилка збереження",
        "error"
      );
    }
  };

  const handleAutoAssign = async () => {
    setAutoAssigning(true);
    try {
      const response = await api.post<AutoAssignResponse>(
        "/schedule/assignments/auto",
        null,
        {
          params: autoSettings,
        }
      );

      const result = response.data;
      setLastAutoAssignResult(result);
      setAutoDialogOpen(false);

      showSnackbar(
        `${result.message}. Створено ${result.assignments_created} призначень`,
        result.groups_below_target > 0 ? "info" : "success"
      );
      loadData();
    } catch (error: any) {
      showSnackbar(
        error.response?.data?.detail || "Помилка автопризначення",
        "error"
      );
    } finally {
      setAutoAssigning(false);
    }
  };

  const handleOpenImportPicker = () => {
    if (importingCsv) {
      return;
    }
    importFileInputRef.current?.click();
  };

  const handleImportAssignmentsCsv = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      setImportingCsv(true);
      const formData = new FormData();
      formData.append("file", file);

      const response = await api.post<AssignmentImportResponse>(
        "/schedule/assignments/import/csv",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );

      const result = response.data;
      setLastImportResult(result);

      const successMessage =
        `${result.message}. Імпортовано ${result.rows_imported}/${result.rows_total} рядків.`;
      const severity = result.errors.length > 0 ? "info" : "success";
      showSnackbar(successMessage, severity);

      loadData();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      showSnackbar(
        typeof detail === "string" ? detail : "Помилка імпорту призначень",
        "error"
      );
    } finally {
      setImportingCsv(false);
      event.target.value = "";
    }
  };

  const handleExportAssignmentsCsv = async () => {
    try {
      setExportingCsv(true);
      const response = await api.get("/schedule/assignments/export/csv", {
        responseType: "blob",
      });

      const fallbackName = `assignments_${new Date().toISOString().slice(0, 10)}.csv`;
      const filename = getFilenameFromDisposition(
        response.headers["content-disposition"],
        fallbackName
      );

      const blob =
        response.data instanceof Blob
          ? response.data
          : new Blob([response.data], { type: "text/csv;charset=utf-8;" });

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      window.URL.revokeObjectURL(url);

      showSnackbar("CSV експорт призначень виконано", "success");
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      showSnackbar(
        typeof detail === "string" ? detail : "Помилка експорту призначень",
        "error"
      );
    } finally {
      setExportingCsv(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm("Видалити це призначення?")) {
      try {
        // Знаходимо призначення за ID
        const assignment = assignments.find((a) => a.id === id);
        if (!assignment) {
          showSnackbar("Призначення не знайдено", "error");
          return;
        }

        // Передаємо course_id, teacher_id, group_id через query параметри
        await api.delete(
          `/schedule/assignments/${id}?course_id=${assignment.course_id}&teacher_id=${assignment.teacher_id}&group_id=${assignment.group_id}`
        );
        showSnackbar("Призначення видалено", "success");
        loadData();
      } catch (error: any) {
        showSnackbar(
          error.response?.data?.detail || "Помилка видалення",
          "error"
        );
      }
    }
  };

  // Statistics
  const stats = {
    totalCourses: courses.length,
    totalTeachers: teachers.length,
    totalGroups: groups.length,
    totalAssignments: assignments.length,
  };

  const topUnderfilledGroups = lastAutoAssignResult
    ? [...lastAutoAssignResult.group_stats]
        .filter((g) => g.missing_hours > 0)
        .sort((a, b) => b.missing_hours - a.missing_hours)
        .slice(0, 5)
    : [];

  return (
    <Box sx={{ p: 3 }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 3,
        }}
      >
        <Box>
          <Typography variant="h4" gutterBottom>
            <AssignmentIcon sx={{ mr: 1, verticalAlign: "middle" }} />
            Призначення курсів
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Призначте курси викладачам та групам для автоматичної генерації
            розкладу
          </Typography>
        </Box>
        <Stack direction="row" spacing={2}>
          <Button
            variant="outlined"
            startIcon={exportingCsv ? <CircularProgress size={16} /> : <DownloadIcon />}
            onClick={handleExportAssignmentsCsv}
            disabled={exportingCsv}
          >
            Експорт призначень CSV
          </Button>
          <Button
            variant="outlined"
            startIcon={importingCsv ? <CircularProgress size={16} /> : <UploadFileIcon />}
            onClick={handleOpenImportPicker}
            disabled={importingCsv}
          >
            Імпорт призначень CSV
          </Button>
          <Button
            variant="outlined"
            startIcon={<AutoFixHighIcon />}
            onClick={() => setAutoDialogOpen(true)}
            disabled={
              courses.length === 0 ||
              teachers.length === 0 ||
              groups.length === 0
            }
            color="secondary"
          >
            AI-призначення
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleOpenDialog}
            disabled={
              courses.length === 0 ||
              teachers.length === 0 ||
              groups.length === 0
            }
          >
            Додати призначення
          </Button>
        </Stack>
      </Box>

      <input
        ref={importFileInputRef}
        type="file"
        accept=".csv,text/csv"
        onChange={handleImportAssignmentsCsv}
        style={{ display: "none" }}
      />

      {/* Statistics Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: "center" }}>
              <SchoolIcon color="primary" sx={{ fontSize: 40 }} />
              <Typography variant="h4">{stats.totalCourses}</Typography>
              <Typography color="text.secondary">Курсів</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: "center" }}>
              <PersonIcon color="secondary" sx={{ fontSize: 40 }} />
              <Typography variant="h4">{stats.totalTeachers}</Typography>
              <Typography color="text.secondary">Викладачів</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: "center" }}>
              <GroupIcon color="info" sx={{ fontSize: 40 }} />
              <Typography variant="h4">{stats.totalGroups}</Typography>
              <Typography color="text.secondary">Груп</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent sx={{ textAlign: "center" }}>
              <AssignmentIcon color="success" sx={{ fontSize: 40 }} />
              <Typography variant="h4">{stats.totalAssignments}</Typography>
              <Typography color="text.secondary">Призначень</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Warning if no data */}
      {(courses.length === 0 ||
        teachers.length === 0 ||
        groups.length === 0) && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Для створення призначень необхідно мати хоча б один курс, викладача та
          групу.
          {courses.length === 0 && " Додайте курси."}
          {teachers.length === 0 && " Додайте викладачів."}
          {groups.length === 0 && " Додайте групи."}
        </Alert>
      )}

      {lastImportResult && (
        <Alert
          severity={lastImportResult.errors.length > 0 ? "warning" : "success"}
          sx={{ mb: 3 }}
        >
          CSV-імпорт призначень: оброблено {lastImportResult.rows_total} рядків, успішно {" "}
          {lastImportResult.rows_imported}. Додано зв'язків курс-викладач: {" "}
          {lastImportResult.teacher_links_created}, курс-група: {lastImportResult.group_links_created}. {" "}
          Дублікати пропущено: {lastImportResult.duplicates_skipped}.
          {lastImportResult.warnings.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="body2" fontWeight={600}>
                Попередження:
              </Typography>
              <Typography variant="body2">
                {lastImportResult.warnings.slice(0, 3).join(" | ")}
              </Typography>
            </Box>
          )}
          {lastImportResult.errors.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="body2" fontWeight={600}>
                Помилки рядків:
              </Typography>
              <Typography variant="body2">
                {lastImportResult.errors.slice(0, 3).join(" | ")}
              </Typography>
            </Box>
          )}
        </Alert>
      )}

      {lastAutoAssignResult && (
        <Alert
          severity={
            lastAutoAssignResult.groups_below_target > 0 ? "warning" : "success"
          }
          sx={{ mb: 3 }}
        >
          AI-призначення: {lastAutoAssignResult.assignments_created} зв'язків курс-група. 
          Груп нижче цілі ({lastAutoAssignResult.requested_min_weekly_lessons} год/тижд): {" "}
          {lastAutoAssignResult.groups_below_target}.
          {topUnderfilledGroups.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="body2" fontWeight={600}>
                Найбільший недобір:
              </Typography>
              <Typography variant="body2">
                {topUnderfilledGroups
                  .map((g) => `${g.group} (-${g.missing_hours} год)`)
                  .join(", ")}
              </Typography>
            </Box>
          )}
        </Alert>
      )}

      {/* Assignments Table */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Поточні призначення
        </Typography>

        {assignments.length === 0 ? (
          <Box sx={{ textAlign: "center", py: 4 }}>
            <Typography color="text.secondary" gutterBottom>
              Призначення відсутні
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Створіть призначення курсів для груп та викладачів, щоб AI міг
              генерувати розклад
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow sx={{ bgcolor: "grey.100" }}>
                  <TableCell>
                    <strong>Курс</strong>
                  </TableCell>
                  <TableCell>
                    <strong>Викладач</strong>
                  </TableCell>
                  <TableCell>
                    <strong>Група</strong>
                  </TableCell>
                  <TableCell align="center">
                    <strong>Дії</strong>
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {assignments.map((assignment) => (
                  <TableRow key={assignment.id} hover>
                    <TableCell>
                      <Chip
                        label={
                          assignment.course_code ||
                          `Course ${assignment.course_id}`
                        }
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                      <Typography
                        variant="caption"
                        display="block"
                        color="text.secondary"
                      >
                        {assignment.course_name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <PersonIcon fontSize="small" color="action" />
                        <span>
                          {assignment.teacher_name ||
                            `Teacher ${assignment.teacher_id}`}
                        </span>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={
                          assignment.group_code ||
                          `Group ${assignment.group_id}`
                        }
                        size="small"
                        color="info"
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Tooltip title="Видалити">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleDelete(assignment.id)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Quick Overview */}
      <Grid container spacing={2} sx={{ mt: 2 }}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              <SchoolIcon
                fontSize="small"
                sx={{ mr: 1, verticalAlign: "middle" }}
              />
              Доступні курси
            </Typography>
            <Divider sx={{ mb: 1 }} />
            <List dense sx={{ maxHeight: 200, overflow: "auto" }}>
              {courses.map((course) => (
                <ListItem key={course.id}>
                  <ListItemText
                    primary={course.name}
                    secondary={`${course.code} • ${course.hours_per_week} год/тижд`}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              <PersonIcon
                fontSize="small"
                sx={{ mr: 1, verticalAlign: "middle" }}
              />
              Викладачі
            </Typography>
            <Divider sx={{ mb: 1 }} />
            <List dense sx={{ maxHeight: 200, overflow: "auto" }}>
              {teachers.map((teacher) => (
                <ListItem key={teacher.id}>
                  <ListItemText
                    primary={teacher.full_name}
                    secondary={teacher.code}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              <GroupIcon
                fontSize="small"
                sx={{ mr: 1, verticalAlign: "middle" }}
              />
              Групи
            </Typography>
            <Divider sx={{ mb: 1 }} />
            <List dense sx={{ maxHeight: 200, overflow: "auto" }}>
              {groups.map((group) => (
                <ListItem key={group.id}>
                  <ListItemText
                    primary={group.code}
                    secondary={`${group.year} курс • ${group.students_count} студентів`}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>

      {/* Dialog */}
      <Dialog
        open={autoDialogOpen}
        onClose={() => !autoAssigning && setAutoDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>AI-призначення курсів</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Алгоритм спочатку намагається забезпечити мінімум занять на тиждень для кожної групи,
            після чого підбирає викладачів з урахуванням навантаження.
          </Typography>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Існуючі призначення будуть видалені та створені заново.
          </Alert>
          <TextField
            margin="dense"
            label="Мінімум занять/тиждень на групу"
            type="number"
            fullWidth
            inputProps={{ min: 1, max: 40 }}
            value={autoSettings.min_weekly_lessons_per_group}
            onChange={(e) =>
              setAutoSettings({
                ...autoSettings,
                min_weekly_lessons_per_group: Number(e.target.value || 10),
              })
            }
          />
          <TextField
            margin="dense"
            label="Викладачів на курс"
            type="number"
            fullWidth
            inputProps={{ min: 1, max: 3 }}
            value={autoSettings.teachers_per_course}
            onChange={(e) =>
              setAutoSettings({
                ...autoSettings,
                teachers_per_course: Number(e.target.value || 2),
              })
            }
          />
          <TextField
            margin="dense"
            label="Максимум груп на курс"
            type="number"
            fullWidth
            inputProps={{ min: 1, max: 20 }}
            value={autoSettings.max_groups_per_course}
            onChange={(e) =>
              setAutoSettings({
                ...autoSettings,
                max_groups_per_course: Number(e.target.value || 4),
              })
            }
          />
          <FormControlLabel
            sx={{ mt: 1 }}
            control={
              <Switch
                checked={autoSettings.strict_teacher_load}
                onChange={(e) =>
                  setAutoSettings({
                    ...autoSettings,
                    strict_teacher_load: e.target.checked,
                  })
                }
              />
            }
            label="Строго враховувати max_hours_per_week викладачів"
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setAutoDialogOpen(false)}
            disabled={autoAssigning}
          >
            Скасувати
          </Button>
          <Button
            onClick={handleAutoAssign}
            variant="contained"
            color="secondary"
            disabled={autoAssigning}
            startIcon={autoAssigning ? <CircularProgress size={16} /> : <AutoFixHighIcon />}
          >
            {autoAssigning ? "Виконується..." : "Запустити AI-призначення"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Створити призначення</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Оберіть курс, викладача та групу для створення призначення
          </Typography>
          <TextField
            margin="dense"
            label="Курс"
            select
            fullWidth
            value={formData.course_id}
            onChange={(e) =>
              setFormData({ ...formData, course_id: Number(e.target.value) })
            }
          >
            {courses.map((course) => (
              <MenuItem key={course.id} value={course.id}>
                {course.code} - {course.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            margin="dense"
            label="Викладач"
            select
            fullWidth
            value={formData.teacher_id}
            onChange={(e) =>
              setFormData({ ...formData, teacher_id: Number(e.target.value) })
            }
          >
            {teachers.map((teacher) => (
              <MenuItem key={teacher.id} value={teacher.id}>
                {teacher.full_name} ({teacher.code})
              </MenuItem>
            ))}
          </TextField>
          <TextField
            margin="dense"
            label="Група"
            select
            fullWidth
            value={formData.group_id}
            onChange={(e) =>
              setFormData({ ...formData, group_id: Number(e.target.value) })
            }
          >
            {groups.map((group) => (
              <MenuItem key={group.id} value={group.id}>
                {group.code} ({group.year} курс, {group.students_count}{" "}
                студентів)
              </MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Скасувати</Button>
          <Button onClick={handleSave} variant="contained">
            Створити
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default CourseAssignments;
