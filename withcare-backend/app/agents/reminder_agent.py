"""
ReminderAgent — deterministic executor for reminders.

Resolves the target person, creates a Google Calendar reminder (recurring via RRULE + a
"notify N minutes before" override) on THAT person's calendar, emails them, and records a
reminder node in the knowledge graph. No LLM call — the orchestrator extracted the details.
"""
import re
from datetime import date, datetime, timedelta

from app.agents.base_agent import BaseAgent
from app.models.response_models import AgentResult, SourcedStep
from app.services.memory_service import resolve_recipient, write_fact
from app.tools.calendar_tool import create_calendar_event
from app.tools.gmail_tool import send_email
from app.utils.exceptions import CalendarActionError

_RRULE = {"daily": "RRULE:FREQ=DAILY", "weekly": "RRULE:FREQ=WEEKLY", "monthly": "RRULE:FREQ=MONTHLY"}


def _parse_time(t: str) -> str:
    """Return HH:MM 24h from '13:00', '1pm', '1:30 pm', etc. Defaults to 09:00."""
    t = (t or "").strip().lower()
    if not t:
        return "09:00"
    m = re.match(r"^(\d{1,2}):(\d{2})$", t)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", t)
    if m:
        h = int(m.group(1)); mn = int(m.group(2) or 0); ap = m.group(3)
        if ap == "pm" and h != 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mn:02d}"
    return "09:00"


class ReminderAgent(BaseAgent):
    name = "reminder_agent"
    description = "Sets calendar + email reminders for a specific person"

    async def run(self, context: dict) -> AgentResult:
        self.logger.info("ReminderAgent starting")
        user_id = context.get("user_id", "")
        message = context.get("message") or context.get("reminder_message") or "Reminder"
        recurrence = (context.get("recurrence") or "none").lower()
        lead = int(context.get("lead_minutes") or 10)
        time_str = _parse_time(context.get("time", ""))

        # Resolve the recipient: explicit mention, else the active care member.
        mention = context.get("recipient") or context.get("for_member") or ""
        recip = resolve_recipient(mention, user_id) if mention and mention != "self" else None
        recip_name = recip["name"] if recip else (mention or "you")
        recip_email = (recip.get("email") if recip else "") or ""
        recip_pid = recip["id"] if recip else context.get("active_profile_id")

        # Start date: given date, else today (recurring starts today).
        start_date = context.get("date") or date.today().isoformat()
        start_iso = f"{start_date}T{time_str}:00"
        end_iso = (datetime.fromisoformat(start_iso) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
        rrule = _RRULE.get(recurrence)
        calendar_id = recip_email or "primary"

        when = ("every day" if recurrence == "daily" else
                "every week" if recurrence == "weekly" else start_date)
        summary = f"Reminder: {message}"

        event_link = ""
        try:
            event = await create_calendar_event(
                calendar_id=calendar_id,
                summary=summary,
                description=f"WithCare reminder for {recip_name}.",
                start_datetime=start_iso, end_datetime=end_iso,
                attendee_emails=[recip_email] if recip_email else None,
                reminder_minutes=[lead],
                recurrence=rrule,
            )
            event_link = event.get("html_link", "")
        except CalendarActionError as e:
            self.logger.warning(f"reminder calendar create failed: {e}")

        # Email the person (best-effort).
        emailed = False
        if recip_email:
            r = await send_email(recip_email, summary,
                                 f"Hi {recip_name}, this is a WithCare reminder: {message} "
                                 f"({when} at {time_str}).")
            emailed = bool(r.get("ok"))

        # Record in the knowledge graph.
        try:
            write_fact(user_id, recip_pid, "reminder", message,
                       data={"time": time_str, "recurrence": recurrence, "lead_minutes": lead,
                             "recipient": recip_name}, predicate="has_reminder")
        except Exception as ex:
            self.logger.warning(f"KG write (reminder) failed: {ex}")

        detail = (f"Reminder is set for {recip_name} — {when} at {time_str}, "
                  f"notifying {lead} min before. Added to {'their' if recip_email else 'the'} calendar"
                  + (" and emailed to them." if emailed else "."))
        self.logger.info(f"ReminderAgent set reminder for {recip_name} ({recurrence} {time_str})")

        return AgentResult(
            agent_name=self.name,
            steps=[SourcedStep(step_number=1, action=f"Reminder for {recip_name}: {message}",
                               detail=detail, source_url=event_link or "https://calendar.google.com",
                               source_label="Google Calendar", agent=self.name)],
            raw_data=[],
        )
