"""
Doctor-visit API — save a recorded consultation as a structured, searchable Reader record.
  POST /api/visits/save   { profile_id?, patient_name?, hospital?, doctor?, transcript, date? }
                          -> { doc_id, label, visit: {summary, medications[], diet[], ...} }

The transcript comes from the /ws/scribe listen-only Gemini Live session. Extraction runs one
Gemini call; nothing is auto-prescribed — the returned meds/routines are surfaced as one-tap
suggestions in the UI.
"""
from fastapi import APIRouter, Header, HTTPException

from app.services import visit_service

router = APIRouter(prefix="/api/visits", tags=["Visits"])


@router.post("/save")
async def save_visit(body: dict, x_user_id: str = Header(...)):
    transcript = (body.get("transcript") or "").strip()
    if len(transcript) < 15:
        raise HTTPException(status_code=400,
                            detail="The recording was too short to capture anything. Try again.")
    return await visit_service.save_visit(
        x_user_id,
        patient_name=(body.get("patient_name") or "").strip(),
        hospital=(body.get("hospital") or "").strip(),
        doctor=(body.get("doctor") or "").strip(),
        transcript=transcript,
        when=(body.get("date") or "").strip() or None,
    )
