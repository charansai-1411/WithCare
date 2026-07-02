"""
Task State Manager (deterministic — no LLM).

Merges the Segmenter's RawTasks into persistent, session-scoped TaskFrames; assigns
location confidence from real GPS availability; wires the FIND_FACILITY -> SCHEDULE
dependency; and drives the SCHEDULE lifecycle (never books directly — SCHEDULE reaches
RUNNING only via the confirmation gate).
"""
import uuid
from typing import Optional

from app.models.task_models import (
    ELIGIBILITY_FACT_KEYS,
    Fact,
    RawTask,
    SessionContext,
    TaskFrame,
    TaskIntent,
    TaskStatus,
    PREFERENCE_KEYS,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

_GOALS = {
    TaskIntent.FIND_SCHEME: "check government scheme eligibility",
    TaskIntent.FIND_FACILITY: "find a suitable clinic or hospital",
    TaskIntent.SCHEDULE: "book an appointment",
}


class TaskStateManager:
    def __init__(self):
        self._frames: dict[str, dict[str, TaskFrame]] = {}   # session_id -> task_id -> frame
        self._session_ctx: dict[str, SessionContext] = {}    # session_id -> context
        self._turn: dict[str, int] = {}

    def _get(self, session_id: str) -> dict[str, TaskFrame]:
        return self._frames.setdefault(session_id, {})

    def context(self, session_id: str) -> SessionContext:
        return self._session_ctx.setdefault(session_id, SessionContext())

    # ── Views ────────────────────────────────────────────────────────────────────
    def open_tasks_summary(self, session_id: str) -> list[dict]:
        """Fed to the Segmenter as OPEN TASKS. Includes AWAITING_CONFIRMATION so a
        mid-confirmation edit ('actually make it 6pm') attaches to the pending frame."""
        return [
            {
                "task_id": tid,
                "intent": f.intent.value,
                "known_facts": {k: v.value for k, v in f.facts.items() if v.value},
                "missing": f.missing_required,
                "status": f.status.value,
            }
            for tid, f in self._get(session_id).items()
            if f.status in (TaskStatus.COLLECTING, TaskStatus.READY, TaskStatus.AWAITING_CONFIRMATION)
        ]

    def active_frames(self, session_id: str) -> list[TaskFrame]:
        return list(self._get(session_id).values())

    def dependency_ready(self, session_id: str) -> list[TaskFrame]:
        """READY frames whose dependency (if any) is DONE."""
        frames = self._get(session_id)
        ready = []
        for f in frames.values():
            if f.status != TaskStatus.READY:
                continue
            if f.depends_on:
                dep = frames.get(f.depends_on)
                if not dep or dep.status != TaskStatus.DONE:
                    continue
            ready.append(f)
        return ready

    def awaiting_confirmation(self, session_id: str) -> Optional[TaskFrame]:
        for f in self._get(session_id).values():
            if f.status == TaskStatus.AWAITING_CONFIRMATION:
                return f
        return None

    # ── Merge ────────────────────────────────────────────────────────────────────
    def merge(
        self,
        session_id: str,
        raw_tasks: list[RawTask],
        coordinates: Optional[dict],
        fallback_location: str = "",
        recipient_conditions: str = "",
    ) -> list[TaskFrame]:
        self._turn[session_id] = self._turn.get(session_id, 0) + 1
        turn = self._turn[session_id]
        frames = self._get(session_id)
        ctx = self.context(session_id)
        if coordinates and coordinates.get("lat") and coordinates.get("lng"):
            ctx.known_coordinates = coordinates
        # A city from the app header counts as a known location for the session.
        if fallback_location and not ctx.known_location:
            ctx.known_location = Fact(value=fallback_location, confidence="high", user_specified=False)

        # Process FIND_FACILITY before SCHEDULE so its task_id exists to link against.
        ordered = sorted(raw_tasks, key=lambda rt: rt.intent != TaskIntent.FIND_FACILITY)
        new_facility_id: Optional[str] = None
        touched: list[TaskFrame] = []

        for rt in ordered:
            existing = rt.refers_to_existing_task and frames.get(rt.refers_to_existing_task)
            if existing:
                frame = existing
                frame.just_learned = {}
            else:
                frame = TaskFrame(
                    task_id=f"t{uuid.uuid4().hex[:8]}",
                    intent=rt.intent,
                    goal=_GOALS[rt.intent],
                    created_turn=turn,
                )
                frames[frame.task_id] = frame
                # New non-SCHEDULE frames inherit a known location from the session.
                if rt.intent != TaskIntent.SCHEDULE and ctx.known_location and "location" not in rt.slots:
                    frame.facts["location"] = ctx.known_location
                if ctx.known_for_member:
                    frame.facts.setdefault("for_member", ctx.known_for_member)

            # Facts
            for k, v in rt.slots.items():
                if k in ("location_is_relative",) or v in (None, ""):
                    continue
                us = bool(rt.user_specified.get(k, True))
                if k in PREFERENCE_KEYS:
                    frame.preferences[k] = Fact(value=str(v), user_specified=us)
                else:
                    frame.facts[k] = Fact(value=str(v), user_specified=us)
                frame.just_learned[k] = str(v)

            # Preferences delivered in the dedicated object
            for k, v in rt.preferences.items():
                if v in (None, ""):
                    continue
                us = bool(rt.user_specified.get(k, True))
                frame.preferences[k] = Fact(value=str(v), user_specified=us)
                frame.just_learned[k] = str(v)

            # location_is_relative — confidence assigned HERE, from real signals, never LLM.
            # Priority: real GPS coords > a known city (header/earlier turn) > unresolved (ask).
            if rt.slots.get("location_is_relative") and not (frame.facts.get("location") and frame.facts["location"].value):
                if coordinates and coordinates.get("lat") and coordinates.get("lng"):
                    frame.facts["location"] = Fact(
                        value=f"{coordinates['lat']},{coordinates['lng']}",
                        confidence="high", user_specified=True,
                    )
                    frame.just_learned["location"] = "your current location"
                elif fallback_location:
                    frame.facts["location"] = Fact(value=fallback_location, confidence="high", user_specified=False)
                    frame.just_learned["location"] = fallback_location
                elif ctx.known_location and ctx.known_location.value:
                    frame.facts["location"] = ctx.known_location
                    frame.just_learned["location"] = ctx.known_location.value
                else:
                    frame.facts["location"] = Fact(value=None, confidence="low", user_specified=True)
                    frame.just_learned["location_unresolved"] = "true"

            # Promote a high-confidence location into the session context.
            loc = frame.facts.get("location")
            if loc and loc.value and loc.confidence == "high":
                ctx.known_location = loc
            fm = frame.facts.get("for_member")
            if fm and fm.value:
                ctx.known_for_member = fm

            # Dependency wiring: FIND_FACILITY id feeds the SCHEDULE that depends on it.
            if frame.intent == TaskIntent.FIND_FACILITY:
                new_facility_id = frame.task_id
            if frame.intent == TaskIntent.SCHEDULE and rt.depends_on_new_task and new_facility_id:
                frame.depends_on = new_facility_id

            frame.updated_turn = turn
            self._apply_status(frame)
            touched.append(frame)

        # Deterministic decomposition — every SCHEDULE that needs a hospital must be fed
        # by a FIND_FACILITY. Don't rely on the LLM to have flagged the dependency; wire it
        # here so the schedule can never orphan (the "listed clinics but never confirmed" bug).
        self._ensure_facility_for_schedules(frames, ctx, turn, touched)

        # Deterministic fact-routing — date/time belong to the SCHEDULE, place/condition to
        # the FIND_FACILITY, regardless of which task the LLM attached them to. This is what
        # stops the date getting lost across turns ("said sunday 10-4 but never scheduled").
        self._route_turn_facts(raw_tasks, frames, ctx)

        # A scheme/insurance search is about the person's eligibility, so backfill its
        # condition from the active profile when the user didn't state one — don't re-ask
        # for something already in their profile.
        if recipient_conditions:
            for f in frames.values():
                if f.intent == TaskIntent.FIND_SCHEME and f.status not in (TaskStatus.DONE, TaskStatus.RUNNING):
                    if not (f.facts.get("condition") and f.facts["condition"].value):
                        f.facts["condition"] = Fact(value=recipient_conditions, user_specified=False)
                        self._apply_status(f)

        # Re-run a completed coverage search when the user answers a follow-up (eligibility
        # info or "government only / private too") — so their answer actually refines results.
        for f in frames.values():
            if f.intent == TaskIntent.FIND_SCHEME and f.status == TaskStatus.DONE:
                if set(f.just_learned) & (ELIGIBILITY_FACT_KEYS | {"coverage_scope"}):
                    f.status = TaskStatus.READY

        return touched

    @staticmethod
    def _backfill_condition(fac: TaskFrame, extra: Optional[Fact] = None) -> None:
        """Ensure a FIND_FACILITY has a `condition` — the Segmenter sometimes only labels
        the need as procedure/specialty, which would strand the facility as 'missing'."""
        if fac.facts.get("condition") and fac.facts["condition"].value:
            return
        for src in (fac.facts.get("procedure"), fac.facts.get("specialty"), extra):
            if src and src.value:
                fac.facts["condition"] = Fact(value=src.value, user_specified=False)
                return

    def _route_turn_facts(self, raw_tasks: list[RawTask], frames, ctx) -> None:
        # Union of every value the Segmenter extracted this turn.
        bag: dict[str, str] = {}
        for rt in raw_tasks:
            for k, v in rt.slots.items():
                if v not in (None, "") and k != "location_is_relative" and k not in bag:
                    bag[k] = str(v)

        def active(intent: TaskIntent):
            cands = [f for f in frames.values()
                     if f.intent == intent and f.status not in (TaskStatus.DONE, TaskStatus.RUNNING)]
            return cands[-1] if cands else None

        def fill(frame, key, is_pref=False):
            if not frame or key not in bag:
                return
            store = frame.preferences if is_pref else frame.facts
            if store.get(key) and store[key].value:
                return  # don't overwrite an existing value
            store[key] = Fact(value=bag[key], user_specified=True)
            frame.just_learned[key] = bag[key]

        sched = active(TaskIntent.SCHEDULE)
        fac = active(TaskIntent.FIND_FACILITY)

        for k in ("procedure", "date", "time_start", "time_end", "for_member"):
            fill(sched, k)
        for k in ("condition", "specialty"):
            fill(fac, k)

        # A concrete place name belongs to the facility (and the session).
        if bag.get("location"):
            fill(fac, "location")
            ctx.known_location = Fact(value=bag["location"], confidence="high", user_specified=True)

        if fac:
            self._backfill_condition(fac, extra=(sched.facts.get("procedure") if sched else None))

        for f in (sched, fac):
            if f:
                self._apply_status(f)

    def _ensure_facility_for_schedules(self, frames, ctx, turn, touched) -> None:
        schedules = [
            f for f in frames.values()
            if f.intent == TaskIntent.SCHEDULE and f.status not in (TaskStatus.DONE, TaskStatus.RUNNING)
        ]
        if not schedules:
            return
        facilities = [f for f in frames.values() if f.intent == TaskIntent.FIND_FACILITY]

        for sched in schedules:
            hosp = sched.facts.get("hospital")
            if hosp and hosp.value:
                continue  # user named a specific hospital → no facility search needed

            if sched.depends_on and sched.depends_on in frames:
                fac = frames[sched.depends_on]
            elif facilities:
                fac = facilities[-1]            # reuse the session's facility search
                sched.depends_on = fac.task_id
            else:
                fac = TaskFrame(
                    task_id=f"t{uuid.uuid4().hex[:8]}",
                    intent=TaskIntent.FIND_FACILITY,
                    goal=_GOALS[TaskIntent.FIND_FACILITY],
                    created_turn=turn,
                )
                proc = sched.facts.get("procedure")
                if proc and proc.value:
                    fac.facts["condition"] = Fact(value=proc.value, user_specified=False)
                loc = sched.facts.get("location") or ctx.known_location
                if loc and loc.value:
                    fac.facts["location"] = loc
                frames[fac.task_id] = fac
                facilities.append(fac)
                sched.depends_on = fac.task_id
                self._apply_status(fac)
                touched.append(fac)

            # Same place — share a resolved location from schedule to its facility.
            s_loc = sched.facts.get("location")
            if s_loc and s_loc.value and not (fac.facts.get("location") and fac.facts["location"].value):
                fac.facts["location"] = s_loc
                if fac not in touched:
                    touched.append(fac)

            # A facility must have a condition to search — derive it from the schedule's
            # procedure when the Segmenter only labelled it as procedure/specialty.
            self._backfill_condition(fac, extra=sched.facts.get("procedure"))
            self._apply_status(fac)

            # If the facility already ran on an earlier turn, inject its hospital now.
            if fac.status == TaskStatus.DONE and fac.results:
                top = fac.results[0].action.replace("Visit ", "").replace(" (nearby)", "")
                sched.facts["hospital"] = Fact(value=top, user_specified=False)
                sched.results = fac.results

            self._apply_status(sched)

    @staticmethod
    def _apply_status(frame: TaskFrame) -> None:
        """Lifecycle transitions. SCHEDULE never goes straight to RUNNING here."""
        if frame.status in (TaskStatus.DONE, TaskStatus.RUNNING):
            return
        missing = frame.missing_required
        if frame.intent == TaskIntent.SCHEDULE:
            if missing:
                frame.status = TaskStatus.COLLECTING
            elif frame.depends_on:
                frame.status = TaskStatus.READY            # gated until facility is DONE
            else:
                frame.status = TaskStatus.AWAITING_CONFIRMATION   # named hospital → confirm
        else:
            frame.status = TaskStatus.READY if not missing else TaskStatus.COLLECTING
