from app.services.gemini_service import generate_structured
from app.utils.logger import get_logger

logger = get_logger(__name__)

CLINICAL_KEYWORDS = [
    "diagnose", "diagnosis", "what disease", "do i have", "is it cancer",
    "treatment for", "cure for", "medicine for", "what medication", "dosage",
    "should i take", "side effects of", "symptoms of", "test results mean",
    "what is wrong with", "prognosis", "how long will i live",
]

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_clinical": {
            "type": "boolean",
            "description": "True ONLY if the user is asking for a medical diagnosis, drug dosage, treatment recommendation, or clinical interpretation of test results. Navigation questions (finding hospitals, schemes, booking appointments) are NOT clinical.",
        },
        "is_ambiguous": {
            "type": "boolean",
            "description": "True ONLY if the request has absolutely zero context to act on — e.g. user said only 'help me' or 'book something' with no condition, procedure, or any health detail at all.",
        },
        "clarifying_question": {
            "type": "string",
            "description": "If is_ambiguous is true: ONE friendly message asking what health need they want help with. Empty string otherwise.",
        },
    },
    "required": ["is_clinical", "is_ambiguous", "clarifying_question"],
}

ROUTER_SYSTEM_PROMPT = """You are the intake router for WithCare, a healthcare navigation assistant for India.

Read the full conversation and determine two things:

1. is_clinical: Is the user asking us to MAKE a medical judgement — diagnose, decide treatment,
   pick/dose a medicine, judge severity, or interpret results? This holds whether it's about
   themselves OR a family member/pet ("my sister", "my father", "my dog").
   - YES: "diagnose my chest pain", "what medication should I take", "interpret my blood test",
     "is this lump cancer?", "what treatment does she need", "is this serious / should I worry?",
     "why is my dog vomiting", "what's causing his fever"
   - NO (navigation for a KNOWN or named need is fine): "find a hospital", "best cancer hospital",
     "schedule an appointment", "which scheme covers this", "book eye checkup", "schemes for her
     diabetes". Naming a disease to find care/coverage is NOT clinical; asking us to decide the
     diagnosis or treatment IS.
   - NO also — general WELLNESS help is fine, even for a named condition and for PETS:
     "create a diet plan for my dog", "make a weekly workout plan for my father", "meal plan for
     her diabetes", "set a reminder to take medicine at 1pm". Diet/fitness/reminders — for people
     OR pets — are lifestyle guidance, not medical treatment. Never mark these clinical.
   When in doubt between "asking us to judge a symptom or prescribe a medicine/treatment" and
   "navigation or wellness help", only the former is clinical.

2. is_ambiguous: Is there genuinely zero health context to act on?
   - YES: "help me" / "book something" with absolutely no other details
   - NO: If the user mentioned ANY condition, procedure, body part, symptom, or healthcare need — even vaguely — it is NOT ambiguous. The agents can figure out the rest.
   - "schedule eye checkup" → NOT ambiguous (procedure is clear)
   - "near me, tomorrow 5pm" → NOT ambiguous if prior conversation has context
   - "I need help with Amma" → ambiguous (no health context)

Do NOT ask about location, hospital, date, or time — the agents will find/ask for those if needed.
Only mark ambiguous if there is truly nothing healthcare-related to work with."""


async def classify_intent(
    message: str,
    profile: list[dict] | None = None,
    history: list[dict] | None = None,
    location: str = "",
) -> dict:
    # Fast-path: keyword clinical check
    lower = message.lower()
    if any(kw in lower for kw in CLINICAL_KEYWORDS):
        logger.info("Clinical request detected via keyword fast-path")
        return {"is_clinical": True, "is_ambiguous": False, "clarifying_question": ""}

    history_context = ""
    if history:
        turns = "\n".join(
            f"{'User' if h.get('role') == 'user' else 'WithCare'}: {h.get('content', '')}"
            for h in history[-6:]
        )
        history_context = f"\n\nConversation so far:\n{turns}"

    try:
        result = await generate_structured(
            system_prompt=ROUTER_SYSTEM_PROMPT,
            user_prompt=f"{history_context}\n\nLatest message: {message}",
            response_schema=INTENT_SCHEMA,
        )
        logger.info(
            f"Router: clinical={result.get('is_clinical')}, "
            f"ambiguous={result.get('is_ambiguous')}"
        )
        return result
    except Exception as e:
        logger.error(f"Router classification failed: {e}")
        return {"is_clinical": False, "is_ambiguous": False, "clarifying_question": ""}
