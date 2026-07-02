"""
WithCareOrchestrator (architecture v3).

Deterministic multi-task conversation manager. Two LLM calls per turn (Segmenter, Writer);
everything else — task state, ask/act decisions, dependency execution, confirmation — is
plain Python. Replaces the old autonomous ADK LlmAgent entirely.
"""
import re
from datetime import datetime
from typing import AsyncGenerator

from app.agents.action_agent import ActionAgent
from app.agents.facility_agent import FacilityAgent
from app.agents.scheme_agent import SchemeAgent
from app.models.request_models import ChatRequest
from app.models.response_models import SourcedStep, StreamChunk
from app.models.task_models import TaskIntent, TaskStatus
from app.orchestrator.composer import compose
from app.orchestrator.executor import DependencyExecutor
from app.orchestrator.planner import plan as build_plan
from app.orchestrator.router import classify_intent
from app.orchestrator.segmenter import segment
from app.orchestrator.task_state import TaskStateManager
from app.services.memory_service import get_profile_memory
from app.services.grounding import renumber_steps
from app.utils.exceptions import ClinicalRequestError
from app.utils.logger import get_logger

logger = get_logger(__name__)

_THINKING = {
    TaskIntent.FIND_SCHEME: ("Searching government health schemes...", "scheme_agent"),
    TaskIntent.FIND_FACILITY: ("Finding hospitals and facilities nearby...", "facility_agent"),
    TaskIntent.SCHEDULE: ("Preparing your appointment...", "action_agent"),
}

_YES = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed",
        "go ahead", "book it", "do it", "please do", "sounds good", "yes please", "book"}
_NO = {"no", "nope", "cancel", "not yet", "wait", "stop", "don't", "dont", "change"}


def classify_yes_no(message: str) -> str:
    """Strict: only a bare yes/no fast-paths. Anything with extra content -> ambiguous."""
    norm = re.sub(r"[^a-z\s]", "", message.lower()).strip()
    if norm in _YES:
        return "yes"
    if norm in _NO:
        return "no"
    return "ambiguous"


class WithCareOrchestrator:
    def __init__(self):
        self.scheme_agent = SchemeAgent()
        self.facility_agent = FacilityAgent()
        self.action_agent = ActionAgent()
        self.task_state = TaskStateManager()
        self.executor = DependencyExecutor(self.scheme_agent, self.facility_agent, self.action_agent)
        logger.info("WithCareOrchestrator (v3) initialized")

    async def handle(self, request: ChatRequest) -> AsyncGenerator[StreamChunk, None]:
        sid = request.session_id
        yield StreamChunk(type="thinking", content="Understanding what you need...", agent="orchestrator")

        # Clinical / ambiguity gate — unchanged safety layer.
        intent = await classify_intent(
            request.message,
            [m.model_dump() for m in (request.family_profile or [])],
            [h.model_dump() for h in (request.history or [])],
            location=request.location or "",
        )
        if intent.get("is_clinical"):
            yield StreamChunk(type="error", content=ClinicalRequestError.message, agent="orchestrator")
            return

        coords = request.coordinates.model_dump() if request.coordinates else None
        history = [h.model_dump() for h in (request.history or [])]
        family = [m.model_dump() for m in (request.family_profile or [])]
        active_pid = family[0].get("id") if family else None
        # Persistent knowledge-graph memory for this person; fall back to the inline request
        # summary if the profile isn't in the DB yet (keeps it working for anonymous/new).
        memory = get_profile_memory(active_pid) if active_pid else ""
        profile_summary = memory or self._profile_summary(family, request.for_member or "self")
        base_ctx = {
            "coordinates": coords,
            "family_profile": family,
            "for_member": request.for_member or "self",
            "session_id": sid,
            "user_id": request.user_id or "",
            "active_profile_id": active_pid,
            "location": request.location or "",
            "full_context": request.message,
            "care_recipient": profile_summary,
            "memory": memory,
        }

        # ── Confirmation pre-check (deterministic, no LLM) ───────────────────────────
        pending = self.task_state.awaiting_confirmation(sid)
        if pending:
            decision = classify_yes_no(request.message)
            if decision == "yes":
                yield StreamChunk(type="thinking", content="Booking your appointment...", agent="action_agent")
                results = await self.executor.run_all(
                    [pending], self.task_state._get(sid), base_ctx, confirmed_task_id=pending.task_id
                )
                async for chunk in self._emit(sid, results, history, request):
                    yield chunk
                return
            if decision == "no":
                pending.status = TaskStatus.COLLECTING
                yield StreamChunk(type="clarify",
                                  content="No problem — what would you like to change?",
                                  agent="orchestrator")
                return
            # ambiguous → fall through; segmenter sees the pending frame in OPEN TASKS

        # ── Segment (LLM #1) → merge (deterministic) ────────────────────────────────
        raw_tasks = await segment(request.message, self.task_state.open_tasks_summary(sid), history, profile=profile_summary)
        if not raw_tasks:
            if intent.get("is_ambiguous") and intent.get("clarifying_question"):
                yield StreamChunk(type="clarify", content=intent["clarifying_question"], agent="orchestrator")
            else:
                yield StreamChunk(type="clarify",
                                  content="I can help you find hospitals, check government schemes, or book an appointment. What would you like to do?",
                                  agent="orchestrator")
            return

        recipient_conditions = family[0].get("conditions", "") if family else ""
        self.task_state.merge(
            sid, raw_tasks, coords,
            fallback_location=request.location or "",
            recipient_conditions=recipient_conditions,
        )

        # ── Execute ready frames ─────────────────────────────────────────────────────
        ready = self.task_state.dependency_ready(sid)
        for f in ready:
            msg, agent = _THINKING.get(f.intent, ("Working on it...", "orchestrator"))
            yield StreamChunk(type="thinking", content=msg, agent=agent)

        results = []
        if ready:
            results = await self.executor.run_all(ready, self.task_state._get(sid), base_ctx)

        async for chunk in self._emit(sid, results, history, request):
            yield chunk

    @staticmethod
    def _profile_summary(family: list[dict], for_member: str) -> str:
        """A short 'who this care is for' line fed to the LLMs so replies know the person,
        their age/gender, and known conditions."""
        if not family:
            return ""
        m = family[0]
        who = m.get("name") or ("you" if for_member == "self" else for_member)
        if m.get("kind") == "pet":
            head = f"{who} — a pet" + (f" ({m['species']})" if m.get("species") else "")
        else:
            head = who
            rel = (m.get("relation") or "").strip()
            if rel and rel.lower() not in ("self", "your own care"):
                head += f" ({rel})"
        parts = [head]
        if m.get("age"):
            parts.append(f"age {m['age']}")
        if m.get("gender"):
            parts.append(m["gender"])
        summary = ", ".join(parts)
        extras = []
        if m.get("conditions"):
            extras.append(f"Known health conditions: {m['conditions']}")
        if m.get("notes"):
            extras.append(f"Other details: {m['notes']}")
        if extras:
            summary += ". " + ". ".join(extras)
        return summary

    async def _emit(self, sid, results, history, request) -> AsyncGenerator[StreamChunk, None]:
        """Build the CommunicationPlan, write the natural message, and stream steps + final."""
        frames = self.task_state._get(sid)
        family = [m.model_dump() for m in (request.family_profile or [])]
        active_pid = family[0].get("id") if family else None
        profile_summary = (get_profile_memory(active_pid) if active_pid else "") \
            or self._profile_summary(family, request.for_member or "self")
        comm = build_plan(self.task_state.active_frames(sid), results)
        message = await compose(comm, frames, results, history, profile=profile_summary)

        # Collect result steps for the care-plan card.
        all_steps: list[SourcedStep] = []
        for r in results:
            if r.status == TaskStatus.DONE:
                all_steps.extend(r.steps)
        all_steps = renumber_steps(all_steps)

        if all_steps:
            for step in all_steps:
                yield StreamChunk(type="step", content=step.model_dump(), agent=step.agent)
            payload = {
                "session_id": sid,
                "for_member": request.for_member or "self",
                "intent_summary": request.message[:80],
                "ordered_steps": [s.model_dump() for s in all_steps],
                "generated_at": datetime.utcnow().isoformat(),
                "message": message,
                "disclaimer": "WithCare provides navigation assistance only. This is not medical advice.",
            }
            yield StreamChunk(type="done", content=payload, agent="orchestrator")
        else:
            # Pure ask / confirm / clarify turn — no card.
            yield StreamChunk(type="clarify", content=message, agent="orchestrator")

        logger.info(f"Turn complete — {len(all_steps)} steps, plan={comm.model_dump()}")
