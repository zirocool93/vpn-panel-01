from __future__ import annotations

from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse

from services import admin_permissions_service, admin_users_service
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/admin-users")


@router.get("")
async def list_admin_users(request: Request, q: str = "", role: str = "", active: str = "all"):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    include_inactive = active != "active"
    return templates.TemplateResponse(
        request,
        "admin_users/list.html",
        template_context(
            request,
            title="Web админы",
            admin_users=admin_users_service.list_admin_users(q, role, include_inactive),
            roles=admin_users_service.role_choices(),
            q=q,
            role=role,
            active=active,
        ),
    )


@router.get("/new")
async def new_admin_user(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "admin_users/form.html", template_context(request, title="Новый Web админ", target=None, roles=admin_users_service.role_choices()))


@router.post("/new")
async def create_admin_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    role: str = Form(...),
    is_active: str = Form(""),
):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    if password != confirm_password:
        flash(request, "Пароли не совпадают", "danger")
        return RedirectResponse("/admin/admin-users/new", status_code=303)
    actor = security.get_current_admin(request)
    try:
        target = admin_users_service.create_web_admin(username, password, role, bool(is_active), actor)
    except Exception as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse("/admin/admin-users/new", status_code=303)
    log_admin_action(actor["admin_user_id"], "admin_user.create", "admin_user", target["id"], {"username": target["username"], "role": target["role"], "is_active": target["is_active"]}, request)
    flash(request, "Web админ создан")
    return RedirectResponse(f"/admin/admin-users/{target['id']}", status_code=303)


@router.get("/roles")
async def roles_list(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "admin_users/roles_list.html", template_context(request, title="Роли", roles=admin_permissions_service.list_roles()))


@router.get("/roles/{role_key}")
async def role_detail(request: Request, role_key: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    role = admin_permissions_service.get_role(role_key)
    return templates.TemplateResponse(
        request,
        "admin_users/role_form.html",
        template_context(request, title="Роль", role=role, grouped_permissions=admin_permissions_service.grouped_permissions(), selected=set(role.get("permissions", [])) if role else set()),
    )


@router.post("/roles/{role_key}")
async def update_role(request: Request, role_key: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    form = await request.form()
    permissions = [str(value) for value in form.getlist("permissions")]
    actor = security.get_current_admin(request)
    try:
        result = admin_permissions_service.update_role_permissions(role_key, permissions, actor["admin_user_id"])
    except Exception as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(f"/admin/admin-users/roles/{role_key}", status_code=303)
    log_admin_action(actor["admin_user_id"], "admin_role.permissions.update", "admin_role", role_key, result, request)
    flash(request, "Права роли обновлены")
    return RedirectResponse(f"/admin/admin-users/roles/{role_key}", status_code=303)


@router.get("/{admin_user_id}")
async def admin_user_detail(request: Request, admin_user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    target = admin_users_service.get_admin_user(admin_user_id)
    effective = admin_permissions_service.get_effective_permissions({"admin_user_id": admin_user_id, **target}) if target else set()
    return templates.TemplateResponse(
        request,
        "admin_users/detail.html",
        template_context(
            request,
            title="Web админ",
            target=target,
            effective_permissions=sorted(effective),
            overrides=admin_permissions_service.get_user_permission_overrides(admin_user_id),
            sessions=admin_users_service.get_admin_sessions(admin_user_id),
            login_attempts=admin_users_service.get_admin_login_attempts(target["username"] if target else "", 20),
            audit_events=admin_users_service.get_admin_audit_events(admin_user_id, 50),
        ),
    )


@router.get("/{admin_user_id}/edit")
async def edit_admin_user(request: Request, admin_user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "admin_users/form.html", template_context(request, title="Редактировать Web админа", target=admin_users_service.get_admin_user(admin_user_id), roles=admin_users_service.role_choices()))


@router.post("/{admin_user_id}/edit")
async def update_admin_user(request: Request, admin_user_id: int, username: str = Form(...), role: str = Form(...), is_active: str = Form("")):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    actor = security.get_current_admin(request)
    old = admin_users_service.get_admin_user(admin_user_id)
    try:
        target = admin_users_service.update_web_admin(admin_user_id, username, role, bool(is_active), actor)
    except Exception as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(f"/admin/admin-users/{admin_user_id}/edit", status_code=303)
    log_admin_action(actor["admin_user_id"], "admin_user.update", "admin_user", admin_user_id, {"old_role": old.get("role") if old else None, "new_role": target["role"], "old_is_active": old.get("is_active") if old else None, "new_is_active": target["is_active"]}, request)
    flash(request, "Web админ обновлён")
    return RedirectResponse(f"/admin/admin-users/{admin_user_id}", status_code=303)


@router.get("/{admin_user_id}/password")
async def password_page(request: Request, admin_user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "admin_users/password.html", template_context(request, title="Сброс пароля", target=admin_users_service.get_admin_user(admin_user_id)))


@router.post("/{admin_user_id}/password")
async def reset_password(request: Request, admin_user_id: int, new_password: str = Form(...), confirm_password: str = Form(...), revoke_sessions: str = Form("")):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    if new_password != confirm_password:
        flash(request, "Пароли не совпадают", "danger")
        return RedirectResponse(f"/admin/admin-users/{admin_user_id}/password", status_code=303)
    actor = security.get_current_admin(request)
    try:
        result = admin_users_service.reset_web_admin_password(admin_user_id, new_password, bool(revoke_sessions))
    except Exception as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(f"/admin/admin-users/{admin_user_id}/password", status_code=303)
    log_admin_action(actor["admin_user_id"], "admin_user.password_reset", "admin_user", admin_user_id, result, request)
    flash(request, "Пароль обновлён")
    return RedirectResponse(f"/admin/admin-users/{admin_user_id}", status_code=303)


@router.post("/{admin_user_id}/disable")
async def disable_admin_user(request: Request, admin_user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    actor = security.get_current_admin(request)
    try:
        result = admin_users_service.disable_web_admin(admin_user_id, actor)
    except Exception as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(f"/admin/admin-users/{admin_user_id}", status_code=303)
    log_admin_action(actor["admin_user_id"], "admin_user.disable", "admin_user", admin_user_id, result, request)
    flash(request, "Web админ отключён", "warning")
    return RedirectResponse(f"/admin/admin-users/{admin_user_id}", status_code=303)


@router.post("/{admin_user_id}/enable")
async def enable_admin_user(request: Request, admin_user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    actor = security.get_current_admin(request)
    result = admin_users_service.enable_web_admin(admin_user_id)
    log_admin_action(actor["admin_user_id"], "admin_user.enable", "admin_user", admin_user_id, result, request)
    flash(request, "Web админ включён")
    return RedirectResponse(f"/admin/admin-users/{admin_user_id}", status_code=303)


@router.post("/{admin_user_id}/revoke-sessions")
async def revoke_sessions(request: Request, admin_user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    actor = security.get_current_admin(request)
    result = admin_users_service.revoke_admin_sessions(admin_user_id, request.cookies.get(security.SESSION_COOKIE))
    log_admin_action(actor["admin_user_id"], "admin_user.sessions.revoke", "admin_user", admin_user_id, result, request)
    flash(request, f"Сессии отозваны: {result['revoked_sessions_count']}", "warning")
    return RedirectResponse(f"/admin/admin-users/{admin_user_id}", status_code=303)


@router.get("/{admin_user_id}/permissions")
async def permissions_page(request: Request, admin_user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    target = admin_users_service.get_admin_user(admin_user_id)
    role_permissions = admin_permissions_service.get_role_permissions(target["role"]) if target else set()
    effective = admin_permissions_service.get_effective_permissions({"admin_user_id": admin_user_id, **target}) if target else set()
    overrides = {item["permission"]: item["effect"] for item in admin_permissions_service.get_user_permission_overrides(admin_user_id)}
    return templates.TemplateResponse(
        request,
        "admin_users/permissions.html",
        template_context(
            request,
            title="Права Web админа",
            target=target,
            grouped_permissions=admin_permissions_service.grouped_permissions(),
            role_permissions=role_permissions,
            effective_permissions=effective,
            overrides=overrides,
        ),
    )


@router.post("/{admin_user_id}/permissions")
async def update_permissions(request: Request, admin_user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    form = await request.form()
    overrides = {}
    for key, value in form.items():
        if key.startswith("override__"):
            overrides[key.removeprefix("override__")] = str(value)
    result = admin_permissions_service.set_user_permission_overrides(admin_user_id, overrides)
    actor = security.get_current_admin(request)
    log_admin_action(actor["admin_user_id"], "admin_user.permissions.update", "admin_user", admin_user_id, result, request)
    flash(request, "Персональные права обновлены")
    return RedirectResponse(f"/admin/admin-users/{admin_user_id}/permissions", status_code=303)
