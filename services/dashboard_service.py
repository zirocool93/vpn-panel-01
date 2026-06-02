"""Dashboard aggregate service for the Web admin."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable

from bot.utils import git_utils
from database.connection import get_db
from database.db_keys import get_all_active_keys_with_server
from database.db_payments import get_daily_payments_stats
from database.db_servers import get_all_servers
from database.db_users import get_users_stats
from services.audit_service import get_audit_log
from services.backup_service import list_backups
from services.host_diagnostics_service import run_command_safe
from services.payment_service import get_payment_stats, list_payments
from services.user_service import list_users


def _safe(default: Any, func: Callable[[], Any]) -> Any:
    try:
        return func()
    except Exception:
        return default


def _scalar(sql: str, params: tuple[Any, ...] = (), default: int = 0) -> int:
    try:
        with get_db() as conn:
            row = conn.execute(sql, params).fetchone()
            if not row:
                return default
            return int(row[0] or 0)
    except Exception:
        return default


def _count_keys(active_only: bool = False) -> int:
    if active_only:
        return len(_safe([], get_all_active_keys_with_server))
    return _scalar("SELECT COUNT(*) FROM vpn_keys")


def _expiring_keys(limit: int = 8) -> list[dict[str, Any]]:
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT
                    k.id,
                    k.user_id,
                    k.custom_name,
                    k.expires_at,
                    u.telegram_id,
                    u.username,
                    s.name AS server_name
                FROM vpn_keys k
                LEFT JOIN users u ON u.id = k.user_id
                LEFT JOIN servers s ON s.id = k.server_id
                WHERE k.expires_at IS NOT NULL
                  AND k.expires_at > datetime('now')
                  AND k.expires_at <= datetime('now', '+3 days')
                ORDER BY k.expires_at ASC, k.id ASC
                LIMIT ?
                """,
                (max(1, min(int(limit), 30)),),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def _servers_with_status(servers: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    try:
        with get_db() as conn:
            latest = {
                int(row["server_id"]): dict(row)
                for row in conn.execute(
                    """
                    SELECT l.*
                    FROM server_diagnostic_log l
                    JOIN (
                        SELECT server_id, MAX(id) AS max_id
                        FROM server_diagnostic_log
                        GROUP BY server_id
                    ) x ON x.max_id = l.id
                    """
                ).fetchall()
            }
    except Exception:
        latest = {}

    result: list[dict[str, Any]] = []
    for server in servers[: max(1, min(int(limit), 30))]:
        item = dict(server)
        diagnostic = latest.get(int(item.get("id") or 0), {})
        item["diagnostic_status"] = diagnostic.get("status")
        item["diagnostic_message"] = diagnostic.get("message")
        item["diagnostic_checked_at"] = diagnostic.get("created_at")
        result.append(item)
    return result


def _servers_with_errors() -> int:
    return _scalar(
        """
        SELECT COUNT(*)
        FROM server_diagnostic_log l
        JOIN (
            SELECT server_id, MAX(id) AS max_id
            FROM server_diagnostic_log
            GROUP BY server_id
        ) x ON x.max_id = l.id
        WHERE l.status IN ('error', 'failed', 'danger')
        """
    )


def _service_status(service_name: str) -> dict[str, Any]:
    if os.name == "nt":
        return {"status": "muted", "label": "Недоступно локально", "raw": ""}
    result = run_command_safe(["systemctl", "is-active", service_name], timeout=2)
    value = (result.get("stdout") or result.get("stderr") or "").strip()
    if result.get("ok") and value == "active":
        return {"status": "ok", "label": "active", "raw": value}
    if "not found" in value.lower():
        return {"status": "warning", "label": "unit не найден", "raw": value}
    return {"status": "danger", "label": value or "inactive", "raw": value}


def _sqlite_health() -> dict[str, Any]:
    try:
        with get_db() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        return {"status": "ok" if integrity == "ok" else "danger", "integrity": integrity, "journal_mode": journal_mode}
    except Exception as exc:
        return {"status": "danger", "integrity": str(exc), "journal_mode": ""}


def _health() -> dict[str, Any]:
    sqlite = _sqlite_health()
    bot = _service_status("yadreno-vpn")
    web = _service_status("yadreno-vpn-web")
    backups = _safe([], list_backups)
    statuses = [sqlite.get("status"), bot.get("status"), web.get("status")]
    overall = "danger" if "danger" in statuses else "warning" if "warning" in statuses else "ok"
    return {
        "bot_service": bot,
        "web_service": web,
        "sqlite": sqlite,
        "last_backup": backups[0] if backups else None,
        "status": overall,
    }


def _git() -> dict[str, Any]:
    commit = _safe(None, git_utils.get_current_commit)
    return {
        "branch": _safe(None, git_utils.get_current_branch),
        "commit": commit,
        "commit_short": commit[:8] if commit else None,
    }


def get_dashboard_data() -> dict[str, Any]:
    users_stats = _safe({}, get_users_stats)
    servers = _safe([], get_all_servers)
    payments_today = _safe({}, get_daily_payments_stats)
    payments_7_days = _safe({}, lambda: get_payment_stats(days=7))
    payments_30_days = _safe({}, lambda: get_payment_stats(days=30))
    expiring_items = _expiring_keys()
    data: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "users": {
            "total": int(users_stats.get("total", 0) or 0),
            "active": int(users_stats.get("active", 0) or 0),
            "new_24h": _scalar("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')"),
        },
        "keys": {
            "total": _count_keys(active_only=False),
            "active": _count_keys(active_only=True),
            "expiring_3d": _scalar(
                """
                SELECT COUNT(*)
                FROM vpn_keys
                WHERE expires_at IS NOT NULL
                  AND expires_at > datetime('now')
                  AND expires_at <= datetime('now', '+3 days')
                """
            ),
            "expired": _scalar("SELECT COUNT(*) FROM vpn_keys WHERE expires_at IS NOT NULL AND expires_at <= datetime('now')"),
            "items_expiring": expiring_items,
        },
        "payments": {
            "today": payments_today,
            "last_7_days": payments_7_days,
            "last_30_days": payments_30_days,
            "recent": _safe([], lambda: list_payments(limit=8)),
        },
        "servers": {
            "total": len(servers),
            "active": sum(1 for server in servers if server.get("is_active")),
            "with_errors": _servers_with_errors(),
            "items": _servers_with_status(servers),
        },
        "audit": {"recent": _safe([], lambda: get_audit_log(limit=8))},
        "health": _health(),
        "git": _git(),
        "recent_users": _safe([], lambda: list_users(limit=8)),
    }

    data.update(
        {
            "users_total": data["users"]["total"],
            "users_active": data["users"]["active"],
            "keys_total": data["keys"]["total"],
            "keys_active": data["keys"]["active"],
            "servers_total": data["servers"]["total"],
            "servers_active": data["servers"]["active"],
            "payments_today": payments_today,
            "payments_7_days": payments_7_days,
            "payments_30_days": payments_30_days,
            "recent_payments": data["payments"]["recent"],
            "servers_legacy": servers,
        }
    )
    return data


def get_dashboard_summary() -> dict[str, Any]:
    return get_dashboard_data()
