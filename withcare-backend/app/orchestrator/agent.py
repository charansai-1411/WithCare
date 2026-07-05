"""
WithCareAgent — the agentic core (behind settings.use_agent).

An LLM function-calling loop that reasons over the person's KG memory + a small toolbox.
Guardrails are enforced by CONTROL FLOW, not by trusting the model:
  * clinical gate      — refuse diagnosis/treatment before the loop (code).
  * confirmation gate  — the ONLY path that executes an irreversible action; the model can
                         only *stage* one (persisted in DB, keyed by session).
  * step cap           — bounded tool loop.
  * arg validation     — missing required args -> the model is told to ask.

Emits the same StreamChunk contract as the pipeline (thinking/step/clarify/done/error), so the
frontend and eval suite are unchanged.
"""
import json
import re
from datetime import date, datetime, timedelta
from typing import AsyncGenerator

from google.genai import types

from app.agents.action_agent import ActionAgent
from app.agents.diet_agent import DietAgent
from app.agents.facility_agent import FacilityAgent
from app.agents.product_agent import ProductAgent
from app.agents.reminder_agent import ReminderAgent
from app.agents.scheme_agent import SchemeAgent
from app.agents.workout_agent import WorkoutAgent
from app.config import settings
from app.db.database import get_db
from app.models.request_models import ChatRequest
from app.models.response_models import SourcedStep, StreamChunk
from app.agents.reminder_agent import _RRULE, _parse_time
from app.db.database import get_db as _get_db
from app.orchestrator.router import classify_intent
from app.services.gemini_service import build_tools, generate_with_tools
from app.services.grounding import renumber_steps
from app.services.memory_service import (
    delete_node, find_nodes, get_profile_memory, resolve_recipient,
    sync_profile_to_kg, write_fact,
)
from app.services.skills import load_skill
from app.tools.calendar_tool import delete_calendar_event, update_calendar_event
from app.utils.exceptions import ClinicalRequestError
from app.utils.logger import get_logger

logger = get_logger(__name__)

_YES = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed",
        "go ahead", "book it", "do it", "please do", "sounds good", "yes please", "book", "proceed"}
_NO = {"no", "nope", "cancel", "not yet", "wait", "stop", "don't", "dont", "change"}


def classify_yes_no(message: str) -> str:
    norm = re.sub(r"[^a-z\s]", "", message.lower()).strip()
    if norm in _YES:
        return "yes"
    if norm in _NO:
        return "no"
    return "ambiguous"


# ── Tool declarations (what the model sees) ──────────────────────────────────────
TOOL_DECLS = [
    {
        "name": "find_facilities",
        "description": "Find places near a location for health, fitness or wellbeing — hospitals & clinics, and also gyms, yoga studios, parks, swimming pools, playgrounds and sports facilities. Read-only.",
        "parameters": {
            "type": "object",
            "properties": {
                "condition": {"type": "string", "description": "What to find, e.g. 'eye care', 'cardiology', 'gym', 'park', 'swimming pool', 'sports ground'"},
                "location": {"type": "string", "description": "City/area; use the user's known location for 'near me'"},
                "specialty": {"type": "string", "description": "Medical specialty if known"},
            },
            "required": ["condition"],
        },
    },
    {
        "name": "find_coverage",
        "description": "Search Indian GOVERNMENT schemes AND PRIVATE insurance a person may qualify for. Read-only.",
        "parameters": {
            "type": "object",
            "properties": {
                "condition": {"type": "string", "description": "Health condition(s); use memory if not restated"},
                "location": {"type": "string"},
                "coverage_scope": {"type": "string", "enum": ["both", "government", "private"], "description": "default 'both'"},
                "occupation": {"type": "string"},
                "annual_income": {"type": "string"},
                "social_category": {"type": "string", "description": "BPL/APL/SC/ST/OBC/general"},
            },
            "required": ["condition"],
        },
    },
    {
        "name": "schedule_appointment",
        "description": ("Propose putting a timed EVENT on the user's calendar — either a health "
                        "appointment OR any activity they want to block time for (gym, a walk, study, "
                        "a meeting). This is the tool for 'schedule …', 'block …', 'put … on my "
                        "calendar'. It does NOT add it yet — it stages the event and the user must "
                        "confirm afterward. Use time_start AND time_end for the block, and recurrence "
                        "for repeating events (e.g. gym every day). For a health visit with no known "
                        "hospital, call find_facilities first and pass the top one. Prefer this over "
                        "set_reminder whenever the user wants the activity itself blocked on the "
                        "calendar (set_reminder is only for a notification nudge)."),
        "parameters": {
            "type": "object",
            "properties": {
                "procedure": {"type": "string", "description": "What to schedule — a procedure ('eye check-up') or an activity ('Gym', 'Morning walk')."},
                "date": {"type": "string", "description": "YYYY-MM-DD (start date; first day for a recurring event)"},
                "time_start": {"type": "string", "description": "HH:MM 24h"},
                "time_end": {"type": "string", "description": "HH:MM 24h"},
                "hospital": {"type": "string", "description": "Optional — clinic/hospital for a health visit; leave empty for a personal activity."},
                "recurrence": {"type": "string", "enum": ["none", "daily", "weekly"], "description": "Repeat the event — 'daily' for e.g. a gym block every day, else 'none'."},
                "repeat_until": {"type": "string", "description": "YYYY-MM-DD — the LAST date a recurring event should repeat (inclusive). For 'for the next one week' set it to 6 days after the start date; omit for an open-ended repeat. Uses TODAY to compute."},
                "for_member": {"type": "string"},
            },
            "required": ["procedure", "date"],
        },
    },
    {
        "name": "set_reminder",
        "description": ("Set a calendar + email reminder for a SPECIFIC person (recurring or "
                        "one-time). Delivered to that person only (their calendar + email)."),
        "parameters": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Who it's for: 'mother','wife', a name, or empty for the active person"},
                "message": {"type": "string", "description": "What to remind them"},
                "date": {"type": "string", "description": "YYYY-MM-DD for one-time; empty for recurring (starts today)"},
                "time": {"type": "string", "description": "HH:MM 24h"},
                "recurrence": {"type": "string", "enum": ["none", "daily", "weekly", "monthly"]},
                "lead_minutes": {"type": "integer", "description": "Notify this many minutes before (default 10)"},
            },
            "required": ["message", "time"],
        },
    },
    {
        "name": "plan_workout",
        "description": "Create a weekly workout plan for the active person, tailored to their "
                       "age/gender/weight/height and conditions. If the user asks for BOTH a "
                       "workout and a diet plan, call this FIRST so the diet can be built to fuel it. "
                       "You MUST know the person's goal before calling — ask if it isn't already clear.",
        "parameters": {"type": "object", "properties": {
            "goal": {"type": "string", "description": "The person's fitness goal for this plan. "
                     "One of: 'weight loss', 'weight gain', 'muscle gain', 'maintain' (normal/general "
                     "fitness), or a specific focus like 'mobility'. REQUIRED — if the user hasn't said "
                     "it and memory doesn't have it, ASK them first; never guess."},
            "person": {"type": "string", "description": "Who the plan is for. Omit for the active "
                       "person, or give the NAME/relation of another care profile (e.g. 'Amma', "
                       "'mother', 'father') to make it for a family member. The user can manage plans "
                       "for anyone in their care."},
            "adjustment": {"type": "string", "description": "OPTIONAL. If the user is asking to "
                       "CHANGE an existing plan (e.g. 'make it only 4 days', 'add more cardio', "
                       "'easier'), put the change here — the current plan is regenerated with it "
                       "applied and replaces the old one. Leave empty for a brand-new plan."}},
            "required": ["goal"]},
    },
    {
        "name": "plan_diet",
        "description": "Create a 7-day diet plan for the active person or pet, tailored to their "
                       "age/gender/weight/height and conditions. It automatically coordinates with "
                       "the person's existing workout plan (fuels training days), so prefer calling "
                       "plan_workout before this when the user wants both. "
                       "You MUST know the person's goal before calling — ask if it isn't already clear.",
        "parameters": {"type": "object", "properties": {
            "goal": {"type": "string", "description": "The person's goal for this plan. One of: "
                     "'weight loss', 'weight gain', 'muscle gain', 'maintain' (normal), or a specific "
                     "focus like 'diabetes control'. REQUIRED — for a person (not a pet), if the user "
                     "hasn't said it and memory doesn't have it, ASK first; never guess."},
            "person": {"type": "string", "description": "Who the plan is for. Omit for the active "
                       "person/pet, or give the NAME/relation of another care profile (e.g. 'Amma', "
                       "'Nemo', 'father') to make it for a family member or pet."},
            "adjustment": {"type": "string", "description": "OPTIONAL. If the user is asking to "
                       "CHANGE an existing diet plan (e.g. 'make it vegetarian', 'no dairy', "
                       "'add more protein', 'cheaper'), put the change here — the current plan is "
                       "regenerated with it applied and replaces the old one. Empty for a new plan."}},
            "required": ["goal"]},
    },
    {
        "name": "update_reminder",
        "description": "Change an EXISTING reminder for a person (its time, message, or recurrence). "
                       "Updates the saved reminder AND its Google Calendar event. Use when the user "
                       "says things like 'change my tablet reminder to 2pm' or 'make the water "
                       "reminder weekly'.",
        "parameters": {"type": "object", "properties": {
            "recipient": {"type": "string", "description": "Whose reminder: 'mother','wife', a name, or empty for the active person"},
            "match": {"type": "string", "description": "A few words identifying WHICH reminder to change (e.g. 'tablet', 'water'). Omit to target their most recent reminder."},
            "time": {"type": "string", "description": "New time HH:MM 24h (omit to keep)"},
            "message": {"type": "string", "description": "New reminder text (omit to keep)"},
            "recurrence": {"type": "string", "enum": ["none", "daily", "weekly", "monthly"], "description": "New recurrence (omit to keep)"},
            "lead_minutes": {"type": "integer", "description": "New minutes-before (omit to keep)"}},
            "required": []},
    },
    {
        "name": "cancel_reminder",
        "description": "Delete/stop an EXISTING reminder for a person, removing its Google Calendar "
                       "event too. Use for 'stop/cancel/delete my X reminder'.",
        "parameters": {"type": "object", "properties": {
            "recipient": {"type": "string", "description": "Whose reminder: 'mother', a name, or empty for the active person"},
            "match": {"type": "string", "description": "A few words identifying WHICH reminder (e.g. 'tablet'). Omit to target their most recent reminder."}},
            "required": []},
    },
    {
        "name": "update_profile",
        "description": "Update a care profile's stored details (age, weight, height, gender, "
                       "conditions, notes, email). Use when the user states a new/changed fact about "
                       "a person, e.g. 'I now weigh 68kg', 'update mother's conditions to add "
                       "arthritis', 'my email is x@y.com'. This keeps the profile and memory in sync.",
        "parameters": {"type": "object", "properties": {
            "person": {"type": "string", "description": "Who to update: 'mother', a name, or empty for the active person"},
            "age": {"type": "integer"},
            "weight": {"type": "number", "description": "kg"},
            "height": {"type": "number", "description": "cm"},
            "gender": {"type": "string"},
            "conditions": {"type": "string", "description": "Full comma-separated conditions list (replaces the stored one)"},
            "notes": {"type": "string"},
            "email": {"type": "string"}},
            "required": []},
    },
    {
        "name": "remember",
        "description": "Save a durable fact WithCare should remember about a person (an allergy, a "
                       "preference, a medication, a hospital). Use for 'remember that I'm allergic to "
                       "penicillin', 'note that Amma prefers vegetarian food'.",
        "parameters": {"type": "object", "properties": {
            "person": {"type": "string", "description": "Who it's about: 'mother', a name, or empty for the active person"},
            "category": {"type": "string", "enum": ["condition", "medication", "hospital", "health_metric", "note"], "description": "Kind of fact (use 'note' for anything else, e.g. an allergy or preference)"},
            "fact": {"type": "string", "description": "The fact to remember, short (e.g. 'Allergic to penicillin')"}},
            "required": ["fact"]},
    },
    {
        "name": "forget",
        "description": "Remove a remembered fact about a person (correcting the memory). Use for "
                       "'forget that I have diabetes', 'remove the penicillin allergy note'.",
        "parameters": {"type": "object", "properties": {
            "person": {"type": "string", "description": "Who it's about: 'mother', a name, or empty for the active person"},
            "match": {"type": "string", "description": "A few words identifying the fact to forget (e.g. 'penicillin', 'diabetes')"}},
            "required": ["match"]},
    },
    {
        "name": "find_products",
        "description": "Price-compare a PRODUCT the user wants to buy — a health device (BP monitor, "
                       "glucometer, thermometer, mask), a supplement, or a medicine THEY NAMED — "
                       "across Indian shopping & pharmacy sites (Amazon, Flipkart, PharmEasy, Apollo, "
                       "MedPlus, 1mg). Returns listings sorted cheapest→costliest with price, platform "
                       "and a buy link. Use when the user asks where/how to buy something, the cheapest "
                       "price, or to compare prices. Only compares what they named — never suggests or "
                       "doses a medicine.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The exact product to price-compare, e.g. "
                      "'Omron HEM-7120 BP monitor', 'Dolo 650 tablet strip', 'Accu-Chek glucometer'."}},
            "required": ["query"]},
    },
    {
        "name": "search_documents",
        "description": "Search the user's uploaded documents (insurance policies, medical/lab "
                       "reports, prescriptions, etc.) and get the relevant excerpts to answer from. "
                       "Use this whenever the user asks about 'my policy/insurance/report/"
                       "prescription/document' or anything that would be in an uploaded file "
                       "(coverage limits, sum insured, test values, dosage, dates). Answer ONLY from "
                       "the returned excerpts and cite the document label.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What to look for, phrased for retrieval."},
            "label": {"type": "string", "description": "Optional — restrict to documents whose "
                      "label/tag matches (e.g. 'Amma insurance'). Omit to search all documents."}},
            "required": ["query"]},
    },
]

def _strict_user_token() -> bool:
    """In production, connector actions REQUIRE the user's own OAuth token — never the
    shared token.json — so nothing lands in the developer's account and users can't
    collide. In local dev the token.json fallback stays enabled so testing works."""
    return (settings.environment or "").lower() == "production"


_AGENT_FOR_TOOL = {
    "find_facilities": ("facility_agent", "Finding hospitals and facilities nearby..."),
    "find_coverage": ("scheme_agent", "Searching schemes and insurance..."),
    "schedule_appointment": ("action_agent", "Preparing your appointment..."),
    "set_reminder": ("reminder_agent", "Setting the reminder..."),
    "plan_workout": ("workout_agent", "Designing a workout plan..."),
    "plan_diet": ("diet_agent", "Designing a diet plan..."),
    "update_reminder": ("reminder_agent", "Updating the reminder..."),
    "cancel_reminder": ("reminder_agent", "Removing the reminder..."),
    "update_profile": ("orchestrator", "Updating the profile..."),
    "remember": ("orchestrator", "Saving to memory..."),
    "forget": ("orchestrator", "Updating memory..."),
    "find_products": ("product_agent", "Comparing prices across stores..."),
    "search_documents": ("reader", "Searching your documents..."),
}


class WithCareAgent:
    def __init__(self):
        self.facility_agent = FacilityAgent()
        self.scheme_agent = SchemeAgent()
        self.action_agent = ActionAgent()
        self.reminder_agent = ReminderAgent()
        self.workout_agent = WorkoutAgent()
        self.diet_agent = DietAgent()
        self.product_agent = ProductAgent()
        self.tools = build_tools(TOOL_DECLS)
        self.skill = load_skill("orchestrator") or "You are WithCare, a healthcare navigation assistant for India."
        logger.info("WithCareAgent (agentic core) initialized")

    # ── pending action persistence (confirmation gate) ──────────────────────────
    @staticmethod
    def _get_pending(sid: str) -> dict | None:
        db = get_db()
        row = db.execute("SELECT * FROM pending_actions WHERE session_id=?", (sid,)).fetchone()
        db.close()
        if not row:
            return None
        d = dict(row)
        d["args"] = json.loads(d.get("args") or "{}")
        d["base_ctx"] = json.loads(d.get("base_ctx") or "{}")
        return d

    @staticmethod
    def _stage_pending(sid: str, tool: str, args: dict, summary: str, base_ctx: dict):
        db = get_db()
        db.execute(
            "INSERT INTO pending_actions(session_id, tool, args, summary, base_ctx) VALUES(?,?,?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET tool=excluded.tool, args=excluded.args, "
            "summary=excluded.summary, base_ctx=excluded.base_ctx, created_at=datetime('now')",
            (sid, tool, json.dumps(args), summary, json.dumps(base_ctx)),
        )
        db.commit()
        db.close()

    @staticmethod
    def _clear_pending(sid: str):
        db = get_db()
        db.execute("DELETE FROM pending_actions WHERE session_id=?", (sid,))
        db.commit()
        db.close()

    # ── main entry ──────────────────────────────────────────────────────────────
    async def handle(self, request: ChatRequest) -> AsyncGenerator[StreamChunk, None]:
        sid = request.session_id
        family = [m.model_dump() for m in (request.family_profile or [])]
        active_pid = family[0].get("id") if family else None
        memory = get_profile_memory(active_pid) if active_pid else ""
        base_ctx = {
            "coordinates": request.coordinates.model_dump() if request.coordinates else None,
            "family_profile": family,
            "for_member": request.for_member or "self",
            "session_id": sid,
            "user_id": request.user_id or "",
            "active_profile_id": active_pid,
            "location": request.location or "",
            "full_context": request.message,
            "memory": memory,
            "connectors": [c.lower() for c in (request.connected_connectors or [])],
            # Per-user OAuth access tokens — actions run on the user's OWN Google account.
            "connector_tokens": {k.lower(): v for k, v in (request.connector_tokens or {}).items()},
        }

        # ── GUARD: confirmation gate — the ONLY path that executes an irreversible action ──
        pending = self._get_pending(sid)
        if pending:
            decision = classify_yes_no(request.message)
            if decision == "yes":
                # Strict: with real OAuth, the booking must run on the user's OWN fresh token.
                # If it expired between staging and confirming, refuse — never use the dev account.
                if _strict_user_token() and not base_ctx["connector_tokens"].get("calendar"):
                    self._clear_pending(sid)
                    yield StreamChunk(type="error", agent="action_agent",
                                      content="Your Google Calendar session has expired. Please reconnect "
                                              "Google Calendar on the Connectors page, then ask me to book again.")
                    return
                yield StreamChunk(type="thinking", content="Booking your appointment...", agent="action_agent")
                # Use the freshest per-user token from THIS "yes" request.
                pending["base_ctx"]["connector_tokens"] = base_ctx["connector_tokens"]
                async for chunk in self._commit(pending):
                    yield chunk
                self._clear_pending(sid)
                return
            if decision == "no":
                self._clear_pending(sid)
                # fall through — the agent handles "no, change X" conversationally

        # ── GUARD: clinical refusal ──
        intent = await classify_intent(request.message, [], [h.model_dump() for h in (request.history or [])])
        if intent.get("is_clinical"):
            yield StreamChunk(type="error", content=ClinicalRequestError.message, agent="orchestrator")
            return

        yield StreamChunk(type="thinking", content="Understanding what you need...", agent="orchestrator")

        # ── Agentic loop ──
        loc = base_ctx.get("location") or (
            "(GPS coordinates available — 'near me' is resolvable, pass the known city or 'near me')"
            if base_ctx.get("coordinates") else "")
        system = (f"{self.skill}\n\n== TODAY == {date.today().isoformat()}\n\n"
                  f"== USER LOCATION == {loc or '(unknown — ask only if a location is truly needed)'}\n\n"
                  f"== CARE IS FOR == {base_ctx.get('for_member', 'self')}\n\n"
                  f"== MEMORY (active person) ==\n{memory or '(no stored profile details)'}")

        # Files attached to THIS message — read their text directly so the agent uses them.
        att_ids = getattr(request, "attachment_document_ids", None) or []
        if att_ids:
            from app.services.reader_service import documents_text
            att = documents_text(request.user_id or "", att_ids)
            if att["found"]:
                system += ("\n\n== ATTACHED FILE(S) — the user attached these to THIS message. READ "
                           "them and answer from their contents. You already have the full text "
                           "below, so do NOT call search_documents for these and do NOT ask the user "
                           "to retype what's in them. If they ask to find/list/read what's in the "
                           "file, ENUMERATE the items you see (e.g. the products/medicines) before "
                           "offering a next step like price-comparison. ==\n" + att["text"])
            elif att["pending"]:
                system += ("\n\n== ATTACHED FILE(S) == The user attached " + ", ".join(att["pending"]) +
                           ", but it's still being read. Tell them it's processing and to ask again in "
                           "a few seconds.")
            elif att["failed"]:
                system += ("\n\n== ATTACHED FILE(S) == The user attached " + ", ".join(att["failed"]) +
                           ", but it couldn't be read (unreadable image or a network issue during "
                           "processing). Ask them to re-upload it.")
        contents = []
        for h in (request.history or [])[-8:]:
            hd = h.model_dump()
            role = "user" if hd.get("role") == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=hd.get("content", ""))]))
        contents.append(types.Content(role="user", parts=[types.Part(text=request.message)]))

        collected: list[SourcedStep] = []
        final_text = ""
        try:
            for _ in range(6):
                resp = generate_with_tools(system, contents, self.tools)
                cand = resp.candidates[0]
                calls = [p.function_call for p in (cand.content.parts or []) if getattr(p, "function_call", None)]
                texts = [p.text for p in (cand.content.parts or []) if getattr(p, "text", None)]
                if texts:
                    final_text = texts[-1]
                if not calls:
                    break
                contents.append(cand.content)
                # Gemini requires the reply to a function-call turn to contain EXACTLY one
                # function_response part per function_call part, all in a SINGLE user turn.
                # When the model calls e.g. plan_workout AND plan_diet together, we must
                # batch their responses into one Content — appending them separately trips a
                # 400 "number of function response parts must equal function call parts".
                response_parts = []
                for call in calls:
                    tool_name = call.name
                    args = dict(call.args or {})
                    agent_name, msg = _AGENT_FOR_TOOL.get(tool_name, ("orchestrator", "Working..."))
                    yield StreamChunk(type="thinking", content=msg, agent=agent_name)
                    try:
                        result = await self._run_tool(tool_name, args, base_ctx, collected)
                    except Exception as te:
                        # One tool failing must NOT sink the whole turn (e.g. a bad reminder should
                        # not lose a diet plan). Report it back so the model continues gracefully.
                        logger.exception(f"tool {tool_name} failed")
                        result = {"error": f"{tool_name} could not be completed ({te}).",
                                  "note": "Tell the user this specific part failed, then continue "
                                          "with everything else that succeeded."}
                    response_parts.append(
                        types.Part.from_function_response(name=tool_name, response=result)
                    )
                contents.append(types.Content(role="user", parts=response_parts))
        except Exception as e:
            logger.exception(f"agent loop failed: {e}")
            yield StreamChunk(type="error", content="Something went wrong — please try again.", agent="orchestrator")
            return

        # ── Emit ──
        steps = renumber_steps(collected)
        if steps:
            for s in steps:
                yield StreamChunk(type="step", content=s.model_dump(), agent=s.agent)
            yield StreamChunk(type="done", content={
                "session_id": sid,
                "for_member": request.for_member or "self",
                "intent_summary": request.message[:80],
                "ordered_steps": [s.model_dump() for s in steps],
                "generated_at": datetime.utcnow().isoformat(),
                "message": final_text or "Here's what I found.",
                "disclaimer": "WithCare provides navigation assistance only. This is not medical advice.",
            }, agent="orchestrator")
        else:
            yield StreamChunk(type="clarify",
                              content=final_text or "How can I help with your care today?",
                              agent="orchestrator")

    # ── tool dispatch ─────────────────────────────────────────────────────────────
    def _connector_blocked(self, base_ctx: dict, connector: str) -> dict | None:
        """Refusal dict if `connector` can't be used for THIS user, else None.

        Strict rule: when real OAuth is configured, the action REQUIRES the user's own
        access token — we never fall back to the shared/dev account, so users can't
        collide and nothing lands in the developer's account. In local dev (no OAuth
        client id set) the token.json fallback is allowed so testing still works."""
        label = {"calendar": "Google Calendar", "gmail": "Gmail",
                 "drive": "Google Drive"}.get(connector, connector)
        if connector not in base_ctx.get("connectors", []):
            return {"status": "not_connected", "connector": label,
                    "note": f"You CANNOT do this — the user hasn't connected {label}. Tell them to "
                            f"connect it on the Connectors page (one click). Do NOT claim it was done."}
        if _strict_user_token() and not base_ctx.get("connector_tokens", {}).get(connector):
            return {"status": "session_expired", "connector": label,
                    "note": f"You CANNOT do this — the user's {label} session has expired. Ask them to "
                            f"reconnect {label} on the Connectors page, then try again. Do NOT claim it was done."}
        return None

    async def _run_tool(self, name: str, args: dict, base_ctx: dict, collected: list) -> dict:
        if name == "find_facilities":
            ctx = {**base_ctx, "condition": args.get("condition", ""),
                   "location": args.get("location") or base_ctx.get("location", ""),
                   "specialty": args.get("specialty", ""), "user_message": base_ctx.get("full_context", "")}
            r = await self.facility_agent.run(ctx)
            collected.extend(r.steps)
            return {"result": self._summarize(r.steps) or "No facilities found."}

        if name == "find_coverage":
            ctx = {**base_ctx, "condition": args.get("condition", ""),
                   "location": args.get("location") or base_ctx.get("location", ""),
                   "coverage_scope": args.get("coverage_scope", "both"),
                   "occupation": args.get("occupation", ""), "annual_income": args.get("annual_income", ""),
                   "social_category": args.get("social_category", ""),
                   "user_message": self._coverage_msg(args)}
            r = await self.scheme_agent.run(ctx)
            collected.extend(r.steps)
            return {"result": self._summarize(r.steps) or "No coverage found."}

        if name == "find_products":
            ctx = {**base_ctx, "query": args.get("query", ""),
                   "location": base_ctx.get("location", ""),
                   "user_message": base_ctx.get("full_context", "")}
            r = await self.product_agent.run(ctx)
            collected.extend(r.steps)
            if not r.steps:
                return {"result": "No listings found for that product."}
            lines = [f"- {s.action}: {(s.meta or {}).get('price_display','')} on {s.source_label}"
                     for s in r.steps]
            return {"result": "Found these listings (cheapest first):\n" + "\n".join(lines)}

        if name == "set_reminder":
            blocked = self._connector_blocked(base_ctx, "calendar")
            if blocked:
                return blocked
            ctx = {**base_ctx,
                   "recipient": args.get("recipient", ""), "message": args.get("message", ""),
                   "date": args.get("date", ""), "time": args.get("time", ""),
                   "recurrence": args.get("recurrence", "none"),
                   "lead_minutes": args.get("lead_minutes", 10)}
            r = await self.reminder_agent.run(ctx)
            collected.extend(r.steps)
            return {"result": self._summarize(r.steps) or "Reminder set."}

        if name in ("plan_workout", "plan_diet"):
            ctx = dict(base_ctx)
            # The plan can target ANY of the owner's care profiles by name, not just the active one.
            person = (args.get("person") or "").strip()
            if person:
                active = (base_ctx.get("family_profile") or [{}])[0]
                same = person.lower() in (str(active.get("name", "")).lower(),
                                          str(active.get("relation", "")).lower())
                if not same:
                    prof = resolve_recipient(person, base_ctx.get("user_id", ""))
                    if prof:
                        ctx["family_profile"] = [prof]
                        ctx["active_profile_id"] = prof["id"]
                        ctx["for_member"] = prof["name"]
                        ctx["memory"] = get_profile_memory(prof["id"])
                    else:
                        return {"status": "need_more", "missing": ["person"],
                                "note": f"No care profile matches '{person}'. Ask the user who it's for, "
                                        "or suggest they add that person under Profiles."}
            # A plan needs a goal. For a person (not a pet), ask if it's missing.
            family = ctx.get("family_profile") or []
            is_pet = (family[0].get("kind") == "pet") if family else False
            goal = (args.get("goal") or args.get("focus") or "").strip()
            if not goal and not is_pet:
                who = (family[0].get("name") if family else None) or "them"
                return {"status": "need_more", "missing": ["goal"],
                        "note": f"Before making {who}'s plan, ASK their goal in ONE short question — "
                                "offer weight loss, weight gain, muscle gain, or maintain (normal). "
                                "Do not generate the plan yet."}
            agent = self.workout_agent if name == "plan_workout" else self.diet_agent
            r = await agent.run({**ctx, "goal": goal, "focus": goal,
                                 "adjustment": (args.get("adjustment") or "").strip()})
            collected.extend(r.steps)
            # Return the full plan so the model can present it (it's the whole point).
            return {"result": (r.steps[0].detail if r.steps else "Could not create the plan.")}

        if name in ("update_reminder", "cancel_reminder"):
            uid = base_ctx.get("user_id", "")
            pid, pname, _ = self._target_profile(args.get("recipient"), base_ctx)
            nodes = find_nodes(uid, "reminder", profile_id=pid, name_contains=args.get("match"))
            if not nodes:
                return {"status": "not_found",
                        "note": f"No matching reminder for {pname}. Ask which reminder they mean, "
                                "or offer to set a new one."}
            node = nodes[0]
            data = node.get("data") or {}
            cal_id = data.get("calendar_id") or "primary"
            event_id = data.get("event_id") or ""
            cal_token = base_ctx.get("connector_tokens", {}).get("calendar")

            if name == "cancel_reminder":
                if event_id:
                    await delete_calendar_event(cal_id, event_id, access_token=cal_token)
                delete_node(uid, node["id"])
                return {"result": f"Cancelled {pname}'s reminder '{node['name']}' and removed its "
                                  "calendar event."}

            new_time = _parse_time(args["time"]) if args.get("time") else (data.get("time") or "09:00")
            new_msg = (args.get("message") or node["name"]).strip()
            new_rec = (args.get("recurrence") or data.get("recurrence") or "none").lower()
            try:
                new_lead = (int(float(args["lead_minutes"])) if args.get("lead_minutes") is not None
                            else int(float(data.get("lead_minutes") or 10)))
            except (TypeError, ValueError):
                new_lead = int(float(data.get("lead_minutes") or 10))
            start_iso = f"{date.today().isoformat()}T{new_time}:00"
            end_iso = (datetime.fromisoformat(start_iso) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
            if event_id:
                await update_calendar_event(cal_id, event_id, summary=f"Reminder: {new_msg}",
                                            start_datetime=start_iso, end_datetime=end_iso,
                                            recurrence=_RRULE.get(new_rec), reminder_minutes=[new_lead],
                                            access_token=cal_token)
            # Replace the KG node in place (its name may have changed); keep the same event.
            delete_node(uid, node["id"])
            write_fact(uid, pid, "reminder", new_msg,
                       data={"time": new_time, "recurrence": new_rec, "lead_minutes": new_lead,
                             "recipient": data.get("recipient") or pname,
                             "event_id": event_id, "calendar_id": cal_id},
                       predicate="has_reminder")
            when = ("every day" if new_rec == "daily" else "every week" if new_rec == "weekly"
                    else "one-time")
            return {"result": f"Updated {pname}'s reminder to '{new_msg}' — {when} at {new_time}, "
                              f"{new_lead} min before. Calendar updated."}

        if name == "update_profile":
            uid = base_ctx.get("user_id", "")
            pid, pname, _ = self._target_profile(args.get("person"), base_ctx)
            if not pid:
                return {"status": "not_found",
                        "note": f"No care profile matches '{args.get('person')}'. Ask who it's for, "
                                "or suggest adding them under Profiles."}
            fields = {k: args[k] for k in ("age", "weight", "height", "gender", "conditions",
                                           "notes", "email")
                      if args.get(k) not in (None, "")}
            if not fields:
                return {"status": "need_more", "note": "Ask which detail to update."}
            db = _get_db()
            sets = ", ".join(f"{k}=?" for k in fields)
            db.execute(f"UPDATE profiles SET {sets}, updated_at=datetime('now') WHERE id=? AND user_id=?",
                       (*fields.values(), pid, uid))
            db.commit()
            row = db.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
            db.close()
            if row:
                sync_profile_to_kg(uid, dict(row))
            changed = ", ".join(f"{k} → {v}" for k, v in fields.items())
            return {"result": f"Updated {pname}'s profile ({changed}). Memory is in sync."}

        if name == "remember":
            uid = base_ctx.get("user_id", "")
            pid, pname, _ = self._target_profile(args.get("person"), base_ctx)
            fact = (args.get("fact") or "").strip()
            if not fact:
                return {"status": "need_more", "note": "Ask what to remember."}
            allowed = {"condition", "medication", "hospital", "health_metric", "note"}
            ntype = (args.get("category") or "note").lower()
            if ntype not in allowed:
                ntype = "note"
            write_fact(uid, pid, ntype, fact, predicate="for_member")
            return {"result": f"Noted for {pname}: {fact}."}

        if name == "forget":
            uid = base_ctx.get("user_id", "")
            pid, pname, _ = self._target_profile(args.get("person"), base_ctx)
            match = (args.get("match") or "").strip().lower()
            found = None
            for t in ("note", "condition", "medication", "hospital", "health_metric",
                      "scheme", "insurance"):
                for n in find_nodes(uid, t, profile_id=pid):
                    if match and match in (n.get("name") or "").lower():
                        found = n
                        break
                if found:
                    break
            if not found:
                return {"status": "not_found",
                        "note": f"Couldn't find a remembered fact matching '{match}' for {pname}. "
                                "(Conditions set on the profile are changed with update_profile.)"}
            delete_node(uid, found["id"])
            return {"result": f"Forgotten for {pname}: {found['name']}."}

        if name == "search_documents":
            from app.services.reader_service import context_for_agent
            uid = base_ctx.get("user_id", "")
            res = context_for_agent(uid, args.get("query", ""), label=args.get("label") or None)
            if not res.get("found"):
                return {"found": False,
                        "note": "No matching uploaded document. Tell the user you couldn't find it in "
                                "their documents and offer to have them upload it in the Reader."}
            return {"found": True, "excerpts": res["excerpts"], "sources": res["sources"],
                    "note": "Answer ONLY from these excerpts; cite the document label in parentheses."}

        if name == "schedule_appointment":
            blocked = self._connector_blocked(base_ctx, "calendar")
            if blocked:
                return blocked
            missing = [k for k in ("procedure", "date") if not args.get(k)]
            if missing:
                return {"status": "need_more", "missing": missing,
                        "note": f"Ask the user for: {', '.join(missing)}."}
            ts, te = args.get("time_start", ""), args.get("time_end", "")
            rec = (args.get("recurrence") or "none").lower()
            when = args["date"] + (f" {ts}" if ts else "") + (f"–{te}" if te else "")
            hosp = args.get("hospital", "")
            if hosp and hosp != "find_nearest":
                summary = f"Book {args['procedure']} at {hosp} on {when}".strip()
            else:
                summary = f"Schedule {args['procedure']} on {when}".strip()
            if rec in ("daily", "weekly"):
                until = f" until {args['repeat_until']}" if args.get("repeat_until") else ""
                summary += f" ({rec}{until})"
            self._stage_pending(base_ctx["session_id"], "schedule_appointment", args, summary, base_ctx)
            return {"status": "confirmation_required", "summary": summary,
                    "note": "Ask the user to confirm with a clear yes/no. Do NOT say it's added yet."}
        return {"error": f"unknown tool {name}"}

    def _target_profile(self, mention: str | None, base_ctx: dict) -> tuple[str | None, str, dict | None]:
        """Resolve a mention ('mother'/a name/empty) to (profile_id, display_name, profile).
        Empty or the active person -> the active profile."""
        active = (base_ctx.get("family_profile") or [{}])[0]
        m = (mention or "").strip()
        if (not m or m.lower() == "self"
                or m.lower() in (str(active.get("name", "")).lower(),
                                 str(active.get("relation", "")).lower())):
            return base_ctx.get("active_profile_id"), active.get("name", "you") or "you", active
        prof = resolve_recipient(m, base_ctx.get("user_id", ""))
        if prof:
            return prof["id"], prof["name"], prof
        return None, m, None

    # ── commit an irreversible action (only from the confirmation gate) ───────────
    async def _commit(self, pending: dict) -> AsyncGenerator[StreamChunk, None]:
        args, base_ctx = pending["args"], pending["base_ctx"]
        date_s = args.get("date", "")
        ts, te = args.get("time_start", ""), args.get("time_end", "")
        start_iso = f"{date_s}T{ts}:00" if date_s and ts and ts != "flexible" else ""
        end_iso = f"{date_s}T{te}:00" if date_s and te and te != "flexible" else ""
        ctx = {**base_ctx,
               "extracted_procedure": args.get("procedure", "Appointment"),
               "extracted_hospital": args.get("hospital", ""),
               "extracted_start_datetime": start_iso, "extracted_end_datetime": end_iso,
               "recurrence": (args.get("recurrence") or "none"),
               "repeat_until": args.get("repeat_until", ""),
               "for_member": args.get("for_member") or base_ctx.get("for_member", "self"),
               "care_plan_steps": [], "user_message": args.get("procedure", ""),
               "care_plan_context": {"intent_summary": args.get("procedure", ""), "ordered_steps": [],
                                     "generated_at": datetime.utcnow().isoformat(),
                                     "disclaimer": "WithCare provides navigation assistance only."}}
        r = await self.action_agent.run(ctx)
        steps = renumber_steps(r.steps)
        for s in steps:
            yield StreamChunk(type="step", content=s.model_dump(), agent=s.agent)
        top = steps[0] if steps else None
        msg = f"Done! {top.action} — {top.detail}" if top else "Your appointment is booked."
        yield StreamChunk(type="done", content={
            "session_id": base_ctx.get("session_id", ""),
            "for_member": base_ctx.get("for_member", "self"),
            "intent_summary": args.get("procedure", "")[:80],
            "ordered_steps": [s.model_dump() for s in steps],
            "generated_at": datetime.utcnow().isoformat(),
            "message": msg,
            "disclaimer": "WithCare provides navigation assistance only. This is not medical advice.",
        }, agent="orchestrator")

    @staticmethod
    def _summarize(steps: list[SourcedStep]) -> str:
        return "\n".join(f"- {s.action}: {s.detail[:180]}" for s in steps[:6])

    @staticmethod
    def _coverage_msg(args: dict) -> str:
        parts = [args.get("condition", "health coverage")]
        if args.get("location"):
            parts.append(f"in {args['location']}")
        for k in ("occupation", "annual_income", "social_category"):
            if args.get(k):
                parts.append(f"{k} {args[k]}")
        return ", ".join(parts)
