"""VPN key service using existing key and VPN API helpers."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from database import db_keys, db_servers, db_tariffs
from database.connection import get_db
from bot.utils.panel_email import get_panel_email_prefix


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


def get_key_full(key_id: int) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                vk.*,
                u.telegram_id,
                u.username,
                u.is_banned,
                t.name AS tariff_name,
                t.duration_days,
                t.price_rub,
                t.price_cents,
                t.price_stars,
                t.traffic_limit_gb,
                t.max_ips,
                s.name AS server_name,
                s.host,
                s.protocol,
                s.is_active AS server_active,
                tg.name AS group_name
            FROM vpn_keys vk
            JOIN users u ON u.id = vk.user_id
            LEFT JOIN tariffs t ON t.id = vk.tariff_id
            LEFT JOIN servers s ON s.id = vk.server_id
            LEFT JOIN server_groups sg ON sg.server_id = s.id
            LEFT JOIN tariff_groups tg ON tg.id = sg.group_id
            WHERE vk.id = ?
            """,
            (key_id,),
        ).fetchone()
        return dict(row) if row else None


def get_key_create_options(user_id: Optional[int] = None) -> dict[str, list[dict[str, Any]]]:
    with get_db() as conn:
        if user_id:
            user_rows = conn.execute(
                "SELECT * FROM users WHERE id = ? AND is_banned = 0",
                (user_id,),
            ).fetchall()
        else:
            user_rows = conn.execute(
                """
                SELECT *
                FROM users
                WHERE is_banned = 0
                ORDER BY id DESC
                LIMIT 200
                """
            ).fetchall()
        group_rows = conn.execute("SELECT * FROM tariff_groups ORDER BY sort_order, id").fetchall()
    return {
        "users": [dict(row) for row in user_rows],
        "tariffs": db_tariffs.get_all_tariffs(include_hidden=False),
        "servers": db_servers.get_active_servers(),
        "groups": [dict(row) for row in group_rows],
    }


async def get_server_inbounds(server_id: int) -> list[dict[str, Any]]:
    from bot.services import vpn_api

    server = db_servers.get_server_by_id(server_id)
    if not server or not server.get("is_active"):
        return []
    client = await vpn_api.get_client(server_id)
    return await client.get_inbounds()


def extend_key(key_id: int, days: int) -> bool:
    return db_keys.extend_vpn_key(key_id, days)


def _traffic_limit_bytes(tariff: dict[str, Any], override_gb: Optional[int] = None) -> int:
    gb = tariff.get("traffic_limit_gb") or 0
    if override_gb is not None:
        gb = max(0, int(override_gb))
    return int(gb) * 1024**3


def _select_server(tariff: dict[str, Any], server_id: Optional[int]) -> Optional[dict[str, Any]]:
    if server_id:
        server = db_servers.get_server_by_id(server_id)
        return server if server and server.get("is_active") else None

    group_id = tariff.get("group_id")
    with get_db() as conn:
        row = None
        if group_id:
            row = conn.execute(
                """
                SELECT s.*
                FROM servers s
                JOIN server_groups sg ON sg.server_id = s.id
                WHERE s.is_active = 1 AND sg.group_id = ?
                ORDER BY s.id
                LIMIT 1
                """,
                (group_id,),
            ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM servers WHERE is_active = 1 ORDER BY id LIMIT 1"
            ).fetchone()
        return dict(row) if row else None


def _generate_panel_email(user: dict[str, Any]) -> str:
    return f"{get_panel_email_prefix(user)}{uuid.uuid4().hex[:5]}"


async def _first_inbound_id(server_id: int) -> Optional[int]:
    inbounds = await get_server_inbounds(server_id)
    if not inbounds:
        return None
    return min(int(inbound["id"]) for inbound in inbounds if "id" in inbound)


async def create_key_for_user(
    user_id: int,
    tariff_id: int,
    server_id: Optional[int] = None,
    inbound_id: Optional[int] = None,
    custom_name: Optional[str] = None,
    starts_now: bool = True,
    expires_at: Optional[str] = None,
    traffic_limit_gb: Optional[int] = None,
    max_ips: Optional[int] = None,
    create_on_panel: bool = True,
) -> dict[str, Any]:
    with get_db() as conn:
        user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user_row:
        return {"success": False, "key_id": None, "message": "User not found", "panel_result": None}
    user = dict(user_row)
    if user.get("is_banned"):
        return {"success": False, "key_id": None, "message": "User is banned", "panel_result": None}

    tariff = db_tariffs.get_tariff_by_id(tariff_id)
    if not tariff or not tariff.get("is_active"):
        return {"success": False, "key_id": None, "message": "Active tariff not found", "panel_result": None}

    days = int(tariff.get("duration_days") or 0)
    if days <= 0 and not expires_at:
        return {"success": False, "key_id": None, "message": "Tariff duration must be positive", "panel_result": None}

    server = _select_server(tariff, server_id)
    if create_on_panel and not server:
        return {"success": False, "key_id": None, "message": "Active server not found", "panel_result": None}

    traffic_limit = _traffic_limit_bytes(tariff, traffic_limit_gb)
    panel_result: Optional[dict[str, Any]] = None

    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).replace(tzinfo=None)
            days = max(1, (expires_dt - datetime.utcnow()).days)
        except ValueError:
            return {"success": False, "key_id": None, "message": "Invalid expires_at", "panel_result": None}

    if not create_on_panel:
        key_id = db_keys.create_initial_vpn_key(user_id, tariff_id, days, traffic_limit)
        if custom_name:
            with get_db() as conn:
                conn.execute("UPDATE vpn_keys SET custom_name = ? WHERE id = ?", (custom_name, key_id))
        return {"success": True, "key_id": key_id, "message": "DB key created", "panel_result": None}

    from bot.services import vpn_api

    assert server is not None
    email = _generate_panel_email(user)
    subscription_mode = vpn_api.is_subscription_mode() and inbound_id is None

    try:
        if subscription_mode:
            selected_inbound_id = await _first_inbound_id(server["id"])
            if selected_inbound_id is None:
                return {"success": False, "key_id": None, "message": "Server has no inbounds", "panel_result": None}
            sub_id = uuid.uuid4().hex
            key_id = db_keys.create_vpn_key_subscription_admin(
                user_id=user_id,
                server_id=server["id"],
                tariff_id=tariff_id,
                panel_inbound_id=selected_inbound_id,
                panel_email=email,
                client_uuid=uuid.uuid4().hex,
                sub_id=sub_id,
                days=days,
                traffic_limit=traffic_limit,
            )
            panel_result = await vpn_api.sync_key_to_panel_state(key_id)
        else:
            selected_inbound_id = inbound_id or await _first_inbound_id(server["id"])
            if selected_inbound_id is None:
                return {"success": False, "key_id": None, "message": "Server has no inbounds", "panel_result": None}
            client = vpn_api.get_client_from_server_data(server)
            flow = await client.get_inbound_flow(int(selected_inbound_id))
            add_result = await client.add_client(
                inbound_id=int(selected_inbound_id),
                email=email,
                total_gb=max(0, int(traffic_limit / 1024**3)),
                expire_days=days,
                limit_ip=int(max_ips or tariff.get("max_ips") or 1),
                tg_id=str(user.get("telegram_id") or ""),
                flow=flow,
            )
            key_id = db_keys.create_vpn_key_admin(
                user_id=user_id,
                server_id=server["id"],
                tariff_id=tariff_id,
                panel_inbound_id=int(selected_inbound_id),
                panel_email=email,
                client_uuid=add_result["uuid"],
                days=days,
                traffic_limit=traffic_limit,
            )
            panel_result = {"ok": 1, "created": 1, "result": add_result}
    except Exception as exc:
        return {"success": False, "key_id": None, "message": str(exc), "panel_result": panel_result}

    if custom_name:
        with get_db() as conn:
            conn.execute("UPDATE vpn_keys SET custom_name = ? WHERE id = ?", (custom_name, key_id))

    return {"success": True, "key_id": key_id, "message": "Key created", "panel_result": panel_result}


def change_key_tariff(key_id: int, tariff_id: int, apply_limits: bool = True) -> dict[str, Any]:
    key = get_key(key_id)
    tariff = db_tariffs.get_tariff_by_id(tariff_id)
    if not key:
        return {"success": False, "message": "Key not found"}
    if not tariff:
        return {"success": False, "message": "Tariff not found"}

    old_values = {"tariff_id": key.get("tariff_id"), "traffic_limit": key.get("traffic_limit")}
    traffic_limit = _traffic_limit_bytes(tariff)
    with get_db() as conn:
        if apply_limits:
            conn.execute(
                "UPDATE vpn_keys SET tariff_id = ?, traffic_limit = ? WHERE id = ?",
                (tariff_id, traffic_limit, key_id),
            )
        else:
            conn.execute("UPDATE vpn_keys SET tariff_id = ? WHERE id = ?", (tariff_id, key_id))
    return {
        "success": True,
        "message": "Tariff changed",
        "old_values": old_values,
        "new_values": {"tariff_id": tariff_id, "traffic_limit": traffic_limit if apply_limits else key.get("traffic_limit")},
    }


async def extend_key_by_tariff(key_id: int, tariff_id: int, update_tariff: bool = False) -> dict[str, Any]:
    tariff = db_tariffs.get_tariff_by_id(tariff_id)
    if not tariff:
        return {"success": False, "message": "Tariff not found", "panel_result": None}
    days = int(tariff.get("duration_days") or 0)
    if days <= 0:
        return {"success": False, "message": "Tariff duration must be positive", "panel_result": None}
    if update_tariff:
        change = change_key_tariff(key_id, tariff_id, apply_limits=True)
        if not change.get("success"):
            return {"success": False, "message": change.get("message", "Tariff change failed"), "panel_result": None}
    success = extend_key(key_id, days)
    panel_result = await sync_key_to_panel(key_id) if success else None
    return {"success": success, "message": "Key extended" if success else "Key not found", "days": days, "panel_result": panel_result}


async def assign_tariff_to_user(
    user_id: int,
    tariff_id: int,
    action: str,
    key_id: Optional[int] = None,
    server_id: Optional[int] = None,
    inbound_id: Optional[int] = None,
    custom_name: Optional[str] = None,
) -> dict[str, Any]:
    if action == "create_key":
        return await create_key_for_user(user_id, tariff_id, server_id=server_id, inbound_id=inbound_id, custom_name=custom_name)
    if action == "create_db_only":
        return await create_key_for_user(user_id, tariff_id, server_id=server_id, inbound_id=inbound_id, custom_name=custom_name, create_on_panel=False)
    if not key_id:
        return {"success": False, "message": "key_id is required", "key_id": None}
    if action == "extend_key":
        result = await extend_key_by_tariff(key_id, tariff_id, update_tariff=True)
        result["key_id"] = key_id
        return result
    if action == "change_key_tariff":
        result = change_key_tariff(key_id, tariff_id, apply_limits=True)
        if result.get("success"):
            result["panel_result"] = await sync_key_to_panel(key_id)
        result["key_id"] = key_id
        return result
    return {"success": False, "message": "Unsupported action", "key_id": key_id}


async def regenerate_key_links(key_id: int) -> dict[str, Any]:
    from bot.utils.key_generator import generate_link

    key = get_key_full(key_id)
    if not key:
        return {"success": False, "message": "Key not found", "subscription_url": None, "client_link": None}

    try:
        from bot.services import vpn_api
    except Exception as exc:
        return {
            "success": False,
            "message": f"Panel helpers unavailable: {exc}",
            "subscription_url": None,
            "client_link": None,
            "key": key,
        }

    subscription_url = await vpn_api.get_subscription_url_for_key(key)
    client_link = None
    if key.get("server_id") and key.get("panel_email"):
        try:
            client = await vpn_api.get_client(key["server_id"])
            config = await client.get_client_config(key["panel_email"])
            if config:
                client_link = generate_link(config)
        except Exception:
            client_link = None
    return {
        "success": bool(subscription_url or client_link),
        "message": "Links generated" if (subscription_url or client_link) else "Links unavailable",
        "subscription_url": subscription_url,
        "client_link": client_link,
        "key": key,
    }


async def reset_key_traffic(key_id: int) -> bool:
    from bot.services import vpn_api

    db_keys.reset_key_traffic_notification(key_id)
    return await vpn_api.reset_key_traffic_if_active(key_id)


async def sync_key_to_panel(key_id: int) -> dict[str, int]:
    from bot.services import vpn_api

    return await vpn_api.sync_key_to_panel_state(key_id)


def delete_key(key_id: int) -> bool:
    return db_keys.delete_vpn_key(key_id)
