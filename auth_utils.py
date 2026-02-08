"""
Authentication utilities for Presina.
Handles guest sessions and token resolution for sockets and API.
"""
import secrets
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Union

from models.user import User

DEFAULT_AVATAR_URL = "/static/img/logo.png"
GUEST_SESSION_DAYS = 7

# In-memory guest sessions: token -> session data
_guest_sessions: Dict[str, dict] = {}
_last_guest_cleanup = 0.0
_GUEST_CLEANUP_INTERVAL = 300  # cleanup every 5 minutes


def _cleanup_expired_guests():
    """Remove expired guest sessions to prevent memory leaks."""
    global _last_guest_cleanup
    now = time.time()
    if now - _last_guest_cleanup < _GUEST_CLEANUP_INTERVAL:
        return
    _last_guest_cleanup = now
    expired = [t for t, s in _guest_sessions.items() if s.get('expires_at', 0) < now]
    for t in expired:
        _guest_sessions.pop(t, None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_display_name(name: Optional[str], max_len: int = 20) -> Optional[str]:
    if not name or not isinstance(name, str):
        return None
    name = name.strip()
    if not name:
        return None
    return name[:max_len]


def create_guest_session(display_name: Optional[str] = None) -> Tuple[str, dict]:
    """Create a guest session and return (token, user_dict)."""
    token = secrets.token_urlsafe(32)
    suffix = secrets.token_hex(2)
    guest_username = f"guest_{suffix}"
    display_name = _sanitize_display_name(display_name) or f"Ospite {suffix.upper()}"
    now_iso = _now_iso()
    expires_at = time.time() + (GUEST_SESSION_DAYS * 24 * 60 * 60)

    guest_user = {
        "id": None,
        "username": guest_username,
        "display_name": display_name,
        "avatar": DEFAULT_AVATAR_URL,
        "created_at": now_iso,
        "last_login": now_iso,
        "is_guest": True
    }

    _guest_sessions[token] = {
        **guest_user,
        "expires_at": expires_at
    }
    return token, guest_user


def _get_guest_by_token(token: str) -> Optional[dict]:
    session = _guest_sessions.get(token)
    if not session:
        return None
    if session.get("expires_at", 0) < time.time():
        _guest_sessions.pop(token, None)
        return None
    return session


def resolve_token(token: Optional[str]) -> Tuple[Optional[Union[User, dict]], bool]:
    """
    Resolve token to a user.
    Returns (user_or_dict, is_guest).
    """
    _cleanup_expired_guests()
    if not token:
        return None, False

    guest = _get_guest_by_token(token)
    if guest:
        return guest, True

    user = User.get_by_token(token)
    if user:
        return user, False

    return None, False


def serialize_user(user: Union[User, dict], is_guest: bool) -> dict:
    """Return a JSON-serializable user dict."""
    if is_guest:
        data = {
            "id": None,
            "username": user.get("username"),
            "display_name": user.get("display_name"),
            "avatar": user.get("avatar") or DEFAULT_AVATAR_URL,
            "created_at": user.get("created_at"),
            "last_login": user.get("last_login"),
            "is_guest": True
        }
        return data
    data = user.to_dict()
    data["is_guest"] = False
    if not data.get("avatar"):
        data["avatar"] = DEFAULT_AVATAR_URL
    return data


def build_auth_payload(user: Union[User, dict], is_guest: bool) -> dict:
    """Build a lightweight auth payload for sockets."""
    if is_guest:
        return {
            "user_id": None,
            "username": user.get("username"),
            "display_name": user.get("display_name"),
            "is_guest": True
        }
    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "is_guest": False
    }


def invalidate_token(token: Optional[str]) -> bool:
    """Invalidate a token (guest or user)."""
    if not token:
        return False
    if token in _guest_sessions:
        _guest_sessions.pop(token, None)
        return True
    user = User.get_by_token(token)
    if user:
        user.logout()
        return True
    return False
