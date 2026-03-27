import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  BestSchedulePreviewResponse,
  TrainingHistoryResponse,
  TrainingStatusResponse,
  trainingService,
} from "../services/api";

interface LegacyTrainingMetrics {
  timestamp: string;
  iterations: number;
  metrics: {
    rewards: number[];
    hard_violations: number[];
    soft_violations: number[];
    completion_rates: number[];
    actor_losses: number[];
    critic_losses: number[];
  };
}

interface DashboardPoint {
  episode: number;
  policyLoss: number | null;
  valueLoss: number | null;
  totalLoss: number | null;
  meanReward: number | null;
  completionRate: number | null;
  hardConflicts: number | null;
  softSatisfaction: number | null;
  successfulGenerations: number | null;
  successRate: number | null;
}

const POLLING_INTERVAL_MS = 4000;

interface PresetJobStatus {
  job_id: string;
  status: "running" | "completed" | "failed" | string;
  return_code?: number | null;
  created_at?: string;
  dataset_name?: string;
  manifest?: string;
  iterations?: number;
  seed?: number;
  log_path?: string;
}

const TrainingMetrics: React.FC = () => {
  const [status, setStatus] = useState<TrainingStatusResponse | null>(null);
  const [history, setHistory] = useState<TrainingHistoryResponse | null>(null);
  const [preview, setPreview] = useState<BestSchedulePreviewResponse | null>(null);
  const [legacy, setLegacy] = useState<LegacyTrainingMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [previewMode, setPreviewMode] = useState<"heatmap" | "table">("heatmap");
  const [presetIterations, setPresetIterations] = useState(100);
  const [presetSeed, setPresetSeed] = useState(42);
  const [presetDevice, setPresetDevice] = useState("cpu");
  const [presetSubmitting, setPresetSubmitting] = useState(false);
  const [presetError, setPresetError] = useState<string | null>(null);
  const [presetInfo, setPresetInfo] = useState<string | null>(null);
  const [presetJob, setPresetJob] = useState<PresetJobStatus | null>(null);

  useEffect(() => {
    let mounted = true;

    const load = async (initial: boolean) => {
      if (!mounted) {
        return;
      }

      if (initial) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }

      try {
        const [statusRes, historyRes, previewRes] = await Promise.all([
          trainingService.getStatus(),
          trainingService.getHistory(240),
          trainingService.getBestSchedulePreview(20),
        ]);

        if (!mounted) {
          return;
        }

        setStatus(statusRes.data);
        setHistory(historyRes.data);
        setPreview(previewRes.data);
        setLegacy(null);
        setError(null);
        setLastUpdated(new Date());
      } catch (liveErr: any) {
        try {
          const legacyRes = await trainingService.getLegacyMetricsSnapshot();

          if (!mounted) {
            return;
          }

          setLegacy(legacyRes.data as LegacyTrainingMetrics);
          setStatus(null);
          setHistory(null);
          setPreview(null);
          setError(null);
          setLastUpdated(new Date());
        } catch (legacyErr: any) {
          if (!mounted) {
            return;
          }

          setError(
            liveErr?.response?.data?.detail ||
              legacyErr?.response?.data?.detail ||
              "Failed to load training dashboard"
          );
        }
      } finally {
        if (mounted) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    };

    load(true);
    const timer = window.setInterval(() => {
      load(false);
    }, POLLING_INTERVAL_MS);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!presetJob?.job_id) {
      return;
    }

    if (presetJob.status === "completed" || presetJob.status === "failed") {
      return;
    }

    let mounted = true;
    const timer = window.setInterval(async () => {
      try {
        const response = await trainingService.getDataset100PresetStatus(presetJob.job_id);
        if (!mounted) {
          return;
        }
        setPresetJob(response.data as PresetJobStatus);
      } catch (err: any) {
        if (!mounted) {
          return;
        }
        setPresetError(err?.response?.data?.detail || "Не вдалося оновити статус preset job");
      }
    }, POLLING_INTERVAL_MS);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [presetJob]);

  const handleStartPreset = async () => {
    setPresetSubmitting(true);
    setPresetError(null);
    setPresetInfo(null);

    try {
      const response = await trainingService.startDataset100Preset({
        iterations: presetIterations,
        seed: presetSeed,
        device: presetDevice,
        regenerate_dataset: true,
        promote: false,
      });

      const data = response.data as PresetJobStatus;
      if (data?.job_id) {
        setPresetJob(data);
        setPresetInfo(`Preset запущено (job: ${data.job_id}).`);
      } else {
        setPresetInfo("Preset поставлено в чергу.");
      }
    } catch (err: any) {
      setPresetError(err?.response?.data?.detail || "Не вдалося запустити dataset-100 preset");
    } finally {
      setPresetSubmitting(false);
    }
  };

  const dashboardData: DashboardPoint[] = useMemo(() => {
    if (history?.iteration?.length) {
      const softArray = history.soft_violations || [];
      const successCountArray = history.success_count || [];
      const successRateArray = history.success_rate || [];
      const softValues = softArray.filter((v): v is number => typeof v === "number");
      const maxSoft = softValues.length ? Math.max(...softValues) : 0;
      return history.iteration.map((rawEpisode, idx) => {
        const soft = softArray[idx];
        const softSatisfaction =
          typeof soft !== "number"
            ? null
            : maxSoft === 0
            ? 100
            : Number((100 * (1 - soft / maxSoft)).toFixed(2));

        return {
          episode: rawEpisode + 1,
          policyLoss: history.policy_loss?.[idx] ?? null,
          valueLoss: history.value_loss?.[idx] ?? null,
          totalLoss: history.total_loss?.[idx] ?? null,
          meanReward: history.average_reward?.[idx] ?? history.episode_reward?.[idx] ?? null,
          completionRate: history.completion_rate?.[idx] ?? null,
          hardConflicts: history.hard_violations?.[idx] ?? null,
          softSatisfaction,
          successfulGenerations: successCountArray[idx] ?? null,
          successRate: successRateArray[idx] ?? null,
        };
      });
    }

    if (!legacy) {
      return [];
    }

    const episodes = Array.from({ length: legacy.metrics.rewards.length }, (_, i) => i + 1);
    const softValues = legacy.metrics.soft_violations || [];
    const maxSoft = softValues.length ? Math.max(...softValues) : 0;

    let cumulativeSuccess = 0;
    return episodes.map((episode, idx) => {
      const soft = legacy.metrics.soft_violations[idx] ?? 0;
      const hard = legacy.metrics.hard_violations[idx] ?? null;
      if (typeof hard === "number" && hard === 0) {
        cumulativeSuccess += 1;
      }
      const successRate = episode > 0 ? Number(((cumulativeSuccess / episode) * 100).toFixed(2)) : null;
      const softSatisfaction = maxSoft === 0 ? 100 : Number((100 * (1 - soft / maxSoft)).toFixed(2));

      return {
        episode,
        policyLoss: legacy.metrics.actor_losses[idx] ?? null,
        valueLoss: legacy.metrics.critic_losses[idx] ?? null,
        totalLoss: null,
        meanReward: legacy.metrics.rewards[idx] ?? null,
        completionRate: legacy.metrics.completion_rates[idx] ?? null,
        hardConflicts: hard,
        softSatisfaction,
        successfulGenerations: cumulativeSuccess,
        successRate,
      };
    });
  }, [history, legacy]);

  const normalizedHyperparameters = useMemo(() => {
    const hp = status?.hyperparameters;
    const metrics = status?.metrics;

    const learningRate =
      typeof hp?.learning_rate === "number"
        ? hp.learning_rate
        : typeof metrics?.learning_rate === "number"
        ? metrics.learning_rate
        : null;

    return {
      learningRate,
      gamma: typeof hp?.gamma === "number" ? hp.gamma : null,
      batchSize: typeof hp?.batch_size === "number" ? hp.batch_size : null,
      epsilon: typeof hp?.epsilon === "number" ? hp.epsilon : null,
    };
  }, [status]);

  const formatNumber = (value: number | null | undefined, digits = 4): string => {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return "-";
    }
    return value.toFixed(digits);
  };

  const kpis = useMemo(() => {
    const lastPoint = dashboardData[dashboardData.length - 1];

    return {
      currentEpisode:
        status?.progress?.current_iteration ?? legacy?.iterations ?? lastPoint?.episode ?? 0,
      totalEpisodes: status?.progress?.total_iterations ?? legacy?.iterations ?? 0,
      meanReward: status?.metrics?.current_reward ?? lastPoint?.meanReward ?? 0,
      bestReward: status?.metrics?.best_reward ?? 0,
      hardConflicts: status?.metrics?.hard_violations ?? lastPoint?.hardConflicts ?? 0,
      successfulGenerations:
        status?.metrics?.successful_generations ?? lastPoint?.successfulGenerations ?? 0,
      successRate: status?.metrics?.success_rate ?? lastPoint?.successRate ?? 0,
      softSatisfaction: lastPoint?.softSatisfaction ?? 0,
    };
  }, [dashboardData, legacy, status]);

  const heatmapMax = useMemo(() => {
    if (!preview?.heatmap?.length) {
      return 1;
    }
    return Math.max(...preview.heatmap.map((cell) => cell.count), 1);
  }, [preview]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={3}>
        <Alert severity="warning">{error}</Alert>
      </Box>
    );
  }

  if (!dashboardData.length && !preview?.available) {
    return (
      <Box p={3}>
        <Alert severity="info">Немає доступних даних тренування</Alert>
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", sm: "center" }}
        spacing={1.5}
        mb={2}
      >
        <Typography variant="h4">Процес навчання нейронної мережі (DRL)</Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          {refreshing && <CircularProgress size={18} />}
          <Chip
            size="small"
            label={status?.active ? "Training Active" : "Snapshot Mode"}
            color={status?.active ? "success" : "default"}
          />
          <Chip
            size="small"
            label={lastUpdated ? `Updated: ${lastUpdated.toLocaleTimeString("uk-UA")}` : "No updates"}
            color="primary"
            variant="outlined"
          />
        </Stack>
      </Stack>

      {status?.progress && (
        <Paper elevation={0} sx={{ p: 2, mb: 3, border: "1px solid", borderColor: "divider" }}>
          <Stack spacing={1}>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2" color="text.secondary">
                Прогрес тренування
              </Typography>
              <Typography variant="body2" fontWeight={700}>
                {status.progress.percentage.toFixed(1)}%
              </Typography>
            </Stack>
            <LinearProgress variant="determinate" value={status.progress.percentage} />
          </Stack>
        </Paper>
      )}

      <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Поточний епізод
            </Typography>
            <Typography variant="h6">{kpis.currentEpisode}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Всього епізодів
            </Typography>
            <Typography variant="h6">{kpis.totalEpisodes || "-"}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Mean Reward
            </Typography>
            <Typography variant="h6">{Number(kpis.meanReward || 0).toFixed(2)}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Best Reward
            </Typography>
            <Typography variant="h6" color="success.main">
              {Number(kpis.bestReward || 0).toFixed(2)}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Hard Constraints
            </Typography>
            <Typography variant="h6" color={kpis.hardConflicts > 0 ? "error.main" : "success.main"}>
              {kpis.hardConflicts}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Successful Generations
            </Typography>
            <Typography variant="h6" color="success.main">
              {kpis.successfulGenerations}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Success Rate
            </Typography>
            <Typography variant="h6" color="primary.main">
              {Number(kpis.successRate || 0).toFixed(1)}%
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Soft Satisfaction
            </Typography>
            <Typography variant="h6" color="primary.main">
              {Number(kpis.softSatisfaction || 0).toFixed(1)}%
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Час з початку
            </Typography>
            <Typography variant="h6">{status?.timing?.elapsed_hms || "-"}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              ETA
            </Typography>
            <Typography variant="h6">{status?.timing?.estimated_remaining_hms || "-"}</Typography>
          </Grid>
        </Grid>
      </Paper>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Session Summary
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="body2" color="text.secondary">
                Dataset Version
              </Typography>
              <Typography variant="subtitle1">
                {status?.session_summary?.dataset_version || "unknown"}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="body2" color="text.secondary">
                Model Version
              </Typography>
              <Typography variant="subtitle1">
                {status?.session_summary?.model_version || "-"}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="body2" color="text.secondary">
                Epochs
              </Typography>
              <Typography variant="subtitle1">
                {status?.session_summary
                  ? `${status.session_summary.epochs_completed}/${status.session_summary.epochs_total}`
                  : "-"}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="body2" color="text.secondary">
                Runtime
              </Typography>
              <Typography variant="subtitle1">
                {status?.session_summary?.runtime_hms || status?.timing?.elapsed_hms || "00:00:00"}
              </Typography>
            </Grid>
            <Grid item xs={12} md={8}>
              <Typography variant="body2" color="text.secondary">
                Dataset Manifest
              </Typography>
              <Typography variant="subtitle2" sx={{ wordBreak: "break-all" }}>
                {status?.session_summary?.dataset_manifest || "-"}
              </Typography>
            </Grid>
            <Grid item xs={12} md={4}>
              <Typography variant="body2" color="text.secondary">
                Best Checkpoint
              </Typography>
              <Typography variant="subtitle2">
                {status?.session_summary?.best_checkpoint
                  ? `${status.session_summary.best_checkpoint.checkpoint_id} (reward ${status.session_summary.best_checkpoint.best_reward.toFixed(2)})`
                  : "-"}
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack
            direction={{ xs: "column", md: "row" }}
            justifyContent="space-between"
            alignItems={{ xs: "flex-start", md: "center" }}
            spacing={2}
            mb={2}
          >
            <Typography variant="h6">Dataset-100 Preset</Typography>
            {presetJob?.status && (
              <Chip
                size="small"
                label={`Job status: ${presetJob.status}`}
                color={presetJob.status === "completed" ? "success" : presetJob.status === "failed" ? "error" : "warning"}
              />
            )}
          </Stack>

          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={4} md={3}>
              <TextField
                fullWidth
                label="Iterations"
                type="number"
                inputProps={{ min: 10, max: 10000 }}
                value={presetIterations}
                onChange={(e) => setPresetIterations(Number(e.target.value) || 100)}
              />
            </Grid>
            <Grid item xs={12} sm={4} md={3}>
              <TextField
                fullWidth
                label="Seed"
                type="number"
                value={presetSeed}
                onChange={(e) => setPresetSeed(Number(e.target.value) || 42)}
              />
            </Grid>
            <Grid item xs={12} sm={4} md={3}>
              <TextField
                fullWidth
                label="Device"
                value={presetDevice}
                onChange={(e) => setPresetDevice(e.target.value)}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <Button
                fullWidth
                variant="contained"
                onClick={handleStartPreset}
                disabled={presetSubmitting}
              >
                {presetSubmitting ? "Starting..." : "Start Dataset-100"}
              </Button>
            </Grid>
          </Grid>

          {presetInfo && (
            <Alert severity="success" sx={{ mt: 2 }}>
              {presetInfo}
            </Alert>
          )}
          {presetError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {presetError}
            </Alert>
          )}

          {presetJob && (
            <Box mt={2}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Last preset run
              </Typography>
              <Grid container spacing={1}>
                <Grid item xs={12} md={4}>
                  <Typography variant="body2">Job ID: {presetJob.job_id}</Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="body2">Dataset: {presetJob.dataset_name || "-"}</Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="body2">Iterations: {presetJob.iterations ?? "-"}</Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
                    Manifest: {presetJob.manifest || "-"}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
                    Log: {presetJob.log_path || "-"}
                  </Typography>
                </Grid>
              </Grid>
            </Box>
          )}
        </CardContent>
      </Card>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Loss Curve
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={dashboardData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="episode" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="policyLoss" name="Policy Loss" stroke="#0d47a1" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="valueLoss" name="Value Loss" stroke="#1976d2" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="totalLoss" name="Total Loss" stroke="#42a5f5" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Mean Reward per Episode
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={dashboardData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="episode" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="meanReward" name="Mean Reward" stroke="#1565c0" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Completion Rate over Time
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={dashboardData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="episode" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="completionRate"
                    name="Completion Rate (%)"
                    stroke="#64b5f6"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
              {!dashboardData.some((point) => typeof point.completionRate === "number") && (
                <Typography variant="caption" color="text.secondary">
                  Для цього режиму завершеність епізодів недоступна.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Hard Conflicts over Time
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={dashboardData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="episode" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="hardConflicts" name="Hard Conflicts" stroke="#ef5350" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Successful Generations Trend
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={dashboardData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="episode" />
                  <YAxis yAxisId="rate" domain={[0, 100]} />
                  <YAxis yAxisId="count" orientation="right" allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Line
                    yAxisId="rate"
                    type="monotone"
                    dataKey="successRate"
                    name="Success Rate (%)"
                    stroke="#2e7d32"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    yAxisId="count"
                    type="monotone"
                    dataKey="successfulGenerations"
                    name="Successful Generations"
                    stroke="#66bb6a"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                justifyContent="space-between"
                alignItems={{ xs: "flex-start", sm: "center" }}
                spacing={1.5}
                mb={2}
              >
                <Typography variant="h6">Гіперпараметри моделі</Typography>
                <ToggleButtonGroup
                  size="small"
                  value={previewMode}
                  exclusive
                  onChange={(_, value: "heatmap" | "table" | null) => {
                    if (value) {
                      setPreviewMode(value);
                    }
                  }}
                >
                  <ToggleButton value="heatmap">Heatmap</ToggleButton>
                  <ToggleButton value="table">Mini Table</ToggleButton>
                </ToggleButtonGroup>
              </Stack>

              <Grid container spacing={2} mb={2}>
                <Grid item xs={6} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Learning Rate
                  </Typography>
                  <Typography variant="subtitle1">{formatNumber(normalizedHyperparameters.learningRate, 6)}</Typography>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Discount Factor (Gamma)
                  </Typography>
                  <Typography variant="subtitle1">{formatNumber(normalizedHyperparameters.gamma, 3)}</Typography>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Batch Size
                  </Typography>
                  <Typography variant="subtitle1">
                    {typeof normalizedHyperparameters.batchSize === "number"
                      ? normalizedHyperparameters.batchSize
                      : "-"}
                  </Typography>
                </Grid>
                <Grid item xs={6} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Epsilon
                  </Typography>
                  <Typography variant="subtitle1">{formatNumber(normalizedHyperparameters.epsilon, 3)}</Typography>
                </Grid>
              </Grid>

              <Typography variant="h6" gutterBottom>
                Візуалізація найкращого розкладу
              </Typography>

              {previewMode === "heatmap" ? (
                <Box>
                  {!preview?.heatmap?.length ? (
                    <Alert severity="info">Немає даних для heatmap</Alert>
                  ) : (
                    <Grid container spacing={1.5}>
                      {preview.heatmap.map((cell, idx) => {
                        const intensity = cell.count / heatmapMax;
                        return (
                          <Grid item xs={6} sm={4} md={3} lg={2} key={`${cell.day}-${cell.period}-${idx}`}>
                            <Paper
                              sx={{
                                p: 1.25,
                                borderRadius: 2,
                                border: "1px solid",
                                borderColor: "divider",
                                background: `linear-gradient(180deg, rgba(25,118,210,${0.12 + intensity * 0.55}) 0%, rgba(255,255,255,1) 100%)`,
                              }}
                            >
                              <Typography variant="caption" color="text.secondary">
                                {cell.day_label}, пара {cell.period}
                              </Typography>
                              <Typography variant="h6" color="primary.main">
                                {cell.count}
                              </Typography>
                            </Paper>
                          </Grid>
                        );
                      })}
                    </Grid>
                  )}
                </Box>
              ) : (
                <Box sx={{ overflowX: "auto" }}>
                  {!preview?.table?.length ? (
                    <Alert severity="info">Немає даних для mini-table</Alert>
                  ) : (
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Курс</TableCell>
                          <TableCell>Викладач</TableCell>
                          <TableCell>Група</TableCell>
                          <TableCell>Аудиторія</TableCell>
                          <TableCell>День</TableCell>
                          <TableCell>Пара</TableCell>
                          <TableCell>Час</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {preview.table.map((row, idx) => (
                          <TableRow key={`${row.course}-${row.group}-${idx}`}>
                            <TableCell>{row.course}</TableCell>
                            <TableCell>{row.teacher}</TableCell>
                            <TableCell>{row.group}</TableCell>
                            <TableCell>{row.room}</TableCell>
                            <TableCell>{row.day_label}</TableCell>
                            <TableCell>{row.period}</TableCell>
                            <TableCell>
                              {row.start_time && row.end_time
                                ? `${row.start_time} - ${row.end_time}`
                                : "-"}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default TrainingMetrics;
