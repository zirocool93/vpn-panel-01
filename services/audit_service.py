"""Audit log service for administrative actions."""
from __future__ import annotations

import json
from typing import Any, Optional

from database.connection import get_db


def _request_meta(request: Any) -> tuple[Optional[str], Optional[str]]:
    if request is None:
        return None, None
    client = getattr(request, "client", None)
    ip_address = getattr(client, "host", None) if client else None
    headers = getattr(request, "headers", {}) or {}
    user_agent = headers.get("user-agent") if hasattr(headers, "get") else None
    return ip_address, user_agent


def _details_to_text(details: Any) -> Optional[str]:
    if details is None:
        return None
    if isinstance(details, str):
        return details
    return json.dumps(details, ensure_ascii=False, default=str)


def log_admin_action(
    admin_user_id: Optional[int],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Any = None,
    request: Any = None,
) -> int:
    """Append an administrative audit event and return its row id."""
    ip_address, user_agent = _request_meta(request)
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO admin_audit_log (
                admin_user_id, action, entity_type, entity_id, details,
                ip_address, user_agent
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                admin_user_id,
                action,
                entity_type,
                str(entity_id) if entity_id is not None else None,
                _details_to_text(details),
                ip_address,
                user_agent,
            ),
        )
        return int(cursor.lastrowid)


def get_audit_log(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """Return recent audit events with admin usernames when available."""
    safe_limit = max(1, min(int(limit), 500))
    safe_offset = max(0, int(offset))
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT
                l.*,
                au.username AS admin_username
            FROM admin_audit_log l
            LEFT JOIN admin_users au ON au.id = l.admin_user_id
            ORDER BY l.created_at DESC, l.id DESC
            LIMIT ? OFFSET ?
            """,
            (safe_limit, safe_offset),
        )
        return [dict(row) for row in cursor.fetchall()]

