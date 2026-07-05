"""
Read-only knowledge-graph endpoints for the frontend feature views (Tasks & Plans).
No LLM calls — just reads the kg_nodes the agents wrote.
"""
import json

from fastapi import APIRouter, Header, HTTPException

from app.db.database import get_db
from app.services.memory_service import get_node, delete_node
from app.tools.calendar_tool import delete_calendar_event

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


@router.delete("/items/{node_id}")
async def delete_kg_item(node_id: str, x_user_id: str = Header(...)):
    """Delete any KG item (reminder, appointment, plan, memory fact…). If it's a reminder or
    appointment with an attached calendar event, remove that event too so the calendar stays
    in sync."""
    node = get_node(node_id, x_user_id)
    if not node:
        raise HTTPException(status_code=404, detail="Item not found")
    data = node.get("data") or {}
    if node["type"] in ("reminder", "appointment") and data.get("event_id"):
        await delete_calendar_event(data.get("calendar_id") or "primary", data["event_id"])
    delete_node(x_user_id, node_id)
    return {"ok": True, "type": node["type"]}
