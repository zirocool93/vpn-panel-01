from __future__ import annotations

from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse

from services import server_service
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/servers")


@router.get("")
async def list_servers(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "servers/list.html",
        template_context(request, title="Серверы", servers=server_service.list_servers()),
    )


@router.get("/new")
async def new_server(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "servers/form.html", template_context(request, title="Новый сервер", server=None))


@router.post("/new")
async def create_server(
    request: Request,
    name: str = Form(...),
    host: str = Form(...),
    port: int = Form(...),
    web_base_path: str = Form(""),
    login: str = Form(...),
    password: str = Form(...),
    protocol: str = Form("https"),
    group_id: int = Form(1),
):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    admin = security.get_current_admin(request)
    server_id = server_service.create_server(name, host, port, web_base_path, login, password, protocol, group_id)
    log_admin_action(admin["admin_user_id"], "server.create", "server", server_id, {"name": name}, request)
    flash(request, "Сервер создан")
    return RedirectResponse("/admin/servers", status_code=303)


@router.get("/{server_id}")
async def server_detail(request: Request, server_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "servers/detail.html",
        template_context(request, title="Сервер", server=server_service.get_server(server_id)),
    )


@router.get("/{server_id}/edit")
async def edit_server(request: Request, server_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "servers/form.html",
        template_context(request, title="Редактировать сервер", server=server_service.get_server(server_id)),
    )


@router.post("/{server_id}/edit")
async def update_server(
    request: Request,
    server_id: int,
    name: str = Form(...),
    host: str = Form(...),
    port: int = Form(...),
    web_base_path: str = Form(""),
    login: str = Form(...),
    new_password: str = Form(""),
    protocol: str = Form("https"),
    group_id: int = Form(1),
):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    fields = {
        "name": name,
        "host": host,
        "port": port,
        "web_base_path": web_base_path,
        "login": login,
        "protocol": protocol,
    }
    if new_password:
        fields["password"] = new_password
    server_service.update_server(server_id, **fields)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "server.update", "server", server_id, {"fields": list(fields)}, request)
    flash(request, "Сервер обновлён")
    return RedirectResponse("/admin/servers", status_code=303)


@router.post("/{server_id}/toggle")
async def toggle_server(request: Request, server_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    status = server_service.toggle_server_active(server_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "server.toggle", "server", server_id, {"is_active": status}, request)
    flash(request, "Статус сервера изменён")
    return RedirectResponse("/admin/servers", status_code=303)


@router.post("/{server_id}/delete")
async def delete_server(request: Request, server_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    server_service.delete_server(server_id)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "server.delete", "server", server_id, request=request)
    flash(request, "Сервер удалён", "warning")
    return RedirectResponse("/admin/servers", status_code=303)


@router.post("/{server_id}/test")
async def test_server(request: Request, server_id: int):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = await server_service.test_server_connection(server_id)
    flash(request, result.get("message", "Проверка завершена"), "success" if result.get("success") else "danger")
    return RedirectResponse(f"/admin/servers/{server_id}", status_code=303)
