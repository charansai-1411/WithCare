# WithCare — Healthcare navigation, with care

WithCare is a multi-agent AI healthcare **navigation** assistant for India. It helps
caregivers find hospitals, discover the government schemes and private insurance a person
qualifies for, and book appointments — for themselves, family members, and pets — through a
natural chat. It **never** gives medical advice; it navigates.

Built on **Google Gemini (Vertex AI)** with Google Calendar, Drive, and Maps integrations.

> ⚠️ WithCare provides navigation assistance only. It is not medical advice.

---

## Highlights

- **Conversational, memory-aware.** A per-person **knowledge graph** remembers conditions,
  past appointments, and coverage explored — so it never re-asks what it already knows and
  stays useful across sessions.
- **Care profiles** for people **and pets** (name, relation/species, age, conditions, Gmail,
  photo), each an openable dashboard of everything the assistant knows about them.
- **Coverage search** returns **government schemes** (Firestore) *and* **private insurance**
  (Gemini + Google Search grounding), then asks eligibility follow-ups.
- **Appointment scheduling** with a hard **confirm-before-booking** guardrail and Google
  Calendar + Drive sync.
- **Google Sign-In** (with a dev/guest fallback) and per-user conversation history.
- **Two interchangeable brains behind a flag:** a deterministic pipeline and a newer **agentic
  core** (LLM function-calling over the memory + a toolbox, with control-flow guardrails).
  Toggle with `USE_AGENT`.
- **Eval/regression suite** (`tests/eval`) that encodes desired behavior as executable
  assertions — the safety net against prompt-by-prompt regressions.

## Architecture (short)

```
Frontend (React/Vite)  ──►  FastAPI  ──►  handler (pipeline | agentic core)
                                              │  reads/writes the Knowledge-Graph memory
                                              └► agents/tools: facilities · coverage · schedule
Google: Vertex Gemini · Maps · Calendar · Drive · Firestore     SQLite: users/profiles/memory
```

- **Deterministic pipeline** (`app/orchestrator/*`): Segmenter → TaskState → Planner →
  Executor(agents) → Writer.
- **Agentic core** (`app/orchestrator/agent.py` + `skills/orchestrator.md`): an LLM
  function-calling loop; guardrails (clinical refusal, DB-persisted confirmation gate, step
  cap, arg validation) enforced in code, behavior in the skill file.

## Repo layout

```
withcare-backend/     FastAPI, agents, tools, knowledge graph, eval suite
withcare-frontend/    React + Vite chat UI
.agents/              architecture & design docs
```

---

## Setup

### Prerequisites
- Python 3.11+, Node 18+
- A Google Cloud project with Vertex AI enabled; `gcloud auth application-default login`
- (Optional) Google Maps API key, a Web OAuth Client ID, and Calendar/Drive OAuth token

### Backend
```bash
cd withcare-backend
python -m venv .venv && . .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in GCP_PROJECT_ID, GOOGLE_MAPS_API_KEY, GOOGLE_OAUTH_CLIENT_ID
python scripts/setup_calendar_auth.py   # optional: generates token.json for Calendar/Drive
uvicorn app.main:app --reload --port 8001
```

### Frontend
```bash
cd withcare-frontend
npm install
cp .env.example .env        # VITE_API_URL=http://localhost:8001
npm run dev                 # http://localhost:5173
```

### Choosing the brain
```bash
# deterministic pipeline (default)
USE_AGENT=0 uvicorn app.main:app --port 8001
# agentic core
USE_AGENT=1 uvicorn app.main:app --port 8001
```

### Running the eval suite
```bash
cd withcare-backend
python -m tests.eval.run_eval            # all cases
python -m tests.eval.run_eval --only <case_id>
```

---

## Security

Secrets are **git-ignored** and must never be committed: `.env`, `token.json`,
`client_secret*.json`, `service-account*.json`, and the SQLite `*.db`. Use the `.env.example`
files as templates.

## Status

Hackathon project (Google Gen AI). The deterministic pipeline is the current default; the
agentic core is being migrated in behind `USE_AGENT`, gated by the eval suite.
