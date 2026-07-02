# Withcare — Multi-Task Conversation Architecture v2

This supersedes `withcare-multitask-architecture.md`. Same foundation (Segmenter →
Task State → Executor), rebuilt on top with: goal-shaped conversation instead of raw
slot-filling, a deterministic Planner separated from the LLM Writer, a confirmation
gate before Calendar writes, and the location bug fixed at its actual source
(`maps_tool.py`), not just papered over upstream.

---

## 0. What changed from v1, and why

| v1 | v2 | Why |
|---|---|---|
| `slots: dict` | `facts: dict[str, Fact]` + `preferences: dict[str, Fact]` | Distinguishes required-for-execution values from optional UX-improving ones; distinguishes "we don't know yet" from "user explicitly decided" |
| No confidence | `Fact.confidence` | "GPS unavailable" and "not asked yet" need different questions, not the same `missing_slots` bucket |
| Composer sees `missing_slots` directly | Planner (deterministic) → `CommunicationPlan` → Writer (LLM) | LLM never decides *what* to ask, only *how* to phrase it — keeps the "LLM doesn't own workflow" guarantee intact |
| "schedule X near me" = 1 frame | Decomposes into FIND_FACILITY → SCHEDULE (dependency chain) | The only way the preference-offer rule stays a clean per-frame check instead of a special case |
| No confirm gate | `AWAITING_CONFIRMATION` status | Calendar writes are irreversible-ish; this was already on your bug list |
| `find_nearby_hospitals` geocodes everything, incl. coordinates | Skip geocode when input is already lat/lng; haversine locally | Root cause of the Hinganghat bug — confirmed against your actual `maps_tool.py` |

---

## 1. Architecture

```
                         User message
                              │
                              ▼
              ┌───────────────────────────┐
              │ Confirmation pre-check     │  (deterministic — cheap, runs first)
              │ Is there an AWAITING_      │
              │ CONFIRMATION frame AND is  │
              │ this a plain yes/no?       │
              └──────────┬─────────────────┘
              yes ────────┘         └──────── no / ambiguous
              │                                │
              ▼                                ▼
     Resolve directly                 ┌─────────────────┐
     (execute or cancel,              │  Task Segmenter   │  (LLM call #1)
      skip segmentation)              │  emits facts +    │
              │                       │  preferences +    │
              │                       │  user_specified    │
              │                       └────────┬──────────┘
              │                                ▼
              │                       ┌─────────────────┐
              │                       │ Task State Mgr   │  (deterministic,
              │                       │ session-scoped   │   session_id-keyed)
              │                       │ assigns confidence│
              │                       │ for location      │
              │                       └────────┬──────────┘
              │                                ▼
              │                       ┌─────────────────┐
              │                       │  Planner          │  (deterministic —
              │                       │  (Facts, priority,│   NO LLM here)
              │                       │   trigger rule)    │
              │                       └────────┬──────────┘
              │                     CommunicationPlan
              │                                ▼
              │                       ┌─────────────────┐
              └──────────────────────▶│ Dependency        │
                                       │ Executor          │  (ready frames only)
                                       └────────┬──────────┘
                                     TaskResult[]
                                                ▼
                                       ┌─────────────────┐
                                       │ Response Writer   │  (LLM call #2 —
                                       │  (CommunicationPlan│   phrasing only)
                                       │   + TaskResults)   │
                                       └────────┬──────────┘
                                                ▼
                                       Streamed reply
```

Still exactly **2 LLM calls per turn** (Segmenter, Writer) in the normal path. The
confirmation pre-check adds a 3rd path that's pure Python and skips both LLM calls
entirely when it applies — cheaper and instant for "yes, book it" replies.

---

## 2. Data models

```python
# app/models/task_models.py
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field
from app.models.response_models import SourcedStep


class TaskIntent(str, Enum):
    FIND_SCHEME = "find_government_schemes"
    FIND_FACILITY = "find_facilities"
    SCHEDULE = "schedule_appointment"


class TaskStatus(str, Enum):
    COLLECTING = "collecting"
    READY = "ready"
    AWAITING_CONFIRMATION = "awaiting_confirmation"   # NEW — SCHEDULE only
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Fact(BaseModel):
    value: Optional[str] = None
    confidence: Literal["high", "low"] = "high"
    # WHO set confidence, stated explicitly per the review:
    #   value + user_specified  → always set by the Segmenter (reading what user said)
    #   confidence               → for `location` specifically, set by the Task State
    #                               Manager based on whether request.coordinates was
    #                               present — the Segmenter cannot know GPS status.
    #                               For all other facts, confidence defaults "high"
    #                               once user_specified=true.
    user_specified: bool = False   # true = user explicitly gave/decided this,
                                    # false = system inferred/placeholder


class TaskFrame(BaseModel):
    task_id: str
    intent: TaskIntent
    goal: str                                    # e.g. "book an eye checkup"
    facts: dict[str, Fact] = Field(default_factory=dict)         # required-for-execution
    preferences: dict[str, Fact] = Field(default_factory=dict)   # optional, UX-only
    depends_on: Optional[str] = None
    status: TaskStatus = TaskStatus.COLLECTING
    just_learned: dict[str, str] = Field(default_factory=dict)   # reset+refilled each turn
    results: list[SourcedStep] = Field(default_factory=list)
    created_turn: int = 0
    updated_turn: int = 0

    @property
    def missing_required(self) -> list[str]:
        required = REQUIRED_FACTS[self.intent]
        return [f for f in required if not self.facts.get(f) or not self.facts[f].value]

    @property
    def stage(self) -> str:
        """Computed, not stored — avoids a second source of truth (v1 Problem 4 fix)."""
        if self.status == TaskStatus.DONE: return "done"
        if self.status == TaskStatus.FAILED: return "failed"
        if self.status == TaskStatus.RUNNING: return "executing"
        if self.status == TaskStatus.AWAITING_CONFIRMATION: return "confirm"
        if self.status == TaskStatus.READY and self.results: return "recommend"
        if self.status == TaskStatus.READY: return "search"
        if self.facts: return "collecting_preferences"
        return "understand"


class SessionContext(BaseModel):
    """Facts that outlive any single task frame — inherited by new frames on creation."""
    known_location: Optional[Fact] = None
    known_coordinates: Optional[dict] = None
    known_for_member: Optional[Fact] = None
    family_profile: list = Field(default_factory=list)


class CommunicationPlan(BaseModel):
    """Output of the deterministic Planner. The Writer LLM never decides any of this,
    only phrases it."""
    report_results: list[str] = Field(default_factory=list)   # task_ids to report
    acknowledge: list[str] = Field(default_factory=list)       # "task_id.fact_name" just learned
    ask: list[str] = Field(default_factory=list)               # "task_id.fact_name" — top priority missing fact per blocked task
    offer_preference: list[str] = Field(default_factory=list)  # "task_id.preference_name"
    confirm: list[str] = Field(default_factory=list)           # task_ids awaiting confirmation
    low_confidence_flags: list[str] = Field(default_factory=list)  # "task_id.fact_name" needing a re-ask, different phrasing
```

```python
REQUIRED_FACTS = {
    TaskIntent.FIND_SCHEME: ["condition"],
    TaskIntent.FIND_FACILITY: ["condition", "location"],
    TaskIntent.SCHEDULE: ["procedure", "date", "hospital"],
    # NOTE: "hospital" is required for SCHEDULE, but is ALWAYS filled by a dependency
    # on a FIND_FACILITY frame's result (see §5 decomposition rule) — SCHEDULE never
    # asks the user for a raw location itself. This is what fixes the trigger-rule
    # contradiction the review caught.
}

PREFERENCE_TRIGGERS = {
    # Only offered when the frame has ZERO missing required facts this turn,
    # and the preference hasn't been resolved or explicitly declined.
    TaskIntent.FIND_FACILITY: ["facility_ranking"],   # nearest vs. highest-rated
    TaskIntent.SCHEDULE: ["time_of_day"],             # morning/afternoon/evening, soft only
}
```

---

## 3. Task Segmenter (LLM call #1) — v2 changes

Same shape as v1 §4, with these additions to the schema and prompt:

**Schema additions:**
```python
"preferences": {
    "type": "object",
    "properties": {
        "facility_ranking": {"type": "string", "enum": ["nearest", "highest_rated", "no_preference", ""]},
        "time_of_day": {"type": "string", "enum": ["morning", "afternoon", "evening", ""]},
    }
},
"user_specified": {
    "type": "object",
    "description": "For each key present in slots or preferences, true if the user explicitly stated/decided it, false if inferred or defaulted",
    "additionalProperties": {"type": "boolean"}
},
"decompose_into_facility_then_schedule": {
    "type": "boolean",
    "description": "true if this task is 'schedule X [near me / at Y]' — location or hospital talk that belongs to finding a facility, not the schedule action itself"
}
```

**Prompt addition:**
```
== DECOMPOSITION RULE (IMPORTANT) ==
If the user's message is "schedule/book [procedure] [near me / at a nearby clinic /
somewhere close]" — this is TWO tasks, not one:
  1. find_facilities (to determine WHICH hospital)
  2. schedule_appointment (depends on task 1's result for "hospital")
Set decompose_into_facility_then_schedule=true and emit BOTH tasks, with the
schedule_appointment task's depends_on_new_task=true.
Only skip this decomposition if the user names a SPECIFIC hospital directly
("schedule at Apollo") — then schedule_appointment can stand alone with hospital
already known.

== EXPLICIT DECLINE DETECTION ==
Phrases like "any is fine", "you choose", "no preference", "doesn't matter" against a
specific fact or preference should be extracted with user_specified=true and the
value set to "no_preference" (for preferences) or a resolving default (for facts,
e.g. hospital="find_nearest" only if paired with a resolved location). This marks the
item CLOSED — it must never be asked again for this task.
```

---

## 4. Task State Manager — v2 (session-scoped, confidence assignment)

```python
# app/orchestrator/task_state.py
import uuid
from app.models.task_models import RawTask, TaskFrame, TaskStatus, Fact, SessionContext, REQUIRED_FACTS

class TaskStateManager:
    def __init__(self):
        self._frames: dict[str, dict[str, TaskFrame]] = {}       # session_id -> task_id -> frame
        self._session_ctx: dict[str, SessionContext] = {}        # session_id -> context
        self._turn: dict[str, int] = {}

    def _get(self, session_id: str) -> dict[str, TaskFrame]:
        return self._frames.setdefault(session_id, {})

    def open_tasks_summary(self, session_id: str) -> list[dict]:
        return [
            {"task_id": tid, "intent": f.intent.value, "known_facts": {k: v.value for k, v in f.facts.items()},
             "missing": f.missing_required}
            for tid, f in self._get(session_id).items()
            if f.status in (TaskStatus.COLLECTING, TaskStatus.READY)
        ]

    def merge(self, session_id: str, raw_tasks: list[RawTask], coordinates: dict | None) -> list[TaskFrame]:
        self._turn[session_id] = self._turn.get(session_id, 0) + 1
        turn = self._turn[session_id]
        frames = self._get(session_id)
        ctx = self._session_ctx.setdefault(session_id, SessionContext())
        touched = []

        for rt in raw_tasks:
            if rt.refers_to_existing_task and rt.refers_to_existing_task in frames:
                frame = frames[rt.refers_to_existing_task]
                frame.just_learned = {}
            else:
                frame = TaskFrame(
                    task_id=f"t{uuid.uuid4().hex[:8]}", intent=rt.intent,
                    goal=self._goal_text(rt.intent), created_turn=turn,
                )
                # Pre-fill from session context — new tasks inherit known facts
                if ctx.known_location and rt.intent != TaskIntent.SCHEDULE:
                    frame.facts["location"] = ctx.known_location
                frames[frame.task_id] = frame

            for k, v in rt.slots.items():
                if not v or k == "location_is_relative":
                    continue
                is_pref = k in ("facility_ranking", "time_of_day")
                target = frame.preferences if is_pref else frame.facts
                target[k] = Fact(value=v, user_specified=rt.user_specified.get(k, True))
                frame.just_learned[k] = v

            # THE ACTUAL FIX — confidence for location is Python-assigned, never LLM-guessed
            if rt.slots.get("location_is_relative"):
                if coordinates and coordinates.get("lat") and coordinates.get("lng"):
                    frame.facts["location"] = Fact(value=f"{coordinates['lat']},{coordinates['lng']}",
                                                     confidence="high", user_specified=True)
                    ctx.known_coordinates = coordinates
                    frame.just_learned["location"] = "your current location"
                else:
                    frame.facts["location"] = Fact(value=None, confidence="low", user_specified=True)
                    frame.just_learned["location_unresolved"] = "true"

            if frame.facts.get("location") and frame.facts["location"].confidence == "high":
                ctx.known_location = frame.facts["location"]

            frame.updated_turn = turn
            frame.status = TaskStatus.READY if not frame.missing_required else TaskStatus.COLLECTING
            touched.append(frame)

        return touched

    def dependency_ready(self, session_id: str) -> list[TaskFrame]:
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

    def blocked(self, session_id: str) -> list[TaskFrame]:
        return [f for f in self._get(session_id).values() if f.status == TaskStatus.COLLECTING]

    def awaiting_confirmation(self, session_id: str) -> Optional[TaskFrame]:
        for f in self._get(session_id).values():
            if f.status == TaskStatus.AWAITING_CONFIRMATION:
                return f
        return None

    @staticmethod
    def _goal_text(intent: TaskIntent) -> str:
        return {
            TaskIntent.FIND_SCHEME: "check government scheme eligibility",
            TaskIntent.FIND_FACILITY: "find a suitable clinic/hospital",
            TaskIntent.SCHEDULE: "book an appointment",
        }[intent]
```

---

## 5. Deterministic Planner (no LLM)

```python
# app/orchestrator/planner.py
from app.models.task_models import TaskFrame, TaskStatus, CommunicationPlan, REQUIRED_FACTS, PREFERENCE_TRIGGERS

def plan(frames: list[TaskFrame], done_results: list) -> CommunicationPlan:
    p = CommunicationPlan()

    for r in done_results:
        p.report_results.append(r.task_id)

    for f in frames:
        if f.status != TaskStatus.COLLECTING:
            continue

        # Acknowledge whatever was just learned this turn
        for k in f.just_learned:
            if k == "location_unresolved":
                p.low_confidence_flags.append(f"{f.task_id}.location")
            else:
                p.acknowledge.append(f"{f.task_id}.{k}")

        # Ask for the highest-priority missing fact — ONE per task, priority = REQUIRED_FACTS order
        missing = f.missing_required
        if missing:
            p.ask.append(f"{f.task_id}.{missing[0]}")

        # Offer a preference ONLY if zero missing required facts (the corrected per-frame rule)
        if not missing:
            for pref_name in PREFERENCE_TRIGGERS.get(f.intent, []):
                already_set = pref_name in f.preferences and f.preferences[pref_name].user_specified
                if not already_set:
                    p.offer_preference.append(f"{f.task_id}.{pref_name}")
                    break  # cap at one preference offer per task, per turn

    for f in frames:
        if f.status == TaskStatus.AWAITING_CONFIRMATION:
            p.confirm.append(f.task_id)

    return p
```

This is the piece that makes the trigger rule a **guarantee**: it's an `if` statement,
not a prompt instruction an LLM might ignore under pressure.

---

## 6. Confirmation gate

```python
# In orchestrator.handle(), BEFORE segmentation:

pending_confirm = self.task_state.awaiting_confirmation(session_id)
if pending_confirm:
    decision = classify_yes_no(request.message)   # cheap — regex/small classifier, not a full LLM call
    if decision == "yes":
        result = await self.executor.run_all([pending_confirm], ...)
        reply = await self.compose_response([result], blocked=[], ...)
        yield StreamChunk(type="message", content=reply)
        return
    elif decision == "no":
        pending_confirm.status = TaskStatus.COLLECTING  # reopen for changes
        yield StreamChunk(type="message", content="No problem — what would you like to change?")
        return
    # else: ambiguous — fall through to normal segmentation,
    # the new message might be answering something else entirely or changing details

# When a SCHEDULE frame's required facts complete (in the Planner/merge step):
if frame.intent == TaskIntent.SCHEDULE and not frame.missing_required:
    frame.status = TaskStatus.AWAITING_CONFIRMATION   # NOT READY — never auto-executes
```

`schedule_appointment` never fires from `READY` status directly — it can only be
executed from a user's explicit "yes." This closes the original active bug
("no confirmation gate before Calendar API fires") structurally.

---

## 7. Response Writer (LLM call #2) — takes a plan, not raw facts

```
SYSTEM:
You write WithCare's replies. You are given a CommunicationPlan that already decided
everything — what to acknowledge, what to ask, what preference to offer, what to
confirm. Your ONLY job is natural phrasing. Do not add new questions, do not omit
items in the plan, do not decide priority — that's already done.

Rules:
- ACKNOWLEDGE items: briefly confirm you understood, don't just repeat the value back robotically.
- ASK items: phrase as a goal-shaped question, not a form field. "Should I look for a
  clinic near you, or do you have one in mind?" not "What is your location?"
- LOW_CONFIDENCE_FLAGS: phrase differently from a normal ask — acknowledge the
  attempt failed gently. "I'm having trouble finding your exact location — what area
  or city should I search?" not a repeat of the original question.
- OFFER_PREFERENCE items: phrase as an optional add-on to the main ask, same
  sentence, not a separate question. Never make it sound mandatory.
- CONFIRM items: state exactly what will happen if they say yes, in one sentence,
  ending in a clear yes/no ask.
- REPORT_RESULTS: 1-2 sentences per task, lead with the top result, invite follow-up
  rather than dumping every detail.
- Combine everything into ONE message. Vary phrasing across turns — don't reuse the
  same sentence structure every time this conversation happens.
- Never mention task IDs, facts, confidence, or any internal field names.

---
PLAN:
{communication_plan_json}

RESOLVED VALUES (for filling in acknowledge/confirm text — task_id → relevant facts):
{resolved_values_json}

CONVERSATION SO FAR (last 4 turns, for tone):
{history_text}
```

---

## 8. Maps tool fix (`maps_tool.py`) — the actual root-cause patch

Confirmed against your code: `find_nearby_hospitals` always calls `geocode()` on its
`location` argument, and `geocode()` unconditionally appends `", India"` — which
mangles `"17.4,78.5"` into a garbage forward-geocode query. Places already returns
`lat`/`lng` per result (lines 81-82), so distance can be computed locally with zero
extra API calls, and `distance_text` never needs to exist as a dict key at all.

```python
# maps_tool.py — additions/changes

import math

def _is_coordinate_pair(s: str) -> bool:
    parts = s.split(",")
    if len(parts) != 2:
        return False
    try:
        float(parts[0].strip()); float(parts[1].strip())
        return True
    except ValueError:
        return False

def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlambda/2)**2
    return R * 2 * math.asin(math.sqrt(a))


async def find_nearby_hospitals(location: str, specialty: str = "", radius_meters: int = 15000, max_results: int = 5):
    origin_lat = origin_lng = None

    if _is_coordinate_pair(location):
        # FIX: skip geocode entirely when we already have coordinates —
        # this is what was silently mangling GPS input through ", India"
        origin_lat, origin_lng = (float(x.strip()) for x in location.split(","))
    else:
        coords = await geocode(location)
        if not coords:
            return []
        origin_lat, origin_lng = coords["lat"], coords["lng"]

    # ... existing Places API call, using f"{origin_lat},{origin_lng}" directly
    # as the location param (NOT through geocode again) ...

    results = []
    for place in data.get("results", [])[:max_results]:
        plat = place["geometry"]["location"]["lat"]
        plng = place["geometry"]["location"]["lng"]
        results.append({
            "name": place.get("name", ""),
            "address": place.get("vicinity", ""),
            "rating": place.get("rating"),
            "user_ratings_total": place.get("user_ratings_total", 0),
            "place_id": place.get("place_id"),
            "maps_url": f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id')}",
            "lat": plat, "lng": plng,
            # FIX: real distance, computed locally, no missing dict key
            "distance_km": round(_haversine_km(origin_lat, origin_lng, plat, plng), 1),
            "open_now": place.get("opening_hours", {}).get("open_now"),
        })
    results.sort(key=lambda r: r["distance_km"])   # actually sorted by proximity now
    return results


async def get_distance(origin: str, destination: str) -> dict | None:
    # FIX: don't append ", India" to something that's already coordinates
    origin_param = origin if _is_coordinate_pair(origin) else origin + ", India"
    resp = await client.get(DISTANCE_URL, params={
        "origins": origin_param,
        "destinations": destination + ", India",
        "key": settings.google_maps_api_key,
    })
    # ... rest unchanged
```

**Downstream change needed in `facility_agent.py`:** the `float(mh["distance_text"]...)`
line (~161) reading a now-nonexistent key must become `mh["distance_km"]` directly —
no parsing, no `except: pass` swallowing failures silently. Also, since `find_nearby_hospitals`
now returns pre-sorted, correct results, the reverse-geocode-once-for-Firestore-city
step (mentioned in the review as the Bug B fix) should happen at the top of
`FacilityAgent.run()` when `coordinates` is present but `city` is empty — one Maps
reverse-geocode call, cached per session, so Firestore's `city` filter and the Maps
proximity search agree on the same place instead of drifting (the actual cause of the
Hyderabad/Hinganghat split in your screenshot).

---

## 9. Dependency Executor — one addition

The FIND_FACILITY → SCHEDULE decomposition means the old "auto-trigger facility
search if ADK skipped it" safety net in `schedule_appointment` is **deleted, not
ported** — the chain structurally guarantees facility search runs first. The Executor
from v1 §6 is otherwise unchanged; `_execute_one` for `SCHEDULE` now always expects
`prior_output.intent == FIND_FACILITY` to be present when `depends_on` is set, and
uses `prior_output.steps[0]` for the hospital instead of a fallback re-search.

---

## 10. What's new / to build (updated from v1)

1. `app/models/task_models.py` — `Fact`, `TaskFrame` v2, `SessionContext`, `CommunicationPlan`
2. `app/orchestrator/task_state.py` — session-scoped, confidence assignment (§4)
3. `app/orchestrator/planner.py` — new, deterministic (§5)
4. `app/orchestrator/segmenter.py` — v2 prompt with decomposition + preference extraction (§3)
5. `app/orchestrator/composer.py` — rewritten to take `CommunicationPlan`, not raw slots (§7)
6. `app/orchestrator/executor.py` — mostly v1, minus the deleted safety net (§9)
7. `maps_tool.py` — haversine fix, skip-geocode-for-coordinates (§8) — **required**, not optional, or `facility_ranking` preference has no data
8. `facility_agent.py` — small change: read `distance_km` directly, add reverse-geocode-once for city (§8)
9. `WithCareOrchestrator.handle()` — confirmation pre-check + full pipeline (§2, §6)

## 11. What stays fully untouched

- `SchemeAgent`, `ActionAgent` internal logic
- `SourcedStep`, `CarePlan`, `StreamChunk` models
- `create_calendar_event`, `sync_to_family_calendar`, Firestore query tool
- `classify_intent` clinical/ambiguity router — still runs first, unchanged

---

## Still open — need your call before implementation starts

1. **`classify_yes_no` in §6** — simple enough to be regex/keyword-based ("yes", "go ahead", "book it" vs "no", "wait", "change") rather than an LLM call, to keep confirmation cheap and instant. Confirm this is fine, or you'd rather it always go through the Writer for a more flexible confirm/decline read.
2. **Reverse-geocode caching** in §8 — cache per `session_id` for the conversation's duration (avoids repeat API calls if multiple facility searches happen in one session) — confirm that's acceptable versus always calling fresh.
