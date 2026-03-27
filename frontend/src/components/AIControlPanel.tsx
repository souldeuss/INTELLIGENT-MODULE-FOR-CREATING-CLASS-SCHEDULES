import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Box,
  Paper,
  Typography,
  Button,
  Slider,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
  Chip,
  Alert,
  IconButton,
  Tooltip,
  Grid,
  Card,
  CardContent,
  Divider,
  TextField,
  Stack,
  CircularProgress,
} from "@mui/material";
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  ExpandMore as ExpandMoreIcon,
  Psychology as AIIcon,
  Speed as SpeedIcon,
  Tune as TuneIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  Save as SaveIcon,
  DeleteForever as DeleteForeverIcon,
  Timeline as TimelineIcon,
} from "@mui/icons-material";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";
import { useNavigate } from "react-router-dom";
import {
  generateSchedule,
  getGenerationStatus,
  stopGeneration,
  clearSchedule,
  GenerationParams,
} from "../services/api";

interface TrainingMetrics {
  iteration: number;
  reward: number;
  hardViolations: number;
  softViolations: number;
}

interface AIControlPanelProps {
  onGenerationComplete?: () => void;
  compact?: boolean;
}

const AIControlPanel: React.FC<AIControlPanelProps> = ({
  onGenerationComplete,
  compact = false,
}) => {
  const navigate = useNavigate();
  const pollIntervalRef = useRef<number | null>(null);
  const ACTIVE_GENERATION_STORAGE_KEY = "aiControlActiveGenerationId";

  // Generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationId, setGenerationId] = useState<number | null>(null);
  const [status, setStatus] = useState<
    "idle" | "running" | "completed" | "failed" | "stopped"
  >("idle");
  const [progress, setProgress] = useState(0);
  const [currentIteration, setCurrentIteration] = useState(0);

  // Parameters
  const [iterations, setIterations] = useState(100);
  const [preserveLocked, setPreserveLocked] = useState(true);
  const [useExisting, setUseExisting] = useState(false);

  // PPO Hyperparameters
  const [learningRate, setLearningRate] = useState(0.0003);
  const [gamma, setGamma] = useState(0.99);
  const [epsilon, setEpsilon] = useState(0.2);
  const [batchSize, setBatchSize] = useState(64);

  // Constraint weights
  const [constraintWeights, setConstraintWeights] = useState({
    teacher_conflict: 10,
    room_conflict: 10,
    group_conflict: 10,
    capacity: 5,
    preferences: 2,
  });

  // Metrics
  const [metrics, setMetrics] = useState<TrainingMetrics[]>([]);
  const [bestReward, setBestReward] = useState<number | null>(null);
  const [estimatedTime, setEstimatedTime] = useState<string>("");
  const [clearingSchedule, setClearingSchedule] = useState(false);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      window.clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const persistGenerationId = useCallback(
    (id: number) => {
      localStorage.setItem(ACTIVE_GENERATION_STORAGE_KEY, String(id));
    },
    [ACTIVE_GENERATION_STORAGE_KEY]
  );

  const clearPersistedGenerationId = useCallback(() => {
    localStorage.removeItem(ACTIVE_GENERATION_STORAGE_KEY);
  }, [ACTIVE_GENERATION_STORAGE_KEY]);

  const applyTerminalStatus = useCallback(
    (nextStatus: "completed" | "failed" | "stopped") => {
      setStatus(nextStatus);
      setIsGenerating(false);
      setGenerationId(null);
      stopPolling();
      clearPersistedGenerationId();

      if (nextStatus === "completed") {
        onGenerationComplete?.();
      }
    },
    [clearPersistedGenerationId, onGenerationComplete, stopPolling]
  );

  const syncGenerationStatus = useCallback(
    async (id: number) => {
      try {
        const response = await getGenerationStatus(id);
        const data = response.data;

        const totalIterations =
          typeof data.iterations === "number" && data.iterations > 0
            ? data.iterations
            : iterations;
        const currentIter =
          typeof data.current_iteration === "number" ? data.current_iteration : 0;

        setGenerationId(id);
        setCurrentIteration(currentIter);
        setProgress(
          totalIterations > 0 ? (currentIter / totalIterations) * 100 : 0
        );

        if (Array.isArray(data.reward_history)) {
          setMetrics(
            data.reward_history.map((r: number, i: number) => ({
              iteration: i + 1,
              reward: r,
              hardViolations:
                typeof data.hard_violations === "number" ? data.hard_violations : 0,
              softViolations:
                typeof data.soft_violations === "number" ? data.soft_violations : 0,
            }))
          );
        }

        if (typeof data.best_reward === "number") {
          setBestReward(data.best_reward);
        }

        if (data.status === "completed") {
          applyTerminalStatus("completed");
          return "completed" as const;
        }
        if (data.status === "failed") {
          applyTerminalStatus("failed");
          return "failed" as const;
        }
        if (data.status === "stopped") {
          applyTerminalStatus("stopped");
          return "stopped" as const;
        }

        setStatus("running");
        setIsGenerating(true);
        persistGenerationId(id);
        return "running" as const;
      } catch (error: any) {
        if (error?.response?.status === 404) {
          clearPersistedGenerationId();
          setGenerationId(null);
          setIsGenerating(false);
          setStatus("idle");
          stopPolling();
          return "missing" as const;
        }

        console.error("Status sync failed:", error);
        applyTerminalStatus("failed");
        return "failed" as const;
      }
    },
    [
      applyTerminalStatus,
      clearPersistedGenerationId,
      iterations,
      persistGenerationId,
      stopPolling,
    ]
  );

  const startPolling = useCallback(
    (id: number) => {
      stopPolling();

      pollIntervalRef.current = window.setInterval(() => {
        void syncGenerationStatus(id);
      }, 1000);

      void syncGenerationStatus(id);
    },
    [stopPolling, syncGenerationStatus]
  );

  // Clear current schedule
  const handleClearSchedule = async () => {
    if (
      window.confirm(
        "Ви впевнені, що хочете видалити поточний розклад? Цю дію неможливо скасувати!"
      )
    ) {
      try {
        setClearingSchedule(true);
        await clearSchedule();
        setStatus("idle");
        setProgress(0);
        setCurrentIteration(0);
        setGenerationId(null);
        stopPolling();
        clearPersistedGenerationId();
        setMetrics([]);
        setBestReward(null);
        onGenerationComplete?.();
      } catch (error) {
        console.error("Clear schedule failed:", error);
      } finally {
        setClearingSchedule(false);
      }
    }
  };

  // Start generation
  const handleStart = async () => {
    const persistedIdRaw = localStorage.getItem(ACTIVE_GENERATION_STORAGE_KEY);
    const persistedId = persistedIdRaw ? Number(persistedIdRaw) : null;

    if (persistedId && Number.isFinite(persistedId) && persistedId > 0) {
      const existingStatus = await syncGenerationStatus(persistedId);
      if (existingStatus === "running") {
        startPolling(persistedId);
        return;
      }
    }

    setIsGenerating(true);
    setStatus("running");
    setProgress(0);
    setCurrentIteration(0);
    setMetrics([]);
    setBestReward(null);

    try {
      const params: GenerationParams = {
        iterations,
        preserve_locked: preserveLocked,
        use_existing: useExisting,
        learning_rate: learningRate,
        gamma,
        epsilon,
        batch_size: batchSize,
        constraint_weights: constraintWeights,
      };

      const response = await generateSchedule(params);
      const startedId = response.data.id;
      setGenerationId(startedId);
      persistGenerationId(startedId);
      startPolling(startedId);

      // Estimate time
      const estimatedSeconds = iterations * 0.3; // ~0.3s per iteration
      setEstimatedTime(formatTime(estimatedSeconds));
    } catch (error) {
      console.error("Generation failed:", error);
      applyTerminalStatus("failed");
    }
  };

  // Stop generation
  const handleStop = async () => {
    if (generationId) {
      try {
        await stopGeneration(generationId);
        applyTerminalStatus("stopped");
      } catch (error) {
        console.error("Stop failed:", error);
      }
    }
  };

  useEffect(() => {
    const persistedIdRaw = localStorage.getItem(ACTIVE_GENERATION_STORAGE_KEY);
    const persistedId = persistedIdRaw ? Number(persistedIdRaw) : null;

    if (persistedId && Number.isFinite(persistedId) && persistedId > 0) {
      setGenerationId(persistedId);
      setStatus("running");
      setIsGenerating(true);
      startPolling(persistedId);
    }

    return () => {
      stopPolling();
    };
  }, [ACTIVE_GENERATION_STORAGE_KEY, startPolling, stopPolling]);

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `~${Math.round(seconds)}с`;
    if (seconds < 3600) return `~${Math.round(seconds / 60)}хв`;
    return `~${(seconds / 3600).toFixed(1)}год`;
  };

  const getStatusColor = () => {
    switch (status) {
      case "running":
        return "primary";
      case "completed":
        return "success";
      case "failed":
        return "error";
      case "stopped":
        return "warning";
      default:
        return "default";
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case "running":
        return <CircularProgress size={16} />;
      case "completed":
        return <CheckIcon />;
      case "failed":
        return <ErrorIcon />;
      default:
        return <InfoIcon />;
    }
  };

  // Compact version for sidebar
  if (compact) {
    return (
      <Paper sx={{ p: 2 }}>
        <Stack spacing={2}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <AIIcon color="primary" />
            <Typography variant="subtitle1" fontWeight="bold">
              AI Generator
            </Typography>
            <Chip
              size="small"
              label={status}
              color={getStatusColor() as any}
              icon={getStatusIcon()}
            />
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Ітерації: {iterations}
            </Typography>
            <Slider
              value={iterations}
              onChange={(_, v) => setIterations(v as number)}
              min={10}
              max={1000}
              step={10}
              disabled={isGenerating}
              size="small"
            />
          </Box>

          {isGenerating && (
            <Box>
              <LinearProgress variant="determinate" value={progress} />
              <Typography variant="caption" color="text.secondary">
                {currentIteration} / {iterations} ({progress.toFixed(0)}%)
              </Typography>
            </Box>
          )}

          <Button
            variant="contained"
            color={isGenerating ? "error" : "primary"}
            startIcon={isGenerating ? <StopIcon /> : <PlayIcon />}
            onClick={isGenerating ? handleStop : handleStart}
            fullWidth
          >
            {isGenerating ? "Зупинити" : "Генерувати"}
          </Button>
        </Stack>
      </Paper>
    );
  }

  // Full panel
  return (
    <Box sx={{ p: 3 }}>
      <Paper sx={{ p: 3 }}>
        {/* Header */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            mb: 3,
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <AIIcon sx={{ fontSize: 40 }} color="primary" />
            <Box>
              <Typography variant="h5" fontWeight="bold">
                AI Control Center
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Deep Reinforcement Learning (PPO) Schedule Generator
              </Typography>
            </Box>
          </Box>
          <Chip
            label={status.toUpperCase()}
            color={getStatusColor() as any}
            icon={getStatusIcon()}
            size="medium"
          />
        </Box>

        <Divider sx={{ mb: 3 }} />

        <Grid container spacing={3}>
          {/* Left column - Controls */}
          <Grid item xs={12} md={6}>
            {/* Basic Settings */}
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography
                  variant="h6"
                  gutterBottom
                  sx={{ display: "flex", alignItems: "center", gap: 1 }}
                >
                  <SpeedIcon /> Основні налаштування
                </Typography>

                <Box sx={{ mb: 3 }}>
                  <Typography gutterBottom>
                    Кількість ітерацій: <strong>{iterations}</strong>
                  </Typography>
                  <Slider
                    value={iterations}
                    onChange={(_, v) => setIterations(v as number)}
                    min={10}
                    max={1000}
                    step={10}
                    marks={[
                      { value: 100, label: "100" },
                      { value: 500, label: "500" },
                      { value: 1000, label: "1000" },
                    ]}
                    disabled={isGenerating}
                  />
                  <Typography variant="caption" color="text.secondary">
                    Приблизний час: {formatTime(iterations * 0.3)}
                  </Typography>
                </Box>

                <Stack spacing={1}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={preserveLocked}
                        onChange={(e) => setPreserveLocked(e.target.checked)}
                        disabled={isGenerating}
                      />
                    }
                    label="Зберігати заблоковані заняття"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={useExisting}
                        onChange={(e) => setUseExisting(e.target.checked)}
                        disabled={isGenerating}
                      />
                    }
                    label="Використовувати існуючий розклад як базу"
                  />
                </Stack>
              </CardContent>
            </Card>

            {/* PPO Hyperparameters */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography
                  sx={{ display: "flex", alignItems: "center", gap: 1 }}
                >
                  <TuneIcon /> PPO Гіперпараметри
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <TextField
                      label="Learning Rate"
                      type="number"
                      value={learningRate}
                      onChange={(e) =>
                        setLearningRate(parseFloat(e.target.value))
                      }
                      size="small"
                      fullWidth
                      disabled={isGenerating}
                      inputProps={{ step: 0.0001, min: 0.0001, max: 0.01 }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      label="Gamma (γ)"
                      type="number"
                      value={gamma}
                      onChange={(e) => setGamma(parseFloat(e.target.value))}
                      size="small"
                      fullWidth
                      disabled={isGenerating}
                      inputProps={{ step: 0.01, min: 0.9, max: 0.999 }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      label="Epsilon (ε)"
                      type="number"
                      value={epsilon}
                      onChange={(e) => setEpsilon(parseFloat(e.target.value))}
                      size="small"
                      fullWidth
                      disabled={isGenerating}
                      inputProps={{ step: 0.05, min: 0.1, max: 0.4 }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      label="Batch Size"
                      type="number"
                      value={batchSize}
                      onChange={(e) => setBatchSize(parseInt(e.target.value))}
                      size="small"
                      fullWidth
                      disabled={isGenerating}
                      inputProps={{ step: 16, min: 16, max: 256 }}
                    />
                  </Grid>
                </Grid>
              </AccordionDetails>
            </Accordion>

            {/* Constraint Weights */}
            <Accordion sx={{ mt: 1 }}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography>⚖️ Ваги обмежень</Typography>
              </AccordionSummary>
              <AccordionDetails>
                {Object.entries(constraintWeights).map(([key, value]) => (
                  <Box key={key} sx={{ mb: 2 }}>
                    <Typography variant="body2" gutterBottom>
                      {key.replace(/_/g, " ")}: {value}
                    </Typography>
                    <Slider
                      value={value}
                      onChange={(_, v) =>
                        setConstraintWeights((prev) => ({
                          ...prev,
                          [key]: v as number,
                        }))
                      }
                      min={0}
                      max={20}
                      step={1}
                      disabled={isGenerating}
                      size="small"
                    />
                  </Box>
                ))}
              </AccordionDetails>
            </Accordion>

            {/* Action Buttons */}
            <Box sx={{ mt: 3, display: "flex", gap: 2, flexWrap: "wrap" }}>
              <Button
                variant="contained"
                color={isGenerating ? "error" : "primary"}
                size="large"
                startIcon={isGenerating ? <StopIcon /> : <PlayIcon />}
                onClick={isGenerating ? handleStop : handleStart}
                sx={{ flex: 2, minWidth: "200px" }}
              >
                {isGenerating ? "Зупинити генерацію" : "Запустити генерацію"}
              </Button>
              <Button
                variant="outlined"
                color="error"
                size="large"
                startIcon={
                  clearingSchedule ? (
                    <CircularProgress size={20} />
                  ) : (
                    <DeleteForeverIcon />
                  )
                }
                onClick={handleClearSchedule}
                disabled={isGenerating || clearingSchedule}
                sx={{ flex: 1, minWidth: "180px" }}
              >
                {clearingSchedule ? "Очищення..." : "Очистити розклад"}
              </Button>
              <Button
                variant="outlined"
                color="info"
                size="large"
                startIcon={<TimelineIcon />}
                onClick={() => navigate("/training-metrics")}
                disabled={isGenerating}
                sx={{ flex: 1, minWidth: "180px" }}
              >
                Метрики навчання
              </Button>
            </Box>
          </Grid>

          {/* Right column - Metrics */}
          <Grid item xs={12} md={6}>
            {/* Progress Card */}
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  📊 Прогрес навчання
                </Typography>

                {isGenerating && (
                  <>
                    <LinearProgress
                      variant="determinate"
                      value={progress}
                      sx={{ height: 10, borderRadius: 5, mb: 1 }}
                    />
                    <Box
                      sx={{ display: "flex", justifyContent: "space-between" }}
                    >
                      <Typography variant="body2">
                        Ітерація: {currentIteration} / {iterations}
                      </Typography>
                      <Typography variant="body2">
                        {progress.toFixed(1)}%
                      </Typography>
                    </Box>
                  </>
                )}

                {bestReward !== null && (
                  <Alert severity="info" sx={{ mt: 2 }}>
                    Найкраща винагорода:{" "}
                    <strong>{bestReward.toFixed(2)}</strong>
                  </Alert>
                )}

                {status === "completed" && (
                  <Alert severity="success" sx={{ mt: 2 }}>
                    ✅ Генерацію завершено успішно!
                  </Alert>
                )}

                {status === "failed" && (
                  <Alert severity="error" sx={{ mt: 2 }}>
                    ❌ Помилка генерації
                  </Alert>
                )}
              </CardContent>
            </Card>

            {/* Reward Chart */}
            {metrics.length > 0 && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📈 Динаміка Reward
                  </Typography>
                  <ResponsiveContainer width="100%" height={250}>
                    <AreaChart data={metrics}>
                      <defs>
                        <linearGradient
                          id="colorReward"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="5%"
                            stopColor="#8884d8"
                            stopOpacity={0.8}
                          />
                          <stop
                            offset="95%"
                            stopColor="#8884d8"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="iteration" />
                      <YAxis />
                      <RechartsTooltip />
                      <Area
                        type="monotone"
                        dataKey="reward"
                        stroke="#8884d8"
                        fillOpacity={1}
                        fill="url(#colorReward)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            )}
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default AIControlPanel;
