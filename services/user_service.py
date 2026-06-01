"""User service backed by existing user database helpers."""
from __future__ import annotations

from typing import Any, Optional

from database import db_users
from database.connection import get_db


def list_users(search: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 200))
    safe_offset = max(0, int(offset))
    if search:
        pattern = f"%{search.strip().lstrip('@')}%"
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM users
                WHERE CAST(telegram_id AS TEXT) LIKE ?
                   OR LOWER(COALESCE(username, '')) LIKE LOWER(?)
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (pattern, pattern, safe_limit, safe_offset),
            ).fetchall()
            return [dict(row) for row in rows]

    users, _total = db_users.get_all_users_paginated(offset=safe_offset, limit=safe_limit, filter_type="all")
    return users


def get_user(user_id: int) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_telegram_id(telegram_id: int) -> Optional[dict[str, Any]]:
    return db_users.get_user_by_telegram_id(telegram_id)


def update_user_balance(user_id: int, amount_delta_cents: int) -> bool:
    if amount_delta_cents >= 0:
        return db_users.add_to_balance(user_id, amount_delta_cents)
    return db_users.deduct_from_balance(user_id, abs(amount_delta_cents))


def ban_user(user_id: int) -> Optional[bool]:
    user = get_user(user_id)
    if not user:
        return None
    if user.get("is_banned"):
        return True
    return db_users.toggle_user_ban(user["telegram_id"])


def unban_user(user_id: int) -> Optional[bool]:
    user = get_user(user_id)
    if not user:
        return None
    if not user.get("is_banned"):
        return False
    toggled = db_users.toggle_user_ban(user["telegram_id"])
    return False if toggled is False else toggled

