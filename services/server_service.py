"""Server service backed by existing database and VPN API helpers."""
from __future__ import annotations

from typing import Any, Optional

from database import db_servers
from bot.services.vpn_api import test_server_connection as _test_server_connection


def list_servers() -> list[dict[str, Any]]:
    return db_servers.get_all_servers()


def get_server(server_id: int) -> Optional[dict[str, Any]]:
    return db_servers.get_server_by_id(server_id)


def create_server(
    name: str,
    host: str,
    port: int,
    web_base_path: str,
    login: str,
    password: str,
    protocol: str = "https",
    group_id: int = 1,
) -> int:
    return db_servers.add_server(name, host, port, web_base_path, login, password, protocol, group_id)


def update_server(server_id: int, **fields: Any) -> bool:
    return db_servers.update_server(server_id, **fields)


def delete_server(server_id: int) -> bool:
    return db_servers.delete_server(server_id)


def toggle_server_active(server_id: int) -> Optional[bool]:
    return db_servers.toggle_server_active(server_id)


async def test_server_connection(server_id: int) -> dict[str, Any]:
    server = get_server(server_id)
    if not server:
        return {"success": False, "message": "Сервер не найден", "stats": None}
    return await _test_server_connection(server)

