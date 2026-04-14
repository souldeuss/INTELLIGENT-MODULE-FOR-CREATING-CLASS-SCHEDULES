import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogContent,
  Divider,
  Grid,
  IconButton,
  LinearProgress,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  BarChart as BarChartIcon,
  CheckCircle as CheckCircleIcon,
  Close as CloseIcon,
  ErrorOutline as ErrorOutlineIcon,
  Group as GroupIcon,
  Person as PersonIcon,
  Refresh as RefreshIcon,
} from "@mui/icons-material";
import { statsService, TimetableInsightsResponse } from "../services/api";

interface TimetableInsightsDialogProps {
  open: boolean;
  onClose: () => void;
}

interface SummaryCardProps {
  title: string;
  value: string;
  subtitle: string;
  progress: number;
  color: string;
}

const clampPercent = (value: number): number => {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
};

const SummaryCard: React.FC<SummaryCardProps> = ({
  title,
  value,
  subtitle,
  progress,
  color,
}) => {
  const safeProgress = clampPercent(progress);

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        borderRadius: 2,
        border: "1px solid",
        borderColor: "grey.200",
        height: "100%",
      }}
    >
      <Typography variant="body2" color="text.secondary" gutterBottom>
        {title}
      </Typography>
      <Typography variant="h4" fontWeight={700} sx={{ color, mb: 0.5 }}>
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
        {subtitle}
      </Typography>
      <LinearProgress
        variant="determinate"
        value={safeProgress}
        sx={{
          height: 8,
          borderRadius: 999,
          backgroundColor: "grey.200",
          "& .MuiLinearProgress-bar": { backgroundColor: color },
        }}
      />
    </Paper>
  );
};

const TimetableInsightsDialog: React.FC<TimetableInsightsDialogProps> = ({
  open,
  onClose,
}) => {
  const [insights, setInsights] = useState<TimetableInsightsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadInsights = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await statsService.getTimetableInsights();
      setInsights(response.data);
    } catch (requestError: any) {
      const fallbackError = "Не вдалося завантажити статистику розкладу";
      setError(requestError?.response?.data?.detail || fallbackError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    void loadInsights();
  }, [open, loadInsights]);

  const completion = insights?.completion;

  const maxDailyPeriods = useMemo(() => {
    if (!insights?.lesson_distribution_by_day?.length) {
      return 1;
    }
    return Math.max(
      1,
      ...insights.lesson_distribution_by_day.map((item) => item.periods_count)
    );
  }, [insights]);

  const generatedAtLabel = useMemo(() => {
    if (!insights?.generated_at) {
      return "";
    }
    const parsed = new Date(insights.generated_at);
    if (Number.isNaN(parsed.getTime())) {
      return "";
    }
    return parsed.toLocaleString("uk-UA");
  }, [insights]);

  const scheduledProgress = completion?.total_required_periods
    ? clampPercent((completion.scheduled_count / completion.total_required_periods) * 100)
    : 0;

  const unscheduledProgress = completion?.total_required_periods
    ? clampPercent((completion.unscheduled_count / completion.total_required_periods) * 100)
    : 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: { xs: 1.5, sm: 2.5 },
          overflow: "hidden",
          minHeight: { xs: "70vh", sm: "75vh" },
        },
      }}
    >
      <Box
        sx={{
          px: { xs: 2, sm: 3 },
          py: { xs: 2, sm: 2.5 },
          color: "common.white",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 2,
          background:
            "linear-gradient(118deg, #1d4ed8 0%, #0891b2 45%, #0d9488 100%)",
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minWidth: 0 }}>
          <BarChartIcon sx={{ fontSize: { xs: 24, sm: 30 } }} />
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6" fontWeight={700} noWrap>
              Статистика генерації розкладу
            </Typography>
            <Typography variant="body2" sx={{ opacity: 0.9 }} noWrap>
              Інсайти по активному розкладу в базі даних
            </Typography>
          </Box>
        </Stack>

        <Tooltip title="Закрити">
          <IconButton
            onClick={onClose}
            sx={{ color: "common.white", backgroundColor: "rgba(255,255,255,0.12)" }}
          >
            <CloseIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <DialogContent dividers sx={{ p: { xs: 2, sm: 3 } }}>
        <Stack spacing={3}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={1}
            justifyContent="space-between"
            alignItems={{ xs: "flex-start", sm: "center" }}
          >
            <Typography variant="body2" color="text.secondary">
              {generatedAtLabel
                ? `Оновлено: ${generatedAtLabel}`
                : "Оновлено: час недоступний"}
            </Typography>
            <Button
              size="small"
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={() => void loadInsights()}
              disabled={loading}
            >
              Оновити
            </Button>
          </Stack>

          {loading && (
            <Box sx={{ py: 8, textAlign: "center" }}>
              <CircularProgress size={36} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                Завантаження статистики...
              </Typography>
            </Box>
          )}

          {!loading && error && (
            <Alert
              severity="warning"
              action={
                <Button color="inherit" size="small" onClick={() => void loadInsights()}>
                  Повторити
                </Button>
              }
            >
              {error}
            </Alert>
          )}

          {!loading && !error && insights && (
            <>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={4}>
                  <SummaryCard
                    title="Завершеність розкладу"
                    value={`${completion?.completion_rate.toFixed(1) || "0.0"}%`}
                    subtitle={`${completion?.scheduled_count || 0} / ${completion?.total_required_periods || 0} пар`}
                    progress={completion?.completion_rate || 0}
                    color="#2563eb"
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={4}>
                  <SummaryCard
                    title="Заплановані пари"
                    value={String(completion?.scheduled_count || 0)}
                    subtitle="З урахуванням багатогодинних занять"
                    progress={scheduledProgress}
                    color="#16a34a"
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={4}>
                  <SummaryCard
                    title="Незаплановані пари"
                    value={String(completion?.unscheduled_count || 0)}
                    subtitle="Пари, які ще треба розмістити"
                    progress={unscheduledProgress}
                    color="#dc2626"
                  />
                </Grid>
              </Grid>

              <Paper elevation={0} sx={{ p: 2.5, borderRadius: 2, border: "1px solid", borderColor: "grey.200" }}>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                  <CheckCircleIcon color="primary" />
                  <Typography variant="h6" fontWeight={600}>
                    Розподіл занять за днями
                  </Typography>
                </Stack>
                <Grid container spacing={1.5}>
                  {insights.lesson_distribution_by_day.map((dayItem) => (
                    <Grid item xs={12} sm={6} md={4} lg={2} key={dayItem.day_index}>
                      <Paper
                        elevation={0}
                        sx={{
                          p: 1.5,
                          borderRadius: 1.5,
                          border: "1px solid",
                          borderColor: "grey.200",
                          backgroundColor: "grey.50",
                        }}
                      >
                        <Typography variant="body2" fontWeight={600}>
                          {dayItem.day}
                        </Typography>
                        <Typography variant="h6" color="primary.main" sx={{ mt: 0.5 }}>
                          {dayItem.periods_count} пар
                        </Typography>
                        <LinearProgress
                          variant="determinate"
                          value={clampPercent((dayItem.periods_count / maxDailyPeriods) * 100)}
                          sx={{
                            mt: 1,
                            height: 6,
                            borderRadius: 999,
                            "& .MuiLinearProgress-bar": { backgroundColor: "#2563eb" },
                          }}
                        />
                      </Paper>
                    </Grid>
                  ))}
                </Grid>
              </Paper>

              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Paper
                    elevation={0}
                    sx={{ p: 2.5, borderRadius: 2, border: "1px solid", borderColor: "grey.200" }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                      <GroupIcon color="success" />
                      <Typography variant="h6" fontWeight={600}>
                        Використання періодів групами
                      </Typography>
                    </Stack>
                    <Box sx={{ maxHeight: 320, overflowY: "auto", pr: 1 }}>
                      <Stack spacing={1.5}>
                        {insights.class_period_usage.map((item) => (
                          <Box key={item.group_id}>
                            <Stack direction="row" justifyContent="space-between" spacing={1}>
                              <Typography variant="body2" fontWeight={600} noWrap>
                                {item.group_code}
                              </Typography>
                              <Typography variant="caption" color="text.secondary" noWrap>
                                {item.assigned_periods} / {item.available_periods} ({item.usage_rate.toFixed(1)}%)
                              </Typography>
                            </Stack>
                            <LinearProgress
                              variant="determinate"
                              value={clampPercent(item.usage_rate)}
                              sx={{
                                mt: 0.7,
                                height: 7,
                                borderRadius: 999,
                                backgroundColor: "grey.200",
                                "& .MuiLinearProgress-bar": { backgroundColor: "#16a34a" },
                              }}
                            />
                          </Box>
                        ))}
                      </Stack>
                    </Box>
                  </Paper>
                </Grid>

                <Grid item xs={12} md={6}>
                  <Paper
                    elevation={0}
                    sx={{ p: 2.5, borderRadius: 2, border: "1px solid", borderColor: "grey.200" }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                      <PersonIcon color="info" />
                      <Typography variant="h6" fontWeight={600}>
                        Використання періодів викладачами
                      </Typography>
                    </Stack>
                    <Box sx={{ maxHeight: 320, overflowY: "auto", pr: 1 }}>
                      <Stack spacing={1.5}>
                        {insights.teacher_period_usage.map((item) => (
                          <Box key={item.teacher_id}>
                            <Stack direction="row" justifyContent="space-between" spacing={1}>
                              <Typography variant="body2" fontWeight={600} noWrap>
                                {item.teacher_name}
                              </Typography>
                              <Typography variant="caption" color="text.secondary" noWrap>
                                {item.assigned_periods} / {item.max_periods} ({item.usage_rate.toFixed(1)}%)
                              </Typography>
                            </Stack>
                            <LinearProgress
                              variant="determinate"
                              value={clampPercent(item.usage_rate)}
                              sx={{
                                mt: 0.7,
                                height: 7,
                                borderRadius: 999,
                                backgroundColor: "grey.200",
                                "& .MuiLinearProgress-bar": { backgroundColor: "#0284c7" },
                              }}
                            />
                          </Box>
                        ))}
                      </Stack>
                    </Box>
                  </Paper>
                </Grid>
              </Grid>
            </>
          )}

          {!loading && !error && !insights && (
            <Box sx={{ py: 6, textAlign: "center" }}>
              <ErrorOutlineIcon color="disabled" sx={{ fontSize: 38 }} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                Дані статистики наразі недоступні.
              </Typography>
            </Box>
          )}

          <Divider />
          <Typography variant="caption" color="text.secondary">
            Джерело даних: активний розклад у базі даних (поточний стан).
          </Typography>
        </Stack>
      </DialogContent>
    </Dialog>
  );
};

export default TimetableInsightsDialog;
