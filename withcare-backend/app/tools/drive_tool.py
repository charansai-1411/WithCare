"""
Drive tool — save care plans as Google Docs and share with family members.
Uses Google Drive API v3 with OAuth credentials (token.json).
"""
import json
from app.utils.exceptions import WithCareError
from app.utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]


def _creds(access_token, import_creds, import_request):
    """Build credentials: from the user's OAuth access token if given, else token.json."""
    if access_token:
        return import_creds(token=access_token)  # user's own account
    import os
    token_path = os.environ.get("WITHCARE_TOKEN_PATH", "token.json")
    if not os.path.exists(token_path):
        raise WithCareError(
            "No token.json found. Run scripts/setup_calendar_auth.py to generate it."
        )
    creds = import_creds.from_authorized_user_file(token_path, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(import_request())
    return creds


def get_drive_service(access_token: str | None = None):
    """Returns Google Drive API service — the user's account if access_token given."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = _creds(access_token, Credentials, Request)
    return build("drive", "v3", credentials=creds)


def get_docs_service(access_token: str | None = None):
    """Returns Google Docs API service — the user's account if access_token given."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = _creds(access_token, Credentials, Request)
    return build("docs", "v1", credentials=creds)


async def save_care_plan_to_drive(care_plan: dict, access_token: str | None = None) -> dict:
    """
    Creates a Google Doc with the care plan and returns its URL.
    Returns {"doc_id": str, "doc_url": str}
    """
    try:
        drive = get_drive_service(access_token)
        docs = get_docs_service(access_token)

        title = f"WithCare Plan — {care_plan.get('for_member', 'Self')} — {care_plan.get('generated_at', '')[:10]}"

        # Create blank doc
        doc = docs.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        # Build content as plain text requests
        lines = [
            f"{title}\n\n",
            f"Summary: {care_plan.get('intent_summary', '')}\n\n",
            "YOUR ACTION PLAN\n\n",
        ]
        for step in care_plan.get("ordered_steps", []):
            lines.append(
                f"Step {step['step_number']}: {step['action']}\n"
                f"{step['detail']}\n"
                f"Source: {step['source_url']}\n\n"
            )
        lines.append(f"\n{care_plan.get('disclaimer', '')}")

        full_text = "".join(lines)

        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": full_text}}]},
        ).execute()

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        logger.info(f"Care plan saved to Drive: {doc_url}")
        return {"doc_id": doc_id, "doc_url": doc_url}

    except Exception as e:
        logger.error(f"save_care_plan_to_drive failed: {e}")
        return {}


async def share_doc_with_email(doc_id: str, email: str, role: str = "reader", access_token: str | None = None) -> bool:
    """
    Share a Drive doc with a family member by email.
    role: 'reader' | 'commenter' | 'writer'
    """
    try:
        drive = get_drive_service(access_token)
        drive.permissions().create(
            fileId=doc_id,
            body={"type": "user", "role": role, "emailAddress": email},
            sendNotificationEmail=True,
        ).execute()
        logger.info(f"Doc {doc_id} shared with {email} as {role}")
        return True
    except Exception as e:
        logger.error(f"share_doc_with_email failed: {e}")
        return False
