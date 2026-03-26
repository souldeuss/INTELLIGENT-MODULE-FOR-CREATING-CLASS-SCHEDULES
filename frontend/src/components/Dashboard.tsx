import React, { useState } from "react";
import {
  AppBar,
  Box,
  Container,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  CircularProgress,
  LinearProgress,
  Alert,
} from "@mui/material";
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  School,
  CalendarMonth,
  Analytics,
} from "@mui/icons-material";
import { useNavigate } from "react-router-dom";
import { generateSchedule, getGenerationStatus } from "../services/api";

const Dashboard: React.FC = () => {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [iterations, setIterations] = useState(1000);
  const [generating, setGenerating] = useState(false);
  const [generationId, setGenerationId] = useState<number | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [currentIteration, setCurrentIteration] = useState<number>(0);
  const [totalIterations, setTotalIterations] = useState<number>(0);
  const navigate = useNavigate();

  const handleGenerate = async () => {
    setGenerating(true);
    setCurrentIteration(0);
    setTotalIterations(iterations);
    try {
      const response = await generateSchedule({ iterations });
      setGenerationId(response.data.id);
      pollGenerationStatus(response.data.id);
    } catch (error) {
      console.error("Generation failed:", error);
      setStatus("error");
      setGenerating(false);
    }
  };

  const pollGenerationStatus = async (id: number) => {
    const interval = setInterval(async () => {
      try {
        const response = await getGenerationStatus(id);
        const currentStatus = response.data.status;
        const current = response.data.current_iteration || 0;
        const total = response.data.iterations || iterations;

        setCurrentIteration(current);
        setTotalIterations(total);

        if (currentStatus === "completed") {
          setStatus("success");
          setGenerating(false);
          clearInterval(interval);
        } else if (currentStatus === "failed") {
          setStatus("error");
          setGenerating(false);
          clearInterval(interval);
        }
      } catch (error) {
        console.error("Status check failed:", error);
        clearInterval(interval);
      }
    }, 2000);
  };

  const menuItems = [
    { text: "Dashboard", icon: <DashboardIcon />, path: "/" },
    { text: "Courses", icon: <School />, path: "/courses" },
    { text: "Timetable", icon: <CalendarMonth />, path: "/timetable" },
    { text: "Analytics", icon: <Analytics />, path: "/analytics" },
  ];

  return (
    <Box sx={{ display: "flex" }}>
      <AppBar position="fixed">
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={() => setDrawerOpen(!drawerOpen)}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Intelligent Timetabling System
          </Typography>
          <Button
            color="inherit"
            variant="outlined"
            onClick={() => setGenerateDialogOpen(true)}
          >
            Generate Schedule
          </Button>
        </Toolbar>
      </AppBar>

      <Drawer
        anchor="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        <Box sx={{ width: 250 }} role="presentation">
          <List>
            {menuItems.map((item) => (
              <ListItem key={item.text} disablePadding>
                <ListItemButton
                  onClick={() => {
                    navigate(item.path);
                    setDrawerOpen(false);
                  }}
                >
                  <ListItemIcon>{item.icon}</ListItemIcon>
                  <ListItemText primary={item.text} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Box>
      </Drawer>

      <Container sx={{ mt: 10, mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Welcome to Intelligent Timetabling System
        </Typography>
        <Typography variant="body1" paragraph>
          This system uses Deep Reinforcement Learning (DRL) with Actor-Critic
          architecture and dual-attention mechanism to automatically generate
          optimal university schedules.
        </Typography>
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" gutterBottom>
            Quick Stats
          </Typography>
          {/* TODO: Add statistics cards */}
        </Box>
      </Container>

      <Dialog
        open={generateDialogOpen}
        onClose={() => setGenerateDialogOpen(false)}
      >
        <DialogTitle>Generate Schedule with DRL</DialogTitle>
        <DialogContent>
          {generating ? (
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                p: 3,
              }}
            >
              <CircularProgress />
              <Typography sx={{ mt: 2, mb: 2 }}>
                Generating schedule... {currentIteration}/{totalIterations}
              </Typography>
              <Box sx={{ width: "100%", mt: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={
                    totalIterations > 0
                      ? (currentIteration / totalIterations) * 100
                      : 0
                  }
                />
              </Box>
              <Typography variant="caption" sx={{ mt: 1 }}>
                {totalIterations > 0
                  ? `${Math.round((currentIteration / totalIterations) * 100)}%`
                  : "0%"}
              </Typography>
            </Box>
          ) : status === "success" ? (
            <Alert severity="success">Schedule generated successfully!</Alert>
          ) : status === "error" ? (
            <Alert severity="error">Generation failed. Please try again.</Alert>
          ) : (
            <TextField
              autoFocus
              margin="dense"
              label="Iterations"
              type="number"
              fullWidth
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value))}
              helperText="Number of DRL training iterations (100-10000)"
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setGenerateDialogOpen(false)}>Cancel</Button>
          {!generating && status !== "success" && (
            <Button onClick={handleGenerate} variant="contained">
              Generate
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Dashboard;
