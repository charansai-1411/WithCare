"""
Medication management API.
  POST /api/medications/list          { profile_id?, connector_tokens } → list + fire refill alerts
  POST /api/medications/add           { profile_id, person, email?, name, dose, times[],
                                        per_dose, quantity, refill_threshold_days, connector_tokens }
  POST /api/medications/{id}/refill   { quantity, connector_tokens? }
  POST /api/medications/{id}/delete   { connector_tokens? }
"""
from fastapi import APIRouter, Header, HTTPException

from app.services import medication_service as med

router = APIRouter(prefix="/api/medications", tags=["Medications"])


def _tokens(body: dict) -> dict:
    t = body.get("connector_tokens") or {}
    return {k.lower(): v for k, v in t.items()}


@router.post("/list")
async def list_meds(body: dict, x_user_id: str = Header(...)):
    return await med.list_medications(x_user_id, body.get("profile_id") or None, _tokens(body))


@router.post("/add")
async def add_med(body: dict, x_user_id: str = Header(...)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Medicine name is required.")
    try:
        qty = int(float(body.get("quantity") or 0))
        per_dose = int(float(body.get("per_dose") or 1))
        thresh = int(float(body.get("refill_threshold_days") or 5))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Quantity, per-dose and threshold must be numbers.")
    return await med.add_medication(
        x_user_id, body.get("profile_id") or None, (body.get("person") or "").strip(),
        (body.get("email") or "").strip(), name, (body.get("dose") or "").strip(),
        body.get("times") or [], per_dose, qty, thresh, _tokens(body),
    )


@router.post("/{med_id}/refill")
async def refill_med(med_id: str, body: dict, x_user_id: str = Header(...)):
    try:
        qty = int(float(body.get("quantity"))) if body.get("quantity") is not None else None
    except (TypeError, ValueError):
        qty = None
    out = await med.refill_medication(x_user_id, med_id, qty, _tokens(body))
    if out is None:
        raise HTTPException(status_code=404, detail="Medicine not found.")
    return out


@router.post("/{med_id}/delete")
async def delete_med(med_id: str, body: dict, x_user_id: str = Header(...)):
    ok = await med.delete_medication(x_user_id, med_id, _tokens(body))
    if not ok:
        raise HTTPException(status_code=404, detail="Medicine not found.")
    return {"ok": True}
