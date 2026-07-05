from pydantic import BaseModel, Field


class FamilyMember(BaseModel):
    id: str = ""          # profile id — keys the knowledge-graph memory
    name: str
    relation: str = ""  # "self" | "parent" | "child" | "spouse" | free text
    kind: str = "person"  # "person" | "pet"
    species: str = ""      # for pets: dog, cat, etc.
    email: str = ""        # Gmail — used to sync appointment to their calendar & share the plan
    age: int | None = None
    gender: str = ""
    weight: float | None = None   # kg — used for diet/workout calorie & load tailoring
    height: float | None = None   # cm — with weight, lets plans reason about BMI
    conditions: str = ""   # known health conditions/problems for tailoring guidance
    notes: str = ""
    calendar_id: str | None = None  # Google Calendar ID; None = caregiver's primary
    consent_given: bool = False


class ConversationTurn(BaseModel):
    role: str          # "user" | "assistant"
    content: str       # plain text of the message


class Coordinates(BaseModel):
    lat: float
    lng: float


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., description="Client-generated UUID for conversation continuity")
    user_id: str = ""     # authenticated user id — keys the knowledge-graph memory
    family_profile: list[FamilyMember] | None = None
    for_member: str | None = None
    location: str | None = None
    coordinates: Coordinates | None = None
    language: str = "en"
    history: list[ConversationTurn] = Field(default_factory=list, description="Previous turns in this conversation")
    attachment_document_ids: list[str] = Field(default_factory=list, description="Reader document ids attached to THIS message — the agent reads their text directly")
    connected_connectors: list[str] = Field(default_factory=list, description="Connectors the user has authorized (e.g. 'calendar','gmail','drive','fit') — gate actions on these")
