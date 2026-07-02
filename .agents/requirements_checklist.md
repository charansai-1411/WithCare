# WithCare — Requirements Checklist

Extracted from the PRD. Track completion status here during the build.

---

## P0 — Must-Have (cannot ship July 6 without these)

### P0-1: Natural-language intake & orchestration
- [ ] Orchestrator accepts free-text health situation
- [ ] Routes to relevant sub-agents and returns a single synthesized plan
- [ ] Asks exactly one clarifying question when confidence is low
- [ ] Declines and redirects diagnostic/clinical advice requests

### P0-2: Genuine multi-agent system (min. 4 working agents)
- [ ] Orchestrator + Government Scheme + Facility + Action(Calendar) all functioning
- [ ] Each agent has a distinct tool and data source
- [ ] Agents' individual outputs are inspectable (not merged into opaque blob)

### P0-3: Structured data retrieval
- [ ] Firestore holds facility + scheme data with a structured schema
- [ ] Scheme eligibility stored as structured logic (not free text)
- [ ] Retrieval returns precise, sourced records

### P0-4: Real-world action (Calendar)
- [ ] Visits/reminders created on a real Google Calendar via MCP
- [ ] At least one reminder type (appointment or refill) demonstrably created

### P0-5: Grounded, ordered output
- [ ] Output is an ordered action plan (sequenced steps)
- [ ] Every recommendation carries a verifiable source reference

### P0-6: Deployed API
- [ ] FastAPI on Cloud Run, public URL reachable by a judge
- [ ] `/docs` live; core flow works end-to-end on deployed URL

### P0-7: Family care profiles with consent-based calendar sync
- [ ] Caregiver can manage care for a dependent
- [ ] Events written to BOTH caregiver's and dependent's calendars
- [ ] Two independent OAuth grants (each person authorizes their own account)
- [ ] Consent is explicit and revocable

---

## P1 — Nice-to-Have (high-priority fast-follows)

- [ ] P1-1: Private Insurance Agent (Drive MCP + Gemini doc understanding)
- [ ] P1-2: Medicine Agent (affordable-source lookup + refill flag + reorder draft)
- [ ] P1-3: BigQuery layer (scale/analytics queries)
- [ ] P1-4: Gmail MCP plan delivery (send finished plan summary)
- [ ] P1-5: Streaming reasoning (user watches agents work step-by-step)

---

## P2 — Future (design for, don't build now)

- [ ] P2-1: Urgent/emergency flow
- [ ] P2-2: Real pharmacy transaction
- [ ] P2-3: Public-health data grounding (DHS MCP)
- [ ] P2-4: Ride-to-appointment
- [ ] P2-5: Multilingual intake
