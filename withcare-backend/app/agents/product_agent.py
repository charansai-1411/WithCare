"""
ProductAgent — price-compares a product the user named (medicines by name, health devices like
BP monitors/glucometers, supplements, general health products) across Indian e-commerce and
pharmacy sites (Amazon, Flipkart, PharmEasy, Apollo Pharmacy, MedPlus, Netmeds, 1mg…) using
grounded Google Search. Returns options sorted cheapest → costliest with price, platform and a
buy link. It only compares what the user asked for — it never chooses or doses a medicine.
"""
from app.agents.base_agent import BaseAgent
from app.models.response_models import AgentResult, SourcedStep
from app.services.gemini_service import generate_json_self_correcting
from app.utils.logger import get_logger

logger = get_logger(__name__)

_PHARMACY_HINTS = ("tablet", "capsule", "syrup", "mg", "medicine", "medication", "ointment",
                   "cream", "drops", "injection", "insulin", "inhaler")


class ProductAgent(BaseAgent):
    name = "product_agent"
    description = "Price-compares a named health product/medicine across Indian shopping & pharmacy sites"

    async def run(self, context: dict) -> AgentResult:
        self.logger.info("ProductAgent starting")
        query = (context.get("query") or context.get("user_message") or "").strip()
        location = context.get("location") or "India"
        if not query:
            return AgentResult(agent_name=self.name, steps=[], raw_data=[])

        is_medicine = any(h in query.lower() for h in _PHARMACY_HINTS)

        system = (
            "You are a shopping price-comparison assistant for India. Use Google Search to find the "
            "SAME product the user asked for, listed on reputable Indian sites — Amazon.in, Flipkart, "
            "PharmEasy, Apollo Pharmacy, Tata 1mg, Netmeds, MedPlus. Compare only what they asked "
            "for; do NOT substitute a different medicine or recommend a treatment. Report current "
            "indicative prices in INR and a real product/listing URL for each. Prefer well-reviewed "
            "sellers and in-stock listings."
        )
        prompt = (
            f"Product the user wants to buy: \"{query}\". Location: {location}.\n"
            "Find up to 6 listings for THIS product across different platforms, cheapest first.\n\n"
            "Return ONLY a JSON array, no prose. Each item:\n"
            '{"name": str (product + pack size), "platform": str (store name), '
            '"price_inr": number (numeric INR, no symbols), "price_display": str (e.g. "₹249"), '
            '"url": str (real listing URL), "rating": str (e.g. "4.3★" or ""), '
            '"note": str (one short reason to pick this one, e.g. "lowest price", "fastest delivery", '
            '"trusted pharmacy")}.\n'
            "Use real platform names and plausible official listing URLs. Sort ascending by price_inr."
        )

        def _validate(v):
            if not isinstance(v, list):
                raise ValueError("expected a JSON array of listings")
            if v and not isinstance(v[0], dict):
                raise ValueError("array items must be objects")

        try:
            items = await generate_json_self_correcting(
                system, prompt, validate=_validate, retries=1, grounded=True
            ) or []
        except Exception as e:
            self.logger.warning(f"product search failed (non-critical): {e}")
            return AgentResult(agent_name=self.name, steps=[], raw_data=[])

        # Normalise, drop junk, sort cheapest → costliest.
        cleaned = []
        for it in items:
            if not isinstance(it, dict):
                continue
            name = (it.get("name") or "").strip()
            platform = (it.get("platform") or "").strip()
            if not name or not platform:
                continue
            price = _to_price(it.get("price_inr"))
            cleaned.append({
                "name": name,
                "platform": platform,
                "price_inr": price,
                "price_display": (it.get("price_display") or (f"₹{int(price)}" if price else "See price")).strip(),
                "url": (it.get("url") or "").strip(),
                "rating": (it.get("rating") or "").strip(),
                "note": (it.get("note") or "").strip(),
            })
        cleaned.sort(key=lambda p: (p["price_inr"] is None, p["price_inr"] if p["price_inr"] is not None else 1e12))

        steps: list[SourcedStep] = []
        for i, p in enumerate(cleaned[:6]):
            tag = "Cheapest" if i == 0 and p["price_inr"] is not None else ""
            steps.append(SourcedStep(
                step_number=i + 1,
                action=p["name"],
                detail=p["note"] or "Available online",
                source_url=p["url"],
                source_label=p["platform"],
                agent=self.name,
                meta={
                    "kind": "product",
                    "platform": p["platform"],
                    "price_inr": p["price_inr"],
                    "price_display": p["price_display"],
                    "rating": p["rating"],
                    "tag": tag,
                    "is_medicine": is_medicine,
                },
            ))

        self.logger.info(f"ProductAgent found {len(steps)} listings for '{query}'")
        return AgentResult(agent_name=self.name, steps=steps, raw_data=cleaned)


def _to_price(v) -> float | None:
    """Coerce a price to a float, ignoring symbols/commas. None if not parseable."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("₹", "").replace("Rs", "").replace("INR", "").strip()
    try:
        return float(s)
    except ValueError:
        return None
