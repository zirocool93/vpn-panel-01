"""Diagnostics for configured 3X-UI servers."""
from __future__ import annotations

import asyncio
import json
import socket
import time
from datetime import datetime
from typing import Any, Optional

import aiohttp

from database import db_servers
from database.connection import get_db
from services.security_utils import mask_secret as _mask_secret
from services.security_utils import mask_sensitive_dict


def _vpn_api():
    from bot.services import vpn_api

    return vpn_api


def mask_secret(value: Optional[str]) -> str:
    return _mask_secret(value)


def mask_sensitive_panel_data(data: Any) -> Any:
    return mask_sensitive_dict(data)


def _check(name: str, label: str, status: str, message: str, start: float, details: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "status": status,
        "message": message,
        "details": details or {},
        "duration_ms": int((time.perf_counter() - start) * 1000),
    }


def _summarize_inbound(inbound: dict[str, Any]) -> dict[str, Any]:
    settings = _load_json(inbound.get("settings"), {})
    stream = _load_json(inbound.get("streamSettings"), {})
    clients = settings.get("clients") if isinstance(settings, dict) else []
    if not isinstance(clients, list):
        clients = []
    active_clients = [client for client in clients if isinstance(client, dict) and client.get("enable", True)]
    return {
        "id": inbound.get("id"),
        "remark": inbound.get("remark") or inbound.get("name") or "",
        "protocol": inbound.get("protocol") or "",
        "port": inbound.get("port"),
        "listen": inbound.get("listen") or "",
        "enable": inbound.get("enable", True),
        "clients_count": len(clients),
        "active_clients_count": len(active_clients),
        "up": inbound.get("up") or 0,
        "down": inbound.get("down") or 0,
        "settings_summary": _settings_summary(settings),
        "stream_summary": _stream_summary(stream),
        "settings": mask_sensitive_panel_data(settings),
        "streamSettings": mask_sensitive_panel_data(stream),
        "clients": mask_sensitive_panel_data(clients),
    }


async def diagnose_server(server_id: int) -> dict[str, Any]:
    server = db_servers.get_server_by_id(server_id)
    checks: list[dict[str, Any]] = []
    if not server:
        return {"server": None, "ok": False, "status": "error", "checks": [], "panel": {}, "inbounds": [], "clients_count": 0, "online_clients": [], "last_error": "Server not found", "recent_events": []}

    panel = {
        "version": server.get("panel_version"),
        "api_profile": server.get("panel_api_profile"),
        "checked_at": server.get("panel_checked_at"),
        "has_api_token": bool(server.get("api_token")),
        "api_token_masked": mask_secret(server.get("api_token")),
    }
    inbounds: list[dict[str, Any]] = []
    online_clients: list[Any] = []
    last_error = ""

    start = time.perf_counter()
    checks.append(_check("server_active", "Server active", "ok" if server.get("is_active") else "warning", "Server is active" if server.get("is_active") else "Server is disabled", start))

    start = time.perf_counter()
    try:
        await asyncio.wait_for(asyncio.to_thread(_tcp_connect, server["host"], int(server["port"])), timeout=5)
        checks.append(_check("tcp_connect", "TCP connection", "ok", "TCP port is reachable", start))
    except Exception as exc:
        last_error = str(exc)
        checks.append(_check("tcp_connect", "TCP connection", "error", str(exc), start))
        log_server_diagnostic_event(server_id, "error", "tcp_connect", str(exc))

    start = time.perf_counter()
    http_result = await _http_probe(server)
    checks.append(_check("http_panel", "HTTP panel", "ok" if http_result["ok"] else "warning", http_result["message"], start, http_result))

    vpn_api = _vpn_api()
    client = vpn_api.get_client_from_server_data(server)
    start = time.perf_counter()
    try:
        await client.login()
        checks.append(_check("login", "Authorization", "ok", "Login/API token validation succeeded", start))
        panel.update(
            {
                "version": getattr(client, "panel_version", None) or panel["version"],
                "api_profile": getattr(client, "api_profile", None) or panel["api_profile"],
                "checked_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "has_api_token": bool(getattr(client, "api_token", None)),
                "api_token_masked": mask_secret(getattr(client, "api_token", None)),
            }
        )
    except Exception as exc:
        last_error = str(exc)
        checks.append(_check("login", "Authorization", "error", str(exc), start))
        log_server_diagnostic_event(server_id, "error", "login", str(exc))

    if any(check["name"] == "login" and check["status"] == "ok" for check in checks):
        start = time.perf_counter()
        try:
            raw_inbounds = await client.get_inbounds()
            inbounds = [_summarize_inbound(inbound) for inbound in raw_inbounds]
            checks.append(_check("inbounds", "Inbound list", "ok", f"Loaded {len(inbounds)} inbounds", start))
        except Exception as exc:
            last_error = str(exc)
            checks.append(_check("inbounds", "Inbound list", "error", str(exc), start))
            log_server_diagnostic_event(server_id, "error", "inbounds", str(exc))

        start = time.perf_counter()
        online_result = await get_server_online_clients(server_id)
        online_clients = online_result.get("online_clients", [])
        checks.append(_check("online_clients", "Online clients", online_result.get("status", "unknown"), online_result.get("message", ""), start))

    status = _overall_status(checks)
    return {
        "server": {**server, "password": "********", "api_token": mask_secret(server.get("api_token"))},
        "ok": status == "ok",
        "status": status,
        "checks": checks,
        "panel": panel,
        "inbounds": inbounds,
        "clients_count": sum(inbound["clients_count"] for inbound in inbounds),
        "online_clients": online_clients,
        "last_error": last_error,
        "recent_events": get_recent_server_diagnostic_events(server_id),
    }


async def get_server_inbounds_detailed(server_id: int) -> dict[str, Any]:
    if not db_servers.get_server_by_id(server_id):
        return {"status": "error", "message": "Server not found", "inbounds": []}
    try:
        vpn_api = _vpn_api()
        client = await vpn_api.get_client(server_id)
        inbounds = await client.get_inbounds()
        return {"status": "ok", "message": f"Loaded {len(inbounds)} inbounds", "inbounds": [_summarize_inbound(inbound) for inbound in inbounds]}
    except Exception as exc:
        log_server_diagnostic_event(server_id, "error", "inbounds", str(exc))
        return {"status": "error", "message": str(exc), "inbounds": []}


async def get_server_online_clients(server_id: int) -> dict[str, Any]:
    if not db_servers.get_server_by_id(server_id):
        return {"status": "warning", "message": "Server not found", "online_clients": []}
    try:
        vpn_api = _vpn_api()
        client = await vpn_api.get_client(server_id)
        await client.login()
        profile = await client._ensure_api_profile() if hasattr(client, "_ensure_api_profile") else None
        endpoint = "/panel/api/clients/onlines" if profile == "clients_api" else "/panel/api/inbounds/onlines"
        response = await client._request("POST", endpoint, retry=False, log_error=False)
        rows = response.get("obj") if isinstance(response, dict) else None
        if isinstance(rows, list):
            return {"status": "ok", "message": f"Loaded {len(rows)} online clients", "online_clients": mask_sensitive_panel_data(rows)}
        return {"status": "warning", "message": "This 3X-UI API did not return online clients list.", "online_clients": []}
    except Exception as exc:
        log_server_diagnostic_event(server_id, "warning", "online_clients", str(exc))
        return {"status": "warning", "message": f"Online clients unavailable: {exc}", "online_clients": []}


async def relogin_server(server_id: int) -> dict[str, Any]:
    try:
        _vpn_api().invalidate_client_cache(server_id)
    except Exception:
        pass
    try:
        client = await _vpn_api().get_client(server_id)
        await client.login()
        return {"success": True, "message": "Relogin succeeded", "api_profile": getattr(client, "api_profile", None), "panel_version": getattr(client, "panel_version", None)}
    except Exception as exc:
        log_server_diagnostic_event(server_id, "error", "relogin", str(exc))
        return {"success": False, "message": str(exc)}


def reset_server_api_token(server_id: int) -> dict[str, Any]:
    ok = db_servers.update_server_api_token(server_id, None)
    try:
        _vpn_api().invalidate_client_cache(server_id)
    except Exception:
        pass
    return {"success": ok, "message": "api_token reset" if ok else "Server not found"}


def log_server_diagnostic_event(server_id: int, status: str, check_name: str, message: str, details: Any = None) -> None:
    text_details = json.dumps(mask_sensitive_panel_data(details or {}), ensure_ascii=False, default=str)
    if len(text_details) > 2000:
        text_details = text_details[:2000] + "..."
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO server_diagnostic_log (server_id, status, check_name, message, details) VALUES (?, ?, ?, ?, ?)",
                (server_id, status, check_name, message[:500], text_details),
            )
    except Exception:
        return


def get_recent_server_diagnostic_events(server_id: int, limit: int = 20) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM server_diagnostic_log
            WHERE server_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (server_id, max(1, min(int(limit), 100))),
        ).fetchall()
        return [dict(row) for row in rows]


def _tcp_connect(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=5):
        return


async def _http_probe(server: dict[str, Any]) -> dict[str, Any]:
    base_path = (server.get("web_base_path") or "").strip("/")
    url = f"{server.get('protocol', 'https')}://{server['host']}:{server['port']}" + (f"/{base_path}" if base_path else "")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5), connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.get(url) as response:
                return {"ok": response.status < 500, "message": f"HTTP {response.status}", "url": url, "status_code": response.status}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "url": url}


def _load_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _settings_summary(settings: Any) -> dict[str, Any]:
    if not isinstance(settings, dict):
        return {}
    return {key: settings.get(key) for key in ("method", "network", "security") if key in settings}


def _stream_summary(stream: Any) -> dict[str, Any]:
    if not isinstance(stream, dict):
        return {}
    return {key: stream.get(key) for key in ("network", "security") if key in stream}


def _overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "error" for check in checks):
        return "error"
    if any(check["status"] == "warning" for check in checks):
        return "warning"
    if checks:
        return "ok"
    return "unknown"
