# Withcare — Product Requirements Document (PRD)

**Tagline:** *Healthcare, with care.*
**One line:** A multi-agent AI care companion that turns a person's messy, ongoing health situation into a managed, affordable, fully-scheduled plan — and acts on it.

**Hackathon:** Google Gen AI 2.0 Cohort 2 — Problem Statement 1 (Decision Intelligence Platform)
**Solution area:** Healthcare Access & Community Wellness
**Build type:** Solo · 7-day prototype · Deployed (Cloud Run URL + GitHub repo + 3-min demo video)
**Version:** v1 (Prototype, July 6) → v2 (Top-100 Refinement)

---

## 1. Problem Statement

In India, managing an *ongoing* health situation — a chronic condition, post-procedure recovery, or an elderly parent's continuing care — forces an ordinary person (usually a family caregiver, not a clinician) to juggle disconnected, high-stakes tasks across systems that never talk to each other: finding the right facility, figuring out which government scheme or private insurance covers it and how to redeem it, sourcing affordable medicines, and keeping a calendar of visits, refills, and follow-ups. Each task lives on a different portal, in a different document, or only in someone's memory. The cost of getting it wrong is measured in money lost to uncovered bills, missed medication, and avoidable health deterioration.

Today this navigation is done by panicked web searches, phone calls, and word of mouth — slow, error-prone, and expensive. There is no single intelligence holding the whole picture and turning it into an executable plan. **Withcare is that intelligence.**

---

## 2. What Withcare Is (and Is Not)

**Withcare is** a decision-intelligence and care-navigation platform. A user describes their situation in natural language; a coordinated team of AI agents reasons across real public data sources and the user's own documents to produce — and then *execute* (schedule, remind, prepare) — a concrete ongoing care plan.

**Withcare is NOT** a diagnostic tool, symptom checker, or source of clinical advice. It never tells a user what disease they have or what treatment to take. It operates strictly on the **access, eligibility, affordability, logistics, and scheduling** side of healthcare. This boundary is a hard product rule, not a guideline.

---

## 3. Goals

1. **Collapse time-to-plan.** Convert a free-text health situation into a complete, sourced, ordered care plan in under 60 seconds — replacing what today takes a caregiver hours or days across multiple portals.
2. **Surface entitled coverage.** For every plan, identify the government schemes and private-insurance coverage the user is actually entitled to, and produce the specific redemption/claim path — closing the gap between coverage that exists and coverage that gets used.
3. **Move from advice to action.** Do not just recommend — execute: schedule visits and reminders on the user's real calendar, prepare medicine reorders, and assemble ready-to-use artifacts (application checklists, plan summaries).
4. **Ground every claim.** Every recommendation in the plan links to a verifiable source (a facility record, a scheme rule, a clause in the user's uploaded document). Zero unsourced health guidance.
5. **Prove scalable architecture.** Demonstrate a stateless, containerized, multi-agent system on managed Google infrastructure that is credibly scalable to millions of users without re-architecture.

---

## 4. Non-Goals (explicitly out of scope, with rationale)

1. **Clinical diagnosis or treatment advice** — out of scope permanently. It is a safety and liability boundary, and it converts the product into an LLM symptom-checker, which is exactly what loses.
2. **Doctor-side / hospital-operations tooling** — out of scope. Requires private EHR/operational data that is privacy-walled and unobtainable; the defensible data and the scope both live on the patient/caregiver side.
3. **Real-time clinical data** (live bed counts, live queue status) — out of scope for v1. Most such feeds are not public; v1 commits to data whose cadence (directory, scheme rules, medicine catalogues) is honestly stable.
4. **Actually placing pharmacy orders / making payments** — out of scope for v1. No trustworthy public ordering API exists in the timeline; v1 *prepares* the reorder and reminds, it does not transact. Prevents demoing a fake transaction.
5. **Urgent / emergency "need care now" flow** — deferred to a later phase. v1 owns the *ongoing care management* moment; the urgent moment is a v2/v3 addition that reuses the same agents.

---

## 5. Target Users (Personas)

**P1 — The Family Caregiver (primary).** An adult managing a parent's or relative's ongoing care. Health-literate enough to act, not clinically trained. Time-poor, cost-sensitive, overwhelmed by fragmentation. *This is who the demo speaks to.*

**P2 — The Chronic-Condition Patient (primary).** A person managing their own continuing condition (diabetes, post-surgery recovery, ongoing medication). Needs coverage, affordable medicine, and a reliable schedule they don't have to hold in their head.

**P3 — The Coverage-Unaware Citizen (secondary).** Someone entitled to a government scheme or holding an insurance policy they don't understand, who is paying out of pocket for care that is partly or fully covered. Withcare's coverage agents exist largely for this person.

---

## 6. User Stories

**Situation intake & planning**
- As a caregiver, I want to describe my parent's situation in plain language so that I don't have to know in advance which portal, scheme, or service I need.
- As a patient, I want the system to ask me one clarifying question when my situation is ambiguous so that the plan it produces is actually right for me, not a generic answer.
- As a caregiver, I want a single ordered action plan (what to do, in what sequence) so that I'm never left guessing what the next step is.

**Coverage — government**
- As a coverage-unaware citizen, I want to know which government health schemes I qualify for so that I stop paying out of pocket for care that's covered.
- As a citizen, I want the specific redemption path for a scheme (eligibility, documents, where to apply) so that knowing I qualify actually turns into using it.

**Coverage — private insurance**
- As a policyholder, I want to upload my insurance document and be told in plain language what it covers and how to claim so that I can actually use the policy I'm paying for.

**Facility**
- As a caregiver, I want the right facilities ranked by reachability so that I choose based on what's actually accessible, not just what exists.

**Medicine**
- As a patient, I want affordable sources for my prescribed medicines and a prepared reorder when a refill is due so that I never run out and never overpay.

**Action / execution**
- As a caregiver, I want visits, follow-ups, and refill reminders placed on my real calendar automatically so that the plan runs itself instead of living in my memory.
- As a user, I want a clean summary of my whole plan I can save or share so that I can act on it offline and show it to family.

**Edge / error states**
- As a user, when a data source returns nothing for my area, I want the system to say so honestly and offer the nearest alternative so that I'm never given a false or empty answer.
- As a user, when my situation falls outside what Withcare does (e.g., I ask for a diagnosis), I want it to clearly decline and redirect so that I'm never misled into treating it as medical advice.

---

## 7. System Architecture (Multi-Agent)

### 7.1 Design principles
- **Every brain and every action surface is Google.** Reasoning (Gemini), agent framework (ADK), action (Calendar), deploy (Cloud Run), data (Firestore + BigQuery), location (Maps). The *data agents read* may come from public non-Google sources (government portals, the user's documents); that is tool-use, not a violation.
- **Stateless and horizontally scalable.** No server-side session state in the app tier; all state in managed data services. Any Cloud Run instance can serve any request, enabling scale to millions by horizontal autoscaling with no re-architecture.
- **Honest multi-agent.** Each sub-agent has a genuinely distinct job, tool, and data source. No agent exists only to inflate the count.
- **Grounded output.** Every agent returns sourced records; the orchestrator never fabricates.

### 7.2 Agent roster

**Orchestrator (primary agent)** — receives the natural-language situation, performs non-clinical intake/routing, dynamically selects and sequences the sub-agents required, requests one clarification when confidence is low, and synthesizes all sub-agent outputs into a single ordered, sourced care plan.

**Sub-agents (each: distinct job · distinct tool · distinct data):**

1. **Government Scheme Agent** — reasons over government health-scheme eligibility rules (e.g., Ayushman Bharat, state schemes) stored as structured logic; returns qualifying schemes + redemption path. *Data: ingested public scheme rules in Firestore.*
2. **Private Insurance Agent** — reads the user's **uploaded** insurance document, extracts coverage, and explains the claim/redemption process in plain language. *Tool: Google Drive (MCP) + Gemini document understanding. Distinct from the Scheme Agent because it reasons over a user-provided document, not a public database.*
3. **Facility Agent** — locates and ranks facilities by reachability. *Tool: Google Maps Platform (used sparingly/precomputed in dev, live in prod). Fallback: stored facility list with coordinates so the live demo never breaks on a billing/API hiccup.*
4. **Medicine Agent** — finds affordable medicine sources (e.g., Jan Aushadhi public catalogue) and prepares reorders / flags due refills. *Data: ingested public medicine-source data; reorder = prepare + remind, not transact.*
5. **Database Agent** — structured retrieval backbone all agents draw on. *Tools: Firestore (live app data) + BigQuery (scale/analytics queries).*
6. **Action Agent** — executes the plan in the real world. *Tool: Google Calendar (MCP) — books visits/follow-ups, sets medicine & appointment reminders. Optional: Gmail (MCP) to send the plan summary.*

### 7.3 Tool & integration map

| Capability | Integration type | Provider | v1 status |
|---|---|---|---|
| Reasoning / LLM | Core | Gemini (AI Studio) | P0 |
| Agent orchestration | Core | Google ADK | P0 |
| Calendar actions | **Real MCP** | Google Calendar | P0 |
| Insurance doc source | **Real MCP** | Google Drive | P1 |
| Plan delivery email | **Real MCP** | Gmail | P1 |
| Facility location | Native tool | Google Maps | P0 (precomputed dev) |
| Live app database | Native tool | Firestore | P0 |
| Scale/analytics | Native tool | BigQuery | P1 |
| Scheme rules | Native tool (DB-backed) | Firestore | P0 |
| Medicine source | Native tool | Public catalogue | P1 |
| Pharma reorder | Native tool (sim in dev) | External | P2 |

### 7.4 Deployment
- FastAPI application, containerized (Docker), deployed on **Cloud Run** behind a public HTTPS URL.
- Auto-generated interactive API docs (FastAPI `/docs`) for judge inspection.
- Streaming responses so the multi-agent reasoning is observable step-by-step.
- Stateless tier + managed data services = horizontal autoscale to millions without re-architecture (the scalability story judges will probe).

---

## 8. Requirements

### 8.1 Must-Have — P0 (cannot ship July 6 without these)

**P0-1 — Natural-language intake & orchestration**
The orchestrator accepts a free-text situation and produces a coherent response by coordinating sub-agents.
- Given a free-text health situation, when submitted, then the orchestrator routes to the relevant sub-agents and returns a single synthesized plan.
- Given an ambiguous situation, when confidence is low, then the system asks exactly one clarifying question before planning.
- Given a request for diagnosis/clinical advice, when detected, then the system declines and redirects to its actual scope.

**P0-2 — Genuine multi-agent system (min. 4 working agents)**
Orchestrator + Government Scheme + Facility + Action(Calendar) all functioning and visibly distinct.
- [ ] Each agent has a distinct tool and data source.
- [ ] Agents' individual outputs are inspectable, not merged into an opaque blob.

**P0-3 — Structured data retrieval**
- [ ] Real database (Firestore) holds facility + scheme data with a structured schema.
- [ ] Scheme eligibility stored as structured logic the agent reasons over (not free text).
- [ ] Retrieval returns precise, sourced records.

**P0-4 — Real-world action (Calendar)**
- Given a completed plan, when the user confirms, then visits/reminders are created on a real Google Calendar via MCP.
- [ ] At least one reminder type (appointment or refill) demonstrably created.

**P0-5 — Grounded, ordered output**
- [ ] Output is an ordered action plan (sequenced steps), not an information dump.
- [ ] Every recommendation carries a verifiable source reference.

**P0-6 — Deployed API**
- [ ] FastAPI on Cloud Run, public URL reachable by a judge.
- [ ] `/docs` live. Core flow works end-to-end on the deployed URL (not just locally).

**P0-7 — Family care profiles with consent-based calendar sync**
A caregiver can manage care for a dependent (elderly parent / child) so the plan lands on both people's calendars automatically — because the person needing care often cannot operate the app, and the caregiver should not have to copy the schedule manually. Standard family-sharing pattern (cf. Google Family Link, Apple Family Sharing), implemented with explicit consent.
- Given a caregiver account, when they create a care profile for a dependent, then they can manage that dependent's care plan from their own session.
- Given the dependent (or, for a minor, their guardian) authenticates their own Google account and grants consent, when a plan schedules a visit/reminder, then the event is written to **both** the caregiver's and the dependent's calendars.
- [ ] Two independent OAuth grants (each person authorizes their own account); no single party accesses another's account without that party's consent.
- [ ] For a minor dependent, scheduling is guardian-managed under guardian consent.
- [ ] Consent is explicit and revocable; nothing is linked silently.

### 8.2 Nice-to-Have — P1 (high-priority fast-follows)

- **P1-1 Private Insurance Agent** — Drive(MCP) upload + Gemini doc understanding → coverage + claim path.
- **P1-2 Medicine Agent** — affordable-source lookup + refill-due flag + prepared reorder draft.
- **P1-3 BigQuery layer** — scale/analytics queries powering a "reason over data at scale" story.
- **P1-4 Gmail(MCP) plan delivery** — send the finished plan summary to the user.
- **P1-5 Streaming reasoning** — user watches agents work step-by-step.

### 8.3 Future Considerations — P2 (design for, don't build now)

- **P2-1 Urgent/emergency flow** — reuse agents for "need care now."
- **P2-2 Real pharmacy transaction** — actual order placement when a trustworthy API exists.
- **P2-3 Public-health data grounding** (e.g., DHS MCP) — ground impact claims in real statistics.
- **P2-4 Ride-to-appointment** — transport logistics as a second action surface.
- **P2-5 Multilingual intake** — Indian-language situation input.

---

## 9. Data Sources (all public or user-provided)

| Source | Type | Used by | Notes |
|---|---|---|---|
| Government health-scheme rules (Ayushman Bharat / state) | Public | Scheme Agent | Ingested → Firestore as structured eligibility logic |
| Facility directory (govt hospital lists, with coordinates) | Public | Facility Agent | Stored fallback + Maps for live ranking |
| Jan Aushadhi / generic medicine catalogue | Public | Medicine Agent | Affordable-source lookup |
| User's insurance document | User-provided | Insurance Agent | Via Drive; never stored beyond session unless user opts in |
| Google Maps Platform | API | Facility Agent | Sparing in dev, live in prod |

**Data integrity rule:** No fabricated or synthetic data presented as real. Where a source is thin for the demo region, the system states the limitation rather than inventing records.

---

## 10. Success Metrics

### Leading (demo / prototype-level)
- **Task completion:** core flow (situation → sourced, ordered plan → calendar action) completes end-to-end on the deployed URL. Target: 100% on the demo scenarios.
- **Time-to-plan:** < 60s from submission to full plan.
- **Grounding rate:** % of plan recommendations carrying a verifiable source. Target: 100%.
- **Agent coordination:** ≥ 4 distinct agents demonstrably invoked in a single representative run.

### Lagging (real-world framing for the deck/scale story)
- **Coverage-utilization lift:** entitled-but-unused coverage surfaced per user (the core value).
- **Out-of-pocket reduction:** estimated ₹ saved per plan via correct scheme + affordable medicine sourcing.
- **Adherence:** reduction in missed refills/follow-ups via scheduled reminders.

---

## 11. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| First-time Cloud Run deploy eats build time | High | Budget a dedicated half-day early; deploy a "hello world" container on Day 1 before building features. |
| Maps billing hiccup breaks live demo | Med | Stored facility+coordinates fallback; Maps only on final ranking step. |
| "Fake multi-agent" perception | High | Keep Scheme vs Insurance genuinely distinct (DB-rules vs user-doc); never split one job into many. |
| Symptom-checker drift | High | Hard scope rule + explicit decline-and-redirect behavior (P0-1). |
| Six agents half-built | High | Ship P0 four complete; P1 two as fast-follows; don't attempt all six shallow. |
| Dual-account OAuth + first Cloud Run deploy in one build | High | Family sync is P0 but is the FIRST feature to defer if the deploy clock forces it; deploy Cloud Run Day 1 so it never ambushes the OAuth work later. |
| Data thin for demo region | Med | State limitations honestly; curate a few well-covered demo regions deeply. |
| Judge asks "is this real-time?" | Low | Pre-empt: this is a planning tool; chosen data's cadence matches the decisions it supports. |

---

## 12. Open Questions

- **(Data)** Which government scheme(s) and which 2–3 demo regions give the deepest, cleanest data for the prototype? — *blocking for ingestion.*
- **(Engineering)** ADK orchestration depth achievable in the timeline vs. plain-Gemini fallback if Cloud Run setup overruns? — *resolve by end of Day 2.*
- **(Engineering)** Firestore-only for v1 with BigQuery as P1, or wire BigQuery from the start? — *non-blocking; lean Firestore-first.*
- **(Scope)** Confirm Gmail(MCP) is P1 vs cut — depends on Day 5 progress.
- **(Data)** Verify DHS MCP India granularity before treating as P2 grounding source.

---

## 13. Timeline & Phasing

- **Hard deadline:** July 6, 2026, 11:59 PM IST — deployed Cloud Run URL + GitHub repo + ≤3-min demo video + brief description, all publicly accessible.
- **Phase 1 (July 6 submission):** all P0 + as many P1 as time allows → clear Top 100.
- **Phase 2 (Top-100 Refinement, from July 15):** remaining P1 + selected P2 (urgent flow, real reorder, public-health grounding) → push toward Top 10.

*(Detailed day-by-day build order is a separate document.)*

---

## 14. The Scalability Argument (for the "scale to millions" question)

- **Stateless app tier on Cloud Run** autoscales horizontally; no sticky sessions, any instance serves any request.
- **Managed data services** (Firestore, BigQuery) scale independently of the app tier and absorb read/write growth without sharding work by the team.
- **Agent calls are per-request and parallelizable**; no shared mutable state between requests.
- **Tool integrations are swappable** (MCP / clean tool interface), so adding regions, schemes, or data sources is configuration/data work, not re-architecture.
- **Cost scales with use, not with idle capacity** (serverless), making millions-of-users economically coherent, not just technically possible.

This is why Withcare is presented not as a demo that happens to run, but as a prototype of a system that is architecturally ready to scale.
