import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Box,
  Drawer,
  AppBar,
  Toolbar,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  IconButton,
  Divider,
  Badge,
  Tooltip,
  Avatar,
  Chip,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import DashboardIcon from "@mui/icons-material/Dashboard";
import SchoolIcon from "@mui/icons-material/School";
import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import BarChartIcon from "@mui/icons-material/BarChart";
import PersonIcon from "@mui/icons-material/Person";
import GroupIcon from "@mui/icons-material/Group";
import RoomIcon from "@mui/icons-material/Room";
import AssignmentIcon from "@mui/icons-material/Assignment";
import FolderIcon from "@mui/icons-material/Folder";
import PsychologyIcon from "@mui/icons-material/Psychology";
import WarningIcon from "@mui/icons-material/Warning";
import { useNavigate, useLocation } from "react-router-dom";
// New Modern Components
import ModernDashboard from "./components/ModernDashboard";
import InteractiveTimetable from "./components/InteractiveTimetable";
import AIControlPanel from "./components/AIControlPanel";
import ConflictCenter from "./components/ConflictCenter";
// Existing Components
import CourseManagement from "./components/CourseManagement";
import TeacherManagement from "./components/TeacherManagement";
import GroupManagement from "./components/GroupManagement";
import ClassroomManagement from "./components/ClassroomManagement";
import CourseAssignments from "./components/CourseAssignments";
import TimetableView from "./components/TimetableView";
import Analytics from "./components/Analytics";
import ScheduleManager from "./components/ScheduleManager";
import TrainingMetrics from "./components/TrainingMetrics";

const drawerWidth = 280;

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1976d2",
      light: "#42a5f5",
      dark: "#1565c0",
    },
    secondary: {
      main: "#9c27b0",
    },
    success: {
      main: "#4caf50",
    },
    warning: {
      main: "#ff9800",
    },
    error: {
      main: "#f44336",
    },
    background: {
      default: "#f5f7fa",
      paper: "#ffffff",
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      fontWeight: 700,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 600,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          borderRight: "none",
          boxShadow: "2px 0 12px rgba(0,0,0,0.05)",
        },
      },
    },
  },
});

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
        text: "AI Генератор",
        icon: <PsychologyIcon />,
        path: "/ai-generator",
        badge: "NEW",
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
        text: "Призначення",
        icon: <AssignmentIcon />,
        path: "/assignments",
        badge: null,
      },
    ],
  },
  {
    title: "Аналітика",
    items: [
      {
        text: "Збережені розклади",
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

function AppContent() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const drawer = (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Logo Header */}
      <Toolbar sx={{ justifyContent: "center", py: 2 }}>
        <Box sx={{ textAlign: "center" }}>
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
      </Toolbar>
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
                    onClick={() => {
                      navigate(item.path);
                      setMobileOpen(false);
                    }}
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

  return (
    <Box sx={{ display: "flex" }}>
      <CssBaseline />
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          ml: { sm: `${drawerWidth}px` },
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: "none" } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div">
            Intelligent Module for Creating Class Schedules
          </Typography>
        </Toolbar>
      </AppBar>
      <Box
        component="nav"
        sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: "block", sm: "none" },
            "& .MuiDrawer-paper": {
              boxSizing: "border-box",
              width: drawerWidth,
            },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: "none", sm: "block" },
            "& .MuiDrawer-paper": {
              boxSizing: "border-box",
              width: drawerWidth,
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerWidth}px)` },
        }}
      >
        <Toolbar />
        <Routes>
          <Route path="/" element={<ModernDashboard />} />
          <Route path="/timetable" element={<InteractiveTimetable />} />
          <Route path="/ai-generator" element={<AIControlPanel />} />
          <Route path="/conflicts" element={<ConflictCenter />} />
          <Route path="/courses" element={<CourseManagement />} />
          <Route path="/teachers" element={<TeacherManagement />} />
          <Route path="/groups" element={<GroupManagement />} />
          <Route path="/classrooms" element={<ClassroomManagement />} />
          <Route path="/assignments" element={<CourseAssignments />} />
          <Route path="/schedules" element={<ScheduleManager />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/training-metrics" element={<TrainingMetrics />} />
          {/* Legacy routes for backward compatibility */}
          <Route path="/legacy-timetable" element={<TimetableView />} />
        </Routes>
      </Box>
    </Box>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <AppContent />
      </Router>
    </ThemeProvider>
  );
}

export default App;
