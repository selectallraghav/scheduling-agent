# Scheduling Agent - Apexon Candidate Engagement Bot

A Streamlit-based conversational chatbot that automatically schedules "connect" meetings between new hires and key personas at Apexon (hiring manager, reporting manager, HRBP, etc.) based on their availability and constraints.

## Features

- **Automated Meeting Scheduling**: Finds optimal meeting slots considering multiple calendars and timezones
- **Dual Calendar Support**: Handles both Apexon and Client calendars for managers, with Client calendar taking priority
- **Constraint-Based Algorithm**: Respects business hours, working days, and deadline constraints
- **Multi-Timezone Support**: Handles participants across different timezones (IST, PST, EST, etc.)
- **Darwin API Integration**: Fetches real employee and candidate data from Darwinbox
- **Conversational UI**: Natural language chatbot interface for scheduling meetings
- **Mock Services**: Simulates calendar events and email sending (calendar and email services are mocked)

## Project Structure

```
.
├── streamlit_scheduler.py         # Main Streamlit chatbot application
├── models/
│   ├── __init__.py
│   └── entities.py                 # Domain models (Candidate, Manager, Meeting, etc.)
├── services/
│   ├── __init__.py
│   ├── darwinbox_client.py         # Darwinbox API client
│   ├── talent_recruit_client.py    # Employee data client (wraps Darwinbox API)
│   ├── calendar_service.py         # Calendar service with dual calendar logic
│   ├── scheduling_engine.py        # Core scheduling algorithm
│   ├── email_service_mock.py       # Mock email service
│   ├── response_formatter.py       # Chatbot response formatting
│   └── talent_recruit_mock.py      # Mock client for testing (legacy)
├── .env.example                    # Environment variables template
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

The application integrates with the Darwinbox API to fetch real employee and candidate data. You need to configure the API credentials before running the application.

### Environment Variables

Create a `.env` file in the project root (see `.env.example` for template):

```bash
# OpenAI API Configuration (required)
OPENAI_API_KEY=your-openai-api-key-here

# Darwinbox API Configuration (required)
DARWINBOX_API_KEY=your-darwinbox-api-key-here
DARWINBOX_BASE_URL=https://your-darwinbox-instance.com
```

**Note:** 
- Get your OpenAI API key from: https://platform.openai.com/api-keys
- Get your Darwinbox API credentials from your Apexon administrator
- The `.env` file is gitignored and will not be committed to the repository

## Usage

### Conversational Chatbot Version
Run the chatbot interface:
```bash
streamlit run streamlit_scheduler.py
```

The app will open in your default web browser at `http://localhost:8501`.

**Note:** Make sure you've configured the API credentials in your `.env` file (see Configuration section above) before running the application.

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

1. **List Candidates**: Use natural language commands like "show me candidates" or "list 10 candidates"
2. **Select a Candidate**: Choose a candidate by name or number from the list
3. **Configure Meeting**: Set meeting type, duration, date range, and business hours via chat
4. **Generate Proposals**: Ask the chatbot to "generate proposals" or "find meeting times"
5. **Book Meeting**: Select a time slot by saying "option 2" or "book option 3"
6. **Send Invites**: Confirm booking to simulate sending email invitations

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
- **Darwinbox Client**: Real API integration to fetch employee data from Darwinbox
  - Fetches employee information including employee IDs, names, and manager relationships
  - Retrieves HRBP and direct manager information
  - Maps API responses to internal `Candidate` and `Manager` entities
- **Employee Data Client**: Wraps Darwinbox client and provides a unified interface for candidate and manager data
- **Calendar Service**: Manages calendar availability with dual calendar support (Apexon + Client calendars)
- **Scheduling Engine**: Core algorithm for finding optimal meeting time slots
- **Email Service Mock**: Logs "sent" emails instead of actually sending them

## Darwinbox API Integration

The application integrates with the Darwinbox Employee API to fetch real employee information:

- **Employee Data API**: Fetches employee records with:
  - Employee IDs, names, and contact information
  - Direct manager relationships (hiring/reporting manager)
  - HRBP (Human Resources Business Partner) assignments
  - Manager contact details and email addresses

The API client automatically maps the Darwinbox API response structure to internal `Candidate` and `Manager` entities for use throughout the application. See `DARWIN_API_FIELDS.md` for detailed API field mappings.

## Future Enhancements

- ✅ Integration with Darwinbox API (Completed)
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

