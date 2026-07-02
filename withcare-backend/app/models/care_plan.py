from datetime import datetime

from pydantic import BaseModel

from app.models.response_models import SourcedStep


class CarePlan(BaseModel):
    session_id: str
    for_member: str
    intent_summary: str
    ordered_steps: list[SourcedStep]
    calendar_event_id: str | None = None
    calendar_event_url: str | None = None
    disclaimer: str = (
        "WithCare provides navigation assistance only. "
        "This is not medical advice. Always consult a licensed healthcare professional."
    )
    generated_at: datetime
