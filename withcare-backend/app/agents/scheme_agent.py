import json
import re

from app.agents.base_agent import BaseAgent
from app.models.response_models import AgentResult, SourcedStep
from app.services.gemini_service import generate_with_search
from app.services.memory_service import write_fact
from app.tools.firestore_tool import query_schemes


ELIGIBILITY_SCHEMA = {
    "type": "object",
    "properties": {
        "state": {"type": "string", "description": "Indian state name, empty string if not mentioned"},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Eligibility tags from: BPL, salaried, employment, central_government_employee, pensioner, unorganised_sector, accident, low_income, cancer, cardiac, dialysis",
        },
        "income_level": {"type": "string", "enum": ["BPL", "low", "middle", "high", "unknown"]},
    },
    "required": ["state", "tags", "income_level"],
}

RANK_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "scheme_id": {"type": "string"},
            "relevance_reason": {"type": "string"},
            "how_to_apply_summary": {"type": "string"},
        },
        "required": ["scheme_id", "relevance_reason", "how_to_apply_summary"],
    },
}


class SchemeAgent(BaseAgent):
    name = "scheme_agent"
    description = "Finds government health schemes the user is eligible for and explains how to apply"

    async def run(self, context: dict) -> AgentResult:
        self.logger.info("SchemeAgent starting")
        user_message = context.get("user_message", "")
        scope = context.get("coverage_scope", "both")  # both | government | private
        want_gov = scope in ("both", "government")
        want_private = scope in ("both", "private")

        # Step 1: Extract eligibility signals
        eligibility = await self._extract_eligibility(user_message)
        self.logger.info(f"Eligibility extracted: {eligibility} (scope={scope})")

        # Step 2: Query Firestore for GOVERNMENT schemes (if wanted)
        schemes = []
        if want_gov:
            schemes = await query_schemes(
                tags=eligibility.get("tags") or None,
                state=eligibility.get("state") or None,
            )

        steps: list[SourcedStep] = []
        step_num = 1

        if schemes:
            ranked = await self._rank_and_explain(schemes, user_message)
            scheme_map = {s["id"]: s for s in schemes}
            for item in ranked:
                scheme = scheme_map.get(item.get("scheme_id", ""))
                if not scheme:
                    continue
                source_url = scheme.get("application_url") or scheme.get("source_url", "")
                steps.append(SourcedStep(
                    step_number=step_num,
                    action=f"Apply for {scheme['name']}",
                    detail=f"Government scheme — {item['relevance_reason']} — {item['how_to_apply_summary']}",
                    source_url=source_url,
                    source_label=scheme["name"],
                    agent=self.name,
                ))
                step_num += 1
        else:
            self.logger.info("No government schemes matched in Firestore")

        # Step 3: PRIVATE insurance via Google Search grounding (if wanted)
        private = await self._find_private_insurance(context) if want_private else []
        for p in private:
            p.step_number = step_num
            steps.append(p)
            step_num += 1

        # Remember what coverage was explored for this person.
        try:
            uid = context.get("user_id", "")
            pid = context.get("active_profile_id")
            for p in private[:3]:
                write_fact(uid, pid, "insurance", p.source_label.replace(" (private insurance)", ""),
                           data={"detail": p.detail[:160]}, predicate="explored")
            for s in steps[:3]:
                if "private insurance" not in (s.source_label or ""):
                    write_fact(uid, pid, "scheme", s.source_label,
                               data={"detail": s.detail[:160]}, predicate="explored")
        except Exception as ex:
            self.logger.warning(f"KG write (coverage) failed: {ex}")

        self.logger.info(f"SchemeAgent produced {len(steps)} steps ({len(private)} private)")
        return AgentResult(agent_name=self.name, steps=steps, raw_data=schemes)

    async def _find_private_insurance(self, context: dict) -> list[SourcedStep]:
        """Live private health-insurance options via grounded Google Search."""
        recipient = context.get("care_recipient", "") or "the user"
        location = context.get("location", "") or "India"
        condition = context.get("condition", "")

        system = (
            "You are a health-insurance research assistant for India. Use Google Search to find "
            "CURRENT, real private health insurance plans from reputable insurers (e.g. Star Health, "
            "HDFC ERGO, Niva Bupa, Care Health, ICICI Lombard) or marketplaces (PolicyBazaar). "
            "Prefer plans that suit the person's age and conditions."
        )
        prompt = (
            f"Find up to 4 private health insurance plans in India suitable for: {recipient}. "
            f"Location: {location}." + (f" Health focus: {condition}." if condition else "") + "\n\n"
            "Return ONLY a JSON array, no prose. Each item: "
            '{"insurer": str, "plan": str, "why_suitable": str, "approx_premium": str, '
            '"buy_url": str, "how_to_buy": str}. Use real insurer names and plausible official URLs.'
        )
        try:
            raw = await generate_with_search(system, prompt)
            items = self._parse_json_array(raw)
        except Exception as e:
            self.logger.warning(f"Private insurance search failed (non-critical): {e}")
            return []

        out: list[SourcedStep] = []
        for it in items[:4]:
            insurer = (it.get("insurer") or "").strip()
            plan = (it.get("plan") or "").strip()
            if not insurer:
                continue
            title = f"{insurer} — {plan}" if plan else insurer
            detail_bits = [
                "Private insurance",
                it.get("why_suitable", "").strip(),
                f"Approx premium: {it['approx_premium']}" if it.get("approx_premium") else "",
                it.get("how_to_buy", "").strip(),
            ]
            out.append(SourcedStep(
                step_number=0,
                action=f"Consider {title}",
                detail=" — ".join(b for b in detail_bits if b),
                source_url=it.get("buy_url", "") or "",
                source_label=f"{insurer} (private insurance)",
                agent=self.name,
            ))
        return out

    @staticmethod
    def _parse_json_array(text: str) -> list[dict]:
        if not text:
            return []
        # Strip ```json fences and grab the outermost [ ... ].
        cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        m = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def _extract_eligibility(self, message: str) -> dict:
        system = (
            "You extract healthcare eligibility signals from a user's message. "
            "Return the Indian state if mentioned, relevant eligibility tags, and income level. "
            "Tags must only come from the allowed list in the schema."
        )
        try:
            return await self.generate_structured(system, message, ELIGIBILITY_SCHEMA)
        except Exception as e:
            self.logger.warning(f"Eligibility extraction failed, using defaults: {e}")
            return {"state": "", "tags": ["BPL", "low_income"], "income_level": "unknown"}

    async def _rank_and_explain(self, schemes: list[dict], user_message: str) -> list[dict]:
        scheme_summaries = "\n".join(
            f"- id: {s['id']}, name: {s['name']}, beneficiaries: {s['beneficiaries']}"
            for s in schemes
        )
        system = (
            "You are a healthcare scheme advisor for India. "
            "Given a list of government schemes and a user's situation, "
            "rank the top 3 most relevant schemes and explain why each is relevant and how to apply. "
            "Return only schemes from the provided list using their exact IDs."
        )
        prompt = f"User situation: {user_message}\n\nAvailable schemes:\n{scheme_summaries}"
        try:
            return await self.generate_structured(system, prompt, RANK_SCHEMA)
        except Exception as e:
            self.logger.warning(f"Ranking failed, returning all schemes unranked: {e}")
            return [
                {"scheme_id": s["id"], "relevance_reason": s["beneficiaries"], "how_to_apply_summary": s.get("how_to_apply", "")}
                for s in schemes[:3]
            ]
