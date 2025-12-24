"""Calendar service with dual calendar support."""

from datetime import datetime, timedelta, time
from typing import Literal

import pytz

from models.entities import CalendarEvent, Manager, TimeSlot
from services.talent_recruit_client import TalentRecruitClient


class CalendarService:
    """Service for managing calendar availability with dual calendar support."""
    
    def __init__(self, data_client: TalentRecruitClient):
        """Initialize with employee data client."""
        self.data_client = data_client
        self._calendar_events: dict[str, list[CalendarEvent]] = {}
        self._initialize_synthetic_events()
    
    def _initialize_synthetic_events(self):
        """Generate synthetic calendar events for managers."""
        # Note: These are synthetic manager IDs for calendar simulation
        # In production, these would come from the data client
        managers = [
            self.data_client.get_manager_by_id("mgr_001"),
            self.data_client.get_manager_by_id("mgr_002"),
            self.data_client.get_manager_by_id("mgr_003"),
            self.data_client.get_manager_by_id("mgr_004"),
            self.data_client.get_manager_by_id("mgr_005"),
        ]
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for manager in managers:
            if not manager:
                continue
            
            events = []
            tz = pytz.timezone(manager.location_timezone)
            
            # Generate events for the next 30 days
            for day_offset in range(30):
                current_date = today + timedelta(days=day_offset)
                
                # Skip weekends
                if current_date.weekday() >= 5:
                    continue
                
                # Combine date with time.min to create a datetime, then localize
                local_date = tz.localize(datetime.combine(current_date, time.min))
                
                # Apexon calendar: regular meetings during business hours
                if "apexon" in manager.calendar_ids:
                    # Morning standup (9:00-9:30 local)
                    events.append(CalendarEvent(
                        id=f"apexon_{manager.id}_{day_offset}_standup",
                        calendar_type="apexon",
                        owner_id=manager.id,
                        start=local_date.replace(hour=9, minute=0),
                        end=local_date.replace(hour=9, minute=30),
                        title="Daily Standup"
                    ))
                    
                    # Afternoon meeting (14:00-15:00 local) - every other day
                    if day_offset % 2 == 0:
                        events.append(CalendarEvent(
                            id=f"apexon_{manager.id}_{day_offset}_meeting",
                            calendar_type="apexon",
                            owner_id=manager.id,
                            start=local_date.replace(hour=14, minute=0),
                            end=local_date.replace(hour=15, minute=0),
                            title="Team Meeting"
                        ))
                
                # Client calendar: client meetings (higher priority)
                if "client" in manager.calendar_ids:
                    # Client sync (11:00-12:00 local) - 3 days a week
                    if day_offset % 3 == 0:
                        events.append(CalendarEvent(
                            id=f"client_{manager.id}_{day_offset}_sync",
                            calendar_type="client",
                            owner_id=manager.id,
                            start=local_date.replace(hour=11, minute=0),
                            end=local_date.replace(hour=12, minute=0),
                            title="Client Sync"
                        ))
                    
                    # Client review (16:00-17:00 local) - 2 days a week
                    if day_offset % 4 == 1:
                        events.append(CalendarEvent(
                            id=f"client_{manager.id}_{day_offset}_review",
                            calendar_type="client",
                            owner_id=manager.id,
                            start=local_date.replace(hour=16, minute=0),
                            end=local_date.replace(hour=17, minute=0),
                            title="Client Review"
                        ))
            
            self._calendar_events[manager.id] = events
    
    def get_apexon_calendar_events(self, user_id: str) -> list[CalendarEvent]:
        """Get Apexon calendar events for a user."""
        all_events = self._calendar_events.get(user_id, [])
        return [e for e in all_events if e.calendar_type == "apexon"]
    
    def get_client_calendar_events(self, user_id: str) -> list[CalendarEvent]:
        """Get Client calendar events for a user."""
        all_events = self._calendar_events.get(user_id, [])
        return [e for e in all_events if e.calendar_type == "client"]
    
    def get_merged_availability(
        self, 
        user_id: str, 
        start_date: datetime, 
        end_date: datetime,
        business_hours_start: int = 9,
        business_hours_end: int = 18
    ) -> list[TimeSlot]:
        """
        Merge Apexon and Client calendars and return free time slots.
        
        Rule: Client calendar busy times take priority over Apexon.
        
        Args:
            user_id: Manager ID
            start_date: Start of date range (UTC)
            end_date: End of date range (UTC)
            business_hours_start: Start hour (0-23) in local timezone
            business_hours_end: End hour (0-23) in local timezone
        
        Returns:
            List of free TimeSlots
        """
        manager = self.data_client.get_manager_by_id(user_id)
        if not manager:
            return []
        
        tz = pytz.timezone(manager.location_timezone)
        
        # Get all busy events
        apexon_events = self.get_apexon_calendar_events(user_id)
        client_events = self.get_client_calendar_events(user_id)
        
        # Convert to UTC and merge (client events take priority)
        busy_slots: list[tuple[datetime, datetime]] = []
        
        # Add client events first (higher priority)
        for event in client_events:
            busy_slots.append((event.start.astimezone(pytz.UTC), event.end.astimezone(pytz.UTC)))
        
        # Add apexon events, but skip if they conflict with client events
        for event in apexon_events:
            event_start_utc = event.start.astimezone(pytz.UTC)
            event_end_utc = event.end.astimezone(pytz.UTC)
            
            # Check if this overlaps with any client event
            conflicts = False
            for client_start, client_end in busy_slots:
                if not (event_end_utc <= client_start or event_start_utc >= client_end):
                    conflicts = True
                    break
            
            if not conflicts:
                busy_slots.append((event_start_utc, event_end_utc))
        
        # Sort busy slots by start time
        busy_slots.sort(key=lambda x: x[0])
        
        # Generate free slots
        free_slots = []
        current = start_date.replace(tzinfo=pytz.UTC)
        
        # Iterate through each day in the range
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            # Skip weekends
            if current_date.weekday() < 5:
                # Get business hours for this day in local timezone
                local_start = tz.localize(
                    datetime.combine(current_date, time(business_hours_start, 0))
                )
                local_end = tz.localize(
                    datetime.combine(current_date, time(business_hours_end, 0))
                )
                
                day_start_utc = local_start.astimezone(pytz.UTC)
                day_end_utc = local_end.astimezone(pytz.UTC)
                
                # Clamp to requested range
                slot_start = max(day_start_utc, start_date.replace(tzinfo=pytz.UTC))
                slot_end = min(day_end_utc, end_date.replace(tzinfo=pytz.UTC))
                
                if slot_start < slot_end:
                    # Find gaps between busy slots within this day
                    day_busy = [
                        (max(bs[0], slot_start), min(bs[1], slot_end))
                        for bs in busy_slots
                        if bs[0] < slot_end and bs[1] > slot_start
                    ]
                    
                    if not day_busy:
                        # Entire day is free
                        free_slots.append(TimeSlot(
                            start=slot_start,
                            end=slot_end,
                            participants=[user_id],
                            source="merged_availability"
                        ))
                    else:
                        # Find gaps
                        if day_busy[0][0] > slot_start:
                            free_slots.append(TimeSlot(
                                start=slot_start,
                                end=day_busy[0][0],
                                participants=[user_id],
                                source="merged_availability"
                            ))
                        
                        for i in range(len(day_busy) - 1):
                            gap_start = day_busy[i][1]
                            gap_end = day_busy[i + 1][0]
                            if gap_start < gap_end:
                                free_slots.append(TimeSlot(
                                    start=gap_start,
                                    end=gap_end,
                                    participants=[user_id],
                                    source="merged_availability"
                                ))
                        
                        if day_busy[-1][1] < slot_end:
                            free_slots.append(TimeSlot(
                                start=day_busy[-1][1],
                                end=slot_end,
                                participants=[user_id],
                                source="merged_availability"
                            ))
            
            current_date += timedelta(days=1)
        
        return free_slots
    
    def get_busy_slots(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all busy slots (merged) for a user in the date range."""
        manager = self.data_client.get_manager_by_id(user_id)
        if not manager:
            return []
        
        apexon_events = self.get_apexon_calendar_events(user_id)
        client_events = self.get_client_calendar_events(user_id)
        
        all_events = []
        start_utc = start_date.replace(tzinfo=pytz.UTC) if start_date.tzinfo is None else start_date
        end_utc = end_date.replace(tzinfo=pytz.UTC) if end_date.tzinfo is None else end_date
        
        # Add client events (higher priority)
        for event in client_events:
            event_start_utc = event.start.astimezone(pytz.UTC)
            if start_utc <= event_start_utc < end_utc:
                all_events.append(event)
        
        # Add apexon events that don't conflict with client
        for event in apexon_events:
            event_start_utc = event.start.astimezone(pytz.UTC)
            event_end_utc = event.end.astimezone(pytz.UTC)
            
            if start_utc <= event_start_utc < end_utc:
                # Check for conflicts with client events
                conflicts = False
                for client_event in client_events:
                    client_start = client_event.start.astimezone(pytz.UTC)
                    client_end = client_event.end.astimezone(pytz.UTC)
                    if not (event_end_utc <= client_start or event_start_utc >= client_end):
                        conflicts = True
                        break
                
                if not conflicts:
                    all_events.append(event)
        
        return sorted(all_events, key=lambda e: e.start)

