from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from starlette.responses import RedirectResponse, Response

from services import key_service
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/keys")


def _optional_int(value: str | None) -> int | None:
    return int(value) if value and str(value).strip() else None


@router.get("")
async def list_keys(request: Request, q: str = Query(""), user_id: int | None = Query(None)):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "keys/list.html",
        template_context(
            request,
            title="Ключи",
            keys=key_service.list_keys(user_id=user_id, search=q or None),
            q=q,
            user_id=user_id,
        ),
    )


@router.get("/new")
async def new_key(request: Request, user_id: int | None = Query(None)):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "keys/new.html",
        template_context(
            request,
            title="Создать ключ",
            options=key_service.get_key_create_options(user_id),
            selected_user_id=user_id,
        ),
    )


@router.post("/new")
async def create_key(
    request: Request,
    user_id: int = Form(...),
    tariff_id: int = Form(...),
    server_id: str = Form(""),
    inbound_id: str = Form(""),
    custom_name: str = Form(""),
    create_on_panel: str | None = Form(None),
):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = await key_service.create_key_for_user(
        user_id=user_id,
        tariff_id=tariff_id,
        server_id=_optional_int(server_id),
        inbound_id=_optional_int(inbound_id),
        custom_name=custom_name or None,
        create_on_panel=create_on_panel == "1",
    )
    admin = security.get_current_admin(request)
    log_admin_action(
        admin["admin_user_id"],
        "key.create",
        "key",
        result.get("key_id"),
        {
            "user_id": user_id,
            "tariff_id": tariff_id,
            "server_id": _optional_int(server_id),
            "inbound_id": _optional_int(inbound_id),
            "create_on_panel": create_on_panel == "1",
            "success": result.get("success"),
            "message": result.get("message"),
        },
        request,
    )
    flash(request, result.get("message", "Готово"), "success" if result.get("success") else "danger")
    if result.get("success") and result.get("key_id"):
        return RedirectResponse(f"/admin/keys/{result['key_id']}", status_code=303)
    return RedirectResponse("/admin/keys/new", status_code=303)


@router.get("/{key_id}")
async def key_detail(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "keys/detail.html",
        template_context(request, title="Ключ", key=key_service.get_key_full(key_id), options=key_service.get_key_create_options()),
    )


@router.post("/{key_id}/extend")
async def extend_key(request: Request, key_id: int, days: int = Form(...)):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    if days <= 0:
        flash(request, "Количество дней должно быть положительным", "danger")
        return RedirectResponse(f"/admin/keys/{key_id}", status_code=303)
    success = key_service.extend_key(key_id, days)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.extend", "key", key_id, {"days": days, "success": success}, request)
    flash(request, "Ключ продлён" if success else "Ключ не найден", "success" if success else "warning")
    return RedirectResponse(f"/admin/keys/{key_id}", status_code=303)


@router.get("/{key_id}/edit-tariff")
async def edit_key_tariff(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "keys/edit_tariff.html",
        template_context(request, title="Изменить тариф", key=key_service.get_key_full(key_id), options=key_service.get_key_create_options()),
    )


@router.post("/{key_id}/edit-tariff")
async def update_key_tariff(request: Request, key_id: int, tariff_id: int = Form(...), apply_limits: str | None = Form(None)):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = key_service.change_key_tariff(key_id, tariff_id, apply_limits=apply_limits == "1")
    if result.get("success"):
        result["panel_result"] = await key_service.sync_key_to_panel(key_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.tariff.change", "key", key_id, result, request)
    flash(request, result.get("message", "Готово"), "success" if result.get("success") else "danger")
    return RedirectResponse(f"/admin/keys/{key_id}", status_code=303)


@router.post("/{key_id}/extend-by-tariff")
async def extend_key_by_tariff(request: Request, key_id: int, tariff_id: int = Form(...), update_tariff: str | None = Form(None)):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = await key_service.extend_key_by_tariff(key_id, tariff_id, update_tariff=update_tariff == "1")
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.extend.by_tariff", "key", key_id, {"tariff_id": tariff_id, **result}, request)
    flash(request, result.get("message", "Готово"), "success" if result.get("success") else "danger")
    return RedirectResponse(f"/admin/keys/{key_id}", status_code=303)


@router.post("/{key_id}/reset-traffic")
async def reset_traffic(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    success = await key_service.reset_key_traffic(key_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.traffic.reset", "key", key_id, {"panel_success": success}, request)
    flash(request, "Трафик сброшен" if success else "Трафик сброшен в БД, панель не подтвердила операцию", "success" if success else "warning")
    return RedirectResponse(f"/admin/keys/{key_id}", status_code=303)


@router.post("/{key_id}/sync")
async def sync_key(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = await key_service.sync_key_to_panel(key_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.sync", "key", key_id, result, request)
    flash(request, "Синхронизация выполнена" if result.get("ok") else "Синхронизация завершилась с ошибками", "success" if result.get("ok") else "warning")
    return RedirectResponse(f"/admin/keys/{key_id}", status_code=303)


@router.get("/{key_id}/confirm-delete")
async def confirm_delete_key(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "keys/confirm_delete.html",
        template_context(request, title="Удалить ключ", key=key_service.get_key_full(key_id)),
    )


@router.post("/{key_id}/delete")
async def delete_key(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    key = key_service.get_key_full(key_id)
    success = key_service.delete_key(key_id)
    admin = security.get_current_admin(request)
    log_admin_action(
        admin["admin_user_id"],
        "key.delete",
        "key",
        key_id,
        {
            "success": success,
            "user_id": key.get("user_id") if key else None,
            "panel_email": key.get("panel_email") if key else None,
            "server_id": key.get("server_id") if key else None,
        },
        request,
    )
    flash(request, "Ключ удалён" if success else "Ключ не найден", "warning")
    return RedirectResponse("/admin/keys", status_code=303)


@router.get("/{key_id}/links")
async def key_links(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = await key_service.regenerate_key_links(key_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "key.links.view", "key", key_id, {"success": result.get("success")}, request)
    return templates.TemplateResponse(
        request,
        "keys/links.html",
        template_context(request, title="Ссылки ключа", result=result, key=result.get("key") or key_service.get_key_full(key_id)),
    )


@router.get("/{key_id}/qr.png")
async def key_qr(request: Request, key_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = await key_service.regenerate_key_links(key_id)
    data = result.get("subscription_url") or result.get("client_link")
    if not data:
        return Response("QR unavailable", status_code=404)
    from bot.utils.key_generator import generate_qr_code

    return Response(generate_qr_code(data), media_type="image/png")
