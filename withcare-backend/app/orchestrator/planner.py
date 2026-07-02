"""
Planner (deterministic — no LLM).

Reads the current TaskFrames + this turn's TaskResults and produces a CommunicationPlan:
what to acknowledge, the single highest-priority thing to ask per blocked task, which
preference to offer, and what to confirm. This is the piece that makes the ask/act/offer
rules a GUARANTEE (plain Python) rather than a prompt an LLM might ignore.
"""
from app.models.task_models import (
    CommunicationPlan,
    ELIGIBILITY_FACT_KEYS,
    PREFERENCE_TRIGGERS,
    SCHEME_FOLLOWUPS,
    TaskFrame,
    TaskIntent,
    TaskResult,
    TaskStatus,
)


def plan(active_frames: list[TaskFrame], done_results: list[TaskResult]) -> CommunicationPlan:
    p = CommunicationPlan()
    done_ids = {r.task_id for r in done_results if r.status == TaskStatus.DONE and r.steps}

    for r in done_results:
        if r.status == TaskStatus.DONE and r.steps:
            p.report_results.append(r.task_id)

    for f in active_frames:
        if f.status == TaskStatus.COLLECTING:
            # Acknowledge what we just learned; flag an unresolved location specially.
            for k in f.just_learned:
                if k == "location_unresolved":
                    p.low_confidence_flags.append(f"{f.task_id}.location")
                else:
                    p.acknowledge.append(f"{f.task_id}.{k}")
            # Ask ONE fact — priority is REQUIRED_FACTS order (missing_required preserves it).
            missing = f.missing_required
            if missing:
                p.ask.append(f"{f.task_id}.{missing[0]}")

        # Re-rank preference: offered on a facility frame that finished THIS turn,
        # unless the preference is already locked by the user.
        if f.status == TaskStatus.DONE and f.task_id in done_ids:
            for pref in PREFERENCE_TRIGGERS.get(f.intent, []):
                locked = pref in f.preferences and f.preferences[pref].user_specified
                if not locked:
                    p.offer_preference.append(f"{f.task_id}.{pref}")
                    break  # cap: one preference offer per task per turn

            # Coverage follow-ups — offer only the ones not yet answered.
            if f.intent == TaskIntent.FIND_SCHEME:
                has_elig = any(f.facts.get(k) and f.facts[k].value for k in ELIGIBILITY_FACT_KEYS)
                has_scope = "coverage_scope" in f.preferences
                for fu in SCHEME_FOLLOWUPS:
                    if fu == "eligibility_details" and has_elig:
                        continue
                    if fu == "coverage_scope" and has_scope:
                        continue
                    p.offer_followups.append(f"{f.task_id}.{fu}")

        if f.status == TaskStatus.AWAITING_CONFIRMATION:
            p.confirm.append(f.task_id)

    return p
