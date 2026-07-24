"""
Routines — personal care routines a user keeps for themselves or a family member: workout,
diet, skincare, hospital check-ups, sleep, hydration, eye care, physiotherapy, or anything
custom. A routine can be added MANUALLY or DRAFTED by Gemini, and can optionally drop a
recurring Google Calendar + email reminder (like medication dose reminders).

Stored as a knowledge-graph `routine` node so it also lives in the person's memory + Profile
view. The existing rich diet_plan / workout_plan nodes are folded into the same list (shown as
Diet / Workout routines) so everything lives in one place.
"""
import json
from datetime import date, datetime, timedelta

from app.agents.reminder_agent import _parse_time
from app.db.database import get_db
from app.services.gemini_service import generate_text
from app.services.memory_service import (
    delete_node, get_node, get_profile_memory, write_fact,
)
from app.tools.calendar_tool import create_calendar_event, delete_calendar_event
from app.utils.exceptions import CalendarActionError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# category key -> display label (kept in sync with the frontend CATS map)
CATEGORIES = {
    "workout": "Workout",
    "diet": "Diet",
    "skincare": "Skincare",
    "checkup": "Health check-ups",
    "sleep": "Sleep",
    "hydration": "Hydration",
    "eyecare": "Eye care",
    "physio": "Physiotherapy",
    "other": "Routine",
}

# Legacy plan node types shown alongside routines, mapped to a routine category.
_LEGACY = {"workout_plan": "workout", "diet_plan": "diet"}

_RRULE = {"daily": "RRULE:FREQ=DAILY", "weekly": "RRULE:FREQ=WEEKLY", "monthly": "RRULE:FREQ=MONTHLY"}

# Sensible default cadence per category (used when Gemini drafts one).
_DEFAULT_FREQ = {
    "skincare": "Twice daily (AM & PM)", "diet": "Daily", "workout": "Weekly",
    "sleep": "Nightly", "hydration": "Throughout the day", "checkup": "Periodic",
    "eyecare": "Daily", "physio": "Daily", "other": "Daily",
}


# ── serialization ──────────────────────────────────────────────────────────────────
def _serialize_routine(node: dict) -> dict:
    d = node.get("data") or {}
    return {
        "id": node["id"], "name": node["name"],
        "category": d.get("category") or "other",
        "content": d.get("content") or "",
        "frequency": d.get("frequency") or "",
        "times": d.get("times") or [],
        "recipient": d.get("recipient") or "",
        "reminds": bool(d.get("event_ids")),
        "profile_id": node.get("profile_id"),
        "profile_name": node.get("profile_name"),
        "updated_at": node.get("updated_at"),
        "kind": "routine",
    }


def _serialize_legacy(node: dict) -> dict:
    d = node.get("data") or {}
    return {
        "id": node["id"], "name": node["name"],
        "category": _LEGACY.get(node["type"], "other"),
        "content": d.get("plan") or "",
        "frequency": "Weekly plan",
        "times": [], "recipient": "", "reminds": False,
        "profile_id": node.get("profile_id"),
        "profile_name": node.get("profile_name"),
        "updated_at": node.get("updated_at"),
        "kind": node["type"],  # workout_plan / diet_plan — so the UI can render day-by-day cards
    }


# ── reads ──────────────────────────────────────────────────────────────────────────
def list_routines(user_id: str, profile_id: str | None = None) -> list[dict]:
    """All routines for a user (optionally one profile), newest first, with legacy diet/workout
    plans folded in. Joins profiles so each item carries the person's name."""
    types = ("routine", "workout_plan", "diet_plan")
    db = get_db()
    ph = ",".join("?" * len(types))
    sql = (
        f"SELECT n.id, n.type, n.name, n.data, n.profile_id, n.updated_at, "
        f"       p.name AS profile_name, p.kind AS profile_kind "
        f"FROM kg_nodes n LEFT JOIN profiles p ON n.profile_id = p.id "
        f"WHERE n.user_id = ? AND n.type IN ({ph})"
    )
    params: list = [user_id, *types]
    if profile_id:
        sql += " AND n.profile_id IS ?"
        params.append(profile_id)
    sql += " ORDER BY n.updated_at DESC"
    rows = db.execute(sql, params).fetchall()
    db.close()

    out = []
    for r in rows:
        d = dict(r)
        try:
            d["data"] = json.loads(d.get("data") or "{}")
        except Exception:
            d["data"] = {}
        out.append(_serialize_legacy(d) if d["type"] in _LEGACY else _serialize_routine(d))
    return out


# ── reminders ──────────────────────────────────────────────────────────────────────
async def _create_routine_reminder(user_id, profile_id, recipient, email, routine_name,
                                    time_str, recurrence, cal_token):
    """One recurring calendar + email reminder for a routine at a given time. Returns its ids."""
    start_iso = f"{date.today().isoformat()}T{time_str}:00"
    end_iso = (datetime.fromisoformat(start_iso) + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S")
    rrule = _RRULE.get((recurrence or "daily").lower(), _RRULE["daily"])
    event_id = ""
    try:
        ev = await create_calendar_event(
            calendar_id="primary", summary=routine_name,
            description=f"WithCare routine reminder for {recipient or 'you'}.",
            start_datetime=start_iso, end_datetime=end_iso,
            attendee_emails=[email] if email else None,
            reminder_minutes=[0], recurrence=rrule, access_token=cal_token,
        )
        event_id = ev.get("event_id", "")
    except CalendarActionError as e:
        logger.warning(f"routine reminder calendar create failed: {e}")
    rid = write_fact(user_id, profile_id, "reminder", f"{routine_name} — {time_str}",
                     data={"time": time_str, "recurrence": (recurrence or "daily").lower(),
                           "lead_minutes": 0, "recipient": recipient, "event_id": event_id,
                           "calendar_id": "primary", "routine": routine_name},
                     predicate="has_reminder")
    return {"reminder_id": rid, "event_id": event_id}


# ── writes ─────────────────────────────────────────────────────────────────────────
async def add_routine(user_id, profile_id, recipient, email, name, category, content,
                      frequency, times, recurrence="daily", remind=False, tokens=None):
    """Create (or replace, by name) a routine for a person. If `remind` and times are given,
    also drops a recurring calendar+email reminder for each time."""
    tokens = tokens or {}
    cal_token = tokens.get("calendar")
    category = category if category in CATEGORIES else "other"
    times = [_parse_time(t) for t in (times or []) if str(t).strip()]

    reminders = []
    if remind and times:
        for t in times:
            reminders.append(await _create_routine_reminder(
                user_id, profile_id, recipient, email, name, t, recurrence, cal_token))

    data = {
        "category": category, "content": content or "", "frequency": frequency or "",
        "times": times, "recurrence": (recurrence or "daily").lower() if reminders else "",
        "recipient": recipient or "", "email": email or "",
        "reminder_ids": [r["reminder_id"] for r in reminders],
        "event_ids": [r["event_id"] for r in reminders if r["event_id"]],
    }
    node_id = write_fact(user_id, profile_id, "routine", name, data=data,
                         predicate="follows_routine", unique="name")
    node = get_node(node_id, user_id)
    return _serialize_routine(node) if node else {"id": node_id, "name": name, **data}


async def delete_routine(user_id, routine_id, tokens=None):
    """Delete a routine (or a legacy plan) plus any reminders/calendar events it created."""
    node = get_node(routine_id, user_id)
    if not node:
        return False
    data = node.get("data") or {}
    cal_token = (tokens or {}).get("calendar")
    for ev in data.get("event_ids") or []:
        if ev:
            await delete_calendar_event("primary", ev, access_token=cal_token)
    for rid in data.get("reminder_ids") or []:
        delete_node(user_id, rid)
    delete_node(user_id, routine_id)
    return True


# ── Gemini draft ───────────────────────────────────────────────────────────────────
_DRAFT_SKILL = (
    "You are WithCare, a warm care assistant for India. Draft a concise, practical personal "
    "CARE ROUTINE. Return ONLY the routine itself as short markdown: a one-line intro sentence, "
    "then 4-7 steps as '**Label:** detail' bullet lines (group into Morning / Evening if that "
    "fits). Keep it safe and general wellbeing guidance — NEVER diagnose, prescribe medicines, "
    "or give clinical treatment; for check-ups, say what to track and how often to see a "
    "professional. Honour any allergy, condition, or dietary rule you are told. No preamble, no "
    "sign-off, no disclaimer."
)


async def draft_routine(user_id, profile_id, category, note=""):
    """One Gemini call → a routine draft {name, category, content, frequency}."""
    category = category if category in CATEGORIES else "other"
    label = CATEGORIES[category]
    memory = get_profile_memory(profile_id) if profile_id else ""
    prompt = (
        f"Draft a {label.lower()} routine.\n"
        f"About the person: {memory or '(no details on file)'}\n"
        + (f"Extra request from the user: {note}\n" if note else "")
        + "Tailor it to the person above and honour anything health-related you see."
    )
    try:
        content = (await generate_text(_DRAFT_SKILL, prompt)).strip()
    except Exception as e:
        logger.warning(f"routine draft failed: {e}")
        content = ""
    return {
        "name": f"{label} routine",
        "category": category, "content": content,
        "frequency": _DEFAULT_FREQ.get(category, "Daily"),
    }
