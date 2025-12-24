# Scheduling Agent - Apexon Candidate Engagement Bot

A Streamlit-based prototype that automatically schedules "connect" meetings between new hires and key personas at Apexon (hiring manager, reporting manager, HRBP, etc.) based on their availability and constraints.

## Features

- **Automated Meeting Scheduling**: Finds optimal meeting slots considering multiple calendars and timezones
- **Dual Calendar Support**: Handles both Apexon and Client calendars for managers, with Client calendar taking priority
- **Constraint-Based Algorithm**: Respects business hours, working days, and deadline constraints
- **Multi-Timezone Support**: Handles participants across different timezones (IST, PST, EST, etc.)
- **Mock Services**: Simulates Talent Recruit data, calendar events, and email sending
- **Interactive UI**: Clean Streamlit interface for selecting candidates, configuring meetings, and viewing proposals

## Project Structure

```
.
├── app.py                          # Main Streamlit application
├── models/
│   ├── __init__.py
│   └── entities.py                 # Domain models (Candidate, Manager, Meeting, etc.)
├── services/
│   ├── __init__.py
│   ├── talent_recruit_mock.py      # Mock Talent Recruit service
│   ├── calendar_service.py          # Calendar service with dual calendar logic
│   ├── scheduling_engine.py        # Core scheduling algorithm
│   └── email_service_mock.py       # Mock email service
├── requirements.txt
└── README.md
```

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

The application now integrates with the Talent Recruit API to fetch real candidate data. You need to configure the API credentials before running the application.

### Option 1: Environment Variables

Set the following environment variables:

```bash
export TALENT_RECRUIT_BASE_URL="https://your-talent-recruit-api-url.com"
export TALENT_RECRUIT_API_KEY="your-api-key-here"
export TALENT_RECRUIT_USER_EMAIL="your-email@apexon.com"
```

### Option 2: Streamlit Secrets

Create a `.streamlit/secrets.toml` file (or use Streamlit Cloud secrets):

```toml
[TALENT_RECRUIT]
BASE_URL = "https://your-talent-recruit-api-url.com"
API_KEY = "your-api-key-here"
USER_EMAIL = "your-email@apexon.com"
```

**Note:** The API key is sensitive. If lost, you'll need to request a new one from Talent Recruit as they don't store tokens.

## Usage

### Standard UI Version
Run the Streamlit app:
```bash
streamlit run app.py
```

### Conversational Chatbot Version
Run the chatbot interface:
```bash
streamlit run streamlit_scheduler.py
```

Both apps will open in your default web browser at `http://localhost:8501`.

**Note:** Make sure you've configured the Talent Recruit API credentials (see Configuration section above) before running the application.

### Chatbot Commands

The conversational agent understands natural language. Try these commands:

- **"List candidates"** or **"Show me the candidates"** - See all available new hires
- **"Select [candidate name]"** or **"Choose candidate 1"** - Select a candidate to work with
- **"Schedule intro with hiring manager"** - Set meeting type
- **"Set duration to 45 minutes"** - Configure meeting duration
- **"From 2025-12-24 to 2026-01-03"** - Set date range
- **"Business hours 9 to 5"** - Set working hours
- **"Show availability"** or **"View calendar"** - Check manager calendars
- **"Generate proposals"** or **"Find meeting times"** - Get optimal meeting slots
- **"Send invites"** - Send meeting invitations
- **"Show current settings"** - View configuration
- **"Help"** - See all available commands

## How It Works

1. **Select a Candidate**: Choose from the list of synthetic candidates in the sidebar
2. **Configure Meeting**: Set meeting type, duration, date window, and business hours
3. **View Availability**: See busy slots for the selected manager
4. **Generate Proposals**: Click "Generate Meeting Proposals" to find optimal meeting slots
5. **Send Test Invites**: Click "Send Test Invites" to simulate sending email invitations

## Key Components

### Domain Models (`models/entities.py`)
- `Candidate`: New hire information
- `Manager`: Manager information with dual calendar support
- `CalendarEvent`: Busy time slots
- `TimeSlot`: Free or busy time periods
- `MeetingRequest`: Request to schedule a meeting
- `MeetingProposal`: Proposed meeting time with score

### Calendar Service (`services/calendar_service.py`)
- Merges Apexon and Client calendars
- Client calendar events take priority over Apexon events
- Returns free time slots within business hours

### Scheduling Engine (`services/scheduling_engine.py`)
- Finds overlapping availability across all participants
- Applies constraints (business hours, deadlines, working days)
- Scores proposals based on preference factors
- Returns top N proposals sorted by score

### Services
- **Talent Recruit Client**: Real API integration to fetch candidate data from Talent Recruit
  - Fetches candidates with "Offer Accepted" status
  - Retrieves candidate documents
  - Maps API responses to internal entities
- **Email Service Mock**: Logs "sent" emails instead of actually sending them

## Talent Recruit API Integration

The application integrates with the Talent Recruit API to fetch real candidate information:

- **Candidate List API**: `/api/v1/gateway/apexon/offer/candidate/list`
  - Fetches candidates with "Offer Accepted" substage
  - Returns candidate details including job information, offer details, and recruiter info
  
- **Candidate Documents API**: `/api/v1/gateway/apexon/offer/candidate/document`
  - Fetches documents for candidates in "Document Collection" stages
  - Returns resume and job-related documents

The API client automatically maps the API response structure to internal `Candidate` and `Manager` entities for use throughout the application.

## Future Enhancements

- ✅ Integration with real Talent Recruit API (Completed)
- Integration with Microsoft Graph API for calendar access
- Real email sending via SMTP or email service
- Support for recurring meetings
- Calendar conflict resolution UI
- Meeting rescheduling capabilities
- Enhanced manager mapping from org structure data

## Notes

- All times are handled in UTC internally and converted to local timezones for display
- Business hours are configurable per participant
- The scheduling algorithm prioritizes earlier dates and avoids after-hours meetings
- Client calendar conflicts override Apexon calendar conflicts

## License

Internal prototype for Apexon.

