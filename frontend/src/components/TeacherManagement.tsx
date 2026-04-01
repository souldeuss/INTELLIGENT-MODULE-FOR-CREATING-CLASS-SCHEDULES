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
  TextField,
  IconButton,
  Chip,
  Alert,
  Snackbar,
  CircularProgress,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import {
  getTeachers,
  createTeacher,
  updateTeacher,
  deleteTeacher,
  exportTeachersCsv,
} from "../services/api";

interface Teacher {
  id: number;
  code: string;
  full_name: string;
  email: string;
  department: string;
  max_hours_per_week: number;
  avoid_early_slots: boolean;
  avoid_late_slots: boolean;
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

const TeacherManagement: React.FC = () => {
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingTeacher, setEditingTeacher] = useState<Teacher | null>(null);
  const [formData, setFormData] = useState({
    code: "",
    full_name: "",
    email: "",
    department: "",
    max_hours_per_week: 20,
    avoid_early_slots: false,
    avoid_late_slots: false,
  });
  const [error, setError] = useState("");
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({ open: false, message: "", severity: "success" });

  useEffect(() => {
    loadTeachers();
  }, []);

  const loadTeachers = async () => {
    try {
      setLoading(true);
      const response = await getTeachers();
      setTeachers(response.data);
    } catch (err: any) {
      setError(err.message || "Не вдалось завантажити викладачів");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (teacher?: Teacher) => {
    if (teacher) {
      setEditingTeacher(teacher);
      setFormData({
        code: teacher.code,
        full_name: teacher.full_name,
        email: teacher.email,
        department: teacher.department,
        max_hours_per_week: teacher.max_hours_per_week,
        avoid_early_slots: teacher.avoid_early_slots,
        avoid_late_slots: teacher.avoid_late_slots,
      });
    } else {
      setEditingTeacher(null);
      setFormData({
        code: "",
        full_name: "",
        email: "",
        department: "",
        max_hours_per_week: 20,
        avoid_early_slots: false,
        avoid_late_slots: false,
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingTeacher(null);
    setError("");
  };

  const handleSave = async () => {
    try {
      if (editingTeacher) {
        await updateTeacher(editingTeacher.id, formData);
        setSnackbar({ open: true, message: "Викладача оновлено!", severity: "success" });
      } else {
        await createTeacher(formData);
        setSnackbar({ open: true, message: "Викладача додано!", severity: "success" });
      }
      handleCloseDialog();
      loadTeachers();
    } catch (err: any) {
      setError(err.message || "Не вдалось зберегти викладача");
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm("Ви впевнені, що хочете видалити цього викладача?")) {
      try {
        await deleteTeacher(id);
        setSnackbar({ open: true, message: "Викладача видалено!", severity: "success" });
        loadTeachers();
      } catch (err: any) {
        setError(err.message || "Помилка видалення");
      }
    }
  };

  const handleDeleteAll = async () => {
    if (teachers.length === 0) return;
    if (window.confirm(`Видалити ВСІХ викладачів (${teachers.length})? Це незворотня дія!`)) {
      try {
        setLoading(true);
        for (const teacher of teachers) {
          await deleteTeacher(teacher.id);
        }
        setSnackbar({ open: true, message: "Всіх викладачів видалено!", severity: "success" });
        loadTeachers();
      } catch (err: any) {
        setError(err.message || "Помилка видалення");
        loadTeachers();
      } finally {
        setLoading(false);
      }
    }
  };

  const handleExportCsv = async () => {
    try {
      setExporting(true);
      const response = await exportTeachersCsv();

      const fallbackName = `teachers_${new Date().toISOString().slice(0, 10)}.csv`;
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

      setSnackbar({
        open: true,
        message: "CSV експорт викладачів виконано",
        severity: "success",
      });
    } catch (err: any) {
      setError(err.message || "Не вдалось експортувати викладачів");
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="400px"
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={3}
      >
        <Box>
          <Typography variant="h4" component="h1">
            Управління викладачами
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Всього викладачів: {teachers.length}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleExportCsv}
            disabled={exporting}
          >
            {exporting ? "Експорт..." : "Експорт CSV"}
          </Button>
          {teachers.length > 0 && (
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={handleDeleteAll}
            >
              Видалити всіх
            </Button>
          )}
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
          >
            Додати викладача
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" onClose={() => setError("")} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: "grey.100" }}>
              <TableCell><strong>Код</strong></TableCell>
              <TableCell><strong>ПІБ</strong></TableCell>
              <TableCell><strong>Email</strong></TableCell>
              <TableCell><strong>Кафедра</strong></TableCell>
              <TableCell align="center"><strong>Макс год/тижд</strong></TableCell>
              <TableCell><strong>Переваги</strong></TableCell>
              <TableCell align="right"><strong>Дії</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {teachers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    Викладачі відсутні. Додайте першого викладача.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
            teachers.map((teacher) => (
              <TableRow key={teacher.id} hover>
                <TableCell>
                  <Chip label={teacher.code} size="small" color="secondary" variant="outlined" />
                </TableCell>
                <TableCell>{teacher.full_name}</TableCell>
                <TableCell>{teacher.email || "-"}</TableCell>
                <TableCell>{teacher.department || "-"}</TableCell>
                <TableCell align="center">{teacher.max_hours_per_week}</TableCell>
                <TableCell>
                  {teacher.avoid_early_slots && (
                    <Chip label="Без ранніх" size="small" sx={{ mr: 0.5 }} color="warning" />
                  )}
                  {teacher.avoid_late_slots && (
                    <Chip label="Без пізніх" size="small" color="info" />
                  )}
                </TableCell>
                <TableCell align="right">
                  <IconButton
                    onClick={() => handleOpenDialog(teacher)}
                    size="small"
                  >
                    <EditIcon />
                  </IconButton>
                  <IconButton
                    onClick={() => handleDelete(teacher.id)}
                    size="small"
                    color="error"
                  >
                    <DeleteIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))
          )}</TableBody>
        </Table>
      </TableContainer>

      <Dialog
        open={openDialog}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingTeacher ? "Редагувати викладача" : "Додати нового викладача"}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
            <TextField
              label="Код"
              value={formData.code}
              onChange={(e) =>
                setFormData({ ...formData, code: e.target.value })
              }
              fullWidth
              required
              placeholder="T001"
            />
            <TextField
              label="Повне ім'я"
              value={formData.full_name}
              onChange={(e) =>
                setFormData({ ...formData, full_name: e.target.value })
              }
              fullWidth
              required
              placeholder="Прізвище Ім'я По-батькові"
            />
            <TextField
              label="Email"
              type="email"
              value={formData.email}
              onChange={(e) =>
                setFormData({ ...formData, email: e.target.value })
              }
              fullWidth
              placeholder="teacher@university.edu"
            />
            <TextField
              label="Кафедра"
              value={formData.department}
              onChange={(e) =>
                setFormData({ ...formData, department: e.target.value })
              }
              fullWidth
              placeholder="Кафедра інформатики"
            />
            <TextField
              label="Макс. годин на тиждень"
              type="number"
              value={formData.max_hours_per_week}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  max_hours_per_week: parseInt(e.target.value),
                })
              }
              fullWidth
              inputProps={{ min: 1, max: 40 }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Скасувати</Button>
          <Button onClick={handleSave} variant="contained" color="primary">
            {editingTeacher ? "Зберегти" : "Додати"}
          </Button>
        </DialogActions>
      </Dialog>
      
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default TeacherManagement;
