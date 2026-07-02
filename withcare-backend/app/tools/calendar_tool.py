import os
from datetime import datetime, timedelta

from app.utils.exceptions import CalendarActionError
from app.utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_calendar_service():
    """
    Returns a Google Calendar API service object.
    Tries OAuth token.json first (local dev), falls back to service account ADC (Cloud Run).
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        token_path = "token.json"
        creds = None

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise CalendarActionError(
                    "No valid Calendar credentials found. "
                    "Run scripts/setup_calendar_auth.py to generate token.json"
                )

        return build("calendar", "v3", credentials=creds)

    except CalendarActionError:
        raise
    except Exception as e:
        raise CalendarActionError(f"Failed to initialize Calendar service: {e}")


async def create_calendar_event(
    calendar_id: str,
    summary: str,
    description: str,
    start_datetime: str,
    end_datetime: str,
    location: str | None = None,
    attendee_emails: list[str] | None = None,
) -> dict:
    """
    Creates a Google Calendar event.
    Returns {"event_id": str, "html_link": str}
    start_datetime / end_datetime must be ISO 8601 strings (e.g. 2026-07-10T10:00:00)
    """
    try:
        service = get_calendar_service()

        event_body: dict = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_datetime, "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end_datetime, "timeZone": "Asia/Kolkata"},
        }

        if location:
            event_body["location"] = location
        if attendee_emails:
            event_body["attendees"] = [{"email": e} for e in attendee_emails]

        result = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        logger.info(f"Calendar event created: {result['id']} — {summary}")
        return {"event_id": result["id"], "html_link": result["htmlLink"]}

    except CalendarActionError:
        raise
    except Exception as e:
        logger.error(f"create_calendar_event failed: {e}")
        raise CalendarActionError(f"Failed to create calendar event: {e}")


async def sync_to_family_calendar(
    member_calendar_id: str,
    event_data: dict,
    member_consent: bool,
) -> dict | None:
    """
    Creates the same event on a family member's calendar if consent is given. (P0-7)
    event_data must have: summary, description, start_datetime, end_datetime, location (optional)
    """
    if not member_consent:
        logger.info("Family calendar sync skipped — consent not given")
        return None

    if not member_calendar_id:
        logger.info("Family calendar sync skipped — no calendar_id provided")
        return None

    return await create_calendar_event(
        calendar_id=member_calendar_id,
        summary=event_data["summary"],
        description=event_data["description"],
        start_datetime=event_data["start_datetime"],
        end_datetime=event_data["end_datetime"],
        location=event_data.get("location"),
    )


def suggest_appointment_time() -> tuple[str, str]:
    """Returns a sensible default appointment time: next weekday at 10am IST."""
    now = datetime.now()
    days_ahead = 1
    candidate = now + timedelta(days=days_ahead)
    # Skip to Monday if weekend
    while candidate.weekday() >= 5:
        days_ahead += 1
        candidate = now + timedelta(days=days_ahead)

    start = candidate.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    return start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S")
