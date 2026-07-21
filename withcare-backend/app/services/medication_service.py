"""
Medication management — track a person's medicines, auto-create dose reminders, and email a
refill alert when a medicine is about to run out.

A medicine is stored as a knowledge-graph `medication` node (so it also lives in the person's
memory + Profile view). Supply is tracked from quantity + how many are taken per day; when the
computed days-left drops to the refill threshold, a Gmail alert goes to the caregiver (once).
Adding a medicine also creates a recurring daily calendar+email reminder for each dose time.
"""
from datetime import date, datetime, timedelta

from app.agents.reminder_agent import _parse_time
from app.db.database import get_db
from app.services.memory_service import write_fact, find_nodes, delete_node
from app.tools.calendar_tool import create_calendar_event, delete_calendar_event
from app.tools.gmail_tool import send_email
from app.utils.exceptions import CalendarActionError
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── supply math ──────────────────────────────────────────────────────────────────
def _days_left(data: dict) -> int | None:
    """Days of supply remaining from start_date + quantity / (per_dose × doses per day)."""
    try:
        qty = float(data.get("quantity") or 0)
        per_dose = float(data.get("per_dose") or 1)
        n_times = len(data.get("times") or []) or 1
        per_day = per_dose * n_times
        if per_day <= 0 or qty <= 0:
            return None
        start = datetime.fromisoformat(data.get("start_date") or date.today().isoformat()).date()
        total_days = qty / per_day
        run_out = start + timedelta(days=total_days)
        return (run_out - date.today()).days
    except Exception:
        return None


def _status(data: dict) -> str:
    dl = _days_left(data)
    if dl is None:
        return "ok"
    thresh = int(data.get("refill_threshold_days") or 5)
    if dl <= 0:
        return "out"
    if dl <= thresh:
        return "refill_soon"
    return "ok"


def _serialize(node: dict) -> dict:
    d = node.get("data") or {}
    dl = _days_left(d)
    run_out = None
    if d.get("start_date"):
        try:
            qty = float(d.get("quantity") or 0); per_day = float(d.get("per_dose") or 1) * (len(d.get("times") or []) or 1)
            if per_day > 0:
                run_out = (datetime.fromisoformat(d["start_date"]).date() + timedelta(days=qty / per_day)).isoformat()
        except Exception:
            run_out = None
    return {
        "id": node["id"], "name": node["name"],
        "dose": d.get("dose", ""), "times": d.get("times") or [],
        "per_dose": d.get("per_dose", 1), "quantity": d.get("quantity", 0),
        "refill_threshold_days": d.get("refill_threshold_days", 5),
        "recipient": d.get("recipient", ""), "profile_id": node.get("profile_id"),
        "days_left": dl, "run_out_date": run_out, "status": _status(d),
    }


def _user_email(user_id: str) -> str:
    db = get_db()
    row = db.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
    db.close()
    return (row["email"] if row else "") or ""


# ── dose reminders ────────────────────────────────────────────────────────────────
async def _create_dose_reminder(user_id, profile_id, recipient, email, med_name, dose, time_str, cal_token):
    """One recurring daily calendar+email reminder for a single dose time. Returns its ids."""
    start_iso = f"{date.today().isoformat()}T{time_str}:00"
    end_iso = (datetime.fromisoformat(start_iso) + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S")
    label = f"Take {med_name}" + (f" ({dose})" if dose else "")
    event_id, link = "", ""
    try:
        ev = await create_calendar_event(
            calendar_id="primary", summary=label,
            description=f"WithCare medication reminder for {recipient}.",
            start_datetime=start_iso, end_datetime=end_iso,
            attendee_emails=[email] if email else None,
            reminder_minutes=[0], recurrence="RRULE:FREQ=DAILY", access_token=cal_token,
        )
        event_id, link = ev.get("event_id", ""), ev.get("html_link", "")
    except CalendarActionError as e:
        logger.warning(f"medication reminder calendar create failed: {e}")
    # Distinct KG reminder node per time (name carries the time so multiple doses don't dedupe).
    rid = write_fact(user_id, profile_id, "reminder", f"{label} — {time_str}",
                     data={"time": time_str, "recurrence": "daily", "lead_minutes": 0,
                           "recipient": recipient, "event_id": event_id, "calendar_id": "primary",
                           "medication": med_name}, predicate="has_reminder")
    return {"reminder_id": rid, "event_id": event_id}


# ── public API ─────────────────────────────────────────────────────────────────────
async def add_medication(user_id, profile_id, recipient, email, name, dose, times, per_dose,
                         quantity, refill_threshold_days, tokens=None):
    tokens = tokens or {}
    cal_token = tokens.get("calendar")
    times = [_parse_time(t) for t in (times or []) if str(t).strip()] or ["09:00"]

    # Create a dose reminder per time; keep their ids so we can clean up on delete.
    reminders = []
    for t in times:
        reminders.append(await _create_dose_reminder(user_id, profile_id, recipient, email, name, dose, t, cal_token))

    data = {
        "dose": dose or "", "times": times, "per_dose": per_dose or 1,
        "quantity": quantity or 0, "refill_threshold_days": refill_threshold_days or 5,
        "start_date": date.today().isoformat(), "recipient": recipient or "", "email": email or "",
        "reminder_ids": [r["reminder_id"] for r in reminders],
        "event_ids": [r["event_id"] for r in reminders if r["event_id"]],
        "alerted": False,
    }
    write_fact(user_id, profile_id, "medication", name, data=data, predicate="takes", unique="name")
    node = next((n for n in find_nodes(user_id, "medication", profile_id) if n["name"] == name), None)
    return _serialize(node) if node else {"name": name, **data, "status": _status(data)}


async def list_medications(user_id, profile_id=None, tokens=None):
    """List medications (optionally for one profile) and fire any due refill alerts."""
    nodes = find_nodes(user_id, "medication", profile_id)
    tokens = tokens or {}
    for n in nodes:
        await _maybe_alert(user_id, n, tokens)
    # re-read so the alerted flag is reflected
    nodes = find_nodes(user_id, "medication", profile_id)
    return [_serialize(n) for n in nodes]


async def _maybe_alert(user_id, node, tokens):
    data = node.get("data") or {}
    if data.get("alerted"):
        return
    if _status(data) not in ("out", "refill_soon"):
        return
    to = _user_email(user_id)
    if not to:
        return
    dl = _days_left(data)
    when = "has run out" if (dl is not None and dl <= 0) else f"is running low ({dl} day(s) left)"
    r = await send_email(
        to, f"Refill needed: {node['name']}",
        f"Heads up — {data.get('recipient') or 'your'} medicine \"{node['name']}\""
        + (f" ({data['dose']})" if data.get("dose") else "") + f" {when}. Time to reorder.\n\n— WithCare",
        access_token=tokens.get("gmail"),
    )
    if r.get("ok"):
        data["alerted"] = True
        write_fact(user_id, node.get("profile_id"), "medication", node["name"], data=data,
                   predicate="takes", unique="name")
        logger.info(f"refill alert sent for {node['name']} -> {to}")


async def refill_medication(user_id, med_id, quantity, tokens=None):
    """Mark a medicine restocked: reset the supply clock and clear the alert flag."""
    node = _get(user_id, med_id)
    if not node:
        return None
    data = node["data"]
    data["quantity"] = quantity if quantity is not None else data.get("quantity", 0)
    data["start_date"] = date.today().isoformat()
    data["alerted"] = False
    write_fact(user_id, node.get("profile_id"), "medication", node["name"], data=data,
               predicate="takes", unique="name")
    return _serialize({**node, "data": data})


async def delete_medication(user_id, med_id, tokens=None):
    """Delete a medicine plus the dose reminders (and calendar events) it created."""
    node = _get(user_id, med_id)
    if not node:
        return False
    data = node["data"]
    cal_token = (tokens or {}).get("calendar")
    for ev in data.get("event_ids") or []:
        if ev:
            await delete_calendar_event("primary", ev, access_token=cal_token)
    for rid in data.get("reminder_ids") or []:
        delete_node(user_id, rid)
    delete_node(user_id, med_id)
    return True


def _get(user_id, med_id):
    from app.services.memory_service import get_node
    return get_node(med_id, user_id)
