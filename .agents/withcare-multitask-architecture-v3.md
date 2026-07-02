# Withcare — Multi-Task Conversation Architecture v3 (corrections)

Supersedes v2. v2's foundation is kept; this fixes the internal contradictions the
review caught around the SCHEDULE frame lifecycle, the dependency wiring, the
preference offer, and the confirmation gate — so the spec is consistent before code.

Read v2 for anything not restated here. Only the deltas are below.

---

## The one coherent SCHEDULE lifecycle (fixes C1, C2, I2)

`hospital` is **removed from `REQUIRED_FACTS[SCHEDULE]`**. It is never a user-asked fact —
it is injected by the FIND_FACILITY dependency (or set directly if the user named a
hospital). This kills the "which hospital do you want?" anti-pattern.

```python
REQUIRED_FACTS = {
    TaskIntent.FIND_SCHEME:   ["condition"],
    TaskIntent.FIND_FACILITY: ["condition", "location"],
    TaskIntent.SCHEDULE:      ["procedure", "date"],   # hospital is dependency-injected
}
```

Single lifecycle, every SCHEDULE path funnels through it:

```
COLLECTING (needs procedure/date)
   │  procedure + date filled
   ▼
 ┌── standalone, user named a hospital ──────────────► AWAITING_CONFIRMATION
 │
 └── "near me" / no hospital → has depends_on(FIND_FACILITY)
        │  facility runs, executor injects hospital into the frame
        ▼
     AWAITING_CONFIRMATION
        │  user says "yes"
        ▼
     RUNNING → DONE   (action_agent books the calendar event here, and ONLY here)
```

Rules that make this deterministic:
- A SCHEDULE frame **never** enters `RUNNING` from `merge()` or from the normal executor
  pass. The only path to `RUNNING` is the confirmation gate on an explicit "yes".
- In `merge()`, after filling facts: if `intent == SCHEDULE and not missing_required and
  no depends_on` → status = `AWAITING_CONFIRMATION`. (Named-hospital standalone case.)
- If `intent == SCHEDULE and depends_on is set` → status = `READY` but gated by
  `dependency_ready` until the facility frame is `DONE`; the executor then transitions it
  to `AWAITING_CONFIRMATION` (not to RUNNING).
- All other intents: `READY if not missing_required else COLLECTING` (unchanged).

---

## Dependency wiring lives in `merge()` (fixes I1)

The Segmenter emits two tasks for "schedule X near me" (a `find_facilities` and a
`schedule_appointment` with `depends_on_new_task=true`). Deterministic `merge()` must
**wire the link** — the Segmenter only flags it:

```python
def merge(self, session_id, raw_tasks, coordinates):
    ...
    # Process FIND_FACILITY tasks before SCHEDULE so the facility id exists to link to.
    raw_tasks = sorted(raw_tasks, key=lambda rt: rt.intent != TaskIntent.FIND_FACILITY)
    new_facility_id = None
    for rt in raw_tasks:
        frame = ...  # create or fetch (as v2)
        ... # fill facts / preferences / location-confidence (as v2)

        if frame.intent == TaskIntent.FIND_FACILITY:
            new_facility_id = frame.task_id
        if frame.intent == TaskIntent.SCHEDULE and rt.depends_on_new_task and new_facility_id:
            frame.depends_on = new_facility_id

        # status transition (the lifecycle rules above)
        if frame.intent == TaskIntent.SCHEDULE:
            if not frame.missing_required and not frame.depends_on:
                frame.status = TaskStatus.AWAITING_CONFIRMATION
            elif not frame.missing_required:      # has depends_on → gated ready
                frame.status = TaskStatus.READY
            else:
                frame.status = TaskStatus.COLLECTING
        else:
            frame.status = TaskStatus.READY if not frame.missing_required else TaskStatus.COLLECTING
```

---

## Confirmation-aware executor (fixes C2)

The executor **must not book inside the dependency chain**. When a chain reaches an
unconfirmed SCHEDULE frame it injects the hospital and hands control back for
confirmation instead of calling `action_agent`.

```python
async def run_all(self, ready_frames, all_frames, base_ctx, confirmed_task_id=None):
    chains = self._build_chains(ready_frames, all_frames)   # pulls READY dependents from all_frames
    results = await asyncio.gather(*[self._run_chain(c, base_ctx, confirmed_task_id) for c in chains])
    return [r for rs in results for r in rs]

def _build_chains(self, ready_frames, all_frames):
    chains, seen = [], set()
    for f in ready_frames:
        if f.task_id in seen or f.depends_on:
            continue
        chain = [f]; seen.add(f.task_id)
        # IMPORTANT: pull dependents from ALL frames (READY), not just ready_frames,
        # so a gated SCHEDULE joins its facility's chain the same turn.
        deps = [x for x in all_frames.values()
                if x.depends_on == f.task_id and x.status == TaskStatus.READY]
        chain.extend(deps); seen.update(d.task_id for d in deps)
        chains.append(chain)
    return chains

async def _execute_one(self, frame, base_ctx, prior_output, confirmed_task_id):
    if frame.intent == TaskIntent.SCHEDULE:
        # inject hospital from the facility result if this was decomposed
        if prior_output and prior_output.intent == TaskIntent.FIND_FACILITY and prior_output.steps:
            frame.facts["hospital"] = Fact(
                value=prior_output.steps[0].action.replace("Visit ", "").replace(" (nearby)", ""),
                user_specified=False,
            )
        if frame.task_id != confirmed_task_id:
            # NOT a confirmed booking → move to confirmation, do NOT call action_agent
            frame.status = TaskStatus.AWAITING_CONFIRMATION
            return TaskResult(task_id=frame.task_id, intent=frame.intent,
                              status=TaskStatus.AWAITING_CONFIRMATION,
                              steps=[])   # no calendar write yet
        # confirmed → actually book
        r = await self.action_agent.run({**base_ctx, **self._schedule_ctx(frame)})
        frame.status = TaskStatus.DONE
        return TaskResult(..., status=TaskStatus.DONE, steps=r.steps)
    ...
```

The confirmation gate (§6 v2) calls `run_all([frame], all_frames, base_ctx,
confirmed_task_id=frame.task_id)` so the "yes" path is the ONLY thing that sets
`confirmed_task_id` and therefore the only path that books.

---

## Preference offered on the DONE facility frame (fixes C3)

The Planner offers `facility_ranking` as a **re-rank invite after** the facility search
runs (it executes with `nearest` as the default), not before. The offer therefore keys
off DONE facility frames from this turn's results, not COLLECTING frames.

```python
def plan(active_frames, done_results):
    p = CommunicationPlan()
    done_ids = {r.task_id for r in done_results if r.status == TaskStatus.DONE}

    for r in done_results:
        if r.status == TaskStatus.DONE and r.steps:
            p.report_results.append(r.task_id)

    for f in active_frames:
        if f.status == TaskStatus.COLLECTING:
            for k in f.just_learned:
                (p.low_confidence_flags if k == "location_unresolved" else p.acknowledge)\
                    .append(f"{f.task_id}.{'location' if k=='location_unresolved' else k}")
            missing = f.missing_required
            if missing:
                p.ask.append(f"{f.task_id}.{missing[0]}")   # priority = REQUIRED_FACTS order

        # re-rank preference: DONE facility frame, ran this turn, pref not locked
        if f.status == TaskStatus.DONE and f.task_id in done_ids:
            for pref in PREFERENCE_TRIGGERS.get(f.intent, []):
                locked = pref in f.preferences and f.preferences[pref].user_specified
                if not locked:
                    p.offer_preference.append(f"{f.task_id}.{pref}")
                    break

        if f.status == TaskStatus.AWAITING_CONFIRMATION:
            p.confirm.append(f.task_id)
    return p
```

---

## Mid-confirmation edits attach correctly (fixes I3)

`open_tasks_summary()` must include `AWAITING_CONFIRMATION` frames, so when a user
replies to "book it?" with "actually make it 6pm" (ambiguous → falls through to
segmentation), the Segmenter sees the pending frame in OPEN TASKS and updates it
instead of forking a duplicate.

```python
if f.status in (TaskStatus.COLLECTING, TaskStatus.READY, TaskStatus.AWAITING_CONFIRMATION)
```

`classify_yes_no` stays strict: only a *bare* yes/no fast-paths; anything with extra
content ("yes but 6pm") returns `"ambiguous"` and falls through to full segmentation.
If an edit re-opens a confirmed-pending frame, re-run the lifecycle: still-complete →
back to `AWAITING_CONFIRMATION` with the new details.

---

## RawTask v2 model (fixes M1)

```python
class RawTask(BaseModel):
    intent: TaskIntent
    raw_span: str = ""
    refers_to_existing_task: Optional[str] = None
    depends_on_new_task: bool = False
    slots: dict = Field(default_factory=dict)
    preferences: dict = Field(default_factory=dict)
    user_specified: dict = Field(default_factory=dict)   # per-key bool
```

---

## Output contract + frontend (adds the missing workstream, I4)

Backend emits per turn:
- `thinking` — unchanged (agent animation).
- `step` — one per result `SourcedStep` (facility/scheme/action), unchanged shape.
- Final chunk:
  - If the turn produced result steps → `done` with
    `{ message, ordered_steps, intent_summary, for_member, session_id, generated_at }`
    where **`message` is the Writer's natural text** (replaces the canned
    "Here's your care plan — I consulted N specialists").
  - If the turn is pure ask/confirm/clarify (no steps) → `clarify` with
    `{ content: <Writer text> }` (frontend already handles this).

Frontend deltas (small, targeted):
- `useChat.js` `onDone`: use `carePlan.message` as `intro` when present; else fall back
  to the old canned line.
- `dbMsgToUiMsg`: use stored `care_plan.message` for the assistant `intro`.
- SQLite persistence: `care_plan` JSON now carries `message` alongside `ordered_steps`.
- No change to `stepsToPlan`, the card rendering, the distance/filter UI (the §8 maps
  fix makes `distance_km` real, so the existing filter chips finally have data).

---

## Build order (each step independently testable)

1. `maps_tool.py` — skip-geocode-on-coords + haversine + `reverse_geocode` + `get_distance`
   coord guard (v2 §8). Independent, fixes the visible 426 km bug. **Do first.**
2. `facility_agent.py` — read `distance_km` directly; reverse-geocode coords→city once so
   Firestore and Maps agree.
3. `app/models/task_models.py` — models above.
4. `app/orchestrator/task_state.py` — session-scoped, merge with wiring + lifecycle.
5. `app/orchestrator/segmenter.py` — LLM #1.
6. `app/orchestrator/planner.py` — deterministic.
7. `app/orchestrator/executor.py` — confirmation-aware.
8. `app/orchestrator/composer.py` — LLM #2 (Writer).
9. `orchestrator.py` — rewrite `handle()`: confirm pre-check → segment → merge →
   dependency execute → plan → write → stream. Delete ADK LlmAgent + the auto-trigger
   safety net.
10. `useChat.js` — `message` field handling.

## Untouched
`SchemeAgent`/`ActionAgent` internals, `SourcedStep`/`CarePlan`/`StreamChunk`,
`create_calendar_event`, Firestore query tool, `classify_intent` (still runs first).
