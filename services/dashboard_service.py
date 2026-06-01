"""Dashboard aggregate service for the Web admin."""
from __future__ import annotations

from typing import Any

from database.connection import get_db
from database.db_keys import get_all_active_keys_with_server
from database.db_payments import get_daily_payments_stats
from database.db_servers import get_all_servers
from database.db_users import get_users_stats
from services.payment_service import get_payment_stats, list_payments
from services.user_service import list_users


def _count_keys(active_only: bool = False) -> int:
    if active_only:
        return len(get_all_active_keys_with_server())
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM vpn_keys").fetchone()
        return int(row["cnt"] if row else 0)


def get_dashboard_summary() -> dict[str, Any]:
    users_stats = get_users_stats()
    servers = get_all_servers()
    payments_today = get_daily_payments_stats()

    return {
        "users_total": users_stats.get("total", 0),
        "users_active": users_stats.get("active", 0),
        "keys_total": _count_keys(active_only=False),
        "keys_active": _count_keys(active_only=True),
        "servers_total": len(servers),
        "servers_active": sum(1 for server in servers if server.get("is_active")),
        "payments_today": payments_today,
        "payments_7_days": get_payment_stats(days=7),
        "payments_30_days": get_payment_stats(days=30),
        "recent_payments": list_payments(limit=10),
        "recent_users": list_users(limit=10),
        "servers": servers,
    }

