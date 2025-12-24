"""Structured response formatter for consistent chatbot responses."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz

from models.entities import Candidate, Manager, MeetingProposal


class ResponseFormatter:
    """Formats chatbot responses in a consistent, structured manner."""
    
    @staticmethod
    def format_section(title: str, content: List[str], icon: str = "📋") -> str:
        """Format a section with title and content."""
        lines = [f"**{icon} {title}**", ""]
        lines.extend(content)
        return "\n".join(lines)
    
    @staticmethod
    def format_list_item(index: int, text: str, highlight: bool = False) -> str:
        """Format a list item with optional highlighting."""
        prefix = "⭐" if highlight else f"{index}."
        return f"{prefix} {text}"
    
    @staticmethod
    def format_info_line(label: str, value: str, available: bool = True) -> str:
        """Format an info line with availability indicator."""
        icon = "✅" if available else "❌"
        return f"   {icon} **{label}:** {value}"
    
    @staticmethod
    def format_candidate_list(
        candidates: List[Candidate], 
        limit: int = 50, 
        data_client=None,
        total_count: Optional[int] = None,
        current_offset: int = 0
    ) -> str:
        """Format a list of candidates with employee ID and manager info."""
        if not candidates:
            return ResponseFormatter.format_error(
                "No More Candidates",
                "No more candidates available. You've reached the end of the list."
            )
        
        display_count = len(candidates)
        total = total_count if total_count is not None else display_count
        
        lines = [
            f"**📋 Available Candidates**",
            ""
        ]
        
        # Show appropriate message with pagination info
        if total_count and total_count > display_count:
            lines.append(f"Showing **{current_offset + 1}-{current_offset + display_count}** of **{total_count}** candidate(s) from Darwin API.")
        elif display_count < total:
            lines.append(f"Showing **{display_count}** of **{total}** candidate(s) from Darwin API.")
        else:
            lines.append(f"Found **{display_count}** candidate(s) from Darwin API.")
        
        lines.extend([
            "",
            "**Candidates:**",
            ""
        ])
        
        # Import here to avoid circular dependency
        if data_client is None:
            from services.talent_recruit_client import TalentRecruitClient
            data_client = TalentRecruitClient()
        
        for i, candidate in enumerate(candidates[:display_count], 1):
            lines.append(f"{i}. **{candidate.name}** (Employee ID: {candidate.id})")
            
            # Get manager info for this candidate
            personas = data_client.get_related_personas_for_candidate(candidate.id)
            
            # Show HRBP if available
            if "hrbp" in personas:
                hrbp = personas["hrbp"]
                lines.append(f"   • HRBP: {hrbp.name} ({hrbp.email})")
            
            # Show Hiring Manager if available
            if "hiring_manager" in personas:
                hm = personas["hiring_manager"]
                lines.append(f"   • Hiring Manager: {hm.name} ({hm.email})")
            
            # Show Reporting Manager if available and different from Hiring Manager
            if "reporting_manager" in personas:
                rm = personas["reporting_manager"]
                # Only show if different from hiring manager
                if "hiring_manager" not in personas or rm.email != personas["hiring_manager"].email:
                    lines.append(f"   • Reporting Manager: {rm.name} ({rm.email})")
            
            # If no manager info available
            if not personas:
                lines.append(f"   • Manager Info: Not available")
            
            lines.append("")
        
        # Show pagination message
        remaining = total - (current_offset + display_count) if total_count else 0
        if remaining > 0:
            lines.append(f"*+ {remaining} more candidate(s). Say 'show more candidates' to see the next batch, or use a name/number to select.*")
        elif current_offset > 0:
            lines.append(f"*End of list. Say 'show candidates' to start from the beginning, or use a name/number to select.*")
        else:
            lines.append(f"*Use a name or number to select a candidate.*")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_candidate_details(candidate: Candidate, personas: Dict[str, Manager]) -> str:
        """Format detailed candidate information (only fields available from Darwin API)."""
        lines = [
            f"**👤 Candidate Details: {candidate.name}**",
            "",
            "**Basic Information:**",
            f"• **Employee ID:** {candidate.id}",
            f"• **Name:** {candidate.name}",
            f"• **Email:** {candidate.email}",
            ""
        ]
        
        # Only show role if it's not the default "Employee"
        if candidate.role_title and candidate.role_title != "Employee":
            lines.append(f"• **Role:** {candidate.role_title}")
        
        lines.extend([
            "",
            "**👥 Associated People (from Darwin API):**",
            ""
        ])
        
        # HRBP
        if "hrbp" in personas:
            hrbp = personas["hrbp"]
            lines.append(ResponseFormatter.format_info_line("HRBP", f"{hrbp.name} ({hrbp.email})", True))
        else:
            lines.append(ResponseFormatter.format_info_line("HRBP", "Not available", False))
        
        # Hiring Manager
        if "hiring_manager" in personas:
            hm = personas["hiring_manager"]
            lines.append(ResponseFormatter.format_info_line("Hiring Manager", f"{hm.name} ({hm.email})", True))
        else:
            lines.append(ResponseFormatter.format_info_line("Hiring Manager", "Not available", False))
        
        # Reporting Manager
        if "reporting_manager" in personas:
            rm = personas["reporting_manager"]
            lines.append(ResponseFormatter.format_info_line("Reporting Manager", f"{rm.name} ({rm.email})", True))
        else:
            lines.append(ResponseFormatter.format_info_line("Reporting Manager", "Not available", False))
        
        lines.append("")
        lines.append("ℹ️ **Note:** Recruiter information is not available from Darwin API.")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_personas_list(candidates: List[Candidate], persona_type: str = "hiring_manager") -> str:
        """Format a list showing candidates with/without specific persona."""
        if not candidates:
            return ResponseFormatter.format_error(
                "No Candidates Found",
                "No candidates are currently available."
            )
        
        candidates_with = []
        candidates_without = []
        
        for candidate in candidates:
            from services.talent_recruit_client import TalentRecruitClient
            data_client = TalentRecruitClient()
            personas = data_client.get_related_personas_for_candidate(candidate.id)
            
            if persona_type in personas:
                candidates_with.append((candidate, personas[persona_type]))
            else:
                candidates_without.append(candidate)
        
        # Determine persona label
        persona_labels = {
            "hiring_manager": "Hiring Manager",
            "reporting_manager": "Reporting Manager",
            "hrbp": "HRBP"
        }
        persona_label = persona_labels.get(persona_type, persona_type.title())
        
        lines = [
            f"**📋 {persona_label} Information Availability**",
            "",
            "**Summary:**",
            f"• Total Candidates: {len(candidates)}",
            f"• With {persona_label}: {len(candidates_with)} ({len(candidates_with)*100//len(candidates) if candidates else 0}%)",
            f"• Without {persona_label}: {len(candidates_without)} ({len(candidates_without)*100//len(candidates) if candidates else 0}%)",
            ""
        ]
        
        if candidates_with:
            lines.append(f"**✅ Candidates with {persona_label} Information:**")
            lines.append("")
            for i, (candidate, manager) in enumerate(candidates_with, 1):
                lines.append(f"{i}. **{candidate.name}**")
                # Only show role if it's not the default "Employee"
                if candidate.role_title and candidate.role_title != "Employee":
                    lines.append(f"   • Role: {candidate.role_title}")
                lines.append(f"   • {persona_label}: {manager.name} ({manager.email})")
                lines.append("")
        
        if candidates_without:
            lines.append(f"**❌ Candidates without {persona_label} Information:**")
            lines.append("")
            for i, candidate in enumerate(candidates_without, 1):
                lines.append(f"{i}. **{candidate.name}**")
                # Only show role if it's not the default "Employee"
                if candidate.role_title and candidate.role_title != "Employee":
                    lines.append(f"   • Role: {candidate.role_title}")
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_proposals(proposals: List[MeetingProposal], candidate: Candidate, show_all: bool = False) -> tuple[str, List[Dict[str, Any]]]:
        """
        Format meeting proposals with button information.
        
        Returns:
            tuple: (formatted_text, button_info_list)
            button_info_list contains dicts with 'label' and 'index' for each proposal
        """
        if not proposals:
            return (
                ResponseFormatter.format_error(
                    "No Available Times Found",
                    "Could not find any available meeting times with the current configuration.",
                    suggestions=[
                        "Try adjusting the date range",
                        "Check if all participants have calendar availability",
                        "Consider different meeting duration"
                    ]
                ),
                []
            )
        
        candidate_tz = pytz.timezone(candidate.location_timezone)
        limit = len(proposals) if show_all else min(5, len(proposals))  # Show up to 5 options
        
        lines = [
            "**🎯 Available Meeting Times**",
            "",
            f"Found **{len(proposals)}** available time slot(s).",
            "",
            "**Available Options:**",
            ""
        ]
        
        button_info = []
        
        for i, proposal in enumerate(proposals[:limit], 1):
            slot = proposal.time_slot
            candidate_local = slot.start.astimezone(candidate_tz)
            
            day_name = candidate_local.strftime('%A')
            date_str = candidate_local.strftime('%B %d, %Y')
            time_str = candidate_local.strftime('%I:%M %p')
            
            if i == 1:
                lines.append(f"⭐ **Option {i} (Best Match)**")
            else:
                lines.append(f"**Option {i}**")
            
            lines.append(f"   • Date: {day_name}, {date_str}")
            lines.append(f"   • Time: {time_str} ({candidate.location_timezone})")
            
            if proposal.constraints_violated:
                lines.append(f"   • ⚠️ Note: {', '.join(proposal.constraints_violated)}")
            
            lines.append("")
            
            # Add button info for this proposal with time slot in label
            button_info.append({
                "label": time_str,  # Show only the time slot (e.g., "09:00 AM")
                "index": i - 1,  # 0-based index
                "proposal_index": i - 1
            })
        
        if len(proposals) > limit:
            lines.append(f"*+ {len(proposals) - limit} more option(s) available. Say 'show all' to see them.*")
        
        return "\n".join(lines), button_info
    
    @staticmethod
    def format_success(title: str, message: str, details: Optional[List[str]] = None) -> str:
        """Format a success message."""
        lines = [
            f"**✅ {title}**",
            "",
            message
        ]
        
        if details:
            lines.append("")
            lines.append("**Details:**")
            for detail in details:
                lines.append(f"• {detail}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_error(title: str, message: str, suggestions: Optional[List[str]] = None) -> str:
        """Format an error message."""
        lines = [
            f"**❌ {title}**",
            "",
            message
        ]
        
        if suggestions:
            lines.append("")
            lines.append("**Suggestions:**")
            for suggestion in suggestions:
                lines.append(f"• {suggestion}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_info(title: str, message: str, items: Optional[List[str]] = None) -> str:
        """Format an informational message."""
        lines = [
            f"**ℹ️ {title}**",
            "",
            message
        ]
        
        if items:
            lines.append("")
            for item in items:
                lines.append(f"• {item}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_meeting_config(candidate: Candidate, meeting_type: str, duration: int) -> str:
        """Format meeting configuration summary."""
        lines = [
            "**⚙️ Meeting Configuration**",
            "",
            "**Current Setup:**",
            f"• **Candidate:** {candidate.name}",
            f"• **Meeting Type:** {meeting_type}",
            f"• **Duration:** {duration} minutes",
            "",
            "Ready to find available times! Say 'find times' or 'generate proposals' to continue."
        ]
        
        return "\n".join(lines)
