"""
Voice input — speech-to-text so users can talk instead of type.
  POST /api/voice/transcribe   multipart (file=audio, language=hint) → { "text": "..." }

Uses Gemini (multimodal) on Vertex AI, so no separate Speech-to-Text API is required.
"""
from fastapi import APIRouter, File, UploadFile, Form, Header, HTTPException

from app.services.gemini_service import transcribe_audio
from app.utils.exceptions import GeminiServiceError
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/voice", tags=["Voice"])
logger = get_logger(__name__)

# Browsers record webm/opus (Chrome) or ogg/mp4 depending on platform — accept the common ones.
_ALLOWED = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mp4",
            "audio/mpeg", "audio/mp3", "audio/aac", "audio/flac", "audio/m4a", "audio/x-m4a"}
_MAX_BYTES = 10 * 1024 * 1024  # ~10 MB — several minutes of opus


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(""),
    x_user_id: str = Header(default=""),
):
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime and mime not in _ALLOWED:
        logger.info(f"transcribe: unusual audio mime {mime!r} — attempting anyway")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="No audio received.")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Recording too long (max ~10 MB).")
    try:
        text = await transcribe_audio(data, mime or "audio/webm", language)
    except GeminiServiceError:
        raise HTTPException(status_code=502, detail="Couldn't transcribe the audio — please try again.")
    return {"text": text}
