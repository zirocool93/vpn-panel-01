"""Web admin authentication helpers."""
from __future__ import annotations

import logging
import os
import secrets
from fnmatch import fnmatch
from typing import Any, Optional

from starlette.requests import Request
from starlette.responses import RedirectResponse

from database.db_settings import get_setting
from services.auth_service import get_session_by_token


logger = logging.getLogger(__name__)

SESSION_COOKIE = "web_admin_session"

ALL_PERMISSIONS = {
    "dashboard.view",
    "audit.view",
    "servers.view",
    "servers.create",
    "servers.update",
    "servers.delete",
    "servers.toggle",
    "servers.test",
    "servers.diagnostics",
    "servers.relogin",
    "servers.reset_api_token",
    "tariffs.view",
    "tariffs.create",
    "tariffs.update",
    "tariffs.toggle",
    "tariffs.delete",
    "users.view",
    "users.ban",
    "users.balance",
    "users.assign_tariff",
    "keys.view",
    "keys.create",
    "keys.update",
    "keys.delete",
    "keys.extend",
    "keys.reset_traffic",
    "keys.sync",
    "keys.links",
    "pages.view",
    "pages.update",
    "pages.reset",
    "pages.copy_default_buttons",
    "payments.view",
    "payments.manage",
    "settings.view",
    "settings.update",
    "system.view",
    "system.diagnostics",
    "system.logs",
    "system.clear_logs",
    "system.restart",
    "system.backups",
    "system.backup_create",
    "system.backup_download",
    "system.backup_restore",
    "system.backup_delete",
}

ROLES = {
    "owner": ALL_PERMISSIONS,
    "admin": ALL_PERMISSIONS - {"system.restart", "system.backup_restore"},
    "support": {
        "dashboard.view",
        "users.view",
        "users.assign_tariff",
        "keys.view",
        "keys.create",
        "keys.update",
        "keys.extend",
        "keys.sync",
        "keys.links",
        "servers.view",
        "servers.diagnostics",
        "tariffs.view",
        "pages.view",
    },
    "finance": {"dashboard.view", "users.view", "users.balance", "payments.view", "payments.manage", "tariffs.view", "audit.view"},
    "content": {"dashboard.view", "pages.view", "pages.update", "pages.reset", "pages.copy_default_buttons"},
    "readonly": {"dashboard.view", "servers.view", "users.view", "keys.view", "tariffs.view", "payments.view", "pages.view", "system.view"},
}

PERMISSION_RULES = [
    ("GET", "/admin", "dashboard.view"),
    ("GET", "/admin/", "dashboard.view"),
    ("GET", "/admin/audit*", "audit.view"),
    ("GET", "/admin/servers", "servers.view"),
    ("GET", "/admin/servers/new", "servers.create"),
    ("POST", "/admin/servers/new", "servers.create"),
    ("GET", "/admin/servers/*/diagnostics", "servers.diagnostics"),
    ("GET", "/admin/servers/*/inbounds*", "servers.diagnostics"),
    ("GET", "/admin/servers/*/online-clients", "servers.diagnostics"),
    ("POST", "/admin/servers/*/check-api-token", "servers.relogin"),
    ("POST", "/admin/servers/*/reset-api-token", "servers.reset_api_token"),
    ("POST", "/admin/servers/*/relogin", "servers.relogin"),
    ("GET", "/admin/servers/*/edit", "servers.update"),
    ("POST", "/admin/servers/*/edit", "servers.update"),
    ("POST", "/admin/servers/*/toggle", "servers.toggle"),
    ("POST", "/admin/servers/*/delete", "servers.delete"),
    ("POST", "/admin/servers/*/test", "servers.test"),
    ("GET", "/admin/servers*", "servers.view"),
    ("GET", "/admin/tariffs", "tariffs.view"),
    ("GET", "/admin/tariffs/new", "tariffs.create"),
    ("POST", "/admin/tariffs/new", "tariffs.create"),
    ("GET", "/admin/tariffs/*/edit", "tariffs.update"),
    ("POST", "/admin/tariffs/*/edit", "tariffs.update"),
    ("POST", "/admin/tariffs/*/toggle", "tariffs.toggle"),
    ("GET", "/admin/tariffs*", "tariffs.view"),
    ("GET", "/admin/users*", "users.view"),
    ("POST", "/admin/users/*/ban", "users.ban"),
    ("POST", "/admin/users/*/unban", "users.ban"),
    ("POST", "/admin/users/*/balance", "users.balance"),
    ("POST", "/admin/users/*/assign-tariff", "users.assign_tariff"),
    ("GET", "/admin/keys/new", "keys.create"),
    ("POST", "/admin/keys/new", "keys.create"),
    ("POST", "/admin/keys/*/extend*", "keys.extend"),
    ("GET", "/admin/keys/*/edit-tariff", "keys.update"),
    ("POST", "/admin/keys/*/edit-tariff", "keys.update"),
    ("POST", "/admin/keys/*/reset-traffic", "keys.reset_traffic"),
    ("POST", "/admin/keys/*/sync", "keys.sync"),
    ("GET", "/admin/keys/*/links", "keys.links"),
    ("GET", "/admin/keys/*/qr.png", "keys.links"),
    ("POST", "/admin/keys/*/delete", "keys.delete"),
    ("GET", "/admin/keys*", "keys.view"),
    ("POST", "/admin/pages/*/edit", "pages.update"),
    ("POST", "/admin/pages/*/reset*", "pages.reset"),
    ("POST", "/admin/pages/*/copy-default-buttons", "pages.copy_default_buttons"),
    ("POST", "/admin/pages/*/validate", "pages.update"),
    ("GET", "/admin/pages*", "pages.view"),
    ("GET", "/admin/payments*", "payments.view"),
    ("POST", "/admin/settings*", "settings.update"),
    ("GET", "/admin/settings*", "settings.view"),
    ("GET", "/admin/system/backups*/download", "system.backup_download"),
    ("POST", "/admin/system/backups/create", "system.backup_create"),
    ("POST", "/admin/system/backups/integrity-check", "system.backups"),
    ("POST", "/admin/system/backups/vacuum", "system.backup_restore"),
    ("POST", "/admin/system/backups/*/verify", "system.backups"),
    ("POST", "/admin/system/backups/*/delete", "system.backup_delete"),
    ("GET", "/admin/system/backups/*/restore", "system.backup_restore"),
    ("POST", "/admin/system/backups/*/restore", "system.backup_restore"),
    ("GET", "/admin/system/backups*", "system.backups"),
    ("POST", "/admin/system/restart-*", "system.restart"),
    ("POST", "/admin/system/clear-log", "system.clear_logs"),
    ("POST", "/admin/system/*", "system.diagnostics"),
    ("GET", "/admin/system/diagnostics", "system.diagnostics"),
    ("GET", "/admin/system/services", "system.diagnostics"),
    ("GET", "/admin/system/network", "system.diagnostics"),
    ("GET", "/admin/system/database", "system.diagnostics"),
    ("GET", "/admin/system*", "system.view"),
]


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


def get_cookie_secure() -> bool:
    value = os.getenv("WEB_COOKIE_SECURE") or get_setting("web_cookie_secure", "0")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def get_cookie_samesite() -> str:
    value = (os.getenv("WEB_COOKIE_SAMESITE") or get_setting("web_cookie_samesite", "lax") or "lax").strip().lower()
    return value if value in {"lax", "strict", "none"} else "lax"


def get_client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")


def get_current_admin(request: Request) -> Optional[dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return get_session_by_token(token)


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token") if hasattr(request, "session") else None
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return str(token)


def validate_csrf_token(request: Request, token: str | None) -> bool:
    expected = request.session.get("csrf_token") if hasattr(request, "session") else None
    return bool(expected and token and secrets.compare_digest(str(expected), str(token)))


def require_confirm(value: str | None, expected: str) -> bool:
    return (value or "").strip() == expected


def has_permission(admin: dict[str, Any] | None, permission: str) -> bool:
    if not admin:
        return False
    role = (admin.get("role") or "readonly").strip().lower()
    return permission in ROLES.get(role, set())


def permission_for_request(method: str, path: str) -> Optional[str]:
    method = method.upper()
    for rule_method, pattern, permission in PERMISSION_RULES:
        if rule_method == method and fnmatch(path, pattern):
            return permission
    if path.startswith("/admin"):
        return "dashboard.view" if method == "GET" else None
    return None


def can(request: Request, permission: str) -> bool:
    return has_permission(get_current_admin(request), permission)


def require_admin(request: Request) -> Optional[RedirectResponse]:
    if get_current_admin(request):
        return None
    return RedirectResponse("/login", status_code=303)


def require_permission(request: Request, permission: str) -> Optional[RedirectResponse]:
    if has_permission(get_current_admin(request), permission):
        return None
    return RedirectResponse("/admin", status_code=303)
