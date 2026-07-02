"""
DietAgent — generates a 7-day diet plan tailored to a person's or pet's conditions, using the
`diet` skill and the knowledge-graph memory. Stores it as a diet_plan node (one per profile; a
new plan supersedes the old, supporting adaptivity as health changes).
"""
from app.agents.base_agent import BaseAgent
from app.models.response_models import AgentResult, SourcedStep
from app.services.gemini_service import generate_text
from app.services.memory_service import write_fact
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
        age = member.get("age")
        conditions = member.get("conditions") or ""
        memory = context.get("memory") or ""

        subject = f"{who} (a {species} pet)" if is_pet else who
        prompt = (
            f"Create the 7-day diet plan.\n"
            f"For: {subject}" + (f", age {age}" if age else "") + ".\n"
            f"Known conditions: {conditions or 'none stated'}.\n"
            f"What we know about them: {memory or '(nothing extra)'}\n"
            + ("This is a pet — use species-appropriate foods.\n" if is_pet else "")
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
