"""
Doctor-visit capture — turn a recorded consultation transcript into a structured, searchable
record.

Flow:  Gemini Live listens to the consultation (see /ws/scribe) and produces a transcript ->
extract_visit() runs ONE Gemini call that pulls out the medically actionable parts (medicines,
diet, exercise, routines, tests, follow-up) -> save_visit() writes a readable visit record into
the Reader (RAG) library, tagged with the patient, hospital, doctor and date, so the user can
later ask "summarise last week's doctor visit" and get an answer grounded in what was said.

Nothing is auto-prescribed: the extraction is stored for reference and surfaced as one-tap
suggestions the user can choose to add to Medications / Routines.
"""
from __future__ import annotations

from datetime import date, datetime

from app.services import reader_service
from app.services.gemini_service import generate_structured
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── extraction ─────────────────────────────────────────────────────────────────────
_EXTRACT_SYSTEM = (
    "You are a careful medical scribe. You are given the raw transcript of a conversation between "
    "a patient (or their caregiver) and a doctor at a clinic/hospital in India. Extract ONLY what "
    "the doctor actually stated — never guess, never add medicines or doses that were not spoken. "
    "If a detail (dose, timing, hospital name, doctor name) was not clearly said, leave that field "
    "an empty string. Transcripts can be noisy and may mix English with Indian languages; still "
    "capture the medical instructions. Write the summary in plain English a family member can act "
    "on. This is a record, NOT medical advice, and you must not invent a diagnosis."
)

# Vertex response schema (OpenAPI subset) — forces structured JSON out.
_VISIT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "2-4 sentence plain-English summary of the visit."},
        "diagnosis": {"type": "string", "description": "Diagnosis/assessment the doctor stated, or ''."},
        "medications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dose": {"type": "string", "description": "e.g. '500mg', '1 tablet'"},
                    "timing": {"type": "string", "description": "when/how often, e.g. 'after breakfast & dinner'"},
                    "duration": {"type": "string", "description": "e.g. '5 days', 'ongoing'"},
                    "notes": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        "diet": {"type": "array", "items": {"type": "string"}, "description": "Food/diet advice, one point each."},
        "workouts": {"type": "array", "items": {"type": "string"}, "description": "Exercise/activity advice."},
        "routines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "workout|diet|skincare|checkup|sleep|hydration|eyecare|physio|other"},
                    "name": {"type": "string"},
                    "content": {"type": "string"},
                    "frequency": {"type": "string"},
                },
                "required": ["name", "content"],
            },
        },
        "tests": {"type": "array", "items": {"type": "string"}, "description": "Lab tests / scans advised."},
        "follow_up": {"type": "string", "description": "Next visit / follow-up instruction, or ''."},
        "hospital": {"type": "string", "description": "Hospital/clinic name if spoken, else ''."},
        "doctor": {"type": "string", "description": "Doctor's name if spoken, else ''."},
    },
    "required": ["summary"],
}


async def extract_visit(transcript: str, patient_name: str = "") -> dict:
    """Run one Gemini call to pull structured medical info out of a consultation transcript."""
    transcript = (transcript or "").strip()
    if not transcript:
        return {"summary": "", "medications": [], "diet": [], "workouts": [], "routines": [],
                "tests": [], "follow_up": "", "diagnosis": "", "hospital": "", "doctor": ""}
    who = f" The patient is {patient_name}." if patient_name else ""
    prompt = (f"Transcript of the doctor consultation:{who}\n\n{transcript}\n\n"
              "Extract the structured record now.")
    try:
        data = await generate_structured(_EXTRACT_SYSTEM, prompt, _VISIT_SCHEMA)
    except Exception as e:
        logger.warning(f"visit extraction failed: {e}")
        # Degrade gracefully: keep the transcript, empty structure.
        data = {"summary": "", "medications": [], "diet": [], "workouts": [], "routines": [],
                "tests": [], "follow_up": "", "diagnosis": "", "hospital": "", "doctor": ""}
    # Normalise shape so the frontend/render never trips on a missing key.
    data.setdefault("summary", "")
    for k in ("medications", "diet", "workouts", "routines", "tests"):
        if not isinstance(data.get(k), list):
            data[k] = []
    for k in ("diagnosis", "follow_up", "hospital", "doctor"):
        data.setdefault(k, "")
    return data


# ── record building + save ───────────────────────────────────────────────────────────
def _bullets(items: list, fmt) -> str:
    return "\n".join(f"  - {fmt(x)}" for x in items if x)


def build_record_text(visit: dict, patient: str, hospital: str, doctor: str, when: str,
                      transcript: str) -> str:
    """A human-readable + RAG-friendly visit record. Metadata sits at the top so retrieval
    always surfaces the who/where/when."""
    lines = [
        "DOCTOR VISIT RECORD",
        f"Patient: {patient or 'Not specified'}",
        f"Date: {when}",
        f"Hospital / clinic: {hospital or 'Not specified'}",
        f"Doctor: {doctor or 'Not specified'}",
        "",
        f"Summary: {visit.get('summary') or 'Not captured.'}",
    ]
    if visit.get("diagnosis"):
        lines.append(f"Assessment: {visit['diagnosis']}")
    if visit.get("medications"):
        lines.append("\nMedications advised:")
        lines.append(_bullets(visit["medications"], lambda m:
            f"{m.get('name','')}"
            + (f" — {m['dose']}" if m.get("dose") else "")
            + (f", {m['timing']}" if m.get("timing") else "")
            + (f", for {m['duration']}" if m.get("duration") else "")
            + (f". {m['notes']}" if m.get("notes") else "")))
    if visit.get("diet"):
        lines.append("\nDiet advice:")
        lines.append(_bullets(visit["diet"], lambda s: s))
    if visit.get("workouts"):
        lines.append("\nExercise / activity advice:")
        lines.append(_bullets(visit["workouts"], lambda s: s))
    if visit.get("routines"):
        lines.append("\nRoutines suggested:")
        lines.append(_bullets(visit["routines"], lambda r:
            f"{r.get('name','')} ({r.get('category','other')}"
            + (f", {r['frequency']}" if r.get("frequency") else "") + f"): {r.get('content','')}"))
    if visit.get("tests"):
        lines.append("\nTests advised:")
        lines.append(_bullets(visit["tests"], lambda s: s))
    if visit.get("follow_up"):
        lines.append(f"\nFollow-up: {visit['follow_up']}")
    if transcript:
        lines.append("\n--- Full transcript ---")
        lines.append(transcript.strip())
    return "\n".join(lines)


async def save_visit(user_id: str, patient_name: str = "", hospital: str = "", doctor: str = "",
                     transcript: str = "", when: str | None = None) -> dict:
    """Extract the visit, write it to the Reader, and return the structured result + doc id.

    Hospital/doctor default to what the transcript revealed if the caller didn't pass them."""
    transcript = (transcript or "").strip()
    when = when or date.today().isoformat()
    visit = await extract_visit(transcript, patient_name)

    hospital = (hospital or "").strip() or (visit.get("hospital") or "").strip()
    doctor = (doctor or "").strip() or (visit.get("doctor") or "").strip()
    visit["hospital"], visit["doctor"] = hospital, doctor
    visit["patient"] = patient_name
    visit["date"] = when

    record = build_record_text(visit, patient_name, hospital, doctor, when, transcript)
    label = f"Doctor visit: {patient_name or 'patient'}" \
            + (f" at {hospital}" if hospital else "") + f" ({when})"
    doc = reader_service.ingest_text(
        user_id, label, record, kind="visit", filename=f"visit-{when}.txt")

    return {
        "doc_id": doc.get("id"),
        "label": label,
        "status": doc.get("status"),
        "saved_at": datetime.utcnow().isoformat(),
        "visit": visit,
    }
