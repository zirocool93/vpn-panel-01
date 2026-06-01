"""Authentication service for Web admin users and sessions."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from passlib.context import CryptContext

from database.connection import get_db
from database.db_settings import get_setting


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_admin_user(username: str, password: str, role: str = "owner") -> int:
    """Create an active Web admin user and return its id."""
    clean_username = username.strip()
    if not clean_username:
        raise ValueError("username must not be empty")
    if not password:
        raise ValueError("password must not be empty")

    password_hash = pwd_context.hash(password)
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO admin_users (username, password_hash, role, is_active)
            VALUES (?, ?, ?, 1)
            """,
            (clean_username, password_hash, role),
        )
        return int(cursor.lastrowid)


def verify_admin_credentials(username: str, password: str) -> Optional[dict[str, Any]]:
    """Return admin user when username/password are valid and active."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM admin_users WHERE username = ? AND is_active = 1",
            (username.strip(),),
        ).fetchone()
    if not row:
        return None
    user = dict(row)
    if not pwd_context.verify(password, user["password_hash"]):
        return None
    return user


def get_admin_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM admin_users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_last_login(user_id: int) -> None:
    with get_db() as conn:
        conn.execute("UPDATE admin_users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))


def create_session(
    admin_user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    lifetime_hours: Optional[int] = None,
) -> dict[str, Any]:
    """Create a persistent Web admin session."""
    if lifetime_hours is None:
        lifetime_hours = int(get_setting("web_session_lifetime_hours", "12") or "12")
    expires_at = datetime.utcnow() + timedelta(hours=max(1, int(lifetime_hours)))
    token = secrets.token_urlsafe(32)
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO admin_sessions (
                admin_user_id, session_token, ip_address, user_agent, expires_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (admin_user_id, token, ip_address, user_agent, expires_at.isoformat(timespec="seconds")),
        )
        session_id = int(cursor.lastrowid)
    return {
        "id": session_id,
        "admin_user_id": admin_user_id,
        "session_token": token,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "expires_at": expires_at.isoformat(timespec="seconds"),
    }


def revoke_session(session_token: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            """
            UPDATE admin_sessions
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE session_token = ? AND revoked_at IS NULL
            """,
            (session_token,),
        )
        return cursor.rowcount > 0


def get_session_by_token(session_token: str) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT s.*, au.username, au.role, au.is_active
            FROM admin_sessions s
            JOIN admin_users au ON au.id = s.admin_user_id
            WHERE s.session_token = ?
              AND s.revoked_at IS NULL
              AND au.is_active = 1
              AND (s.expires_at IS NULL OR s.expires_at > datetime('now'))
            """,
            (session_token,),
        ).fetchone()
        return dict(row) if row else None

