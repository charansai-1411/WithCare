# Temporal Memory — time-aware memory for WithCare

WithCare's Knowledge Graph answers *"what is true now?"* — the current conditions, the current
medicines, the next appointment. **Temporal Memory** answers *"what happened, and how is it
changing?"* — the four-week blood-sugar trend, this week's missed doses, whether Dad actually
went on his walks, how Mom's weight has moved since January.

This document describes the complete architecture: the two memory tiers, the data model
(including **validity intervals**), the APIs, the retrieval + analysis pipeline, and how the two
tiers work together to produce richer, time-aware answers.

---

## 1. Two tiers of memory

| | **Current-State Memory** (existing KG) | **Temporal Memory** (new) |
|---|---|---|
| Question it answers | "What is true *now*?" | "What *happened* / how is it *changing*?" |
| Shape | One row per fact, **upserted** in place | **Append-only** log of timestamped events |
| Store | `kg_nodes` (upsert by name) | `events` table (+ vitals already append-only) |
| Example | `Metformin — 500mg, 2×/day` (latest) | `Aug 1 taken · Aug 2 missed · Aug 3 taken …` |
| Mutation | overwrite | never mutate; append + close intervals |
| Cost of a read | O(1) — the snapshot | O(window) — aggregate over a range |

They are **complements, not competitors**. The KG stays the fast source of truth for "right now";
Temporal Memory is the history the KG throws away when it upserts. A time-aware answer joins both:
the KG gives the current value, Temporal Memory gives the trajectory that led to it.

> **We already do half of this.** Vitals are stored today as `health_metric` KG nodes written
> with `unique="never"` — i.e. append-only, one node per reading, sorted by `data.at`. Temporal
> Memory **generalises that proven pattern** to every domain (adherence, dose changes,
> appointments, labs, exercise/diet) in a single indexed `events` table, and adds the analysis
> layer (trends, summaries, adherence, prediction) on top.

---

## 2. Data model

### 2.1 The `events` table (append-only)

```sql
CREATE TABLE IF NOT EXISTS events (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    profile_id   TEXT,                 -- who it's about (the family member)
    domain       TEXT NOT NULL,        -- vital | medication | exercise | diet | appointment
                                       -- | lab | reminder | health_event
    subject      TEXT DEFAULT '',      -- the thing: 'Metformin', 'Morning walk', 'HbA1c', 'Cardiologist'
    event_type   TEXT NOT NULL,        -- reading | taken | missed | skipped | done | changed
                                       -- | booked | attended | recorded | noted
    value        REAL,                 -- numeric payload (170, 62, 45) when applicable
    value2       REAL,                 -- second number (diastolic BP)
    unit         TEXT DEFAULT '',      -- mg/dL, kg, min, mmHg
    status       TEXT DEFAULT '',      -- adherence status echo / free label

    occurred_at  TEXT NOT NULL,        -- VALID TIME: when the event happened in the real world
    recorded_at  TEXT DEFAULT (datetime('now')),  -- TRANSACTION TIME: when we learned it

    -- VALIDITY INTERVAL (for facts that hold over a span, e.g. a dose regimen)
    valid_from   TEXT,                 -- interval start (defaults to occurred_at)
    valid_to     TEXT,                 -- interval end; NULL = still in effect ("current")

    source       TEXT DEFAULT 'manual',-- manual | conversation | system | import
    subject_ref  TEXT DEFAULT '',      -- FK-ish link to the kg_nodes.id this concerns
    meta         TEXT DEFAULT '{}',    -- JSON: note, plan_day, doctor, etc.
    created_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ev_profile_time   ON events(profile_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_ev_profile_domain ON events(profile_id, domain, occurred_at);
CREATE INDEX IF NOT EXISTS idx_ev_open_interval  ON events(profile_id, subject, valid_to);
```

**Why a dedicated table and not more `kg_nodes`?** Volume and indexing. Daily adherence across
several medicines and several people is high-churn, high-row-count data; it wants its own indexed,
range-scannable table — not the general-purpose node table the whole app reads for the memory
block. Vitals stay where they are (already append-only) and are surfaced through the same temporal
API, so nothing regresses.

### 2.2 Bitemporality — two time axes

Every event carries **valid time** (`occurred_at`, and `valid_from`/`valid_to` for spans) and
**transaction time** (`recorded_at`). This is what lets us answer both:

- *"What was Mom's Metformin dose in **February**?"* → the interval whose `[valid_from, valid_to)`
  covers February. (valid time)
- *"What did we **know** on Feb 1?"* → rows with `recorded_at <= Feb 1`. (transaction time — audit)

### 2.3 Validity intervals — versioned facts

A regimen isn't a point event; it **holds over a span**. A dose change is modelled as *close the
old interval, open a new one*:

```
Metformin 500mg  valid_from=2025-01-01  valid_to=2025-03-15   (superseded)
Metformin 1000mg valid_from=2025-03-15  valid_to=NULL         (current)
```

`valid_to = NULL` means "still in effect", so **the current regimen is just the open interval** —
which is exactly what the KG's current-state node caches. One writer keeps them in lockstep
(§5): a med change appends the closing + opening interval events *and* upserts the KG node.

### 2.4 Domain cheat-sheet

| domain | typical event_type | value / meta |
|---|---|---|
| `vital` | `reading` | value(+value2 for BP), unit; metric in subject |
| `medication` | `taken` / `missed` / `changed` | dose in meta; `changed` uses validity interval |
| `exercise` | `done` / `skipped` | value=minutes, meta.plan_day |
| `diet` | `done` / `skipped` / `noted` | meta.meal |
| `appointment` | `booked` / `attended` / `missed` | subject=specialty, occurred_at=date, meta.doctor |
| `lab` | `recorded` | subject=test, value=result, links to Reader doc |
| `reminder` | `fired` / `acknowledged` | subject=reminder |
| `health_event` | `noted` | free-text symptom/incident in meta.note |

---

## 3. APIs

All under `/api/temporal`, header `x-user-id`, body carries `profile_id`.

| Endpoint | Purpose |
|---|---|
| `POST /adherence` | log a dose/exercise as `taken`/`missed`/`skipped`/`done` (manual check-off) |
| `POST /event` | generic event append (conversational logging, imports) |
| `POST /med-change` | change a medicine's dose/schedule → closes old interval, opens new |
| `POST /timeline` | events in a window: `{profile_id, domain?, since:'week'|'month'|'year'|ISO, until?}` |
| `POST /trend` | `{profile_id, metric}` → first, last, delta, slope, direction, series |
| `POST /adherence-report` | `{profile_id, subject?, since}` → taken/total, %, missed dates |
| `POST /summary` | `{profile_id, period:'week'|'month'}` → cross-domain health summary |
| `POST /next` | `{profile_id, of:'appointment'|'medication'|'checkup'}` → the next upcoming item |
| `POST /attention` | `{profile_id}` → heuristic "worth a look" flags (see §6) |

---

## 4. Retrieval + analysis pipeline

```
question ──▶ resolve profile ──▶ classify time window (week/month/year/all)
                                       │
                    ┌──────────────────┼───────────────────┐
                    ▼                  ▼                    ▼
              events_between()   current KG snapshot   (labs → Reader RAG)
                    │                  │                    │
                    ▼                  ▼                    ▼
              aggregate:  trend() · adherence_stats() · summary() · next() · attention()
                    │
                    ▼
        compact, pre-computed facts injected into the answer
        (numbers are computed in CODE — the LLM only narrates them)
```

**Time-window parsing.** "last week / this month / since January / last year" → a concrete
`[start, end]` used for the range scan. Relative words resolve against `datetime('now')`.

**Cost discipline.** Trends, deltas, adherence % and attention flags are **computed in Python**
(deterministic, free). Gemini is used only to *phrase* the already-computed numbers, or not at all
when a template suffices. No per-reading LLM calls.

---

## 5. Integration with the Knowledge Graph

**One writer, both tiers.** State-changing operations update *both* memories atomically at the
service layer:

```
add_medication()      → KG upsert (current)   + events: 'changed' opens an interval
mark dose taken/missed→ (no KG change)         + events: 'taken'/'missed'
change dose           → KG upsert (new dose)   + events: close old interval, open new
log_vital()           → KG health_metric node  (already append-only; read via temporal API)
book/attend appt      → KG appointment (current)+ events: 'booked'/'attended'
```

- **KG = the head of each interval.** The current-state node is always equal to the open
  (`valid_to = NULL`) interval in Temporal Memory. They can't drift because the same call writes
  both.
- **`subject_ref`** links an event back to the KG node it concerns, so a trend can name the exact
  current medicine/appointment.
- **Memory block.** The compact per-profile memory the agents already receive is extended with a
  one-line temporal digest ("BP trending ↑ 4 wks; Metformin adherence 80% this week") so even a
  plain answer is time-aware, before any tool call.

---

## 6. Trend detection & prediction (heuristic + statistical)

Deterministic, explainable, cheap — no ML infra:

- **Trend** = least-squares slope over the window + first/last delta → `rising | falling | stable`.
- **Rolling averages** smooth day-to-day noise (7-day / 30-day).
- **Adherence** = `taken / (taken + missed)` over the window; also the missed dates.
- **Attention flags** (rules that surface "worth a look"):
  - a vital trending the wrong way N+ consecutive periods (e.g. sugar ↑ 3 weeks),
  - adherence below a threshold (e.g. < 70% this week),
  - a vital crossing a guidance band (e.g. fasting sugar > 180, BP > 140/90),
  - weight change beyond ±5% in a month,
  - an overdue routine check-up (last `attended` older than its cadence).
- **Light forecast (optional slice):** project the slope to estimate *when* a threshold is crossed
  ("at this rate, ~2 weeks to cross 200") — still just linear/EWMA, no model hosting.

Every flag is **navigational, never clinical**: "this trend may be worth discussing with her
doctor", never a diagnosis or a dose.

---

## 7. Worked examples (the whole point)

| User asks | Tiers used | Answer |
|---|---|---|
| "How is Mom doing?" | KG (current sugar) + trend() | "Over the last 4 weeks her blood sugar rose from 130 → 170 — an upward trend worth raising with her doctor." |
| "Has Dad been exercising?" | adherence_report(exercise) | "He completed 3 of the last 5 planned walks." |
| "Weekly medication report" | adherence_report(medication, week) | "Metformin: 5/7 doses taken; missed Tue and Fri." |
| "Any weight change?" | trend(weight) | "Down 6 kg over four months (68 → 62)." |
| "When's the next check-up?" | next(checkup) | "Eye check-up on 12 Aug; last one was 14 months ago." |
| "What was her dose in February?" | validity interval | "500 mg twice daily — it changed to 1000 mg on 15 Mar." |

---

## 8. Production concerns

- **Storage** lives in the same SQLite-on-GCS volume as the KG (single-writer, `max-instances=1`).
  The append-only, indexed `events` table is the natural first thing to move to Firestore/BigQuery
  when scaling out; the service API is written so that swap is transparent to callers.
- **Retention / rollups.** Raw daily events can be rolled into weekly/monthly aggregates after a
  retention window to bound growth; the summary API reads rollups when present, raw otherwise.
- **Privacy.** Temporal Memory is per-profile and per-user, same isolation as the KG; nothing
  cross-tenant. Health history never leaves the user's own store.
- **Safety.** The analysis layer surfaces *navigation* ("worth discussing", "overdue"), never
  clinical judgement — consistent with WithCare's clinical-gate guarantees.
```
