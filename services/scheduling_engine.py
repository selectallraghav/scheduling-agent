"""Core scheduling algorithm."""

from datetime import date, datetime, timedelta, time
from typing import Literal, Optional

import pytz

from models.entities import MeetingProposal, MeetingRequest, TimeSlot
from services.calendar_service import CalendarService
from services.talent_recruit_client import TalentRecruitClient


class SchedulingEngine:
    """Engine for finding optimal meeting time slots."""
    
    def __init__(
        self,
        calendar_service: CalendarService,
        data_client: TalentRecruitClient
    ):
        """Initialize scheduling engine."""
        self.calendar_service = calendar_service
        self.data_client = data_client
    
    def find_meeting_proposals(
        self,
        request: MeetingRequest,
        business_hours_start: int = 9,
        business_hours_end: int = 18,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days_before_start: int = 3,
        days_after_start: int = 7,
        max_proposals: int = 5
    ) -> list[MeetingProposal]:
        """
        Find optimal meeting time slots for a meeting request.
        
        Args:
            request: Meeting request
            business_hours_start: Business hours start (0-23)
            business_hours_end: Business hours end (0-23)
            start_date: Start date for scheduling window (if None, calculated from candidate start_date)
            end_date: End date for scheduling window (if None, calculated from candidate start_date)
            days_before_start: Days before candidate start date to consider (used if start_date not provided)
            days_after_start: Days after candidate start date to consider (used if end_date not provided)
            max_proposals: Maximum number of proposals to return
        
        Returns:
            List of meeting proposals sorted by score (best first)
        """
        # Get candidate
        candidate = self.data_client.get_candidate_by_id(request.candidate_id)
        if not candidate:
            return []
        
        # Calculate date range
        today = date.today()
        if start_date is None:
            start_date = candidate.start_date - timedelta(days=days_before_start)
        # Ensure start_date is not in the past
        if start_date < today:
            start_date = today
        
        if end_date is None:
            end_date = candidate.start_date + timedelta(days=days_after_start)
        # Ensure end_date is after start_date
        if end_date <= start_date:
            end_date = start_date + timedelta(days=7)
        
        start_datetime = datetime.combine(start_date, time.min).replace(tzinfo=pytz.UTC)
        end_datetime = datetime.combine(end_date, time.max).replace(tzinfo=pytz.UTC)
        
        # Get availability for candidate (assume free during business hours)
        candidate_tz = pytz.timezone(candidate.location_timezone)
        candidate_free_slots = self._get_candidate_availability(
            candidate,
            start_datetime,
            end_datetime,
            business_hours_start,
            business_hours_end
        )
        
        # Get availability for each manager
        manager_availabilities: dict[str, list[TimeSlot]] = {}
        for manager_id in request.participants:
            if manager_id == request.candidate_id:
                continue
            
            manager = self.data_client.get_manager_by_id(manager_id)
            if not manager:
                continue
            
            free_slots = self.calendar_service.get_merged_availability(
                manager_id,
                start_datetime,
                end_datetime,
                business_hours_start,
                business_hours_end
            )
            manager_availabilities[manager_id] = free_slots
        
        # Find overlapping slots
        all_participants = [request.candidate_id] + [
            p for p in request.participants if p != request.candidate_id
        ]
        
        overlapping_slots = self._find_overlapping_slots(
            candidate_free_slots,
            manager_availabilities,
            request.duration_minutes
        )
        
        # Score and rank proposals
        proposals = []
        for slot in overlapping_slots:
            proposal = self._create_proposal(
                slot,
                request,
                candidate,
                all_participants,
                business_hours_start,
                business_hours_end
            )
            proposals.append(proposal)
        
        # Sort by score (higher is better) and return top N
        proposals.sort(key=lambda p: p.score, reverse=True)
        return proposals[:max_proposals]
    
    def _get_candidate_availability(
        self,
        candidate,
        start_datetime: datetime,
        end_datetime: datetime,
        business_hours_start: int,
        business_hours_end: int
    ) -> list[TimeSlot]:
        """Get candidate availability (assume free during business hours)."""
        tz = pytz.timezone(candidate.location_timezone)
        free_slots = []
        
        current_date = start_datetime.date()
        end_date = end_datetime.date()
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:
                local_start = tz.localize(
                    datetime.combine(current_date, time(business_hours_start, 0))
                )
                local_end = tz.localize(
                    datetime.combine(current_date, time(business_hours_end, 0))
                )
                
                slot_start_utc = local_start.astimezone(pytz.UTC)
                slot_end_utc = local_end.astimezone(pytz.UTC)
                
                # Clamp to requested range
                slot_start = max(slot_start_utc, start_datetime)
                slot_end = min(slot_end_utc, end_datetime)
                
                if slot_start < slot_end:
                    free_slots.append(TimeSlot(
                        start=slot_start,
                        end=slot_end,
                        participants=[candidate.id],
                        source="candidate_business_hours"
                    ))
            
            current_date += timedelta(days=1)
        
        return free_slots
    
    def _find_overlapping_slots(
        self,
        candidate_slots: list[TimeSlot],
        manager_availabilities: dict[str, list[TimeSlot]],
        duration_minutes: int
    ) -> list[TimeSlot]:
        """Find overlapping time slots across all participants."""
        if not manager_availabilities:
            # No managers, return candidate slots split by duration
            return self._split_slots_by_duration(candidate_slots, duration_minutes)
        
        # Start with candidate slots
        overlapping = candidate_slots
        
        # Intersect with each manager's availability
        for manager_id, manager_slots in manager_availabilities.items():
            overlapping = self._intersect_slots(overlapping, manager_slots)
        
        # Split into meeting-sized slots
        return self._split_slots_by_duration(overlapping, duration_minutes)
    
    def _intersect_slots(
        self,
        slots1: list[TimeSlot],
        slots2: list[TimeSlot]
    ) -> list[TimeSlot]:
        """Find intersection of two slot lists."""
        result = []
        
        for slot1 in slots1:
            for slot2 in slots2:
                # Find overlap
                overlap_start = max(slot1.start, slot2.start)
                overlap_end = min(slot1.end, slot2.end)
                
                if overlap_start < overlap_end:
                    # Merge participants
                    all_participants = list(set(slot1.participants + slot2.participants))
                    result.append(TimeSlot(
                        start=overlap_start,
                        end=overlap_end,
                        participants=all_participants,
                        source="intersection"
                    ))
        
        return result
    
    def _split_slots_by_duration(
        self,
        slots: list[TimeSlot],
        duration_minutes: int
    ) -> list[TimeSlot]:
        """Split long slots into meeting-sized chunks."""
        result = []
        duration_delta = timedelta(minutes=duration_minutes)
        
        for slot in slots:
            current_start = slot.start
            while current_start + duration_delta <= slot.end:
                result.append(TimeSlot(
                    start=current_start,
                    end=current_start + duration_delta,
                    participants=slot.participants,
                    source=slot.source
                ))
                current_start += duration_delta
        
        return result
    
    def _create_proposal(
        self,
        slot: TimeSlot,
        request: MeetingRequest,
        candidate,
        all_participants: list[str],
        business_hours_start: int,
        business_hours_end: int
    ) -> MeetingProposal:
        """Create a meeting proposal with scoring."""
        score = 100.0
        violations = []
        
        # Check if within deadline
        slot_date = slot.start.date()
        if slot_date > request.deadline_date:
            score -= 50
            violations.append("After deadline")
        
        # Prefer earlier dates (closer to start date)
        days_from_start = abs((slot_date - candidate.start_date).days)
        if days_from_start > 7:
            score -= 20
        elif days_from_start > 3:
            score -= 10
        
        # Check business hours for all participants
        for participant_id in all_participants:
            if participant_id == candidate.id:
                tz = pytz.timezone(candidate.location_timezone)
            else:
                manager = self.data_client.get_manager_by_id(participant_id)
                if not manager:
                    continue
                tz = pytz.timezone(manager.location_timezone)
            
            local_time = slot.start.astimezone(tz)
            hour = local_time.hour
            
            if hour < business_hours_start:
                score -= 15
                violations.append(f"Before business hours for {participant_id}")
            elif hour >= business_hours_end:
                score -= 15
                violations.append(f"After business hours for {participant_id}")
        
        # Prefer morning slots (9-12) over afternoon/evening
        candidate_local = slot.start.astimezone(pytz.timezone(candidate.location_timezone))
        if 9 <= candidate_local.hour < 12:
            score += 10
        elif candidate_local.hour >= 17:
            score -= 5
        
        # Prefer weekdays (already enforced, but add bonus)
        if slot.start.weekday() < 5:
            score += 5
        
        return MeetingProposal(
            time_slot=slot,
            meeting_type=request.meeting_type,
            score=max(0, score),  # Ensure non-negative
            constraints_violated=violations
        )

