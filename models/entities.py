"""Domain models for the Scheduling Agent."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Optional


@dataclass
class Candidate:
    """Represents a new hire candidate."""
    id: str
    name: str
    email: str
    role_title: str
    location_timezone: str
    start_date: date
    hiring_manager_id: str
    reporting_manager_id: str


@dataclass
class Manager:
    """Represents a manager (hiring, reporting, HRBP, etc.)."""
    id: str
    name: str
    email: str
    role: Literal["Hiring Manager", "Reporting Manager", "HRBP", "Buddy", "Recruiter"]
    location_timezone: str
    calendar_ids: dict[str, str]  # {"apexon": "...", "client": "..."}


@dataclass
class CalendarEvent:
    """Represents a calendar event (busy slot)."""
    id: str
    calendar_type: Literal["apexon", "client"]
    owner_id: str  # manager id
    start: datetime
    end: datetime
    title: str


@dataclass
class TimeSlot:
    """Represents a time slot (can be free or busy)."""
    start: datetime
    end: datetime
    participants: list[str]  # list of participant ids
    source: Optional[str] = None  # e.g., "merged_availability"


@dataclass
class MeetingRequest:
    """Request to schedule a meeting."""
    candidate_id: str
    participants: list[str]  # candidate + managers
    duration_minutes: int
    deadline_date: date
    meeting_type: Literal["Intro with Hiring Manager", "Intro with Reporting Manager", "Intro with HRBP", "Intro with Buddy"]


@dataclass
class MeetingProposal:
    """A proposed meeting time slot."""
    time_slot: TimeSlot
    meeting_type: str
    score: float
    constraints_violated: list[str]

