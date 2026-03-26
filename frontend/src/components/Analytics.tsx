import React, { useState, useEffect } from "react";
import { Box, Typography, Paper, Grid } from "@mui/material";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { getAnalytics } from "../services/api";

const Analytics: React.FC = () => {
  const [analytics, setAnalytics] = useState<any>(null);

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    try {
      const response = await getAnalytics();
      setAnalytics(response.data);
    } catch (error) {
      console.error("Failed to load analytics:", error);
    }
  };

  if (!analytics) {
    return <Typography>Loading...</Typography>;
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Analytics Dashboard
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Classroom Utilization
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={analytics.classroom_utilization}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="classroom_code" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="utilization_rate" fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Teacher Workload
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={analytics.teacher_workload}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="teacher_name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="workload_rate" fill="#82ca9d" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Summary Statistics
            </Typography>
            <Typography>Total Classes: {analytics.total_classes}</Typography>
            <Typography>
              Hard Constraint Violations: {analytics.hard_constraint_violations}
            </Typography>
            <Typography>
              Soft Constraint Violations: {analytics.soft_constraint_violations}
            </Typography>
            <Typography>
              Average Score: {analytics.average_score.toFixed(2)}
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Analytics;
