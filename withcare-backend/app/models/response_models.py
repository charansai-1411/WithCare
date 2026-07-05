from pydantic import BaseModel


class SourcedStep(BaseModel):
    step_number: int
    action: str
    detail: str
    source_url: str
    source_label: str
    agent: str
    distance_km: float | None = None
    meta: dict | None = None  # extra structured data for rich cards (e.g. product price/tag)


class AgentResult(BaseModel):
    agent_name: str
    steps: list[SourcedStep]
    raw_data: list[dict] = []


class StreamChunk(BaseModel):
    type: str  # "thinking" | "step" | "clarify" | "done" | "error"
    content: str | dict
    agent: str | None = None
