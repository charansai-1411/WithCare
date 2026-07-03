"""
Gemini embeddings for the Reader (RAG). Wraps `embed_content` and cosine similarity.
Vectors are 768-dim (text-embedding-004). Kept tiny and dependency-light (numpy only).
"""
from __future__ import annotations

import numpy as np
from google.genai import types

from app.services.gemini_service import get_gemini_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

EMBED_MODEL = "text-embedding-004"
_BATCH = 100


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed a list of texts. Returns one vector (list of floats) per input, in order."""
    if not texts:
        return []
    client = get_gemini_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), _BATCH):
        batch = texts[i:i + _BATCH]
        resp = client.models.embed_content(
            model=EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        out.extend([list(e.values) for e in resp.embeddings])
    return out


def embed_query(text: str) -> list[float]:
    vecs = embed_texts([text], task_type="RETRIEVAL_QUERY")
    return vecs[0] if vecs else []


def cosine_top_k(query_vec: list[float], candidates: list[tuple], k: int = 6) -> list[tuple]:
    """candidates: list of (payload, vector). Returns the top-k [(payload, score)] by cosine."""
    if not query_vec or not candidates:
        return []
    q = np.asarray(query_vec, dtype=np.float32)
    qn = np.linalg.norm(q) or 1.0
    scored = []
    for payload, vec in candidates:
        if not vec:
            continue
        v = np.asarray(vec, dtype=np.float32)
        denom = (np.linalg.norm(v) or 1.0) * qn
        scored.append((payload, float(np.dot(q, v) / denom)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
