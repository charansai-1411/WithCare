# WithCare — Architecture Reference

## System Overview

```
User (natural language) → FastAPI → Orchestrator Agent
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
              Scheme Agent      Facility Agent      Action Agent
              (Firestore)       (Maps + DB)        (Calendar MCP)
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        │
                              Synthesized Care Plan
                          (ordered, sourced, actionable)
```

## Agent Roster

### Orchestrator (Primary Agent)
- **Job:** Receive natural-language situation, route to sub-agents, synthesize outputs into a single ordered care plan.
- **Behaviour:** Ask exactly one clarifying question when confidence is low. Decline clinical/diagnostic requests.
- **Framework:** Google ADK

### Sub-Agents

| Agent | Job | Tool/Data | P-level |
|-------|-----|-----------|---------|
| **Government Scheme Agent** | Match user to eligible government health schemes, return redemption path | Firestore (ingested scheme rules as structured logic) | P0 |
| **Facility Agent** | Locate and rank healthcare facilities by reachability | Google Maps + stored facility fallback | P0 |
| **Action Agent** | Book visits/reminders on real Google Calendar (both caregiver + dependent) | Google Calendar MCP | P0 |
| **Private Insurance Agent** | Read uploaded insurance doc, extract coverage, explain claim path | Google Drive MCP + Gemini doc understanding | P1 |
| **Medicine Agent** | Find affordable medicine sources (Jan Aushadhi), flag refill-due, prepare reorder | Ingested public catalogue in Firestore | P1 |
| **Database Agent** | Structured retrieval backbone for all agents | Firestore + BigQuery | P0/P1 |

## Tool & Integration Map

| Capability | Type | Provider | Priority |
|------------|------|----------|----------|
| Reasoning / LLM | Core | Gemini (AI Studio) | P0 |
| Agent orchestration | Core | Google ADK | P0 |
| Calendar actions | Real MCP | Google Calendar | P0 |
| Insurance doc source | Real MCP | Google Drive | P1 |
| Plan delivery email | Real MCP | Gmail | P1 |
| Facility location | Native tool | Google Maps | P0 (precomputed dev) |
| Live app database | Native tool | Firestore | P0 |
| Scale/analytics | Native tool | BigQuery | P1 |

## Data Sources (all public or user-provided)

| Source | Type | Agent | Notes |
|--------|------|-------|-------|
| Government health-scheme rules | Public | Scheme Agent | Ingested → Firestore as structured eligibility logic |
| Facility directory (with coordinates) | Public | Facility Agent | Stored fallback + Maps for live ranking |
| Jan Aushadhi / generic medicine catalogue | Public | Medicine Agent | Affordable-source lookup |
| User's insurance document | User-provided | Insurance Agent | Via Drive; never stored beyond session |
| Google Maps Platform | API | Facility Agent | Sparing in dev, live in prod |

## Deployment Architecture

- **Runtime:** FastAPI on Cloud Run (containerized via Docker)
- **Scaling:** Stateless tier → horizontal autoscale; managed data services scale independently
- **Database:** Firestore (live app data) + BigQuery (scale/analytics)
- **Auth:** Two independent OAuth grants (caregiver + dependent); explicit, revocable consent
- **API docs:** Auto-generated at `/docs` for judge inspection

## Key Design Decisions

1. **Family care profiles with dual calendar sync** — caregiver manages dependent's care; events land on BOTH calendars via separate OAuth grants.
2. **Facility fallback** — stored facility list with coordinates ensures demo never breaks on Maps billing hiccups.
3. **Scheme rules as structured logic** — not free text; agent reasons over structured eligibility data.
4. **Streaming responses** — multi-agent reasoning observable step-by-step.
