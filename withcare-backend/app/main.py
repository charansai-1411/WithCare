import json
import os

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.db.database import init_db
from app.routes.conversations import router as conv_router
from app.routes.auth import router as auth_router
from app.routes.profiles import router as profiles_router
from app.config import settings
from app.models.request_models import ChatRequest
from app.orchestrator.orchestrator import WithCareOrchestrator
from app.orchestrator.agent import WithCareAgent
from app.utils.exceptions import ClinicalRequestError, WithCareError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="WithCare API",
    description=(
        "Healthcare navigation multi-agent system for India. "
        "Finds government schemes, hospitals, and schedules appointments — "
        "powered by Gemini and Google ADK."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Init DB on startup ─────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("SQLite DB initialized")

# ── Include routers ────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(profiles_router)
app.include_router(conv_router)

# ── Handlers: deterministic pipeline (default) or agentic core (USE_AGENT=1) ──────
orchestrator = WithCareOrchestrator()
agent = WithCareAgent()


def get_handler():
    """Pick the request handler by flag so both can run in parallel during migration."""
    return agent if settings.use_agent else orchestrator


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint — used by Cloud Run and load balancers."""
    return {
        "status": "ok",
        "service": "withcare-backend",
        "version": "1.0.0",
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "service": "WithCare API",
        "tagline": "Healthcare, with care.",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "stream": "POST /chat/stream  — SSE streaming (recommended)",
            "sync": "POST /chat          — synchronous (for testing)",
        },
    }


# ── SSE Streaming endpoint ─────────────────────────────────────────────────────
@app.post("/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest, http_request: Request):
    """
    Primary endpoint. Streams care plan chunks as Server-Sent Events.

    Event types:
    - `thinking` — agent is working (show loading state)
    - `step`     — one action step with source URL (append to plan)
    - `clarify`  — one clarifying question needed from user
    - `done`     — full CarePlan object (final state)
    - `error`    — error message

    Example curl:
    ```
    curl -N -X POST http://localhost:8080/chat/stream \\
      -H "Content-Type: application/json" \\
      -d '{"message": "BPL family in Delhi, need cancer hospital", "session_id": "abc123"}'
    ```
    """
    async def event_generator():
        try:
            async for chunk in get_handler().handle(request):
                # Check if client disconnected
                if await http_request.is_disconnected():
                    logger.info(f"Client disconnected mid-stream for session {request.session_id}")
                    break
                yield {
                    "event": chunk.type,
                    "data": json.dumps(chunk.model_dump()),
                }
        except ClinicalRequestError as e:
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "content": str(e), "agent": "orchestrator"}),
            }
        except WithCareError as e:
            logger.error(f"WithCareError in stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "content": str(e), "agent": "orchestrator"}),
            }
        except Exception as e:
            logger.error(f"Unexpected error in stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "content": "An unexpected error occurred. Please try again.", "agent": "orchestrator"}),
            }

    return EventSourceResponse(event_generator())


# ── Sync endpoint (for testing / curl) ────────────────────────────────────────
@app.post("/chat", tags=["Chat"])
async def chat_sync(request: ChatRequest):
    """
    Synchronous endpoint — collects all chunks and returns the final CarePlan.
    Use for testing or when SSE is not available.
    Returns the `done` chunk content (CarePlan) or error details.
    """
    chunks = []
    try:
        async for chunk in get_handler().handle(request):
            chunks.append(chunk.model_dump())
    except Exception as e:
        logger.error(f"Sync chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Return the done chunk if present
    done = next((c for c in chunks if c["type"] == "done"), None)
    if done:
        return done["content"]

    # Return error chunk if present
    error = next((c for c in chunks if c["type"] == "error"), None)
    if error:
        return JSONResponse(status_code=400, content={"error": error["content"]})

    # Return clarify chunk if present
    clarify = next((c for c in chunks if c["type"] == "clarify"), None)
    if clarify:
        return {"clarify": clarify["content"], "chunks": chunks}

    return {"chunks": chunks}


# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(WithCareError)
async def withcare_error_handler(request: Request, exc: WithCareError):
    logger.error(f"WithCareError: {exc}")
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "type": type(exc).__name__},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
