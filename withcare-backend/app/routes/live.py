"""
Gemini Live — a WebSocket that bridges the browser to the Gemini Live API (native audio) on
Vertex AI, so the user can have a real spoken conversation with WithCare.

  ws://<backend>/ws/live
    browser -> server : binary frames = 16 kHz mono PCM16 mic audio; text {"type":"end"}
    server  -> browser: binary frames = 24 kHz mono PCM16 reply audio;
                        text events {"type": "ready"|"text"|"interrupted"|"turn_complete"|"error"}

The server holds the Vertex credentials; the browser never sees them.
"""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from app.config import settings
from app.services.skills import load_skill
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Live"])

# The Live model is served from a different Vertex location (default "global") than the
# text model, so it needs its own client.
_live_client: genai.Client | None = None


def get_live_client() -> genai.Client:
    global _live_client
    if _live_client is None:
        _live_client = genai.Client(
            vertexai=True, project=settings.gcp_project_id, location=settings.gemini_live_location,
        )
        logger.info(f"Live client initialized (location={settings.gemini_live_location}, model={settings.gemini_live_model})")
    return _live_client


def _system_prompt() -> str:
    base = load_skill("orchestrator") or "You are WithCare, a warm healthcare-navigation assistant for India."
    return (
        base
        + "\n\n== YOU ARE IN A LIVE VOICE CONVERSATION =="
        "\n- Speak warmly and CONVERSATIONALLY, in 1-2 short sentences at a time."
        "\n- You cannot show cards or links here, so summarise verbally and offer to open the app for details."
        "\n- Never diagnose, prescribe, or interpret results - gently guide to a professional and help navigate care."
        "\n- LANGUAGE: Reply in English by default. Only switch to another language if the person clearly speaks a"
        " full sentence in that language; do NOT switch based on a single word like a greeting. Match the person's"
        " language once they have clearly established it."
    )


@router.websocket("/ws/live")
async def live_ws(ws: WebSocket):
    await ws.accept()
    client = get_live_client()
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=_system_prompt())]),
    )

    try:
        async with client.aio.live.connect(model=settings.gemini_live_model, config=config) as session:
            await ws.send_text(json.dumps({"type": "ready"}))
            logger.info("Live session connected")

            async def browser_to_gemini():
                while True:
                    msg = await ws.receive()
                    if msg.get("type") == "websocket.disconnect":
                        raise WebSocketDisconnect()
                    data = msg.get("bytes")
                    if data:
                        await session.send_realtime_input(
                            audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                        )
                    elif msg.get("text"):
                        try:
                            evt = json.loads(msg["text"])
                        except Exception:
                            evt = {}
                        if evt.get("type") == "end":
                            raise WebSocketDisconnect()

            async def gemini_to_browser():
                # session.receive() yields the messages for ONE turn and then ends, so it must be
                # re-entered for each subsequent turn. Without this loop, the assistant replies once
                # and then goes silent forever.
                while True:
                    got_turn = False
                    async for response in session.receive():
                        got_turn = True
                        if response.data:
                            await ws.send_bytes(response.data)  # 24 kHz PCM reply audio
                        if getattr(response, "text", None):
                            await ws.send_text(json.dumps({"type": "text", "text": response.text}))
                        sc = getattr(response, "server_content", None)
                        if sc and getattr(sc, "interrupted", None):
                            await ws.send_text(json.dumps({"type": "interrupted"}))
                        if sc and getattr(sc, "turn_complete", None):
                            await ws.send_text(json.dumps({"type": "turn_complete"}))
                    # If the stream yields nothing (session closing), stop rather than busy-loop.
                    if not got_turn:
                        break

            await asyncio.gather(browser_to_gemini(), gemini_to_browser())

    except WebSocketDisconnect:
        logger.info("Live session: client disconnected")
    except Exception as e:
        logger.error(f"Live session failed: {e}")
        try:
            await ws.send_text(json.dumps({"type": "error", "message": f"Live voice is unavailable: {e}"}))
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
