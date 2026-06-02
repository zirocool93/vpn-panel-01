"""Small helpers for masking secrets before audit/log output."""
from __future__ import annotations

from typing import Any


SENSITIVE_KEY_PARTS = (
    "token",
    "api_token",
    "password",
    "secret",
    "privatekey",
    "private_key",
    "session",
    "cookie",
    "bot_token",
    "yookassa",
    "cardlink",
    "wata",
    "platega",
    "cryptobot",
    "csrf",
)


def mask_secret(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    if len(text) <= 8:
        return "******"
    return f"{text[:4]}******{text[-4:]}"


def mask_sensitive_dict(data: Any) -> Any:
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            key_l = str(key).lower()
            if any(part in key_l for part in SENSITIVE_KEY_PARTS):
                result[key] = mask_secret(value)
            else:
                result[key] = mask_sensitive_dict(value)
        return result
    if isinstance(data, list):
        return [mask_sensitive_dict(item) for item in data]
    if isinstance(data, tuple):
        return tuple(mask_sensitive_dict(item) for item in data)
    return data
