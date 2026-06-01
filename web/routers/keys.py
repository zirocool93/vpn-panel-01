from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from starlette.responses import RedirectResponse

from services import key_service
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/keys")


@router.get("")
async def list_keys(request: Request, q: str = Query(""), user_id: int | None = Query(None)):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "keys/list.html",
        template_context(request, title="Ключи", keys=key_service.list_keys(user_id=user_id, search=q or None), q=q, user_id=user_id),
    )


@router.get("/{key_id}")
async def key_detail(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "keys/detail.html",
        template_context(request, title="Ключ", key=key_service.get_key(key_id)),
    )


@router.post("/{key_id}/extend")
async def extend_key(request: Request, key_id: int, days: int = Form(...)):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    success = key_service.extend_key(key_id, days)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.extend", "key", key_id, {"days": days, "success": success}, request)
    flash(request, "Ключ продлён" if success else "Ключ не найден", "success" if success else "warning")
    return RedirectResponse(f"/admin/keys/{key_id}", status_code=303)


@router.post("/{key_id}/reset-traffic")
async def reset_traffic(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    success = await key_service.reset_key_traffic(key_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.traffic.reset", "key", key_id, {"panel_success": success}, request)
    flash(request, "Трафик сброшен")
    return RedirectResponse(f"/admin/keys/{key_id}", status_code=303)


@router.post("/{key_id}/sync")
async def sync_key(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = await key_service.sync_key_to_panel(key_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.sync", "key", key_id, result, request)
    flash(request, "Синхронизация выполнена")
    return RedirectResponse(f"/admin/keys/{key_id}", status_code=303)


@router.post("/{key_id}/delete")
async def delete_key(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    success = key_service.delete_key(key_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.delete", "key", key_id, {"success": success}, request)
    flash(request, "Ключ удалён" if success else "Ключ не найден", "warning")
    return RedirectResponse("/admin/keys", status_code=303)
