"""Mock email service for sending meeting invites."""

from datetime import datetime
from typing import Optional

import pytz

from models.entities import MeetingProposal, TimeSlot
from services.talent_recruit_mock import TalentRecruitClientMock


class EmailServiceMock:
    """Mock email service that logs emails instead of sending them."""
    
    def __init__(self, talent_recruit_client: TalentRecruitClientMock):
        """Initialize email service."""
        self.talent_recruit = talent_recruit_client
        self.sent_emails: list[dict] = []
    
    def send_meeting_invite(
        self,
        proposal: MeetingProposal,
        candidate_id: str,
        participant_ids: list[str]
    ) -> dict:
        """
        Send meeting invite email (mock).
        
        Returns:
            dict with email details
        """
        candidate = self.talent_recruit.get_candidate_by_id(candidate_id)
        if not candidate:
            return {}
        
        # Get participant emails and names
        to_emails = []
        participant_names = []
        
        for pid in participant_ids:
            if pid == candidate_id:
                to_emails.append(candidate.email)
                participant_names.append(candidate.name)
            else:
                manager = self.talent_recruit.get_manager_by_id(pid)
                if manager:
                    to_emails.append(manager.email)
                    participant_names.append(manager.name)
        
        # Generate email content
        subject, body = self._generate_invite_content(
            proposal,
            candidate,
            participant_names
        )
        
        email_record = {
            "to": to_emails,
            "subject": subject,
            "body": body,
            "sent_at": datetime.utcnow(),
            "meeting_type": proposal.meeting_type,
            "proposed_time_utc": proposal.time_slot.start.isoformat()
        }
        
        self.sent_emails.append(email_record)
        return email_record
    
    def _generate_invite_content(
        self,
        proposal: MeetingProposal,
        candidate,
        participant_names: list[str]
    ) -> tuple[str, str]:
        """Generate email subject and body."""
        slot = proposal.time_slot
        
        # Format time in each participant's timezone
        time_info = []
        candidate_tz = pytz.timezone(candidate.location_timezone)
        candidate_local = slot.start.astimezone(candidate_tz)
        candidate_time_str = candidate_local.strftime('%A, %B %d, %Y at %I:%M %p %Z')
        time_info.append(
            f"{candidate.name}: {candidate_time_str}"
        )
        
        manager_name = None
        manager_time_str = None
        for pid, name in zip(proposal.time_slot.participants, participant_names):
            if pid == candidate.id:
                continue
            manager = self.talent_recruit.get_manager_by_id(pid)
            if manager:
                manager_name = name
                manager_tz = pytz.timezone(manager.location_timezone)
                manager_local = slot.start.astimezone(manager_tz)
                manager_time_str = manager_local.strftime('%A, %B %d, %Y at %I:%M %p %Z')
                time_info.append(
                    f"{name}: {manager_time_str}"
                )
        
        duration_minutes = int((slot.end - slot.start).total_seconds() / 60)
        
        # Determine meeting purpose based on type
        meeting_purpose_map = {
            "Intro with Hiring Manager": "introduction with their Hiring Manager",
            "Intro with Reporting Manager": "introduction with their Reporting Manager",
            "Intro with HRBP": "introduction with their HR Business Partner",
            "Intro with Buddy": "introduction with their Buddy"
        }
        meeting_purpose = meeting_purpose_map.get(proposal.meeting_type, "introduction meeting")
        
        subject = f"Introduction Meeting: {candidate.name} - {proposal.meeting_type}"
        
        # Build a more natural email body
        # Greeting
        if manager_name:
            body = f"""Hi {candidate.name} and {manager_name},"""
        else:
            body = f"""Hi {candidate.name},"""
        
        body += f"""

I hope you're doing well! I'm reaching out to coordinate an {meeting_purpose} for {candidate.name}, who will be joining our team as a {candidate.role_title}.

This is an important part of {candidate.name}'s onboarding process, and I've found a time that should work well for everyone's schedule. Here are the details:

📅 **Proposed Meeting Time:**
"""
        
        if manager_name and manager_time_str and candidate_time_str != manager_time_str:
            body += f"""• {candidate.name}: {candidate_time_str}
• {manager_name}: {manager_time_str}
"""
        else:
            body += f"""• {candidate_time_str}
"""
        
        body += f"""• Duration: {duration_minutes} minutes

**Who's attending:**
• {candidate.name} ({candidate.email}) - {candidate.role_title}
"""
        
        for pid, name in zip(proposal.time_slot.participants, participant_names):
            if pid != candidate.id:
                manager = self.talent_recruit.get_manager_by_id(pid)
                if manager:
                    body += f"""• {name} ({manager.email}) - {manager.role}
"""
        
        body += f"""
This meeting will be a great opportunity for {candidate.name} to connect with the team and get a better understanding of their role and responsibilities. 

Please let me know if this time works for you. If you need to reschedule or have any questions, just reply to this email and I'll be happy to find an alternative time that works better.

I'll send out a calendar invite once we confirm. Looking forward to getting this scheduled!

Best regards,
Talent Acquisition Team
Apexon

---
Note: This meeting proposal was generated automatically. Please confirm your availability or suggest an alternative time if needed.
        """.strip()
        
        return subject, body
    
    def get_sent_emails(self) -> list[dict]:
        """Get all sent emails."""
        return self.sent_emails.copy()
    
    def clear_emails(self):
        """Clear email log (for testing/reset)."""
        self.sent_emails = []

