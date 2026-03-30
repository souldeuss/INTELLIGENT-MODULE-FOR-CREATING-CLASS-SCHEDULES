import React from "react";
import {
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Typography,
  Box,
  Badge,
  Chip,
  Avatar,
} from "@mui/material";
import DashboardIcon from "@mui/icons-material/Dashboard";
import SchoolIcon from "@mui/icons-material/School";
import PersonIcon from "@mui/icons-material/Person";
import GroupIcon from "@mui/icons-material/Group";
import RoomIcon from "@mui/icons-material/Room";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import BarChartIcon from "@mui/icons-material/BarChart";
import FolderIcon from "@mui/icons-material/Folder";
import PsychologyIcon from "@mui/icons-material/Psychology";
import WarningIcon from "@mui/icons-material/Warning";
import TimelineIcon from "@mui/icons-material/Timeline";
import { useNavigate, useLocation } from "react-router-dom";

// Menu structure with sections
const menuSections = [
  {
    title: "Головне",
    items: [
      { text: "Dashboard", icon: <DashboardIcon />, path: "/", badge: null },
      {
        text: "Розклад",
        icon: <CalendarMonthIcon />,
        path: "/timetable",
        badge: null,
      },
      {
        text: "Створення і навчання моделі",
        icon: <TimelineIcon />,
        path: "/training-metrics",
        badge: "LIVE",
      },
      {
        text: "Конфлікти",
        icon: <WarningIcon />,
        path: "/conflicts",
        badge: 2,
      },
    ],
  },
  {
    title: "Управління даними",
    items: [
      { text: "Курси", icon: <SchoolIcon />, path: "/courses", badge: null },
      {
        text: "Викладачі",
        icon: <PersonIcon />,
        path: "/teachers",
        badge: null,
      },
      { text: "Групи", icon: <GroupIcon />, path: "/groups", badge: null },
      {
        text: "Аудиторії",
        icon: <RoomIcon />,
        path: "/classrooms",
        badge: null,
      },
      {
        text: "Часові слоти",
        icon: <AccessTimeIcon />,
        path: "/timeslots",
        badge: null,
      },
    ],
  },
  {
    title: "Аналітика",
    items: [
      {
        text: "Збережені",
        icon: <FolderIcon />,
        path: "/schedules",
        badge: null,
      },
      {
        text: "Статистика",
        icon: <BarChartIcon />,
        path: "/analytics",
        badge: null,
      },
    ],
  },
];

const Navigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Logo Header */}
      <Box sx={{ p: 2, textAlign: "center" }}>
        <Avatar
          sx={{
            width: 48,
            height: 48,
            bgcolor: "primary.main",
            mx: "auto",
            mb: 1,
          }}
        >
          <PsychologyIcon />
        </Avatar>
        <Typography variant="h6" fontWeight="bold" noWrap>
          DRL Scheduler
        </Typography>
        <Typography variant="caption" color="text.secondary">
          AI-powered timetabling
        </Typography>
      </Box>
      <Divider />

      {/* Menu Sections */}
      <Box sx={{ flexGrow: 1, overflowY: "auto", py: 1 }}>
        {menuSections.map((section, sectionIdx) => (
          <Box key={section.title}>
            <Typography
              variant="overline"
              sx={{
                px: 3,
                pt: 2,
                pb: 1,
                display: "block",
                color: "text.secondary",
              }}
            >
              {section.title}
            </Typography>
            <List disablePadding>
              {section.items.map((item) => (
                <ListItem key={item.text} disablePadding sx={{ px: 1 }}>
                  <ListItemButton
                    selected={location.pathname === item.path}
                    onClick={() => navigate(item.path)}
                    sx={{
                      borderRadius: 2,
                      mb: 0.5,
                      "&.Mui-selected": {
                        bgcolor: "primary.50",
                        "&:hover": { bgcolor: "primary.100" },
                      },
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 40 }}>
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText primary={item.text} />
                    {item.badge &&
                      (typeof item.badge === "number" ? (
                        <Badge badgeContent={item.badge} color="error" />
                      ) : (
                        <Chip
                          label={item.badge}
                          size="small"
                          color="secondary"
                          sx={{ height: 20, fontSize: 10 }}
                        />
                      ))}
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
            {sectionIdx < menuSections.length - 1 && <Divider sx={{ my: 1 }} />}
          </Box>
        ))}
      </Box>

      {/* Footer */}
      <Box sx={{ p: 2, borderTop: 1, borderColor: "divider" }}>
        <Typography
          variant="caption"
          color="text.secondary"
          display="block"
          textAlign="center"
        >
          Version 2.0 • DRL Engine
        </Typography>
      </Box>
    </Box>
  );
};

export default Navigation;
