"""Conversational Scheduling Agent - Streamlined UX."""

import ast
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List

import pytz
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from models.entities import MeetingRequest
from services.calendar_service import CalendarService
from services.email_service_mock import EmailServiceMock
from services.scheduling_engine import SchedulingEngine
from services.talent_recruit_client import TalentRecruitClient
from services.response_formatter import ResponseFormatter

# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from .env file
load_dotenv()

# Get OpenAI API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("⚠️ OPENAI_API_KEY not found in environment variables. Please create a .env file with your OpenAI API key.")
    st.stop()

openai_client = OpenAI(api_key=OPENAI_API_KEY)

st.set_page_config(
    page_title="Scheduling Assistant",
    page_icon="🗓️",
    layout="wide"
)

# ============================================================================
# SERVICE INITIALIZATION
# ============================================================================

@st.cache_resource
def get_services(_cache_version="v3.4"):
    """Initialize and cache services using Darwin API."""
    # TalentRecruitClient wraps Darwinbox API for employee data
    try:
        data_client = TalentRecruitClient()
    except Exception as e:
        st.error(f"Failed to initialize Darwin API client: {e}")
        return None, None, None, None
    
    calendar_service = CalendarService(data_client)
    scheduling_engine = SchedulingEngine(calendar_service, data_client)
    email_service = EmailServiceMock(data_client)
    return data_client, calendar_service, scheduling_engine, email_service

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.selected_candidate = None
    st.session_state.meeting_config = {
        "type": None,
        "duration": 30,
        "start_date": None,
        "end_date": None,
        "business_hours_start": 9,
        "business_hours_end": 18
    }
    st.session_state.proposals = []
    st.session_state.meeting_request = None
    st.session_state.awaiting_confirmation = False
    st.session_state.pending_proposal_index = None
    # Track session start time for duration calculation
    st.session_state.session_start_time = datetime.now()
    # Track candidate list pagination
    st.session_state.candidate_list_offset = 0

# Initialize session start time if not set (for existing sessions)
if "session_start_time" not in st.session_state:
    st.session_state.session_start_time = datetime.now()

# Initialize persistent chat history (survives reset)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Initialize candidate list offset if not set
if "candidate_list_offset" not in st.session_state:
    st.session_state.candidate_list_offset = 0

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_conversation_title(messages: List[Dict[str, Any]]) -> str:
    """Generate an appropriate title for a conversation based on its content."""
    if not messages:
        return "Empty Conversation"
    
    # Try to find candidate name from messages
    candidate_name = None
    meeting_type = None
    
    # Check selected candidate in context
    if st.session_state.get("selected_candidate"):
        candidate_name = st.session_state.selected_candidate.name
    
    # Look through messages for candidate mentions and meeting types
    for msg in messages:
        content = msg.get("content", "")
        
        # Check if content mentions a candidate name (try to get from global if available)
        try:
            if 'data_client' in globals() and data_client:
                candidates = data_client.list_candidates()
                for candidate in candidates:
                    if candidate.name in content:
                        candidate_name = candidate.name
                        break
        except:
            pass
        
        # Check for meeting type mentions
        content_lower = content.lower()
        if "hiring manager" in content_lower:
            meeting_type = "Hiring Manager"
        elif "reporting manager" in content_lower:
            meeting_type = "Reporting Manager"
        elif "hrbp" in content_lower or "hr bp" in content_lower:
            meeting_type = "HRBP"
        elif "buddy" in content_lower:
            meeting_type = "Buddy"
        # Note: Recruiter meetings not available from Darwin API
    
    # Build title
    title_parts = []
    if candidate_name:
        title_parts.append(candidate_name)
    if meeting_type:
        title_parts.append(meeting_type)
    
    if title_parts:
        return " • ".join(title_parts)
    
    # Fallback: use first user message (truncated)
    for msg in messages:
        if msg.get("role") == "user":
            first_message = msg.get("content", "")[:50]
            if first_message:
                return first_message + ("..." if len(msg.get("content", "")) > 50 else "")
    
    return f"Conversation {len(st.session_state.chat_history) + 1}"

def generate_conversation_summary(messages: List[Dict[str, Any]], meeting_config: Dict[str, Any] = None) -> str:
    """Generate a 1-liner summary of what happened in the conversation."""
    if not messages:
        return "Empty conversation"
    
    # Extract key information from messages and state
    user_messages = [msg.get("content", "").lower() for msg in messages if msg.get("role") == "user"]
    assistant_messages = [msg.get("content", "").lower() for msg in messages if msg.get("role") == "assistant"]
    
    all_text = " ".join(user_messages + assistant_messages)
    
    # Check for key actions (in priority order)
    summary_parts = []
    
    # Check if meeting was booked
    if any("meeting booked" in msg or ("✅" in msg and "meeting" in msg) for msg in assistant_messages):
        duration = meeting_config.get("duration") if meeting_config else None
        meeting_type = meeting_config.get("type") if meeting_config else None
        if meeting_type:
            type_short = meeting_type.replace("Intro with ", "")
            if duration:
                summary_parts.append(f"Booked {duration}min {type_short} meeting")
            else:
                summary_parts.append(f"Booked {type_short} meeting")
        else:
            summary_parts.append("Meeting booked")
    
    # Check if proposals were generated
    elif any("found" in msg and ("available times" in msg or "proposals" in msg) for msg in assistant_messages):
        summary_parts.append("Found meeting times")
    
    # Check if hiring manager info was queried
    elif any("hiring manager info" in msg or "hiring manager information" in msg or "hiring manager availability" in msg for msg in all_text):
        summary_parts.append("Checked hiring manager availability")
    
        # Note: Recruiter info not available from Darwin API
    
    # Check if candidates were listed
    elif any("candidates ready for onboarding" in msg or "candidates with" in msg or "candidates:" in msg for msg in assistant_messages):
        summary_parts.append("Listed candidates")
    
    # Check if candidate details were viewed
    elif any("candidate details" in msg or "candidate information" in msg for msg in assistant_messages):
        summary_parts.append("Viewed candidate details")
    
    # Check if meeting was configured
    elif any("updated" in msg and ("meeting type" in msg or "duration" in msg) for msg in assistant_messages):
        duration = meeting_config.get("duration") if meeting_config else None
        meeting_type = meeting_config.get("type") if meeting_config else None
        if meeting_type and duration:
            type_short = meeting_type.replace("Intro with ", "")
            summary_parts.append(f"Configured {duration}min {type_short} meeting")
        elif meeting_type:
            type_short = meeting_type.replace("Intro with ", "")
            summary_parts.append(f"Configured {type_short} meeting")
        else:
            summary_parts.append("Configured meeting")
    
    # Check if candidate was selected
    elif any("got it! scheduling for" in msg or "scheduling for" in msg for msg in assistant_messages):
        summary_parts.append("Selected candidate")
    
    # Default fallback - use first meaningful user message
    if not summary_parts:
        for msg in messages:
            if msg.get("role") == "user":
                first_msg = msg.get("content", "").strip()
                # Skip welcome messages or very short messages
                if len(first_msg) > 10 and first_msg.lower() not in ["hi", "hello", "hey"]:
                    if len(first_msg) > 60:
                        summary_parts.append(first_msg[:60] + "...")
                    else:
                        summary_parts.append(first_msg)
                    break
    
    return summary_parts[0] if summary_parts else "Conversation"

def format_candidate_summary(candidate) -> str:
    """Quick candidate summary (without redundant fields)."""
    return f"✓ **{candidate.name}**"

def format_candidate_details(candidate) -> str:
    """Format detailed candidate information using structured formatter."""
    personas = data_client.get_related_personas_for_candidate(candidate.id)
    return ResponseFormatter.format_candidate_details(candidate, personas)

def format_proposals(proposals: List, candidate, show_all: bool = False) -> tuple[str, List[Dict[str, Any]]]:
    """Format meeting proposals using structured formatter."""
    return ResponseFormatter.format_proposals(proposals, candidate, show_all)

def parse_intent_with_openai(prompt: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Enhanced OpenAI intent parsing with better context awareness."""
    if not prompt:
        return None
    
    try:
        context_str = f"""Current state:
- Selected candidate: {context.get('selected_candidate_name', 'None')}
- Meeting type: {context.get('meeting_type', 'None')}
- Duration: {context.get('duration', 'None')} minutes
- Has proposals: {context.get('has_proposals', False)}
- Awaiting confirmation: {context.get('awaiting_confirmation', False)}
"""
        
        recent_messages = context.get('recent_messages', [])
        conversation_history = ""
        if recent_messages:
            conversation_history = "\nRecent conversation:\n"
            for msg in recent_messages[-4:]:
                role = msg.get('role', 'user')
                content = msg.get('content', '')[:200]
                conversation_history += f"{role}: {content}\n"
        
        system_prompt = """You are an intelligent meeting scheduling assistant. Parse user queries naturally and extract structured information.

Available meeting types (return EXACTLY as shown):
- "Intro with Hiring Manager"
- "Intro with Reporting Manager"
- "Intro with HRBP"
- "Intro with Buddy"

IMPORTANT: "Intro with Recruiter" is NOT available - Darwin API does not provide recruiter information.

Available intents:
- list_candidates: Show available candidates from Darwin API (MUST extract count if user specifies a number)
- list_candidates_with_hiring_managers: List candidates showing hiring manager availability (whose hiring manager info is available, who has hiring manager info, which candidates have hiring manager, etc.)
- select_candidate: Choose a candidate (extract name if mentioned)
- view_candidate_details: Show detailed information about a candidate (info, details, about, who is)
- configure_meeting: Set up meeting details
- set_duration: Specify meeting duration
- generate_proposals: Find available meeting times
- confirm_booking: User confirms they want to book (yes, confirm, book it, etc)
- send_invites: Send meeting invitations
- view_email: Show email content
- start_over: Restart the process
- help: User needs assistance

IMPORTANT PARSING RULES:
1. COUNT EXTRACTION IS CRITICAL: If user says "show me 10 candidates" or "list 5 candidates" or "10 candidates", you MUST:
   - Set intent: "list_candidates"
   - Set count: the number they specified (10, 5, etc.)
   - Examples: "show me 10" → count=10, "list 20 candidates" → count=20, "10 people" → count=10
2. If user says "choose [name] and [action]", extract name AND set intent to the action
3. For "30 min with hiring manager" → extract both duration and type
4. "yes", "confirm", "book it", "send it" → intent: confirm_booking
5. Handle typos intelligently (hring→hiring, manaegr→manager)
6. "show me more candidates" or "show more candidates" → intent: list_candidates (increment offset, keep current count)
6a. "show me more", "other options" (for proposals) → intent: generate_proposals with show_all: true
7. Recognize complete requests: "Schedule John Smith for 45 min hiring manager meeting" should extract ALL info
8. IMPORTANT: Recruiter information is NOT available from Darwin API - NEVER set meeting_type to "Intro with Recruiter"
9. Queries about "whose hiring manager", "who has hiring manager", "hiring manager info available", "which candidates have hiring manager" → intent: list_candidates_with_hiring_managers
10. If user asks about recruiter, politely inform them that recruiter information is not available from Darwin API

Return JSON with:
{
    "intent": "primary_intent",
    "candidate_name": "extracted name or null",
    "meeting_type": "meeting type or null",
    "duration": number or null,
    "count": number or null,
    "wants_proposals": true/false,
    "show_all": true/false,
    "confidence": 0.0-1.0
}

CRITICAL COUNT EXTRACTION RULES (MUST FOLLOW):
1. If user says "show me 10 candidates" → MUST return: {"intent": "list_candidates", "count": 10}
2. If user says "list 5 candidates" → MUST return: {"intent": "list_candidates", "count": 5}
3. If user says "10 candidates" → MUST return: {"intent": "list_candidates", "count": 10}
4. If user says "show me 20" → MUST return: {"intent": "list_candidates", "count": 20}
5. If user says "list candidates" (no number) → return: {"intent": "list_candidates", "count": null}
6. ALWAYS extract the number when present - look for patterns like:
   - "show me X"
   - "list X"
   - "X candidates"
   - "X people"
   - Just "X" when context is about listing candidates
7. The count field MUST be a number (integer), not a string. If no number found, use null."""

        user_prompt = f"""{context_str}{conversation_history}

User query: "{prompt}"

Parse and return ONLY valid JSON."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        return None

def auto_extract_all_info(prompt: str) -> Dict[str, Any]:
    """Extract all possible info from a single message."""
    info = {
        "candidate_name": None,
        "meeting_type": None,
        "duration": None
    }
    
    # Extract candidate name with improved matching
    candidates = data_client.list_candidates()
    prompt_lower = prompt.lower().strip()
    
    # Handle possessive queries like "john doe's manager" or "his manager"
    # Extract name before apostrophe or possessive words
    possessive_patterns = [
        r"(\w+(?:\s+\w+)*)\s*'s\s+",  # "john doe's"
    ]
    
    extracted_name = None
    for pattern in possessive_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            extracted_name = match.group(1).strip()
            break
    
    # Handle "setup [candidate] with [person]" pattern
    # Extract candidate name before "with"
    with_pattern = re.search(r"(?:setup|schedule|meet|call)\s+(\w+(?:\s+\w+)*)\s+with", prompt_lower)
    if with_pattern:
        potential_candidate = with_pattern.group(1).strip()
        # Verify it's actually a candidate name
        for candidate in candidates:
            if potential_candidate.lower() in candidate.name.lower() or candidate.name.lower() in potential_candidate.lower():
                extracted_name = candidate.name
                break
    
    # Try exact match first
    for candidate in candidates:
        candidate_name_lower = candidate.name.lower().strip()
        if candidate_name_lower == prompt_lower or (extracted_name and candidate_name_lower == extracted_name):
            info["candidate_name"] = candidate.name
            break
    
    # Try substring match (candidate name in prompt or prompt in candidate name)
    if not info["candidate_name"]:
        search_text = extracted_name if extracted_name else prompt_lower
        for candidate in candidates:
            candidate_name_lower = candidate.name.lower().strip()
            # Check if full candidate name appears in prompt
            if candidate_name_lower in search_text or search_text in candidate_name_lower:
                info["candidate_name"] = candidate.name
                break
            # Check if prompt words match candidate name parts
            search_words = set(search_text.split())
            # If all search words are in candidate name (for partial matches like "john" matching "John Doe")
            if search_words and all(word in candidate_name_lower for word in search_words if len(word) > 2):
                info["candidate_name"] = candidate.name
                break
    
    # Extract meeting type (only Darwin API supported types)
    type_mapping = {
        "hiring manager": "Intro with Hiring Manager",
        "hiring": "Intro with Hiring Manager",
        "reporting manager": "Intro with Reporting Manager",
        "reporting": "Intro with Reporting Manager",
        "hrbp": "Intro with HRBP",
        "hr bp": "Intro with HRBP",
        "buddy": "Intro with Buddy"
    }
    
    prompt_lower = prompt.lower()
    
    # Check for meeting types (recruiter is NOT available from Darwin API)
    for key, value in type_mapping.items():
        if key in prompt_lower:
            info["meeting_type"] = value
            break
    
    # Extract duration
    duration_match = re.search(r'(\d+)\s*(?:min|minutes|minute)', prompt_lower)
    if duration_match:
        info["duration"] = int(duration_match.group(1))
    
    return info

def is_ready_to_generate_proposals() -> bool:
    """Check if we have all info needed to generate proposals."""
    return (
        st.session_state.selected_candidate is not None and
        st.session_state.meeting_config.get("type") is not None and
        st.session_state.meeting_config.get("duration") is not None
    )

def smart_suggest_next_action() -> Optional[str]:
    """Intelligently suggest what the user should do next."""
    if not st.session_state.selected_candidate:
        return "💡 *Try: 'Show me candidates' or just type a candidate's name*"
    
    if not st.session_state.meeting_config.get("type"):
        return "💡 *Try: 'Set up hiring manager meeting' or '30 min with HRBP'*"
    
    if not st.session_state.meeting_config.get("duration"):
        return "💡 *Try: '30 minutes' or '45 min'*"
    
    if not st.session_state.proposals:
        return "💡 *Try: 'Find available times' or just say 'go'*"
    
    return None

# ============================================================================
# INTENT HANDLERS - Streamlined
# ============================================================================

def handle_list_candidates(count: Optional[int] = None, offset: Optional[int] = None, reset_offset: bool = False) -> str:
    """Show candidates with structured response and pagination support."""
    candidates = data_client.list_candidates()
    
    # Handle offset
    if reset_offset:
        # Reset to beginning when explicitly requesting a count
        st.session_state.candidate_list_offset = 0
        current_offset = 0
    elif offset is not None:
        # Use provided offset
        current_offset = offset
        st.session_state.candidate_list_offset = offset
    else:
        # Use current session offset (for "show more")
        current_offset = st.session_state.candidate_list_offset
    
    # Use requested count, default to 10 if not specified
    limit = count if count and count > 0 else 10
    
    # Calculate end index
    end_index = current_offset + limit
    
    # Get the slice of candidates
    candidates_slice = candidates[current_offset:end_index]
    
    # Update offset for next "show more" request
    if len(candidates_slice) > 0:
        st.session_state.candidate_list_offset = end_index
    
    return ResponseFormatter.format_candidate_list(
        candidates_slice, 
        limit=limit, 
        data_client=data_client,
        total_count=len(candidates),
        current_offset=current_offset
    )

def handle_list_candidates_with_recruiters() -> str:
    """Handle recruiter queries - inform user that recruiter info is not available from Darwin API."""
    return ResponseFormatter.format_info(
        "Recruiter Information Not Available",
        "Recruiter information is not available from Darwin API. The Darwin API provides the following information:",
        [
            "✅ HRBP (Human Resources Business Partner)",
            "✅ Hiring Manager (Direct Manager)",
            "✅ Reporting Manager (Direct Manager)",
            "❌ Recruiter (Not available)"
        ]
    )

def handle_list_candidates_with_hiring_managers() -> str:
    """List candidates with structured response showing hiring manager availability."""
    candidates = data_client.list_candidates()
    return ResponseFormatter.format_personas_list(candidates, "hiring_manager")

def handle_view_candidate_details(candidate_name: str = None) -> str:
    """Show detailed information about a candidate."""
    # Determine which candidate to show
    candidate = None
    
    if candidate_name:
        # Try to find candidate by name with improved matching
        candidates = data_client.list_candidates()
        candidate_name_lower = candidate_name.lower().strip()
        
        # Try exact match first
        for cand in candidates:
            if cand.name.lower().strip() == candidate_name_lower:
                candidate = cand
                break
        
        # Try substring match
        if not candidate:
            for cand in candidates:
                cand_name_lower = cand.name.lower().strip()
                if candidate_name_lower in cand_name_lower or cand_name_lower in candidate_name_lower:
                    candidate = cand
                    break
        
        # Try word-based matching (for partial names like "john" matching "John Doe")
        if not candidate:
            candidate_name_words = set(candidate_name_lower.split())
            for cand in candidates:
                cand_name_lower = cand.name.lower().strip()
                cand_words = set(cand_name_lower.split())
                # If all words in candidate_name are found in candidate's name
                if candidate_name_words and all(word in cand_name_lower for word in candidate_name_words if len(word) > 2):
                    candidate = cand
                    break
        
        # Try by number
        if not candidate:
            try:
                num = int(candidate_name)
                if 1 <= num <= len(candidates):
                    candidate = candidates[num - 1]
            except ValueError:
                pass
    elif st.session_state.selected_candidate:
        # Use currently selected candidate
        candidate = st.session_state.selected_candidate
    
    if not candidate:
        candidates = data_client.list_candidates()
        return f"🤔 I couldn't find a candidate named '{candidate_name}'. Could you try again?\n\n{ResponseFormatter.format_candidate_list(candidates, limit=10, data_client=data_client)}"
    
    return format_candidate_details(candidate)

def handle_select_candidate(candidate_name: str, ai_intent: Dict[str, Any]) -> str:
    """Select candidate and auto-progress if more info provided."""
    candidates = data_client.list_candidates()
    
    # Try to find candidate with improved matching
    candidate = None
    candidate_name_lower = candidate_name.lower().strip()
    
    # Try exact match first
    for cand in candidates:
        if cand.name.lower().strip() == candidate_name_lower:
            candidate = cand
            break
    
    # Try substring match
    if not candidate:
        for cand in candidates:
            cand_name_lower = cand.name.lower().strip()
            if candidate_name_lower in cand_name_lower or cand_name_lower in candidate_name_lower:
                candidate = cand
                break
    
    # Try word-based matching
    if not candidate:
        candidate_name_words = set(candidate_name_lower.split())
        for cand in candidates:
            cand_name_lower = cand.name.lower().strip()
            if candidate_name_words and all(word in cand_name_lower for word in candidate_name_words if len(word) > 2):
                candidate = cand
                break
    
    # Try by number
    if not candidate:
        try:
            num = int(candidate_name)
            if 1 <= num <= len(candidates):
                candidate = candidates[num - 1]
        except ValueError:
            pass
    
    if not candidate:
        return (
            f"**❌ Candidate Not Found**\n\n"
            f"Could not find a candidate named '{candidate_name}'.\n\n"
            f"**Please try:**\n"
            f"• Type the full name\n"
            f"• Use a candidate number from the list\n"
            f"• Check spelling\n\n"
            f"{ResponseFormatter.format_candidate_list(candidates, limit=10, data_client=data_client)}"
        )
    
    # Select candidate
    st.session_state.selected_candidate = candidate
    
    # Check for additional info in same message
    meeting_type = ai_intent.get("meeting_type") if ai_intent else None
    duration = ai_intent.get("duration") if ai_intent else None
    
    if meeting_type:
        st.session_state.meeting_config["type"] = meeting_type
    if duration:
        st.session_state.meeting_config["duration"] = duration
    
    # Build structured response
    lines = [
        "**✅ Candidate Selected**",
        "",
        f"**Name:** {candidate.name}",
        ""
    ]
    
    # Only show role if it's not the default "Employee"
    if candidate.role_title and candidate.role_title != "Employee":
        lines.append(f"**Role:** {candidate.role_title}")
        lines.append("")
    
    if meeting_type:
        lines.append(f"**Meeting Type:** {meeting_type}")
    else:
        lines.append("**Meeting Type:** Not set")
    
    if duration:
        lines.append(f"**Duration:** {duration} minutes")
    else:
        lines.append("**Duration:** Not set")
    
    lines.append("")
    
    # Auto-generate if we have everything
    if is_ready_to_generate_proposals():
        lines.append("🔍 **Finding available meeting times...**")
        st.session_state.auto_generate = True
    else:
        lines.append("**Next Steps:**")
        if not meeting_type:
            lines.append("• Specify meeting type (e.g., 'hiring manager', 'HRBP', 'reporting manager')")
        if not duration:
            lines.append("• Specify duration (e.g., '30 minutes', '45 min')")
        if meeting_type and duration:
            lines.append("• Say 'find times' or 'generate proposals' to find available slots")
    
    return "\n".join(lines)

def handle_configure_meeting(ai_intent: Dict[str, Any], prompt: str = "") -> str:
    """Configure meeting with smart extraction."""
    # Extract all info from prompt if available
    extracted_info = auto_extract_all_info(prompt) if prompt else {}
    
    # First, try to extract and select candidate if mentioned in the query
    candidate_name = ai_intent.get("candidate_name") if ai_intent else None
    if not candidate_name:
        candidate_name = extracted_info.get("candidate_name")
    
    # If candidate name found but not selected, select it first
    if candidate_name and not st.session_state.selected_candidate:
        candidates = data_client.list_candidates()
        candidate = None
        candidate_name_lower = candidate_name.lower().strip()
        
        # Try exact match first
        for cand in candidates:
            if cand.name.lower().strip() == candidate_name_lower:
                candidate = cand
                break
        
        # Try substring match
        if not candidate:
            for cand in candidates:
                cand_name_lower = cand.name.lower().strip()
                if candidate_name_lower in cand_name_lower or cand_name_lower in candidate_name_lower:
                    candidate = cand
                    break
        
        # Try word-based matching
        if not candidate:
            candidate_name_words = set(candidate_name_lower.split())
            for cand in candidates:
                cand_name_lower = cand.name.lower().strip()
                if candidate_name_words and all(word in cand_name_lower for word in candidate_name_words if len(word) > 2):
                    candidate = cand
                    break
        
        # Try by number if not found by name
        if not candidate:
            try:
                num = int(candidate_name)
                if 1 <= num <= len(candidates):
                    candidate = candidates[num - 1]
            except ValueError:
                pass
        
        if candidate:
            st.session_state.selected_candidate = candidate
        else:
            return (
                f"**❌ Candidate Not Found**\n\n"
                f"Could not find a candidate named '{candidate_name}'.\n\n"
                f"**Please try:**\n"
                f"• Type the full name\n"
                f"• Use a candidate number from the list\n"
                f"• Check spelling\n\n"
                f"{format_candidate_list(candidates)}"
            )
    
    # If still no candidate selected, ask for it
    if not st.session_state.selected_candidate:
        return (
            "**📋 Select a Candidate**\n\n"
            "Please select a candidate first to configure the meeting.\n\n"
            "**You can:**\n"
            "• Type a candidate's name\n"
            "• Say 'list candidates' to see all available candidates\n"
            "• Use a candidate number from the list"
        )
    
    # Extract meeting type and duration from AI intent or prompt
    meeting_type = ai_intent.get("meeting_type") if ai_intent else None
    if not meeting_type:
        meeting_type = extracted_info.get("meeting_type")
    
    duration = ai_intent.get("duration") if ai_intent else None
    if not duration:
        duration = extracted_info.get("duration")
    
    # Build structured response
    candidate = st.session_state.selected_candidate
    lines = [
        "**⚙️ Meeting Configuration**",
        ""
    ]
    
    # If candidate was just selected, mention it
    if candidate_name and st.session_state.selected_candidate:
        if candidate_name.lower() in candidate.name.lower():
            lines.append(f"**Candidate:** {candidate.name} ({candidate.role_title})")
            lines.append("")
    
    updated = []
    
    if meeting_type:
        st.session_state.meeting_config["type"] = meeting_type
        lines.append(f"✅ **Meeting Type:** {meeting_type}")
        updated.append("meeting type")
    else:
        lines.append("❌ **Meeting Type:** Not set")
    
    if duration:
        st.session_state.meeting_config["duration"] = duration
        lines.append(f"✅ **Duration:** {duration} minutes")
        updated.append("duration")
    else:
        lines.append("❌ **Duration:** Not set")
    
    lines.append("")
    
    # Auto-generate if ready
    if is_ready_to_generate_proposals():
        lines.append("🔍 **Finding available meeting times...**")
        st.session_state.auto_generate = True
    else:
        lines.append("**Next Steps:**")
        if not meeting_type:
            lines.append("• Specify meeting type (e.g., 'hiring manager', 'HRBP', 'reporting manager')")
        if not duration:
            lines.append("• Specify duration (e.g., '30 minutes', '45 min')")
        if meeting_type and duration:
            lines.append("• Say 'find times' or 'generate proposals' to find available slots")
        lines.append("")
        lines.append("ℹ️ **Note:** Recruiter meetings are not available - Darwin API does not provide recruiter information")
    
    return "\n".join(lines)

def handle_generate_proposals(show_all: bool = False) -> str:
    """Generate and display proposals with structured response."""
    candidate = st.session_state.selected_candidate
    if not candidate:
        return (
            "**❌ No Candidate Selected**\n\n"
            "Please select a candidate first before generating meeting proposals.\n\n"
            "**You can:**\n"
            "• Type a candidate's name\n"
            "• Say 'list candidates' to see all available candidates"
        )
    
    meeting_type = st.session_state.meeting_config.get("type")
    if not meeting_type:
        return (
            "**❌ Meeting Type Not Set**\n\n"
            "Please specify the meeting type before generating proposals.\n\n"
            "**Available types:**\n"
            "• Intro with Hiring Manager\n"
            "• Intro with Reporting Manager\n"
            "• Intro with HRBP\n"
            "• Intro with Buddy"
        )
    
    # Get participants
    personas = data_client.get_related_personas_for_candidate(candidate.id)
    participant_ids = [candidate.id]
    
    # Check if we have the required persona for the meeting type
    if "hiring" in meeting_type.lower():
        if "hiring_manager" in personas:
            participant_ids.append(personas["hiring_manager"].id)
        else:
            return (
                f"**❌ Hiring Manager Not Available**\n\n"
                f"Hiring manager information is not available for **{candidate.name}**.\n\n"
                f"**Available from Darwin API:**\n"
                f"• HRBP: {'✅ Available' if 'hrbp' in personas else '❌ Not available'}\n"
                f"• Reporting Manager: {'✅ Available' if 'reporting_manager' in personas else '❌ Not available'}\n\n"
                f"**Please:**\n"
                f"• Use a different meeting type\n"
                f"• Or ensure manager data is configured in Darwin API"
            )
    elif "reporting" in meeting_type.lower():
        if "reporting_manager" in personas:
            participant_ids.append(personas["reporting_manager"].id)
        else:
            return (
                f"**❌ Reporting Manager Not Available**\n\n"
                f"Reporting manager information is not available for **{candidate.name}**.\n\n"
                f"**Available from Darwin API:**\n"
                f"• HRBP: {'✅ Available' if 'hrbp' in personas else '❌ Not available'}\n"
                f"• Hiring Manager: {'✅ Available' if 'hiring_manager' in personas else '❌ Not available'}\n\n"
                f"**Please:**\n"
                f"• Use a different meeting type\n"
                f"• Or ensure manager data is configured in Darwin API"
            )
    elif "hrbp" in meeting_type.lower():
        if "hrbp" in personas:
            participant_ids.append(personas["hrbp"].id)
        else:
            return (
                f"**❌ HRBP Not Available**\n\n"
                f"HRBP information is not available for **{candidate.name}**.\n\n"
                f"**Available from Darwin API:**\n"
                f"• Hiring Manager: {'✅ Available' if 'hiring_manager' in personas else '❌ Not available'}\n"
                f"• Reporting Manager: {'✅ Available' if 'reporting_manager' in personas else '❌ Not available'}\n\n"
                f"**Please:**\n"
                f"• Use a different meeting type\n"
                f"• Or ensure manager data is configured in Darwin API"
            )
    elif "buddy" in meeting_type.lower():
        if "buddy" in personas:
            participant_ids.append(personas["buddy"].id)
        else:
            return (
                f"**❌ Buddy Not Available**\n\n"
                f"Buddy information is not available for **{candidate.name}**.\n\n"
                f"**Available from Darwin API:**\n"
                f"• HRBP: {'✅ Available' if 'hrbp' in personas else '❌ Not available'}\n"
                f"• Hiring Manager: {'✅ Available' if 'hiring_manager' in personas else '❌ Not available'}\n"
                f"• Reporting Manager: {'✅ Available' if 'reporting_manager' in personas else '❌ Not available'}\n\n"
                f"**Please:**\n"
                f"• Use a different meeting type\n"
                f"• Or ensure buddy data is configured"
            )
    elif "recruiter" in meeting_type.lower():
        return ResponseFormatter.format_error(
            "Recruiter Not Available",
            "Recruiter information is not available from Darwin API.",
            [
                "Available meeting types:",
                "• Intro with Hiring Manager",
                "• Intro with Reporting Manager",
                "• Intro with HRBP",
                "• Intro with Buddy"
            ]
        )
    
    if len(participant_ids) < 2:
        return (
            f"**❌ Participant Not Found**\n\n"
            f"Could not find the required participant for **{meeting_type}**.\n\n"
            f"**Please:**\n"
            f"• Check the meeting type\n"
            f"• Ensure manager data is available in Darwin API"
        )
    
    # Create meeting request
    duration = st.session_state.meeting_config.get("duration", 30)
    start_date = candidate.start_date - timedelta(days=3)
    end_date = candidate.start_date + timedelta(days=7)
    
    st.session_state.meeting_config["start_date"] = start_date
    st.session_state.meeting_config["end_date"] = end_date
    
    meeting_request = MeetingRequest(
        candidate_id=candidate.id,
        participants=participant_ids,
        duration_minutes=duration,
        deadline_date=end_date,
        meeting_type=meeting_type
    )
    
    # Generate proposals
    proposals = scheduling_engine.find_meeting_proposals(
        meeting_request,
        business_hours_start=9,
        business_hours_end=18,
        start_date=start_date,
        end_date=end_date
    )
    
    st.session_state.proposals = proposals
    st.session_state.meeting_request = meeting_request
    st.session_state.awaiting_confirmation = True
    st.session_state.pending_proposal_index = 0
    
    if proposals:
        response_text, _ = format_proposals(proposals, candidate, show_all=show_all)
        response_text += "\n\n**To book a time slot, say:**"
        response_text += "\n• 'yes' or 'book it' to book the best option (Option 1)"
        if len(proposals) > 1:
            response_text += f"\n• 'option 2', 'option 3', etc. to book a different time slot"
        if not show_all and len(proposals) > 5:
            response_text += "\n• 'show all' to see all available options"
        return response_text
    else:
        return "❌ No available times found. Try adjusting the date range?"

def handle_confirm_booking(proposal_index: int = 0) -> str:
    """Confirm and send meeting invite."""
    if not st.session_state.proposals:
        return "No proposals available. Let's find some meeting times first!"
    
    proposal = st.session_state.proposals[proposal_index]
    meeting_request = st.session_state.meeting_request
    candidate = st.session_state.selected_candidate
    
    # Send invite
    email_record = email_service.send_meeting_invite(
        proposal=proposal,
        candidate_id=candidate.id,
        participant_ids=meeting_request.participants
    )
    
    slot = proposal.time_slot
    candidate_tz = pytz.timezone(candidate.location_timezone)
    candidate_local = slot.start.astimezone(candidate_tz)
    
    response = f"✅ **Meeting booked!**\n\n"
    response += f"📅 {candidate_local.strftime('%A, %B %d at %I:%M %p %Z')}\n"
    response += f"📧 Invites sent to {len(email_record.get('to', []))} people\n\n"
    response += "*Need to schedule another meeting? Just let me know!*"
    
    # Reset state
    st.session_state.awaiting_confirmation = False
    st.session_state.pending_proposal_index = None
    st.session_state.proposals = []
    
    return response

def handle_view_email() -> str:
    """Display the latest sent email content."""
    sent_emails = email_service.get_sent_emails()
    if not sent_emails:
        return "📧 No emails have been sent yet. Please send a meeting invite first!"
    
    # Get the latest email
    latest_email = sent_emails[-1]
    
    # Format email display
    response = "📧 **Latest Email Content:**\n\n"
    response += f"**To:** {', '.join(latest_email.get('to', []))}\n\n"
    response += f"**Subject:** {latest_email.get('subject', 'N/A')}\n\n"
    response += f"**Sent At:** {latest_email.get('sent_at', datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    response += "**Email Body:**\n\n"
    response += "```\n"
    response += latest_email.get('body', '')
    response += "\n```"
    
    return response

def handle_start_over() -> str:
    """Reset and start fresh."""
    st.session_state.selected_candidate = None
    st.session_state.meeting_config = {
        "type": None,
        "duration": 30,
        "start_date": None,
        "end_date": None,
        "business_hours_start": 9,
        "business_hours_end": 18
    }
    st.session_state.proposals = []
    st.session_state.meeting_request = None
    st.session_state.awaiting_confirmation = False
    # Reset session start time for new session
    st.session_state.session_start_time = datetime.now()
    
    return "✨ Starting fresh! Who would you like to schedule a meeting for?"

# Initialize services using Darwin API (no configuration needed)
data_client, calendar_service, scheduling_engine, email_service = get_services()

if data_client is None:
    st.error("Failed to initialize services. Please check your configuration.")
    st.stop()

# ============================================================================
# CONVERSATION HISTORY FUNCTIONS
# ============================================================================

def save_current_conversation_to_history():
    """Save current conversation with state to history."""
    if st.session_state.messages:
        conversation_title = generate_conversation_title(st.session_state.messages)
        conversation_summary = generate_conversation_summary(
            st.session_state.messages, 
            st.session_state.meeting_config
        )
        
        # Save candidate ID instead of object (for serialization)
        candidate_id = None
        if st.session_state.selected_candidate:
            candidate_id = st.session_state.selected_candidate.id
        
        conversation_entry = {
            "title": conversation_title,
            "summary": conversation_summary,
            "messages": st.session_state.messages.copy(),
            "state": {
                "candidate_id": candidate_id,
                "meeting_config": st.session_state.meeting_config.copy(),
                # Note: proposals and meeting_request are not saved as they may contain complex objects
                # They will be regenerated if needed
            }
        }
        st.session_state.chat_history.append(conversation_entry)

def messages_are_identical(messages1: List[Dict], messages2: List[Dict]) -> bool:
    """Compare two message lists to see if they're identical."""
    if len(messages1) != len(messages2):
        return False
    
    for msg1, msg2 in zip(messages1, messages2):
        if (msg1.get("role") != msg2.get("role") or 
            msg1.get("content") != msg2.get("content")):
            return False
    return True

def conversation_already_in_history(messages: List[Dict]) -> bool:
    """Check if a conversation with these exact messages already exists in history."""
    for saved_entry in st.session_state.chat_history:
        saved_messages = saved_entry.get("messages", [])
        if messages_are_identical(messages, saved_messages):
            return True
    return False

def restore_conversation(conversation_entry: Dict[str, Any]):
    """Restore a conversation from history."""
    current_messages = st.session_state.messages
    target_messages = conversation_entry.get("messages", [])
    
    # Check if we're trying to restore the same conversation that's currently active
    is_same_conversation = messages_are_identical(current_messages, target_messages)
    
    # Only save current conversation if:
    # 1. It's not the same conversation we're restoring
    # 2. It has meaningful content (user messages, not just welcome)
    # 3. It's not already in history
    if not is_same_conversation and current_messages:
        # Check if there are any user messages (not just assistant welcome message)
        user_messages = [msg for msg in current_messages if msg.get("role") == "user"]
        if len(user_messages) > 0:
            # Check if current conversation is already in history (avoid duplicates)
            if not conversation_already_in_history(current_messages):
                save_current_conversation_to_history()
    
    # Restore messages
    st.session_state.messages = target_messages.copy()
    
    # Reset session start time when restoring a conversation (new session starts)
    st.session_state.session_start_time = datetime.now()
    
    # Restore state (backward compatible with old conversations that don't have state)
    saved_state = conversation_entry.get("state", {})
    candidate_id = saved_state.get("candidate_id") if saved_state else None
    
    # Restore candidate if ID is available
    if candidate_id:
        try:
            candidate = data_client.get_candidate_by_id(candidate_id)
            if candidate:
                st.session_state.selected_candidate = candidate
            else:
                st.session_state.selected_candidate = None
        except Exception:
            st.session_state.selected_candidate = None
    else:
        # Try to extract candidate from messages if state not available (backward compatibility)
        st.session_state.selected_candidate = None
        if not saved_state:
            # Try to find candidate name in messages
            for msg in st.session_state.messages:
                content = msg.get("content", "")
                try:
                    candidates = data_client.list_candidates()
                    for candidate in candidates:
                        if candidate.name in content or f"**{candidate.name}**" in content:
                            st.session_state.selected_candidate = candidate
                            break
                    if st.session_state.selected_candidate:
                        break
                except Exception:
                    pass
    
    # Restore meeting config
    saved_meeting_config = saved_state.get("meeting_config", {}) if saved_state else {}
    if saved_meeting_config:
        st.session_state.meeting_config = saved_meeting_config.copy()
    else:
        # Default config if not available
        st.session_state.meeting_config = {
            "type": None,
            "duration": 30,
            "start_date": None,
            "end_date": None,
            "business_hours_start": 9,
            "business_hours_end": 18
        }
    
    # Reset proposals and meeting request (will be regenerated if needed)
    st.session_state.proposals = []
    st.session_state.meeting_request = None
    st.session_state.awaiting_confirmation = False
    st.session_state.pending_proposal_index = None

# ============================================================================
# MAIN CHAT INTERFACE
# ============================================================================

# Sidebar for conversation history
with st.sidebar:
    st.header("💬 Conversation History")
    
    # Collapsible toggle
    show_history = st.checkbox("Show History", value=True, key="show_history")
    
    if show_history:
        if st.session_state.chat_history:
            st.markdown("---")
            
            # Display order toggle
            display_order = st.radio(
                "Order",
                ["Newest First", "Oldest First"],
                horizontal=True,
                key="history_order",
                label_visibility="collapsed"
            )
            
            # Prepare messages for display
            messages_to_display = list(reversed(st.session_state.chat_history)) if display_order == "Newest First" else st.session_state.chat_history
            
            # Scrollable container for history
            for idx, conversation_entry in enumerate(messages_to_display):
                # Each entry is a dict with 'title', 'summary', and 'messages'
                title = conversation_entry.get("title", f"Conversation {idx + 1}")
                summary = conversation_entry.get("summary", "")
                messages = conversation_entry.get("messages", [])
                
                # Generate summary if not available (backward compatibility for old conversations)
                if not summary and messages:
                    saved_state = conversation_entry.get("state", {})
                    meeting_config = saved_state.get("meeting_config", {}) if saved_state else {}
                    summary = generate_conversation_summary(messages, meeting_config)
                
                # Check if this is the current active conversation
                is_current_conversation = messages_are_identical(st.session_state.messages, messages)
                
                # Create a unique key for each conversation button using title hash
                title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
                conversation_key = f"continue_{title_hash}_{idx}"
                
                # Determine styling based on whether it's the current conversation
                if is_current_conversation:
                    # Highlight current conversation
                    border_style = "2px solid #1f77b4"
                    bg_style = "rgba(31, 119, 180, 0.15)"
                else:
                    border_style = "1px solid rgba(255, 255, 255, 0.1)"
                    bg_style = "rgba(255, 255, 255, 0.02)"
                
                # Create clickable card using a button styled as a card
                # Format button content with title and summary
                button_text = f"💬 {title}\n\n{summary if summary else 'No summary available'}"
                
                # Use a container to wrap the button and apply styling
                with st.container():
                    # Add CSS for this specific conversation item
                    # Use a unique class name based on the key
                    st.markdown(f"""
                    <style>
                    .conv-btn-{conversation_key} button {{
                        width: 100% !important;
                        text-align: left !important;
                        padding: 12px !important;
                        border: {border_style} !important;
                        background-color: {bg_style} !important;
                        border-radius: 8px !important;
                        white-space: pre-wrap !important;
                        font-weight: normal !important;
                        height: auto !important;
                        min-height: 60px !important;
                        margin: 8px 0 !important;
                    }}
                    </style>
                    <div class="conv-btn-{conversation_key}">
                    """, unsafe_allow_html=True)
                    
                    # Create the clickable button (entire card area is clickable)
                    if st.button(button_text, key=conversation_key, help=f"Click to continue: {title}", use_container_width=True):
                        restore_conversation(conversation_entry)
                        st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                
                # Add expander for details
                with st.expander("View details", expanded=False):
                    if messages:
                        for msg in messages:
                            role = msg.get("role", "user")
                            content = msg.get("content", "")
                            
                            if role == "user":
                                st.markdown(f"**👤 You:**")
                            else:
                                st.markdown(f"**🤖 Assistant:**")
                            
                            st.markdown(content)
                            
                            if msg != messages[-1]:
                                st.markdown("---")
                    else:
                        st.markdown("*No messages*")
                
                if idx < len(messages_to_display) - 1:
                    st.markdown("---")
            
            st.markdown("---")
            st.caption(f"Total conversations: {len(st.session_state.chat_history)}")
            
            # Clear history button
            if st.button("🗑️ Clear All History", key="clear_history", help="Permanently delete all conversation history"):
                st.session_state.chat_history = []
                st.rerun()
        else:
            st.info("No conversation history yet. Your conversations will be saved here after you reset.")
        
        # Current session info
        st.markdown("---")
        st.subheader("📊 Current Session")
        if st.session_state.selected_candidate:
            candidate = st.session_state.selected_candidate
            st.markdown(f"**Selected:** {candidate.name}")
            st.markdown(f"**Role:** {candidate.role_title}")
        else:
            st.markdown("*No candidate selected*")
        
        meeting_type = st.session_state.meeting_config.get("type")
        if meeting_type:
            st.markdown(f"**Meeting:** {meeting_type}")
        
        # Calculate and display session duration (dynamic with minutes and seconds)
        session_start = st.session_state.get("session_start_time")
        if session_start:
            elapsed = datetime.now() - session_start
            total_seconds = int(elapsed.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            # Format duration with minutes and seconds (always show seconds)
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
            
            st.markdown(f"**Session Duration:** {duration_str}")
        
        # Show meeting duration if configured
        meeting_duration = st.session_state.meeting_config.get("duration")
        if meeting_duration:
            st.markdown(f"**Meeting Duration:** {meeting_duration} min")
        
        st.markdown(f"**Messages in session:** {len(st.session_state.messages)}")

# Main content area
st.title("🗓️ Meeting Scheduler")
st.caption("Schedule onboarding meetings for new hires - just chat naturally!")

# Reset button
if st.button("🔄 Reset Conversation", key="reset_button"):
    # Save current conversation to history before clearing
    save_current_conversation_to_history()
    
    # Clear current session
    st.session_state.selected_candidate = None
    st.session_state.meeting_config = {
        "type": None,
        "duration": 30,
        "start_date": None,
        "end_date": None,
        "business_hours_start": 9,
        "business_hours_end": 18
    }
    st.session_state.proposals = []
    st.session_state.meeting_request = None
    st.session_state.awaiting_confirmation = False
    st.session_state.messages = []
    # Reset session start time for new session
    st.session_state.session_start_time = datetime.now()
    st.rerun()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        content = message.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        st.markdown(content)

# Welcome message
if not st.session_state.messages:
    welcome = """👋 Hi! I'm here to help you schedule onboarding meetings for new hires.

Just chat with me naturally! For example:
• "Show me the candidates"
• "Schedule John Smith for a 30 min hiring manager meeting"
• "Setup John with HRBP for 30 minutes"
• "Find available times"

**What would you like to do?**"""
    
    st.session_state.messages.append({"role": "assistant", "content": welcome})
    with st.chat_message("assistant"):
        st.markdown(welcome)

# Handle auto-generate flag
if st.session_state.get("auto_generate"):
    st.session_state.auto_generate = False
    with st.spinner("Finding available times..."):
        result = handle_generate_proposals()
        response_text = result[0] if isinstance(result, tuple) else str(result) if result else ""
        st.session_state.messages.append({"role": "assistant", "content": response_text})
        with st.chat_message("assistant"):
            st.markdown(response_text)

# Chat input
prompt = st.chat_input("Type your message here...")

if prompt:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Build context
    context = {
        "selected_candidate_name": st.session_state.selected_candidate.name if st.session_state.selected_candidate else None,
        "meeting_type": st.session_state.meeting_config.get("type"),
        "duration": st.session_state.meeting_config.get("duration"),
        "has_proposals": bool(st.session_state.proposals),
        "awaiting_confirmation": st.session_state.awaiting_confirmation,
        "recent_messages": st.session_state.messages[-10:]
    }
    
    # Handle pronouns (his, her, their) - check recent messages for candidate name
    prompt_lower = prompt.lower()
    if any(pronoun in prompt_lower for pronoun in ["his", "her", "their", "him", "she", "they"]):
        # Look for candidate name in recent messages
        for msg in reversed(st.session_state.messages[-5:]):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                # Try to extract candidate name from recent assistant messages
                candidates = data_client.list_candidates()
                for candidate in candidates:
                    if candidate.name in content or f"**{candidate.name}**" in content:
                        # Found a candidate mentioned recently, use it as context
                        if not context.get("selected_candidate_name"):
                            context["selected_candidate_name"] = candidate.name
                        break
    
    # Parse with AI
    ai_intent = parse_intent_with_openai(prompt, context)
    
    # Also extract all info at once
    extracted_info = auto_extract_all_info(prompt)
    
    # If pronoun detected and we have context, use it
    if any(pronoun in prompt_lower for pronoun in ["his", "her", "their", "him", "she", "they"]) and context.get("selected_candidate_name"):
        if not extracted_info.get("candidate_name"):
            extracted_info["candidate_name"] = context["selected_candidate_name"]
    
    # Merge extracted info with AI intent
    if ai_intent:
        if not ai_intent.get("candidate_name") and extracted_info["candidate_name"]:
            ai_intent["candidate_name"] = extracted_info["candidate_name"]
        if not ai_intent.get("meeting_type") and extracted_info["meeting_type"]:
            ai_intent["meeting_type"] = extracted_info["meeting_type"]
        if not ai_intent.get("duration") and extracted_info["duration"]:
            ai_intent["duration"] = extracted_info["duration"]
    
    # Determine intent
    intent = ai_intent.get("intent") if ai_intent and ai_intent.get("confidence", 0) > 0.5 else None
    
    # Define pattern lists for priority checks
    prompt_lower = prompt.lower()
    
    # Check for option selection - must happen before other intent processing
    if st.session_state.get("proposals"):
        option_match = re.search(r'option\s*(\d+)', prompt_lower)
        if option_match:
            option_num = int(option_match.group(1))
            proposal_index = option_num - 1
            proposals = st.session_state.get("proposals", [])
            if 0 <= proposal_index < len(proposals):
                st.session_state.pending_proposal_index = proposal_index
                st.session_state.awaiting_confirmation = True
                intent = "confirm_booking"
            else:
                intent = "invalid_option"
    
    # Check for hiring manager info queries
    has_hiring_manager_keywords = (
        "hiring manager" in prompt_lower and 
        any(word in prompt_lower for word in ["info", "available", "whose", "who has"])
    ) or any(phrase in prompt_lower for phrase in [
        "whose hiring manager", "who has hiring manager", "hiring manager info",
        "hiring manager available", "which candidates have hiring manager",
        "candidates with hiring manager", "hiring manager information"
    ])
    
    if has_hiring_manager_keywords:
        intent = "list_candidates_with_hiring_managers"
    
    # Fallback intent detection
    if not intent:
        if any(phrase in prompt_lower for phrase in ["whose recruiter", "who has recruiter", "recruiter info available"]):
            intent = "list_candidates_with_recruiters"
        elif any(phrase in prompt_lower for phrase in ["show more candidates", "show more", "next candidates", "more candidates"]):
            intent = "list_candidates"
        elif any(word in prompt_lower for word in ["list", "show", "see"]) and "candidate" in prompt_lower:
            intent = "list_candidates"
        elif st.session_state.get("proposals") and any(word in prompt_lower for word in ["yes", "confirm", "book", "send", "good", "perfect", "ok"]):
            st.session_state.pending_proposal_index = 0
            st.session_state.awaiting_confirmation = True
            intent = "confirm_booking"
        elif any(word in prompt_lower for word in ["yes", "confirm", "book", "send", "good", "perfect", "ok"]) and st.session_state.awaiting_confirmation:
            st.session_state.pending_proposal_index = 0
            intent = "confirm_booking"
        elif any(word in prompt_lower for word in ["find", "available", "times", "proposals", "when", "schedule"]):
            intent = "generate_proposals"
        elif any(word in prompt_lower for word in ["email", "view email", "show email", "see email", "sent email"]):
            intent = "view_email"
        elif any(word in prompt_lower for word in ["recruiter", "recruiters", "who recruited"]) and (extracted_info["candidate_name"] or st.session_state.selected_candidate):
            # If asking about recruiter, inform user it's not available
            intent = "list_candidates_with_recruiters"
        elif any(word in prompt_lower for word in ["info", "details", "about", "who is", "tell me about"]) and (extracted_info["candidate_name"] or st.session_state.selected_candidate):
            intent = "view_candidate_details"
        elif any(word in prompt_lower for word in ["start over", "reset", "restart", "new"]):
            intent = "start_over"
        elif any(word in prompt_lower for word in ["setup", "set up", "configure", "schedule"]) and (extracted_info["meeting_type"] or extracted_info["duration"] or extracted_info["candidate_name"]):
            # If user says "setup/configure/schedule" with meeting details, it's configure_meeting
            intent = "configure_meeting"
        elif extracted_info["candidate_name"]:
            intent = "select_candidate"
        elif extracted_info["meeting_type"] or extracted_info["duration"]:
            intent = "configure_meeting"
    
    # Handle intent
    response = ""
    
    with st.spinner("Thinking..."):
        try:
            if intent == "list_candidates":
                # Check if this is a "show more" request
                is_show_more = any(phrase in prompt_lower for phrase in [
                    "show more candidates", "show more", "next candidates", 
                    "more candidates", "continue", "load more"
                ])
                
                # Extract count from AI intent first (most reliable)
                count = None
                reset_offset = False
                
                if ai_intent and "count" in ai_intent:
                    count_value = ai_intent.get("count")
                    if count_value is not None:
                        try:
                            count = int(count_value)
                            reset_offset = True
                        except (ValueError, TypeError):
                            count = None
                
                # Fallback: Extract from prompt directly
                if not count or count <= 0:
                    patterns = [
                        r'show\s+(?:me\s+)?(\d+)\s*(?:candidates?|people|employees?)?',
                        r'list\s+(\d+)\s*(?:candidates?|people|employees?)?',
                        r'(\d+)\s+candidates?',
                        r'(\d+)\s+people',
                        r'(\d+)\s+employees?',
                        r'give\s+me\s+(\d+)',
                        r'display\s+(\d+)',
                        r'(\d+)\s*$',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, prompt_lower)
                        if match:
                            try:
                                count = int(match.group(1))
                                if count > 0:
                                    reset_offset = True
                                    break
                            except (ValueError, IndexError):
                                continue
                
                if is_show_more and not reset_offset:
                    response = handle_list_candidates(count=count or 10, reset_offset=False)
                else:
                    response = handle_list_candidates(count=count, reset_offset=reset_offset or True)
            elif intent == "list_candidates_with_recruiters":
                response = handle_list_candidates_with_recruiters()
            elif intent == "list_candidates_with_hiring_managers":
                response = handle_list_candidates_with_hiring_managers()
            elif intent == "select_candidate":
                candidate_name = ai_intent.get("candidate_name") if ai_intent else extracted_info["candidate_name"]
                if not candidate_name:
                    candidate_name = prompt
                response = handle_select_candidate(candidate_name, ai_intent)
            elif intent == "configure_meeting":
                response = handle_configure_meeting(ai_intent, prompt)
            elif intent == "generate_proposals":
                show_all = ai_intent.get("show_all", False) if ai_intent else False
                response = handle_generate_proposals(show_all=show_all)
            elif intent == "invalid_option":
                # Handle invalid option number
                proposals = st.session_state.get("proposals", [])
                response = f"❌ Invalid option. Please select an option between 1 and {len(proposals)}."
            elif intent == "confirm_booking":
                # Get proposal index from session state (set by option parsing or defaults to 0 for best match)
                proposal_index = st.session_state.pending_proposal_index
                if proposal_index is None:
                    proposal_index = 0  # Default to best match if not specified
                # Validate proposal index
                proposals = st.session_state.get("proposals", [])
                if not proposals:
                    response = "❌ No proposals available. Please generate proposals first."
                elif proposal_index < 0 or proposal_index >= len(proposals):
                    response = f"❌ Invalid option. Please select an option between 1 and {len(proposals)}."
                else:
                    response = handle_confirm_booking(proposal_index)
            elif intent == "view_email":
                response = handle_view_email()
            elif intent == "view_candidate_details":
                candidate_name = ai_intent.get("candidate_name") if ai_intent else extracted_info.get("candidate_name")
                # Don't pass None as candidate_name - use selected candidate or extract from context
                if not candidate_name and st.session_state.selected_candidate:
                    candidate_name = None  # Will use selected candidate
                elif not candidate_name:
                    # Try to extract from prompt if it mentions a specific name
                    prompt_lower = prompt.lower()
                    candidates = data_client.list_candidates()
                    for cand in candidates:
                        if cand.name.lower() in prompt_lower or prompt_lower in cand.name.lower():
                            candidate_name = cand.name
                            break
                response = handle_view_candidate_details(candidate_name)
            elif intent == "start_over":
                response = handle_start_over()
            else:
                # Smart fallback
                if st.session_state.awaiting_confirmation:
                    response = "Not sure what you mean. Say 'yes' to book the meeting, or 'show more' for other times."
                elif not st.session_state.selected_candidate:
                    response = "I'm here to help schedule meetings! Try saying 'show candidates' or just type a candidate's name."
                else:
                    response = "I'm not quite sure what you'd like to do. "
                    suggestion = smart_suggest_next_action()
                    if suggestion:
                        response += f"\n\n{suggestion}"
        except Exception as e:
            response = f"Oops, something went wrong: {str(e)}\n\nLet's try again!"
    
    # Display response - extract text from tuple if needed
    if isinstance(response, tuple) and len(response) == 2:
        response_text = response[0] if isinstance(response[0], str) else str(response[0])
    else:
        response_text = str(response) if response else ""
    
    # Clean tuple representation if it leaked into string
    if response_text.strip().startswith("(") and "proposal_index" in response_text:
        try:
            parsed = ast.literal_eval(response_text)
            if isinstance(parsed, tuple) and len(parsed) == 2:
                response_text = str(parsed[0]) if parsed[0] else ""
        except:
            match = re.search(r"^\(['\"](.+?)(?:',\s*\[|\",\s*\[)", response_text, re.DOTALL)
            if match:
                response_text = match.group(1).replace("\\n", "\n")
    
    st.session_state.messages.append({"role": "assistant", "content": response_text})
    
    with st.chat_message("assistant"):
        st.markdown(response_text)
    
    st.rerun()
