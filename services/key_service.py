"""VPN key service using existing key and VPN API helpers."""
from __future__ import annotations

from typing import Any, Optional

from database import db_keys
from database.connection import get_db


def list_keys(user_id: Optional[int] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 200))
    safe_offset = max(0, int(offset))
    params: list[Any] = []
    where: list[str] = []

    if user_id is not None:
        where.append("vk.user_id = ?")
        params.append(user_id)
    if search:
        pattern = f"%{search.strip()}%"
        where.append(
            "(vk.panel_email LIKE ? OR vk.client_uuid LIKE ? OR vk.custom_name LIKE ? "
            "OR CAST(u.telegram_id AS TEXT) LIKE ? OR LOWER(COALESCE(u.username, '')) LIKE LOWER(?))"
        )
        params.extend([pattern, pattern, pattern, pattern, pattern])

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    params.extend([safe_limit, safe_offset])

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                vk.*,
                u.telegram_id,
                u.username,
                t.name AS tariff_name,
                s.name AS server_name
            FROM vpn_keys vk
            JOIN users u ON u.id = vk.user_id
            LEFT JOIN tariffs t ON t.id = vk.tariff_id
            LEFT JOIN servers s ON s.id = vk.server_id
            {where_sql}
            ORDER BY vk.created_at DESC, vk.id DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def get_key(key_id: int) -> Optional[dict[str, Any]]:
    return db_keys.get_vpn_key_by_id(key_id)


def extend_key(key_id: int, days: int) -> bool:
    return db_keys.extend_vpn_key(key_id, days)


async def reset_key_traffic(key_id: int) -> bool:
    from bot.services import vpn_api

    db_keys.reset_key_traffic_notification(key_id)
    return await vpn_api.reset_key_traffic_if_active(key_id)


async def sync_key_to_panel(key_id: int) -> dict[str, int]:
    from bot.services import vpn_api

    return await vpn_api.sync_key_to_panel_state(key_id)


def delete_key(key_id: int) -> bool:
    return db_keys.delete_vpn_key(key_id)
