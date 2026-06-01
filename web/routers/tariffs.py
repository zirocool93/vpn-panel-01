from __future__ import annotations

from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse

from services import tariff_service
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/tariffs")


@router.get("")
async def list_tariffs(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "tariffs/list.html",
        template_context(request, title="Тарифы", tariffs=tariff_service.list_tariffs(include_hidden=True)),
    )


@router.get("/new")
async def new_tariff(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "tariffs/form.html", template_context(request, title="Новый тариф", tariff=None))


@router.post("/new")
async def create_tariff(
    request: Request,
    name: str = Form(...),
    duration_days: int = Form(...),
    price_rub: int = Form(0),
    price_cents: int = Form(0),
    price_stars: int = Form(0),
    traffic_limit_gb: int = Form(0),
    max_ips: int = Form(1),
    group_id: int = Form(1),
    display_order: int = Form(0),
):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    tariff_id = tariff_service.create_tariff(
        name, duration_days, price_cents, price_stars, price_rub,
        display_order, traffic_limit_gb, group_id, max_ips,
    )
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "tariff.create", "tariff", tariff_id, {"name": name}, request)
    flash(request, "Тариф создан")
    return RedirectResponse("/admin/tariffs", status_code=303)


@router.get("/{tariff_id}")
async def tariff_detail(request: Request, tariff_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "tariffs/detail.html",
        template_context(request, title="Тариф", tariff=tariff_service.get_tariff(tariff_id)),
    )


@router.get("/{tariff_id}/edit")
async def edit_tariff(request: Request, tariff_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "tariffs/form.html",
        template_context(request, title="Редактировать тариф", tariff=tariff_service.get_tariff(tariff_id)),
    )


@router.post("/{tariff_id}/edit")
async def update_tariff(
    request: Request,
    tariff_id: int,
    name: str = Form(...),
    duration_days: int = Form(...),
    price_rub: int = Form(0),
    price_cents: int = Form(0),
    price_stars: int = Form(0),
    traffic_limit_gb: int = Form(0),
    max_ips: int = Form(1),
    group_id: int = Form(1),
    display_order: int = Form(0),
):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    fields = {
        "name": name,
        "duration_days": duration_days,
        "price_rub": price_rub,
        "price_cents": price_cents,
        "price_stars": price_stars,
        "traffic_limit_gb": traffic_limit_gb,
        "max_ips": max_ips,
        "group_id": group_id,
        "display_order": display_order,
    }
    tariff_service.update_tariff(tariff_id, **fields)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "tariff.update", "tariff", tariff_id, {"fields": list(fields)}, request)
    flash(request, "Тариф обновлён")
    return RedirectResponse("/admin/tariffs", status_code=303)


@router.post("/{tariff_id}/toggle")
async def toggle_tariff(request: Request, tariff_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    status = tariff_service.toggle_tariff_active(tariff_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "tariff.toggle", "tariff", tariff_id, {"is_active": status}, request)
    flash(request, "Статус тарифа изменён")
    return RedirectResponse("/admin/tariffs", status_code=303)
