"""
Emergency info + SOS.

- emergency_summary(): the "show the doctor" sheet for a person — age, blood group, allergies,
  conditions, current medicines, and family contacts. Built from the profile + knowledge graph.
- send_sos(): email that summary as an urgent alert to the person's family members (the other
  care profiles that have an email) and the caregiver, with a location link if available.
"""
from datetime import datetime

from app.db.database import get_db
from app.services.memory_service import find_nodes
from app.tools.gmail_tool import send_email
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _profiles(user_id):
    db = get_db()
    rows = [dict(r) for r in db.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchall()]
    db.close()
    return rows


def _user(user_id):
    db = get_db()
    row = db.execute("SELECT name, email FROM users WHERE id=?", (user_id,)).fetchone()
    db.close()
    return dict(row) if row else {"name": "", "email": ""}


def emergency_summary(user_id, profile_id):
    profs = _profiles(user_id)
    person = next((p for p in profs if p["id"] == profile_id), None)
    if not person:
        return None
    meds = [n["name"] for n in find_nodes(user_id, "medication", profile_id)]
    contacts = [
        {"name": p["name"], "relation": p.get("relation", ""), "email": p.get("email", "")}
        for p in profs if p["id"] != profile_id and p.get("email")
    ]
    return {
        "profile_id": profile_id,
        "person": person["name"],
        "age": person.get("age"),
        "gender": person.get("gender", ""),
        "blood_group": person.get("blood_group", ""),
        "allergies": person.get("allergies", ""),
        "conditions": person.get("conditions", ""),
        "medications": meds,
        "email": person.get("email", ""),
        "contacts": contacts,
    }


async def send_sos(user_id, profile_id, location="", coordinates=None, tokens=None):
    s = emergency_summary(user_id, profile_id)
    if not s:
        return None
    tokens = tokens or {}
    caregiver = _user(user_id)

    # Recipients: family members (other profiles with email) + the caregiver.
    recips = {c["email"] for c in s["contacts"] if c["email"]}
    if caregiver.get("email"):
        recips.add(caregiver["email"])
    recips = [r for r in recips if r]

    if coordinates and coordinates.get("lat"):
        loc_line = f"Location: https://www.google.com/maps?q={coordinates['lat']},{coordinates['lng']}\n"
    elif location:
        loc_line = f"Location: {location}\n"
    else:
        loc_line = ""

    body = (
        "EMERGENCY ALERT from WithCare\n\n"
        f"{s['person']} may need urgent help.\n"
        f"Time: {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
        f"{loc_line}\n"
        "Key medical info:\n"
        f"- Age: {s['age'] if s['age'] is not None else '-'}\n"
        f"- Blood group: {s['blood_group'] or '-'}\n"
        f"- Conditions: {s['conditions'] or '-'}\n"
        f"- Allergies: {s['allergies'] or '-'}\n"
        f"- Current medicines: {', '.join(s['medications']) if s['medications'] else '-'}\n\n"
        "Please check on them now, or call emergency services (108 in India)."
    )
    subject = f"EMERGENCY: {s['person']} needs help"

    notified = []
    for to in recips:
        r = await send_email(to, subject, body, access_token=tokens.get("gmail"))
        if r.get("ok"):
            notified.append(to)
    logger.info(f"SOS for {s['person']}: notified {len(notified)}/{len(recips)}")
    return {
        "person": s["person"],
        "recipients": recips,
        "notified": notified,
        "emailed": len(notified) > 0,
        "contact_names": [c["name"] for c in s["contacts"]],
    }
