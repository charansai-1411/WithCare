"""
Emergency info + SOS API.
  GET  /api/emergency/summary?profile_id=   the person's emergency sheet
  POST /api/emergency/sos                    { profile_id, location?, coordinates?, connector_tokens }
                                             → emails an urgent alert to family + caregiver
"""
from fastapi import APIRouter, Header, HTTPException

from app.services import emergency_service as emg

router = APIRouter(prefix="/api/emergency", tags=["Emergency"])


@router.get("/summary")
def summary(profile_id: str, x_user_id: str = Header(...)):
    s = emg.emergency_summary(x_user_id, profile_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return s


@router.post("/sos")
async def sos(body: dict, x_user_id: str = Header(...)):
    pid = body.get("profile_id")
    if not pid:
        raise HTTPException(status_code=400, detail="profile_id is required.")
    tokens = {k.lower(): v for k, v in (body.get("connector_tokens") or {}).items()}
    out = await emg.send_sos(x_user_id, pid, body.get("location", ""), body.get("coordinates"), tokens)
    if out is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return out
