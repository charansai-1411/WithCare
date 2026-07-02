"""
Response Writer (LLM call #2).

Takes a CommunicationPlan (already decided by the deterministic Planner) plus the
resolved values, and writes ONE natural, warm message. It makes zero decisions — it
only phrases what the plan says to acknowledge / ask / offer / confirm / report.
"""
import json

from app.models.task_models import CommunicationPlan, TaskFrame, TaskResult
from app.services.gemini_service import generate_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

WRITER_SYSTEM = """You are WithCare's voice — a warm, concise healthcare navigation assistant for India.
You are given a PLAN that already decided everything: what to acknowledge, what to ask, what
preference to offer, what to confirm, what results to report. Your ONLY job is natural phrasing.
Do NOT add new questions, do NOT omit anything in the plan, do NOT change priorities.

Rules:
- ACKNOWLEDGE: briefly show you understood — don't robotically repeat the value.
- ASK: phrase as a goal-shaped question, not a form field. "Should I look for a clinic near you,
  or do you have one in mind?" — NOT "What is your location?"
- LOW_CONFIDENCE (location): gently note the attempt failed, ask for area/city — phrase it
  DIFFERENTLY from a normal location ask.
- OFFER_PREFERENCE: an optional add-on in the SAME sentence as the main ask/result, never mandatory.
- OFFER_FOLLOWUPS (coverage/insurance results only): after reporting the options, add ONE short,
  friendly line offering these next steps — combine them, don't make a long checklist:
    * eligibility_details -> to pin down what they actually qualify for, ask for the person's
      occupation, annual income, and category (BPL/APL, caste/community).
    * coverage_scope -> ask whether they want government options only, or private plans too.
    * next_step -> offer to walk through a specific plan or explain how to enrol / claim it.
- CONFIRM (highest priority — NEVER skip): if the plan has a CONFIRM item, you MUST end the
  message with an explicit one-sentence confirmation stating exactly what will happen and asking
  yes/no — e.g. "Shall I go ahead and book <procedure> at <hospital> on <date> — yes or no?".
  Even when you also reported results/facilities, always append this ask. Never end a CONFIRM
  turn without a clear yes/no question.
- REPORT_RESULTS: 1-2 sentences, lead with the top recommendation, invite follow-up — don't dump every field.
- Combine everything into ONE message. Vary phrasing. Never mention task IDs, internal fields, or agent names.
- CARE RECIPIENT: you're given who this care is for (name/relation, age, gender, known conditions).
  Personalise naturally when relevant — refer to them ("for your mother", "for Amma") and factor
  their known conditions into how you frame results. Don't recite their whole record or over-share.
- If the plan asks for nothing and reports nothing, just close warmly."""


def _resolved_values(frames_by_id: dict[str, TaskFrame], done_results: list[TaskResult]) -> dict:
    results_by_id = {r.task_id: r for r in done_results}
    out = {}
    for tid, f in frames_by_id.items():
        entry = {
            "intent": f.intent.value,
            "goal": f.goal,
            "known": {k: v.value for k, v in f.facts.items() if v.value},
            "preferences": {k: v.value for k, v in f.preferences.items() if v.value},
        }
        r = results_by_id.get(tid)
        if r and r.steps:
            entry["top_results"] = [
                {"name": s.action.replace("Visit ", ""), "detail": s.detail[:160]}
                for s in r.steps[:3]
            ]
        out[tid] = entry
    return out


async def compose(
    plan: CommunicationPlan,
    frames_by_id: dict[str, TaskFrame],
    done_results: list[TaskResult],
    history: list[dict],
    profile: str = "",
) -> str:
    resolved = _resolved_values(frames_by_id, done_results)
    history_text = "\n".join(
        f"{'User' if h.get('role') == 'user' else 'WithCare'}: {h.get('content', '')}"
        for h in (history or [])[-4:]
    )
    prompt = (
        f"CARE RECIPIENT:\n{profile or '(the user themselves)'}\n\n"
        f"PLAN:\n{plan.model_dump_json()}\n\n"
        f"RESOLVED VALUES (task_id -> details):\n{json.dumps(resolved, ensure_ascii=False)}\n\n"
        f"CONVERSATION SO FAR (last 4 turns, for tone):\n{history_text or '(none)'}"
    )
    try:
        return (await generate_text(WRITER_SYSTEM, prompt)).strip()
    except Exception as e:
        logger.error(f"Writer failed: {e}")
        # Deterministic fallback so the user still gets something coherent.
        return _fallback(plan, resolved)


def _fallback(plan: CommunicationPlan, resolved: dict) -> str:
    bits = []
    if plan.report_results:
        bits.append("Here's what I found for you.")
    if plan.confirm:
        bits.append("Shall I go ahead and book this? (yes/no)")
    if plan.ask or plan.low_confidence_flags:
        bits.append("Could you share a few more details so I can help?")
    return " ".join(bits) or "How can I help with your care today?"
