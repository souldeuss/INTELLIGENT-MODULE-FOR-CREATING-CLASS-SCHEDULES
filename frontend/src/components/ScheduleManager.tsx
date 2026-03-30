import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Snackbar,
  Chip,
  Tooltip,
  CircularProgress,
  Card,
  CardContent,
  Grid,
} from "@mui/material";
import {
  Download as DownloadIcon,
  Delete as DeleteIcon,
  Upload as UploadIcon,
  Save as SaveIcon,
  Refresh as RefreshIcon,
  Folder as FolderIcon,
} from "@mui/icons-material";
import { scheduleService } from "../services/api";

interface ScheduleFile {
  filename: string;
  created_at: string;
  size_bytes?: number;
  size_kb?: number;
  classes_count: number;
  description?: string;
  meta?: {
    generation_id?: number;
    overall_score?: number;
    best_reward?: number;
    hard_violations?: number;
    soft_violations?: number;
    description?: string;
  } | null;
}

const ScheduleManager: React.FC = () => {
  const [files, setFiles] = useState<ScheduleFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [importLoading, setImportLoading] = useState<string | null>(null);

  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "info";
  }>({ open: false, message: "", severity: "info" });

  const [exportDialog, setExportDialog] = useState(false);
  const [exportDescription, setExportDescription] = useState("");

  const [deleteDialog, setDeleteDialog] = useState<string | null>(null);

  const loadFiles = async () => {
    setLoading(true);
    try {
      const response = await scheduleService.getScheduleFiles();
      const raw = Array.isArray(response.data)
        ? response.data
        : Array.isArray(response.data?.files)
        ? response.data.files
        : [];

      const normalized: ScheduleFile[] = raw.map((file: any) => ({
        filename: String(file.filename || ""),
        created_at: String(file.created_at || new Date().toISOString()),
        size_bytes:
          typeof file.size_bytes === "number"
            ? file.size_bytes
            : typeof file.size_kb === "number"
            ? Math.round(file.size_kb * 1024)
            : 0,
        size_kb: typeof file.size_kb === "number" ? file.size_kb : undefined,
        classes_count: Number(file.classes_count || 0),
        description: typeof file.description === "string" ? file.description : undefined,
        meta:
          file.meta && typeof file.meta === "object"
            ? file.meta
            : {
                description: typeof file.description === "string" ? file.description : undefined,
              },
      }));

      setFiles(normalized);
    } catch (error) {
      console.error("Failed to load schedule files:", error);
      setSnackbar({
        open: true,
        message: "Помилка завантаження списку файлів",
        severity: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const response = await scheduleService.exportSchedule(
        exportDescription || undefined
      );
      setSnackbar({
        open: true,
        message: `Розклад збережено: ${response.data.filename}`,
        severity: "success",
      });
      setExportDialog(false);
      setExportDescription("");
      loadFiles();
    } catch (error: any) {
      setSnackbar({
        open: true,
        message: error.response?.data?.detail || "Помилка експорту розкладу",
        severity: "error",
      });
    } finally {
      setExportLoading(false);
    }
  };

  const handleImport = async (filename: string) => {
    setImportLoading(filename);
    try {
      const response = await scheduleService.importSchedule(filename, true);
      setSnackbar({
        open: true,
        message: `Завантажено ${response.data.imported_count} занять з файлу ${filename}`,
        severity: "success",
      });
    } catch (error: any) {
      setSnackbar({
        open: true,
        message: error.response?.data?.detail || "Помилка імпорту розкладу",
        severity: "error",
      });
    } finally {
      setImportLoading(null);
    }
  };

  const handleDelete = async (filename: string) => {
    try {
      await scheduleService.deleteScheduleFile(filename);
      setSnackbar({
        open: true,
        message: `Файл ${filename} видалено`,
        severity: "success",
      });
      setDeleteDialog(null);
      loadFiles();
    } catch (error: any) {
      setSnackbar({
        open: true,
        message: error.response?.data?.detail || "Помилка видалення файлу",
        severity: "error",
      });
    }
  };

  const handleDownload = async (filename: string) => {
    try {
      const response = await scheduleService.downloadScheduleFile(filename);
      const blob = new Blob([JSON.stringify(response.data, null, 2)], {
        type: "application/json",
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setSnackbar({
        open: true,
        message: "Помилка завантаження файлу",
        severity: "error",
      });
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("uk-UA", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getOverallScoreColor = (score: number): "success" | "warning" | "error" => {
    if (score >= 85) return "success";
    if (score >= 65) return "warning";
    return "error";
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
        <Typography
          variant="h4"
          sx={{ display: "flex", alignItems: "center", gap: 1 }}
        >
          <FolderIcon /> Збережені розклади
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadFiles}
            disabled={loading}
          >
            Оновити
          </Button>
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={() => setExportDialog(true)}
          >
            Зберегти поточний
          </Button>
        </Box>
      </Box>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="body2" color="text.secondary">
            Тут зберігаються всі згенеровані розклади. Ви можете завантажити
            збережений розклад, експортувати поточний або видалити непотрібні
            файли. Розклади автоматично зберігаються після кожної генерації.
          </Typography>
        </CardContent>
      </Card>

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
          <CircularProgress />
        </Box>
      ) : files.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Typography color="text.secondary">
            Немає збережених розкладів. Згенеруйте розклад або експортуйте
            поточний.
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Файл</TableCell>
                <TableCell>Дата створення</TableCell>
                <TableCell align="center">Занять</TableCell>
                <TableCell align="center">Розмір</TableCell>
                <TableCell align="center">Якість</TableCell>
                <TableCell>Опис</TableCell>
                <TableCell align="center">Дії</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {files.map((file) => (
                <TableRow key={file.filename} hover>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ fontFamily: "monospace" }}
                    >
                      {file.filename}
                    </Typography>
                  </TableCell>
                  <TableCell>{formatDate(file.created_at)}</TableCell>
                  <TableCell align="center">
                    <Chip
                      label={file.classes_count}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell align="center">
                    {formatSize(file.size_bytes || 0)}
                  </TableCell>
                  <TableCell align="center">
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 0.5,
                        alignItems: "center",
                      }}
                    >
                      {typeof file.meta?.overall_score === "number" ? (
                        <Tooltip title="Загальна оцінка розкладу (0-100)">
                          <Chip
                            label={`O: ${file.meta.overall_score.toFixed(1)}%`}
                            size="small"
                            color={getOverallScoreColor(file.meta.overall_score)}
                          />
                        </Tooltip>
                      ) : (
                        <Tooltip title="Для цього файлу оцінка ще не збережена">
                          <Chip label="O: Н/Д" size="small" variant="outlined" />
                        </Tooltip>
                      )}
                      {file.meta?.best_reward !== undefined && (
                        <Tooltip title="Найкраща винагорода">
                          <Chip
                            label={`R: ${file.meta.best_reward.toFixed(1)}`}
                            size="small"
                            color={file.meta.best_reward > 0 ? "success" : "warning"}
                            variant="outlined"
                          />
                        </Tooltip>
                      )}
                      {file.meta?.hard_violations !== undefined && (
                        <Tooltip title="Жорсткі порушення">
                          <Chip
                            label={`H: ${file.meta.hard_violations}`}
                            size="small"
                            color={file.meta.hard_violations === 0 ? "success" : "error"}
                            variant="outlined"
                          />
                        </Tooltip>
                      )}
                      {file.meta?.soft_violations !== undefined && (
                        <Tooltip title="М'які порушення">
                          <Chip
                            label={`S: ${file.meta.soft_violations}`}
                            size="small"
                            color={file.meta.soft_violations === 0 ? "success" : "warning"}
                            variant="outlined"
                          />
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ maxWidth: 200 }}
                    >
                      {file.meta?.description || file.description || "-"}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Box
                      sx={{
                        display: "flex",
                        gap: 0.5,
                        justifyContent: "center",
                      }}
                    >
                      <Tooltip title="Завантажити в систему">
                        <IconButton
                          color="primary"
                          onClick={() => handleImport(file.filename)}
                          disabled={importLoading === file.filename}
                        >
                          {importLoading === file.filename ? (
                            <CircularProgress size={20} />
                          ) : (
                            <UploadIcon />
                          )}
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Завантажити файл">
                        <IconButton
                          color="info"
                          onClick={() => handleDownload(file.filename)}
                        >
                          <DownloadIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Видалити">
                        <IconButton
                          color="error"
                          onClick={() => setDeleteDialog(file.filename)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Export Dialog */}
      <Dialog
        open={exportDialog}
        onClose={() => setExportDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Зберегти поточний розклад</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Опис (необов'язково)"
            fullWidth
            variant="outlined"
            value={exportDescription}
            onChange={(e) => setExportDescription(e.target.value)}
            placeholder="Наприклад: Основний розклад на весняний семестр"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setExportDialog(false)}>Скасувати</Button>
          <Button
            onClick={handleExport}
            variant="contained"
            disabled={exportLoading}
            startIcon={
              exportLoading ? <CircularProgress size={16} /> : <SaveIcon />
            }
          >
            Зберегти
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteDialog} onClose={() => setDeleteDialog(null)}>
        <DialogTitle>Підтвердіть видалення</DialogTitle>
        <DialogContent>
          <Typography>
            Ви впевнені, що хочете видалити файл <strong>{deleteDialog}</strong>
            ?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialog(null)}>Скасувати</Button>
          <Button
            onClick={() => deleteDialog && handleDelete(deleteDialog)}
            color="error"
            variant="contained"
          >
            Видалити
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
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ScheduleManager;
