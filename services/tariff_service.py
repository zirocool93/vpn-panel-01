"""Tariff service using the existing database tariff functions."""
from __future__ import annotations

from typing import Any, Optional

from database import db_tariffs


def list_tariffs(include_hidden: bool = True) -> list[dict[str, Any]]:
    return db_tariffs.get_all_tariffs(include_hidden=include_hidden)


def get_tariff(tariff_id: int) -> Optional[dict[str, Any]]:
    return db_tariffs.get_tariff_by_id(tariff_id)


def create_tariff(
    name: str,
    duration_days: int,
    price_cents: int = 0,
    price_stars: int = 0,
    price_rub: int = 0,
    display_order: int = 0,
    traffic_limit_gb: int = 0,
    group_id: int = 1,
    max_ips: int = 1,
) -> int:
    return db_tariffs.add_tariff(
        name,
        duration_days,
        price_cents,
        price_stars,
        price_rub,
        display_order,
        traffic_limit_gb,
        group_id,
        max_ips,
    )


def update_tariff(tariff_id: int, **fields: Any) -> bool:
    return db_tariffs.update_tariff(tariff_id, **fields)


def deactivate_tariff(tariff_id: int) -> bool:
    return db_tariffs.update_tariff(tariff_id, is_active=0)


def delete_tariff(tariff_id: int) -> bool:
    """Safe delete for Web MVP: deactivate instead of removing tariff history."""
    return deactivate_tariff(tariff_id)


def toggle_tariff_active(tariff_id: int) -> Optional[bool]:
    return db_tariffs.toggle_tariff_active(tariff_id)

