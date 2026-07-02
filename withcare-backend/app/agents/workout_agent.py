"""
WorkoutAgent — generates a weekly workout plan tailored to a person's age/conditions, using the
`workout` skill and the knowledge-graph memory. Stores the plan as a workout_plan node (one per
person; a new plan supersedes the old).
"""
from app.agents.base_agent import BaseAgent
from app.models.response_models import AgentResult, SourcedStep
from app.services.gemini_service import generate_text
from app.services.memory_service import write_fact
from app.services.skills import load_skill


class WorkoutAgent(BaseAgent):
    name = "workout_agent"
    description = "Creates weekly workout plans tailored to health conditions"

    async def run(self, context: dict) -> AgentResult:
        self.logger.info("WorkoutAgent starting")
        family = context.get("family_profile") or []
        member = family[0] if family else {}
        who = member.get("name") or context.get("for_member") or "you"
        age = member.get("age")
        conditions = member.get("conditions") or ""
        memory = context.get("memory") or ""

        prompt = (
            f"Create the weekly workout plan.\n"
            f"Person: {who}" + (f", age {age}" if age else "") + ".\n"
            f"Known conditions: {conditions or 'none stated'}.\n"
            f"What we know about them: {memory or '(nothing extra)'}\n"
        )
        try:
            plan = (await generate_text(load_skill("workout"), prompt)).strip()
        except Exception as e:
            self.logger.warning(f"workout generation failed: {e}")
            return AgentResult(agent_name=self.name, steps=[], raw_data=[])

        try:
            write_fact(context.get("user_id", ""), context.get("active_profile_id"),
                       "workout_plan", f"Weekly workout plan for {who}",
                       data={"plan": plan}, predicate="follows_plan", unique="type")
        except Exception as ex:
            self.logger.warning(f"KG write (workout_plan) failed: {ex}")

        return AgentResult(
            agent_name=self.name,
            steps=[SourcedStep(step_number=1, action=f"Weekly workout plan for {who}",
                               detail=plan, source_url="", source_label="WithCare Plan",
                               agent=self.name)],
            raw_data=[],
        )
