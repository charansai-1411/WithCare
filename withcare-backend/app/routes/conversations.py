import json
import uuid

from fastapi import APIRouter, Header, HTTPException
from typing import Optional

from app.db.database import get_db

router = APIRouter(prefix="/api", tags=["Conversations"])


def _ensure_user(db, user_id: str):
    db.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (user_id,))
    db.commit()


# ── List conversations ──────────────────────────────────────────────────────────
@router.get("/conversations")
def list_conversations(x_user_id: str = Header(...)):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC",
        (x_user_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ── Create conversation ─────────────────────────────────────────────────────────
@router.post("/conversations")
def create_conversation(body: dict, x_user_id: str = Header(...)):
    db = get_db()
    _ensure_user(db, x_user_id)
    conv_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO conversations(id, user_id, title, profile_name) VALUES(?,?,?,?)",
        (
            conv_id,
            x_user_id,
            body.get("title", "New conversation"),
            body.get("profile_name", "You"),
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
    db.close()
    return dict(row)


# ── Get messages for a conversation ────────────────────────────────────────────
@router.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: str, x_user_id: str = Header(...)):
    db = get_db()
    # Verify conversation belongs to user
    conv = db.execute(
        "SELECT id FROM conversations WHERE id=? AND user_id=?", (conv_id, x_user_id)
    ).fetchone()
    if not conv:
        db.close()
        raise HTTPException(status_code=404, detail="Conversation not found")

    # rowid tiebreak = true insertion order. created_at is only 1-second precision, so
    # messages saved in the same second (user + reply) would otherwise reorder on reload.
    rows = db.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC, rowid ASC",
        (conv_id,),
    ).fetchall()
    db.close()

    msgs = []
    for r in rows:
        m = dict(r)
        if m.get("care_plan"):
            try:
                m["care_plan"] = json.loads(m["care_plan"])
            except Exception:
                m["care_plan"] = None
        msgs.append(m)
    return msgs


# ── Save a message ──────────────────────────────────────────────────────────────
@router.post("/conversations/{conv_id}/messages")
def save_message(conv_id: str, body: dict, x_user_id: str = Header(...)):
    db = get_db()
    _ensure_user(db, x_user_id)

    # Auto-create conversation if it doesn't exist yet
    existing = db.execute("SELECT id FROM conversations WHERE id=?", (conv_id,)).fetchone()
    if not existing:
        db.execute(
            "INSERT OR IGNORE INTO conversations(id, user_id, title, profile_name) VALUES(?,?,?,?)",
            (conv_id, x_user_id, body.get("title", "New conversation"), body.get("profile_name", "You")),
        )

    msg_id = str(uuid.uuid4())
    care_plan_json = json.dumps(body["care_plan"]) if body.get("care_plan") else None

    db.execute(
        "INSERT INTO messages(id, conversation_id, role, content, care_plan) VALUES(?,?,?,?,?)",
        (msg_id, conv_id, body["role"], body["content"], care_plan_json),
    )

    # Update conversation's title (from first user message) and updated_at
    if body.get("role") == "user":
        first_title = body["content"][:70]
        db.execute(
            """UPDATE conversations
               SET updated_at = datetime('now'),
                   title = CASE WHEN title = 'New conversation' THEN ? ELSE title END
               WHERE id = ?""",
            (first_title, conv_id),
        )
    else:
        db.execute(
            "UPDATE conversations SET updated_at=datetime('now') WHERE id=?",
            (conv_id,),
        )

    db.commit()
    db.close()
    return {"id": msg_id, "ok": True}


# ── Delete conversation ─────────────────────────────────────────────────────────
@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str, x_user_id: str = Header(...)):
    db = get_db()
    db.execute("DELETE FROM messages WHERE conversation_id=?", (conv_id,))
    db.execute(
        "DELETE FROM conversations WHERE id=? AND user_id=?", (conv_id, x_user_id)
    )
    db.commit()
    db.close()
    return {"ok": True}


# ── Update conversation title ───────────────────────────────────────────────────
@router.patch("/conversations/{conv_id}")
def update_conversation(conv_id: str, body: dict, x_user_id: str = Header(...)):
    db = get_db()
    if "title" in body:
        db.execute(
            "UPDATE conversations SET title=? WHERE id=? AND user_id=?",
            (body["title"], conv_id, x_user_id),
        )
    db.commit()
    db.close()
    return {"ok": True}
