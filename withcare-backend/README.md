# WithCare — Backend

The API and multi-agent core for **WithCare**. A **FastAPI** service where **Gemini** decides
*what* to do (function calling) and typed tools with **code-level guardrails** decide *whether
and how* it actually happens — so a healthcare assistant stays safe and grounded.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then fill in GCP_PROJECT_ID, GOOGLE_MAPS_API_KEY, etc.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Health check: `GET /health` · API docs: `/docs` · main endpoint: `POST /chat/stream` (SSE).

## Layout

| Path | What's there |
|------|--------------|
| `app/main.py` | FastAPI app, routes, SSE streaming |
| `app/orchestrator/` | `agent.py` (the Gemini function-calling loop + guardrails), `router.py` (clinical/ambiguity gate) |
| `app/agents/` | Specialist agents — facility, coverage, reminder, action, workout, diet, product |
| `app/services/` | Gemini, knowledge-graph memory, RAG reader, embeddings, skills loader |
| `app/tools/` | Maps, Calendar, Gmail, Drive, Firestore integrations |
| `skills/` | Markdown playbooks loaded per agent (orchestrator, workout, diet, reader, coverage) |
| `app/db/` | SQLite schema — profiles, conversations, knowledge graph, documents |

## How it stays safe
- **Clinical gate** — refuses diagnosis/treatment questions before the loop runs.
- **Confirm-before-book** — irreversible actions are staged in the DB and only run on an explicit "yes".
- **Grounded** — facilities (Maps + Firestore), coverage & prices (Google Search), documents (the
  user's own files) — never model memory.
- **Per-user tokens** — in production, Calendar/Gmail/Drive act on the *user's* Google account.

Gemini runs via **Vertex AI**; data lives in **Firestore** + local **SQLite**. See the
[root README](../README.md) for the full architecture.
