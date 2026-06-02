"""CRUD and safety checks for Web admin users."""
from __future__ import annotations

from typing import Any

from database.connection import get_db
from services import admin_permissions_service
from services.auth_service import _hash_password


def list_admin_users(q: str = "", role: str = "", include_inactive: bool = True) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []
    if q.strip():
        where.append("(au.username LIKE ? OR CAST(au.id AS TEXT) = ?)")
        params.extend([f"%{q.strip()}%", q.strip()])
    if role.strip():
        where.append("au.role = ?")
        params.append(role.strip())
    if not include_inactive:
        where.append("au.is_active = 1")
    sql_where = "WHERE " + " AND ".join(where) if where else ""
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                au.id, au.username, au.role, au.is_active, au.created_at, au.last_login_at,
                (SELECT COUNT(*) FROM admin_sessions s
                 WHERE s.admin_user_id = au.id AND s.revoked_at IS NULL
                   AND (s.expires_at IS NULL OR s.expires_at > datetime('now'))) AS active_sessions_count,
                (SELECT COUNT(*) FROM admin_login_attempts la
                 WHERE lower(la.username) = lower(au.username)
                   AND la.success = 0
                   AND la.created_at >= datetime('now', '-24 hours')) AS failed_logins_24h
            FROM admin_users au
            {sql_where}
            ORDER BY au.id
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def get_admin_user(admin_user_id: int) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, role, is_active, created_at, last_login_at FROM admin_users WHERE id = ?",
            (admin_user_id,),
        ).fetchone()
        return dict(row) if row else None


def count_active_owners() -> int:
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM admin_users WHERE role = 'owner' AND is_active = 1").fetchone()
        return int(row["count"] if row else 0)


def create_web_admin(username: str, password: str, role: str, is_active: bool = True, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    clean_username = username.strip()
    clean_role = _validate_role(role)
    if not clean_username:
        raise ValueError("username must not be empty")
    if len(password or "") < 10:
        raise ValueError("password must be at least 10 characters")
    if clean_role == "owner" and not _actor_is_owner(actor):
        raise ValueError("Only owner can create owner")
    password_hash = _hash_password(password)
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO admin_users (username, password_hash, role, is_active)
            VALUES (?, ?, ?, ?)
            """,
            (clean_username, password_hash, clean_role, 1 if is_active else 0),
        )
        admin_user_id = int(cursor.lastrowid)
    return get_admin_user(admin_user_id) or {"id": admin_user_id, "username": clean_username, "role": clean_role, "is_active": int(is_active)}


def update_web_admin(admin_user_id: int, username: str, role: str, is_active: bool, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    current = get_admin_user(admin_user_id)
    if not current:
        raise ValueError("Admin user not found")
    clean_username = username.strip()
    clean_role = _validate_role(role)
    if not clean_username:
        raise ValueError("username must not be empty")
    if current["role"] == "owner" and (clean_role != "owner" or not is_active) and count_active_owners() <= 1:
        raise ValueError("Cannot disable or demote the last active owner")
    if (current["role"] == "owner" or clean_role == "owner") and not _actor_is_owner(actor):
        raise ValueError("Only owner can edit owner access")
    with get_db() as conn:
        conn.execute(
            """
            UPDATE admin_users
            SET username = ?, role = ?, is_active = ?
            WHERE id = ?
            """,
            (clean_username, clean_role, 1 if is_active else 0, admin_user_id),
        )
    if not is_active:
        revoke_admin_sessions(admin_user_id)
    return get_admin_user(admin_user_id) or current


def reset_web_admin_password(admin_user_id: int, new_password: str, revoke_sessions: bool = True) -> dict[str, Any]:
    if len(new_password or "") < 10:
        raise ValueError("password must be at least 10 characters")
    if not get_admin_user(admin_user_id):
        raise ValueError("Admin user not found")
    with get_db() as conn:
        conn.execute("UPDATE admin_users SET password_hash = ? WHERE id = ?", (_hash_password(new_password), admin_user_id))
    revoked = revoke_admin_sessions(admin_user_id)["revoked_sessions_count"] if revoke_sessions else 0
    return {"admin_user_id": admin_user_id, "revoked_sessions_count": revoked}


def disable_web_admin(admin_user_id: int, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    current = get_admin_user(admin_user_id)
    if not current:
        raise ValueError("Admin user not found")
    if current["role"] == "owner" and count_active_owners() <= 1:
        raise ValueError("Cannot disable or demote the last active owner")
    if current["role"] == "owner" and not _actor_is_owner(actor):
        raise ValueError("Only owner can disable owner")
    with get_db() as conn:
        conn.execute("UPDATE admin_users SET is_active = 0 WHERE id = ?", (admin_user_id,))
    revoked = revoke_admin_sessions(admin_user_id)["revoked_sessions_count"]
    return {"admin_user_id": admin_user_id, "revoked_sessions_count": revoked}


def enable_web_admin(admin_user_id: int) -> dict[str, Any]:
    if not get_admin_user(admin_user_id):
        raise ValueError("Admin user not found")
    with get_db() as conn:
        conn.execute("UPDATE admin_users SET is_active = 1 WHERE id = ?", (admin_user_id,))
    return {"admin_user_id": admin_user_id}


def revoke_admin_sessions(admin_user_id: int, except_current_token: str | None = None) -> dict[str, Any]:
    params: list[Any] = [admin_user_id]
    extra = ""
    if except_current_token:
        extra = " AND session_token <> ?"
        params.append(except_current_token)
    with get_db() as conn:
        cursor = conn.execute(
            f"""
            UPDATE admin_sessions
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE admin_user_id = ? AND revoked_at IS NULL {extra}
            """,
            params,
        )
        return {"admin_user_id": admin_user_id, "revoked_sessions_count": cursor.rowcount}


def get_admin_sessions(admin_user_id: int) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, admin_user_id, ip_address, user_agent, created_at, expires_at, revoked_at,
                   CASE WHEN revoked_at IS NULL AND (expires_at IS NULL OR expires_at > datetime('now')) THEN 1 ELSE 0 END AS is_active
            FROM admin_sessions
            WHERE admin_user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 50
            """,
            (admin_user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_admin_login_attempts(username: str, limit: int = 50) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT username, ip_address, user_agent, success, failure_reason, created_at
            FROM admin_login_attempts
            WHERE lower(username) = lower(?)
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (username, max(1, min(int(limit), 200))),
        ).fetchall()
        return [dict(row) for row in rows]


def get_admin_audit_events(admin_user_id: int, limit: int = 100) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM admin_audit_log
            WHERE admin_user_id = ? OR entity_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (admin_user_id, str(admin_user_id), max(1, min(int(limit), 200))),
        ).fetchall()
        return [dict(row) for row in rows]


def role_choices() -> list[dict[str, Any]]:
    return [role for role in admin_permissions_service.list_roles() if role.get("is_active", 1)]


def _validate_role(role: str) -> str:
    clean = (role or "").strip().lower()
    if not clean or not admin_permissions_service.get_role(clean):
        raise ValueError("Unknown role")
    return clean


def _actor_is_owner(actor: dict[str, Any] | None) -> bool:
    return bool(actor and (actor.get("role") or "").lower() == "owner")
