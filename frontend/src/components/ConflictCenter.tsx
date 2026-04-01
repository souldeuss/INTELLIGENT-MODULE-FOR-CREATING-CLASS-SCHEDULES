import React, { useState, useEffect, useCallback } from "react";
import {
  Box,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  Badge,
  Collapse,
  Alert,
  Button,
  Tooltip,
  Divider,
  Card,
  CardContent,
  Stack,
  LinearProgress,
} from "@mui/material";
import {
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  CheckCircle as CheckIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Refresh as RefreshIcon,
  Visibility as ViewIcon,
  AutoFixHigh as FixIcon,
  Group as GroupIcon,
  Person as PersonIcon,
  Room as RoomIcon,
  Schedule as ScheduleIcon,
  Delete as DeleteIcon,
} from "@mui/icons-material";
import {
  checkConflicts,
  getSuggestions,
  aiService,
  deleteScheduledClass,
} from "../services/api";

interface Suggestion {
  text: string;
  type: "move_timeslot" | "change_room" | "change_teacher";
  target_id?: number;
}

interface Conflict {
  id: string;
  type: "hard" | "soft";
  category: "teacher" | "room" | "group" | "capacity" | "preference";
  message: string;
  details: {
    class_id?: number;
    timeslot?: string;
    affected_items?: string[];
  };
  suggestions?: string[];
  structured_suggestions?: Suggestion[];
}

interface ConflictCenterProps {
  onNavigateToConflict?: (classId: number) => void;
  autoRefresh?: boolean;
  refreshInterval?: number;
  compact?: boolean;
  onConflictResolved?: () => void;
}

const ConflictCenter: React.FC<ConflictCenterProps> = ({
  onNavigateToConflict,
  autoRefresh = true,
  refreshInterval = 5000,
  compact = false,
  onConflictResolved,
}) => {
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "info";
  }>({ open: false, message: "", severity: "info" });
  const [loading, setLoading] = useState(false);
  const [expandedConflict, setExpandedConflict] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadConflicts = useCallback(async () => {
    setLoading(true);
    try {
      const response = await checkConflicts();
      setConflicts(response.data || []);
    } catch (error: any) {
      console.error("Failed to load conflicts:", error);
      setSnackbar({
        open: true,
        message:
          error.response?.data?.detail || "Помилка завантаження конфліктів",
        severity: "error",
      });
      setConflicts([]);
    } finally {
      setLoading(false);
      setLastUpdated(new Date());
    }
  }, []);

  useEffect(() => {
    loadConflicts();

    if (autoRefresh) {
      const interval = setInterval(loadConflicts, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [loadConflicts, autoRefresh, refreshInterval]);

  const hardConflicts = conflicts.filter((c) => c.type === "hard");
  const softConflicts = conflicts.filter((c) => c.type === "soft");

  const handleApplySuggestion = async (
    conflict: Conflict,
    suggestionIdx: number,
    suggestionText: string
  ) => {
    if (!conflict.details?.class_id) {
      setSnackbar({
        open: true,
        message: "Неможливо застосувати: не знайдено ID заняття",
        severity: "error",
      });
      return;
    }

    setApplyingId(`${conflict.id}-${suggestionIdx}`);

    try {
      // Спробуємо знайти доступні варіанти
      const availableSlots = await aiService.getAvailableSlots(
        conflict.details.class_id
      );

      if (
        availableSlots.data.available_slots &&
        availableSlots.data.available_slots.length > 0
      ) {
        // Візьмемо перший доступний слот
        const targetSlot = availableSlots.data.available_slots[0];
        await aiService.applySuggestion(
          conflict.details.class_id,
          "move_timeslot",
          targetSlot.id
        );

        setSnackbar({
          open: true,
          message: `Заняття переміщено на ${targetSlot.day_name}, ${targetSlot.period_number} урок`,
          severity: "success",
        });

        // Оновити конфлікти та сповістити батьківський компонент
        loadConflicts();
        onConflictResolved?.();
      } else {
        // Спробуємо змінити аудиторію
        const availableRooms = await aiService.getAvailableRooms(
          conflict.details.class_id
        );

        if (
          availableRooms.data.available_rooms &&
          availableRooms.data.available_rooms.length > 0
        ) {
          const targetRoom = availableRooms.data.available_rooms[0];
          await aiService.applySuggestion(
            conflict.details.class_id,
            "change_room",
            targetRoom.id
          );

          setSnackbar({
            open: true,
            message: `Аудиторію змінено на ${targetRoom.code}`,
            severity: "success",
          });

          loadConflicts();
          onConflictResolved?.();
        } else {
          setSnackbar({
            open: true,
            message:
              "Не знайдено вільних варіантів для автоматичного виправлення",
            severity: "info",
          });
        }
      }
    } catch (error: any) {
      setSnackbar({
        open: true,
        message:
          error.response?.data?.detail || "Помилка застосування рекомендації",
        severity: "error",
      });
    } finally {
      setApplyingId(null);
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "teacher":
        return <PersonIcon />;
      case "room":
        return <RoomIcon />;
      case "group":
        return <GroupIcon />;
      case "capacity":
        return <WarningIcon />;
      default:
        return <InfoIcon />;
    }
  };

  const getConflictColor = (type: string) => {
    return type === "hard" ? "error" : "warning";
  };

  const handleToggleExpand = (id: string) => {
    setExpandedConflict(expandedConflict === id ? null : id);
  };

  const handleDeleteClass = async (classId: number) => {
    if (!window.confirm("Ви впевнені, що хочете видалити це заняття?")) {
      return;
    }

    setDeletingId(classId);
    try {
      await deleteScheduledClass(classId);
      setSnackbar({
        open: true,
        message: "Заняття видалено",
        severity: "success",
      });
      loadConflicts();
      onConflictResolved?.();
    } catch (error: any) {
      setSnackbar({
        open: true,
        message: error.response?.data?.detail || "Помилка видалення",
        severity: "error",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const ConflictItem: React.FC<{ conflict: Conflict }> = ({ conflict }) => (
    <Box sx={{ mb: 1 }}>
      <ListItem
        sx={{
          bgcolor: conflict.type === "hard" ? "error.50" : "warning.50",
          borderRadius: 1,
          border: 1,
          borderColor: conflict.type === "hard" ? "error.200" : "warning.200",
        }}
        secondaryAction={
          <Stack direction="row" spacing={1}>
            {conflict.details.class_id && (
              <>
                <Tooltip title="Видалити заняття">
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() =>
                      handleDeleteClass(conflict.details.class_id!)
                    }
                    disabled={deletingId === conflict.details.class_id}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Перейти до заняття">
                  <IconButton
                    size="small"
                    onClick={() =>
                      onNavigateToConflict?.(conflict.details.class_id!)
                    }
                  >
                    <ViewIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </>
            )}
            <IconButton
              size="small"
              onClick={() => handleToggleExpand(conflict.id)}
            >
              {expandedConflict === conflict.id ? (
                <ExpandLessIcon />
              ) : (
                <ExpandMoreIcon />
              )}
            </IconButton>
          </Stack>
        }
      >
        <ListItemIcon>
          <Badge
            badgeContent={conflict.type === "hard" ? "!" : ""}
            color="error"
          >
            {getCategoryIcon(conflict.category)}
          </Badge>
        </ListItemIcon>
        <ListItemText
          primary={
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Chip
                size="small"
                label={conflict.type === "hard" ? "Жорсткий" : "М'який"}
                color={getConflictColor(conflict.type) as any}
              />
              <Typography variant="body2" fontWeight="medium">
                {conflict.message}
              </Typography>
            </Box>
          }
          secondary={conflict.details.timeslot}
        />
      </ListItem>

      <Collapse in={expandedConflict === conflict.id}>
        <Paper sx={{ ml: 7, mr: 2, mt: 1, p: 2, bgcolor: "grey.50" }}>
          {conflict.details.affected_items && (
            <Box sx={{ mb: 2 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                Зачеплені елементи:
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                {conflict.details.affected_items.map((item, idx) => (
                  <Chip
                    key={idx}
                    label={item}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Stack>
            </Box>
          )}

          {conflict.suggestions && conflict.suggestions.length > 0 && (
            <Box>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                💡 AI Рекомендації:
              </Typography>
              <List dense>
                {conflict.suggestions.map((suggestion, idx) => (
                  <ListItem key={idx} sx={{ py: 0.5 }}>
                    <ListItemIcon sx={{ minWidth: 32 }}>
                      <FixIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={suggestion}
                      primaryTypographyProps={{ variant: "body2" }}
                    />
                    <Button
                      size="small"
                      variant="outlined"
                      disabled={applyingId === `${conflict.id}-${idx}`}
                      onClick={() =>
                        handleApplySuggestion(conflict, idx, suggestion)
                      }
                    >
                      {applyingId === `${conflict.id}-${idx}`
                        ? "Застосування..."
                        : "Застосувати"}
                    </Button>
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </Paper>
      </Collapse>
    </Box>
  );

  return (
    <Paper sx={{ p: compact ? 1.5 : 2, height: "100%" }}>
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          mb: compact ? 1 : 2,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <WarningIcon
            color="warning"
            fontSize={compact ? "small" : "medium"}
          />
          <Typography variant={compact ? "subtitle1" : "h6"} fontWeight="bold">
            Conflict Center
          </Typography>
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          {!compact && (
            <Typography variant="caption" color="text.secondary">
              Оновлено: {lastUpdated.toLocaleTimeString()}
            </Typography>
          )}
          <IconButton size="small" onClick={loadConflicts} disabled={loading}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      {loading && <LinearProgress sx={{ mb: compact ? 1 : 2 }} />}

      {/* Summary */}
      <Stack
        direction="row"
        spacing={compact ? 1 : 2}
        sx={{ mb: compact ? 1 : 2 }}
      >
        <Card
          sx={{
            flex: 1,
            bgcolor: hardConflicts.length > 0 ? "error.50" : "success.50",
          }}
        >
          <CardContent
            sx={{
              py: compact ? 0.5 : 1,
              "&:last-child": { pb: compact ? 0.5 : 1 },
            }}
          >
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <Typography variant="body2" color="text.secondary">
                Жорсткі
              </Typography>
              <Chip
                size="small"
                label={hardConflicts.length}
                color={hardConflicts.length > 0 ? "error" : "success"}
                icon={hardConflicts.length > 0 ? <ErrorIcon /> : <CheckIcon />}
              />
            </Box>
          </CardContent>
        </Card>
        <Card
          sx={{
            flex: 1,
            bgcolor: softConflicts.length > 0 ? "warning.50" : "success.50",
          }}
        >
          <CardContent
            sx={{
              py: compact ? 0.5 : 1,
              "&:last-child": { pb: compact ? 0.5 : 1 },
            }}
          >
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <Typography variant="body2" color="text.secondary">
                М'які
              </Typography>
              <Chip
                size="small"
                label={softConflicts.length}
                color={softConflicts.length > 0 ? "warning" : "success"}
                icon={
                  softConflicts.length > 0 ? <WarningIcon /> : <CheckIcon />
                }
              />
            </Box>
          </CardContent>
        </Card>
      </Stack>

      {/* Status Alert */}
      {hardConflicts.length === 0 && softConflicts.length === 0 ? (
        <Alert
          severity="success"
          icon={<CheckIcon />}
          sx={{ py: compact ? 0.5 : 1 }}
        >
          {compact
            ? "Конфліктів немає"
            : "Чудово! Конфліктів не виявлено. Розклад валідний."}
        </Alert>
      ) : hardConflicts.length > 0 ? (
        <Alert
          severity="error"
          sx={{ mb: compact ? 1 : 2, py: compact ? 0.5 : 1 }}
        >
          {compact
            ? `${hardConflicts.length} жорстких`
            : `Виявлено ${hardConflicts.length} жорстких конфліктів. Необхідно виправити!`}
        </Alert>
      ) : (
        <Alert
          severity="warning"
          sx={{ mb: compact ? 1 : 2, py: compact ? 0.5 : 1 }}
        >
          {compact
            ? `${softConflicts.length} м'яких`
            : `Виявлено ${softConflicts.length} м'яких конфліктів. Рекомендовано оптимізувати.`}
        </Alert>
      )}

      {!compact && <Divider sx={{ my: 2 }} />}

      {/* Conflicts List - only show in full mode */}
      {!compact && hardConflicts.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography
            variant="subtitle2"
            color="error"
            gutterBottom
            sx={{ display: "flex", alignItems: "center", gap: 1 }}
          >
            <ErrorIcon fontSize="small" /> Жорсткі конфлікти (
            {hardConflicts.length})
          </Typography>
          <List dense disablePadding>
            {hardConflicts.map((conflict) => (
              <ConflictItem key={conflict.id} conflict={conflict} />
            ))}
          </List>
        </Box>
      )}

      {!compact && softConflicts.length > 0 && (
        <Box>
          <Typography
            variant="subtitle2"
            color="warning.dark"
            gutterBottom
            sx={{ display: "flex", alignItems: "center", gap: 1 }}
          >
            <WarningIcon fontSize="small" /> М'які конфлікти (
            {softConflicts.length})
          </Typography>
          <List dense disablePadding>
            {softConflicts.map((conflict) => (
              <ConflictItem key={conflict.id} conflict={conflict} />
            ))}
          </List>
        </Box>
      )}

      {/* Snackbar for notifications */}
      <Alert
        severity={snackbar.severity}
        sx={{
          position: "fixed",
          bottom: 24,
          right: 24,
          display: snackbar.open ? "flex" : "none",
          zIndex: 1300,
          boxShadow: 3,
        }}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        {snackbar.message}
      </Alert>
    </Paper>
  );
};

export default ConflictCenter;
