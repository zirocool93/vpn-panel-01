from __future__ import annotations

from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse

from database.db_settings import get_setting
from services.audit_service import log_admin_action
from services.auth_service import (
    create_session,
    is_login_rate_limited,
    log_login_attempt,
    revoke_session,
    update_last_login,
    verify_admin_credentials,
)
from web import security
from web.deps import flash, template_context, templates


router = APIRouter()


@router.get("/")
async def root(request: Request):
    if security.get_current_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return RedirectResponse("/login", status_code=303)


@router.get("/login")
async def login_page(request: Request):
    if security.get_current_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "login.html", template_context(request, title="Login"))


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    ip_address = security.get_client_ip(request)
    user_agent = security.get_user_agent(request)
    rate_limit = is_login_rate_limited(username, ip_address)
    if rate_limit["limited"]:
        log_login_attempt(username, ip_address, user_agent, False, "rate_limited")
        log_admin_action(None, "login.rate_limited", "security", None, {"username": username, "attempts": rate_limit["attempts"]}, request=request)
        flash(request, "Слишком много попыток входа. Повторите позже.", "danger")
        return RedirectResponse("/login", status_code=303)

    admin = verify_admin_credentials(username, password)
    if not admin:
        log_login_attempt(username, ip_address, user_agent, False, "invalid_credentials")
        log_admin_action(None, "login.failed", "security", None, {"username": username}, request=request)
        flash(request, "Неверный логин или пароль", "danger")
        return RedirectResponse("/login", status_code=303)

    session = create_session(admin["id"], ip_address=ip_address, user_agent=user_agent)
    update_last_login(admin["id"])
    log_login_attempt(username, ip_address, user_agent, True)
    log_admin_action(admin["id"], "login", "admin_user", admin["id"], request=request)

    response = RedirectResponse("/admin", status_code=303)
    lifetime_hours = int(get_setting("web_session_lifetime_hours", "12") or "12")
    response.set_cookie(
        security.SESSION_COOKIE,
        session["session_token"],
        httponly=True,
        secure=security.get_cookie_secure(),
        samesite=security.get_cookie_samesite(),
        max_age=max(1, lifetime_hours) * 60 * 60,
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    admin = security.get_current_admin(request)
    token = request.cookies.get(security.SESSION_COOKIE)
    if token:
        revoke_session(token)
    if admin:
        log_admin_action(admin["admin_user_id"], "logout", "admin_user", admin["admin_user_id"], request=request)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(security.SESSION_COOKIE)
    return response
