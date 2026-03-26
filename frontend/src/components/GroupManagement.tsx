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
  Alert,
  Snackbar,
  Chip,
  CircularProgress,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import GroupsIcon from "@mui/icons-material/Groups";
import {
  getGroups,
  createGroup,
  updateGroup,
  deleteGroup,
} from "../services/api";

interface Group {
  id: number;
  code: string;
  year: number;
  students_count: number;
  specialization: string;
}

const GroupManagement: React.FC = () => {
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(false);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingGroup, setEditingGroup] = useState<Group | null>(null);
  const [formData, setFormData] = useState({
    code: "",
    year: 1,
    students_count: 25,
    specialization: "",
  });
  const [error, setError] = useState("");
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({ open: false, message: "", severity: "success" });

  useEffect(() => {
    loadGroups();
  }, []);

  const loadGroups = async () => {
    try {
      setLoading(true);
      const response = await getGroups();
      setGroups(response.data);
    } catch (err: any) {
      setError(err.message || "Не вдалося завантажити групи");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (group?: Group) => {
    if (group) {
      setEditingGroup(group);
      setFormData({
        code: group.code,
        year: group.year,
        students_count: group.students_count,
        specialization: group.specialization,
      });
    } else {
      setEditingGroup(null);
      setFormData({
        code: "",
        year: 1,
        students_count: 25,
        specialization: "",
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingGroup(null);
    setError("");
  };

  const handleSave = async () => {
    try {
      if (editingGroup) {
        await updateGroup(editingGroup.id, formData);
        setSnackbar({
          open: true,
          message: "Групу оновлено!",
          severity: "success",
        });
      } else {
        await createGroup(formData);
        setSnackbar({
          open: true,
          message: "Групу додано!",
          severity: "success",
        });
      }
      handleCloseDialog();
      loadGroups();
    } catch (err: any) {
      setError(err.message || "Не вдалося зберегти групу");
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm("Ви впевнені, що хочете видалити цю групу?")) {
      try {
        await deleteGroup(id);
        setSnackbar({
          open: true,
          message: "Групу видалено!",
          severity: "success",
        });
        loadGroups();
      } catch (err: any) {
        setError(err.message || "Не вдалося видалити групу");
      }
    }
  };

  const handleDeleteAll = async () => {
    if (groups.length === 0) return;
    if (
      window.confirm(
        `Ви впевнені, що хочете видалити всі ${groups.length} груп? Цю дію неможливо скасувати!`
      )
    ) {
      try {
        setLoading(true);
        for (const group of groups) {
          await deleteGroup(group.id);
        }
        setSnackbar({
          open: true,
          message: "Всі групи видалено!",
          severity: "success",
        });
        loadGroups();
      } catch (err: any) {
        setError(err.message || "Не вдалося видалити всі групи");
      } finally {
        setLoading(false);
      }
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
        <Box display="flex" alignItems="center" gap={2}>
          <GroupsIcon sx={{ fontSize: 40, color: "primary.main" }} />
          <Typography variant="h4" component="h1">
            Управління групами
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          {groups.length > 0 && (
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteSweepIcon />}
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
            Додати групу
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" onClose={() => setError("")} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper} elevation={2}>
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: "primary.main" }}>
              <TableCell sx={{ color: "white", fontWeight: "bold" }}>
                Код
              </TableCell>
              <TableCell sx={{ color: "white", fontWeight: "bold" }}>
                Курс
              </TableCell>
              <TableCell sx={{ color: "white", fontWeight: "bold" }}>
                К-сть студентів
              </TableCell>
              <TableCell sx={{ color: "white", fontWeight: "bold" }}>
                Спеціальність
              </TableCell>
              <TableCell
                align="right"
                sx={{ color: "white", fontWeight: "bold" }}
              >
                Дії
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {groups.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    Групи відсутні. Додайте першу групу.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              groups.map((group) => (
                <TableRow key={group.id} hover>
                  <TableCell>
                    <Chip
                      label={group.code}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={`${group.year} курс`}
                      size="small"
                      color="secondary"
                    />
                  </TableCell>
                  <TableCell>{group.students_count} студ.</TableCell>
                  <TableCell>{group.specialization || "-"}</TableCell>
                  <TableCell align="right">
                    <IconButton
                      onClick={() => handleOpenDialog(group)}
                      size="small"
                    >
                      <EditIcon />
                    </IconButton>
                    <IconButton
                      onClick={() => handleDelete(group.id)}
                      size="small"
                      color="error"
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog
        open={openDialog}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingGroup ? "Редагувати групу" : "Додати нову групу"}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
            <TextField
              label="Код групи"
              value={formData.code}
              onChange={(e) =>
                setFormData({ ...formData, code: e.target.value })
              }
              fullWidth
              required
              placeholder="КІ-21"
            />
            <TextField
              label="Курс"
              type="number"
              value={formData.year}
              onChange={(e) =>
                setFormData({ ...formData, year: parseInt(e.target.value) })
              }
              fullWidth
              required
              inputProps={{ min: 1, max: 6 }}
            />
            <TextField
              label="Кількість студентів"
              type="number"
              value={formData.students_count}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  students_count: parseInt(e.target.value),
                })
              }
              fullWidth
              inputProps={{ min: 1, max: 100 }}
            />
            <TextField
              label="Спеціальність"
              value={formData.specialization}
              onChange={(e) =>
                setFormData({ ...formData, specialization: e.target.value })
              }
              fullWidth
              placeholder="Комп'ютерна інженерія"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Скасувати</Button>
          <Button onClick={handleSave} variant="contained" color="primary">
            {editingGroup ? "Зберегти" : "Додати"}
          </Button>
        </DialogActions>
      </Dialog>

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

export default GroupManagement;
