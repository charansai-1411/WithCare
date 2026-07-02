"""
Gmail send tool — delivers reminder emails to the target person.

Best-effort: uses the same OAuth token.json. If it lacks the `gmail.send` scope, sending
fails gracefully (the Calendar reminder still reaches the person). To enable email, add
`gmail.send` to the auth scopes and regenerate token.json.
"""
import base64
import os
from email.mime.text import MIMEText

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _gmail_service():
    if not os.path.exists("token.json"):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file("token.json")
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                return None
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.warning(f"gmail service init failed: {e}")
        return None


async def send_email(to: str, subject: str, body: str) -> dict:
    """Send a plain-text email. Returns {ok: bool, error?: str}. Never raises."""
    if not to:
        return {"ok": False, "error": "no recipient"}
    try:
        service = _gmail_service()
        if not service:
            return {"ok": False, "error": "gmail scope not authorized"}
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info(f"reminder email sent to {to}")
        return {"ok": True}
    except Exception as e:
        logger.warning(f"gmail send failed (non-fatal): {e}")
        return {"ok": False, "error": str(e)}
