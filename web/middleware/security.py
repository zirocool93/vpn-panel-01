"""Security middleware for the Web admin."""
from __future__ import annotations

from urllib.parse import parse_qs

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from services.audit_service import log_admin_action
from web import security


CSRF_ALLOWED_PATHS = set()
CONFIRM_RULES = [
    ("/admin/system/restart-bot", "RESTART"),
    ("/admin/system/restart-web", "RESTART"),
    ("/admin/system/clear-log", "CLEAR"),
    ("/admin/servers/*/reset-api-token", "RESET"),
    ("/admin/servers/*/delete", "DELETE"),
    ("/admin/keys/*/delete", "DELETE"),
    ("/admin/system/backups/*/restore", "RESTORE"),
    ("/admin/system/backups/*/delete", "DELETE"),
    ("/admin/system/backups/vacuum", "VACUUM"),
]


class WebSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/admin") or request.url.path in {"/login", "/logout"}:
            security.get_or_create_csrf_token(request)

        if request.method.upper() == "POST" and request.url.path not in CSRF_ALLOWED_PATHS:
            form_values = await _extract_form_values(request)
            token = form_values.get("csrf_token")
            if not security.validate_csrf_token(request, token):
                _flash(request, "Ошибка безопасности формы. Обновите страницу и повторите действие.", "danger")
                _audit_security(request, "security.csrf_failed", {"path": request.url.path, "method": request.method})
                return RedirectResponse(_redirect_target(request), status_code=303)
            expected_confirm = _confirm_for_path(request.url.path)
            if expected_confirm and not security.require_confirm(form_values.get("confirm"), expected_confirm):
                _flash(request, "Подтверждение не совпадает", "danger")
                _audit_security(request, "security.confirm_failed", {"path": request.url.path, "expected": expected_confirm})
                return RedirectResponse(_redirect_target(request), status_code=303)

        permission = security.permission_for_request(request.method, request.url.path)
        if permission and request.url.path.startswith("/admin"):
            admin = security.get_current_admin(request)
            if admin and not security.has_permission(admin, permission):
                _flash(request, "Недостаточно прав", "danger")
                _audit_security(request, "security.permission_denied", {"permission": permission, "path": request.url.path, "role": admin.get("role")})
                return RedirectResponse("/admin", status_code=303)

        response = await call_next(request)
        _apply_security_headers(request, response)
        return response


async def _extract_form_values(request: Request) -> dict[str, str]:
    header = request.headers.get("x-csrf-token")
    values = {"csrf_token": header} if header else {}

    body = await request.body()
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    request._receive = receive

    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        values.update({key: items[0] if items else "" for key, items in parsed.items()})
        return values
    if "multipart/form-data" in content_type:
        form = await request.form()
        values.update({key: str(value) for key, value in form.items()})
        return values
    return values


def _confirm_for_path(path: str) -> str | None:
    from fnmatch import fnmatch

    for pattern, expected in CONFIRM_RULES:
        if fnmatch(path, pattern):
            return expected
    return None


def _apply_security_headers(request: Request, response: Response) -> None:
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self'; frame-ancestors 'none'",
    )
    if request.url.path.startswith("/admin"):
        response.headers.setdefault("Cache-Control", "no-store")


def _redirect_target(request: Request) -> str:
    if request.url.path == "/login":
        return "/login"
    return request.headers.get("referer") or "/admin"


def _flash(request: Request, message: str, category: str) -> None:
    flashes = request.session.get("flashes", [])
    flashes.append({"message": message, "category": category})
    request.session["flashes"] = flashes


def _audit_security(request: Request, action: str, details: dict) -> None:
    admin = security.get_current_admin(request)
    admin_id = admin.get("admin_user_id") if admin else None
    try:
        log_admin_action(admin_id, action, "security", None, details, request)
    except Exception:
        return
