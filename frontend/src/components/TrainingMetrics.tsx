import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,

  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  LinearProgress,
  MenuItem,
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
  DatasetDimensionsResponse,
  Dataset100PresetStatusResponse,
  ModelVersionItem,
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
  loss: number | null;
  meanReward: number | null;
  completionRate: number | null;
  hardConflicts: number | null;
  softSatisfaction: number | null;
  successfulGenerations: number | null;
  successRate: number | null;
}

interface TrainingHyperparameterDraft {
  learning_rate: number;
  gamma: number;
  epsilon: number;
}

const POLLING_INTERVAL_MS = 4000;
const TRAINING_DASHBOARD_CACHE_KEY = "trainingMetricsDashboardCacheV1";
const DEFAULT_TRAINING_HYPERPARAMETERS: TrainingHyperparameterDraft = {
  learning_rate: 3e-4,
  gamma: 0.99,
  epsilon: 0.2,
};

type PresetJobStatus = Dataset100PresetStatusResponse;

interface TrainingDashboardCache {
  status: TrainingStatusResponse | null;
  history: TrainingHistoryResponse | null;
  preview: BestSchedulePreviewResponse | null;
  legacy: LegacyTrainingMetrics | null;
  presetJob: PresetJobStatus | null;
  modelVersions: ModelVersionItem[];
  selectedModelVersion: string;
  compareModelVersion: string;
  trainingHyperparameters: TrainingHyperparameterDraft;
  lastUpdatedIso: string | null;
}

const sanitizeTrainingHyperparameters = (
  source?: Partial<TrainingHyperparameterDraft> | null
): TrainingHyperparameterDraft => ({
  learning_rate:
    typeof source?.learning_rate === "number" ? source.learning_rate : DEFAULT_TRAINING_HYPERPARAMETERS.learning_rate,
  gamma: typeof source?.gamma === "number" ? source.gamma : DEFAULT_TRAINING_HYPERPARAMETERS.gamma,
  epsilon: typeof source?.epsilon === "number" ? source.epsilon : DEFAULT_TRAINING_HYPERPARAMETERS.epsilon,
});

const readDashboardCache = (): TrainingDashboardCache | null => {
  try {
    const raw = localStorage.getItem(TRAINING_DASHBOARD_CACHE_KEY);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<TrainingDashboardCache>;
    return {
      status: parsed.status ?? null,
      history: parsed.history ?? null,
      preview: parsed.preview ?? null,
      legacy: parsed.legacy ?? null,
      presetJob: parsed.presetJob ?? null,
      modelVersions: Array.isArray(parsed.modelVersions) ? parsed.modelVersions : [],
      selectedModelVersion: parsed.selectedModelVersion ?? "",
      compareModelVersion: parsed.compareModelVersion ?? "",
      trainingHyperparameters: sanitizeTrainingHyperparameters(parsed.trainingHyperparameters),
      lastUpdatedIso: parsed.lastUpdatedIso ?? null,
    };
  } catch {
    return null;
  }
};

const TrainingMetrics: React.FC = () => {
  const initialCache = useMemo(() => readDashboardCache(), []);
  const hasCachedSnapshot = useMemo(() => {
    if (!initialCache) {
      return false;
    }
    return Boolean(initialCache.status || initialCache.history || initialCache.preview || initialCache.legacy || initialCache.presetJob);
  }, [initialCache]);

  const [status, setStatus] = useState<TrainingStatusResponse | null>(initialCache?.status ?? null);
  const [history, setHistory] = useState<TrainingHistoryResponse | null>(initialCache?.history ?? null);
  const [preview, setPreview] = useState<BestSchedulePreviewResponse | null>(initialCache?.preview ?? null);
  const [legacy, setLegacy] = useState<LegacyTrainingMetrics | null>(initialCache?.legacy ?? null);
  const [loading, setLoading] = useState(!hasCachedSnapshot);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(
    initialCache?.lastUpdatedIso ? new Date(initialCache.lastUpdatedIso) : null
  );
  const [previewMode, setPreviewMode] = useState<"heatmap" | "table">("heatmap");
  const [presetIterations, setPresetIterations] = useState(100);
  const [presetSeed, setPresetSeed] = useState(42);
  const [presetDevice, setPresetDevice] = useState("cpu");
  const [trainingHyperparameters, setTrainingHyperparameters] = useState<TrainingHyperparameterDraft>(
    initialCache?.trainingHyperparameters ?? DEFAULT_TRAINING_HYPERPARAMETERS
  );
  const [datasetSizeMode, setDatasetSizeMode] = useState<"compatible_100" | "compatible_1000" | "custom">("compatible_100");
  const [customDatasetSize, setCustomDatasetSize] = useState(200);
  const [iterationsMode, setIterationsMode] = useState<"total" | "per-case">("total");
  const [presetSubmitting, setPresetSubmitting] = useState(false);
  const [presetStopping, setPresetStopping] = useState(false);
  const [hyperparameterSubmitting, setHyperparameterSubmitting] = useState(false);
  const [presetError, setPresetError] = useState<string | null>(null);
  const [presetInfo, setPresetInfo] = useState<string | null>(null);
  const [hyperparameterError, setHyperparameterError] = useState<string | null>(null);
  const [hyperparameterInfo, setHyperparameterInfo] = useState<string | null>(null);
  const [presetJob, setPresetJob] = useState<PresetJobStatus | null>(initialCache?.presetJob ?? null);
  const [modelVersions, setModelVersions] = useState<ModelVersionItem[]>(initialCache?.modelVersions ?? []);
  const [selectedModelVersion, setSelectedModelVersion] = useState<string>(initialCache?.selectedModelVersion ?? "");
  const [compareModelVersion, setCompareModelVersion] = useState<string>(initialCache?.compareModelVersion ?? "");
  const [compareHistory, setCompareHistory] = useState<TrainingHistoryResponse | null>(null);
  const [datasetDimensions, setDatasetDimensions] = useState<DatasetDimensionsResponse | null>(null);
  const [datasetDimensionsError, setDatasetDimensionsError] = useState<string | null>(null);
  const [fullscreenChart, setFullscreenChart] = useState<"policy" | "loss" | "reward" | "completion" | "success" | null>(null);
  const hasHydratedHyperparametersRef = useRef(Boolean(initialCache?.trainingHyperparameters));

  const selectedDatasetName = useMemo(() => {
    if (presetJob?.dataset_name) {
      return presetJob.dataset_name;
    }
    if (datasetSizeMode === "compatible_100") {
      return "dataset_compatible_100";
    }
    if (datasetSizeMode === "compatible_1000") {
      return "dataset_compatible_1000";
    }
    return `dataset_${customDatasetSize}`;
  }, [customDatasetSize, datasetSizeMode, presetJob?.dataset_name]);

  useEffect(() => {
    try {
      localStorage.setItem(
        TRAINING_DASHBOARD_CACHE_KEY,
        JSON.stringify({
          status,
          history,
          preview,
          legacy,
          presetJob,
          modelVersions,
          selectedModelVersion,
          compareModelVersion,
          trainingHyperparameters,
          lastUpdatedIso: lastUpdated ? lastUpdated.toISOString() : null,
        } satisfies TrainingDashboardCache)
      );
    } catch {
      // Ignore cache write failures and continue with in-memory state.
    }
  }, [
    status,
    history,
    preview,
    legacy,
    presetJob,
    modelVersions,
    selectedModelVersion,
    compareModelVersion,
    trainingHyperparameters,
    lastUpdated,
  ]);

  useEffect(() => {
    if (hasHydratedHyperparametersRef.current) {
      return;
    }

    const hyperparameters = status?.hyperparameters;
    if (!hyperparameters) {
      return;
    }

    setTrainingHyperparameters({
      learning_rate:
        typeof hyperparameters.learning_rate === "number"
          ? hyperparameters.learning_rate
          : DEFAULT_TRAINING_HYPERPARAMETERS.learning_rate,
      gamma: typeof hyperparameters.gamma === "number" ? hyperparameters.gamma : DEFAULT_TRAINING_HYPERPARAMETERS.gamma,
      epsilon: typeof hyperparameters.epsilon === "number" ? hyperparameters.epsilon : DEFAULT_TRAINING_HYPERPARAMETERS.epsilon,
    });
    hasHydratedHyperparametersRef.current = true;
  }, [status]);

  useEffect(() => {
    if (presetJob?.job_id) {
      return;
    }

    let mounted = true;
    const restoreActiveJob = async () => {
      try {
        const response = await trainingService.getModelTrainingJobs();
        if (!mounted) {
          return;
        }

        const jobs = response.data?.jobs || [];
        const activeJob = jobs.find((job) => job.status === "running") || jobs[0] || null;
        if (activeJob) {
          setPresetJob(activeJob);
        }
      } catch {
        // Keep UI responsive even if jobs restore endpoint is temporarily unavailable.
      }
    };

    void restoreActiveJob();
    return () => {
      mounted = false;
    };
  }, [presetJob?.job_id]);

  useEffect(() => {
    let mounted = true;

    const load = async (initial: boolean) => {
      if (!mounted) {
        return;
      }

      if (initial) {
        if (hasCachedSnapshot) {
          setRefreshing(true);
        } else {
          setLoading(true);
        }
      } else {
        setRefreshing(true);
      }

      try {
        const [statusRes, modelsRes] = await Promise.all([trainingService.getStatus(), trainingService.getModelVersions()]);

        if (!mounted) {
          return;
        }

        const versions = modelsRes.data?.versions || [];
        const activeModel = modelsRes.data?.active_model || "";
        const effectivePrimaryModel =
          selectedModelVersion && versions.some((item) => item.name === selectedModelVersion)
            ? selectedModelVersion
            : activeModel || versions[0]?.name || "";

        const effectiveCompareModel =
          compareModelVersion && compareModelVersion !== effectivePrimaryModel ? compareModelVersion : "";

        const [historyRes, compareHistoryRes, previewRes] = await Promise.all([
          trainingService.getHistory(240, effectivePrimaryModel || undefined),
          effectiveCompareModel ? trainingService.getHistory(240, effectiveCompareModel) : Promise.resolve(null),
          trainingService.getBestSchedulePreview(20, effectivePrimaryModel || undefined),
        ]);

        if (!mounted) {
          return;
        }

        setStatus(statusRes.data);
        setHistory(historyRes.data);
        setCompareHistory(compareHistoryRes?.data || null);
        setPreview(previewRes.data);
        setModelVersions(versions);
        if (effectivePrimaryModel !== selectedModelVersion) {
          setSelectedModelVersion(effectivePrimaryModel);
        }
        if (!effectiveCompareModel && compareModelVersion) {
          setCompareModelVersion("");
        }
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
          setCompareHistory(null);
          setPreview(null);
          setError(null);
          setLastUpdated(new Date());

          const [modelsRes] = await Promise.allSettled([trainingService.getModelVersions()]);
          if (modelsRes.status === "fulfilled") {
            setModelVersions(modelsRes.value.data?.versions || []);
          }
        } catch (legacyErr: any) {
          if (!mounted) {
            return;
          }

          setError(
            liveErr?.response?.data?.detail || legacyErr?.response?.data?.detail || "Failed to load training dashboard"
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
  }, [compareModelVersion, hasCachedSnapshot, selectedModelVersion]);

  useEffect(() => {
    if (!presetJob?.job_id) {
      return;
    }

    if (presetJob.status === "completed" || presetJob.status === "failed" || presetJob.status === "stopped") {
      return;
    }

    let mounted = true;
    const timer = window.setInterval(async () => {
      try {
        const response = await trainingService.getModelTrainingStatus(presetJob.job_id);
        if (!mounted) {
          return;
        }
        setPresetJob(response.data);
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

  useEffect(() => {
    let mounted = true;

    const loadDimensions = async () => {
      try {
        const response = await trainingService.getDatasetDimensions(selectedDatasetName);
        if (!mounted) {
          return;
        }
        setDatasetDimensions(response.data);
        setDatasetDimensionsError(null);
      } catch (err: any) {
        if (!mounted) {
          return;
        }
        setDatasetDimensions(null);
        setDatasetDimensionsError(err?.response?.data?.detail || "Не вдалося отримати розмірності поточної БД/датасету");
      }
    };

    void loadDimensions();
    const timer = window.setInterval(() => {
      void loadDimensions();
    }, POLLING_INTERVAL_MS);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [selectedDatasetName]);

  const handleStartPreset = async () => {
    setPresetSubmitting(true);
    setPresetError(null);
    setPresetInfo(null);

    try {
      const response = await trainingService.createModelTraining({
        iterations: presetIterations,
        seed: presetSeed,
        device: presetDevice,
        learning_rate: trainingHyperparameters.learning_rate,
        gamma: trainingHyperparameters.gamma,
        epsilon: trainingHyperparameters.epsilon,
        dataset_size_mode: datasetSizeMode,
        custom_case_count: datasetSizeMode === "custom" ? customDatasetSize : undefined,
        iterations_mode: iterationsMode,
        regenerate_dataset: true,
        promote: false,
      });

      const data = response.data as PresetJobStatus;
      if (data?.job_id) {
        setPresetJob(data);
        setPresetInfo(`Навчання моделі запущено (job: ${data.job_id}).`);
      } else {
        setPresetInfo("Тренування моделі поставлено в чергу.");
      }
    } catch (err: any) {
      setPresetError(err?.response?.data?.detail || "Не вдалося запустити навчання моделі");
    } finally {
      setPresetSubmitting(false);
    }
  };

  const handleStopPreset = async () => {
    if (!presetJob?.job_id || presetJob.status !== "running") {
      return;
    }

    setPresetStopping(true);
    setPresetError(null);
    try {
      const response = await trainingService.stopModelTraining(presetJob.job_id);
      setPresetJob(response.data as PresetJobStatus);
      setPresetInfo("Тренування моделі зупинено.");
    } catch (err: any) {
      setPresetError(err?.response?.data?.detail || "Не вдалося зупинити тренування");
    } finally {
      setPresetStopping(false);
    }
  };

  const handleHyperparameterChange = (field: keyof TrainingHyperparameterDraft, value: string) => {
    const parsed = Number(value);
    setTrainingHyperparameters((previous) => ({
      ...previous,
      [field]: Number.isFinite(parsed) ? parsed : previous[field],
    }));
  };

  const handleApplyHyperparameters = async () => {
    if (!presetJob?.job_id || presetJob.status !== "running") {
      setHyperparameterError("Live update доступний лише для активного job.");
      return;
    }

    setHyperparameterSubmitting(true);
    setHyperparameterError(null);
    setHyperparameterInfo(null);

    const activeHyperparameters = {
      learning_rate:
        typeof status?.hyperparameters?.learning_rate === "number"
          ? status.hyperparameters.learning_rate
          : typeof status?.metrics?.learning_rate === "number"
          ? status.metrics.learning_rate
          : null,
      gamma: typeof status?.hyperparameters?.gamma === "number" ? status.hyperparameters.gamma : null,
      epsilon: typeof status?.hyperparameters?.epsilon === "number" ? status.hyperparameters.epsilon : null,
    };

    const updates: Array<Promise<unknown>> = [];
    const queuedLabels: string[] = [];

    (Object.keys(trainingHyperparameters) as Array<keyof TrainingHyperparameterDraft>).forEach((field) => {
      const currentValue = activeHyperparameters[field];
      const nextValue = trainingHyperparameters[field];
      if (typeof currentValue === "number" && Math.abs(currentValue - nextValue) < 1e-12) {
        return;
      }

      updates.push(
        trainingService.updateHyperparameter({
          parameter: field,
          value: nextValue,
          reason: `Updated from training dashboard for job ${presetJob.job_id}`,
        })
      );
      queuedLabels.push(field.replace("_", " "));
    });

    if (!updates.length) {
      setHyperparameterInfo("Немає змін для застосування.");
      setHyperparameterSubmitting(false);
      return;
    }

    try {
      await Promise.all(updates);
      setHyperparameterInfo(
        `Оновлення поставлено в чергу: ${queuedLabels.join(", ")}. Зміни застосуються з наступної ітерації.`
      );
    } catch (err: any) {
      setHyperparameterError(err?.response?.data?.detail || "Не вдалося оновити PPO гіперпараметри");
    } finally {
      setHyperparameterSubmitting(false);
    }
  };

  const dashboardData: DashboardPoint[] = useMemo(() => {
    const asPercent = (value: number | null | undefined): number | null => {
      if (typeof value !== "number") {
        return null;
      }
      return value <= 1 ? Number((value * 100).toFixed(2)) : Number(value.toFixed(2));
    };

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
          loss: history.total_loss?.[idx] ?? history.value_loss?.[idx] ?? null,
          meanReward: Math.abs(
            history.reward_per_step?.[idx] ?? history.average_reward?.[idx] ?? history.episode_reward?.[idx] ?? 0
          ),
          completionRate: asPercent(history.completion_rate?.[idx]),
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
        loss: legacy.metrics.critic_losses[idx] ?? null,
        meanReward: Math.abs(legacy.metrics.rewards[idx] ?? 0),
        completionRate: asPercent(legacy.metrics.completion_rates[idx] ?? null),
        hardConflicts: hard,
        softSatisfaction,
        successfulGenerations: cumulativeSuccess,
        successRate,
      };
    });
  }, [history, legacy]);

  const compareDashboardData: DashboardPoint[] = useMemo(() => {
    if (!compareHistory?.iteration?.length) {
      return [];
    }

    const asPercent = (value: number | null | undefined): number | null => {
      if (typeof value !== "number") {
        return null;
      }
      return value <= 1 ? Number((value * 100).toFixed(2)) : Number(value.toFixed(2));
    };

    const softArray = compareHistory.soft_violations || [];
    const successCountArray = compareHistory.success_count || [];
    const successRateArray = compareHistory.success_rate || [];
    const softValues = softArray.filter((v): v is number => typeof v === "number");
    const maxSoft = softValues.length ? Math.max(...softValues) : 0;

    return compareHistory.iteration.map((rawEpisode, idx) => {
      const soft = softArray[idx];
      const softSatisfaction =
        typeof soft !== "number"
          ? null
          : maxSoft === 0
          ? 100
          : Number((100 * (1 - soft / maxSoft)).toFixed(2));

      return {
        episode: rawEpisode + 1,
        policyLoss: compareHistory.policy_loss?.[idx] ?? null,
        loss: compareHistory.total_loss?.[idx] ?? compareHistory.value_loss?.[idx] ?? null,
        meanReward: Math.abs(
          compareHistory.reward_per_step?.[idx] ??
            compareHistory.average_reward?.[idx] ??
            compareHistory.episode_reward?.[idx] ??
            0
        ),
        completionRate: asPercent(compareHistory.completion_rate?.[idx]),
        hardConflicts: compareHistory.hard_violations?.[idx] ?? null,
        softSatisfaction,
        successfulGenerations: successCountArray[idx] ?? null,
        successRate: successRateArray[idx] ?? null,
      };
    });
  }, [compareHistory]);

  const rewardComparisonData = useMemo(() => {
    const maxLen = Math.max(dashboardData.length, compareDashboardData.length);
    if (maxLen === 0) {
      return [];
    }

    const rows: Array<{ episode: number; primaryReward: number | null; compareReward: number | null }> = [];
    for (let idx = 0; idx < maxLen; idx += 1) {
      rows.push({
        episode: idx + 1,
        primaryReward: dashboardData[idx]?.meanReward ?? null,
        compareReward: compareDashboardData[idx]?.meanReward ?? null,
      });
    }
    return rows;
  }, [compareDashboardData, dashboardData]);

  const completionComparisonData = useMemo(() => {
    const maxLen = Math.max(dashboardData.length, compareDashboardData.length);
    if (maxLen === 0) {
      return [];
    }
    const rows: Array<{ episode: number; primaryCompletion: number | null; compareCompletion: number | null }> = [];
    for (let idx = 0; idx < maxLen; idx += 1) {
      rows.push({
        episode: idx + 1,
        primaryCompletion: dashboardData[idx]?.completionRate ?? null,
        compareCompletion: compareDashboardData[idx]?.completionRate ?? null,
      });
    }
    return rows;
  }, [compareDashboardData, dashboardData]);

  const policyLossChartData = useMemo(() => {
    return dashboardData.map((point) => ({
      episode: point.episode,
      policyLoss: point.policyLoss,
    }));
  }, [dashboardData]);

  const lossChartData = useMemo(() => {
    return dashboardData.map((point) => ({
      episode: point.episode,
      loss: point.loss,
    }));
  }, [dashboardData]);

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

  const compactFormatter = useMemo(
    () =>
      new Intl.NumberFormat("uk-UA", {
        notation: "compact",
        maximumFractionDigits: 2,
      }),
    []
  );

  const formatMetricCompact = (value: number | null | undefined, digits = 2): string => {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return "-";
    }

    const absValue = Math.abs(value);
    if (absValue >= 1000) {
      return compactFormatter.format(value);
    }

    return value.toFixed(digits);
  };

  const formatChartValue = (value: number | string): string => {
    if (typeof value === "number") {
      return formatMetricCompact(value);
    }

    const parsed = Number(value);
    if (!Number.isNaN(parsed)) {
      return formatMetricCompact(parsed);
    }

    return String(value);
  };

  const parseDurationSeconds = (value: string | number | null | undefined): number | null => {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }

    if (typeof value !== "string" || !value.trim()) {
      return null;
    }

    const parts = value.split(":").map((part) => Number(part));
    if (parts.some((part) => Number.isNaN(part))) {
      return null;
    }

    if (parts.length === 3) {
      const [hours, minutes, seconds] = parts;
      return hours * 3600 + minutes * 60 + seconds;
    }

    if (parts.length === 2) {
      const [minutes, seconds] = parts;
      return minutes * 60 + seconds;
    }

    return null;
  };

  const formatDurationMinutes = (seconds: number | null | undefined): string => {
    if (typeof seconds !== "number" || Number.isNaN(seconds)) {
      return "-";
    }

    const minutes = seconds / 60;
    return `${minutes.toFixed(minutes >= 10 ? 0 : 1)} хв`;
  };

  const trainingDurationMinutes = useMemo(() => {
    const elapsedSeconds =
      status?.timing?.elapsed_seconds ??
      parseDurationSeconds(status?.session_summary?.runtime_hms) ??
      parseDurationSeconds(status?.timing?.elapsed_hms) ??
      null;

    return formatDurationMinutes(elapsedSeconds);
  }, [status]);

  const rewardValueLabel = (value: number | null | undefined, digits = 2): string => {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return "-";
    }

    return formatNumber(Math.abs(value), digits);
  };

  const getChartTitle = (chart: NonNullable<typeof fullscreenChart>): string => {
    switch (chart) {
      case "policy":
        return "Policy Loss Curve";
      case "loss":
        return "Training Loss";
      case "reward":
        return "Mean Reward per Episode";
      case "completion":
        return "Completion Rate over Time";
      case "success":
        return "Successful Generations Trend";
      default:
        return "";
    }
  };

  const formatDateTime = (value: string | number | null | undefined): string => {
    if (value === null || value === undefined || value === "") {
      return "-";
    }

    if (typeof value === "number") {
      const timestamp = value < 1_000_000_000_000 ? value * 1000 : value;
      const date = new Date(timestamp);
      return Number.isNaN(date.getTime()) ? "-" : date.toLocaleString("uk-UA");
    }

    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString("uk-UA");
  };

  const kpis = useMemo(() => {
    const lastPoint = dashboardData[dashboardData.length - 1];
    const normalizedRewards = (history?.reward_per_step || []).filter(
      (value): value is number => typeof value === "number"
    );
    const meanNormalizedReward =
      normalizedRewards.length > 0
        ? normalizedRewards.reduce((sum, reward) => sum + reward, 0) / normalizedRewards.length
        : null;
    const currentNormalizedReward =
      normalizedRewards.length > 0 ? normalizedRewards[normalizedRewards.length - 1] : null;
    const bestNormalizedReward =
      normalizedRewards.length > 0 ? Math.max(...normalizedRewards) : null;

    const episodeRewards = (history?.episode_reward || []).filter(
      (value): value is number => typeof value === "number"
    );
    const meanEpisodeReward =
      episodeRewards.length > 0
        ? episodeRewards.reduce((sum, reward) => sum + reward, 0) / episodeRewards.length
        : null;
    const currentEpisodeReward =
      episodeRewards.length > 0 ? episodeRewards[episodeRewards.length - 1] : null;
    const bestEpisodeReward = episodeRewards.length > 0 ? Math.max(...episodeRewards) : null;
    const bestHistoryReward = dashboardData.reduce<number | null>((best, point) => {
      if (typeof point.meanReward !== "number") {
        return best;
      }
      if (best === null) {
        return point.meanReward;
      }
      return Math.max(best, point.meanReward);
    }, null);

    return {
      currentEpisode:
        lastPoint?.episode ?? status?.progress?.current_iteration ?? legacy?.iterations ?? 0,
      totalEpisodes: lastPoint?.episode ?? status?.progress?.total_iterations ?? legacy?.iterations ?? 0,
      meanReward:
        meanNormalizedReward ?? currentNormalizedReward ?? meanEpisodeReward ?? currentEpisodeReward ?? lastPoint?.meanReward ?? status?.metrics?.current_reward ?? 0,
      bestReward:
        bestNormalizedReward ?? bestEpisodeReward ?? bestHistoryReward ?? status?.metrics?.best_reward ?? 0,
      hardConflicts: lastPoint?.hardConflicts ?? status?.metrics?.hard_violations ?? 0,
      successfulGenerations:
        lastPoint?.successfulGenerations ?? status?.metrics?.successful_generations ?? 0,
      successRate: lastPoint?.successRate ?? status?.metrics?.success_rate ?? 0,
      softSatisfaction: lastPoint?.softSatisfaction ?? 0,
    };
  }, [dashboardData, history, legacy, status]);

  const heatmapMax = useMemo(() => {
    if (!preview?.heatmap?.length) {
      return 1;
    }
    return Math.max(...preview.heatmap.map((cell) => cell.count), 1);
  }, [preview]);

  const hasPrimaryHistory = useMemo(() => {
    return Boolean(history?.iteration?.length);
  }, [history]);

  const recentModelVersions = useMemo(() => {
    return [...modelVersions]
      .sort((left, right) => {
        const leftTimestamp = Date.parse(String(left.updated_at ?? "")) || 0;
        const rightTimestamp = Date.parse(String(right.updated_at ?? "")) || 0;
        return rightTimestamp - leftTimestamp;
      })
      .slice(0, 3);
  }, [modelVersions]);

  const renderPolicyLossChart = (height: number) => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={policyLossChartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="episode" />
        <YAxis tickFormatter={(value: number) => formatMetricCompact(value)} />
        <Tooltip formatter={(value: number | string) => formatChartValue(value)} />
        <Legend />
        <Line type="monotone" dataKey="policyLoss" name="Policy Loss" stroke="#0d47a1" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );

  const renderLossChart = (height: number) => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={lossChartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="episode" />
        <YAxis tickFormatter={(value: number) => formatMetricCompact(value)} />
        <Tooltip formatter={(value: number | string) => formatChartValue(value)} />
        <Legend />
        <Line type="monotone" dataKey="loss" name="Training Loss" stroke="#1976d2" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );

  const renderRewardChart = (height: number) => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rewardComparisonData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="episode" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey="primaryReward"
          name={`Mean Reward • ${selectedModelVersion || "selected"}`}
          stroke="#1565c0"
          strokeWidth={2.5}
          dot={false}
        />
        {compareModelVersion && (
          <Line
            type="monotone"
            dataKey="compareReward"
            name={`Mean Reward • ${compareModelVersion}`}
            stroke="#ef6c00"
            strokeWidth={2.5}
            dot={false}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );

  const renderCompletionChart = (height: number) => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={completionComparisonData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="episode" />
        <YAxis domain={[0, 100]} />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey="primaryCompletion"
          name={`Completion • ${selectedModelVersion || "selected"}`}
          stroke="#64b5f6"
          strokeWidth={2}
          dot={false}
        />
        {compareModelVersion && (
          <Line
            type="monotone"
            dataKey="compareCompletion"
            name={`Completion • ${compareModelVersion}`}
            stroke="#ef6c00"
            strokeWidth={2}
            dot={false}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );

  const renderSuccessChart = (height: number) => (
    <ResponsiveContainer width="100%" height={height}>
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
  );

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

  if (!dashboardData.length && !preview?.available && modelVersions.length === 0) {
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

      <Paper elevation={0} sx={{ p: 2, mb: 3, border: "1px solid", borderColor: "divider" }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ xs: "stretch", md: "center" }}>
          <TextField
            select
            label="Статистика моделі"
            value={selectedModelVersion}
            onChange={(e) => setSelectedModelVersion(e.target.value)}
            size="small"
            sx={{ minWidth: 320 }}
          >
            {modelVersions.map((model) => (
              <MenuItem key={model.name} value={model.name}>
                {model.name} {model.is_active ? "(active)" : ""}
              </MenuItem>
            ))}
          </TextField>

          <TextField
            select
            label="Порівняти з"
            value={compareModelVersion}
            onChange={(e) => setCompareModelVersion(e.target.value)}
            size="small"
            sx={{ minWidth: 320 }}
          >
            <MenuItem value="">Без порівняння</MenuItem>
            {modelVersions
              .filter((model) => model.name !== selectedModelVersion)
              .map((model) => (
                <MenuItem key={model.name} value={model.name}>
                  {model.name} {model.is_active ? "(active)" : ""}
                </MenuItem>
              ))}
          </TextField>
        </Stack>

        {compareModelVersion && (
          <Alert severity="info" sx={{ mt: 2 }}>
            Порівняння активне: {selectedModelVersion} vs {compareModelVersion}
          </Alert>
        )}

        {!hasPrimaryHistory && selectedModelVersion && (
          <Alert severity="info" sx={{ mt: 2 }}>
            Для моделі {selectedModelVersion} відсутня збережена історія метрик.
          </Alert>
        )}
      </Paper>

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
              Mean Normalized Reward/Step
            </Typography>
            <Typography variant="h6">{rewardValueLabel(kpis.meanReward)}</Typography>
            <Typography variant="caption" color="text.secondary">
              Показано без від’ємного знака.
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Best Normalized Reward/Step
            </Typography>
            <Typography variant="h6" color="success.main">
              {rewardValueLabel(kpis.bestReward)}
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
              Тривалість навчання
            </Typography>
            <Typography variant="h6">{trainingDurationMinutes}</Typography>
          </Grid>
        </Grid>
      </Paper>

      <Paper elevation={0} sx={{ p: 2, mb: 3, border: "1px solid", borderColor: "divider" }}>
        <Stack spacing={1}>
          <Typography variant="subtitle1" fontWeight={700}>
            Розмірності середовища
          </Typography>
          <Typography variant="body2">
            Поточна БД: state_dim={datasetDimensions?.current_db?.state_dim ?? "-"}, action_dim=
            {datasetDimensions?.current_db?.action_dim ?? "-"}
          </Typography>
          <Typography variant="body2">
            Поточний датасет ({selectedDatasetName}): state_dim={datasetDimensions?.dataset?.state_dim ?? "-"},
            action_dim={datasetDimensions?.dataset?.action_dim ?? "-"}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            raw_action_dim БД: {datasetDimensions?.current_db?.raw_action_dim ?? "-"}; raw_action_dim датасету: {" "}
            {datasetDimensions?.dataset?.raw_action_dim ?? "-"}; sample_case: {datasetDimensions?.dataset?.sample_case || "-"}
          </Typography>
          {(datasetDimensionsError || (datasetDimensions && (!datasetDimensions.dataset.found || datasetDimensions.dataset.error))) && (
            <Alert severity="warning" sx={{ mt: 1 }}>
              {datasetDimensionsError || datasetDimensions?.dataset?.error || "Датасет не знайдено або не вдалося обчислити розмірності"}
            </Alert>
          )}
        </Stack>
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
                Training Duration
              </Typography>
              <Typography variant="subtitle1">{trainingDurationMinutes}</Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" color="text.secondary">
                Best Checkpoint
              </Typography>
              <Typography variant="subtitle2">
                {status?.session_summary?.best_checkpoint
                  ? `${status.session_summary.best_checkpoint.checkpoint_id} (reward ${status.session_summary.best_checkpoint.best_reward.toFixed(2)})`
                  : "-"}
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" color="text.secondary">
                Current Status
              </Typography>
              <Typography variant="subtitle2">{status?.status || "-"}</Typography>
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
            <Typography variant="h6">Створення та навчання моделі</Typography>
            {presetJob?.status && (
              <Chip
                size="small"
                label={`Job status: ${presetJob.status}`}
                color={presetJob.status === "completed" ? "success" : presetJob.status === "failed" ? "error" : "warning"}
              />
            )}
          </Stack>

          <Paper elevation={0} sx={{ p: 2, mb: 2, border: "1px solid", borderColor: "divider" }}>
            <Stack spacing={1.5}>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                justifyContent="space-between"
                alignItems={{ xs: "flex-start", sm: "center" }}
                spacing={1}
              >
                <Box>
                  <Typography variant="subtitle1" fontWeight={700}>
                    PPO Гіперпараметри
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Параметри впливають на новий запуск і на live update активного тренування.
                  </Typography>
                </Box>
                <Chip
                  size="small"
                  label={presetJob?.status === "running" ? "Live update доступний" : "Live update неактивний"}
                  color={presetJob?.status === "running" ? "success" : "default"}
                  variant="outlined"
                />
              </Stack>

              <Grid container spacing={2}>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Learning Rate"
                    type="number"
                    value={trainingHyperparameters.learning_rate}
                    onChange={(e) => handleHyperparameterChange("learning_rate", e.target.value)}
                    inputProps={{ step: 0.0001, min: 0.000001, max: 0.1 }}
                    disabled={presetSubmitting || hyperparameterSubmitting}
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Gamma (γ)"
                    type="number"
                    value={trainingHyperparameters.gamma}
                    onChange={(e) => handleHyperparameterChange("gamma", e.target.value)}
                    inputProps={{ step: 0.01, min: 0.9, max: 1 }}
                    disabled={presetSubmitting || hyperparameterSubmitting}
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Epsilon (ε)"
                    type="number"
                    value={trainingHyperparameters.epsilon}
                    onChange={(e) => handleHyperparameterChange("epsilon", e.target.value)}
                    inputProps={{ step: 0.01, min: 0.05, max: 0.5 }}
                    disabled={presetSubmitting || hyperparameterSubmitting}
                  />
                </Grid>
              </Grid>

              <Typography variant="caption" color="text.secondary">
                Поточні активні значення: LR={formatNumber(normalizedHyperparameters.learningRate, 6)}, Gamma=
                {formatNumber(normalizedHyperparameters.gamma, 3)}, Epsilon={formatNumber(normalizedHyperparameters.epsilon, 3)}
              </Typography>

              <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                <Button
                  variant="outlined"
                  onClick={handleApplyHyperparameters}
                  disabled={hyperparameterSubmitting || presetJob?.status !== "running"}
                >
                  {hyperparameterSubmitting ? "Applying..." : "Apply to running job"}
                </Button>
              </Stack>
            </Stack>
          </Paper>

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
                select
                fullWidth
                label="Розмір датасету"
                value={datasetSizeMode}
                onChange={(e) =>
                  setDatasetSizeMode(
                    e.target.value as "compatible_100" | "compatible_1000" | "custom"
                  )
                }
              >
                <MenuItem value="compatible_100">Compatible 100 кейсів</MenuItem>
                <MenuItem value="compatible_1000">Compatible 1000 кейсів</MenuItem>
                <MenuItem value="custom">Custom N</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} sm={4} md={3}>
              <TextField
                fullWidth
                label="Custom N"
                type="number"
                inputProps={{ min: 2, max: 10000 }}
                value={customDatasetSize}
                onChange={(e) => setCustomDatasetSize(Number(e.target.value) || 200)}
                disabled={datasetSizeMode !== "custom"}
              />
            </Grid>
            <Grid item xs={12} sm={4} md={3}>
              <TextField
                select
                fullWidth
                label="Iterations Mode"
                value={iterationsMode}
                onChange={(e) => setIterationsMode(e.target.value as "total" | "per-case")}
              >
                <MenuItem value="total">total</MenuItem>
                <MenuItem value="per-case">per-case</MenuItem>
              </TextField>
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
                select
                fullWidth
                label="Device"
                value={presetDevice}
                onChange={(e) => setPresetDevice(e.target.value)}
              >
                <MenuItem value="cpu">CPU</MenuItem>
                <MenuItem value="gpu">GPU (CUDA)</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} md={3}>
              <Stack direction="row" spacing={1}>
                <Button
                  fullWidth
                  variant="contained"
                  onClick={handleStartPreset}
                  disabled={presetSubmitting || presetJob?.status === "running"}
                >
                  {presetSubmitting ? "Starting..." : "Create & Train Model"}
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  color="error"
                  onClick={handleStopPreset}
                  disabled={presetStopping || presetJob?.status !== "running"}
                >
                  {presetStopping ? "Stopping..." : "Stop Training"}
                </Button>
              </Stack>
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

          {hyperparameterInfo && (
            <Alert severity="success" sx={{ mt: 2 }}>
              {hyperparameterInfo}
            </Alert>
          )}
          {hyperparameterError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {hyperparameterError}
            </Alert>
          )}

          {presetJob && (
            <Box mt={2}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Останній запуск тренування
              </Typography>
              {(typeof presetJob.progress_percent === "number" ||
                typeof presetJob.cases_total === "number") && (
                <Box sx={{ mb: 2 }}>
                  <Stack spacing={0.75}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2" color="text.secondary">
                        Прогрес навчання датасету
                      </Typography>
                      <Typography variant="body2" fontWeight={700}>
                        {typeof presetJob.progress_percent === "number"
                          ? `${presetJob.progress_percent.toFixed(1)}%`
                          : "-"}
                      </Typography>
                    </Stack>
                    <LinearProgress
                      variant="determinate"
                      value={Math.max(0, Math.min(100, presetJob.progress_percent ?? 0))}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {typeof presetJob.cases_done === "number" && typeof presetJob.cases_total === "number"
                        ? `Оброблено кейсів: ${presetJob.cases_done}/${presetJob.cases_total}`
                        : "Очікуємо деталізацію прогресу..."}
                      {typeof presetJob.current_case === "number"
                        ? ` • Поточний кейс: ${presetJob.current_case}`
                        : ""}
                      {typeof presetJob.remaining_cases === "number"
                        ? ` • Залишилось: ${presetJob.remaining_cases}`
                        : ""}
                    </Typography>
                  </Stack>
                </Box>
              )}

              <Grid container spacing={1}>
                <Grid item xs={12} md={4}>
                  <Typography variant="body2">Job ID: {presetJob.job_id}</Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="body2">Dataset: {presetJob.dataset_name || "-"}</Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="body2">Dataset size: {presetJob.dataset_size ?? "-"}</Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="body2">Iterations: {presetJob.iterations ?? "-"}</Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2">
                    Effective Iterations: {presetJob.effective_iterations ?? "-"}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2">Iterations Mode: {presetJob.iterations_mode || "-"}</Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2">Model version: {presetJob.model_version || "-"}</Typography>
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

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Історія моделей і навчання
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Model Versions ({recentModelVersions.length} of {modelVersions.length})
              </Typography>
              <Box sx={{ overflowX: "auto" }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Model</TableCell>
                      <TableCell>Active</TableCell>
                      <TableCell>Updated</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {recentModelVersions.map((model) => (
                      <TableRow key={model.name}>
                        <TableCell title={model.name} sx={{ maxWidth: 320, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {model.name.replace(/^actor_critic_/, "")}
                        </TableCell>
                        <TableCell>{model.is_active ? "Yes" : "No"}</TableCell>
                        <TableCell>{formatDateTime(model.updated_at)}</TableCell>
                      </TableRow>
                    ))}
                    {recentModelVersions.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={3}>Немає збережених версій</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2} mb={2}>
                <Typography variant="h6">Policy Loss Curve</Typography>
                <Button size="small" onClick={() => setFullscreenChart("policy")}>На весь екран</Button>
              </Stack>
              {renderPolicyLossChart(300)}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2} mb={2}>
                <Typography variant="h6">Training Loss</Typography>
                <Button size="small" onClick={() => setFullscreenChart("loss")}>На весь екран</Button>
              </Stack>
              {renderLossChart(300)}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2} mb={2}>
                <Typography variant="h6">Mean Reward per Episode</Typography>
                <Button size="small" onClick={() => setFullscreenChart("reward")}>На весь екран</Button>
              </Stack>
              {renderRewardChart(300)}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2} mb={2}>
                <Typography variant="h6">Completion Rate over Time</Typography>
                <Button size="small" onClick={() => setFullscreenChart("completion")}>На весь екран</Button>
              </Stack>
              {renderCompletionChart(300)}
              {!dashboardData.some((point) => typeof point.completionRate === "number") && (
                <Typography variant="caption" color="text.secondary">
                  Для цього режиму завершеність епізодів недоступна.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2} mb={2}>
                <Typography variant="h6">Successful Generations Trend</Typography>
                <Button size="small" onClick={() => setFullscreenChart("success")}>На весь екран</Button>
              </Stack>
              {renderSuccessChart(300)}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Dialog open={Boolean(fullscreenChart)} onClose={() => setFullscreenChart(null)} fullWidth maxWidth="xl">
        <DialogTitle>{fullscreenChart ? getChartTitle(fullscreenChart) : ""}</DialogTitle>
        <DialogContent dividers sx={{ height: "calc(100vh - 160px)", p: 2 }}>
          <Box sx={{ width: "100%", height: "100%" }}>
            {fullscreenChart === "policy" && renderPolicyLossChart(620)}
            {fullscreenChart === "loss" && renderLossChart(620)}
            {fullscreenChart === "reward" && renderRewardChart(620)}
            {fullscreenChart === "completion" && renderCompletionChart(620)}
            {fullscreenChart === "success" && renderSuccessChart(620)}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFullscreenChart(null)}>Закрити</Button>
        </DialogActions>
      </Dialog>

      <Grid container spacing={3}>
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

              {preview?.message && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  {preview.message}
                </Alert>
              )}

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
                                {cell.day_label}, урок {cell.period}
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
                          <TableCell>Урок</TableCell>
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
