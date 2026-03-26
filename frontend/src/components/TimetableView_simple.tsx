// Simplified TimetableView component
import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from "@mui/material";
import { getGroups, getGroupTimetable } from "../services/api";

const TimetableView: React.FC = () => {
  const [groups, setGroups] = useState<any[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<number | null>(null);
  const [schedule, setSchedule] = useState<any[]>([]);

  useEffect(() => {
    loadGroups();
  }, []);

  const loadGroups = async () => {
    try {
      const response = await getGroups();
      setGroups(response.data);
    } catch (error) {
      console.error("Failed to load groups:", error);
    }
  };

  const loadSchedule = async (groupId: number) => {
    try {
      const response = await getGroupTimetable(groupId);
      setSchedule(response.data);
    } catch (error) {
      console.error("Failed to load schedule:", error);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Timetable View
      </Typography>
      <FormControl sx={{ minWidth: 200, mb: 3 }}>
        <InputLabel>Select Group</InputLabel>
        <Select
          value={selectedGroup || ""}
          onChange={(e) => {
            const id = Number(e.target.value);
            setSelectedGroup(id);
            loadSchedule(id);
          }}
        >
          {groups.map((group) => (
            <MenuItem key={group.id} value={group.id}>
              {group.code}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      {schedule.length > 0 ? (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Course</TableCell>
                <TableCell>Teacher</TableCell>
                <TableCell>Classroom</TableCell>
                <TableCell>Timeslot</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {schedule.map((item: any) => (
                <TableRow key={item.id}>
                  <TableCell>{item.course_id}</TableCell>
                  <TableCell>{item.teacher_id}</TableCell>
                  <TableCell>{item.classroom_id}</TableCell>
                  <TableCell>{item.timeslot_id}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Typography>No schedule. Generate first.</Typography>
      )}
    </Box>
  );
};

export default TimetableView;
