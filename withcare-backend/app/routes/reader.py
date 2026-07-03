"""
Reader (RAG) API — a shared per-user document library WithCare can answer from.
  POST   /api/documents        multipart upload (file, label) → ingest
  GET    /api/documents        list the user's documents
  DELETE /api/documents/{id}   remove a document + its chunks
  POST   /api/documents/ask    { question, label? } → grounded answer + sources
"""
import asyncio

from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form

from app.services import reader_service

router = APIRouter(prefix="/api/documents", tags=["Reader"])

_ALLOWED = {"application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp"}
_MAX_BYTES = 12 * 1024 * 1024  # 12 MB


@router.get("")
def list_docs(x_user_id: str = Header(...)):
    return reader_service.list_documents(x_user_id)


@router.post("")
async def upload_doc(file: UploadFile = File(...), label: str = Form(""), x_user_id: str = Header(...)):
    mime = (file.content_type or "").lower()
    if mime not in _ALLOWED:
        raise HTTPException(status_code=415, detail="Please upload a PDF or an image (PNG/JPG).")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 12 MB).")
    # ingest is blocking (extraction + embeddings) → run off the event loop
    doc = await asyncio.to_thread(
        reader_service.ingest_document, x_user_id, file.filename or "document", label, mime, data
    )
    if doc.get("status") == "error":
        raise HTTPException(status_code=422, detail=doc.get("error") or "Could not read the document.")
    return doc


@router.delete("/{doc_id}")
def delete_doc(doc_id: str, x_user_id: str = Header(...)):
    if not reader_service.delete_document(x_user_id, doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"ok": True}


@router.post("/ask")
async def ask_docs(body: dict, x_user_id: str = Header(...)):
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")
    label = (body.get("label") or "").strip() or None
    return await reader_service.answer(x_user_id, question, label=label)
