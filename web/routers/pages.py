from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from starlette.responses import RedirectResponse

from services import page_service
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/pages")


@router.get("")
async def list_pages(request: Request, q: str = Query(""), group: str = Query("")):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "pages/list.html",
        template_context(
            request,
            title="Страницы бота",
            pages=page_service.list_pages(q=q, group=group),
            groups=page_service.get_page_groups(),
            q=q,
            selected_group=group,
        ),
    )


@router.get("/{page_key}")
async def page_detail(request: Request, page_key: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "pages/detail.html",
        template_context(request, title=f"Страница {page_key}", page=page_service.get_page_full(page_key)),
    )


@router.get("/{page_key}/preview")
async def page_preview(request: Request, page_key: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "pages/preview.html",
        template_context(request, title=f"Preview {page_key}", page=page_service.get_page_full(page_key)),
    )


@router.get("/{page_key}/edit")
async def edit_page(request: Request, page_key: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "pages/edit.html",
        template_context(request, title=f"Редактировать {page_key}", page=page_service.get_page_full(page_key), errors=[]),
    )


@router.post("/{page_key}/edit")
async def update_page(
    request: Request,
    page_key: str,
    text_custom: str = Form(""),
    image_custom: str = Form(""),
    buttons_custom: str = Form(""),
):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    page = page_service.get_page_full(page_key)
    if not page:
        flash(request, "Страница не найдена", "warning")
        return RedirectResponse("/admin/pages", status_code=303)

    result = page_service.update_page_from_web(page_key, text_custom, image_custom, buttons_custom)
    admin = security.get_current_admin(request)
    if not result.ok:
        page.update(
            {
                "text_custom": text_custom,
                "image_custom": image_custom,
                "buttons_custom_pretty": buttons_custom,
            }
        )
        return templates.TemplateResponse(
            request,
            "pages/edit.html",
            template_context(request, title=f"Редактировать {page_key}", page=page, errors=result.errors),
            status_code=400,
        )

    log_admin_action(
        admin["admin_user_id"],
        "page.update",
        "page",
        page_key,
        {
            "text_custom": bool(text_custom),
            "image_custom": bool(image_custom.strip()),
            "buttons_custom": bool(buttons_custom.strip()),
        },
        request,
    )
    flash(request, "Страница обновлена")
    return RedirectResponse(f"/admin/pages/{page_key}", status_code=303)


@router.post("/{page_key}/reset")
async def reset_page_field(request: Request, page_key: str, field: str = Form(...)):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    if not page_service.get_page_full(page_key):
        flash(request, "Страница не найдена", "warning")
        return RedirectResponse("/admin/pages", status_code=303)
    try:
        page_service.reset_page_custom_field(page_key, field)
    except ValueError:
        flash(request, "Неизвестное поле для сброса", "danger")
        return RedirectResponse(f"/admin/pages/{page_key}", status_code=303)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "page.reset", "page", page_key, {"field": field}, request)
    flash(request, "Пользовательское значение сброшено")
    return RedirectResponse(f"/admin/pages/{page_key}", status_code=303)


async def _reset_specific_field(request: Request, page_key: str, field: str, action: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    if not page_service.get_page_full(page_key):
        flash(request, "Страница не найдена", "warning")
        return RedirectResponse("/admin/pages", status_code=303)
    page_service.reset_page_custom_field(page_key, field)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], action, "page", page_key, {"field": field}, request)
    flash(request, "Пользовательское значение сброшено")
    return RedirectResponse(f"/admin/pages/{page_key}", status_code=303)


@router.post("/{page_key}/reset-text")
async def reset_page_text(request: Request, page_key: str):
    return await _reset_specific_field(request, page_key, "text", "page.reset_text")


@router.post("/{page_key}/reset-image")
async def reset_page_image(request: Request, page_key: str):
    return await _reset_specific_field(request, page_key, "image", "page.reset_image")


@router.post("/{page_key}/reset-buttons")
async def reset_page_buttons(request: Request, page_key: str):
    return await _reset_specific_field(request, page_key, "buttons", "page.reset_buttons")


@router.post("/{page_key}/copy-default-buttons")
async def copy_default_buttons(request: Request, page_key: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    if not page_service.get_page_full(page_key):
        flash(request, "Страница не найдена", "warning")
        return RedirectResponse("/admin/pages", status_code=303)
    result = page_service.copy_default_buttons_to_custom(page_key)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "page.copy_default_buttons", "page", page_key, result, request)
    flash(
        request,
        "Default buttons скопированы в custom" if result.get("copied") else "Default buttons пустые",
        "success" if result.get("copied") else "warning",
    )
    return RedirectResponse(f"/admin/pages/{page_key}/edit", status_code=303)


@router.post("/{page_key}/validate")
async def validate_page(
    request: Request,
    page_key: str,
    text_custom: str = Form(""),
    image_custom: str = Form(""),
    buttons_custom: str = Form(""),
):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    page = page_service.get_page_full(page_key)
    result = page_service.validate_page_payload(text_custom, image_custom, buttons_custom)
    if result.ok:
        flash(request, "HTML, изображение и JSON кнопок валидны")
    if page is None:
        page = {"page_key": page_key, "text_default": "", "buttons_default_pretty": "", "variables": []}
    page.update(
        {
            "text_custom": text_custom,
            "image_custom": image_custom,
            "buttons_custom_pretty": result.normalized_buttons or buttons_custom,
        }
    )
    return templates.TemplateResponse(
        request,
        "pages/edit.html",
        template_context(request, title=f"Редактировать {page_key}", page=page, errors=result.errors),
        status_code=200 if result.ok else 400,
    )
