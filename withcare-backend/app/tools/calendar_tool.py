import os
from datetime import datetime, timedelta

from app.utils.exceptions import CalendarActionError
from app.utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# All appointment times in WithCare are India Standard Time. Events are created
# with an explicit dateTime + this zone, so the stored instant is always correct
# IST (e.g. "10 AM" = 10:00 IST). If a user's Google Calendar *displays* another
# zone, that's their account's display setting, not a booking error.
_EVENT_TZ = "Asia/Kolkata"


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
    reminder_minutes: list[int] | None = None,
    recurrence: str | None = None,
) -> dict:
    """
    Creates a Google Calendar event.
    Returns {"event_id": str, "html_link": str}
    start_datetime / end_datetime must be ISO 8601 strings (e.g. 2026-07-10T10:00:00)
    - reminder_minutes: popup+email reminders this many minutes before (e.g. [10] or [60]).
    - recurrence: an RRULE string for recurring events (e.g. "RRULE:FREQ=DAILY").
    """
    try:
        service = get_calendar_service()

        event_body: dict = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_datetime, "timeZone": _EVENT_TZ},
            "end": {"dateTime": end_datetime, "timeZone": _EVENT_TZ},
        }

        if location:
            event_body["location"] = location
        if attendee_emails:
            event_body["attendees"] = [{"email": e} for e in attendee_emails]
        if recurrence:
            event_body["recurrence"] = [recurrence]
        if reminder_minutes:
            overrides = []
            for m in reminder_minutes:
                overrides.append({"method": "popup", "minutes": m})
                overrides.append({"method": "email", "minutes": m})
            event_body["reminders"] = {"useDefault": False, "overrides": overrides}

        result = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        logger.info(f"Calendar event created: {result['id']} — {summary}")
        return {"event_id": result["id"], "html_link": result["htmlLink"]}

    except CalendarActionError:
        raise
    except Exception as e:
        logger.error(f"create_calendar_event failed: {e}")
        raise CalendarActionError(f"Failed to create calendar event: {e}")


async def delete_calendar_event(calendar_id: str, event_id: str) -> bool:
    """Delete a calendar event. Best-effort — returns True on success, False otherwise
    (a missing event or auth issue must not crash the caller)."""
    if not event_id:
        return False
    try:
        service = get_calendar_service()
        service.events().delete(calendarId=calendar_id or "primary", eventId=event_id).execute()
        logger.info(f"Calendar event deleted: {event_id}")
        return True
    except Exception as e:
        logger.warning(f"delete_calendar_event failed for {event_id}: {e}")
        return False


async def update_calendar_event(
    calendar_id: str,
    event_id: str,
    summary: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    recurrence: str | None = None,
    reminder_minutes: list[int] | None = None,
) -> bool:
    """Patch an existing calendar event in place (only the fields provided). Best-effort."""
    if not event_id:
        return False
    try:
        service = get_calendar_service()
        patch: dict = {}
        if summary is not None:
            patch["summary"] = summary
        if start_datetime:
            patch["start"] = {"dateTime": start_datetime, "timeZone": _EVENT_TZ}
        if end_datetime:
            patch["end"] = {"dateTime": end_datetime, "timeZone": _EVENT_TZ}
        if recurrence is not None:
            patch["recurrence"] = [recurrence] if recurrence else []
        if reminder_minutes:
            overrides = []
            for m in reminder_minutes:
                overrides.append({"method": "popup", "minutes": m})
                overrides.append({"method": "email", "minutes": m})
            patch["reminders"] = {"useDefault": False, "overrides": overrides}
        if not patch:
            return False
        service.events().patch(calendarId=calendar_id or "primary", eventId=event_id, body=patch).execute()
        logger.info(f"Calendar event updated: {event_id}")
        return True
    except Exception as e:
        logger.warning(f"update_calendar_event failed for {event_id}: {e}")
        return False


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
