import React, { useState, useEffect, useCallback } from "react";
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  Chip,
  IconButton,
  Menu,
  Stack,
} from "@mui/material";
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Lock as LockIcon,
  LockOpen as UnlockIcon,
  MoreVert as MoreIcon,
  Info as InfoIcon,
} from "@mui/icons-material";
import {
  getGroups,
  getTeachers,
  getClassrooms,
  getTimeslots,
  updateScheduledClass,
  lockScheduledClass,
  deleteScheduledClass,
  ScheduleUpdate,
} from "../services/api";

interface ScheduledClass {
  id: number;
  course_id: number;
  course_name: string;
  course_code: string;
  teacher_id: number;
  teacher_name: string;
  group_id: number;
  group_code: string;
  classroom_id: number;
  classroom_code: string;
  timeslot_id: number;
  day_of_week: number;
  period_number: number;
  start_time: string;
  end_time: string;
  is_locked: boolean;
  has_conflict?: boolean;
  conflict_type?: string;
}

interface GroupData {
  id: number;
  code: string;
  specialization?: string;
}

interface TimeslotItem {
  id: number;
  day_of_week: number;
  period_number: number;
  is_active: boolean;
}

const DAYS = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця"];
const PERIODS = [
  { number: 1, time: "08:30 - 09:15" },
  { number: 2, time: "09:25 - 10:10" },
  { number: 3, time: "10:20 - 11:05" },
  { number: 4, time: "11:15 - 12:00" },
  { number: 5, time: "12:10 - 12:55" },
  { number: 6, time: "13:05 - 13:50" },
];

// Color scheme for different course types
const getCourseColor = (courseCode: string): string => {
  const colors: { [key: string]: string } = {
    "Українська література": "#FFB6D9",
    "Англійська мова": "#90EE90",
    Операційні: "#90EE90",
    Програмування: "#87CEEB",
    Психологія: "#FFB6D9",
    Філософія: "#DDA0DD",
    Географія: "#FFB6B6",
    Математика: "#FFD700",
    Економічна: "#E6B3CC",
    Історія: "#F4A460",
    Біологія: "#98D98E",
    "Бази даних": "#87CEEB",
    Алгоритми: "#87CEEB",
  };

  // Check for keywords
  for (const [key, color] of Object.entries(colors)) {
    if (courseCode.includes(key)) {
      return color;
    }
  }

  return "#E8E8E8";
};

interface AllGroupsTimetableProps {
  zoom: number;
  schedule: ScheduledClass[];
  onEditClass: (classItem: ScheduledClass) => void;
  onDeleteClass: (classId: number) => Promise<void>;
  onLockToggle: (classId: number, locked: boolean) => Promise<void>;
  onRefresh: () => Promise<void>;
}

const AllGroupsTimetable: React.FC<AllGroupsTimetableProps> = ({
  zoom,
  schedule,
  onEditClass,
  onDeleteClass,
  onLockToggle,
  onRefresh,
}) => {
  const [groups, setGroups] = useState<GroupData[]>([]);
  const [timeslots, setTimeslots] = useState<TimeslotItem[]>([]);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    classItem: ScheduledClass;
  } | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [groupsRes, timeslotsRes] = await Promise.all([
        getGroups(),
        getTimeslots(),
      ]);

      setGroups(groupsRes.data);
      setTimeslots(
        (timeslotsRes.data || []).filter(
          (slot: TimeslotItem) => slot.is_active !== false
        )
      );
    } catch (error) {
      console.error("Failed to load groups and timeslots:", error);
    }
  };

  // Get classes for a specific group, day, and period
  const getClassesForCell = (groupId: number, dayOfWeek: number, period: number): ScheduledClass[] => {
    return schedule.filter(
      (c) => c.group_id === groupId && c.day_of_week === dayOfWeek && c.period_number === period
    );
  };

  const handleContextMenu = (e: React.MouseEvent, classItem: ScheduledClass) => {
    e.preventDefault();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      classItem,
    });
  };

  const handleDeleteClick = async () => {
    if (contextMenu?.classItem) {
      try {
        await onDeleteClass(contextMenu.classItem.id);
        setContextMenu(null);
        await onRefresh();
      } catch (error) {
        console.error("Failed to delete class:", error);
      }
    }
  };

  const handleLockClick = async () => {
    if (contextMenu?.classItem) {
      try {
        await onLockToggle(contextMenu.classItem.id, !contextMenu.classItem.is_locked);
        setContextMenu(null);
        await onRefresh();
      } catch (error) {
        console.error("Failed to toggle lock:", error);
      }
    }
  };

  const handleEditClick = () => {
    if (contextMenu?.classItem) {
      onEditClass(contextMenu.classItem);
      setContextMenu(null);
    }
  };

  return (
    <Box sx={{ width: "100%", overflow: "auto" }}>
      <TableContainer component={Paper} sx={{ maxHeight: "calc(100vh - 250px)" }}>
        <Table stickyHeader sx={{ minWidth: 1200 }}>
          <TableHead>
            <TableRow sx={{ bgcolor: "#f5f5f5" }}>
              <TableCell
                sx={{
                  fontWeight: "bold",
                  position: "sticky",
                  left: 0,
                  bgcolor: "primary.main",
                  color: "white",
                  zIndex: 10,
                  minWidth: 120,
                }}
              >
                Група
              </TableCell>

              {DAYS.map((day, dayIdx) => (
                <React.Fragment key={dayIdx}>
                  {PERIODS.map((period) => (
                    <TableCell
                      key={`${dayIdx}-${period.number}`}
                      align="center"
                      sx={{
                        fontWeight: "500",
                        fontSize: "0.85rem",
                        bgcolor: "primary.light",
                        color: "primary.contrastText",
                        p: 1,
                        minWidth: 180,
                      }}
                    >
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: "bold" }}>
                          {day.substring(0, 3)}
                        </Typography>
                        <Typography variant="caption">
                          {period.number} урок
                        </Typography>
                        <Typography variant="caption" display="block">
                          {period.time}
                        </Typography>
                      </Box>
                    </TableCell>
                  ))}
                </React.Fragment>
              ))}
            </TableRow>
          </TableHead>

          <TableBody>
            {groups.map((group) => (
              <TableRow key={group.id} sx={{ "&:hover": { bgcolor: "grey.50" } }}>
                <TableCell
                  sx={{
                    fontWeight: "bold",
                    position: "sticky",
                    left: 0,
                    bgcolor: "grey.100",
                    zIndex: 9,
                    minWidth: 120,
                  }}
                >
                  {group.code}
                </TableCell>

                {DAYS.map((_, dayIdx) =>
                  PERIODS.map((period) => {
                    const cellClasses = getClassesForCell(group.id, dayIdx, period.number);

                    return (
                      <TableCell
                        key={`${group.id}-${dayIdx}-${period.number}`}
                        sx={{
                          p: 1,
                          minWidth: 180,
                          maxWidth: 180,
                          bgcolor: cellClasses.length > 0 ? "grey.50" : "white",
                          border: "1px solid #e0e0e0",
                          verticalAlign: "top",
                          position: "relative",
                          overflow: "visible",
                        }}
                      >
                        {cellClasses.map((classItem) => (
                          <Box
                            key={classItem.id}
                            onContextMenu={(e) => handleContextMenu(e, classItem)}
                            sx={{
                              bgcolor: getCourseColor(classItem.course_name),
                              p: 0.75,
                              mb: 0.5,
                              borderRadius: 0.5,
                              fontSize: "0.75rem",
                              cursor: "context-menu",
                              border: classItem.is_locked ? "2px solid #1976d2" : "1px solid #ccc",
                              position: "relative",
                              "&:hover": {
                                boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
                                transform: "scale(1.02)",
                              },
                              transition: "all 0.2s",
                            }}
                          >
                            <Typography
                              variant="caption"
                              sx={{
                                fontWeight: "500",
                                display: "block",
                                whiteSpace: "normal",
                                wordBreak: "break-word",
                              }}
                            >
                              {classItem.course_name}
                            </Typography>
                            <Typography
                              variant="caption"
                              sx={{
                                display: "block",
                                color: "rgba(0,0,0,0.7)",
                                fontSize: "0.7rem",
                              }}
                            >
                              {classItem.teacher_name}
                            </Typography>
                            <Typography
                              variant="caption"
                              sx={{
                                display: "block",
                                color: "rgba(0,0,0,0.7)",
                                fontSize: "0.7rem",
                              }}
                            >
                              {classItem.classroom_code}
                            </Typography>

                            {classItem.is_locked && (
                              <LockIcon
                                sx={{
                                  fontSize: "0.85rem",
                                  position: "absolute",
                                  top: 2,
                                  right: 2,
                                  color: "#1976d2",
                                }}
                              />
                            )}

                            {classItem.has_conflict && (
                              <Tooltip title={classItem.conflict_type}>
                                <InfoIcon
                                  sx={{
                                    fontSize: "0.85rem",
                                    position: "absolute",
                                    top: 2,
                                    right: classItem.is_locked ? 14 : 2,
                                    color: "error.main",
                                  }}
                                />
                              </Tooltip>
                            )}
                          </Box>
                        ))}

                        {cellClasses.length === 0 && (
                          <Typography
                            variant="caption"
                            sx={{ color: "grey.400", fontStyle: "italic" }}
                          >
                            -
                          </Typography>
                        )}
                      </TableCell>
                    );
                  })
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Context Menu */}
      <Menu
        open={contextMenu !== null}
        onClose={() => setContextMenu(null)}
        anchorReference="anchorPosition"
        anchorPosition={
          contextMenu ? { top: contextMenu.y, left: contextMenu.x } : undefined
        }
      >
        <MenuItem onClick={handleEditClick}>
          <EditIcon sx={{ mr: 1 }} /> Редагувати
        </MenuItem>
        <MenuItem onClick={handleLockClick}>
          {contextMenu?.classItem?.is_locked ? (
            <>
              <UnlockIcon sx={{ mr: 1 }} /> Розблокувати
            </>
          ) : (
            <>
              <LockIcon sx={{ mr: 1 }} /> Заблокувати
            </>
          )}
        </MenuItem>
        <MenuItem onClick={handleDeleteClick}>
          <DeleteIcon sx={{ mr: 1 }} /> Видалити
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default AllGroupsTimetable;
