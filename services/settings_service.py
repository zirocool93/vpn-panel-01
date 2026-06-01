"""Settings service with masking helpers for Web admin."""
from __future__ import annotations

from typing import Optional

from database.connection import get_db
from database.db_settings import get_setting as _get_setting, set_setting as _set_setting


SECRET_KEYWORDS = ("token", "secret", "password", "api_key", "jwt")


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    return _get_setting(key, default)


def set_setting(key: str, value: str) -> None:
    _set_setting(key, value)


def get_all_settings(mask_secrets: bool = False) -> dict[str, str]:
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
    settings = {row["key"]: row["value"] for row in rows}
    if mask_secrets:
        return {key: mask_secret(key, value) for key, value in settings.items()}
    return settings


def update_many_settings(values: dict[str, str]) -> None:
    for key, value in values.items():
        set_setting(key, value)


def mask_secret(key: str, value: Optional[str]) -> str:
    if not value:
        return ""
    if not any(part in key.lower() for part in SECRET_KEYWORDS):
        return value
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}******{value[-4:]}"

