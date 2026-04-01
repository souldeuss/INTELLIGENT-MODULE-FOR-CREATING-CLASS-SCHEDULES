import React, { useState, useEffect } from "react";
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Typography,
  IconButton,
  Tooltip,
  Alert,
  Snackbar,
  Chip,
  Stack,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import {
  getCourses,
  createCourse,
  updateCourse,
  deleteCourse,
  exportCoursesCsv,
} from "../services/api";

interface Course {
  id: number;
  code: string;
  name: string;
  credits: number;
  hours_per_week: number;
  requires_lab?: boolean;
  difficulty?: number;
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

const CourseManagement: React.FC = () => {
  const [courses, setCourses] = useState<Course[]>([]);
  const [exporting, setExporting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCourse, setEditingCourse] = useState<Course | null>(null);
  const [formData, setFormData] = useState({
    code: "",
    name: "",
    credits: 3,
    hours_per_week: 2,
    requires_lab: false,
    difficulty: 1,
  });
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "info";
  }>({ open: false, message: "", severity: "info" });

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    try {
      const response = await getCourses();
      setCourses(response.data);
    } catch (error) {
      console.error("Failed to load courses:", error);
      showSnackbar("Помилка завантаження курсів", "error");
    }
  };

  const showSnackbar = (
    message: string,
    severity: "success" | "error" | "info"
  ) => {
    setSnackbar({ open: true, message, severity });
  };

  const handleOpenDialog = (course?: Course) => {
    if (course) {
      setEditingCourse(course);
      setFormData({
        code: course.code,
        name: course.name,
        credits: course.credits,
        hours_per_week: course.hours_per_week,
        requires_lab: course.requires_lab || false,
        difficulty: course.difficulty || 1,
      });
    } else {
      setEditingCourse(null);
      setFormData({
        code: "",
        name: "",
        credits: 3,
        hours_per_week: 2,
        requires_lab: false,
        difficulty: 1,
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingCourse(null);
  };

  const handleSave = async () => {
    try {
      if (editingCourse) {
        await updateCourse(editingCourse.id, formData);
        showSnackbar("Курс оновлено", "success");
      } else {
        await createCourse(formData);
        showSnackbar("Курс створено", "success");
      }
      handleCloseDialog();
      loadCourses();
    } catch (error: any) {
      showSnackbar(
        error.response?.data?.detail || "Помилка збереження",
        "error"
      );
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (window.confirm(`Видалити курс "${name}"?`)) {
      try {
        await deleteCourse(id);
        showSnackbar("Курс видалено", "success");
        loadCourses();
      } catch (error: any) {
        showSnackbar(
          error.response?.data?.detail || "Помилка видалення",
          "error"
        );
      }
    }
  };

  const handleDeleteAll = async () => {
    if (
      window.confirm(
        `Видалити ВСІ курси (${courses.length})? Це незворотня дія!`
      )
    ) {
      try {
        for (const course of courses) {
          await deleteCourse(course.id);
        }
        showSnackbar(`Видалено ${courses.length} курсів`, "success");
        loadCourses();
      } catch (error: any) {
        showSnackbar("Помилка видалення", "error");
        loadCourses();
      }
    }
  };

  const handleExportCsv = async () => {
    try {
      setExporting(true);
      const response = await exportCoursesCsv();

      const fallbackName = `courses_${new Date().toISOString().slice(0, 10)}.csv`;
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

      showSnackbar("CSV експорт курсів виконано", "success");
    } catch (error: any) {
      showSnackbar(
        error.response?.data?.detail || "Помилка експорту курсів",
        "error"
      );
    } finally {
      setExporting(false);
    }
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
            Управління курсами
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Всього курсів: {courses.length}
          </Typography>
        </Box>
        <Stack direction="row" spacing={2}>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleExportCsv}
            disabled={exporting}
          >
            {exporting ? "Експорт..." : "Експорт CSV"}
          </Button>
          {courses.length > 0 && (
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteSweepIcon />}
              onClick={handleDeleteAll}
            >
              Видалити всі
            </Button>
          )}
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
          >
            Додати курс
          </Button>
        </Stack>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: "grey.100" }}>
              <TableCell>
                <strong>Код</strong>
              </TableCell>
              <TableCell>
                <strong>Назва</strong>
              </TableCell>
              <TableCell align="center">
                <strong>Кредити</strong>
              </TableCell>
              <TableCell align="center">
                <strong>Год/тижд</strong>
              </TableCell>
              <TableCell align="center">
                <strong>Складність</strong>
              </TableCell>
              <TableCell align="center">
                <strong>Дії</strong>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {courses.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    Курси відсутні. Додайте перший курс.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              courses.map((course) => (
                <TableRow key={course.id} hover>
                  <TableCell>
                    <Chip
                      label={course.code}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>{course.name}</TableCell>
                  <TableCell align="center">{course.credits}</TableCell>
                  <TableCell align="center">{course.hours_per_week}</TableCell>
                  <TableCell align="center">
                    <Chip
                      label={`${course.difficulty || 1}/5`}
                      size="small"
                      color={
                        (course.difficulty || 1) >= 4
                          ? "error"
                          : (course.difficulty || 1) >= 3
                          ? "warning"
                          : "success"
                      }
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="Редагувати">
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => handleOpenDialog(course)}
                      >
                        <EditIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Видалити">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleDelete(course.id, course.name)}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingCourse ? "Редагувати курс" : "Додати новий курс"}
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Код курсу"
            fullWidth
            value={formData.code}
            onChange={(e) => setFormData({ ...formData, code: e.target.value })}
            placeholder="CS101"
          />
          <TextField
            margin="dense"
            label="Назва курсу"
            fullWidth
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Програмування"
          />
          <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
            <TextField
              margin="dense"
              label="Кредити"
              type="number"
              fullWidth
              value={formData.credits}
              onChange={(e) =>
                setFormData({ ...formData, credits: Number(e.target.value) })
              }
              inputProps={{ min: 1, max: 10 }}
            />
            <TextField
              margin="dense"
              label="Годин на тиждень"
              type="number"
              fullWidth
              value={formData.hours_per_week}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  hours_per_week: Number(e.target.value),
                })
              }
              inputProps={{ min: 1, max: 10 }}
            />
          </Stack>
          <TextField
            margin="dense"
            label="Складність (1-5)"
            type="number"
            fullWidth
            value={formData.difficulty}
            onChange={(e) =>
              setFormData({ ...formData, difficulty: Number(e.target.value) })
            }
            inputProps={{ min: 1, max: 5 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Скасувати</Button>
          <Button onClick={handleSave} variant="contained">
            {editingCourse ? "Зберегти" : "Створити"}
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

export default CourseManagement;
