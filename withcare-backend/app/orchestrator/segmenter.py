"""
Task Segmenter (LLM call #1).

Turns a raw message into a list[RawTask]. It ONLY extracts structured data — it never
decides workflow, never phrases a reply, never calls a tool. Runs on every message and
is told about OPEN TASKS so it can tell "new task" from "answering a pending question".
"""
from datetime import date

from app.models.task_models import RawTask, TaskIntent
from app.services.gemini_service import generate_structured
from app.utils.logger import get_logger

logger = get_logger(__name__)

SEGMENTER_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["find_government_schemes", "find_facilities", "schedule_appointment"],
                    },
                    "raw_span": {"type": "string"},
                    "refers_to_existing_task": {
                        "type": "string",
                        "description": "task_id from OPEN TASKS if this text answers/updates that task, else empty string",
                    },
                    "depends_on_new_task": {
                        "type": "boolean",
                        "description": "true only if this task needs the RESULT of another NEW task in this same message (e.g. a schedule that needs a facility found in the same message)",
                    },
                    "slots": {
                        "type": "object",
                        "properties": {
                            "condition": {"type": "string"},
                            "location": {"type": "string", "description": "Real place/city name ONLY. Never 'near me'/'nearby'."},
                            "location_is_relative": {"type": "boolean", "description": "true if user said 'near me'/'nearby'/'close by' or gave no location"},
                            "specialty": {"type": "string"},
                            "hospital": {"type": "string", "description": "Only if user named a SPECIFIC hospital"},
                            "procedure": {"type": "string"},
                            "date": {"type": "string", "description": "YYYY-MM-DD resolved against today"},
                            "time_start": {"type": "string", "description": "HH:MM 24h, or 'flexible'"},
                            "time_end": {"type": "string"},
                            "for_member": {"type": "string"},
                            "occupation": {"type": "string", "description": "Job/employment for coverage eligibility, e.g. 'farmer', 'government employee', 'unemployed'"},
                            "annual_income": {"type": "string", "description": "Annual income or band for eligibility, e.g. '2 lakh', 'below 5 lakh'"},
                            "social_category": {"type": "string", "description": "Category for eligibility, e.g. 'BPL', 'APL', 'SC', 'ST', 'OBC', 'general'"},
                        },
                    },
                    "preferences": {
                        "type": "object",
                        "properties": {
                            "facility_ranking": {"type": "string", "enum": ["nearest", "highest_rated", "no_preference", ""]},
                            "time_of_day": {"type": "string", "enum": ["morning", "afternoon", "evening", ""]},
                            "coverage_scope": {"type": "string", "enum": ["government", "private", "both", ""], "description": "Set if the user says they want only government schemes, only private insurance, or both"},
                        },
                    },
                },
                "required": ["intent", "raw_span", "refers_to_existing_task", "depends_on_new_task", "slots", "preferences"],
            },
        }
    },
    "required": ["tasks"],
}

SEGMENTER_SYSTEM = """You are the task segmentation layer for WithCare, a healthcare navigation assistant for India.
Your ONLY job is to identify the distinct tasks in the user's message and extract slot values as structured data.
You do NOT decide what happens next, you do NOT write any reply, and you NEVER call a tool.

== TASK TYPES ==
- find_government_schemes — user wants HEALTH COVERAGE guidance: government schemes AND/OR private
  health insurance. Trigger on words like "scheme", "insurance", "policy", "mediclaim",
  "health cover", "coverage", "cashless", "premium", or "what do I/they qualify for",
  "best plans". (This one intent covers both government and private coverage.)
- find_facilities — user wants a hospital/clinic recommendation
- schedule_appointment — user wants something put on their calendar

Two clauses are the SAME task if one only adds detail to the other ("schedule an eye checkup" + "near me" = one task).
Two clauses are DIFFERENT tasks if they have separate goals ("find a cardiologist AND check CGHS eligibility" = two tasks).

== DECOMPOSITION RULE (IMPORTANT) ==
Whenever the user wants to schedule/book a procedure WITHOUT naming a specific hospital
(whether they say "near me", or say nothing about location at all), it is TWO tasks:
  1. find_facilities  (to determine WHICH hospital — carries the condition + location)
  2. schedule_appointment  (depends_on_new_task = true — needs task 1's hospital; carries procedure + date)
Emit BOTH. The find_facilities task's condition = the procedure's specialty area (e.g.
"eye check-up" -> condition "eye care"). Only skip decomposition if the user named a
SPECIFIC hospital ("schedule at Apollo") — then schedule_appointment stands alone with
hospital filled and depends_on_new_task = false.

== MATCH AGAINST OPEN TASKS ==
You are given OPEN TASKS from earlier turns (task_id, intent, known facts, what's missing).
If the new message fills a missing fact for an open task, set refers_to_existing_task = that task_id
and put ONLY the new information in slots. Otherwise refers_to_existing_task = "".

== SLOT RULES ==
- Dates: resolve "tomorrow", "next Monday", "5-july" to YYYY-MM-DD using TODAY = {today}.
- Times: "5pm" -> "17:00"; "between 5 and 8pm" -> time_start "17:00", time_end "20:00";
  "morning" -> leave time_start empty and set preferences.time_of_day = "morning" (do NOT invent 09:00).
- Location: a real place -> slots.location, location_is_relative = false.
  "near me"/"nearby"/"close by"/none given -> slots.location = "", location_is_relative = true.
  NEVER put "near me" in slots.location.
- hospital: only a specifically named hospital. "any"/"you choose"/"no idea" -> leave empty AND set
  preferences.facility_ranking = "no_preference".
- Explicit declines ("any is fine", "doesn't matter") -> set the matching preference to "no_preference".
- Coverage answers: if the user gives eligibility info (job, income, BPL/APL/SC/ST/OBC) or says
  "only government"/"private too", attach it to the OPEN coverage task (find_government_schemes) via
  refers_to_existing_task, filling slots.occupation / annual_income / social_category and/or
  preferences.coverage_scope. A message that is purely such an answer is NOT a new task.

== CARE RECIPIENT ==
You are given a CARE RECIPIENT PROFILE (who the care is for, plus their known conditions).
If the user's request needs a condition/specialty but they don't state one, AND their request
clearly concerns the recipient's existing health (e.g. "find a hospital for my mother",
"any schemes for her"), you MAY fill slots.condition from the recipient's known conditions.
Do NOT invent conditions that aren't listed, and don't attach them to unrelated requests.

Return ONLY JSON matching the schema. No prose."""


async def segment(user_message: str, open_tasks: list[dict], history: list[dict], profile: str = "") -> list[RawTask]:
    history_text = "\n".join(
        f"{'User' if h.get('role') == 'user' else 'WithCare'}: {h.get('content', '')}"
        for h in (history or [])[-8:]
    )
    open_json = _fmt(open_tasks)
    system = SEGMENTER_SYSTEM.replace("{today}", date.today().isoformat())
    prompt = (
        f"CARE RECIPIENT PROFILE:\n{profile or '(the user themselves — no extra details)'}\n\n"
        f"OPEN TASKS:\n{open_json}\n\n"
        f"CONVERSATION (last 8 turns):\n{history_text or '(none)'}\n\n"
        f"NEW USER MESSAGE:\n{user_message}"
    )
    try:
        result = await generate_structured(system, prompt, SEGMENTER_SCHEMA)
    except Exception as e:
        logger.error(f"Segmenter failed: {e}")
        return []

    raw_tasks: list[RawTask] = []
    for t in result.get("tasks", []):
        try:
            slots = {k: v for k, v in (t.get("slots") or {}).items() if v not in (None, "")}
            prefs = {k: v for k, v in (t.get("preferences") or {}).items() if v not in (None, "")}
            # location_is_relative is a bool signal — keep it even though it's not a "value"
            if (t.get("slots") or {}).get("location_is_relative"):
                slots["location_is_relative"] = True
            raw_tasks.append(RawTask(
                intent=TaskIntent(t["intent"]),
                raw_span=t.get("raw_span", ""),
                refers_to_existing_task=(t.get("refers_to_existing_task") or None),
                depends_on_new_task=bool(t.get("depends_on_new_task", False)),
                slots=slots,
                preferences=prefs,
            ))
        except Exception as e:
            logger.warning(f"Skipping malformed task {t}: {e}")

    logger.info(f"Segmenter -> {[ (r.intent.value, r.slots) for r in raw_tasks ]}")
    return raw_tasks


def _fmt(open_tasks: list[dict]) -> str:
    if not open_tasks:
        return "(none)"
    import json
    return json.dumps(open_tasks, ensure_ascii=False)
