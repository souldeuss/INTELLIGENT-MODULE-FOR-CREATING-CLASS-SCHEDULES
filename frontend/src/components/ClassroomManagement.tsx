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
  FormControlLabel,
  Switch,
  MenuItem,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import ComputerIcon from "@mui/icons-material/Computer";
import TvIcon from "@mui/icons-material/Tv";
import {
  getClassrooms,
  createClassroom,
  updateClassroom,
  deleteClassroom,
  exportClassroomsCsv,
} from "../services/api";

interface Classroom {
  id: number;
  code: string;
  building?: string;
  floor?: number;
  capacity: number;
  classroom_type: string;
  has_projector: boolean;
  has_computers: boolean;
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

const CLASSROOM_TYPES = [
  { value: "general", label: "Загальна" },
  { value: "lecture", label: "Лекційна" },
  { value: "lab", label: "Лабораторія" },
  { value: "computer", label: "Комп'ютерний клас" },
  { value: "seminar", label: "Семінарська" },
];

const ClassroomManagement: React.FC = () => {
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [exporting, setExporting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingClassroom, setEditingClassroom] = useState<Classroom | null>(
    null
  );
  const [formData, setFormData] = useState({
    code: "",
    building: "",
    floor: 1,
    capacity: 30,
    classroom_type: "general",
    has_projector: true,
    has_computers: false,
  });
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "info";
  }>({ open: false, message: "", severity: "info" });

  useEffect(() => {
    loadClassrooms();
  }, []);

  const loadClassrooms = async () => {
    try {
      const response = await getClassrooms();
      setClassrooms(response.data);
    } catch (error) {
      console.error("Failed to load classrooms:", error);
      showSnackbar("Помилка завантаження аудиторій", "error");
    }
  };

  const showSnackbar = (
    message: string,
    severity: "success" | "error" | "info"
  ) => {
    setSnackbar({ open: true, message, severity });
  };

  const handleOpenDialog = (classroom?: Classroom) => {
    if (classroom) {
      setEditingClassroom(classroom);
      setFormData({
        code: classroom.code,
        building: classroom.building || "",
        floor: classroom.floor || 1,
        capacity: classroom.capacity,
        classroom_type: classroom.classroom_type,
        has_projector: classroom.has_projector,
        has_computers: classroom.has_computers,
      });
    } else {
      setEditingClassroom(null);
      setFormData({
        code: "",
        building: "",
        floor: 1,
        capacity: 30,
        classroom_type: "general",
        has_projector: true,
        has_computers: false,
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingClassroom(null);
  };

  const handleSave = async () => {
    try {
      if (editingClassroom) {
        await updateClassroom(editingClassroom.id, formData);
        showSnackbar("Аудиторію оновлено", "success");
      } else {
        await createClassroom(formData);
        showSnackbar("Аудиторію створено", "success");
      }
      handleCloseDialog();
      loadClassrooms();
    } catch (error: any) {
      showSnackbar(
        error.response?.data?.detail || "Помилка збереження",
        "error"
      );
    }
  };

  const handleDelete = async (id: number, code: string) => {
    if (window.confirm(`Видалити аудиторію "${code}"?`)) {
      try {
        await deleteClassroom(id);
        showSnackbar("Аудиторію видалено", "success");
        loadClassrooms();
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
        `Видалити ВСІ аудиторії (${classrooms.length})? Це незворотня дія!`
      )
    ) {
      try {
        for (const classroom of classrooms) {
          await deleteClassroom(classroom.id);
        }
        showSnackbar(`Видалено ${classrooms.length} аудиторій`, "success");
        loadClassrooms();
      } catch (error: any) {
        showSnackbar("Помилка видалення", "error");
        loadClassrooms();
      }
    }
  };

  const getTypeLabel = (type: string) => {
    return CLASSROOM_TYPES.find((t) => t.value === type)?.label || type;
  };

  const handleExportCsv = async () => {
    try {
      setExporting(true);
      const response = await exportClassroomsCsv();

      const fallbackName = `classrooms_${new Date().toISOString().slice(0, 10)}.csv`;
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

      showSnackbar("CSV експорт аудиторій виконано", "success");
    } catch (error: any) {
      showSnackbar(
        error.response?.data?.detail || "Помилка експорту аудиторій",
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
            Управління аудиторіями
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Всього аудиторій: {classrooms.length} | Загальна місткість:{" "}
            {classrooms.reduce((sum, c) => sum + c.capacity, 0)} місць
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
          {classrooms.length > 0 && (
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
            Додати аудиторію
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
                <strong>Корпус</strong>
              </TableCell>
              <TableCell align="center">
                <strong>Поверх</strong>
              </TableCell>
              <TableCell align="center">
                <strong>Місткість</strong>
              </TableCell>
              <TableCell>
                <strong>Тип</strong>
              </TableCell>
              <TableCell align="center">
                <strong>Обладнання</strong>
              </TableCell>
              <TableCell align="center">
                <strong>Дії</strong>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {classrooms.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    Аудиторії відсутні. Додайте першу аудиторію.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              classrooms.map((classroom) => (
                <TableRow key={classroom.id} hover>
                  <TableCell>
                    <Chip
                      label={classroom.code}
                      size="small"
                      color="secondary"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>{classroom.building || "-"}</TableCell>
                  <TableCell align="center">{classroom.floor || "-"}</TableCell>
                  <TableCell align="center">
                    <Chip
                      label={`${classroom.capacity} місць`}
                      size="small"
                      color={
                        classroom.capacity >= 100
                          ? "success"
                          : classroom.capacity >= 50
                          ? "info"
                          : "default"
                      }
                    />
                  </TableCell>
                  <TableCell>
                    {getTypeLabel(classroom.classroom_type)}
                  </TableCell>
                  <TableCell align="center">
                    <Stack
                      direction="row"
                      spacing={0.5}
                      justifyContent="center"
                    >
                      {classroom.has_projector && (
                        <Tooltip title="Проектор">
                          <TvIcon fontSize="small" color="primary" />
                        </Tooltip>
                      )}
                      {classroom.has_computers && (
                        <Tooltip title="Комп'ютери">
                          <ComputerIcon fontSize="small" color="info" />
                        </Tooltip>
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="Редагувати">
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => handleOpenDialog(classroom)}
                      >
                        <EditIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Видалити">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() =>
                          handleDelete(classroom.id, classroom.code)
                        }
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
          {editingClassroom ? "Редагувати аудиторію" : "Додати нову аудиторію"}
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Код аудиторії"
            fullWidth
            value={formData.code}
            onChange={(e) => setFormData({ ...formData, code: e.target.value })}
            placeholder="301"
          />
          <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
            <TextField
              margin="dense"
              label="Корпус"
              fullWidth
              value={formData.building}
              onChange={(e) =>
                setFormData({ ...formData, building: e.target.value })
              }
              placeholder="Головний"
            />
            <TextField
              margin="dense"
              label="Поверх"
              type="number"
              fullWidth
              value={formData.floor}
              onChange={(e) =>
                setFormData({ ...formData, floor: Number(e.target.value) })
              }
              inputProps={{ min: 1, max: 20 }}
            />
          </Stack>
          <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
            <TextField
              margin="dense"
              label="Місткість"
              type="number"
              fullWidth
              value={formData.capacity}
              onChange={(e) =>
                setFormData({ ...formData, capacity: Number(e.target.value) })
              }
              inputProps={{ min: 1, max: 500 }}
            />
            <TextField
              margin="dense"
              label="Тип аудиторії"
              select
              fullWidth
              value={formData.classroom_type}
              onChange={(e) =>
                setFormData({ ...formData, classroom_type: e.target.value })
              }
            >
              {CLASSROOM_TYPES.map((type) => (
                <MenuItem key={type.value} value={type.value}>
                  {type.label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={formData.has_projector}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      has_projector: e.target.checked,
                    })
                  }
                />
              }
              label="Проектор"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={formData.has_computers}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      has_computers: e.target.checked,
                    })
                  }
                />
              }
              label="Комп'ютери"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Скасувати</Button>
          <Button onClick={handleSave} variant="contained">
            {editingClassroom ? "Зберегти" : "Створити"}
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

export default ClassroomManagement;
