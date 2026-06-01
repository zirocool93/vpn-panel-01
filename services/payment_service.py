"""Payment read service for Web admin."""
from __future__ import annotations

from typing import Any, Optional

from database.connection import get_db
from database.db_payments import get_daily_payments_stats


def list_payments(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    payment_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 200))
    safe_offset = max(0, int(offset))
    where: list[str] = []
    params: list[Any] = []

    if user_id is not None:
        where.append("p.user_id = ?")
        params.append(user_id)
    if status:
        where.append("p.status = ?")
        params.append(status)
    if payment_type:
        where.append("p.payment_type = ?")
        params.append(payment_type)
    if date_from:
        where.append("p.paid_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("p.paid_at <= ?")
        params.append(date_to)

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    params.extend([safe_limit, safe_offset])

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                p.*,
                u.telegram_id,
                u.username,
                t.name AS tariff_name,
                t.price_rub
            FROM payments p
            JOIN users u ON u.id = p.user_id
            LEFT JOIN tariffs t ON t.id = p.tariff_id
            {where_sql}
            ORDER BY p.paid_at DESC, p.id DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def get_payment(payment_id: int) -> Optional[dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                p.*,
                u.telegram_id,
                u.username,
                t.name AS tariff_name,
                t.price_rub
            FROM payments p
            JOIN users u ON u.id = p.user_id
            LEFT JOIN tariffs t ON t.id = p.tariff_id
            WHERE p.id = ?
            """,
            (payment_id,),
        ).fetchone()
        return dict(row) if row else None


def get_payment_stats(days: int = 30) -> dict[str, Any]:
    if days == 1:
        return get_daily_payments_stats()
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS paid_count,
                COALESCE(SUM(amount_cents), 0) AS paid_cents,
                COALESCE(SUM(amount_stars), 0) AS paid_stars,
                COALESCE(SUM(COALESCE(amount_cents, 0)), 0) AS raw_amount_cents
            FROM payments
            WHERE status = 'paid'
              AND paid_at >= datetime('now', ?)
            """,
            (f"-{int(days)} days",),
        ).fetchone()
        return dict(row) if row else {}

