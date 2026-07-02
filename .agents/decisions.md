# WithCare — Design Decisions Log

Record every significant technical or product decision here with rationale.
This prevents re-debating settled questions and gives context to future changes.

---

## Decision Format
```
### DD-{number}: {title}
**Date:** YYYY-MM-DD
**Status:** Decided / Revisiting / Superseded by DD-{x}
**Context:** Why this decision was needed.
**Decision:** What was decided.
**Rationale:** Why this choice over alternatives.
**Consequences:** What this enables or constrains.
```

---

### DD-001: All-Google Stack
**Date:** 2026-06-30
**Status:** Decided
**Context:** Hackathon requires demonstrating Google Gen AI capabilities. Need to choose infrastructure, reasoning, and action tools.
**Decision:** Use exclusively Google services — Gemini for LLM, ADK for agents, Calendar/Drive/Gmail MCPs for actions, Cloud Run for deploy, Firestore + BigQuery for data, Maps for location.
**Rationale:** Aligns with hackathon requirements. Demonstrates deep Google ecosystem integration. Simplifies auth (single GCP project). Judges evaluate Google tech usage.
**Consequences:** No third-party LLMs, no non-Google databases, no external agent frameworks.

### DD-002: Stateless App Tier
**Date:** 2026-06-30
**Status:** Decided
**Context:** Need to credibly claim "scales to millions."
**Decision:** No server-side session state in the app tier. All state lives in Firestore/BigQuery.
**Rationale:** Any Cloud Run instance can serve any request. Horizontal autoscaling with zero re-architecture. This is the scalability story judges will probe.
**Consequences:** Must design all endpoints to be stateless. Session context passed per-request or stored in managed services.

### DD-003: Scheme Rules as Structured Logic
**Date:** 2026-06-30
**Status:** Decided
**Context:** Government scheme eligibility could be stored as free text or structured data.
**Decision:** Store as structured eligibility logic in Firestore (not free-text paragraphs).
**Rationale:** Agent can reason deterministically over rules. More reliable than LLM parsing free text every time. Verifiable outputs.
**Consequences:** Requires upfront data ingestion work. Scheme data must be curated into a schema.

### DD-004: Facility Fallback Data
**Date:** 2026-06-30
**Status:** Decided
**Context:** Google Maps API could fail during demo due to billing, rate limits, or network issues.
**Decision:** Maintain a stored facility list with coordinates as demo fallback. Maps used for live ranking only.
**Rationale:** Demo must never break. Judges should see working results regardless of external API state.
**Consequences:** Need to pre-populate facility data for demo regions. Two code paths (live Maps vs. fallback).

### DD-005: Dual OAuth for Family Calendar Sync
**Date:** 2026-06-30
**Status:** Decided
**Context:** Caregiver manages dependent's care. Events need to appear on both calendars.
**Decision:** Two independent OAuth grants — each person authorizes their own Google account. Events written to both calendars separately.
**Rationale:** Privacy-respecting. Standard family-sharing pattern (cf. Google Family Link). No single party accesses another's account without consent.
**Consequences:** More complex auth flow. Need consent management UI. Must handle case where dependent hasn't granted consent yet.

---

*Add new decisions below as they arise during development.*
