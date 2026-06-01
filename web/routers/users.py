from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from starlette.responses import RedirectResponse

from services import key_service, payment_service, user_service
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/users")


@router.get("")
async def list_users(request: Request, q: str = Query("")):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "users/list.html",
        template_context(request, title="Пользователи", users=user_service.list_users(search=q or None), q=q),
    )


@router.get("/{user_id}")
async def user_detail(request: Request, user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "users/detail.html",
        template_context(
            request,
            title="Пользователь",
            user=user_service.get_user(user_id),
            keys=key_service.list_keys(user_id=user_id, limit=20),
            payments=payment_service.list_payments(user_id=user_id, limit=20),
        ),
    )


@router.post("/{user_id}/ban")
async def ban_user(request: Request, user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    status = user_service.ban_user(user_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "user.ban", "user", user_id, {"is_banned": status}, request)
    flash(request, "Пользователь заблокирован")
    return RedirectResponse(f"/admin/users/{user_id}", status_code=303)


@router.post("/{user_id}/unban")
async def unban_user(request: Request, user_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    status = user_service.unban_user(user_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "user.unban", "user", user_id, {"is_banned": status}, request)
    flash(request, "Пользователь разблокирован")
    return RedirectResponse(f"/admin/users/{user_id}", status_code=303)


@router.post("/{user_id}/balance")
async def update_balance(request: Request, user_id: int, amount_delta_cents: int = Form(...), reason: str = Form(...)):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    user = user_service.get_user(user_id)
    old_value = user.get("personal_balance", 0) if user else 0
    success = user_service.update_user_balance(user_id, amount_delta_cents)
    new_user = user_service.get_user(user_id)
    new_value = new_user.get("personal_balance", old_value) if new_user else old_value
    admin = security.get_current_admin(request)
    log_admin_action(
        admin["admin_user_id"],
        "user.balance.update",
        "user",
        user_id,
        {"old_value": old_value, "new_value": new_value, "delta": amount_delta_cents, "reason": reason, "success": success},
        request,
    )
    flash(request, "Баланс обновлён" if success else "Баланс не изменён", "success" if success else "warning")
    return RedirectResponse(f"/admin/users/{user_id}", status_code=303)
