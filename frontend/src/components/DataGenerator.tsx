import React, { useState } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Typography,
  CircularProgress,
  Alert,
  Tooltip,
  IconButton,
  Paper,
  Grid,
} from "@mui/material";
import {
  Casino as RandomIcon,
  Delete as DeleteIcon,
  Info as InfoIcon,
  CheckCircle as SuccessIcon,
} from "@mui/icons-material";
import { seedService } from "../services/api";

interface DataGeneratorProps {
  onDataGenerated?: () => void;
  compact?: boolean;
}

const DataGenerator: React.FC<DataGeneratorProps> = ({
  onDataGenerated,
  compact = false,
}) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<any>(null);

  const [params, setParams] = useState({
    num_teachers: 8,
    num_groups: 6,
    num_courses: 14,
    num_classrooms: 12,
  });

  const handleOpen = () => {
    setOpen(true);
    setSuccess(false);
    setError(null);
    setStats(null);
  };

  const handleClose = () => {
    setOpen(false);
  };

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await seedService.generateRandomData(params);
      setStats(response.data);
      setSuccess(true);

      // Викликаємо callback якщо передано
      if (onDataGenerated) {
        setTimeout(() => {
          onDataGenerated();
        }, 1000);
      }
    } catch (err: any) {
      console.error("Помилка генерації даних:", err);
      setError(err.response?.data?.detail || "Помилка при генерації даних");
    } finally {
      setLoading(false);
    }
  };

  const handleClearAll = async () => {
    if (
      !window.confirm(
        "Ви впевнені, що хочете видалити ВСІ дані? Цю дію неможливо скасувати!"
      )
    ) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await seedService.clearAllData();
      setSuccess(true);
      setStats({ message: "Всі дані успішно видалені" });

      if (onDataGenerated) {
        setTimeout(() => {
          onDataGenerated();
        }, 1000);
      }
    } catch (err: any) {
      console.error("Помилка очищення даних:", err);
      setError(err.response?.data?.detail || "Помилка при видаленні даних");
    } finally {
      setLoading(false);
    }
  };

  if (compact) {
    return (
      <>
        <Tooltip title="Згенерувати тестові дані">
          <Button
            variant="outlined"
            color="primary"
            startIcon={<RandomIcon />}
            onClick={handleOpen}
            size="small"
          >
            Тестові дані
          </Button>
        </Tooltip>

        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
          <DialogTitle>
            <Box display="flex" alignItems="center">
              <RandomIcon sx={{ mr: 1 }} />
              Генерація тестових даних
            </Box>
          </DialogTitle>
          <DialogContent>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            {success && stats && (
              <Alert severity="success" icon={<SuccessIcon />} sx={{ mb: 2 }}>
                <Typography variant="body2">{stats.message}</Typography>
                {stats.timeslots && (
                  <Box mt={1}>
                    <Typography variant="caption">
                      • Таймслоти: {stats.timeslots}
                    </Typography>
                    <br />
                    <Typography variant="caption">
                      • Аудиторії: {stats.classrooms}
                    </Typography>
                    <br />
                    <Typography variant="caption">
                      • Викладачі: {stats.teachers}
                    </Typography>
                    <br />
                    <Typography variant="caption">
                      • Групи: {stats.groups}
                    </Typography>
                    <br />
                    <Typography variant="caption">
                      • Курси: {stats.courses}
                    </Typography>
                  </Box>
                )}
              </Alert>
            )}

            {!success && (
              <>
                <Alert severity="info" icon={<InfoIcon />} sx={{ mb: 2 }}>
                  Система згенерує випадкові дані для тестування: таймслоти,
                  аудиторії, викладачів, групи та курси.
                </Alert>

                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Кількість викладачів"
                      value={params.num_teachers}
                      onChange={(e) =>
                        setParams({
                          ...params,
                          num_teachers: parseInt(e.target.value) || 0,
                        })
                      }
                      inputProps={{ min: 1, max: 50 }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Кількість груп"
                      value={params.num_groups}
                      onChange={(e) =>
                        setParams({
                          ...params,
                          num_groups: parseInt(e.target.value) || 0,
                        })
                      }
                      inputProps={{ min: 1, max: 30 }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Кількість курсів"
                      value={params.num_courses}
                      onChange={(e) =>
                        setParams({
                          ...params,
                          num_courses: parseInt(e.target.value) || 0,
                        })
                      }
                      inputProps={{ min: 1, max: 50 }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Кількість аудиторій"
                      value={params.num_classrooms}
                      onChange={(e) =>
                        setParams({
                          ...params,
                          num_classrooms: parseInt(e.target.value) || 0,
                        })
                      }
                      inputProps={{ min: 1, max: 50 }}
                    />
                  </Grid>
                </Grid>
              </>
            )}
          </DialogContent>
          <DialogActions>
            {!success && (
              <>
                <Button
                  onClick={handleClearAll}
                  color="error"
                  startIcon={<DeleteIcon />}
                  disabled={loading}
                >
                  Очистити все
                </Button>
                <Box flex={1} />
              </>
            )}
            <Button onClick={handleClose} disabled={loading}>
              {success ? "Закрити" : "Скасувати"}
            </Button>
            {!success && (
              <Button
                onClick={handleGenerate}
                variant="contained"
                startIcon={
                  loading ? <CircularProgress size={20} /> : <RandomIcon />
                }
                disabled={loading}
              >
                {loading ? "Генерація..." : "Згенерувати"}
              </Button>
            )}
          </DialogActions>
        </Dialog>
      </>
    );
  }

  // Full version for settings/admin panel
  return (
    <Paper elevation={3} sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        <RandomIcon sx={{ mr: 1, verticalAlign: "middle" }} />
        Генерація тестових даних
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {success && stats && (
        <Alert severity="success" icon={<SuccessIcon />} sx={{ mb: 2 }}>
          <Typography variant="body2">{stats.message}</Typography>
          {stats.timeslots && (
            <Box mt={1}>
              <Typography variant="caption">
                • Таймслоти: {stats.timeslots}
              </Typography>
              <br />
              <Typography variant="caption">
                • Аудиторії: {stats.classrooms}
              </Typography>
              <br />
              <Typography variant="caption">
                • Викладачі: {stats.teachers}
              </Typography>
              <br />
              <Typography variant="caption">• Групи: {stats.groups}</Typography>
              <br />
              <Typography variant="caption">
                • Курси: {stats.courses}
              </Typography>
            </Box>
          )}
        </Alert>
      )}

      <Alert severity="info" icon={<InfoIcon />} sx={{ mb: 3 }}>
        Автоматична генерація випадкових даних для тестування системи розкладу.
      </Alert>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} md={3}>
          <TextField
            fullWidth
            type="number"
            label="Викладачі"
            value={params.num_teachers}
            onChange={(e) =>
              setParams({
                ...params,
                num_teachers: parseInt(e.target.value) || 0,
              })
            }
            inputProps={{ min: 1, max: 50 }}
          />
        </Grid>
        <Grid item xs={6} md={3}>
          <TextField
            fullWidth
            type="number"
            label="Групи"
            value={params.num_groups}
            onChange={(e) =>
              setParams({
                ...params,
                num_groups: parseInt(e.target.value) || 0,
              })
            }
            inputProps={{ min: 1, max: 30 }}
          />
        </Grid>
        <Grid item xs={6} md={3}>
          <TextField
            fullWidth
            type="number"
            label="Курси"
            value={params.num_courses}
            onChange={(e) =>
              setParams({
                ...params,
                num_courses: parseInt(e.target.value) || 0,
              })
            }
            inputProps={{ min: 1, max: 50 }}
          />
        </Grid>
        <Grid item xs={6} md={3}>
          <TextField
            fullWidth
            type="number"
            label="Аудиторії"
            value={params.num_classrooms}
            onChange={(e) =>
              setParams({
                ...params,
                num_classrooms: parseInt(e.target.value) || 0,
              })
            }
            inputProps={{ min: 1, max: 50 }}
          />
        </Grid>
      </Grid>

      <Box display="flex" gap={2}>
        <Button
          variant="contained"
          color="primary"
          startIcon={loading ? <CircularProgress size={20} /> : <RandomIcon />}
          onClick={handleGenerate}
          disabled={loading}
          fullWidth
        >
          {loading ? "Генерація..." : "Згенерувати дані"}
        </Button>
        <Button
          variant="outlined"
          color="error"
          startIcon={<DeleteIcon />}
          onClick={handleClearAll}
          disabled={loading}
        >
          Очистити все
        </Button>
      </Box>
    </Paper>
  );
};

export default DataGenerator;
