import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Paper,
} from "@mui/material";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { getGroups, getGroupTimetable } from "../services/api";

interface Group {
  id: number;
  code: string;
}

const TimetableView: React.FC = () => {
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<number | null>(null);
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    loadGroups();
  }, []);

  useEffect(() => {
    if (selectedGroup) {
      loadTimetable(selectedGroup);
    }
  }, [selectedGroup]);

  const loadGroups = async () => {
    try {
      const response = await getGroups();
      setGroups(response.data);
      if (response.data.length > 0) {
        setSelectedGroup(response.data[0].id);
      }
    } catch (error) {
      console.error("Failed to load groups:", error);
    }
  };

  const loadTimetable = async (groupId: number) => {
    try {
      const response = await getGroupTimetable(groupId);
      // Convert to FullCalendar events format
      const calendarEvents = response.data.map((item: any) => ({
        title: `${item.course_id}`,
        start: new Date(), // TODO: parse timeslot
        end: new Date(),
      }));
      setEvents(calendarEvents);
    } catch (error) {
      console.error("Failed to load timetable:", error);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Timetable View
      </Typography>

      <FormControl fullWidth sx={{ mb: 3 }}>
        <InputLabel>Group</InputLabel>
        <Select
          value={selectedGroup || ""}
          onChange={(e) => setSelectedGroup(Number(e.target.value))}
        >
          {groups.map((group) => (
            <MenuItem key={group.id} value={group.id}>
              {group.code}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Paper sx={{ p: 2 }}>
        <FullCalendar
          plugins={[timeGridPlugin]}
          initialView="timeGridWeek"
          headerToolbar={{
            left: "prev,next today",
            center: "title",
            right: "timeGridWeek,timeGridDay",
          }}
          events={events}
          slotMinTime="08:00:00"
          slotMaxTime="18:00:00"
          allDaySlot={false}
        />
      </Paper>
    </Box>
  );
};

export default TimetableView;
