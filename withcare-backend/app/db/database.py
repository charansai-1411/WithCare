import sqlite3
import os

# In Cloud Run the DB lives on a mounted GCS volume (set WITHCARE_DB_PATH, e.g.
# /mnt/db/withcare.db). Locally it defaults to a file next to the backend.
DB_PATH = os.environ.get(
    "WITHCARE_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "withcare.db"),
)

# Ensure the parent directory exists (the GCS mount point, or local dir).
os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT DEFAULT 'You',
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT 'New conversation',
        profile_name TEXT DEFAULT 'You',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        care_plan TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        kind TEXT DEFAULT 'person',
        relation TEXT DEFAULT '',
        species TEXT DEFAULT '',
        email TEXT DEFAULT '',
        age INTEGER,
        gender TEXT DEFAULT '',
        weight REAL,
        height REAL,
        conditions TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        photo TEXT DEFAULT '',
        is_self INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    -- Knowledge graph: per-person memory that every feature reads/writes.
    CREATE TABLE IF NOT EXISTS kg_nodes (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        profile_id TEXT,
        type TEXT NOT NULL,        -- condition, medication, appointment, hospital, scheme,
                                   -- insurance, workout_plan, diet_plan, reminder, task, health_metric
        name TEXT NOT NULL,
        data TEXT DEFAULT '{}',    -- JSON payload
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS kg_edges (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        src TEXT NOT NULL,         -- node id or profile id
        predicate TEXT NOT NULL,   -- has_condition, booked, enrolled_in, follows_plan, has_reminder...
        dst TEXT NOT NULL,
        data TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS kg_summaries (
        profile_id TEXT PRIMARY KEY,
        summary TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS reminders (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        profile_id TEXT,            -- who the reminder is FOR (the target person)
        target_email TEXT DEFAULT '',
        message TEXT NOT NULL,
        kind TEXT DEFAULT 'one_time',   -- one_time | recurring
        recurrence TEXT DEFAULT '',      -- RRULE string, empty for one_time
        at_time TEXT DEFAULT '',         -- ISO datetime (one_time) or HH:MM (recurring)
        lead_minutes INTEGER DEFAULT 10,
        event_id TEXT DEFAULT '',        -- Google Calendar event id
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    );

    -- Reader (RAG): a shared per-user document library. Each doc has a freeform label/tag.
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        label TEXT DEFAULT '',           -- freeform tag/note, e.g. "Amma insurance", "lab report"
        mime TEXT DEFAULT '',
        kind TEXT DEFAULT 'document',    -- insurance | report | prescription | document (best-effort)
        char_count INTEGER DEFAULT 0,
        chunk_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'ready',     -- processing | ready | error
        error TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now'))
    );

    -- Retrieval chunks with their embedding (JSON float array), for cosine search.
    CREATE TABLE IF NOT EXISTS doc_chunks (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        chunk_index INTEGER DEFAULT 0,
        text TEXT NOT NULL,
        embedding TEXT DEFAULT '',        -- JSON array of floats
        created_at TEXT DEFAULT (datetime('now'))
    );

    -- Agentic core: a staged irreversible action awaiting the user's explicit confirmation.
    -- The confirmation gate is deterministic; the LLM can only stage, never execute.
    CREATE TABLE IF NOT EXISTS pending_actions (
        session_id TEXT PRIMARY KEY,
        tool TEXT NOT NULL,
        args TEXT NOT NULL DEFAULT '{}',
        summary TEXT DEFAULT '',
        base_ctx TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
    CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
    CREATE INDEX IF NOT EXISTS idx_prof_user ON profiles(user_id);
    CREATE INDEX IF NOT EXISTS idx_kgn_profile ON kg_nodes(profile_id);
    CREATE INDEX IF NOT EXISTS idx_kgn_user ON kg_nodes(user_id);
    CREATE INDEX IF NOT EXISTS idx_kge_src ON kg_edges(src);
    CREATE INDEX IF NOT EXISTS idx_rem_profile ON reminders(profile_id);
    CREATE INDEX IF NOT EXISTS idx_rem_user ON reminders(user_id);
    CREATE INDEX IF NOT EXISTS idx_doc_user ON documents(user_id);
    CREATE INDEX IF NOT EXISTS idx_chunk_user ON doc_chunks(user_id);
    CREATE INDEX IF NOT EXISTS idx_chunk_doc ON doc_chunks(document_id);
    """)

    # Idempotent column additions for existing DBs.
    for ddl in [
        "ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN picture TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN google_sub TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'guest'",
        "ALTER TABLE profiles ADD COLUMN kind TEXT DEFAULT 'person'",
        "ALTER TABLE profiles ADD COLUMN species TEXT DEFAULT ''",
        "ALTER TABLE profiles ADD COLUMN email TEXT DEFAULT ''",
        "ALTER TABLE profiles ADD COLUMN weight REAL",
        "ALTER TABLE profiles ADD COLUMN height REAL",
    ]:
        try:
            c.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
