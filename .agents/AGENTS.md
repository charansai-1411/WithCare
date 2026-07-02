# WithCare — Project Rules

## Identity
- WithCare is a **decision-intelligence and care-navigation platform**, NOT a diagnostic tool or symptom checker.
- It operates strictly on **access, eligibility, affordability, logistics, and scheduling**. Never generate clinical advice.
- Hackathon: Google Gen AI 2.0 Cohort 2 — Problem Statement 1 (Decision Intelligence Platform)
- Hard deadline: **July 6, 2026, 11:59 PM IST**

## Hard Boundaries
1. **Never provide diagnosis, treatment advice, or clinical recommendations.** Decline and redirect.
2. **Never fabricate data.** If a source is thin, state the limitation honestly.
3. **Every recommendation must carry a verifiable source reference.** Zero unsourced health guidance.
4. **No fake transactions.** Prepare + remind for reorders, never transact.
5. **All Google stack.** Reasoning = Gemini, Agents = ADK, Action = Calendar MCP, Deploy = Cloud Run, Data = Firestore + BigQuery, Location = Maps.

## Architecture Principles
- **Stateless app tier** — no server-side session state; all state in managed data services.
- **Honest multi-agent** — each sub-agent has a genuinely distinct job, tool, and data source.
- **Grounded output** — every agent returns sourced records; the orchestrator never fabricates.
- **Horizontally scalable** — any Cloud Run instance can serve any request.

## Code Style
- Backend: Python 3.11+, FastAPI, async/await throughout.
- Frontend: React (Vite), Vanilla CSS (no Tailwind unless explicitly requested).
- Use type hints in Python. Use Pydantic for all request/response models.
- Keep files focused and single-responsibility. Avoid god-files.

## Priorities
- **P0 first.** Ship 4 working agents (Orchestrator + Scheme + Facility + Action/Calendar) before touching P1.
- **Deploy early.** Cloud Run "hello world" container on Day 1.
- **Demo-proof.** Every feature must work end-to-end on the deployed URL, not just locally.
