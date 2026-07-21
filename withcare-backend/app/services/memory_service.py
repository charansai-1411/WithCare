"""
Knowledge-graph memory service.

The shared, persistent per-person memory that every feature reads and writes.
- write_fact(...)         : agents/profile edits record facts as nodes (+ an edge to the person)
- get_profile_memory(...) : compact rendered slice injected into the LLMs (token-cheap)
- get_profile_graph(...)  : structured aggregate for the Profile detail view
- sync_profile_to_kg(...) : keep the graph in step with profile edits (auto memory)
- resolve_recipient(...)  : map "mother"/"Bruno"/a name -> the right profile (for reminders)

Storage is the existing SQLite (kg_nodes / kg_edges / kg_summaries) — a graph *model* that
can migrate to a real graph DB later without changing callers.
"""
import json
import uuid

from app.db.database import get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Writes ───────────────────────────────────────────────────────────────────────
def write_fact(
    user_id: str,
    profile_id: str | None,
    node_type: str,
    name: str,
    data: dict | None = None,
    predicate: str = "for_member",
    unique: str = "name",   # "name" -> dedupe by (profile,type,name); "type" -> one per type;
                            # "never" -> always insert a new node (for time-series like vitals)
) -> str:
    """Upsert a KG node and link it to the person. Returns the node id."""
    if not name:
        return ""
    db = get_db()
    payload = json.dumps(data or {}, ensure_ascii=False)

    if unique == "never":
        row = None
    elif unique == "type":
        row = db.execute(
            "SELECT id FROM kg_nodes WHERE profile_id IS ? AND type=?",
            (profile_id, node_type),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT id FROM kg_nodes WHERE profile_id IS ? AND type=? AND name=?",
            (profile_id, node_type, name),
        ).fetchone()

    if row:
        node_id = row["id"]
        db.execute(
            "UPDATE kg_nodes SET name=?, data=?, updated_at=datetime('now') WHERE id=?",
            (name, payload, node_id),
        )
    else:
        node_id = "n-" + uuid.uuid4().hex[:12]
        db.execute(
            "INSERT INTO kg_nodes(id, user_id, profile_id, type, name, data) VALUES(?,?,?,?,?,?)",
            (node_id, user_id, profile_id, node_type, name, payload),
        )
        if profile_id:
            db.execute(
                "INSERT INTO kg_edges(id, user_id, src, predicate, dst) VALUES(?,?,?,?,?)",
                ("e-" + uuid.uuid4().hex[:12], user_id, profile_id, predicate, node_id),
            )
    db.commit()
    db.close()
    return node_id


def get_node(node_id: str, user_id: str) -> dict | None:
    """Fetch a single KG node owned by the user, with `data` parsed. None if not found."""
    if not node_id:
        return None
    db = get_db()
    row = db.execute(
        "SELECT * FROM kg_nodes WHERE id=? AND user_id=?", (node_id, user_id)
    ).fetchone()
    db.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["data"] = json.loads(d.get("data") or "{}")
    except Exception:
        d["data"] = {}
    return d


def delete_node(user_id: str, node_id: str) -> dict | None:
    """Delete a KG node (scoped to the user) and any edges touching it. Returns the deleted
    node (so callers can clean up an attached calendar event), or None if it wasn't found."""
    node = get_node(node_id, user_id)
    if not node:
        return None
    db = get_db()
    db.execute("DELETE FROM kg_edges WHERE user_id=? AND (src=? OR dst=?)", (user_id, node_id, node_id))
    db.execute("DELETE FROM kg_nodes WHERE id=? AND user_id=?", (node_id, user_id))
    db.commit()
    db.close()
    return node


def find_nodes(
    user_id: str,
    node_type: str,
    profile_id: str | None = None,
    name_contains: str | None = None,
) -> list[dict]:
    """Find KG nodes of a type for a user (optionally a profile), newest first. If
    `name_contains` is given, prefer nodes whose name matches it (case-insensitive)."""
    db = get_db()
    sql = "SELECT * FROM kg_nodes WHERE user_id=? AND type=?"
    params: list = [user_id, node_type]
    if profile_id:
        sql += " AND profile_id IS ?"
        params.append(profile_id)
    sql += " ORDER BY updated_at DESC"
    rows = db.execute(sql, params).fetchall()
    db.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["data"] = json.loads(d.get("data") or "{}")
        except Exception:
            d["data"] = {}
        out.append(d)
    if name_contains:
        needle = name_contains.strip().lower()
        matched = [n for n in out if needle in (n.get("name") or "").lower()]
        if matched:
            return matched
    return out


def sync_profile_to_kg(user_id: str, profile: dict) -> None:
    """On profile create/edit, turn each listed condition into a condition node so the graph
    reflects the edit automatically."""
    pid = profile.get("id")
    conditions = (profile.get("conditions") or "").strip()
    if not pid or not conditions:
        return
    for cond in [c.strip() for c in conditions.replace(";", ",").split(",") if c.strip()]:
        write_fact(user_id, pid, "condition", cond, predicate="has_condition")


# ── Reads ────────────────────────────────────────────────────────────────────────
_TYPE_LABEL = {
    "condition": "Conditions",
    "medication": "Medications",
    "appointment": "Appointments",
    "hospital": "Hospitals",
    "scheme": "Govt schemes",
    "insurance": "Insurance",
    "workout_plan": "Workout plan",
    "diet_plan": "Diet plan",
    "reminder": "Reminders",
    "task": "Tasks",
    "health_metric": "Health",
    "note": "Remembered",
}
_TYPE_ORDER = list(_TYPE_LABEL.keys())


def _profile_row(profile_id: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
    db.close()
    return dict(row) if row else None


def _nodes(profile_id: str) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM kg_nodes WHERE profile_id=? ORDER BY updated_at DESC", (profile_id,)
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


def get_profile_memory(profile_id: str | None) -> str:
    """Compact, token-cheap memory block for the LLMs. Built from structured data (no LLM)."""
    if not profile_id:
        return ""
    p = _profile_row(profile_id)
    if not p:
        return ""

    who = p["name"]
    bits = []
    if p.get("kind") == "pet":
        head = f"{who} (pet{', ' + p['species'] if p.get('species') else ''}"
    else:
        head = f"{who} ({p.get('relation') or 'self'}"
    if p.get("age"):
        head += f", {p['age']}"
    if p.get("gender"):
        head += f" {p['gender']}"
    if p.get("weight"):
        head += f", {p['weight']}kg"
    if p.get("height"):
        head += f", {p['height']}cm"
    head += ")"
    bits.append(head)
    if p.get("conditions"):
        bits.append(f"Conditions: {p['conditions']}")
    if p.get("notes"):
        bits.append(f"Notes: {p['notes']}")

    # Group KG nodes by type into short phrases (cap a few per type).
    grouped: dict[str, list[str]] = {}
    for n in _nodes(profile_id):
        grouped.setdefault(n["type"], []).append(n["name"])
    for t in _TYPE_ORDER:
        if t == "condition" and p.get("conditions"):
            continue  # already covered by the profile field
        names = grouped.get(t)
        if names:
            bits.append(f"{_TYPE_LABEL[t]}: {', '.join(names[:4])}")

    summary = _summary(profile_id)
    block = ". ".join(bits)
    if summary:
        block += f"\nRecent: {summary}"
    return block


def get_plan(profile_id: str | None, node_type: str) -> str:
    """Return the latest stored plan text of a given type (workout_plan / diet_plan) for a
    person, or "" if none. Used so the diet plan can coordinate with the workout plan."""
    if not profile_id:
        return ""
    for n in _nodes(profile_id):  # _nodes is ordered newest-first
        if n["type"] == node_type:
            return (n.get("data") or {}).get("plan", "") or ""
    return ""


def get_profile_graph(profile_id: str) -> dict:
    """Structured aggregate for the Profile detail view — About + nodes grouped by type."""
    p = _profile_row(profile_id)
    if not p:
        return {}
    grouped: dict[str, list[dict]] = {}
    for n in _nodes(profile_id):
        grouped.setdefault(n["type"], []).append(
            {"id": n["id"], "name": n["name"], "data": n["data"], "updated_at": n["updated_at"]}
        )
    return {"profile": p, "nodes": grouped, "summary": _summary(profile_id)}


def _summary(profile_id: str) -> str:
    db = get_db()
    row = db.execute("SELECT summary FROM kg_summaries WHERE profile_id=?", (profile_id,)).fetchone()
    db.close()
    return row["summary"] if row and row["summary"] else ""


def set_summary(profile_id: str, summary: str) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO kg_summaries(profile_id, summary, updated_at) VALUES(?,?,datetime('now')) "
        "ON CONFLICT(profile_id) DO UPDATE SET summary=excluded.summary, updated_at=datetime('now')",
        (profile_id, summary),
    )
    db.commit()
    db.close()


# ── Recipient resolution (used by reminders in Phase 2) ────────────────────────────
def resolve_recipient(mention: str, user_id: str) -> dict | None:
    """Map a mention like 'mother' / 'Bruno' / a name to one of the user's profiles."""
    if not mention:
        return None
    m = mention.strip().lower()
    db = get_db()
    rows = [dict(r) for r in db.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchall()]
    db.close()
    # exact name, then relation, then substring
    for r in rows:
        if (r.get("name") or "").lower() == m:
            return r
    for r in rows:
        if (r.get("relation") or "").lower() == m or m in (r.get("relation") or "").lower():
            return r
    for r in rows:
        if m in (r.get("name") or "").lower():
            return r
    return None
