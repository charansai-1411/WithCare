"""
Reader (RAG) service — a shared per-user document library that WithCare can answer from.

Flow:  upload → extract text (Gemini multimodal reads PDFs *and* images/scans; a guarded pypdf
fast-path is used for text PDFs if the lib is present) → chunk → embed → store.
query → embed question → cosine over the user's chunks → Gemini answers from the top chunks,
citing the document's label.

Storage: SQLite (documents / doc_chunks). Vectors live as JSON in doc_chunks.embedding.
"""
from __future__ import annotations

import io
import json
import uuid

from google.genai import types

from app.db.database import get_db
from app.services.gemini_service import get_gemini_client, generate_text
from app.services.embedding_service import embed_texts, embed_query, cosine_top_k
from app.services.skills import load_skill
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_CHARS = 1200
_OVERLAP = 150


# ── extraction ─────────────────────────────────────────────────────────────────
def _pdf_text_fast(file_bytes: bytes) -> str:
    """Local, free PDF text extraction if pypdf is installed; else "" to trigger Gemini."""
    try:
        import pypdf  # optional; not required
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return text if len(text.strip()) > 40 else ""
    except Exception:
        return ""


def extract_text(file_bytes: bytes, mime: str) -> str:
    """Extract text from a PDF or image. PDFs try a local fast-path first, then Gemini;
    images always go through Gemini vision (OCR)."""
    mime = (mime or "").lower()
    if "pdf" in mime:
        fast = _pdf_text_fast(file_bytes)
        if fast:
            return fast
    # Gemini multimodal (handles scanned PDFs and images/photos)
    client = get_gemini_client()
    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime or "application/pdf"),
            "Extract ALL text from this document verbatim, preserving structure, numbers, dates, "
            "amounts, tables and field labels. Output plain text only — no commentary.",
        ],
        config=types.GenerateContentConfig(
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            max_output_tokens=8192,
        ),
    )
    return (resp.text or "").strip()


def _chunk(text: str) -> list[str]:
    """Character chunks with overlap, split on paragraph/whitespace boundaries."""
    text = (text or "").strip()
    if not text:
        return []
    chunks, i, n = [], 0, len(text)
    while i < n:
        end = min(i + _MAX_CHARS, n)
        if end < n:  # back up to a boundary
            cut = text.rfind("\n", i + int(_MAX_CHARS * 0.6), end)
            if cut == -1:
                cut = text.rfind(" ", i + int(_MAX_CHARS * 0.6), end)
            if cut != -1:
                end = cut
        chunks.append(text[i:end].strip())
        if end >= n:
            break
        i = max(end - _OVERLAP, i + 1)
    return [c for c in chunks if c]


def _guess_kind(label: str, filename: str, text: str) -> str:
    hay = f"{label} {filename} {text[:600]}".lower()
    if any(w in hay for w in ("insur", "policy", "sum insured", "premium", "aarogyasri", "mediclaim", "cashless")):
        return "insurance"
    if any(w in hay for w in ("prescription", "rx", "tablet", "mg ", "dosage", "sig ")):
        return "prescription"
    if any(w in hay for w in ("report", "lab", "haemoglobin", "hba1c", "cholesterol", "blood", "scan", "x-ray", "mri")):
        return "report"
    return "document"


# ── public API ─────────────────────────────────────────────────────────────────
def ingest_document(user_id: str, filename: str, label: str, mime: str, file_bytes: bytes) -> dict:
    """Extract → chunk → embed → store. Returns the document row (dict)."""
    doc_id = "d-" + uuid.uuid4().hex[:12]
    db = get_db()
    db.execute(
        "INSERT INTO documents(id, user_id, filename, label, mime, status) VALUES(?,?,?,?,?, 'processing')",
        (doc_id, user_id, filename, label or "", mime or ""),
    )
    db.commit()
    try:
        text = extract_text(file_bytes, mime)
        if not text.strip():
            raise ValueError("No readable text found in the document.")
        chunks = _chunk(text)
        vectors = embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")
        for idx, (ch, vec) in enumerate(zip(chunks, vectors)):
            db.execute(
                "INSERT INTO doc_chunks(id, document_id, user_id, chunk_index, text, embedding) VALUES(?,?,?,?,?,?)",
                ("dc-" + uuid.uuid4().hex[:12], doc_id, user_id, idx, ch, json.dumps(vec)),
            )
        kind = _guess_kind(label, filename, text)
        db.execute(
            "UPDATE documents SET status='ready', char_count=?, chunk_count=?, kind=? WHERE id=?",
            (len(text), len(chunks), kind, doc_id),
        )
        db.commit()
    except Exception as e:
        logger.warning(f"ingest failed for {filename}: {e}")
        db.execute("UPDATE documents SET status='error', error=? WHERE id=?", (str(e)[:300], doc_id))
        db.commit()
    row = db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    db.close()
    return dict(row)


def list_documents(user_id: str) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM documents WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def delete_document(user_id: str, doc_id: str) -> bool:
    db = get_db()
    owned = db.execute("SELECT id FROM documents WHERE id=? AND user_id=?", (doc_id, user_id)).fetchone()
    if not owned:
        db.close()
        return False
    db.execute("DELETE FROM doc_chunks WHERE document_id=?", (doc_id,))
    db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    db.commit()
    db.close()
    return True


def search(user_id: str, query: str, k: int = 6, label: str | None = None) -> list[dict]:
    """Return the top-k relevant chunks: [{text, score, label, filename, document_id}]."""
    db = get_db()
    sql = ("SELECT c.text, c.embedding, d.label, d.filename, d.id AS doc_id "
           "FROM doc_chunks c JOIN documents d ON d.id=c.document_id "
           "WHERE c.user_id=? AND d.status='ready'")
    params: list = [user_id]
    if label:
        sql += " AND lower(d.label) LIKE ?"
        params.append(f"%{label.lower()}%")
    rows = db.execute(sql, params).fetchall()
    db.close()
    if not rows:
        return []
    candidates = []
    for r in rows:
        try:
            vec = json.loads(r["embedding"] or "[]")
        except Exception:
            vec = []
        candidates.append((dict(r), vec))
    qv = embed_query(query)
    top = cosine_top_k(qv, candidates, k=k)
    return [{"text": p["text"], "score": round(s, 3), "label": p["label"],
             "filename": p["filename"], "document_id": p["doc_id"]} for p, s in top]


# Prefer the modular Reader skill; fall back to this lean prompt if the file is missing.
_ANSWER_SYSTEM_FALLBACK = (
    "You answer the user's question using ONLY the document excerpts provided. "
    "Be specific — quote exact figures, dates, limits and terms. If the excerpts don't "
    "contain the answer, say so plainly; never invent details. Cite which document each fact "
    "came from by its label in parentheses. Keep it concise and clear."
)


def _answer_system() -> str:
    return load_skill("reader") or _ANSWER_SYSTEM_FALLBACK


def _dedupe_sources(hits: list[dict]) -> list[dict]:
    seen, sources = set(), []
    for h in hits:
        key = h["document_id"]
        if key in seen:
            continue
        seen.add(key)
        sources.append({"label": h["label"] or h["filename"], "filename": h["filename"],
                        "score": h["score"], "snippet": h["text"][:180]})
    return sources


async def answer(user_id: str, question: str, label: str | None = None) -> dict:
    """RAG answer: retrieve top chunks and let Gemini answer strictly from them, with sources."""
    hits = search(user_id, question, k=6, label=label)
    if not hits:
        return {"answer": "I couldn't find anything about that in your uploaded documents. "
                          "Try uploading the relevant file, or rephrasing your question.",
                "sources": [], "found": False}
    context = "\n\n".join(f"[Doc: {h['label'] or h['filename']}]\n{h['text']}" for h in hits)
    prompt = f"Document excerpts:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    text = await generate_text(_answer_system(), prompt)
    return {"answer": text.strip(), "sources": _dedupe_sources(hits), "found": True}


def context_for_agent(user_id: str, question: str, label: str | None = None) -> dict:
    """Lightweight retrieval for the orchestrator tool: returns the raw excerpts + sources so the
    main chat's LLM composes the answer itself (no extra generate call here)."""
    hits = search(user_id, question, k=6, label=label)
    if not hits:
        return {"found": False, "excerpts": "", "sources": []}
    excerpts = "\n\n".join(f"[{h['label'] or h['filename']}] {h['text']}" for h in hits)
    return {"found": True, "excerpts": excerpts, "sources": _dedupe_sources(hits)}
