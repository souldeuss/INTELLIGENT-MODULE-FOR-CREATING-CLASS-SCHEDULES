import React, { useState, useEffect } from "react";
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

const CourseAssignments: React.FC = () => {
  const [courses, setCourses] = useState<Course[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
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
    if (
      window.confirm(
        "AI автоматично призначить курси викладачам та групам на основі департаментів, року навчання та складності. Існуючі призначення будуть видалені. Продовжити?"
      )
    ) {
      try {
        const response = await api.post("/schedule/assignments/auto");
        showSnackbar(
          `${response.data.message}. Створено ${response.data.assignments_created} призначень`,
          "success"
        );
        loadData();
      } catch (error: any) {
        showSnackbar(
          error.response?.data?.detail || "Помилка автопризначення",
          "error"
        );
      }
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
            startIcon={<AutoFixHighIcon />}
            onClick={handleAutoAssign}
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
