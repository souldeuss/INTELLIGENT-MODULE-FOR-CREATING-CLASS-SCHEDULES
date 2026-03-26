import React, { useState, useEffect } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  Alert,
  Paper,
} from "@mui/material";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import axios from "axios";

interface TrainingMetrics {
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

const TrainingMetrics: React.FC = () => {
  const [metrics, setMetrics] = useState<TrainingMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMetrics();
  }, []);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        "http://localhost:8000/api/schedule/training-metrics"
      );
      setMetrics(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load training metrics");
    } finally {
      setLoading(false);
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

  if (error) {
    return (
      <Box p={3}>
        <Alert severity="warning">{error}</Alert>
      </Box>
    );
  }

  if (!metrics) {
    return (
      <Box p={3}>
        <Alert severity="info">No training metrics available</Alert>
      </Box>
    );
  }

  // Prepare data for charts
  const epochs = Array.from(
    { length: metrics.metrics.rewards.length },
    (_, i) => i + 1
  );

  const rewardsData = epochs.map((epoch, idx) => ({
    epoch,
    reward: metrics.metrics.rewards[idx],
  }));

  const violationsData = epochs.map((epoch, idx) => ({
    epoch,
    hardViolations: metrics.metrics.hard_violations[idx],
    softViolations: metrics.metrics.soft_violations[idx],
  }));

  const completionData = epochs.map((epoch, idx) => ({
    epoch,
    completionRate: (metrics.metrics.completion_rates[idx] * 100).toFixed(1),
  }));

  const lossesData = epochs.map((epoch, idx) => ({
    epoch,
    actorLoss: metrics.metrics.actor_losses[idx],
    criticLoss: metrics.metrics.critic_losses[idx],
  }));

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        📊 Метрики навчання нейромережі
      </Typography>

      <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="textSecondary">
              Дата навчання
            </Typography>
            <Typography variant="h6">
              {new Date(metrics.timestamp).toLocaleString("uk-UA")}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="textSecondary">
              Кількість епох
            </Typography>
            <Typography variant="h6">{metrics.iterations}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="textSecondary">
              Фінальна винагорода
            </Typography>
            <Typography
              variant="h6"
              color={
                metrics.metrics.rewards[metrics.metrics.rewards.length - 1] > 0
                  ? "success.main"
                  : "error.main"
              }
            >
              {metrics.metrics.rewards[
                metrics.metrics.rewards.length - 1
              ].toFixed(2)}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="body2" color="textSecondary">
              Завершеність розкладу
            </Typography>
            <Typography variant="h6">
              {(
                metrics.metrics.completion_rates[
                  metrics.metrics.completion_rates.length - 1
                ] * 100
              ).toFixed(1)}
              %
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      <Grid container spacing={3}>
        {/* Rewards Chart */}
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                🎯 Винагороди за епохами
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={rewardsData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="epoch"
                    label={{
                      value: "Епоха",
                      position: "insideBottom",
                      offset: -5,
                    }}
                  />
                  <YAxis
                    label={{
                      value: "Винагорода",
                      angle: -90,
                      position: "insideLeft",
                    }}
                  />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="reward" name="Винагорода" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Violations Chart */}
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                ⚠️ Порушення обмежень за епохами
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={violationsData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="epoch"
                    label={{
                      value: "Епоха",
                      position: "insideBottom",
                      offset: -5,
                    }}
                  />
                  <YAxis
                    label={{
                      value: "Кількість порушень",
                      angle: -90,
                      position: "insideLeft",
                    }}
                  />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="hardViolations"
                    name="Жорсткі порушення"
                    stroke="#ff4444"
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="softViolations"
                    name="М'які порушення"
                    stroke="#ff9800"
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Completion Rate Chart */}
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                ✅ Завершеність розкладу за епохами
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={completionData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="epoch"
                    label={{
                      value: "Епоха",
                      position: "insideBottom",
                      offset: -5,
                    }}
                  />
                  <YAxis
                    label={{
                      value: "Завершеність (%)",
                      angle: -90,
                      position: "insideLeft",
                    }}
                    domain={[0, 100]}
                  />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="completionRate"
                    name="Завершеність"
                    stroke="#4caf50"
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Losses Chart */}
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                📉 Втрати моделі за епохами
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={lossesData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="epoch"
                    label={{
                      value: "Епоха",
                      position: "insideBottom",
                      offset: -5,
                    }}
                  />
                  <YAxis
                    label={{
                      value: "Втрати",
                      angle: -90,
                      position: "insideLeft",
                    }}
                  />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="actorLoss"
                    name="Втрати Actor"
                    stroke="#9c27b0"
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="criticLoss"
                    name="Втрати Critic"
                    stroke="#2196f3"
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default TrainingMetrics;
