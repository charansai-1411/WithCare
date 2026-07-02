from app.models.care_plan import CarePlan
from app.models.response_models import SourcedStep
from app.utils.exceptions import GroundingError
from app.utils.logger import get_logger

logger = get_logger(__name__)


def attach_source(step: SourcedStep, doc: dict) -> SourcedStep:
    """
    Pulls source_url from a Firestore doc and attaches it to a step.
    Raises GroundingError if no URL can be found on the doc.
    """
    url = (
        doc.get("source_url")
        or doc.get("application_url")
        or doc.get("website")
        or doc.get("html_link")
    )
    if not url:
        raise GroundingError(f"No source URL found for doc id={doc.get('id', 'unknown')}")

    step.source_url = url
    step.source_label = doc.get("name", url)
    return step


def validate_care_plan(plan: CarePlan) -> None:
    """
    Validates that every step in the care plan has a non-empty source_url.
    Raises GroundingError listing all ungrounded steps.
    """
    ungrounded = [
        f"Step {s.step_number} ({s.agent}): '{s.action}'"
        for s in plan.ordered_steps
        if not s.source_url
    ]
    if ungrounded:
        raise GroundingError(
            f"Care plan has {len(ungrounded)} ungrounded steps: {'; '.join(ungrounded)}"
        )
    logger.info(f"Care plan validated — all {len(plan.ordered_steps)} steps are grounded")


def renumber_steps(steps: list[SourcedStep]) -> list[SourcedStep]:
    """Re-numbers steps sequentially across all agents."""
    for i, step in enumerate(steps):
        step.step_number = i + 1
    return steps
