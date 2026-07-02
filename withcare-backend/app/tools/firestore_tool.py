from google.cloud import firestore

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_db: firestore.Client | None = None


def get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=settings.gcp_project_id, database=settings.firestore_database)
        logger.info(f"Firestore client initialized for project {settings.gcp_project_id}")
    return _db


async def query_schemes(
    tags: list[str] | None = None,
    state: str | None = None,
    limit: int = 6,
) -> list[dict]:
    """
    Returns matching scheme docs from Firestore.
    Filters by state if provided (matches 'national' or exact state).
    Then filters by tags in-memory to avoid composite index requirements.
    """
    try:
        db = get_db()
        ref = db.collection("schemes")
        docs = ref.stream()
        results = []

        for doc in docs:
            data = doc.to_dict()

            # State filter: include if national or matches requested state
            if state:
                eligible_states = data.get("eligible_states", [])
                if "all" not in eligible_states and state.lower() not in [s.lower() for s in eligible_states]:
                    continue

            # Tag filter: include if any requested tag matches doc tags
            if tags:
                doc_tags = data.get("tags", [])
                if not any(t.lower() in [dt.lower() for dt in doc_tags] for t in tags):
                    continue

            results.append(data)

        logger.info(f"query_schemes returned {len(results)} results (state={state}, tags={tags})")
        return results[:limit]

    except Exception as e:
        logger.error(f"query_schemes failed: {e}")
        return []


async def query_facilities(
    city: str | None = None,
    state: str | None = None,
    specialty: str | None = None,
    accepts_scheme: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Returns matching facility docs from Firestore.
    All filtering done in-memory to avoid composite index requirements.
    """
    try:
        db = get_db()
        ref = db.collection("facilities")
        docs = ref.stream()
        results = []

        for doc in docs:
            data = doc.to_dict()

            # City filter — substring match handles "Delhi" matching "New Delhi"
            if city:
                doc_city = data.get("city", "").lower()
                search_city = city.lower()
                if search_city not in doc_city and doc_city not in search_city:
                    continue

            # State filter
            if state and data.get("state", "").lower() != state.lower():
                continue

            # Specialty filter
            if specialty:
                specialties = data.get("specialties", [])
                if specialty.lower() not in [s.lower() for s in specialties]:
                    continue

            # Scheme acceptance filter (e.g., accepts_scheme="pmjay" checks accepts_pmjay=True)
            if accepts_scheme:
                field = f"accepts_{accepts_scheme.lower()}"
                if not data.get(field, False):
                    continue

            results.append(data)

        logger.info(f"query_facilities returned {len(results)} results (city={city}, specialty={specialty})")
        return results[:limit]

    except Exception as e:
        logger.error(f"query_facilities failed: {e}")
        return []


async def get_document(collection: str, doc_id: str) -> dict | None:
    """Direct document fetch by collection and ID."""
    try:
        db = get_db()
        doc = db.collection(collection).document(doc_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error(f"get_document failed for {collection}/{doc_id}: {e}")
        return None
