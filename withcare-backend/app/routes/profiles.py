"""
Care profiles CRUD. Each profile belongs to a user (x-user-id header).
Fields: name, relation, age, gender, conditions, notes, photo (base64 data URL).
"""
import uuid

from fastapi import APIRouter, Header, HTTPException

from app.db.database import get_db
from app.services.memory_service import sync_profile_to_kg, get_profile_graph

router = APIRouter(prefix="/api/profiles", tags=["Profiles"])

_FIELDS = ("name", "kind", "relation", "species", "email", "age", "gender", "weight", "height", "conditions", "notes", "photo", "is_self", "blood_group", "allergies")


def _ensure_user(db, user_id: str):
    db.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (user_id,))


def _seed_self_profile(db, user_id: str):
    """Every user gets a default 'You' profile the first time they load profiles."""
    existing = db.execute(
        "SELECT COUNT(*) AS n FROM profiles WHERE user_id=?", (user_id,)
    ).fetchone()
    if existing["n"] == 0:
        row = db.execute("SELECT name FROM users WHERE id=?", (user_id,)).fetchone()
        name = (row["name"] if row and row["name"] else "You") or "You"
        db.execute(
            "INSERT INTO profiles(id, user_id, name, relation, is_self) VALUES(?,?,?,?,1)",
            ("p-" + uuid.uuid4().hex[:12], user_id, name, "Your own care"),
        )
        db.commit()


@router.get("")
def list_profiles(x_user_id: str = Header(...)):
    db = get_db()
    _ensure_user(db, x_user_id)
    _seed_self_profile(db, x_user_id)
    rows = db.execute(
        "SELECT * FROM profiles WHERE user_id=? ORDER BY is_self DESC, created_at ASC",
        (x_user_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("")
def create_profile(body: dict, x_user_id: str = Header(...)):
    if not (body.get("name") or "").strip():
        raise HTTPException(status_code=400, detail="Name is required")
    db = get_db()
    _ensure_user(db, x_user_id)
    pid = "p-" + uuid.uuid4().hex[:12]
    db.execute(
        """INSERT INTO profiles(id, user_id, name, kind, relation, species, email, age, gender, weight, height, conditions, notes, photo, blood_group, allergies)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            pid, x_user_id,
            body["name"].strip(),
            body.get("kind", "person"),
            body.get("relation", ""),
            body.get("species", ""),
            body.get("email", ""),
            body.get("age"),
            body.get("gender", ""),
            body.get("weight"),
            body.get("height"),
            body.get("conditions", ""),
            body.get("notes", ""),
            body.get("photo", ""),
            body.get("blood_group", ""),
            body.get("allergies", ""),
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
    db.close()
    prof = dict(row)
    sync_profile_to_kg(x_user_id, prof)   # auto-update memory with any conditions
    return prof


@router.patch("/{profile_id}")
def update_profile(profile_id: str, body: dict, x_user_id: str = Header(...)):
    db = get_db()
    owned = db.execute(
        "SELECT id FROM profiles WHERE id=? AND user_id=?", (profile_id, x_user_id)
    ).fetchone()
    if not owned:
        db.close()
        raise HTTPException(status_code=404, detail="Profile not found")

    updates = {k: body[k] for k in _FIELDS if k in body}
    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        db.execute(
            f"UPDATE profiles SET {sets}, updated_at=datetime('now') WHERE id=?",
            (*updates.values(), profile_id),
        )
        db.commit()
    row = db.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
    db.close()
    prof = dict(row)
    sync_profile_to_kg(x_user_id, prof)   # auto-update memory on edit
    return prof


@router.get("/{profile_id}/graph")
def profile_graph(profile_id: str, x_user_id: str = Header(...)):
    """Aggregate everything the knowledge graph knows about this person — for the detail view."""
    db = get_db()
    owned = db.execute(
        "SELECT id FROM profiles WHERE id=? AND user_id=?", (profile_id, x_user_id)
    ).fetchone()
    db.close()
    if not owned:
        raise HTTPException(status_code=404, detail="Profile not found")
    return get_profile_graph(profile_id)


@router.delete("/{profile_id}")
def delete_profile(profile_id: str, x_user_id: str = Header(...)):
    db = get_db()
    prof = db.execute(
        "SELECT is_self FROM profiles WHERE id=? AND user_id=?", (profile_id, x_user_id)
    ).fetchone()
    if not prof:
        db.close()
        raise HTTPException(status_code=404, detail="Profile not found")
    if prof["is_self"]:
        db.close()
        raise HTTPException(status_code=400, detail="Can't delete your own profile")
    db.execute("DELETE FROM profiles WHERE id=? AND user_id=?", (profile_id, x_user_id))
    db.commit()
    db.close()
    return {"ok": True}
