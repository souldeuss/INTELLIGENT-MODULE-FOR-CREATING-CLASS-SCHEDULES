import React, { useState, useEffect } from "react";
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Stack,
  LinearProgress,
  IconButton,
  Button,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemSecondaryAction,
  Avatar,
  Tooltip,
  Badge,
  CircularProgress,
  Alert,
  useTheme,
} from "@mui/material";
import {
  School as SchoolIcon,
  Person as PersonIcon,
  Room as RoomIcon,
  Event as EventIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon,
  Schedule as ScheduleIcon,
  Psychology as AIIcon,
  Speed as SpeedIcon,
  Star as StarIcon,
  Refresh as RefreshIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
  PlayArrow as PlayIcon,
  Notifications as NotificationIcon,
  Assessment as AssessmentIcon,
  CalendarToday as CalendarIcon,
} from "@mui/icons-material";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { useNavigate } from "react-router-dom";
import { statsService, aiService, getSchedules } from "../services/api";
import ConflictCenter from "./ConflictCenter";
import DataGenerator from "./DataGenerator";

interface DashboardStats {
  groups_count: number;
  teachers_count: number;
  classrooms_count: number;
  courses_count: number;
  schedules_count: number;
  active_conflicts: number;
  average_score: number;
}

interface ScheduleVersion {
  id: number;
  name: string;
  created_at: string;
  score: number;
  conflicts: number;
}

interface Activity {
  id: number;
  action: string;
  description: string;
  timestamp: string;
  type: "generation" | "edit" | "conflict" | "export";
}

const CHART_COLORS = [
  "#1976d2",
  "#4caf50",
  "#ff9800",
  "#f44336",
  "#9c27b0",
  "#00bcd4",
];

const ModernDashboard: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [scheduleScore, setScheduleScore] = useState<any>(null);
  const [recentSchedules, setRecentSchedules] = useState<ScheduleVersion[]>([]);
  const [recentActivity, setRecentActivity] = useState<Activity[]>([]);
  const [trainingHistory, setTrainingHistory] = useState<any[]>([]);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [statsRes, scoreRes, schedulesRes, historyRes] = await Promise.all([
        statsService.getDashboardStats(),
        aiService.getScheduleScore(),
        getSchedules(),
        aiService.getTrainingHistory(),
      ]);

      setStats(statsRes.data);
      setScheduleScore(scoreRes.data);
      setRecentSchedules(schedulesRes.data?.slice(0, 5) || []);
      setTrainingHistory(historyRes.data?.rewards || []);
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
      // Set mock data for demo
      setStats({
        groups_count: 12,
        teachers_count: 25,
        classrooms_count: 18,
        courses_count: 45,
        schedules_count: 3,
        active_conflicts: 2,
        average_score: 87.5,
      });
      setScheduleScore({
        overall: 87.5,
        teacher_conflicts: 95,
        room_conflicts: 90,
        gap_penalty: 82,
        distribution: 85,
      });
      setTrainingHistory([
        { episode: 1, reward: -50 },
        { episode: 10, reward: -30 },
        { episode: 20, reward: -10 },
        { episode: 30, reward: 5 },
        { episode: 40, reward: 15 },
        { episode: 50, reward: 20 },
      ]);
    }
    setLoading(false);
  };

  // Stat Card Component
  const StatCard: React.FC<{
    title: string;
    value: number | string;
    icon: React.ReactNode;
    color: string;
    trend?: number;
    subtitle?: string;
  }> = ({ title, value, icon, color, trend, subtitle }) => (
    <Card sx={{ height: "100%" }}>
      <CardContent>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <Box>
            <Typography color="text.secondary" variant="body2" gutterBottom>
              {title}
            </Typography>
            <Typography variant="h4" fontWeight="bold">
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="caption" color="text.secondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          <Avatar sx={{ bgcolor: color, width: 48, height: 48 }}>{icon}</Avatar>
        </Box>
        {trend !== undefined && (
          <Box sx={{ display: "flex", alignItems: "center", mt: 1 }}>
            {trend >= 0 ? (
              <ArrowUpIcon sx={{ color: "success.main", fontSize: 16 }} />
            ) : (
              <ArrowDownIcon sx={{ color: "error.main", fontSize: 16 }} />
            )}
            <Typography
              variant="body2"
              sx={{ color: trend >= 0 ? "success.main" : "error.main" }}
            >
              {Math.abs(trend)}% від минулого
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );

  // Score Card Component
  const ScoreCard: React.FC<{ score: any }> = ({ score }) => {
    if (!score) return null;

    const metrics = [
      {
        label: "Конфлікти викладачів",
        value: score.teacher_conflicts,
        color: "#4caf50",
      },
      {
        label: "Конфлікти аудиторій",
        value: score.room_conflicts,
        color: "#2196f3",
      },
      { label: "Вікна в розкладі", value: score.gap_penalty, color: "#ff9800" },
      {
        label: "Розподіл навантаження",
        value: score.distribution,
        color: "#9c27b0",
      },
    ];

    return (
      <Card>
        <CardHeader
          title={
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <AIIcon color="primary" />
              <Typography variant="h6">Оцінка AI</Typography>
            </Box>
          }
          action={
            <Chip
              label={`${score.overall}%`}
              color={
                score.overall > 80
                  ? "success"
                  : score.overall > 60
                  ? "warning"
                  : "error"
              }
              size="medium"
              icon={<StarIcon />}
            />
          }
        />
        <CardContent>
          <Box
            sx={{
              position: "relative",
              display: "inline-flex",
              width: "100%",
              justifyContent: "center",
              mb: 3,
            }}
          >
            <CircularProgress
              variant="determinate"
              value={score.overall}
              size={120}
              thickness={4}
              sx={{
                color:
                  score.overall > 80
                    ? "success.main"
                    : score.overall > 60
                    ? "warning.main"
                    : "error.main",
              }}
            />
            <Box
              sx={{
                position: "absolute",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
              }}
            >
              <Typography variant="h4" fontWeight="bold">
                {score.overall}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                загальний бал
              </Typography>
            </Box>
          </Box>

          <Stack spacing={2}>
            {metrics.map((metric) => (
              <Box key={metric.label}>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    mb: 0.5,
                  }}
                >
                  <Typography variant="body2">{metric.label}</Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {metric.value}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={metric.value}
                  sx={{
                    height: 8,
                    borderRadius: 4,
                    bgcolor: "grey.200",
                    "& .MuiLinearProgress-bar": { bgcolor: metric.color },
                  }}
                />
              </Box>
            ))}
          </Stack>
        </CardContent>
      </Card>
    );
  };

  // Training Progress Chart
  const TrainingChart: React.FC = () => (
    <Card>
      <CardHeader
        title={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <TrendingUpIcon color="primary" />
            <Typography variant="h6">Прогрес навчання</Typography>
          </Box>
        }
        subheader="Reward по епізодах"
      />
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={trainingHistory}>
            <defs>
              <linearGradient id="colorReward" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#1976d2" stopOpacity={0.8} />
                <stop offset="95%" stopColor="#1976d2" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="episode" />
            <YAxis />
            <RechartsTooltip />
            <Area
              type="monotone"
              dataKey="reward"
              stroke="#1976d2"
              fillOpacity={1}
              fill="url(#colorReward)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );

  // Quick Actions
  const QuickActions: React.FC = () => (
    <Card>
      <CardHeader
        title={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <SpeedIcon color="primary" />
            <Typography variant="h6">Швидкі дії</Typography>
          </Box>
        }
      />
      <CardContent>
        <Grid container spacing={2}>
          <Grid item xs={6}>
            <Button
              variant="contained"
              fullWidth
              startIcon={<PlayIcon />}
              onClick={() => navigate("/timetable")}
              sx={{ py: 2 }}
            >
              До розкладу
            </Button>
          </Grid>
          <Grid item xs={6}>
            <Button
              variant="outlined"
              fullWidth
              startIcon={<CalendarIcon />}
              onClick={() => navigate("/timetable")}
              sx={{ py: 2 }}
            >
              Переглянути
            </Button>
          </Grid>
          <Grid item xs={6}>
            <Button
              variant="outlined"
              fullWidth
              startIcon={<AssessmentIcon />}
              onClick={() => navigate("/training-metrics")}
              sx={{ py: 2 }}
            >
              Аналітика
            </Button>
          </Grid>
          <Grid item xs={6}>
            <Button
              variant="outlined"
              fullWidth
              startIcon={<RefreshIcon />}
              onClick={loadDashboardData}
              sx={{ py: 2 }}
            >
              Оновити
            </Button>
          </Grid>
          <Grid item xs={12}>
            <DataGenerator compact onDataGenerated={loadDashboardData} />
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );

  // Recent Schedules
  const RecentSchedules: React.FC = () => (
    <Card>
      <CardHeader
        title={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <ScheduleIcon color="primary" />
            <Typography variant="h6">Останні розклади</Typography>
          </Box>
        }
      />
      <CardContent sx={{ p: 0 }}>
        <List>
          {recentSchedules.length === 0 ? (
            <ListItem>
              <ListItemText secondary="Немає збережених розкладів" />
            </ListItem>
          ) : (
            recentSchedules.map((schedule, idx) => (
              <ListItem
                key={schedule.id || idx}
                divider={idx < recentSchedules.length - 1}
              >
                <ListItemIcon>
                  <Badge badgeContent={schedule.conflicts || 0} color="error">
                    <EventIcon color="primary" />
                  </Badge>
                </ListItemIcon>
                <ListItemText
                  primary={schedule.name || `Розклад #${schedule.id}`}
                  secondary={schedule.created_at || "Сьогодні"}
                />
                <ListItemSecondaryAction>
                  <Chip
                    size="small"
                    label={`${schedule.score || 85}%`}
                    color={schedule.score > 80 ? "success" : "warning"}
                  />
                </ListItemSecondaryAction>
              </ListItem>
            ))
          )}
        </List>
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, bgcolor: "grey.50", minHeight: "100vh" }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          🎓 Інтелектуальна система розкладу
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Автоматичне складання розкладу занять на основі Deep Reinforcement
          Learning
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {/* Stats Row */}
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Групи"
            value={stats?.groups_count || 0}
            icon={<SchoolIcon />}
            color="#1976d2"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Викладачі"
            value={stats?.teachers_count || 0}
            icon={<PersonIcon />}
            color="#4caf50"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Аудиторії"
            value={stats?.classrooms_count || 0}
            icon={<RoomIcon />}
            color="#ff9800"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Конфлікти"
            value={stats?.active_conflicts || 0}
            icon={<WarningIcon />}
            color={stats?.active_conflicts === 0 ? "#4caf50" : "#f44336"}
            subtitle={
              stats?.active_conflicts === 0 ? "Все добре!" : "Потребує уваги"
            }
          />
        </Grid>

        {/* Main Content */}
        <Grid item xs={12} md={8}>
          <Grid container spacing={3}>
            {/* AI Score */}
            <Grid item xs={12} md={6}>
              <ScoreCard score={scheduleScore} />
            </Grid>

            {/* Quick Actions */}
            <Grid item xs={12} md={6}>
              <QuickActions />
            </Grid>

            {/* Training Chart */}
            <Grid item xs={12}>
              <TrainingChart />
            </Grid>

            {/* Conflict Center Preview */}
            <Grid item xs={12}>
              <ConflictCenter compact />
            </Grid>
          </Grid>
        </Grid>

        {/* Sidebar */}
        <Grid item xs={12} md={4}>
          <Stack spacing={3}>
            <Alert severity="info">
              Генерацію розкладу перенесено на сторінку "Розклад", а запуск навчання моделі доступний у вкладці "Створення і навчання моделі".
            </Alert>

            {/* Recent Schedules */}
            <RecentSchedules />
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
};

export default ModernDashboard;
