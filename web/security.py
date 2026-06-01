"""Web admin authentication helpers."""
from __future__ import annotations

import logging
import os
import secrets
from typing import Any, Optional

from starlette.requests import Request
from starlette.responses import RedirectResponse

from database.db_settings import get_setting
from services.auth_service import get_session_by_token


logger = logging.getLogger(__name__)

SESSION_COOKIE = "web_admin_session"


def get_secret_key() -> str:
    secret = os.getenv("WEB_SECRET_KEY") or get_setting("web_secret_key")
    if secret:
        return secret
    generated = secrets.token_urlsafe(32)
    logger.warning(
        "WEB_SECRET_KEY is not set and settings.web_secret_key is empty. "
        "Using an ephemeral development secret; set WEB_SECRET_KEY in production."
    )
    return generated


def get_client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")


def get_current_admin(request: Request) -> Optional[dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return get_session_by_token(token)


def require_admin(request: Request) -> Optional[RedirectResponse]:
    if get_current_admin(request):
        return None
    return RedirectResponse("/login", status_code=303)

