from datetime import datetime, timedelta

from app.agents.base_agent import BaseAgent
from app.models.response_models import AgentResult, SourcedStep
from app.tools.calendar_tool import create_calendar_event, sync_to_family_calendar, suggest_appointment_time
from app.tools.drive_tool import save_care_plan_to_drive, share_doc_with_email
from app.services.memory_service import write_fact
from app.utils.exceptions import CalendarActionError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ActionAgent(BaseAgent):
    name = "action_agent"
    description = "Creates Google Calendar events for health appointments"

    async def run(self, context: dict) -> AgentResult:
        self.logger.info("ActionAgent starting")

        # Use typed params passed directly by the orchestrator — no re-extraction needed
        procedure      = context.get("extracted_procedure") or context.get("user_message", "Healthcare Appointment")
        start_dt       = context.get("extracted_start_datetime", "")
        end_dt         = context.get("extracted_end_datetime", "")
        hospital       = context.get("extracted_hospital", "")
        for_member     = context.get("for_member", "self")
        family_profile = context.get("family_profile", [])
        care_plan_steps = context.get("care_plan_steps", [])

        # Build event title: "Eye Check-up — LV Prasad Eye Institute"
        summary = procedure
        if hospital and hospital != "find_nearest":
            summary = f"{procedure} — {hospital}"
        elif care_plan_steps:
            # Use the top facility from previous find_facilities call
            top = care_plan_steps[0] if care_plan_steps else None
            if top:
                hosp_name = (top.get("action", "") if isinstance(top, dict) else getattr(top, "action", "")).replace("Visit ", "").replace(" (nearby)", "")
                if hosp_name:
                    summary = f"{procedure} — {hosp_name}"

        # Validate / fall back datetime
        if not start_dt or "T" not in start_dt:
            start_dt, end_dt = suggest_appointment_time()
            self.logger.info(f"No datetime extracted — using fallback: {start_dt}")
        elif not end_dt or "T" not in end_dt:
            try:
                s = datetime.fromisoformat(start_dt)
                end_dt = (s + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                _, end_dt = suggest_appointment_time()

        # Format readable time string
        try:
            s_dt = datetime.fromisoformat(start_dt)
            e_dt = datetime.fromisoformat(end_dt)
            time_str = f"{s_dt.strftime('%d %b %Y, %I:%M %p')} – {e_dt.strftime('%I:%M %p')} IST"
        except Exception:
            time_str = start_dt[:10]

        # Primary calendar
        primary_calendar_id = "primary"
        for member in family_profile:
            if member.get("relation") == "self" and member.get("calendar_id"):
                primary_calendar_id = member["calendar_id"]
                break

        event_data = {
            "summary": summary,
            "description": f"WithCare scheduled appointment for {for_member}. Procedure: {procedure}.",
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "location": hospital if hospital and hospital != "find_nearest" else None,
        }

        try:
            event = await create_calendar_event(calendar_id=primary_calendar_id, **event_data)
            html_link = event["html_link"]
            event_id  = event["event_id"]
        except CalendarActionError as e:
            self.logger.warning(f"Calendar creation failed: {e}")
            return AgentResult(
                agent_name=self.name,
                steps=[SourcedStep(
                    step_number=1,
                    action=summary,
                    detail=f"Recommended: {time_str}. (Calendar integration requires OAuth setup.)",
                    source_url="https://calendar.google.com",
                    source_label="Google Calendar",
                    agent=self.name,
                )],
                raw_data=[],
            )

        # Family calendar sync
        synced = []
        for member in family_profile:
            if member.get("consent_given") and member.get("calendar_id") and member["calendar_id"] != primary_calendar_id:
                try:
                    await sync_to_family_calendar(member["calendar_id"], event_data, True)
                    synced.append(member.get("name", "family member"))
                except CalendarActionError:
                    pass

        sync_note = f" Also synced to: {', '.join(synced)}." if synced else ""

        # Drive save
        drive_step = None
        care_plan_context = context.get("care_plan_context")
        if care_plan_context:
            try:
                doc = await save_care_plan_to_drive(care_plan_context)
                if doc.get("doc_url"):
                    for member in family_profile:
                        if member.get("consent_given") and member.get("email"):
                            await share_doc_with_email(doc["doc_id"], member["email"])
                    drive_step = SourcedStep(
                        step_number=2,
                        action="Care Plan saved to Google Drive",
                        detail="Your full care plan has been saved as a Google Doc and shared with family.",
                        source_url=doc["doc_url"],
                        source_label="Google Drive — Care Plan",
                        agent=self.name,
                    )
            except Exception as ex:
                self.logger.warning(f"Drive save failed (non-critical): {ex}")

        self.logger.info(f"ActionAgent created event {event_id}: {summary} @ {time_str}")

        # Record in the knowledge graph so future sessions remember this appointment.
        try:
            write_fact(
                context.get("user_id", ""), context.get("active_profile_id"),
                "appointment", summary,
                data={"when": time_str, "hospital": hospital, "url": html_link, "event_id": event_id},
                predicate="booked",
            )
        except Exception as ex:
            self.logger.warning(f"KG write (appointment) failed: {ex}")

        steps = [SourcedStep(
            step_number=1,
            action=summary,
            detail=f"Scheduled: {time_str}.{sync_note}",
            source_url=html_link,
            source_label="Google Calendar",
            agent=self.name,
        )]
        if drive_step:
            steps.append(drive_step)

        return AgentResult(agent_name=self.name, steps=steps, raw_data=[event])
