"""
Multi-task conversation models (architecture v3).

Facts carry value + confidence + who-set-it, so the system can distinguish
"we don't know yet" from "user explicitly decided" and "GPS failed" from "not asked".
All workflow decisions are made deterministically over these models — the LLM only
extracts (Segmenter) and phrases (Writer).
"""
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.response_models import SourcedStep


class TaskIntent(str, Enum):
    FIND_SCHEME = "find_government_schemes"
    FIND_FACILITY = "find_facilities"
    SCHEDULE = "schedule_appointment"


class TaskStatus(str, Enum):
    COLLECTING = "collecting"                       # missing a required fact
    READY = "ready"                                 # required facts filled, not executed
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # SCHEDULE only — waits for user "yes"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Fact(BaseModel):
    value: Optional[str] = None
    confidence: Literal["high", "low"] = "high"
    # value + user_specified are set by the Segmenter (reading what the user said).
    # confidence for `location` is set by the TaskStateManager based on whether GPS
    # coordinates were present — the Segmenter cannot know GPS status.
    user_specified: bool = False


class RawTask(BaseModel):
    """One task detected by the Segmenter in a single message."""
    intent: TaskIntent
    raw_span: str = ""
    refers_to_existing_task: Optional[str] = None
    depends_on_new_task: bool = False
    slots: dict = Field(default_factory=dict)
    preferences: dict = Field(default_factory=dict)
    user_specified: dict = Field(default_factory=dict)  # per-key bool


# ── The deterministic rulebook ──────────────────────────────────────────────────
REQUIRED_FACTS: dict[TaskIntent, list[str]] = {
    TaskIntent.FIND_SCHEME:   [],  # coverage is broadly searchable; refine via follow-ups, don't gate
    TaskIntent.FIND_FACILITY: ["condition", "location"],
    TaskIntent.SCHEDULE:      ["procedure", "date"],   # hospital is dependency-injected
}

PREFERENCE_TRIGGERS: dict[TaskIntent, list[str]] = {
    TaskIntent.FIND_FACILITY: ["facility_ranking"],   # nearest vs. highest-rated
    TaskIntent.SCHEDULE:      ["time_of_day"],         # soft only
}

PREFERENCE_KEYS = {"facility_ranking", "time_of_day", "coverage_scope"}

# Deterministic follow-ups offered after a coverage (scheme/insurance) search completes.
# The Planner offers the ones not yet resolved; the Writer phrases them.
SCHEME_FOLLOWUPS = ["eligibility_details", "coverage_scope", "next_step"]
# Facts that mean the user has given eligibility info (so we stop offering that follow-up).
ELIGIBILITY_FACT_KEYS = {"occupation", "annual_income", "social_category"}


class TaskFrame(BaseModel):
    task_id: str
    intent: TaskIntent
    goal: str = ""
    facts: dict[str, Fact] = Field(default_factory=dict)
    preferences: dict[str, Fact] = Field(default_factory=dict)
    depends_on: Optional[str] = None
    status: TaskStatus = TaskStatus.COLLECTING
    just_learned: dict[str, str] = Field(default_factory=dict)  # reset+refilled each turn
    results: list[SourcedStep] = Field(default_factory=list)
    created_turn: int = 0
    updated_turn: int = 0

    @property
    def missing_required(self) -> list[str]:
        required = REQUIRED_FACTS[self.intent]
        return [f for f in required if not self.facts.get(f) or not self.facts[f].value]


class SessionContext(BaseModel):
    """Facts that outlive any single task frame — inherited by new frames on creation."""
    known_location: Optional[Fact] = None
    known_coordinates: Optional[dict] = None
    known_for_member: Optional[Fact] = None
    family_profile: list = Field(default_factory=list)


class CommunicationPlan(BaseModel):
    """Output of the deterministic Planner. The Writer LLM only phrases this."""
    report_results: list[str] = Field(default_factory=list)        # task_ids to report
    acknowledge: list[str] = Field(default_factory=list)            # "task_id.fact"
    ask: list[str] = Field(default_factory=list)                    # "task_id.fact"
    offer_preference: list[str] = Field(default_factory=list)       # "task_id.pref"
    offer_followups: list[str] = Field(default_factory=list)        # "task_id.followup"
    confirm: list[str] = Field(default_factory=list)               # task_ids
    low_confidence_flags: list[str] = Field(default_factory=list)   # "task_id.fact"

    @property
    def is_empty(self) -> bool:
        return not any([
            self.report_results, self.acknowledge, self.ask,
            self.offer_preference, self.offer_followups, self.confirm, self.low_confidence_flags,
        ])


class TaskResult(BaseModel):
    task_id: str
    intent: TaskIntent
    status: TaskStatus
    depends_on: Optional[str] = None
    steps: list[SourcedStep] = Field(default_factory=list)
    error: Optional[str] = None
