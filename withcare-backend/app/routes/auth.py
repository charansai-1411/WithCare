"""
Authentication routes.

- POST /api/auth/google — verify a Google Sign-In ID token, upsert the user, return it.
- POST /api/auth/dev    — dev-only fallback login (used until a Web OAuth Client ID is set).
- GET  /api/auth/me     — fetch the current user by id.

Identity is the user id (returned here); the rest of the API keeps using the
`x-user-id` header, so conversations/profiles tie to the authenticated account.
"""
import uuid

from fastapi import APIRouter, Header, HTTPException
from typing import Optional

from app.config import settings
from app.db.database import get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _user_dict(row) -> dict:
    d = dict(row)
    d.pop("google_sub", None)  # don't leak the raw subject id
    return d


def _upsert_google_user(sub: str, email: str, name: str, picture: str) -> dict:
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()
    if row:
        db.execute(
            "UPDATE users SET name=?, email=?, picture=? WHERE id=?",
            (name, email, picture, row["id"]),
        )
        uid = row["id"]
    else:
        uid = "u-" + uuid.uuid4().hex[:12]
        db.execute(
            "INSERT INTO users(id, name, email, picture, google_sub, auth_provider) "
            "VALUES(?,?,?,?,?, 'google')",
            (uid, name or "You", email, picture, sub),
        )
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return _user_dict(row)


@router.post("/google")
def google_login(body: dict):
    token = body.get("credential") or body.get("id_token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing Google credential")

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        # Verify signature + issuer always; check audience only if a client id is configured.
        audience = settings.google_oauth_client_id or None
        info = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), audience, clock_skew_in_seconds=10
        )
        if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise ValueError("Wrong issuer")
    except Exception as e:
        logger.warning(f"Google token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google sign-in token")

    user = _upsert_google_user(
        sub=info["sub"],
        email=info.get("email", ""),
        name=info.get("name") or info.get("given_name") or "You",
        picture=info.get("picture", ""),
    )
    return user


@router.post("/dev")
def dev_login(body: dict):
    """Fallback login for local testing before a Web OAuth Client ID exists."""
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Dev login disabled in production")
    name = (body.get("name") or "Dev User").strip()
    email = (body.get("email") or "dev@withcare.local").strip()

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email=? AND auth_provider='dev'", (email,)).fetchone()
    if row:
        uid = row["id"]
    else:
        uid = "u-" + uuid.uuid4().hex[:12]
        db.execute(
            "INSERT INTO users(id, name, email, auth_provider) VALUES(?,?,?, 'dev')",
            (uid, name, email),
        )
        db.commit()
    row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return _user_dict(row)


@router.get("/me")
def me(x_user_id: Optional[str] = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Not signed in")
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (x_user_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_dict(row)


@router.get("/config")
def auth_config():
    """Frontend asks whether real Google login is available (client id configured)."""
    return {
        "google_client_id": settings.google_oauth_client_id,
        "google_enabled": bool(settings.google_oauth_client_id),
        "dev_login_enabled": settings.environment != "production",
    }
