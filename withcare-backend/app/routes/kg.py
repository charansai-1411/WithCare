"""
Read-only knowledge-graph endpoints for the frontend feature views (Tasks & Plans).
No LLM calls — just reads the kg_nodes the agents wrote.
"""
import json

from fastapi import APIRouter, Header

from app.db.database import get_db

router = APIRouter(prefix="/api/kg", tags=["Knowledge"])

_KINDS = {
    "tasks": ("appointment", "task", "reminder"),
    "plans": ("workout_plan", "diet_plan"),
}


@router.get("/items")
def items(kind: str, x_user_id: str = Header(...)):
    """kind = 'tasks' (appointments/reminders) or 'plans' (workout/diet), across the user's profiles."""
    types = _KINDS.get(kind)
    if not types:
        return []
    db = get_db()
    placeholders = ",".join("?" * len(types))
    rows = db.execute(
        f"""SELECT n.id, n.type, n.name, n.data, n.updated_at,
                   p.name AS profile_name, p.kind AS profile_kind
            FROM kg_nodes n LEFT JOIN profiles p ON n.profile_id = p.id
            WHERE n.user_id = ? AND n.type IN ({placeholders})
            ORDER BY n.updated_at DESC""",
        (x_user_id, *types),
    ).fetchall()
    db.close()

    out = []
    for r in rows:
        d = dict(r)
        try:
            d["data"] = json.loads(d.get("data") or "{}")
        except Exception:
            d["data"] = {}
        out.append(d)
    return out
