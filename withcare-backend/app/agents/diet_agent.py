"""
DietAgent — generates a 7-day diet plan tailored to a person's or pet's conditions, using the
`diet` skill and the knowledge-graph memory. Stores it as a diet_plan node (one per profile; a
new plan supersedes the old, supporting adaptivity as health changes).
"""
from app.agents.base_agent import BaseAgent
from app.models.response_models import AgentResult, SourcedStep
from app.services.gemini_service import generate_text
from app.services.memory_service import write_fact, get_plan
from app.services.skills import load_skill


class DietAgent(BaseAgent):
    name = "diet_agent"
    description = "Creates diet plans tailored to health conditions (people and pets)"

    async def run(self, context: dict) -> AgentResult:
        self.logger.info("DietAgent starting")
        family = context.get("family_profile") or []
        member = family[0] if family else {}
        who = member.get("name") or context.get("for_member") or "you"
        is_pet = member.get("kind") == "pet"
        species = member.get("species") or ""
        conditions = member.get("conditions") or ""
        memory = context.get("memory") or ""
        goal = context.get("goal") or context.get("focus") or "maintain (normal)"
        adjustment = (context.get("adjustment") or "").strip()

        # If the user is changing an existing plan, start from it and apply the change.
        current_plan = get_plan(context.get("active_profile_id"), "diet_plan") if adjustment else ""

        # Full physical profile so portions/calories/macros can be tailored.
        facts = []
        if member.get("age"):    facts.append(f"age {member['age']}")
        if member.get("gender"): facts.append(str(member["gender"]))
        if member.get("weight"): facts.append(f"weight {member['weight']} kg")
        if member.get("height"): facts.append(f"height {member['height']} cm")
        facts_line = ", ".join(facts) if facts else "not specified"

        # Coordinate with the person's current workout plan, if one exists.
        workout = get_plan(context.get("active_profile_id"), "workout_plan") if not is_pet else ""

        subject = f"{who} (a {species} pet)" if is_pet else f"{who} ({facts_line})"
        prompt = (
            f"Create the 7-day diet plan.\n"
            f"For: {subject}.\n"
            + (f"GOAL: {goal}.  ← size portions and calories around this goal.\n" if not is_pet else "")
            + f"Known conditions: {conditions or 'none stated'}.\n"
            + (f"Other details: {member['notes']}.\n" if member.get("notes") else "")
            + f"What we know about them: {memory or '(nothing extra)'}\n"
            + ("This is a pet — use species-appropriate foods.\n" if is_pet else
               "Use their age/weight/height to size portions and energy needs.\n")
            + (
                "\nThey are ALSO following this workout plan — design the diet to FUEL it: put "
                "more carbs/protein and calories on training days, lighter on rest days, and align "
                "meal timing with workouts:\n"
                f"----- CURRENT WORKOUT PLAN -----\n{workout}\n--------------------------------\n"
                if workout else ""
            )
            + (
                "\nThe user wants to CHANGE their existing diet plan. Apply this requested change "
                f"and keep the rest of what already works:\nCHANGE REQUESTED: {adjustment}\n"
                "Regenerate the FULL 7-day plan (Day 1–7) with the change applied — do not return a "
                "partial plan. Honour any dietary restriction implied by the change (e.g. "
                "vegetarian, no dairy, an allergy).\n"
                f"----- CURRENT DIET PLAN TO MODIFY -----\n{current_plan}\n---------------------------------------\n"
                if adjustment and current_plan else
                (f"\nApply this preference to the plan: {adjustment}.\n" if adjustment else "")
            )
        )
        try:
            plan = (await generate_text(load_skill("diet"), prompt)).strip()
        except Exception as e:
            self.logger.warning(f"diet generation failed: {e}")
            return AgentResult(agent_name=self.name, steps=[], raw_data=[])

        try:
            write_fact(context.get("user_id", ""), context.get("active_profile_id"),
                       "diet_plan", f"Diet plan for {who}",
                       data={"plan": plan}, predicate="follows_plan", unique="type")
        except Exception as ex:
            self.logger.warning(f"KG write (diet_plan) failed: {ex}")

        return AgentResult(
            agent_name=self.name,
            steps=[SourcedStep(step_number=1, action=f"Diet plan for {who}",
                               detail=plan, source_url="", source_label="WithCare Plan",
                               agent=self.name)],
            raw_data=[],
        )
