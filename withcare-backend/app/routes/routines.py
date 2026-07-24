"""
Routines API — personal care routines (workout, diet, skincare, check-ups, sleep, …).
  POST /api/routines/list          { profile_id?, connector_tokens }
  POST /api/routines/draft         { profile_id?, category, note? }        → Gemini draft
  POST /api/routines/add           { profile_id, person?, email?, name, category, content,
                                     frequency?, times[]?, recurrence?, remind?, connector_tokens }
  POST /api/routines/{id}/delete   { connector_tokens? }
"""
from fastapi import APIRouter, Header, HTTPException

from app.services import routine_service as rt

router = APIRouter(prefix="/api/routines", tags=["Routines"])


def _tokens(body: dict) -> dict:
    t = body.get("connector_tokens") or {}
    return {k.lower(): v for k, v in t.items()}


@router.post("/list")
async def list_routines(body: dict, x_user_id: str = Header(...)):
    return rt.list_routines(x_user_id, body.get("profile_id") or None)


@router.post("/draft")
async def draft(body: dict, x_user_id: str = Header(...)):
    return await rt.draft_routine(
        x_user_id, body.get("profile_id") or None,
        (body.get("category") or "other"), (body.get("note") or "").strip(),
    )


@router.post("/add")
async def add(body: dict, x_user_id: str = Header(...)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Routine name is required.")
    return await rt.add_routine(
        x_user_id, body.get("profile_id") or None,
        (body.get("person") or "").strip(), (body.get("email") or "").strip(),
        name, (body.get("category") or "other"), (body.get("content") or "").strip(),
        (body.get("frequency") or "").strip(), body.get("times") or [],
        (body.get("recurrence") or "daily"), bool(body.get("remind")), _tokens(body),
    )


@router.post("/{routine_id}/delete")
async def delete(routine_id: str, body: dict, x_user_id: str = Header(...)):
    ok = await rt.delete_routine(x_user_id, routine_id, _tokens(body))
    if not ok:
        raise HTTPException(status_code=404, detail="Routine not found.")
    return {"ok": True}
