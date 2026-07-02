from abc import ABC, abstractmethod

from app.models.response_models import AgentResult
from app.services.gemini_service import generate_structured, generate_text
from app.utils.logger import get_logger


class BaseAgent(ABC):
    name: str = "base_agent"
    description: str = "Base agent"

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.generate_structured = generate_structured
        self.generate_text = generate_text

    @abstractmethod
    async def run(self, context: dict) -> AgentResult:
        """
        context keys:
          - user_message: str
          - intent: dict (from router)
          - location: str | None
          - family_profile: list[dict]
          - care_plan_steps: list (only for action agent)
        """
