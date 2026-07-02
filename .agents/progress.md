# WithCare — Progress Tracker

## Timeline
- **Hard deadline:** July 6, 2026, 11:59 PM IST
- **Deliverables:** Deployed Cloud Run URL + GitHub repo + ≤3-min demo video + brief description

---

## Day 0 — June 30, 2026

### Completed
- [x] Project structure created (backend + frontend directories and empty files)
- [x] PRD reviewed and distilled into `.agents/` brain documents
- [x] `.agents/` brain initialized:
  - `AGENTS.md` — project rules and constraints
  - `architecture.md` — agent roster, tool map, deployment topology
  - `requirements_checklist.md` — P0/P1/P2 tracker
  - `structure.md` — project structure map
  - `decisions.md` — design decisions log
  - `progress.md` — this file

### Next Steps
- [ ] Deploy "hello world" FastAPI container to Cloud Run (risk mitigation — PRD says Day 1)
- [ ] Set up Firestore project and schema
- [ ] Begin P0 agent implementation (Orchestrator → Scheme Agent → Facility Agent → Action Agent)
- [ ] Set up Google ADK for agent orchestration

---

## Upcoming Milestones

### By End of Day 2 (July 2)
- [ ] Cloud Run deployed with working FastAPI
- [ ] Firestore schema designed and populated with demo scheme + facility data
- [ ] Orchestrator routing working
- [ ] At least 1 sub-agent (Scheme) returning real results

### By End of Day 4 (July 4)
- [ ] All P0 agents working (Scheme + Facility + Action/Calendar)
- [ ] Calendar MCP integration live
- [ ] Dual OAuth flow implemented
- [ ] Frontend chat UI connected to backend

### By End of Day 5 (July 5)
- [ ] P1 agents if time permits (Insurance, Medicine)
- [ ] Agent flow animation working in frontend
- [ ] End-to-end flow on deployed URL
- [ ] Begin demo video recording

### July 6 — Submission Day
- [ ] Final testing on deployed URL
- [ ] Demo video (≤3 min) recorded and uploaded
- [ ] GitHub repo cleaned and README finalized
- [ ] Submit: Cloud Run URL + GitHub + Video + Description

---

## Blockers & Risks

| Risk | Status | Mitigation |
|------|--------|------------|
| Cloud Run first deploy | 🟡 Not started | Budget half-day early; deploy hello-world first |
| Maps billing hiccup | 🟢 Mitigated | Facility fallback data in place |
| ADK vs plain Gemini | 🟡 To evaluate | Resolve by end of Day 2 |
| Data thin for demo region | 🟡 To evaluate | Pick 2-3 well-covered demo regions |

---

*Update this file daily during the build sprint.*
