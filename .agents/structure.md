# WithCare — Project Structure Map

Quick reference for where everything lives in the codebase.

## Root
```
WithCare/
├── .agents/                          # 🧠 PROJECT BRAIN — rules, architecture, context
│   ├── AGENTS.md                     # Project-wide rules and constraints
│   ├── Withcare_PRD.md               # Full Product Requirements Document
│   ├── architecture.md               # Architecture reference (agents, tools, deployment)
│   ├── requirements_checklist.md     # P0/P1/P2 requirements tracker
│   ├── structure.md                  # THIS FILE — project structure map
│   ├── decisions.md                  # Design decisions log
│   └── progress.md                   # Daily progress and status tracking
│
├── withcare-backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py                   # FastAPI entry point
│   │   ├── config.py                 # Settings: API keys, project IDs, env vars
│   │   ├── orchestrator/
│   │   │   ├── orchestrator.py       # Primary agent — routing, synthesis
│   │   │   └── router.py            # Routing logic: which sub-agents fire
│   │   ├── agents/
│   │   │   ├── base_agent.py         # Shared base class
│   │   │   ├── scheme_agent.py       # Government Scheme Agent (P0)
│   │   │   ├── insurance_agent.py    # Private Insurance Agent (P1)
│   │   │   ├── facility_agent.py     # Facility Agent — Maps (P0)
│   │   │   ├── medicine_agent.py     # Medicine Agent (P1)
│   │   │   └── action_agent.py       # Action Agent — Calendar (P0)
│   │   ├── tools/
│   │   │   ├── firestore_tool.py     # Database reads/writes
│   │   │   ├── bigquery_tool.py      # Scale/analytics queries (P1)
│   │   │   ├── maps_tool.py          # Google Maps facility lookup
│   │   │   ├── calendar_tool.py      # Google Calendar MCP
│   │   │   ├── drive_tool.py         # Google Drive MCP (P1)
│   │   │   └── gmail_tool.py         # Gmail MCP (P1)
│   │   ├── models/
│   │   │   ├── request_models.py     # API request schemas
│   │   │   ├── response_models.py    # API response schemas + agent_trace
│   │   │   └── care_plan.py          # Structured care plan object
│   │   ├── data/
│   │   │   ├── schemes/              # Ingested government scheme rules
│   │   │   ├── facilities/           # Facility directory + coordinates
│   │   │   └── medicines/            # Jan Aushadhi medicine data
│   │   ├── services/
│   │   │   ├── gemini_service.py     # All Gemini LLM calls
│   │   │   ├── auth_service.py       # OAuth — dual-account consent
│   │   │   └── grounding.py          # Source citation attachment
│   │   └── utils/
│   │       ├── logger.py             # Logging
│   │       └── exceptions.py         # Error handling
│   ├── scripts/
│   │   ├── ingest_schemes.py         # One-time: load scheme data
│   │   ├── ingest_facilities.py      # One-time: load facility data
│   │   └── ingest_medicines.py       # One-time: load medicine data
│   ├── tests/
│   │   └── test_orchestrator.py      # Smoke tests
│   ├── Dockerfile                    # Cloud Run container
│   ├── requirements.txt
│   ├── .env.example
│   ├── .gitignore
│   ├── .dockerignore
│   ├── cloudbuild.yaml
│   └── README.md
│
├── withcare-frontend/                # React (Vite) frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatThread.jsx        # Message thread
│   │   │   ├── AgentFlowAnimation.jsx # Agent trace visualization
│   │   │   ├── CarePlanCard.jsx      # Inline care plan card
│   │   │   ├── Sidebar.jsx           # History, profiles, connectors
│   │   │   ├── ProfileSwitcher.jsx   # Family profile switcher
│   │   │   └── ConnectorsPanel.jsx   # MCP connector status
│   │   ├── services/
│   │   │   └── api.js                # Backend API client
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   └── README.md
│
└── README.md                         # Root project description
```

## Key Conventions
- **P0 agents**: Orchestrator, Scheme, Facility, Action — these get built first
- **P1 agents**: Insurance, Medicine — built after P0 is solid
- **Data directory**: Contains pre-ingested structured data as fallback
- **`.agents/`**: The project brain — check here before making architectural decisions
