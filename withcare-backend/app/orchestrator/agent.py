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
from datetime import date, datetime
from typing import AsyncGenerator

from google.genai import types

from app.agents.action_agent import ActionAgent
from app.agents.facility_agent import FacilityAgent
from app.agents.scheme_agent import SchemeAgent
from app.db.database import get_db
from app.models.request_models import ChatRequest
from app.models.response_models import SourcedStep, StreamChunk
from app.orchestrator.router import classify_intent
from app.services.gemini_service import build_tools, generate_with_tools
from app.services.grounding import renumber_steps
from app.services.memory_service import get_profile_memory
from app.utils.exceptions import ClinicalRequestError
from app.utils.logger import get_logger

logger = get_logger(__name__)

_SKILL_PATH = __import__("os").path.join(
    __import__("os").path.dirname(__file__), "..", "..", "skills", "orchestrator.md"
)

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
        "description": "Find hospitals/clinics for a health need near a location. Read-only.",
        "parameters": {
            "type": "object",
            "properties": {
                "condition": {"type": "string", "description": "Health need or specialty, e.g. 'eye care', 'cardiology'"},
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
        "description": ("Propose booking a health appointment on the calendar. Does NOT book — it "
                        "stages the booking; the user must confirm afterward. If no hospital is known, "
                        "call find_facilities first and pass the top hospital."),
        "parameters": {
            "type": "object",
            "properties": {
                "procedure": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time_start": {"type": "string", "description": "HH:MM 24h"},
                "time_end": {"type": "string", "description": "HH:MM 24h"},
                "hospital": {"type": "string"},
                "for_member": {"type": "string"},
            },
            "required": ["procedure", "date"],
        },
    },
]

_AGENT_FOR_TOOL = {
    "find_facilities": ("facility_agent", "Finding hospitals and facilities nearby..."),
    "find_coverage": ("scheme_agent", "Searching schemes and insurance..."),
    "schedule_appointment": ("action_agent", "Preparing your appointment..."),
}


class WithCareAgent:
    def __init__(self):
        self.facility_agent = FacilityAgent()
        self.scheme_agent = SchemeAgent()
        self.action_agent = ActionAgent()
        self.tools = build_tools(TOOL_DECLS)
        try:
            with open(_SKILL_PATH, encoding="utf-8") as f:
                self.skill = f.read()
        except Exception as e:
            logger.warning(f"skill load failed: {e}")
            self.skill = "You are WithCare, a healthcare navigation assistant for India."
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
        }

        # ── GUARD: confirmation gate — the ONLY path that executes an irreversible action ──
        pending = self._get_pending(sid)
        if pending:
            decision = classify_yes_no(request.message)
            if decision == "yes":
                yield StreamChunk(type="thinking", content="Booking your appointment...", agent="action_agent")
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
                for call in calls:
                    tool_name = call.name
                    args = dict(call.args or {})
                    agent_name, msg = _AGENT_FOR_TOOL.get(tool_name, ("orchestrator", "Working..."))
                    yield StreamChunk(type="thinking", content=msg, agent=agent_name)
                    result = await self._run_tool(tool_name, args, base_ctx, collected)
                    contents.append(types.Content(role="user", parts=[
                        types.Part.from_function_response(name=tool_name, response=result)
                    ]))
        except Exception as e:
            logger.error(f"agent loop failed: {e}")
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

        if name == "schedule_appointment":
            missing = [k for k in ("procedure", "date") if not args.get(k)]
            if missing:
                return {"status": "need_more", "missing": missing,
                        "note": f"Ask the user for: {', '.join(missing)}."}
            when = f"{args['date']} {args.get('time_start','')}".strip()
            hosp = args.get("hospital") or "a suitable nearby clinic"
            summary = f"Book {args['procedure']} at {hosp} on {when}".strip()
            self._stage_pending(base_ctx["session_id"], "schedule_appointment", args, summary, base_ctx)
            return {"status": "confirmation_required", "summary": summary,
                    "note": "Ask the user to confirm with a clear yes/no. Do NOT say it's booked yet."}
        return {"error": f"unknown tool {name}"}

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
