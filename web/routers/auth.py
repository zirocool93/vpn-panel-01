from __future__ import annotations

from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse

from services.audit_service import log_admin_action
from services.auth_service import create_session, revoke_session, update_last_login, verify_admin_credentials
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
    admin = verify_admin_credentials(username, password)
    if not admin:
        flash(request, "Неверный логин или пароль", "danger")
        return RedirectResponse("/login", status_code=303)

    session = create_session(
        admin["id"],
        ip_address=security.get_client_ip(request),
        user_agent=security.get_user_agent(request),
    )
    update_last_login(admin["id"])
    log_admin_action(admin["id"], "login", "admin_user", admin["id"], request=request)

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        security.SESSION_COOKIE,
        session["session_token"],
        httponly=True,
        samesite="lax",
        max_age=12 * 60 * 60,
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
